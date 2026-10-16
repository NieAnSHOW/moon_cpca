#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-03 双产物一致性专检：testdata/golden.jsonl ↔ testdata/golden.mbt 逐项对账。

契约（引擎 spec §4.4 / brief 步 5）：断言两产物的
- 用例条数
- 每条 input / umap / expected 8 字段值 / upstream_version
逐项相等；另核 jsonl 行字段锁定 4 字段（不得有第五字段）、expected 恰为
8 字段、逐行与文件级版本标识 = cpca 实际 __version__——后者通过对 vendored
chinese_province_city_area_mapper/cpca/__init__.py 的 VERSION 元组直读解析
（不 import，避免副作用；该目录为只读 vendored、不入库，缺失时打印 NOTE 跳过
该单项，0.5.5 外部锚由 testdata/golden_test.mbt 的版本断言承担）。
不一致 = 非 0 退出并打印差异；一致 = exit 0 + OK 汇总行。

.mbt 解析 = 针对 tools/gen_golden.py 固定序列化形态的递归下降回解
（ grammar 子集：JSON 风格字符串字面量 / Int / None / Some(x) / 元组 /
数组 / 具名字段结构体字面量），不做通用 MoonBit 解析。
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONL_PATH = os.path.join(ROOT, "testdata", "golden.jsonl")
MBT_PATH = os.path.join(ROOT, "testdata", "golden.mbt")
CPCA_INIT_PATH = os.path.join(
    ROOT, "chinese_province_city_area_mapper", "cpca", "__init__.py"
)

EXPECTED_KEYS = [
    "province",
    "city",
    "area",
    "addr",
    "adcode",
    "province_pos",
    "city_pos",
    "area_pos",
]
OPT_KEYS = {"province", "city", "area", "addr", "adcode"}
ROW_KEYS = ["input", "umap", "expected", "upstream_version"]


