#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_adcodes.py -- authoritative generator for data/adcodes.mbt.

Reads the upstream adcodes CSV (columns: adcode,name,longitude,latitude),
derives an administrative Level for every row, and emits the MoonBit data
package file `data/adcodes.mbt` (Level enum + Rec struct + adcodes array).
It also ensures a `moon.pkg` exists next to the output file.

Self-check contract (spec 4.4): generation success IMPLIES self-check
passed. The six contract checks -- 记录数 / 逐字段一致 / 等级分档 / 重名统计 /
行序一致 / 无经纬度字段 -- run against the WRITTEN bytes re-read from disk
(a staged temp file), not against in-memory text, so they catch generation
bugs rather than only emit-memory bugs. The staged file is promoted onto
the product path (atomic os.replace) only after ALL six checks pass. Any
failure means: exit code 2, non-empty stderr naming the failed check(s),
and a diagnostic report at <repo>/_build/gen_report.json while the
previous product stays byte-identical.

Input exception paths (spec 4.3, data spec section 4.3): every failure
before staging goes through the SAME clean error path -- exit 2, no Python
traceback, `gen_adcodes: error: ...` on stderr naming the SPECIFIC missing
item, nothing written to the product path, and a `status: "failed"` report
in which the six checks read `not_run`:
  1. 文件缺失 -- `--csv <nonexistent>`: stderr carries the requested path
     string verbatim plus the resolved absolute path.
  2. 只有表头无数据行 -- header-only CSV: stderr carries "无数据行 / no
     data rows".
  3. 缺列 -- header missing (or adding) an expected column: stderr names
     the missing/extra column(s), e.g. `缺少列: name (missing column(s):
     name)`. The exact 4-column header stays mandatory.
  4. CSV 无法解析 (malformed CSV) -- `csv.Error` raised by the reader while
     iterating (e.g. "field larger than field limit"): stderr names the
     CSV path plus the row where parsing stopped. `csv.Error` is NOT a
     ValueError, so it is translated at both read sites (header + rows)
     instead of reaching the top-level handler.

--no-network-check: opt-in process-wide zero-network assertion (spec 4.3,
PRD US-01 acceptance 3). Before ANY file I/O a `sys.addaudithook` (PEP 578)
is installed that raises on every socket/urllib network audit event
(socket.* -- getaddrinfo / gethostbyname* / addr / connect / sendto /
sendmsg / ... -- plus urllib.Request). Zero fired events -> the run
completes normally and the report records the pass; any fired event ->
exit 2 with a clear stderr message. The generator performs no network
calls regardless of the flag; the flag merely turns that fact into
machine-checkable evidence.

Input schema (spec 4.2, controller-verified data facts):
  adcode: ^[0-9]{6}0{6}$  -- all 3511 real adcodes end with "000000";
  name:   1..15 characters -- V-04: real maximum name length = 15.
A violating row is rejected BEFORE anything is written: clean error (exit
2, no traceback) carrying 行号 / 上游值 / 违规说明 on stderr, plus a
`line` / `csv_value` / `product_value` (="rejected") entry in the report.
A failed run therefore leaves the previous product byte-identical.

Path resolution rule: all default paths and relative --csv/--out paths are
resolved against the REPOSITORY ROOT (the parent of the directory that
contains this script), independent of the current working directory.
Running from the repo root therefore behaves identically.

Level derivation (verbatim upstream semantic,
chinese_province_city_area_mapper/cpca/__init__.py:51-56):
    take adcode[:6];
    endswith("0000") -> Province; endswith("00") -> City; else Area.

Source identification (product header comment) contains EXACTLY three
input-determined fields: upstream file name, record count, sha256 of the
raw CSV bytes. No wall-clock timestamp, no version string, no tool name --
regeneration from identical input must be byte-identical (diff = 0).

Exit semantics: 0 = product written and all six self-checks passed; 2 =
nothing valid was produced (diagnostic report written; previous product
intact).

Standard library only; zero network access.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, NoReturn, Optional, Tuple

EXPECTED_HEADER = ["adcode", "name", "longitude", "latitude"]
DEFAULT_CSV_REL = os.path.join(
    "chinese_province_city_area_mapper", "cpca", "resources", "adcodes.csv"
)
DEFAULT_OUT_REL = os.path.join("data", "adcodes.mbt")
# Diagnostic report path -- LOCKED, repo-relative; `_build/` is git-ignored.
REPORT_REL = os.path.join("_build", "gen_report.json")

