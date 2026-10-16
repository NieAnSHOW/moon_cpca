// moon_cpca 提取引擎 — golden 比对骨架（T-03）
// 宿主裁定（T-03 裁定 1，覆盖 brief Files 的 `<engine>/golden_test.mbt`）：
// 本文件落 `testdata/` 包，与 golden.mbt 同包 → 编译期常量装载（引擎 spec
// §4.4 装载方式契约锁定，core 无 fs/io/path，运行时读文件必违反 E13）。
// 本工具链把 `*_test.mbt` 作为黑盒测试编译（隐式 @testdata 限定，[0025]），
// 故同包常量以 `@testdata.` 限定引用；形态与兄弟包测试约定一致。
// 比对逻辑为完整实现：启用用例逐条调 @engine.extract 并对 Location 全部
// 8 字段逐一比对（失败信息带用例号/input/字段名/期望值/实际值）。
//
// 本阶段启用集（T-04 步 6 裁定 = 控制器裁定 1：宿主留在 testdata/，启用集
// 由 T-03 的 ⑥⑦⑧ 三类扩到【全部 13 类 32 条】，逐条全 8 字段比对，无豁免）：
// T-04 落地 M-8 前缀补全（update_res_by_adcode/adcode_name，__init__.py:229-248）、
// M-9 addr 尾串截取（truncate_index 线程，__init__.py:195/199/224）、
// M-7 umap 分支与 M-10 空记录后，①②③④⑤⑨⑩⑪⑫⑬ 的命中用例通路打开
// （含④仅省类实跑期望 addr=""（末位命中后的空尾串）：引擎 addr 语义 =
// 末匹配词之后子串，空即 Some("")，替换输出构造后与 golden 自然对齐）。
// TODO(T-06)：本文件类别白名单收口为全量回归形态（启用集机制/骨架整理）。
//
// S1 静态门（P3）：本包测试侧零 fs/网络标识 —— golden 经编译期常量装载。

