// moon_cpca 提取引擎 — Location 字段与 NULL 性白盒测试（T-06 步骤 2）
// 覆盖矩阵（engine spec §4.2 Location 字段表 ↔ 测试名 ↔ 上游/权威锚点）：
//   8 字段形状与类型        → location_fields_shape_and_types            → spec §4.2 DT1-DT3 逐字段类型/NULL 性
//   adcode 6 位口径         → location_adcode_six_digits                → __init__.py:45-46（AddrInfo 构造期 adcode[:6]）
//   pos 非空 Int + 空记录-1 → location_pos_fields_int_and_minus_one     → V-10（空记录 pos 全 -1）
//   Option 语义（Some/None） → location_option_semantics                 → spec §4.2 NULL 性 + V-08/V-09/V-10
//   直辖市市位 = 市辖区     → location_direct_municipality_city         → V-08（北京市海淀区 → 市辖区）
//   省级单独命中 市 = None  → location_province_only_city_none         → V-08（北京市 → 市 None）
//   县级补全全链            → location_area_prefix_completion           → V-07（徐汇区 → 上海市/市辖区/310104）
//   addr 吞后续文本         → location_addr_swallows_tail              → V-09（吉林省朝阳区，而我家… → 「，而我家在…」）
//   addr 空尾串 = Some("")   → location_addr_empty_tail_some           → golden ③④ 类（成都市 / 北京市 实跑 = ""）
//   非 BMP pos 口径         → location_pos_codepoint_index_non_bmp      → V-11/V-12（上海😀市徐汇区 area_pos=4）
// 上游测试域映射（spec §4.5）：tests/test_structures.py（Pca 字段/NULL 性/pos 结构）
// → 本文件 Location 字段/NULL 性/pos 结构用例；tests/test_cpca.py（_assert_line
// 的 8 值断言形态）→ 同形态逐字段断言。
// 白盒形态（*_wbtest.mbt）：与 engine 包同作用域；断言只用可观察字段值，
// 零 mock、零文件/网络/环境变量。展示用 String 拼接（opt_str 风格），规避
// Option Show 的 deprecated 警告。

///|
/// String? 的确定性展示（规避 Option Show 的 deprecated 警告；
/// 形态沿用 golden_test.mbt 的 opt_str）。
fn opt_str(s : String?) -> String {
  match s {
    None => "None"
    Some(v) => "Some(\"" + v + "\")"
  }
}

///|
/// Int 的确定性展示（Option[Int] 同形态；本结构体 pos 为非空 Int，
/// 此助手仅供字段表展示复用）。
fn int_str(i : Int) -> String {
  "\{i}"
}

///|
/// Location 8 字段逐字展示（由 location_fields_shape_and_types 快照断言消费）。
fn dump(loc : Location) -> String {
  "province=" + opt_str(loc.province) + " city=" + opt_str(loc.city) + " area=" + opt_str(loc.area) + " addr=" + opt_str(loc.addr) + " adcode=" + opt_str(loc.adcode) + " province_pos=" + int_str(loc.province_pos) + " city_pos=" + int_str(loc.city_pos) + " area_pos=" + int_str(loc.area_pos)
}

///|
/// 码点计数（for 计数形态，非 String::length() 的 UTF-16 码元口径）。
/// 本助手仅用于 adcode 字段位宽校验（ASCII 数字字段宽度 = 6，spec §4.2
/// adcode 行），不参与任何文本位置计算；位置口径由引擎侧 pos 字段断言覆盖。
fn code_len(s : String?) -> Int {
  match s {
    None => 0
    Some(v) => {
      let mut n = 0
      for _ in v {
        n = n + 1
      }
      n
    }
  }
}

/// 是否全为 ASCII 数字（adcode 形态校验；None = false）。
fn all_digits(s : String?) -> Bool {
  match s {
    None => false
    Some(v) => {
      let mut ok = true
      for ch in v {
        if !(ch >= '0' && ch <= '9') {
          ok = false
        }
      }
      ok
    }
  }
}

/// 是否以 n 个 '0' 结尾（末级语义校验；None = false）。
fn has_suffix_zeros(s : String?, n : Int) -> Bool {
  match s {
    None => false
    Some(v) => {
      // 先码点计数取尾段起点（字段宽度小且为 ASCII 数字，非文本位置计算），
      // 再逐字符比 '0'。
      let mut total = 0
      for _ in v {
        total = total + 1
      }
      if total < n {
        false
      } else {
        let mut i = 0
        let mut ok = true
        for ch in v {
          if i >= total - n && ch != '0' {
            ok = false
          }
          i = i + 1
        }
        ok
      }
    }
  }
}

