#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-03 golden 生成器：oracle 现生成 + 双产物同进程写出。

契约来源（逐字）：
- 引擎 spec §4.4（testdata/golden.jsonl 4 字段行格式 / golden.mbt 编译期常量载体 /
  13 类规模行 / 复现性）
- brief F6 权威调用形态：transform(input, pos_sensitive=True[, umap])
  （chinese_province_city_area_mapper/cpca/__init__.py:90，T-03 步 1 已核读）
- upstream_version 权威：cpca/__init__.py:9 VERSION → __version__

行为：
- 读固定输入集（本文件内 CASES 常量，13 类各 ≥1，总数 ≥30；类别标签只在
  生成器/.mbt 侧，jsonl 行格式锁定 4 字段不含类别）；
- 每条用例调用上游 transform 实跑取期望（pos 列名以实跑 df.columns 为准，
  禁臆造/禁手改/禁反推，A 级证据）；
- **同一次运行**写 testdata/golden.jsonl 与 testdata/golden.mbt 两产物；
- 确定性：用例序 = CASES 序；jsonl 每行字段序固定；umap 键排序序列化；
  二次生成字节级 diff = 0。

CLI：
- python tools/gen_golden.py            全量重生成，写两产物
- python tools/gen_golden.py --stats    输出总条数与逐类计数（不写文件）
"""

import argparse
import json
import os
import sys
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPSTREAM_DIR = os.path.join(ROOT, "chinese_province_city_area_mapper")
TESTDATA_DIR = os.path.join(ROOT, "testdata")
JSONL_PATH = os.path.join(TESTDATA_DIR, "golden.jsonl")
MBT_PATH = os.path.join(TESTDATA_DIR, "golden.mbt")

# vendored 上游只读；仅通过 sys.path 消费，不修改任何上游文件。
sys.path.insert(0, UPSTREAM_DIR)
# 上游 __init__.py:68 使用已弃用的 pkg_resources，Py3.12 触发 UserWarning；
# 屏蔽该警告不污染工具输出（不触碰上游代码）。
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

import cpca  # noqa: E402  (vendored oracle, 只读)
from cpca import transform  # noqa: E402  (权威调用形态 __init__.py:90)

UPSTREAM_VERSION = cpca.__version__  # 权威 __init__.py:9-11 → "0.5.5"

# ---------------------------------------------------------------------------
# 期望列名映射：键 = 引擎 spec §4.2 8 字段（jsonl expected 固定序），
# 值 = 上游 transform(pos_sensitive=True) 实跑 df.columns 中文列名
# （权威 __init__.py:13-34；实跑列序 ['省','市','区','地址','adcode',
#  '省_pos','市_pos','区_pos']，本文件 EXPECTED_COLUMNS 再断言一次）。
# ---------------------------------------------------------------------------
FIELD_TO_CN = [
    ("province", "省"),
    ("city", "市"),
    ("area", "区"),
    ("addr", "地址"),
    ("adcode", "adcode"),
    ("province_pos", "省_pos"),
    ("city_pos", "市_pos"),
    ("area_pos", "区_pos"),
]
EXPECTED_KEYS = [en for en, _ in FIELD_TO_CN]

# ---------------------------------------------------------------------------
# 固定输入集：(类别, input, umap)。umap=None → 调 transform 不传 umap
# （走默认参数）；dict → 显式传（含空 {}，jsonl 中与 null 可区分）。
# 13 类定义 = 引擎 spec §4.4 规模行；类别标签不进 jsonl（4 字段锁定）。
# ---------------------------------------------------------------------------
CATS = [
    "①完整省市区",
    "②仅区县",
    "③仅市",
    "④仅省",
    "⑤简称",
    "⑥数字字母混排",
    "⑦无匹配",
    "⑧空输入",
    "⑨同名区无上级",
    "⑩同名区有上级限定",
    "⑪umap",
    "⑫addr吞后续文本",
    "⑬非BMP-pos",
]

CASES = [
    # ① 完整省市区
    ("①完整省市区", "北京市海淀区中关村大街1号", None),
    ("①完整省市区", "广东省深圳市南山区科技园路1号", None),
    ("①完整省市区", "上海市浦东新区世纪大道100号", None),
    # T-09：上游 test_cpca.py::test_transform 全量补齐（10 条字符串，不含
    #       类型层 N/A 的 int 32323；见 testdata 覆盖文档 T-04）。
    ("①完整省市区", "泉州市洛江区万安塘西工业区", None),
    ("①完整省市区", "我家的地址是江苏淮安清江浦区人民路111号", None),
    ("①完整省市区", "我家的地址是江苏淮安清江浦区上海路111号", None),
    ("①完整省市区", "上海市浦东新区东明路街道三林路15号", None),
    ("①完整省市区", "贵州省黔南布依族苗族自治州长顺县长寨街道和平中路28号", None),
    ("①完整省市区", "淮安市市辖区", None),
    # ② 仅区县（无上级）。含一条「同 end 后缀碰撞」形态：城东区(630102) 与
    #    东区(攀枝花 510402) 在 end=2 同位竞争，期望值由 pyahocorasick 实跑
    #    决定 —— T-03 裁定 4 的 load-bearing 枚举序验证素材。
    ("②仅区县", "徐汇区虹漕路461号58号楼5楼", None),
    ("②仅区县", "城东区某某路", None),
    ("②仅区县", "天河区体育西路", None),
    # ③ 仅市
    ("③仅市", "成都市", None),
    ("③仅市", "苏州市观前街", None),
    # ④ 仅省
    ("④仅省", "北京市", None),
    # T-09：上游 test_transform 的直辖市输入（省=天津市，市/区=None）。
    ("④仅省", "天津市", None),
    ("④仅省", "江苏省", None),
    ("④仅省", "广东省", None),
    # ⑤ 简称（V-14 锚：江苏/淮安/内蒙古自治区/宁夏）
    ("⑤简称", "江苏", None),
    ("⑤简称", "淮安", None),
    ("⑤简称", "内蒙古自治区", None),
    ("⑤简称", "宁夏", None),
    # ⑥ 数字字母混排
    ("⑥数字字母混排", "abc123def456", None),
    ("⑥数字字母混排", "A1B2C3无地名", None),
    # ⑦ 无匹配（V-10 锚：'32323'）
    ("⑦无匹配", "32323", None),
    ("⑦无匹配", "哈哈哈不存在", None),
    # ⑧ 空输入（V-10 锚：''）
    ("⑧空输入", "", None),
    # ⑨ 同名区无上级（V-05 锚：朝阳区 → 220104 候选首元素）
    ("⑨同名区无上级", "朝阳区汉庭酒店大山子店", None),
    ("⑨同名区无上级", "鼓楼区鼓楼医院", None),
    # ⑩ 同名区有上级限定（V-13 三条锚）
    ("⑩同名区有上级限定", "吉林省朝阳区不知道店", None),
    ("⑩同名区有上级限定", "福建省鼓楼区鼓楼医院", None),
    ("⑩同名区有上级限定", "南京市鼓楼区", None),
    # ⑪ umap 指定 / 空 umap / 未知区名 umap（V-06 锚）
    ("⑪umap", "朝阳区汉庭酒店大山子店", {"朝阳区": "110105"}),
    ("⑪umap", "朝阳区汉庭酒店大山子店", {}),
    ("⑪umap", "朝阳区汉庭酒店大山子店", {"不存在区": "110105"}),
    # T-09：上游 test_umap 第二条（同一输入无 umap 时见 ⑩，adcode=220104；
    #       umap 命中 朝阳区→110105 时上游仍按上级限定选 220104）。
    ("⑪umap", "吉林省朝阳区不知道店", {"朝阳区": "110105"}),
    # ⑫ addr 吞后续文本长文（V-09 锚第一条）
    ("⑫addr吞后续文本", "你家在吉林省朝阳区，而我家在北京市朝阳区，太远了", None),
    ("⑫addr吞后续文本", "北京市石景山区金顶北路22号(地铁站B口步行80米)", None),
    # ⑬ 非 BMP pos（V-11 锚：'上海😀市徐汇区虹漕路' 区_pos=4；另加一条
    #    非 BMP 无匹配输入）
    ("⑬非BMP-pos", "上海😀市徐汇区虹漕路", None),
    ("⑬非BMP-pos", "😀没有地名", None),
]


def run_oracle(case):
    """单条用例走上游 transform 实跑，返回 (expected_dict, umap_or_None)。

    调用形态（F6 权威 __init__.py:90）：transform(input, pos_sensitive=True[, umap])
    """
    _cat, inp, umap = case
    kwargs = {"pos_sensitive": True}
    if umap is not None:
        kwargs["umap"] = umap
    df = transform([inp], **kwargs)
    cols = list(df.columns)
    expected_cols = ["省", "市", "区", "地址", "adcode", "省_pos", "市_pos", "区_pos"]
    if cols != expected_cols:
        raise SystemExit(
            "实跑 df.columns 与预期中文列名不符（禁臆造列名，中止）: %r" % (cols,)
        )
    rec = df.to_dict("records")[0]
    expected = {}
    for en, cn in FIELD_TO_CN:
        expected[en] = rec[cn]
    return expected


def build_rows():
    rows = []
    for case in CASES:
        cat, inp, umap = case
        expected = run_oracle(case)
        rows.append(
            {
                "category": cat,
                "input": inp,
                "umap": umap,
                "expected": expected,
                "upstream_version": UPSTREAM_VERSION,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# 产物 1：testdata/golden.jsonl —— 每行 4 字段（input/umap/expected/
# upstream_version），字段序固定；umap 对象键排序保证确定性。
# ---------------------------------------------------------------------------


def jsonl_line(row):
    obj = {
        "input": row["input"],
        "umap": (
            None
            if row["umap"] is None
            else {k: row["umap"][k] for k in sorted(row["umap"])}
        ),
        "expected": {k: row["expected"][k] for k in EXPECTED_KEYS},
        "upstream_version": row["upstream_version"],
    }
    return json.dumps(obj, ensure_ascii=False, sort_keys=False)


# ---------------------------------------------------------------------------
# 产物 2：testdata/golden.mbt —— 编译期常量（GCase 数组；expected 用本包
# GExpected 载体 = Location 8 字段逐字同形 + location_as_expected 桥，
# 因本工具链外部包不能构造 @engine.Location 记录字面量 [4036]）。
# 字符串序列化 = json.dumps(ensure_ascii=False)，与 MoonBit 字面量转义兼容；
# check_golden.py 按本格式做机械回解。
# ---------------------------------------------------------------------------


def mb_str(s):
    return json.dumps(s, ensure_ascii=False)


def mb_opt(value):
    return "None" if value is None else "Some(%s)" % (mb_str(value))


def mb_expected(exp):
    lines = []
    for key in EXPECTED_KEYS:
        v = exp[key]
        if key in ("province", "city", "area", "addr", "adcode"):
            rendered = mb_opt(v)
        else:
            rendered = str(v)  # Int 非空（-1 = 未匹配，empty_record 语义）
        lines.append("        %s : %s," % (key, rendered))
    return "{\n" + "\n".join(lines) + "\n      }"


def mb_umap(umap):
    if umap is None:
        return "None"
    if not umap:
        return "Some([])"
    pairs = ", ".join(
        "(%s, %s)" % (mb_str(k), mb_str(umap[k])) for k in sorted(umap)
    )
    return "Some([%s])" % pairs


MBT_HEADER = """// 本文件由 tools/gen_golden.py 生成（oracle 现生成，同一次运行写出双产物）；
// 禁止单独手改 —— 权威中间件为 testdata/golden.jsonl，一致性由
// python tools/check_golden.py 专检（不一致 = 非 0 退出）。
// 期望值 = 上游 chinese_province_city_area_mapper v{ver} `transform(input,
// pos_sensitive=True[, umap])` 实跑输出（A 级证据，锚 cpca/__init__.py:90）。

