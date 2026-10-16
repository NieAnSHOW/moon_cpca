#!/usr/bin/env python3
"""E13 依赖白名单机检（引擎 spec §6 E13 / §2 / §9.3 C-3 逐字口径）。

判据：`moon.mod` 的 deps/import 条目 ∪ 引擎包 `moon.pkg` 的 import 条目
⊆ { `moonbitlang/core/*`, 兄弟单元数据包 `"<module>/data"` }，
其中 `<module>` = 被检 `moon.mod` 的 name 字段（本仓库 = moon_cpca）。
白名单外计数 = 0 → 退出码 0；否则打印清单并非 0 退出。

说明：
- 解析对象是 DSL 文本（moon.mod / moon.pkg 的 rr TOML/DSL 形态），非 JSON。
- core 依赖（moonbitlang/core/*）通常不在 moon.mod 显式出现，容忍空集。
- `--mod` / `--pkg` 覆盖路径：违规样本用**副本**注入，不污染真实文件
  （兄弟 plan 独占的 moon.mod 保持逐字节不动）。

用法：
  python tools/check_deps.py [--mod <path>] [--pkg <path>]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

QUOTED_RE = re.compile(r'"([^"]+)"')
# 依赖映射的「键」字面量："module/name" = ...（只取等号左侧，避免把版本号当条目）
QUOTED_KEY_RE = re.compile(r'"([^"]+)"\s*=')


def dep_entries(fragment: str) -> list[str]:
    """从 deps/import 文本片段提取依赖条目名。"""
    keys = QUOTED_KEY_RE.findall(fragment)
    return keys if keys else QUOTED_RE.findall(fragment)
# moon.mod 中承载依赖的键（rr_moon_mod TOML 形态）
DEP_KEY_RE = re.compile(
    r"^\s*(deps|dep|dependencies|dev-dependencies|dev_dependencies|"
    r"import|imports)\s*=\s*(?P<val>.*)$",
    re.IGNORECASE,
)
# [dependencies] / [dev-dependencies] 表段落
DEP_SECTION_RE = re.compile(
    r"^\s*\[\s*[\"']?(dependencies|dev-dependencies|deps)[\"']?\s*\]\s*$",
    re.IGNORECASE,
)
ANY_SECTION_RE = re.compile(r"^\s*\[.*\]\s*$")


def parse_module_name(mod_text: str) -> str:
    """moon.mod 的 name 字段 = 模块字面量（`<module>`，E13 白名单第二项前缀）。"""
    m = re.search(r'^\s*name\s*=\s*"([^"]+)"', mod_text, re.MULTILINE)
    if not m:
        raise ValueError("moon.mod 缺少 name 字段，无法确定 <module>")
    return m.group(1)


def extract_mod_deps(mod_text: str) -> list[str]:
    """moon.mod 的 deps/import 条目：键值行 + 表段落内的引号字面量。"""
    deps: list[str] = []
    in_dep_section = False
    in_dep_braces = False
    for line in mod_text.splitlines():
        if in_dep_braces:
            deps.extend(dep_entries(line))
            if "}" in line:
                in_dep_braces = False
            continue
        if DEP_SECTION_RE.match(line):
            in_dep_section = True
            continue
        if in_dep_section:
            if ANY_SECTION_RE.match(line):
                in_dep_section = False
            else:
                deps.extend(dep_entries(line))
                continue
        m = DEP_KEY_RE.match(line)
        if m:
            val = m.group("val")
            deps.extend(dep_entries(val))
            # 多行表值 deps = { ... （开 brace 未闭合）
            if "{" in val and "}" not in val:
                in_dep_braces = True
    return deps


def extract_pkg_imports(pkg_text: str) -> list[str]:
    """engine/moon.pkg 的 import { "..." @alias, } 块内引号字面量。"""
    imports: list[str] = []
    in_block = False
    for line in pkg_text.splitlines():
        if in_block:
            if "}" in line:
                in_block = False
            imports.extend(dep_entries(line))
            continue
        m = re.match(r"^\s*import\s*\{(?P<rest>.*)$", line)
        if m:
            rest = m.group("rest")
            imports.extend(dep_entries(rest))
            if "}" not in rest:  # 多行块起始：import { 同行未闭合
                in_block = True
    return imports


def check(mod_path: Path, pkg_path: Path) -> int:
    mod_text = mod_path.read_text(encoding="utf-8")
    pkg_text = pkg_path.read_text(encoding="utf-8")
    module = parse_module_name(mod_text)
    mod_deps = extract_mod_deps(mod_text)
    pkg_imports = extract_pkg_imports(pkg_text)
    union = list(dict.fromkeys(mod_deps + pkg_imports))  # 并集，保序去重

    def allowed(entry: str) -> bool:
        if entry == "moonbitlang/core" or entry.startswith("moonbitlang/core/"):
            return True
        if entry == f"{module}/data":  # 兄弟单元数据包（spec §9.3 锁定字面量）
            return True
        return False

    print(f"[check_deps] module = {module}")
    print(f"[check_deps] moon.mod deps    = {mod_deps}")
    print(f"[check_deps] moon.pkg imports = {pkg_imports}")
    print(f"[check_deps] import 并集      = {union}")

    offenders = [e for e in union if not allowed(e)]
    for e in offenders:
        print(f"[check_deps] NON-WHITELIST: {e}")
    print(f"[check_deps] 白名单外条目计数 = {len(offenders)}")
    if offenders:
        print("[check_deps] FAIL: 违反 E13 依赖白名单（spec §2 / §6 E13）")
        return 1
    print("[check_deps] PASS: 白名单外计数 = 0")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mod", default=str(REPO_ROOT / "moon.mod"),
                    help="moon.mod 路径覆盖（违规样本用副本）")
    ap.add_argument("--pkg", default=str(REPO_ROOT / "engine" / "moon.pkg"),
                    help="引擎包 moon.pkg 路径覆盖（违规样本用副本）")
    ns = ap.parse_args(argv)
    return check(Path(ns.mod), Path(ns.pkg))


if __name__ == "__main__":
    sys.exit(main())
