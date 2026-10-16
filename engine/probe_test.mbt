// moon_cpca 提取引擎 — A9 冒烟探针（T-01 步 6 创建；T-02 转绿并扩充）
// 断言 FINAL 预期行为；断言形态沿用兄弟数据包约定
// （`inspect(cond, content="true")`，规避 Option Show 的 deprecated 警告）；
// 引用形态用 `@engine.` 限定（规避 0025 警告）。
// T-02 转绿清单：探针①（数据产物消费）、探针②（pos 码点口径）、
// L2 同名区消歧链路对。
// T-04 走查门（S3）扩充：L1 补全全链、L3 umap（含回落支路）、L4 无匹配/空输入
// 空记录，另加收尾路径（仅市命中 addr=""）专项。

///|
test "a9_probe_shanghai" {
  let province = @engine.extract("上海市").province
  inspect(province is Some("上海市"), content="true")
}

///|
test "a9_probe2_pos_codepoint_index" {
  // 探针②：pos 口径 = 码点（Char）序号，禁用 UTF-16 码元口径。
  // "A1上海市徐汇区" 中「上海市」起始于码点下标 2。
  let pos = @engine.extract("A1上海市徐汇区", pos_sensitive=true).province_pos
  inspect(pos == 2, content="true")
}

///|
test "l2_same_name_district_belong_disambiguation" {
  // L2 走查对（同名区消歧）：「朝阳区」两名候选（长春 220104 / 北京 110105），
  // 上级「吉林省」按 belong_to 前缀语义（22**）选中长春市朝阳区。
  // adcode 断言 = S3 走查门；省市补全（update_res_by_adcode）与 addr 归 T-04。
  let adcode = @engine.extract("吉林省朝阳区不知道店").adcode
  inspect(adcode is Some("220104"), content="true")
}

///|
test "l2_fujian_gulou_belong_disambiguation" {
  // L2 走查对之二：「鼓楼区」在上级「福建省」下按前缀 35** 选中福州市鼓楼区。
  let adcode = @engine.extract("福建省鼓楼区鼓楼医院").adcode
  inspect(adcode is Some("350102"), content="true")
}

///|
test "l1_xuhui_full_chain_t04" {
  // L1 走查（S3，V-07 全链）：无上级时「徐汇区」取候选首元素（M-6）→
  // 310104 县级命中即产出；省市名由 update_res_by_adcode 按 adcode 前缀反查
  // （M-8）：adcode_name("31")=上海市、adcode_name("3101")=市辖区（V-08 直辖市
  // 市位形态，非「上海市」重复）；addr = 末匹配词 end 之后子串（M-9，V-09 口径）。
  // 与 golden 类别② 同输入行（testdata/golden.mbt ②「徐汇区虹漕路461号58号楼5楼」）
  // 期望逐字段同形。
  let res = @engine.extract("徐汇区虹漕路461号58号楼5楼", pos_sensitive=true)
  inspect(res.province is Some("上海市"), content="true")
  inspect(res.city is Some("市辖区"), content="true")
  inspect(res.area is Some("徐汇区"), content="true")
  inspect(res.addr is Some("虹漕路461号58号楼5楼"), content="true")
  inspect(res.adcode is Some("310104"), content="true")
  inspect(res.province_pos, content="-1")
  inspect(res.city_pos, content="-1")
  inspect(res.area_pos, content="0")
}

///|
test "l3_umap_selects_beijing_chaoyang" {
  // L3 走查（S3，V-06 / M-7）：同名区「朝阳区」候选首元素为长春 220104（V-04/V-05），
  // 传 umap {"朝阳区": "110105"}（key=匹配原文、value=6 位 adcode，
  // 上游 transform 文档 __init__.py:97）后按 adcode 选候选 → 北京 110105；
  // 省市补全为 北京市/市辖区（V-08）。
  let umap : Map[String, String] = Map([("朝阳区", "110105")])
  let res = @engine.extract("朝阳区汉庭酒店大山子店", pos_sensitive=true, umap=umap)
  inspect(res.province is Some("北京市"), content="true")
  inspect(res.city is Some("市辖区"), content="true")
  inspect(res.area is Some("朝阳区"), content="true")
  inspect(res.addr is Some("汉庭酒店大山子店"), content="true")
  inspect(res.adcode is Some("110105"), content="true")
  inspect(res.area_pos, content="0")
}

///|
test "l3b_umap_unknown_key_and_absent_fall_back_to_first" {
  // M-7 回落支路（matcher.py:16-18）：umap 里查不到匹配原文 → 候选首元素；
  // 与不传 umap（= 上游默认空 dict，__init__.py:90）行为一致（V-05）。
  let res_unknown =
    @engine.extract("朝阳区汉庭酒店大山子店", pos_sensitive=true, umap=Map([("不存在区", "110105")]))
  let res_empty =
    @engine.extract("朝阳区汉庭酒店大山子店", pos_sensitive=true, umap=Map([]))
  let res_absent = @engine.extract("朝阳区汉庭酒店大山子店", pos_sensitive=true)
  inspect(res_unknown.adcode is Some("220104"), content="true")
  inspect(res_empty.adcode is Some("220104"), content="true")
  inspect(res_absent.adcode is Some("220104"), content="true")
  inspect(
    res_unknown.province is Some("吉林省") && res_unknown.city is Some("长春市"),
    content="true",
  )
}

///|
test "l4_no_match_empty_record" {
  // L4 走查（S3，M-10 / V-10）：无匹配输入 → 全 None + pos 全 -1；
  // 空输入同形（__init__.py:176-178 空记录分支）。adcode 无命中 = None
  // （6 位口径只在命中时产出；12→6 截位锚 __init__.py:45-46 在 Cand 构造期）。
  for t in ["32323", "哈哈哈不存在", ""] {
    let res = @engine.extract(t, pos_sensitive=true)
    inspect(res.province is None, content="true")
    inspect(res.city is None, content="true")
    inspect(res.area is None, content="true")
    inspect(res.addr is None, content="true")
    inspect(res.adcode is None, content="true")
    inspect(res.province_pos, content="-1")
    inspect(res.city_pos, content="-1")
    inspect(res.area_pos, content="-1")
  }
}

///|
test "l5_city_only_record_addr_empty_string" {
  // 非县级命中收尾路径（__init__.py:223-225）：仅市命中 → 省按前缀补全、
  // 区 None、addr = 末匹配词之后的空尾串（Some("")，③ 类 golden A 级期望）。
  let res = @engine.extract("成都市", pos_sensitive=true)
  inspect(res.province is Some("四川省"), content="true")
  inspect(res.city is Some("成都市"), content="true")
  inspect(res.area is None, content="true")
  inspect(res.addr is Some(""), content="true")
  inspect(res.adcode is Some("510100"), content="true")
  inspect(res.province_pos, content="-1")
  inspect(res.city_pos, content="0")
  inspect(res.area_pos, content="-1")
}
