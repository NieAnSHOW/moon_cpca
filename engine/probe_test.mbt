// moon_cpca 提取引擎 — A9 冒烟探针（T-01 步 6 创建；T-02 转绿并扩充）
// 断言 FINAL 预期行为；断言形态沿用兄弟数据包约定
// （`inspect(cond, content="true")`，规避 Option Show 的 deprecated 警告）；
// 引用形态用 `@engine.` 限定（规避 0025 警告）。
// T-02 转绿清单：探针①（数据产物消费）、探针②（pos 码点口径）、
// L2 同名区消歧链路对、L1 部分状态（area/adcode 先绿，省市补全归 T-04）。

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
test "l1_xuhui_partial_state_t02" {
  // L1 走查（S3）T-02 实际状态：无上级时「徐汇区」取候选首元素（M-6）→
  // area/adcode 先绿；province/city 需 T-04 的 update_res_by_adcode 补全，
  // addr 需 T-04 尾串截取 —— 本探针只锁当前已确定部分，T-04 扩充。
  let res = @engine.extract("徐汇区虹漕路461号58号楼5楼")
  inspect(res.area is Some("徐汇区"), content="true")
  inspect(res.adcode is Some("310104"), content="true")
}
