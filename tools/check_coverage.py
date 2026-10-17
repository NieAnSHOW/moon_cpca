#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_coverage.py -- machine checks for docs/moon_cpca-upstream-coverage.md.

Read-only. Verifies the upstream-coverage map contract (spec §3.5):

1. Document title/version and the exact 6-column header.
2. Exactly 14 data rows, sequential 序号 1..14.
3. Status enum is only ``精确`` / ``类型层 N/A``.
4. Every ``golden:<input>`` ID exists in testdata/golden.jsonl; for golden rows
   the 8-field expectation equals the golden record's ``expected`` object.
5. Every ``engine/<file>.mbt:<test name>`` ID resolves to a ``test "<name>"``
   block in that file (unknown file/test is an error, never skipped).
6. The 10 string ``test_transform`` inputs and the 2 ``test_umap`` inputs are
   covered by golden rows; the two umap inputs have a golden record carrying
   ``umap={"朝阳区":"110105"}``.
7. Row 14 cells are byte-for-byte the fixed §3.5 values, and the referenced
   wbtest body has BOTH a default call (no ``pos_sensitive`` argument) and an
   explicit ``pos_sensitive=false`` call, and asserts province_pos/city_pos/
   area_pos are all ``-1``.

Exit codes: 0 = all checks pass; 1 = contract violation (row number + raw ID
printed on stdout); 2 = unreadable document/golden file.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DOC = Path("docs") / "moon_cpca-upstream-coverage.md"
GOLDEN_REL = Path("testdata") / "golden.jsonl"

TITLE_LINE = "# moon_cpca 上游用例覆盖映射 v1"
HEADER = "| 序号 | 来源 | 输入 | 上游期望 8 字段 | moonbit_case_id | 状态 |"
STATUSES = ("精确", "类型层 N/A")
EXPECTED_ROWS = 14
FIELDS = (
    "province",
    "city",
    "area",
    "addr",
    "adcode",
    "province_pos",
    "city_pos",
    "area_pos",
)

# Upstream tests/test_cpca.py:30-53 -- the 10 string test_transform inputs.
TRANSFORM_STRINGS = (
    "徐汇区虹漕路461号58号楼5楼",
    "泉州市洛江区万安塘西工业区",
    "福建省鼓楼区鼓楼医院",
    "天津市",
    "我家的地址是江苏淮安清江浦区人民路111号",
    "我家的地址是江苏淮安清江浦区上海路111号",
    "上海市浦东新区东明路街道三林路15号",
    "贵州省黔南布依族苗族自治州长顺县长寨街道和平中路28号",
    "宁夏",
    "淮安市市辖区",
)

# Upstream test_umap inputs (same umap={"朝阳区": "110105"} call).
UMAP_INPUTS = ("朝阳区汉庭酒店大山子店", "吉林省朝阳区不知道店")
UMAP = {"朝阳区": "110105"}

ROW14 = {
    "source": "pos_sensitive=false 契约",
    "input": "11 条 test_transform 输入 × pos_sensitive=false/缺省",
    "expected": "无 pos 列（不适用）",
    "case_id": "engine/location_fields_wbtest.mbt:location_pos_default_minus_one",
    "status": "类型层 N/A",
}

SEPARATOR_RE = re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")
TEST_BLOCK_RE = re.compile(r'(?m)^test\s+"([^"]+)"\s*\{')
GOLDEN_ID_RE = re.compile(r"^golden:(.+)$", re.S)
ENGINE_ID_RE = re.compile(r"^engine/([^:]+\.mbt):([^:]+)$")


class CheckFailure(Exception):
    """A contract violation carrying the rendered stdout lines."""

    def __init__(self, lines):
        super().__init__("\n".join(lines))
        self.lines = lines


def read_text(path):
    return path.read_text(encoding="utf-8-sig")