///|
/// Location 期望字段（8 字段与 @engine.Location 逐字同形）。
/// 注：本工具链外部包不能以记录字面量构造 @engine.Location
/// （error [4036] read-only type / [4033] label 解析限于本包可见记录），
/// 故期望以本包同构载体承载，比对在 golden_test.mbt 逐字段对齐 Location。
pub struct GExpected {{
  province : String?
  city : String?
  area : String?
  addr : String?
  adcode : String?
  province_pos : Int
  city_pos : Int
  area_pos : Int
}}

pub struct GCase {{
  input : String
  category : String
  umap : Option[Array[(String, String)]]
  upstream_version : String
  expected : GExpected
}}

///|
/// `@engine.Location` → `GExpected` 字段桥（8 字段逐字对应，spec §4.2 口径）。
/// golden.mbt 不直接构造 Location（外部包记录字面量在本工具链被拒
/// [4036]），比对以投影到 GExpected 后逐字段对齐进行。
pub fn location_as_expected(loc : @engine.Location) -> GExpected {{
  {{
    province : loc.province,
    city : loc.city,
    area : loc.area,
    addr : loc.addr,
    adcode : loc.adcode,
    province_pos : loc.province_pos,
    city_pos : loc.city_pos,
    area_pos : loc.area_pos,
  }}
}}

