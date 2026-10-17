#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_artifact.py -- read-only machine checks for data/adcodes.mbt.

Compares the generated product (data/adcodes.mbt) against the upstream
CSV (chinese_province_city_area_mapper/cpca/resources/adcodes.csv).
READ-ONLY: this script never writes, creates, or modifies any file.

Subswitches (multiple allowed in one invocation):
  --records      product array element count == CSV data row count.
  --fields       every product record's adcode+name equals the CSV row at
                 the same position, in order; any mismatch lists position,
                 csv value and product value.
  --levels       per-Level counts (Province/City/Area) equal the counts
                 derived from the CSV via the adcode[:6] suffix rule
                 (endswith "0000" -> Province, "00" -> City, else Area);
                 also every product record's own level must be consistent
                 with that rule.
  --dup          duplicate-name statistics (distinct names, count of names
                 appearing more than once, total entries sharing a
                 duplicated name) vs the same stats on the CSV.
  --dup <名称>    entry count for one name + its full 12-digit adcode set
                 (existence check: PASS iff count >= 1). Adcodes are always
                 printed in their original 12-digit form; no digit-count
                 normalization is performed anywhere (口径 = 12 位原值).
  --order        spot checks: product record 1 == CSV data row 1
                 (500233000000, 忠县) and further positions spread across
                 the file (100, 1000, 2500, last) match exactly.

Exit codes: 0 = all requested checks pass; 1 = any requested check fails;
2 = usage error or I/O error (product/CSV unreadable or the product cannot
be parsed at all).