///|
test "location_fields_shape_and_types" {
  // spec §4.2（DT1-DT3）：Location 恰为 8 字段，标量类型 =
  // 5 个 String?（province/city/area/addr/adcode，可空）+ 3 个 Int
  // （province_pos/city_pos/area_pos，非空）。
  // 类型/NULL 性按字段逐一取型断言（可观察 = 匹配/构造与字段读取均编译通过）：
  //   String? 字段可直接与 None/Some("x") 比较（Option 语义），
  //   Int 字段可直接与字面量整数比较（非 Option，取不到 None）。
  let res = extract("北京市海淀区中关村大街1号", pos_sensitive=true)
  // 5 个可空字段的 Option 语义（None 与 Some 两条路径都要走到）。
  let p : String? = res.province
  let c : String? = res.city
  let a : String? = res.area
  let ad : String? = res.addr
  let ac : String? = res.adcode
  inspect(opt_str(p), content="Some(\"北京市\")")
  inspect(opt_str(c), content="Some(\"市辖区\")")
  inspect(opt_str(a), content="Some(\"海淀区\")")
  inspect(opt_str(ad), content="Some(\"中关村大街1号\")")
  inspect(opt_str(ac), content="Some(\"110108\")")
  // 3 个非空 Int 字段（非 Option；与整数字面量直接相等比较）。
  let pp : Int = res.province_pos
  let cp : Int = res.city_pos
  let ap : Int = res.area_pos
  inspect(pp, content="0")
  inspect(cp, content="-1")
  inspect(ap, content="3")
  // 8 字段快照（逐字段断言之外的整体形态锁：字段名/顺序/值域一屏可核对）。
  inspect(
    dump(res),
    content="province=Some(\"北京市\") city=Some(\"市辖区\") area=Some(\"海淀区\") addr=Some(\"中关村大街1号\") adcode=Some(\"110108\") province_pos=0 city_pos=-1 area_pos=3",
  )
  // 空记录形态兜底同结构（8 字段同时可读）。
  let empty = extract("32323", pos_sensitive=true)
  inspect(opt_str(empty.province), content="None")
  inspect(empty.province_pos, content="-1")
  inspect(empty.city_pos, content="-1")
  inspect(empty.area_pos, content="-1")
}

///|
test "location_adcode_six_digits" {
  // adcode 输出口径 = 6 位（上游构造期 12 → 前 6 位截断，
  // chinese_province_city_area_mapper/cpca/__init__.py:45-46 `self.adcode = adcode[:6]`；
  // 输入侧数据表 adcode 为 12 位，锚 data spec §4.2）。
  // 可观察面：凡命中，adcode 恒为 6 位数字（省/市/区三类末级各一条）。
  let province_case = extract("江苏省", pos_sensitive=true)
  let city_case = extract("成都市", pos_sensitive=true)
  let area_case = extract("徐汇区虹漕路461号58号楼5楼", pos_sensitive=true)
  inspect(code_len(province_case.adcode), content="6")
  inspect(code_len(city_case.adcode), content="6")
  inspect(code_len(area_case.adcode), content="6")
  inspect(opt_str(province_case.adcode), content="Some(\"320000\")")
  inspect(opt_str(city_case.adcode), content="Some(\"510100\")")
  inspect(opt_str(area_case.adcode), content="Some(\"310104\")")
  // 6 位全为 ASCII 数字（非空、无前缀残留）。
  inspect(all_digits(province_case.adcode), content="true")
  inspect(all_digits(city_case.adcode), content="true")
  inspect(all_digits(area_case.adcode), content="true")
  // 末级语义：省用例后 4 位为 0、市用例后 2 位为 0、区用例末 2 位非全 0。
  inspect(opt_str(province_case.adcode), content="Some(\"320000\")")
  inspect(has_suffix_zeros(province_case.adcode, 4), content="true")
  inspect(has_suffix_zeros(city_case.adcode, 2), content="true")
  inspect(has_suffix_zeros(area_case.adcode, 2), content="false")
}