///|
/// 上游版本标识（V-01 锚：cpca/__init__.py:9 VERSION → __version__）。
pub let golden_upstream_version : String = {ver_lit}

///|
/// golden 用例编译期常量数组（≥30 条代表集，13 类覆盖；T-03 步 7 裁定 (b)：
/// 全量 18367 条慢速集延后，登记跟踪，见计划文件「T-03 裁定记录」）。
pub let golden_cases : Array[GCase] = [
"""

MBT_CASE_TMPL = """  {{
    input : {input},
    category : {category},
    umap : {umap},
    upstream_version : {upver},
    expected : {expected},
  }},
"""


def mbt_text(rows):
    parts = [MBT_HEADER.format(ver=UPSTREAM_VERSION, ver_lit=mb_str(UPSTREAM_VERSION))]
    for r in rows:
        parts.append(
            MBT_CASE_TMPL.format(
                input=mb_str(r["input"]),
                category=mb_str(r["category"]),
                umap=mb_umap(r["umap"]),
                upver=mb_str(r["upstream_version"]),
                expected=mb_expected(r["expected"]),
            )
        )
    parts.append("]\n")
    return "".join(parts)


def write_products(rows):
    os.makedirs(TESTDATA_DIR, exist_ok=True)
    with open(JSONL_PATH, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(jsonl_line(r) + "\n")
    with open(MBT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(mbt_text(rows))


def print_stats(rows):
    total = len(rows)
    print("total = %d" % total)
    ok = True
    for cat in CATS:
        n = sum(1 for r in rows if r["category"] == cat)
        if n < 1:
            ok = False
        print("%s = %d" % (cat, n))
    missing = sorted({r["category"] for r in rows} - set(CATS))
    if missing:
        ok = False
        print("未知类别: %r" % (missing,))
    if total < 30:
        ok = False
        print("总数 < 30，违反 spec §4.4 规模行")
    print("stats_ok = %s" % ok)
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="golden 双产物生成器（T-03）")
    parser.add_argument(
        "--stats", action="store_true", help="输出条数与逐类计数（不写产物）"
    )
    args = parser.parse_args(argv)
    rows = build_rows()
    if args.stats:
        return print_stats(rows)
    write_products(rows)
    print(
        "wrote %s (%d lines) + %s (%d cases), upstream_version=%s"
        % (
            os.path.relpath(JSONL_PATH, ROOT).replace(os.sep, "/"),
            len(rows),
            os.path.relpath(MBT_PATH, ROOT).replace(os.sep, "/"),
            len(rows),
            UPSTREAM_VERSION,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