# Input schema (spec 4.2): every adcode is 12 ASCII digits whose trailing
# six digits are zero; names are 1..15 characters.
ADCODE_RE = re.compile(r"^[0-9]{6}0{6}$")
NAME_MIN_LEN = 1
NAME_MAX_LEN = 15
# A trailing-comma-terminated record line inside the emitted array literal.
ENTRY_RE = re.compile(
    r'^  \{ adcode: "(?P<adcode>[0-9]{12})", '
    r'name: "(?P<name>(?:[^"\\]|\\.)*)", '
    r"level: (?P<level>Province|City|Area) \},$"
)
# P1 guard: the product must never contain a wall-clock date stamp.
TIMESTAMP_RE = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}")
# Check 6: the product must not carry longitude/latitude tokens (FR-11).
LONLAT_RE = re.compile(r"\b(?:longitude|latitude)\b")
# Inverse of escape_moonbit_string, which only emits \\ \" \n \r \t \u{XX}.
UNESCAPE_RE = re.compile(r'\\(?P<tok>\\|"|n|r|t|u\{[0-9A-Fa-f]+\})')

LEVELS = ("Province", "City", "Area")
CHECK_TITLES = {
    "record_count": "记录数",
    "field_match": "逐字段一致",
    "level_counts": "等级分档",
    "dup_names": "重名统计",
    "row_order": "行序一致",
    "no_lonlat": "无经纬度字段",
}
CHECK_IDS: Tuple[str, ...] = tuple(CHECK_TITLES)

Record = Tuple[str, str, str]

_REPORT_PATH: Optional[Path] = None
_UNESCAPE_MAP = {"\\": "\\", '"': '"', "n": "\n", "r": "\r", "t": "\t"}

# --- --no-network-check: process-wide zero-network assertion (PEP 578) ---
# Every standard socket/network audit event. The hook below additionally
# matches ANY event starting with "socket." (e.g. socket.__new__), so even
# creating an unconnected socket object counts as a violation -- the
# generator must use zero sockets, not merely zero connections.
NETWORK_AUDIT_EVENTS = frozenset(
    {
        "socket.getaddrinfo",
        "socket.gethostbyname",
        "socket.gethostbyname_ex",
        "socket.gethostbyaddr",
        "socket.getservbyname",
        "socket.getservbyport",
        "socket.addr",
        "socket.connect",
        "socket.sendto",
        "socket.sendmsg",
        "urllib.Request",
    }
)

_NETWORK_GUARD: Dict[str, Any] = {"enabled": False, "events": 0}


class NetworkCheckViolation(RuntimeError):
    """Raised by the audit hook when a network audit event fires."""


def _network_audit_hook(event: str, args: Tuple[Any, ...]) -> None:
    if not (event.startswith("socket.") or event in NETWORK_AUDIT_EVENTS):
        return
    _NETWORK_GUARD["events"] += 1
    raise NetworkCheckViolation(
        "network audit event fired under --no-network-check: %s %r" % (event, args)
    )


def install_network_guard() -> None:
    """Install a sys.addaudithook aborting on any socket/network event.

    Must be called BEFORE any file I/O so the whole run is covered.
    """
    sys.addaudithook(_network_audit_hook)
    _NETWORK_GUARD["enabled"] = True


def repo_root() -> Path:
    """Repository root = parent of the directory holding this script."""
    return Path(__file__).resolve().parent.parent


def resolve_path(value: str, root: Path) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = root / p
    return p


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def derive_level(adcode: str) -> str:
    """Upstream AddrInfo.rank semantics on adcode[:6] (cpca/__init__.py:51-56)."""
    prefix6 = adcode[:6]
    if prefix6.endswith("0000"):
        return "Province"
    if prefix6.endswith("00"):
        return "City"
    return "Area"


def escape_moonbit_string(s: str) -> str:
    """Escape a string for a MoonBit double-quoted literal (defensive)."""
    out = []
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20:
            out.append("\\u{%X}" % ord(ch))
        else:
            out.append(ch)
    return "".join(out)