def load_golden(path):
    """Return [(input, umap, expected_dict)] in file order."""
    records = []
    for lineno, raw in enumerate(read_text(path).splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CheckFailure(
                ["golden: testdata/golden.jsonl:%d malformed JSON: %s" % (lineno, exc)]
            )
        records.append((obj.get("input"), obj.get("umap"), obj.get("expected")))
    return records


def split_cells(line):
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def parse_table(text):
    """Return (data_rows, errors); each row is (seq_cell, source, input, expected, case_id, status)."""
    lines = text.splitlines()
    header_idx = None
    for idx, line in enumerate(lines):
        if line.strip() == HEADER:
            header_idx = idx
            break
    if header_idx is None:
        raise CheckFailure(["表头不匹配: 期望逐字 `%s`" % HEADER])
    if header_idx + 1 >= len(lines) or not SEPARATOR_RE.match(lines[header_idx + 1].strip()):
        raise CheckFailure(["表头不匹配: 表头下一行不是分隔行"])

    rows = []
    errors = []
    idx = header_idx + 2
    while idx < len(lines) and lines[idx].strip().startswith("|"):
        cells = split_cells(lines[idx])
        if len(cells) != 6:
            errors.append("行 %d: 列数 %d != 6" % (len(rows) + 1, len(cells)))
        else:
            rows.append(tuple(cells))
        idx += 1
    return rows, errors


def strip_comments(text):
    """Remove // comments while preserving string/char literals."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
            out.append(c)
            i += 1
            while i < n:
                out.append(text[i])
                if text[i] == "\\" and i + 1 < n:
                    out.append(text[i + 1])
                    i += 2
                    continue
                i += 1
                if text[i - 1] == '"':
                    break
            continue
        if c == "'":
            out.append(c)
            i += 1
            while i < n:
                out.append(text[i])
                if text[i] == "\\" and i + 1 < n:
                    out.append(text[i + 1])
                    i += 2
                    continue
                i += 1
                if text[i - 1] == "'":
                    break
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def find_matching(text, open_idx, open_ch, close_ch):
    """Index of the matching closer for text[open_idx] == open_ch, or -1."""
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"' or c == "'":
            quote = c
            i += 1
            while i < n:
                if text[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                if text[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def test_bodies(text):
    """Map test name -> body text (comments stripped) for every `test "name" {` block."""
    bodies = {}
    for match in TEST_BLOCK_RE.finditer(text):
        open_idx = match.end() - 1
        close_idx = find_matching(text, open_idx, "{", "}")
        if close_idx < 0:
            continue
        bodies.setdefault(match.group(1), strip_comments(text[open_idx + 1 : close_idx]))
    return bodies


def extract_calls(body):
    """Return the top-level argument lists of every bare `extract(...)` call."""
    calls = []
    for match in re.finditer(r"(?<![\w.])extract\s*\(", body):
        open_idx = match.end() - 1
        close_idx = find_matching(body, open_idx, "(", ")")
        if close_idx < 0:
            continue
        args_text = body[open_idx + 1 : close_idx]
        args = []
        depth = 0
        start = 0
        i = 0
        while i < len(args_text):
            c = args_text[i]
            if c == '"' or c == "'":
                quote = c
                i += 1
                while i < len(args_text):
                    if args_text[i] == "\\" and i + 1 < len(args_text):
                        i += 2
                        continue
                    if args_text[i] == quote:
                        i += 1
                        break
                    i += 1
                continue
            if c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
            elif c == "," and depth == 0:
                args.append(args_text[start:i].strip())
                start = i + 1
            i += 1
        tail = args_text[start:].strip()
        if tail:
            args.append(tail)
        calls.append(args)
    return calls


def check_pos_test(body, row_no, raw_id):
    """Validate the pos_sensitive=false wbtest body; return error lines."""
    errors = []
    calls = extract_calls(body)
    default_calls = [a for a in calls if not any("pos_sensitive" in arg for arg in a)]
    false_calls = [
        a
        for a in calls
        if any(re.match(r"^pos_sensitive\s*=\s*false$", arg) for arg in a)
    ]
    if not default_calls:
        errors.append(
            "行 %d: %s body 缺少不传 pos_sensitive 的默认调用" % (row_no, raw_id)
        )
    if not false_calls:
        errors.append(
            "行 %d: %s body 缺少显式 pos_sensitive=false 调用" % (row_no, raw_id)
        )
    for field in ("province_pos", "city_pos", "area_pos"):
        pattern = re.compile(
            r"\.\s*%s\s*,\s*content\s*=\s*\"-1\"" % re.escape(field)
        )
        if not pattern.search(body):
            errors.append(
                "行 %d: %s body 未断言 %s = -1" % (row_no, raw_id, field)
            )
    return errors


def check(doc_path):
    doc = read_text(doc_path)
    lines = doc.splitlines()
    errors = []

    if not any(line.strip() == TITLE_LINE for line in lines):
        errors.append("标题不匹配: 期望逐字 `%s`" % TITLE_LINE)
    if not any(re.search(r"版本：\s*v1\b", line) for line in lines):
        errors.append("版本缺失: 期望 `版本：v1`")

    rows, parse_errors = parse_table(doc)
    errors.extend(parse_errors)

    if len(rows) != EXPECTED_ROWS:
        errors.append("行数 %d != %d" % (len(rows), EXPECTED_ROWS))

    golden_records = load_golden(ROOT / GOLDEN_REL)
    golden_by_key = {}
    for input_value, umap_value, expected in golden_records:
        golden_by_key[(input_value, json.dumps(umap_value, ensure_ascii=False))] = expected
    covered_inputs = set()
    wbtest_cache = {}

    for idx, row in enumerate(rows, 1):
        seq_cell, source, input_cell, expected_cell, case_cell, status = row
        raw_id = case_cell
        case_id = case_cell.strip("`").strip()

        try:
            if int(seq_cell) != idx:
                errors.append("行 %d: 序号 `%s` != %d" % (idx, seq_cell, idx))
        except ValueError:
            errors.append("行 %d: 序号 `%s` 不是整数" % (idx, seq_cell))

        if status not in STATUSES:
            errors.append(
                "行 %d: 状态 `%s` 不在 {%s}" % (idx, status, ", ".join(STATUSES))
            )

        if idx == EXPECTED_ROWS:
            if source != ROW14["source"]:
                errors.append(
                    "行 %d: 来源 `%s` != `%s`" % (idx, source, ROW14["source"])
                )
            if input_cell != ROW14["input"]:
                errors.append(
                    "行 %d: 输入 `%s` != `%s`" % (idx, input_cell, ROW14["input"])
                )
            if expected_cell != ROW14["expected"]:
                errors.append(
                    "行 %d: 上游期望 8 字段 `%s` != `%s`"
                    % (idx, expected_cell, ROW14["expected"])
                )
            if case_id != ROW14["case_id"]:
                errors.append(
                    "行 %d: moonbit_case_id `%s` != `%s`"
                    % (idx, raw_id, ROW14["case_id"])
                )
            if status != ROW14["status"]:
                errors.append(
                    "行 %d: 状态 `%s` != `%s`" % (idx, status, ROW14["status"])
                )

        golden_match = GOLDEN_ID_RE.match(case_id)
        engine_match = ENGINE_ID_RE.match(case_id)
        if golden_match:
            input_value = golden_match.group(1)
            if not input_value:
                errors.append("行 %d: 空 golden 输入: `%s`" % (idx, raw_id))
                continue
            if input_value not in {rec[0] for rec in golden_records}:
                errors.append(
                    "行 %d: 未知 golden 输入: `%s`" % (idx, raw_id)
                )
                continue
            covered_inputs.add(input_value)

            use_umap = "umap" in source.lower()
            key = (input_value, json.dumps(UMAP if use_umap else None, ensure_ascii=False))
            expected = golden_by_key.get(key)
            if expected is None:
                errors.append(
                    "行 %d: golden 记录缺失（input=%s umap=%s）: `%s`"
                    % (idx, input_value, UMAP if use_umap else None, raw_id)
                )
                continue
            try:
                doc_expected = json.loads(expected_cell)
            except json.JSONDecodeError:
                errors.append(
                    "行 %d: 上游期望 8 字段不是合法 JSON: `%s`" % (idx, expected_cell)
                )
                continue
            if not isinstance(doc_expected, dict) or set(doc_expected) != set(FIELDS):
                errors.append(
                    "行 %d: 上游期望 8 字段键集不符: `%s`" % (idx, expected_cell)
                )
                continue
            if doc_expected != expected:
                errors.append(
                    "行 %d: 上游期望 8 字段与 golden 记录不一致: `%s`"
                    % (idx, raw_id)
                )
        elif engine_match:
            rel_file, test_name = engine_match.group(1), engine_match.group(2)
            file_path = (ROOT / "engine" / rel_file).resolve()
            engine_dir = (ROOT / "engine").resolve()
            if file_path.parent != engine_dir:
                errors.append(
                    "行 %d: 未知 wbtest 文件: `%s`" % (idx, raw_id)
                )
                continue
            if not file_path.is_file():
                errors.append(
                    "行 %d: 未知 wbtest 文件: `%s`" % (idx, raw_id)
                )
                continue
            bodies = wbtest_cache.get(file_path)
            if bodies is None:
                bodies = test_bodies(read_text(file_path))
                wbtest_cache[file_path] = bodies
            if test_name not in bodies:
                errors.append(
                    "行 %d: 未知 test name: `%s`" % (idx, raw_id)
                )
                continue
            if idx == EXPECTED_ROWS:
                errors.extend(check_pos_test(bodies[test_name], idx, raw_id))
        else:
            errors.append("行 %d: 未知 moonbit_case_id 前缀: `%s`" % (idx, raw_id))

    # Row 14 must be the pos_sensitive=false wbtest, not a golden row.
    if len(rows) >= EXPECTED_ROWS:
        last_case = rows[EXPECTED_ROWS - 1][4].strip("`").strip()
        if not ENGINE_ID_RE.match(last_case):
            errors.append("行 %d: 必须使用 wbtest ID，实际 `%s`" % (EXPECTED_ROWS, last_case))

    for input_value in TRANSFORM_STRINGS:
        if input_value not in covered_inputs:
            errors.append("覆盖缺失: test_transform 输入 `%s` 无 golden 行" % input_value)
    for input_value in UMAP_INPUTS:
        if input_value not in covered_inputs:
            errors.append("覆盖缺失: test_umap 输入 `%s` 无 golden 行" % input_value)
        key = (input_value, json.dumps(UMAP, ensure_ascii=False))
        if key not in golden_by_key:
            errors.append(
                "覆盖缺失: test_umap 输入 `%s` 在 golden.jsonl 中无 umap={\"朝阳区\":\"110105\"} 记录"
                % input_value
            )

    if errors:
        raise CheckFailure(errors)
    return len(rows)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Validate docs/moon_cpca-upstream-coverage.md against golden.jsonl and wbtests."
    )
    parser.add_argument(
        "--doc",
        default=str(DEFAULT_DOC),
        help="coverage map path (default: %(default)s)",
    )
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    doc_path = Path(args.doc)
    if not doc_path.is_file():
        print("FAIL: 文档不存在: %s" % args.doc)
        return 2
    if not (ROOT / GOLDEN_REL).is_file():
        print("FAIL: golden 文件不存在: %s" % GOLDEN_REL.as_posix())
        return 2
    try:
        row_count = check(doc_path)
    except CheckFailure as exc:
        for line in exc.lines:
            print(line)
        print("FAIL: coverage check failed (%d issue(s))" % len(exc.lines))
        return 1
    print("PASS: %d rows; statuses, IDs, row 14 and pos_sensitive=false body verified" % row_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
