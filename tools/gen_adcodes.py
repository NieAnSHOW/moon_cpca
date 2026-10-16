#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_adcodes.py -- authoritative generator for data/adcodes.mbt.

Reads the upstream adcodes CSV (columns: adcode,name,longitude,latitude),
derives an administrative Level for every row, and emits the MoonBit data
package file `data/adcodes.mbt` (Level enum + Rec struct + adcodes array).
It also ensures a `moon.pkg` exists next to the output file.

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

Exit semantics: 0 = product written and self-check passed; any non-zero
= nothing valid was produced (the previous product is left intact; the
product file is only replaced atomically after all checks pass).

Standard library only; zero network access.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
from pathlib import Path

EXPECTED_HEADER = ["adcode", "name", "longitude", "latitude"]
DEFAULT_CSV_REL = os.path.join(
    "chinese_province_city_area_mapper", "cpca", "resources", "adcodes.csv"
)
DEFAULT_OUT_REL = os.path.join("data", "adcodes.mbt")

ADCODE_RE = re.compile(r"^[0-9]{12}$")
# A trailing-comma-terminated record line inside the emitted array literal.
ENTRY_RE = re.compile(
    r'^  \{ adcode: "(?P<adcode>[0-9]{12})", '
    r'name: "(?P<name>(?:[^"\\]|\\.)*)", '
    r"level: (?P<level>Province|City|Area) \},$"
)
# P1 guard: the product must never contain a wall-clock date stamp.
TIMESTAMP_RE = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}")


def die(msg: str) -> "NoReturn":  # type: ignore[valid-type]
    sys.stderr.write("gen_adcodes: error: %s\n" % msg)
    sys.exit(2)


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


def load_records(csv_path: Path):
    """Read + validate the CSV; return (records, raw_sha256).

    records is a list of (adcode, name, level) in CSV row order (never sorted).
    Raises ValueError on any malformed input.
    """
    raw = csv_path.read_bytes()
    raw_sha = sha256_hex(raw)
    records = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError("CSV is empty (no header row)")
        if header != EXPECTED_HEADER:
            raise ValueError(
                "unexpected CSV header %r (expected %r)" % (header, EXPECTED_HEADER)
            )
        lineno = 1
        for row in reader:
            lineno += 1
            if not row:  # blank line (e.g. trailing newline handling)
                continue
            if len(row) != len(EXPECTED_HEADER):
                raise ValueError(
                    "CSV line %d: expected %d fields, got %d"
                    % (lineno, len(EXPECTED_HEADER), len(row))
                )
            adcode, name = row[0], row[1]
            if not ADCODE_RE.match(adcode):
                raise ValueError(
                    "CSV line %d: adcode %r is not 12 ASCII digits" % (lineno, adcode)
                )
            if not name:
                raise ValueError("CSV line %d: empty name" % lineno)
            records.append((adcode, name, derive_level(adcode)))
    if not records:
        raise ValueError("CSV contains no data rows")
    return records, raw_sha


def build_product_text(records, upstream_name: str, raw_sha: str) -> str:
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


def self_check(text: str, records, upstream_name: str, raw_sha: str) -> None:
    """Verify the generated text round-trips to exactly the input records.

    Raises ValueError on any mismatch. Runs BEFORE anything is written.
    """
    lines = text.split("\n")
    if lines[0] != "// 上游文件名: %s" % upstream_name:
        raise ValueError("self-check: upstream file-name header line mismatch")
    if lines[1] != "// 记录数: %d" % len(records):
        raise ValueError("self-check: record-count header line mismatch")
    if lines[2] != "// CSV 内容 sha256: %s" % raw_sha:
        raise ValueError("self-check: sha256 header line mismatch")
    if TIMESTAMP_RE.search(text):
        raise ValueError("self-check: product text contains a date-like timestamp")
    parsed = []
    for line in lines:
        m = ENTRY_RE.match(line)
        if m:
            parsed.append((m.group("adcode"), m.group("name"), m.group("level")))
    if len(parsed) != len(records):
        raise ValueError(
            "self-check: parsed %d record lines, expected %d"
            % (len(parsed), len(records))
        )
    for i, (got, want) in enumerate(zip(parsed, records)):
        adcode, name, level = want
        unescaped = (
            got[1]
            .replace("\\\\", "\x00")
            .replace('\\"', '"')
            .replace("\\n", "\n")
            .replace("\\r", "\r")
            .replace("\\t", "\t")
            .replace("\x00", "\\")
        )
        if got[0] != adcode or unescaped != name or got[2] != level:
            raise ValueError("self-check: record %d mismatch: %r vs %r" % (i, got, want))
    order = [p[0] for p in parsed]
    if order != [r[0] for r in records]:
        raise ValueError("self-check: record order deviates from CSV row order")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write via temp file + os.replace so a failure never corrupts the product."""
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def ensure_moon_pkg(out_path: Path) -> bool:
    """Ensure moon.pkg exists next to the output; return True if created."""
    pkg = out_path.parent / "moon.pkg"
    if pkg.exists():
        return False
    atomic_write_bytes(pkg, b"")
    return True


def main(argv=None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Generate data/adcodes.mbt from the upstream adcodes CSV.",
        epilog=(
            "Path resolution: defaults and relative --csv/--out values are "
            "resolved against the repository root (parent of tools/), "
            "not the current working directory."
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
    args = parser.parse_args(argv)

    csv_path = resolve_path(args.csv, root)
    out_path = resolve_path(args.out, root)

    if not csv_path.is_file():
        die("input CSV not found: %s" % csv_path)

    records, raw_sha = load_records(csv_path)  # ValueError -> die below
    upstream_name = csv_path.name

    text = build_product_text(records, upstream_name, raw_sha)
    try:
        self_check(text, records, upstream_name, raw_sha)
    except ValueError as exc:
        die(str(exc))

    # All checks passed -- only now touch the filesystem.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(out_path, text.encode("utf-8"))
    created_pkg = ensure_moon_pkg(out_path)

    counts = {"Province": 0, "City": 0, "Area": 0}
    for _, _, level in records:
        counts[level] += 1
    product_sha = sha256_hex(text.encode("utf-8"))
    print("generated: %s" % out_path)
    print("records: %d (Province=%d City=%d Area=%d)" % (
        len(records), counts["Province"], counts["City"], counts["Area"]))
    print("csv sha256: %s" % raw_sha)
    print("product sha256: %s" % product_sha)
    if created_pkg:
        print("created: %s" % (out_path.parent / "moon.pkg"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValueError as exc:
        die(str(exc))
    except OSError as exc:
        die("I/O failure: %s" % exc)