///|
/// 启用类别 = golden 全集 13 类（T-04 步 6；类别名与 golden.mbt 行内 `category`
/// 字段逐字一致，未列入者视为未覆盖 —— 保留白名单形态以便逐类核对覆盖度）。
let enabled_categories : Array[String] = [
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

///|
/// 类别是否启用（不用 `includes`：本工具链 Array[String] 无该方法，实测
/// [3002]/abstract-type 报错）。
fn is_enabled(cat : String) -> Bool {
  let mut found = false
  for e in enabled_categories {
    if e == cat {
      found = true
    }
  }
  found
}

///|
/// String? 的确定性展示（规避 Option Show 的 deprecated 警告，
/// 形态沿用兄弟包测试约定 engine/probe_test.mbt 头注释）。
fn opt_str(s : String?) -> String {
  match s {
    None => "None"
    Some(v) => "Some(\"" + v + "\")"
  }
}

///|
/// golden.mbt 的 (String, String) 数组形态 → extract 的 Map 入参。
fn umap_of(pairs : Array[(String, String)]) -> Map[String, String] {
  let m : Map[String, String] = Map([])
  for _, kv in pairs {
    m[kv.0] = kv.1
  }
  m
}

///|
/// 用例通路：按 golden 行的 umap 维度调用引擎公开入口
/// （契约 = extract(text, pos_sensitive=true[, umap])，spec §4.4 生成行）。
fn run_case(c : @testdata.GCase) -> @engine.Location {
  match c.umap {
    None => @engine.extract(c.input, pos_sensitive=true)
    Some(pairs) => @engine.extract(c.input, pos_sensitive=true, umap=umap_of(pairs))
  }
}

///|
/// 逐字段完整比对（8 字段全查；不一致即记录差异，不做任何弱化/豁免）。
/// got 经 golden.mbt 的 location_as_expected 桥投影为同构载体后对齐比较。
fn diff_case(
  idx : Int,
  c : @testdata.GCase,
  got : @engine.Location,
  fails : Array[String],
) -> Unit {
  let exp = c.expected
  let got_e = @testdata.location_as_expected(got)
  if got_e.province != exp.province {
    fails.push("case[\{idx}] input=\"\{c.input}\" province: expected=\{opt_str(exp.province)} got=\{opt_str(got_e.province)}")
  }
  if got_e.city != exp.city {
    fails.push("case[\{idx}] input=\"\{c.input}\" city: expected=\{opt_str(exp.city)} got=\{opt_str(got_e.city)}")
  }
  if got_e.area != exp.area {
    fails.push("case[\{idx}] input=\"\{c.input}\" area: expected=\{opt_str(exp.area)} got=\{opt_str(got_e.area)}")
  }
  if got_e.addr != exp.addr {
    fails.push("case[\{idx}] input=\"\{c.input}\" addr: expected=\{opt_str(exp.addr)} got=\{opt_str(got_e.addr)}")
  }
  if got_e.adcode != exp.adcode {
    fails.push("case[\{idx}] input=\"\{c.input}\" adcode: expected=\{opt_str(exp.adcode)} got=\{opt_str(got_e.adcode)}")
  }
  if got_e.province_pos != exp.province_pos {
    fails.push("case[\{idx}] input=\"\{c.input}\" province_pos: expected=\{exp.province_pos} got=\{got_e.province_pos}")
  }
  if got_e.city_pos != exp.city_pos {
    fails.push("case[\{idx}] input=\"\{c.input}\" city_pos: expected=\{exp.city_pos} got=\{got_e.city_pos}")
  }
  if got_e.area_pos != exp.area_pos {
    fails.push("case[\{idx}] input=\"\{c.input}\" area_pos: expected=\{exp.area_pos} got=\{got_e.area_pos}")
  }
}

///|
/// 差异清单 → 单串报告（inspect(Array) 触发 [0020] Show deprecated，
/// 故折叠为 String 后 inspect，全绿时恰为 "ALL_PASS"）。
fn report(fails : Array[String]) -> String {
  if fails.length() == 0 {
    "ALL_PASS"
  } else {
    let mut msg = "FAIL(\{fails.length()}):"
    for f in fails {
      msg = msg + "\n  - " + f
    }
    msg
  }
}

///|
/// golden 比对骨架主通路：逐条（启用类别 = 全 13 类 32 条，T-04 步 6）→
/// 全 8 字段比对；
/// 版本锚定断言（E9 形态）覆盖全部行：upstream_version = "0.5.5" 且
/// 与载体头部标识一致。
test "golden_compare_enabled" {
  let fails : Array[String] = []
  let mut checked = 0
  for i, c in @testdata.golden_cases {
    if c.upstream_version != "0.5.5" || c.upstream_version != @testdata.golden_upstream_version {
      fails.push("case[\{i}] upstream_version 漂移: \{opt_str(Some(c.upstream_version))} (期望 \"0.5.5\"，V-01 锚)")
    }
    if !is_enabled(c.category) {
      continue
    }
    checked = checked + 1
    diff_case(i, c, run_case(c), fails)
  }
  if checked != @testdata.golden_cases.length() {
    fails.push(
      "启用集未覆盖全部 golden 行（逐条全字段比对要求）: checked=\{checked} total=\{@testdata.golden_cases.length()}",
    )
  }
  inspect(report(fails), content="ALL_PASS")
}

///|
/// load-bearing 枚举序探针（T-03 裁定 4）：引擎「同 end 最长先行」假设 vs
/// 真实 pyahocorasick 端到端确认。
/// 素材 = 「城东区某某路」：'城东区'(630102 青海西宁) 与 '东区'(510402 四川
/// 攀枝花) 同 end=2 竞争；上游实测（命令与原始输出见 task-03-report）：
///   raw ac.iter('城东区') → [(2,('城东区',[630102])), (2,('东区',[510402]))]
///   （同 end 先长后短；短者随后被 matcher.py:77 end<=prev_end 吞掉，M-2）
///   transform('城东区某某路', pos_sensitive=True) → 区=城东区 adcode=630102
/// golden 行（A 级）期望同名同码。本探针断言 T-02 可观察面 = 选中候选
/// （area/adcode）——若引擎枚举序假设错（先出 东区），此处即红；
/// 完整 8 字段比对自 T-04 步 6 起随类别②进入全量启用集（本测试保留为
/// 枚举序专项回归锁），
/// 非弱化：启用集比对用上测试的完整 diff_case，无字段豁免。
test "golden_same_end_longest_first_probe" {
  let fails : Array[String] = []
  let mut idx = -1
  for i, c in @testdata.golden_cases {
    if c.input == "城东区某某路" {
      idx = i
    }
  }
  if idx < 0 {
    fails.push("golden 输入集缺失碰撞用例「城东区某某路」（生成器 CASES 被改动？）")
  } else {
    let c = @testdata.golden_cases[idx]
    if c.expected.area != Some("城东区") || c.expected.adcode != Some("630102") {
      fails.push("golden 碰撞用例期望漂移（上游实跑应选 城东区/630102）: area=\{opt_str(c.expected.area)} adcode=\{opt_str(c.expected.adcode)}")
    }
    let got = @engine.extract(c.input, pos_sensitive=true)
    if got.area != c.expected.area {
      fails.push("同 end 枚举序破坏: area expected=\{opt_str(c.expected.area)} got=\{opt_str(got.area)}（引擎先行候选 ≠ 上游 ac.iter 同 end 首出）")
    }
    if got.adcode != c.expected.adcode {
      fails.push("同 end 枚举序破坏: adcode expected=\{opt_str(c.expected.adcode)} got=\{opt_str(got.adcode)}")
    }
  }
  inspect(report(fails), content="ALL_PASS")
}