def unescape_moonbit_string(s: str) -> str:
    """Exact inverse of escape_moonbit_string."""

    def repl(m: "re.Match[str]") -> str:
        tok = m.group("tok")
        if tok in _UNESCAPE_MAP:
            return _UNESCAPE_MAP[tok]
        return chr(int(tok[2:-1], 16))  # u{XX}

    return UNESCAPE_RE.sub(repl, s)


def malformed_csv_error(csv_path: Path, lineno: int, exc: "csv.Error") -> ValueError:
    """Translate a csv.Error into the module's clean-path ValueError.

    `csv.Error` (e.g. "field larger than field limit (131072)") is raised
    lazily by `csv.reader` and is NOT a ValueError, so it would escape the
    top-level handler as a Python traceback with exit 1. Both read sites
    funnel it here so the run keeps its contract: exit 2, no traceback, and
    stderr naming the offending input file plus the row that stopped it.
    """
    return ValueError(
        "malformed CSV (CSV 解析失败): %s (第 %d 行起): %s" % (csv_path, lineno, exc)
    )


def load_records(csv_path: Path) -> Tuple[List[Record], List[Dict[str, Any]], str]:
    """Read + schema-check the CSV.

    Returns (records, violations, raw_sha256):
      records    -- (adcode, name, level) in CSV row order (never sorted);
      violations -- one dict per rejected row with keys `line` (CSV row
                    number including the header), `csv_value` (offending
                    raw value), `product_value` ("rejected") and `reason`
                    (违规说明).
    Raises ValueError for whole-file defects (empty file, bad header).
    """
    raw = csv_path.read_bytes()
    raw_sha = sha256_hex(raw)
    records: List[Record] = []
    violations: List[Dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError("CSV is empty (no header row)")
        except csv.Error as exc:
            raise malformed_csv_error(csv_path, 1, exc)
        if header != EXPECTED_HEADER:
            # Name the SPECIFIC missing/extra columns (spec 4.3: stderr must
            # identify the missing item, e.g. 缺少列: name). The exact
            # 4-column header stays mandatory.
            missing = [c for c in EXPECTED_HEADER if c not in header]
            extra = [c for c in header if c not in EXPECTED_HEADER]
            parts = ["CSV 表头不符 (unexpected CSV header)"]
            if missing:
                parts.append(
                    "缺少列: %s (missing column(s): %s)"
                    % (",".join(missing), ",".join(missing))
                )
            if extra:
                parts.append(
                    "多出列: %s (extra column(s): %s)"
                    % (",".join(extra), ",".join(extra))
                )
            if not missing and not extra:
                parts.append(
                    "列集合相同但顺序/重复不符 (same column set, wrong order or duplicates)"
                )
            parts.append("got %r" % (header,))
            parts.append("expected %r" % (EXPECTED_HEADER,))
            raise ValueError("; ".join(parts))
        lineno = 1  # header occupies line 1; data row i sits on line i+1
        try:
            for row in reader:
                lineno += 1
                if not row:  # blank line (e.g. trailing newline handling)
                    continue
                if len(row) != len(EXPECTED_HEADER):
                    violations.append(
                        {
                            "line": lineno,
                            "csv_value": ",".join(row),
                            "product_value": "rejected",
                            "reason": "expected %d fields, got %d"
                            % (len(EXPECTED_HEADER), len(row)),
                        }
                    )
                    continue
                adcode, name = row[0], row[1]
                if not ADCODE_RE.match(adcode):
                    violations.append(
                        {
                            "line": lineno,
                            "csv_value": adcode,
                            "product_value": "rejected",
                            "reason": "adcode 不匹配 ^[0-9]{6}0{6}$（12 位数字且第 7-12 位须全为 0）",
                        }
                    )
                    continue
                if not (NAME_MIN_LEN <= len(name) <= NAME_MAX_LEN):
                    violations.append(
                        {
                            "line": lineno,
                            "csv_value": name,
                            "product_value": "rejected",
                            "reason": "name 长度须在 %d..%d 之间（实测 %d 字符）"
                            % (NAME_MIN_LEN, NAME_MAX_LEN, len(name)),
                        }
                    )
                    continue
                records.append((adcode, name, derive_level(adcode)))
        except csv.Error as exc:
            # csv.Error is not a ValueError and would otherwise escape the
            # top-level handler as a traceback with exit 1 (I-1).
            raise malformed_csv_error(csv_path, lineno + 1, exc)
    if not records and not violations:
        raise ValueError(
            "CSV 只有表头、无数据行 (header-only CSV: no data rows found "
            "after the header; at least one data row is required)"
        )
    return records, violations, raw_sha


def build_product_text(records: List[Record], upstream_name: str, raw_sha: str) -> str:
    lines = []
    # Header comment: ONLY the three input-determined fields (spec 4.3).
    lines.append("// 上游文件名: %s" % upstream_name)
    lines.append("// 记录数: %d" % len(records))
    lines.append("// CSV 内容 sha256: %s" % raw_sha)
    lines.append("///|")
    lines.append("pub enum Level {")
    lines.append("  Province")
    lines.append("  City")
    lines.append("  Area")
    lines.append("}")
    lines.append("")
    lines.append("///|")
    lines.append("pub struct Rec {")
    lines.append("  adcode : String")
    lines.append("  name : String")
    lines.append("  level : Level")
    lines.append("}")
    lines.append("")
    lines.append("///|")
    lines.append("pub let adcodes : Array[Rec] = [")
    for adcode, name, level in records:
        lines.append(
            '  { adcode: "%s", name: "%s", level: %s },'
            % (escape_moonbit_string(adcode), escape_moonbit_string(name), level)
        )
    lines.append("]")
    return "\n".join(lines) + "\n"


def parse_product_entries(text: str) -> List[Record]:
    """Re-parse emitted record lines into (adcode, name, level) tuples."""
    entries: List[Record] = []
    for line in text.split("\n"):
        m = ENTRY_RE.match(line)
        if m:
            entries.append(
                (
                    m.group("adcode"),
                    unescape_moonbit_string(m.group("name")),
                    m.group("level"),
                )
            )
    return entries


def prewrite_emit_check(
    text: str, records: List[Record], upstream_name: str, raw_sha: str
) -> None:
    """In-memory emit round-trip check, run BEFORE anything touches disk.

    Raises ValueError on any mismatch. The authoritative six checks below
    re-verify the staged bytes from disk; this is a cheap early gate.
    """
    lines = text.split("\n")
    if lines[0] != "// 上游文件名: %s" % upstream_name:
        raise ValueError("upstream file-name header line mismatch")
    if lines[1] != "// 记录数: %d" % len(records):
        raise ValueError("record-count header line mismatch")
    if lines[2] != "// CSV 内容 sha256: %s" % raw_sha:
        raise ValueError("sha256 header line mismatch")
    if TIMESTAMP_RE.search(text):
        raise ValueError("product text contains a date-like timestamp (P1)")
    parsed = parse_product_entries(text)
    if len(parsed) != len(records):
        raise ValueError(
            "parsed %d record lines, expected %d" % (len(parsed), len(records))
        )
    for i, (got, want) in enumerate(zip(parsed, records)):
        if got != want:
            raise ValueError(
                "emit round-trip mismatch at record %d: %r vs %r" % (i + 1, got, want)
            )


def dup_name_map(names: List[str]) -> Dict[str, int]:
    counts = Counter(names)
    return {n: c for n, c in counts.items() if c > 1}


def run_six_checks(text: str, records: List[Record]) -> Dict[str, Any]:
    """The six spec 4.4 checks: staged product text (re-read from disk) vs CSV.

    Returns a dict keyed by check id; each entry carries `title`, `pass`,
    `status`, per-check stats and a `details` array (mismatch items carry
    `line` / `csv_value` / `product_value` where a row identity exists).
    """
    prod = parse_product_entries(text)
    checks: Dict[str, Any] = {}

    def check(cid: str, ok: bool, **stats: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "title": CHECK_TITLES[cid],
            "pass": bool(ok),
            "status": "passed" if ok else "failed",
            "details": [],
        }
        payload.update(stats)
        checks[cid] = payload
        return payload

    # 1. 记录数: product record count == CSV data row count.
    c = check(
        "record_count",
        len(prod) == len(records),
        csv_count=len(records),
        product_count=len(prod),
    )
    if not c["pass"]:
        c["details"].append(
            {
                "csv_value": len(records),
                "product_value": len(prod),
                "reason": "记录数不一致",
            }
        )

    # 2. 逐字段一致: adcode/name per row; all mismatches recorded.
    details = []
    for i in range(min(len(prod), len(records))):
        if prod[i][:2] != records[i][:2]:
            details.append(
                {
                    "line": i + 2,  # header is line 1; data row i+1 -> line i+2
                    "csv_value": "%s,%s" % records[i][:2],
                    "product_value": "%s,%s" % prod[i][:2],
                }
            )
    c = check("field_match", not details, compared=min(len(prod), len(records)))
    c["details"] = details

    # 3. 等级分档: product level counts == counts derived from the CSV
    #    via the same adcode[:6] suffix rule.
    csv_levels = Counter(lv for _, _, lv in records)
    prod_levels = Counter(lv for _, _, lv in prod)
    csv_counts = {lv: csv_levels.get(lv, 0) for lv in LEVELS}
    prod_counts = {lv: prod_levels.get(lv, 0) for lv in LEVELS}
    details = [
        {"level": lv, "csv_value": csv_counts[lv], "product_value": prod_counts[lv]}
        for lv in LEVELS
        if csv_counts[lv] != prod_counts[lv]
    ]
    c = check("level_counts", not details, csv=csv_counts, product=prod_counts)
    c["details"] = details

    # 4. 重名统计: duplicate-name name-count and per-name entry counts.
    csv_dups = dup_name_map([n for _, n, _ in records])
    prod_dups = dup_name_map([n for _, n, _ in prod])
    first_line: Dict[str, int] = {}
    for i, (_, n, _) in enumerate(records):
        first_line.setdefault(n, i + 2)
    details = []
    for n in sorted(set(csv_dups) | set(prod_dups)):
        a, b = csv_dups.get(n, 0), prod_dups.get(n, 0)
        if a != b:
            details.append(
                {"name": n, "line": first_line.get(n), "csv_value": a, "product_value": b}
            )
    c = check(
        "dup_names",
        not details,
        csv={
            "unique_names": len(set(n for _, n, _ in records)),
            "duplicate_names": len(csv_dups),
        },
        product={
            "unique_names": len(set(n for _, n, _ in prod)),
            "duplicate_names": len(prod_dups),
        },
    )
    c["details"] = details

    # 5. 行序一致: product record N == CSV row N; first offset reported.
    details = []
    for i in range(min(len(prod), len(records))):
        if prod[i] != records[i]:
            details.append(
                {
                    "line": i + 2,
                    "csv_value": "%s,%s,%s" % records[i],
                    "product_value": "%s,%s,%s" % prod[i],
                    "reason": "首个行序偏移（产物第 %d 条 != CSV 第 %d 行）" % (i + 1, i + 1),
                }
            )
            break
    c = check(
        "row_order",
        len(prod) == len(records) and not details,
        compared=min(len(prod), len(records)),
    )
    c["details"] = details

    # 6. 无经纬度字段: no longitude/latitude token anywhere in the product.
    hits = LONLAT_RE.findall(text)
    c = check("no_lonlat", len(hits) == 0, hits=len(hits))
    if hits:
        c["details"].append(
            {
                "csv_value": 0,
                "product_value": len(hits),
                "reason": "产物文本含 longitude/latitude 记号",
            }
        )

    return checks


def not_run_checks() -> Dict[str, Any]:
    """Six-check placeholder for runs that failed before any staging."""
    return {
        cid: {
            "title": CHECK_TITLES[cid],
            "pass": None,
            "status": "not_run",
            "details": [],
        }
        for cid in CHECK_IDS
    }


def write_report(payload: Dict[str, Any]) -> Optional[str]:
    """Best-effort report write; never masks the primary outcome.

    Returns None when the report was written (or when no report path is
    configured), else the OSError text -- callers echo that through
    `report_line`, so a `report: <path>` pointer never names a file that
    does not exist (M-1).
    """
    if _REPORT_PATH is None:
        return None
    try:
        _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _REPORT_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        return str(exc)
    return None


def report_line(err: Optional[str]) -> str:
    """The `report: <path>` line for `err` = write_report()'s result."""
    if _REPORT_PATH is None:
        return ""
    if err is None:
        return "report: %s" % _REPORT_PATH
    return "report: %s (NOT written: %s)" % (_REPORT_PATH, err)


def fail_run(
    error: str,
    csv_info: Optional[Dict[str, Any]] = None,
    input_violations: Optional[List[Dict[str, Any]]] = None,
    checks: Optional[Dict[str, Any]] = None,
    staged_tmp: Optional[Path] = None,
) -> NoReturn:
    """Report a failed run: report file + non-empty stderr + exit 2.

    The product is never updated on this path (any staged temp file is
    removed here, and input violations are rejected before staging).
    """
    payload: Dict[str, Any] = {"status": "failed", "error": error}
    if csv_info is not None:
        payload["csv"] = csv_info
    if input_violations is not None:
        payload["input_validation"] = {
            "pass": not input_violations,
            "violations": input_violations,
        }
    payload["checks"] = checks if checks is not None else not_run_checks()
    if staged_tmp is not None:
        try:
            staged_tmp.unlink()
        except OSError:
            pass
    sys.stderr.write("gen_adcodes: error: %s\n" % error)
    if input_violations:
        sys.stderr.write("failed stage: input_validation(输入校验)\n")
        for v in input_violations[:10]:
            sys.stderr.write(
                "  CSV 第 %s 行: 上游值 %r — 违规说明: %s\n"
                % (v["line"], v["csv_value"], v["reason"])
            )
        if len(input_violations) > 10:
            sys.stderr.write(
                "  ... 共 %d 处违规（完整清单见报告）\n" % len(input_violations)
            )
    if checks is not None:
        failed = [cid for cid in CHECK_IDS if checks[cid].get("pass") is False]
        if failed:
            sys.stderr.write(
                "failed checks: %s\n"
                % ", ".join("%s(%s)" % (CHECK_TITLES[cid], cid) for cid in failed)
            )
            for cid in failed:
                for d in checks[cid]["details"][:10]:
                    sys.stderr.write(
                        "  [%s] %s\n" % (CHECK_TITLES[cid], json.dumps(d, ensure_ascii=False))
                    )
    line = report_line(write_report(payload))
    if line:
        sys.stderr.write(line + "\n")
    sys.exit(2)


def stage_bytes(path: Path, data: bytes) -> Path:
    """Write data to a fsync'd temp file next to path; return the temp path.

    The caller promotes the temp file only after all checks pass, so a
    failed run never corrupts an existing product.
    """
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return tmp


def promote(tmp: Path, path: Path) -> None:
    os.replace(tmp, path)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    promote(stage_bytes(path, data), path)


def ensure_moon_pkg(out_path: Path) -> bool:
    """Ensure moon.pkg exists next to the output; return True if created."""
    pkg = out_path.parent / "moon.pkg"
    if pkg.exists():
        return False
    atomic_write_bytes(pkg, b"")
    return True


def main(argv: Optional[List[str]] = None) -> int:
    global _REPORT_PATH
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Generate data/adcodes.mbt from the upstream adcodes CSV.",
        epilog=(
            "Path resolution: defaults and relative --csv/--out values are "
            "resolved against the repository root (parent of tools/), "
            "not the current working directory. The diagnostic report is "
            "always written to <repo>/%s." % REPORT_REL
        ),
    )
    parser.add_argument(
        "--csv",
        default=DEFAULT_CSV_REL,
        help="input CSV path (default: %(default)s, repo-root relative)",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT_REL,
        help="output .mbt path (default: %(default)s, repo-root relative)",
    )
    parser.add_argument(
        "--no-network-check",
        action="store_true",
        help=(
            "opt-in zero-network assertion: install a process-wide "
            "sys.addaudithook BEFORE any file I/O that aborts (exit 2) if "
            "any socket/urllib network audit event fires; a clean run "
            "proves the generation made zero network calls"
        ),
    )
    args = parser.parse_args(argv)

    # Zero-network assertion must be active BEFORE any file I/O (PEP 578).
    if args.no_network_check:
        install_network_guard()

    csv_path = resolve_path(args.csv, root)
    out_path = resolve_path(args.out, root)
    _REPORT_PATH = root / REPORT_REL

    if not csv_path.is_file():
        # 文件缺失: stderr carries the requested path string VERBATIM plus
        # the resolved absolute path; report written; product untouched.
        fail_run(
            "input CSV not found (文件不存在): %s (requested: %s; resolved: %s)"
            % (args.csv, args.csv, csv_path),
            csv_info={"requested": args.csv, "path": str(csv_path)},
        )

    try:
        records, violations, raw_sha = load_records(csv_path)
    except ValueError as exc:
        fail_run(
            "invalid input CSV: %s" % exc,
            csv_info={
                "requested": args.csv,
                "path": str(csv_path),
                "file_name": csv_path.name,
            },
        )

    upstream_name = csv_path.name
    csv_info = {
        "path": str(csv_path),
        "file_name": upstream_name,
        "sha256": raw_sha,
    }

    # Input schema violations are fatal BEFORE any write (spec 4.2/4.3):
    # the previous product stays byte-identical on this path.
    if violations:
        fail_run(
            "input schema violation(s): %d row(s) rejected" % len(violations),
            csv_info=csv_info,
            input_violations=violations,
        )
    csv_info["data_rows"] = len(records)

    text = build_product_text(records, upstream_name, raw_sha)
    try:
        prewrite_emit_check(text, records, upstream_name, raw_sha)
    except ValueError as exc:
        fail_run("emit pre-check: %s" % exc, csv_info=csv_info)

    # Stage the product, then run the six self-checks against the staged
    # bytes RE-READ FROM DISK. Promotion happens only after ALL pass, so
    # generation success implies self-check passed.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    staged = stage_bytes(out_path, text.encode("utf-8"))
    try:
        written = staged.read_text(encoding="utf-8")
        checks = run_six_checks(written, records)
        failed = [cid for cid in CHECK_IDS if not checks[cid]["pass"]]
        if failed:
            fail_run(
                "self-check failed: %s"
                % ", ".join("%s(%s)" % (CHECK_TITLES[cid], cid) for cid in failed),
                csv_info=csv_info,
                checks=checks,
                staged_tmp=staged,
            )
        # moon.pkg is ensured BEFORE the product is promoted: a failure
        # here (OSError -> top-level fail_run) must leave the previous
        # product byte-identical, per the module contract (M-2). The staged
        # temp file is cleaned up by the except clause below.
        created_pkg = ensure_moon_pkg(out_path)
    except BaseException:
        try:
            staged.unlink()
        except OSError:
            pass
        raise
    promote(staged, out_path)

    level_counts = {lv: sum(1 for _, _, l in records if l == lv) for lv in LEVELS}
    names = [n for _, n, _ in records]
    dups = dup_name_map(names)
    summary = {
        "record_count": len(records),
        "csv_sha256": raw_sha,
        "level_counts": level_counts,
        "dup_names": {
            "unique_names": len(set(names)),
            "duplicate_names": len(dups),
            "duplicate_name_entries": sum(dups.values()),
        },
        "max_name_len": max(len(n) for n in names),
    }
    product_sha = sha256_hex(text.encode("utf-8"))
    report_payload: Dict[str, Any] = {
        "status": "passed",
        "generator": "tools/gen_adcodes.py",
        "csv": csv_info,
        "product": {
            "path": str(out_path),
            "sha256": product_sha,
            "records": len(records),
            "level_counts": level_counts,
        },
        "summary": summary,
        "checks": checks,
        "self_check": "generation success implies self-check passed "
        "(six checks re-parsed from disk)",
    }
    if _NETWORK_GUARD["enabled"]:
        report_payload["network_check"] = {
            "requested": True,
            "result": "passed",
            "socket_or_network_audit_events": _NETWORK_GUARD["events"],
        }

    print("generated: %s" % out_path)
    print(
        "records: %d (Province=%d City=%d Area=%d)"
        % (len(records), level_counts["Province"], level_counts["City"], level_counts["Area"])
    )
    print("csv sha256: %s" % raw_sha)
    print("product sha256: %s" % product_sha)
    print(
        "self-check: 6/6 passed (%s)"
        % " ".join("%s=ok" % cid for cid in CHECK_IDS)
    )
    if _NETWORK_GUARD["enabled"]:
        print(
            "network-check: passed (%d socket/network audit events)"
            % _NETWORK_GUARD["events"]
        )
    if created_pkg:
        print("created: %s" % (out_path.parent / "moon.pkg"))
    line = report_line(write_report(report_payload))
    if line:
        print(line)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except NetworkCheckViolation as exc:
        fail_run("network-check failed (零网络断言未通过): %s" % exc)
    except ValueError as exc:
        fail_run(str(exc))
    except OSError as exc:
        fail_run("I/O failure: %s" % exc)