Standard library only (argparse/csv/re/sys/pathlib); zero network. Default
paths resolve against the REPOSITORY ROOT (parent of tools/), independent
of the current working directory. The upstream CSV is consumed strictly by
column position 0 (adcode) and 1 (name); all other columns are ignored.
"""

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

PRODUCT_REL = Path("data") / "adcodes.mbt"
CSV_REL = (
    Path("chinese_province_city_area_mapper")
    / "cpca"
    / "resources"
    / "adcodes.csv"
)

LEVELS = ("Province", "City", "Area")

# Record grammar inside the emitted array literal. Accepts the raw shape
# produced by tools/gen_adcodes.py, the single-line formatted shape with a
# trailing comma after `level`, and the wrapped multi-line block emitted by
# `moon fmt` for long names. Whitespace (including newlines) between block
# tokens is insignificant; field order, field names and the trailing comma
# after the closing brace are not. The name group keeps escape sequences
# intact (\" \\ \n \r \t \u{XX}); real data has none, but parsing is
# defensive.
ENTRY_RE = re.compile(
    r'\{\s*adcode:\s*"(?P<adcode>[0-9]{12})"\s*,\s*'
    r'name:\s*"(?P<name>(?:[^"\\]|\\.)*)"\s*,\s*'
    r"level:\s*(?P<level>Province|City|Area)\s*,?\s*\}\s*,",
    re.S,
)
ARRAY_OPEN_RE = re.compile(r"^pub let adcodes : Array\[Rec\] = \[$")
ARRAY_CLOSE_RE = re.compile(r"^\]$")
UNESCAPE_RE = re.compile(r'\\(?P<tok>\\|"|n|r|t|u\{[0-9A-Fa-f]+\})')
UNESCAPE_MAP = {"\\": "\\", '"': '"', "n": "\n", "r": "\r", "t": "\t"}

MAX_DETAILS = 20  # per-check detail lines printed to stderr


class ProductParseError(Exception):
    """The product file cannot be parsed at all (fatal, exit 2)."""


class CsvError(Exception):
    """The upstream CSV cannot be read as adcode/name rows (fatal, exit 2)."""


Record = tuple  # (adcode: str, name: str, level: str)


def repo_root() -> Path:
    """Repository root = parent of the directory holding this script."""
    return Path(__file__).resolve().parent.parent


def derive_level(adcode: str) -> str:
    """Upstream semantic on adcode[:6] (cpca/__init__.py:51-56)."""
    prefix6 = adcode[:6]
    if prefix6.endswith("0000"):
        return "Province"
    if prefix6.endswith("00"):
        return "City"
    return "Area"


def unescape_moonbit_string(s: str) -> str:
    def repl(m: "re.Match[str]") -> str:
        tok = m.group("tok")
        if tok in UNESCAPE_MAP:
            return UNESCAPE_MAP[tok]
        return chr(int(tok[2:-1], 16))  # u{XX}

    return UNESCAPE_RE.sub(repl, s)


def parse_product(text: str) -> list:
    """Structurally parse the generated .mbt into (adcode, name, level).

    Records may be single-line (raw or formatted) or wrapped across lines by
    `moon fmt`; whitespace between block tokens is insignificant. Raises
    ProductParseError when the array envelope is missing/malformed or any
    non-whitespace content in the array body is not a valid record.
    """
    lines = text.split("\n")
    try:
        open_idx = next(
            i for i, ln in enumerate(lines) if ARRAY_OPEN_RE.match(ln)
        )
    except StopIteration:
        raise ProductParseError(
            "未找到数组声明行 'pub let adcodes : Array[Rec] = ['"
        )
    try:
        close_idx = next(
            i for i in range(open_idx + 1, len(lines))
            if ARRAY_CLOSE_RE.match(lines[i])
        )
    except StopIteration:
        raise ProductParseError("未找到数组结束行 ']'")

    body_lines = lines[open_idx + 1:close_idx]
    body = "\n".join(body_lines)  # body_lines[0] is 1-based line open_idx+2

    def parse_error(offset: int) -> "ProductParseError":
        local = body.count("\n", 0, offset)
        return ProductParseError(
            "第 %d 行不是合法记录行: %r"
            % (open_idx + 2 + local, body_lines[local])
        )

    entries = []
    pos = 0
    while True:
        m = ENTRY_RE.search(body, pos)
        if m is None:
            rest = body[pos:]
            if rest.strip():
                raise parse_error(pos + len(rest) - len(rest.lstrip()))
            break
        gap = body[pos:m.start()]
        if gap.strip():
            raise parse_error(pos + len(gap) - len(gap.lstrip()))
        entries.append(
            (
                m.group("adcode"),
                unescape_moonbit_string(m.group("name")),
                m.group("level"),
            )
        )
        pos = m.end()
    return entries


def load_csv(csv_path: Path) -> list:
    """Read the CSV as (adcode, name, level) rows in file order.

    Only columns 0 (adcode) and 1 (name) are consumed; remaining columns
    are ignored. level is derived from adcode via the suffix rule.
    """
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        try:
            rows = [row for row in csv.reader(f) if row]
        except csv.Error as exc:
            # csv.Error is not caught by main's handler tuple; translate it
            # into the documented clean path (exit 2 + named input, I-1).
            raise CsvError("CSV 解析失败 (malformed CSV): %s" % exc)
    if not rows:
        raise CsvError("CSV 为空（无表头行）")
    header = rows[0]
    if len(header) < 2 or header[0] != "adcode" or header[1] != "name":
        raise CsvError(
            "CSV 表头前两列须为 adcode,name（实测 %r）" % (header[:2],)
        )
    records = []
    for lineno, row in enumerate(rows[1:], start=2):
        if len(row) < 2:
            raise CsvError("CSV 第 %d 行列数不足 2: %r" % (lineno, row))
        adcode, name = row[0], row[1]
        records.append((adcode, name, derive_level(adcode)))
    if not records:
        raise CsvError("CSV 只有表头、无数据行")
    return records


def fmt_pair(rec: Record) -> str:
    return "(%s, %s)" % (rec[0], rec[1])


def check_records(prod: list, csv_rows: list) -> tuple:
    ok = len(prod) == len(csv_rows)
    summary = "PASS --records: 产物记录数=%d, CSV 数据行=%d" % (
        len(prod),
        len(csv_rows),
    )
    details = []
    if not ok:
        summary = "FAIL --records: 产物记录数=%d, CSV 数据行=%d" % (
            len(prod),
            len(csv_rows),
        )
        details.append(
            "记录数不一致: csv_value=%d, product_value=%d"
            % (len(csv_rows), len(prod))
        )
    return ok, summary, details


def check_fields(prod: list, csv_rows: list) -> tuple:
    details = []
    compared = min(len(prod), len(csv_rows))
    for i in range(compared):
        p_adcode, p_name, _ = prod[i]
        c_adcode, c_name, _ = csv_rows[i]
        if p_adcode != c_adcode or p_name != c_name:
            details.append(
                "第 %d 条不一致: csv_value=%s, product_value=%s"
                % (
                    i + 1,
                    fmt_pair(csv_rows[i][:2]),
                    fmt_pair((p_adcode, p_name)),
                )
            )
    ok = not details
    summary = (
        "PASS --fields: 逐条 adcode/name 一致（比对 %d 条，按位置顺序）"
        % compared
        if ok
        else "FAIL --fields: %d 处 adcode/name 不一致（比对 %d 条）"
        % (len(details), compared)
    )
    return ok, summary, details


def check_levels(prod: list, csv_rows: list) -> tuple:
    csv_counts = Counter(lv for _, _, lv in csv_rows)
    prod_counts = Counter(lv for _, _, lv in prod)
    details = []
    for lv in LEVELS:
        if prod_counts.get(lv, 0) != csv_counts.get(lv, 0):
            details.append(
                "等级 %s 计数不一致: csv_value=%d, product_value=%d"
                % (lv, csv_counts.get(lv, 0), prod_counts.get(lv, 0))
            )
    for i, (adcode, _name, level) in enumerate(prod):
        derived = derive_level(adcode)
        if level != derived:
            details.append(
                "第 %d 条 level 与后缀规则矛盾: adcode=%s, "
                "product_value=%s, csv_value(derived)=%s"
                % (i + 1, adcode, level, derived)
            )
    ok = not details
    counts_txt = " ".join(
        "%s=%d/%d" % (lv, prod_counts.get(lv, 0), csv_counts.get(lv, 0))
        for lv in LEVELS
    )
    summary = (
        "PASS --levels: 三档计数 产物==CSV 派生 且逐条一致（%s，格式 等级=产物/CSV）"
        % counts_txt
        if ok
        else "FAIL --levels: %d 处不一致（%s）" % (len(details), counts_txt)
    )
    return ok, summary, details


def dup_stats(records: list) -> tuple:
    """(unique_names, dup_name_count, dup_entry_total)."""
    counts = Counter(n for _, n, _ in records)
    dups = {n: c for n, c in counts.items() if c > 1}
    return len(counts), len(dups), sum(dups.values())


def check_dup_stats(prod: list, csv_rows: list) -> tuple:
    p = dup_stats(prod)
    c = dup_stats(csv_rows)
    labels = ("名称唯一数", "重名名称数", "重名条目总数")
    details = [
        "%s 不一致: csv_value=%d, product_value=%d" % (lab, cv, pv)
        for lab, cv, pv in zip(labels, c, p)
        if cv != pv
    ]
    ok = not details
    stats_txt = " ".join(
        "%s: 产物=%d/CSV=%d" % (lab, pv, cv) for lab, cv, pv in zip(labels, c, p)
    )
    summary = (
        "PASS --dup: 重名统计一致（%s）" % stats_txt
        if ok
        else "FAIL --dup: 重名统计不一致（%s）" % stats_txt
    )
    return ok, summary, details


def check_dup_name(prod: list, name: str) -> tuple:
    adcodes = []
    for adcode, n, _ in prod:
        if n == name and adcode not in adcodes:
            adcodes.append(adcode)
    count = sum(1 for _, n, _ in prod if n == name)
    ok = count >= 1
    # 口径 label: adcodes are output as their original 12-digit values;
    # no digit-count normalization is performed anywhere.
    label = "口径: 12 位原值输出，未做任何位数归一"
    summary = "--dup %s: 条数=%d\n12 位 adcode 集合（%s）: %s" % (
        name,
        count,
        label,
        ", ".join(adcodes) if adcodes else "(空)",
    )
    if not ok:
        details = ["名称 %s 在产物中命中 0 条（存在性检查要求 >= 1）" % name]
        return False, "FAIL --dup: " + summary, details
    return True, "PASS --dup: " + summary, []


def check_order(prod: list, csv_rows: list) -> tuple:
    positions = sorted(
        {p for p in (1, 100, 1000, 2500, len(csv_rows)) if p <= len(csv_rows)}
    )
    details = []
    for pos in positions:
        if pos > len(prod):
            details.append(
                "产物不足 %d 条，无法抽查第 %d 条" % (pos, pos)
            )
            continue
        if tuple(prod[pos - 1]) != tuple(csv_rows[pos - 1]):
            details.append(
                "第 %d 条与 CSV 第 %d 行不一致: csv_value=%s, product_value=%s"
                % (pos, pos + 1, csv_rows[pos - 1], prod[pos - 1])
            )
    ok = not details
    summary = (
        "PASS --order: 抽查位置 %s 全部逐字一致（含首条 500233000000/忠县）"
        % ",".join(str(p) for p in positions)
        if ok
        else "FAIL --order: 抽查位置 %s 中 %d 处不一致"
        % (",".join(str(p) for p in positions), len(details))
    )
    return ok, summary, details


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_artifact.py",
        description="Read-only machine checks: data/adcodes.mbt vs upstream CSV.",
    )
    parser.add_argument(
        "--records", action="store_true", help="产物数组元素数 == CSV 数据行数"
    )
    parser.add_argument(
        "--fields", action="store_true", help="逐条 adcode/name 与 CSV 行一致"
    )
    parser.add_argument(
        "--levels", action="store_true", help="三档计数与后缀规则一致性"
    )
    parser.add_argument(
        "--dup",
        nargs="?",
        const="",
        default=None,
        metavar="名称",
        help="无参=重名统计; 带名称=该名称条数与 12 位 adcode 集合",
    )
    parser.add_argument(
        "--order", action="store_true", help="首条与抽查位置逐字一致"
    )
    return parser


def main(argv: "list[str] | None" = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)

    requested = []
    if args.records:
        requested.append("records")
    if args.fields:
        requested.append("fields")
    if args.levels:
        requested.append("levels")
    if args.dup is not None:
        requested.append("dup")
    if args.order:
        requested.append("order")
    if not requested:
        sys.stderr.write(
            "error: 未提供任何检查开关（--records/--fields/--levels/--dup/--order 之一）\n"
        )
        parser.print_usage(sys.stderr)
        return 2

    root = repo_root()
    product_path = root / PRODUCT_REL
    csv_path = root / CSV_REL

    try:
        text = product_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        sys.stderr.write(
            "check_artifact: error: 无法读取产物 %s: %s\n" % (product_path, exc)
        )
        return 2
    try:
        prod = parse_product(text)
    except ProductParseError as exc:
        sys.stderr.write(
            "check_artifact: error: 产物无法解析 (%s): %s\n" % (product_path, exc)
        )
        return 2
    try:
        csv_rows = load_csv(csv_path)
    except (OSError, UnicodeDecodeError, CsvError) as exc:
        sys.stderr.write(
            "check_artifact: error: 无法读取上游 CSV %s: %s\n" % (csv_path, exc)
        )
        return 2

    results = []
    if args.records:
        results.append(check_records(prod, csv_rows))
    if args.fields:
        results.append(check_fields(prod, csv_rows))
    if args.levels:
        results.append(check_levels(prod, csv_rows))
    if args.dup is not None:
        if args.dup == "":
            results.append(check_dup_stats(prod, csv_rows))
        else:
            results.append(check_dup_name(prod, args.dup))
    if args.order:
        results.append(check_order(prod, csv_rows))

    all_ok = True
    for ok, summary, details in results:
        print(summary)
        if not ok:
            all_ok = False
            sys.stderr.write(summary + "\n")
            for d in details[:MAX_DETAILS]:
                sys.stderr.write("  " + d + "\n")
            if len(details) > MAX_DETAILS:
                sys.stderr.write(
                    "  ... 另有 %d 处未列出\n" % (len(details) - MAX_DETAILS)
                )
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