///|
test "location_pos_fields_int_and_minus_one" {
  // pos 三槽为非空 Int；未匹配槽 = -1（spec §4.2 pos 行 + V-10）。
  // 单条县级命中：只有 area_pos 命中，另两槽保持 -1。
  let res = extract("徐汇区虹漕路461号58号楼5楼", pos_sensitive=true)
  inspect(res.province_pos, content="-1")
  inspect(res.city_pos, content="-1")
  inspect(res.area_pos, content="0")
  // 无匹配 + 空输入：三槽全 -1（M-10 / V-10 上游实跑）。
  for t in ["32323", "", "abc123def456"] {
    let r = extract(t, pos_sensitive=true)
    inspect(r.province_pos, content="-1")
    inspect(r.city_pos, content="-1")
    inspect(r.area_pos, content="-1")
  }
  // pos 与 adcode 槽位一致：省级命中只写 province_pos（V-08/V-14），
  // 市级命中只写 city_pos（golden ③ 类），县级命中写 area_pos（V-07）。
  let prov = extract("江苏省", pos_sensitive=true)
  inspect(prov.province_pos, content="0")
  inspect(prov.city_pos, content="-1")
  inspect(prov.area_pos, content="-1")
  let city = extract("成都市", pos_sensitive=true)
  inspect(city.province_pos, content="-1")
  inspect(city.city_pos, content="0")
  inspect(city.area_pos, content="-1")
  let area = extract("城东区某某路", pos_sensitive=true)
  inspect(area.province_pos, content="-1")
  inspect(area.city_pos, content="-1")
  inspect(area.area_pos, content="0")
  // pos 非负时才 > 0：句中命中给出真实码点序号（省市槽按最终 adcode 反查
  // 不写 pos，故仅末级槽非 -1；多级输入见前缀补全测试）。
}

///|
test "location_pos_codepoint_index_non_bmp" {
  // pos 口径 = 码点（Char）序号，与上游 Python str 索引同口径
  // （V-11：'上海😀市徐汇区虹漕路' 中 徐汇区 index=4、码点 len=10、
  // UTF-16 码元 len=11；V-12：MoonBit char_length=10 / length()=11，
  // 后者为禁用口径）。
  // 可观察面：emoji 占 1 个序号 → 「徐汇区」area_pos = 4（若误用码元
  // 口径会得 5，此处即红）。
  let res = extract("上海😀市徐汇区虹漕路", pos_sensitive=true)
  inspect(res.area is Some("徐汇区"), content="true")
  inspect(res.area_pos, content="4")
  inspect(res.province is Some("上海市"), content="true")
  inspect(res.addr is Some("虹漕路"), content="true")
  // 前置 ASCII 混排同样按字符计数（码点序号，V-11 同口径）。
  let ascii_res = extract("A1上海市徐汇区", pos_sensitive=true)
  inspect(ascii_res.province_pos, content="2")
  // 无匹配含 emoji → 空记录 + pos 全 -1（M-10 / V-10）。
  let none_res = extract("😀没有地名", pos_sensitive=true)
  inspect(opt_str(none_res.adcode), content="None")
  inspect(none_res.area_pos, content="-1")
}

///|
test "location_option_semantics" {
  // Option 语义逐字段（spec §4.2 NULL 性列）：
  // - Some：命中时字段非 None（省/市/区/addr/adcode 依链路填充）；
  // - None：不可补全/未命中时为 None（市级命中时区 = None；
  //   省级单独命中时市/区 = None；无匹配时五字段全 None）。
  // 市级命中：省补全（Some）、区 None、addr Some（空尾串）。
  let city_case = extract("苏州市观前街", pos_sensitive=true)
  inspect(opt_str(city_case.province), content="Some(\"江苏省\")")
  inspect(opt_str(city_case.city), content="Some(\"苏州市\")")
  inspect(opt_str(city_case.area), content="None")
  inspect(opt_str(city_case.addr), content="Some(\"观前街\")")
  inspect(opt_str(city_case.adcode), content="Some(\"320500\")")
  // 省级命中：市/区 None、addr Some("")（末匹配词之后空尾串）。
  let prov_case = extract("江苏省", pos_sensitive=true)
  inspect(opt_str(prov_case.province), content="Some(\"江苏省\")")
  inspect(opt_str(prov_case.city), content="None")
  inspect(opt_str(prov_case.area), content="None")
  inspect(opt_str(prov_case.addr), content="Some(\"\")")
  inspect(opt_str(prov_case.adcode), content="Some(\"320000\")")
  // 县级命中：三字段全 Some（V-07 全链）。
  let area_case = extract("天河区体育西路", pos_sensitive=true)
  inspect(opt_str(area_case.province), content="Some(\"广东省\")")
  inspect(opt_str(area_case.city), content="Some(\"广州市\")")
  inspect(opt_str(area_case.area), content="Some(\"天河区\")")
  inspect(opt_str(area_case.addr), content="Some(\"体育西路\")")
  inspect(opt_str(area_case.adcode), content="Some(\"440106\")")
  // 无匹配：五字段全 None（M-10 / V-10）。
  let none_case = extract("哈哈哈不存在", pos_sensitive=true)
  inspect(opt_str(none_case.province), content="None")
  inspect(opt_str(none_case.city), content="None")
  inspect(opt_str(none_case.area), content="None")
  inspect(opt_str(none_case.addr), content="None")
  inspect(opt_str(none_case.adcode), content="None")
}