# ---------------------------------------------------------------------------
# golden.mbt 回解器（gen_golden.py 输出形态的语法子集）
# ---------------------------------------------------------------------------
class MbtParser:
    def __init__(self, text):
        self.t = text
        self.i = 0
        self.n = len(text)

    def error(self, msg):
        ctx = self.t[max(0, self.i - 40): self.i + 40].replace("\n", "\\n")
        raise ValueError("mbt parse error at offset %d: %s | near: %r" % (self.i, msg, ctx))

    def skip_ws(self):
        while self.i < self.n:
            c = self.t[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif self.t.startswith("//", self.i):
                nl = self.t.find("\n", self.i)
                self.i = self.n if nl < 0 else nl + 1
            else:
                return

    def peek(self):
        self.skip_ws()
        if self.i >= self.n:
            self.error("unexpected EOF")
        return self.t[self.i]

    def expect(self, ch):
        if self.peek() != ch:
            self.error("expected %r got %r" % (ch, self.t[self.i]))
        self.i += 1

    def accept(self, s):
        """匹配关键字/符号（后随非标识符字符才成立）。"""
        self.skip_ws()
        if self.t.startswith(s, self.i):
            rest_ok = (
                s[-1] not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
                or self.i + len(s) >= self.n
                or not re.match(r"[A-Za-z0-9_]", self.t[self.i + len(s)])
            )
            if rest_ok:
                self.i += len(s)
                return True
        return False

    def parse_string(self):
        if self.peek() != '"':
            self.error("expected string literal")
        start = self.i
        self.i += 1
        out = []
        while True:
            if self.i >= self.n:
                self.error("unterminated string")
            c = self.t[self.i]
            if c == "\\":
                j = self.i + 1
                e = self.t[j]
                mapping = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
                if e in mapping:
                    out.append(mapping[e])
                    self.i = j + 1
                elif e == "u":
                    hexs = self.t[j + 1: j + 5]
                    if len(hexs) != 4 or not re.match(r"^[0-9a-fA-F]{4}$", hexs):
                        self.error("bad \\u escape")
                    cp = int(hexs, 16)
                    if 0xD800 <= cp <= 0xDBFF:  # 代理对（json.dumps ensure_ascii=False 不应产出；防御）
                        self.i = j + 5
                        if not self.t.startswith("\\u", self.i):
                            self.error("lone surrogate")
                        hexs2 = self.t[self.i + 2: self.i + 6]
                        cp2 = int(hexs2, 16)
                        out.append(chr(0x10000 + ((cp - 0xD800) << 10) + (cp2 - 0xDC00)))
                        self.i += 6
                    else:
                        out.append(chr(cp))
                        self.i = j + 5
                else:
                    self.error("bad escape \\%s" % e)
            elif c == '"':
                self.i += 1
                return "".join(out)
            else:
                out.append(c)
                self.i += 1
        return "".join(out)

    def parse_int(self):
        m = re.match(r"-?\d+", self.t[self.i:])
        if not m:
            self.error("expected Int")
        self.i += len(m.group(0))
        return int(m.group(0))

    def parse_value(self):
        c = self.peek()
        if c == '"':
            return self.parse_string()
        if c == "{":
            return self.parse_struct()
        if c == "[":
            return self.parse_array()
        if c == "(":
            return self.parse_paren()
        if self.accept("None"):
            return None
        if self.accept("Some"):
            self.expect("(")
            v = self.parse_value()
            self.expect(")")
            return ("__some__", v)
        if c == "-" or c.isdigit():
            return self.parse_int()
        self.error("unexpected token %r" % c)

    def skip_type_annotation(self):
        """跳过 `:` 后的类型标注直至 `)`（本生成器只会用 String? / @engine.Location，
        不含嵌套括号）。"""
        depth = 0
        while self.i < self.n:
            ch = self.t[self.i]
            if ch == "(" :
                depth += 1
            elif ch == ")":
                if depth == 0:
                    return
                depth -= 1
            self.i += 1
        self.error("unterminated type annotation")

    def parse_paren(self):
        """括号形态：元组 `(a, b)` / 冗余括号 `(v)` / 类型标注 `(v : T)`。"""
        self.expect("(")
        items = [self.parse_value()]
        while True:
            c = self.peek()
            if c == ",":
                self.i += 1
                items.append(self.parse_value())
            elif c == ":":
                self.i += 1
                self.skip_type_annotation()
                self.expect(")")
                if len(items) != 1:
                    self.error("ascription on non-single expression")
                return items[0]
            elif c == ")":
                self.i += 1
                break
            else:
                self.error("expected , : or ) in paren")
        if len(items) == 2:
            return (items[0], items[1])
        if len(items) == 1:
            return items[0]
        self.error("unsupported paren arity %d" % len(items))

    def parse_field_name(self):
        m = re.match(r"[A-Za-z_][A-Za-z_0-9]*", self.t[self.i:])
        if not m:
            self.error("expected field name")
        self.i += len(m.group(0))
        return m.group(0)

    def parse_struct(self):
        self.expect("{")
        obj = {}
        while True:
            c = self.peek()
            if c == "}":
                self.i += 1
                return obj
            name = self.parse_field_name()
            self.expect(":")
            obj[name] = self.parse_value()
            c = self.peek()
            if c == ",":
                self.i += 1
            elif c == "}":
                self.i += 1
                return obj
            else:
                self.error("expected , or } in struct")

    def parse_array(self):
        self.expect("[")
        items = []
        while True:
            c = self.peek()
            if c == "]":
                self.i += 1
                return items
            items.append(self.parse_value())
            c = self.peek()
            if c == ",":
                self.i += 1
            elif c == "]":
                self.i += 1
                return items
            else:
                self.error("expected , or ] in array")

    def parse_tuple(self):
        self.expect("(")
        items = [self.parse_value()]
        while True:
            c = self.peek()
            if c == ",":
                self.i += 1
                items.append(self.parse_value())
            elif c == ")":
                self.i += 1
                break
            else:
                self.error("expected , or ) in tuple")
        if len(items) != 2:
            self.error("tuple arity != 2: %d" % len(items))
        return (items[0], items[1])


def parse_mbt(text):
    p = MbtParser(text)
    m = re.search(r"pub let golden_upstream_version : String = ", text)
    if not m:
        raise ValueError("golden.mbt 缺少 golden_upstream_version 绑定")
    p.i = m.end()
    p.skip_ws()
    header_ver = p.parse_string()
    m = re.search(r"pub let golden_cases : Array\[GCase\] = \[", text)
    if not m:
        raise ValueError("golden.mbt 缺少 golden_cases 数组")
    p.i = m.end() - 1  # 停在 '['
    cases = p.parse_array()
    return header_ver, cases


def unwrap(o):
    """把 Some(x) 回解标记转成 x；None 原样。"""
    if isinstance(o, tuple) and len(o) == 2 and o[0] == "__some__":
        return o[1]
    return o


def mbt_umap_to_json(u):
    if u is None:
        return None
    pairs = u
    return {k: v for k, v in pairs}


def json_norm(v):
    return v


def read_cpca_version():
    """直读 vendored cpca __init__.py 的 `VERSION = (0, 5, 5)` 元组并拼出
    __version__ 字符串（等价于上游 `".".join(map(str, VERSION))`），不 import、
    零副作用。返回 None = vendored 文件不存在（该目录只读、不入库，属合法缺失）。"""
    if not os.path.exists(CPCA_INIT_PATH):
        return None
    with open(CPCA_INIT_PATH, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"^VERSION\s*=\s*\(([^)]*)\)", text, re.M)
    if not m:
        raise ValueError(
            "vendored cpca __init__.py 存在但缺少 VERSION 元组: %s" % CPCA_INIT_PATH
        )
    parts = [p.strip() for p in m.group(1).split(",") if p.strip()]
    if not parts or not all(re.fullmatch(r"\d+", p) for p in parts):
        raise ValueError("vendored cpca VERSION 元组形态非预期: %r" % m.group(1))
    return ".".join(parts)


def main():
    problems = []
    for path in (JSONL_PATH, MBT_PATH):
        if not os.path.exists(path):
            print("MISSING: %s" % path)
            return 1
    with open(JSONL_PATH, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f.read().splitlines() if line.strip()]
    with open(MBT_PATH, encoding="utf-8") as f:
        mbt_text = f.read()
    try:
        header_ver, cases = parse_mbt(mbt_text)
    except ValueError as e:
        print("PARSE-FAIL golden.mbt: %s" % e)
        return 1

    # jsonl 行结构锁定：恰 4 字段 + expected 恰 8 字段固定键
    for idx, row in enumerate(rows):
        keys = list(row.keys())
        if keys != ROW_KEYS:
            problems.append("jsonl[%d] 字段序/字段集不符: %r（锁定 %r）" % (idx, keys, ROW_KEYS))
        ek = list(row.get("expected", {}).keys())
        if ek != EXPECTED_KEYS:
            problems.append("jsonl[%d] expected 字段不符: %r" % (idx, ek))

    if header_ver != (rows[0].get("upstream_version") if rows else None):
        problems.append("mbt 头部版本 %r ≠ jsonl 行版本 %r" % (header_ver, rows[0].get("upstream_version") if rows else None))

    # 版本标识 = cpca 实际 __version__ 核验（docstring 契约；直读 vendored 源，不 import）
    try:
        cpca_ver = read_cpca_version()
    except ValueError as e:
        print("PARSE-FAIL cpca __init__.py: %s" % e)
        return 1
    if cpca_ver is None:
        print(
            "NOTE: vendored cpca __init__.py 缺失，跳过 __version__ 核验"
            "（0.5.5 外部锚由 testdata/golden_test.mbt 版本断言承担）"
        )
    elif header_ver != cpca_ver:
        problems.append(
            "版本标识 ≠ cpca 实际 __version__: 产物=%r vendored=%r" % (header_ver, cpca_ver)
        )

    if len(rows) != len(cases):
        problems.append("条数不一致: jsonl=%d mbt=%d" % (len(rows), len(cases)))
    else:
        for idx, (row, case) in enumerate(zip(rows, cases)):
            if row["input"] != case.get("input"):
                problems.append("[%d] input 不一致: jsonl=%r mbt=%r" % (idx, row["input"], case.get("input")))
            if row["upstream_version"] != case.get("upstream_version"):
                problems.append("[%d] upstream_version 不一致: jsonl=%r mbt=%r" % (idx, row["upstream_version"], case.get("upstream_version")))
            if case.get("upstream_version") != header_ver:
                problems.append("[%d] upstream_version ≠ mbt 头部版本: %r vs %r" % (idx, case.get("upstream_version"), header_ver))
            ju = row["umap"]
            mu = mbt_umap_to_json(unwrap(case.get("umap")))
            if ju != mu:
                problems.append("[%d] umap 不一致: jsonl=%r mbt=%r" % (idx, ju, mu))
            je = row["expected"]
            me = case.get("expected", {})
            for k in EXPECTED_KEYS:
                mv = unwrap(me.get(k))
                if je.get(k) != mv:
                    problems.append("[%d][%s] expected 不一致: jsonl=%r mbt=%r (input=%r)" % (idx, k, je.get(k), mv, row["input"]))

    if problems:
        print("MISMATCH count = %d" % len(problems))
        for p_ in problems:
            print("  - %s" % p_)
        return 1
    print(
        "OK: golden.jsonl 与 golden.mbt 一致（cases=%d，8 字段×%d 逐项对账，upstream_version=%s）"
        % (len(rows), len(rows), header_ver)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