///|
test "location_direct_municipality_city_is_shiqu" {
  // 直辖市形态（V-08）：市级命中时市名 = 市辖区（数据侧 adcode_name("1101")
  // = 市辖区，非「上海市」重复）；省级单独命中时市 = None。
  // 北京市海淀区 → 市 = 市辖区（V-08 上游实跑第一行）。
  let res = extract("北京市海淀区中关村大街1号", pos_sensitive=true)
  inspect(opt_str(res.province), content="Some(\"北京市\")")
  inspect(opt_str(res.city), content="Some(\"市辖区\")")
  inspect(opt_str(res.area), content="Some(\"海淀区\")")
  inspect(res.province_pos, content="0")
  inspect(res.city_pos, content="-1")
  inspect(res.area_pos, content="3")
  // 仅省级：市 = None（V-08 上游实跑第二行 '北京市' → 市 None）。
  let prov_only = extract("北京市", pos_sensitive=true)
  inspect(opt_str(prov_only.province), content="Some(\"北京市\")")
  inspect(opt_str(prov_only.city), content="None")
  inspect(opt_str(prov_only.area), content="None")
  inspect(opt_str(prov_only.addr), content="Some(\"\")")
  inspect(opt_str(prov_only.adcode), content="Some(\"110000\")")
  // 天津/上海同级形态（V-08 同规则；天津市上游实跑 = 省 120000）。
  inspect(opt_str(extract("天津市", pos_sensitive=true).adcode), content="Some(\"120000\")")
  inspect(opt_str(extract("上海市徐汇区", pos_sensitive=true).city), content="Some(\"市辖区\")")
}

///|
test "location_area_prefix_completion_three_levels" {
  // M-8 前缀补全（__init__.py:238-248 update_res_by_adcode：省 adcode[:2] /
  // 市 adcode[:4] / 区全串反查）：下级命中时三级名同时给出（V-07）。
  let res = extract("徐汇区虹漕路461号58号楼5楼", pos_sensitive=true)
  inspect(opt_str(res.province), content="Some(\"上海市\")")
  inspect(opt_str(res.city), content="Some(\"市辖区\")")
  inspect(opt_str(res.area), content="Some(\"徐汇区\")")
  inspect(opt_str(res.adcode), content="Some(\"310104\")")
  // 非常住居民区的普通省市补全（V-07 同类）。
  let res2 = extract("福建省鼓楼区鼓楼医院", pos_sensitive=true)
  inspect(opt_str(res2.province), content="Some(\"福建省\")")
  inspect(opt_str(res2.city), content="Some(\"福州市\")")
  inspect(opt_str(res2.area), content="Some(\"鼓楼区\")")
  inspect(opt_str(res2.adcode), content="Some(\"350102\")")
  // 市级前缀补全只写省+市（区 None，spec §4.2 + golden ③ 类）。
  let res3 = extract("淮安市市辖区", pos_sensitive=true)
  inspect(opt_str(res3.province), content="Some(\"江苏省\")")
  inspect(opt_str(res3.city), content="Some(\"淮安市\")")
  inspect(opt_str(res3.area), content="Some(\"市辖区\")")
  inspect(opt_str(res3.adcode), content="Some(\"320801\")")
  inspect(res3.province_pos, content="-1")
  inspect(res3.city_pos, content="0")
  inspect(res3.area_pos, content="3")
}

///|
test "location_addr_swallows_tail_and_empty_string" {
  // M-9（__init__.py:199,224 `sentence[truncate_index + 1:]`）：addr =
  // 最后一个匹配词之后的子串。V-09 上游实跑：
  // '你家在吉林省朝阳区，而我家在北京市朝阳区，太远了' → addr = '，而我家在北京市朝阳区，太远了'。
  let res = extract("你家在吉林省朝阳区，而我家在北京市朝阳区，太远了", pos_sensitive=true)
  inspect(opt_str(res.addr), content="Some(\"，而我家在北京市朝阳区，太远了\")")
  inspect(opt_str(res.adcode), content="Some(\"220104\")")
  inspect(res.province_pos, content="3")
  inspect(res.area_pos, content="6")
  // 空尾串 = Some("")（不是 None）：末匹配词之后无文本（golden ③④ 类）。
  let tail_empty = extract("北京市石景山区金顶北路22号(地铁站B口步行80米)", pos_sensitive=true)
  inspect(opt_str(tail_empty.addr), content="Some(\"金顶北路22号(地铁站B口步行80米)\")")
  inspect(opt_str(extract("成都市", pos_sensitive=true).addr), content="Some(\"\")")
  inspect(opt_str(extract("江苏省", pos_sensitive=true).addr), content="Some(\"\")")
  // 无匹配时 addr = None（V-10）—— 与 Some("") 语义区分开。
  inspect(opt_str(extract("32323", pos_sensitive=true).addr), content="None")
}
