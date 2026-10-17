// moon_cpca 提取引擎 — 匹配语义白盒测试（T-06 步骤 1）
// 覆盖矩阵（engine spec §4.3 M-x ↔ 本文件测试名 ↔ 上游权威锚点）：
//   M-1 最长匹配        → m1_longest_match_wins_at_same_start       → V-15/V-16（matcher.py:74-77、cpca/__init__.py:65 停用词）
//   M-2 区间不重叠      → m2_non_overlapping_intervals_skip_short   → V-16 + golden「城东区某某路」= 630102（matcher.py:77-78）
//   M-3 共享候选列表    → m3_shared_candidate_list_same_name_districts → V-04（朝阳区 [220104,110105]；test_matcher.py 同名区用例）
//   M-3 简称共享列表    → m3_abbrev_shares_list_with_full_name      → V-14/V-17/V-18（matcher.py:35-41、47-61）
//   M-4 同区间去重      → m4_same_start_dedup_yields_longer         → V-16（matcher.py:82-88）
//   M-5 归属消歧        → m5_belong_to_prefix_disambiguation        → V-13/V-19（matcher.py:13-15、__init__.py:58-60）
//   M-5 全不归属丢弃    → m5_no_candidate_belongs_drops_match       → V-19 + __init__.py:190-191（new_entry_when_not_belong=False）
//   M-6 无上级取首元素  → m6_first_candidate_when_no_parent         → V-04/V-05（matcher.py:19-20）
//   M-7 umap 指定       → m7_umap_selects_candidate_by_adcode       → V-06（matcher.py:16-18）
//   M-7 umap 回落首元素 → m7_umap_unknown_falls_back_to_first       → V-06 同输入回落支路（matcher.py:16-18）
//   M-7 umap value 边界 → m7_umap_value_width_and_empty_boundary      → T-04 rubric 缺口锁（matcher.py:16-18 + __init__.py:45-46 + 上游实跑）
// 白盒形态（*_wbtest.mbt）：与 engine 包同作用域，可访问 priv 的 Cand/MatchInfo/
// matcher/iter_matches/get_match_addr/belong_to；断言只作用于可观察行为
// （枚举序、候选序列、选中候选、端到端 extract 输出），零 mock、零文件/网络/环境变量。
// S1 静态门（P1/P2/P3）自查零命中：本文件无码元口径长度调用、无候选排序
// 标识、无网络/文件/环境变量标识（检索式见 task-06 报告；行 13-15 同义表述）。

///|
/// 由全名键取共享候选列表（键缺失 = 空列表；调用方均为已知存在于数据表的键）。
fn cands_of(key : String) -> Array[Cand] {
  match matcher.index.get(key) {
    Some(cs) => cs
    None => []
  }
}

///|
/// 候选列表的 adcode 序列展示（确定性字符串，规避 Option/Array Show 的 deprecated 警告）。
fn join_adcodes(cs : Array[Cand]) -> String {
  let mut s = ""
  let mut first = true
  for c in cs {
    if first {
      s = c.adcode6
      first = false
    } else {
      s = s + "," + c.adcode6
    }
  }
  s
}

///|
/// 候选列表的 name 序列展示（确定性字符串）。
fn join_names(cs : Array[Cand]) -> String {
  let mut s = ""
  let mut first = true
  for c in cs {
    if first {
      s = c.name
      first = false
    } else {
      s = s + "," + c.name
    }
  }
  s
}

///|
/// 匹配序列的 origin_value 连接（确定性展示；空序列 = ""）。
fn join_values(ms : Array[MatchInfo]) -> String {
  let mut s = ""
  let mut first = true
  for m in ms {
    if first {
      s = m.origin_value
      first = false
    } else {
      s = s + "," + m.origin_value
    }
  }
  s
}

///|
/// 取候选列表中 adcode = 给定值的首个候选（测试专造；调用方保证存在）。
fn cs_first(cs : Array[Cand], adcode6 : String) -> Cand {
  let mut found : Cand = cs[0]
  let mut hit = false
  for c in cs {
    if !hit && c.adcode6 == adcode6 {
      found = c
      hit = true
    }
  }
  found
}

///|
/// 消歧结果（Cand?）的确定性展示。
fn cand_code(c : Cand?) -> String {
  match c {
    None => "None"
    Some(x) => x.adcode6
  }
}

///|
test "m1_longest_match_wins_at_same_start" {
  // M-1（最长匹配，matcher.py:74-77 end 位迭代 + 起点回推）：
  // 「上海市」全称与其简称「上海」同 end 竞争，只产出最长命中（V-16 上游
  // matcher.iter('上海市') 实测 1 个匹配；V-15 省_pos=0 单次匹配语义）。
  // 「上海」被「上海市」覆盖（同起点取长），不单独产出。
  let ms = iter_matches("上海市", matcher.index, matcher.max_key_len)
  inspect(join_values(ms), content="上海市")
  inspect(ms[0].start_index, content="0")
  inspect(ms[0].end_index, content="2")
  inspect(join_adcodes(ms[0].cands), content="310000")
  // 端到端：省级单独命中 → 省名 + 6 位 adcode + addr 空尾串（V-08/V-15 口径）。
  let res = extract("上海市", pos_sensitive=true)
  inspect(res.province is Some("上海市"), content="true")
  inspect(res.adcode is Some("310000"), content="true")
  inspect(res.addr is Some(""), content="true")
  inspect(res.province_pos, content="0")
}

///|
test "m2_non_overlapping_intervals_skip_short" {
  // M-2（区间不重叠，matcher.py:77-78 `end_index <= prev_end_index` 即跳过）：
  // 「上海市徐汇区虹漕路461号58号楼5楼」两句独立命中，短匹配「上海」(0-1) 被
  // 随后同起点的「上海市」(0-2) 顶掉（M-1/M-4）；「徐汇区」(3-5) 与前区间
  // (0-2) 不重叠照常产出；区间序列严格升序且不重叠（M-2 不变量）。
  let ms = iter_matches(
    "上海市徐汇区虹漕路461号58号楼5楼",
    matcher.index,
    matcher.max_key_len,
  )
  inspect(join_values(ms), content="上海市,徐汇区")
  inspect(ms[0].start_index, content="0")
  inspect(ms[0].end_index, content="2")
  inspect(ms[1].start_index, content="3")
  inspect(ms[1].end_index, content="5")
  // M-2 同 end 短后缀被吞（实测 pyahocorasick 同 end 先长后短，锚
  // task-03 裁定 4 的 ac.iter('城东区') 记录）：「城东区某某路」只产出
  // 城东区（630102 青海西宁），其短后缀「东区」（510402 攀枝花）不产出。
  let cd = iter_matches(
    "城东区某某路",
    matcher.index,
    matcher.max_key_len,
  )
  inspect(join_values(cd), content="城东区")
  inspect(join_adcodes(cd[0].cands), content="630102")
  inspect(
    extract("城东区某某路", pos_sensitive=true).adcode is Some("630102"),
    content="true",
  )
}

///|
test "m3_shared_candidate_list_same_name_districts" {
  // M-3（全称/简称共享候选 + 同名多 adcode 追加，matcher.py:50-61）：
  // 同名区「朝阳区」两条数据（data/adcodes.mbt 行 450 长春 220104、
  // 行 1500 北京 110105）追加进同一共享列表，顺序 = 数据行序（V-04 上游
  // matcher._get('朝阳区') 实测 ['220104','110105']；test_matcher.py 的
  // 同名区用例同形态：attr_infos[0]/[1] adcode 按加入序排列）。
  let cs = cands_of("朝阳区")
  inspect(join_adcodes(cs), content="220104,110105")
  inspect(join_names(cs), content="朝阳区,朝阳区")
  // 共享引用：连续两次取值序列一致（同名追加不新建列表）。
  inspect(join_adcodes(cands_of("朝阳区")), content="220104,110105")
}

///|
test "m3_abbrev_shares_list_with_full_name" {
  // M-3 简称路径（matcher.py:47-48 _abbr_name + stop_key
  // `([省市]|特别行政区|自治区)$`，cpca/__init__.py:65，V-18）：简称经
  // 后缀剥离后与全名写入同一候选列表（matcher.py:50-56 的 share_list）。
  // 五个自治区走 special_abbre 特表（V-17，matcher.py:35-41），否则
  // 广西/西藏/宁夏等会被剥成「广西壮族」形态；本测试以内蒙古/宁夏两例锁定。
  // 简称键与全名键取到同一候选（同 name / 同 adcode）。
  let abbr = cands_of("江苏")
  let full = cands_of("江苏省")
  inspect(join_names(abbr), content="江苏省")
  inspect(join_names(full), content="江苏省")
  inspect(join_adcodes(abbr), content="320000")
  inspect(join_adcodes(full), content="320000")
  // 端到端简称命中（V-14 上游实跑）：江苏→320000、淮安→320800。
  inspect(
    extract("江苏", pos_sensitive=true).adcode is Some("320000"),
    content="true",
  )
  inspect(
    extract("淮安", pos_sensitive=true).adcode is Some("320800"),
    content="true",
  )
  // 自治区简称（V-17/V-14）：内蒙古自治区→150000、宁夏→640000；
  // 全称与简称两条路径给出同一候选。
  inspect(
    extract("内蒙古自治区", pos_sensitive=true).adcode is Some("150000"),
    content="true",
  )
  inspect(
    extract("内蒙古", pos_sensitive=true).adcode is Some("150000"),
    content="true",
  )
  inspect(
    extract("宁夏", pos_sensitive=true).adcode is Some("640000"),
    content="true",
  )
  inspect(
    extract("宁夏回族自治区", pos_sensitive=true).adcode
    is Some("640000"),
    content="true",
  )
}

///|
test "m4_same_start_dedup_yields_longer" {
  // M-4（同区间去重、后写胜出，matcher.py:81-88）：同一起点的简称先到、
  // 全称后到 → 只产出全称并清空挂起项。「上海市徐汇区」中「上海」(0-1)
  // 与「上海市」(0-2) 同起点，产出唯一匹配「上海市」（V-16 单次匹配语义；
  // 若去重失效会产出两条且首条为简称）。
  let ms = iter_matches(
    "上海市徐汇区",
    matcher.index,
    matcher.max_key_len,
  )
  inspect(join_values(ms), content="上海市,徐汇区")
  inspect(join_adcodes(ms[0].cands), content="310000")
  // 端到端不受简称残留影响：三级记录由最终 adcode 前缀反查（M-8，V-07/V-08）。
  let res = extract("上海市徐汇区", pos_sensitive=true)
  inspect(res.province is Some("上海市"), content="true")
  inspect(res.city is Some("市辖区"), content="true")
  inspect(res.area is Some("徐汇区"), content="true")
  inspect(res.adcode is Some("310104"), content="true")
  inspect(res.province_pos, content="0")
  inspect(res.area_pos, content="3")
}

///|
test "m5_belong_to_prefix_disambiguation" {
  // M-5（归属消歧，matcher.py:13-15 `belong_to` 前缀过滤，V-19 口径：
  // self.adcode.startswith(other.adcode[:(other.rank+1)*2])，省 2 / 市 4 / 区 6 位）。
  // V-13 上游实跑三条：吉林省朝阳区→220104、福建省鼓楼区→350102、
  // 南京市鼓楼区→320106（南京市为市级父结点，前缀长度 4）。
  let cy = cands_of("朝阳区")
  let gl = cands_of("鼓楼区")
  let jilin = cs_first(cands_of("吉林省"), "220000")
  let fujian = cs_first(cands_of("福建省"), "350000")
  let nanjing = cs_first(cands_of("南京市"), "320100")
  inspect(cand_code(get_match_addr(cy, Some(jilin), None)), content="220104")
  inspect(cand_code(get_match_addr(gl, Some(fujian), None)), content="350102")
  inspect(cand_code(get_match_addr(gl, Some(nanjing), None)), content="320106")
  // belong_to 前缀语义逐级（V-19）：区级候选 320106 归属 江苏省/南京市，
  // 不归属 福建省/吉林省。
  inspect(belong_to(cs_first(cy, "110105"), jilin), content="false")
  inspect(belong_to(cs_first(gl, "320106"), nanjing), content="true")
  inspect(belong_to(cs_first(gl, "320106"), fujian), content="false")
  // 端到端同输入（V-13）：省市名由前缀补全给出（M-8）。
  let r1 = extract("吉林省朝阳区不知道店", pos_sensitive=true)
  inspect(r1.adcode is Some("220104"), content="true")
  inspect(r1.province is Some("吉林省"), content="true")
  inspect(r1.city is Some("长春市"), content="true")
  let r2 = extract("福建省鼓楼区鼓楼医院", pos_sensitive=true)
  inspect(r2.adcode is Some("350102"), content="true")
  inspect(r2.province is Some("福建省"), content="true")
  inspect(r2.city is Some("福州市"), content="true")
  let r3 = extract("南京市鼓楼区", pos_sensitive=true)
  inspect(r3.adcode is Some("320106"), content="true")
  inspect(r3.province is Some("江苏省"), content="true")
  inspect(r3.city is Some("南京市"), content="true")
}

///|
test "m5_no_candidate_belongs_drops_match" {
  // M-5 丢弃支路（matcher.py:14-15：父结点限定下无任何候选 belong_to →
  // get_match_addr 返回 None；transform 模式 __init__.py:190-191 配
  // new_entry_when_not_belong=False → 该匹配被静默跳过，线程状态不变）。
  // 白盒层可观察面：福建省 + 朝阳区候选（无一属于 35****）→ 无候选被选中。
  let cy = cands_of("朝阳区")
  let fujian = cs_first(cands_of("福建省"), "350000")
  inspect(cand_code(get_match_addr(cy, Some(fujian), None)), content="None")
  // 端到端（上游 v0.5.5 同输入实跑，anchor = 本仓库 task-06 取证命令）：
  // 「福建省朝阳区」中 朝阳区 匹配被丢弃，线程状态不变（last_info/adcode/
  // truncate_index 仍是 福建省 那一步），最终记录 = 省级命中形态：
  // 省=福建省 / 市=None / 区=None / addr="朝阳区"（末次被接受匹配 福建省
  // 之后的子串）/ adcode=350000 / province_pos=0。若丢弃支路失效（如误选
  // 北京朝阳区 110105），区或 adcode 字段立即偏离。
  let res = extract("福建省朝阳区", pos_sensitive=true)
  inspect(res.province is Some("福建省"), content="true")
  inspect(res.city is None, content="true")
  inspect(res.area is None, content="true")
  inspect(res.addr is Some("朝阳区"), content="true")
  inspect(res.adcode is Some("350000"), content="true")
  inspect(res.province_pos, content="0")
  inspect(res.city_pos, content="-1")
  inspect(res.area_pos, content="-1")
}

///|
test "m6_first_candidate_when_no_parent" {
  // M-6（无上级取候选列表第 0 个，matcher.py:19-20 else 分支）：
  // 顺序 = 数据行序（V-04：朝阳区 [220104, 110105]，数据侧长春在前），
  // 引擎零排序（Global Constraints / spec §4.3 M-6）。
  let cy = cands_of("朝阳区")
  inspect(cand_code(get_match_addr(cy, None, None)), content="220104")
  // 端到端（V-05 上游实跑）：朝阳区汉庭酒店大山子店 → 吉林省/长春市/朝阳区/220104。
  let res = extract("朝阳区汉庭酒店大山子店", pos_sensitive=true)
  inspect(res.province is Some("吉林省"), content="true")
  inspect(res.city is Some("长春市"), content="true")
  inspect(res.area is Some("朝阳区"), content="true")
  inspect(res.addr is Some("汉庭酒店大山子店"), content="true")
  inspect(res.adcode is Some("220104"), content="true")
  inspect(res.area_pos, content="0")
  // get_one_addr 语义（matcher.py:21-22）同取首元素：单候选时不变。
  inspect(
    cand_code(get_match_addr(cands_of("徐汇区"), None, None)),
    content="310104",
  )
}

///|
test "m7_umap_selects_candidate_by_adcode" {
  // M-7（umap 指定，matcher.py:16-18：按 adcode 选候选；上游 transform 文档
  // cpca/__init__.py:97「key 为区名，value 为 adcode，比如 {"朝阳区": "110105"}」）。
  // V-06 上游实跑：同一输入 + umap → 北京市/市辖区/朝阳区/110105。
  let cy = cands_of("朝阳区")
  inspect(cand_code(get_match_addr(cy, None, Some("110105"))), content="110105")
  let umap : Map[String, String] = Map([("朝阳区", "110105")])
  let res = extract(
    "朝阳区汉庭酒店大山子店",
    pos_sensitive=true,
    umap~,
  )
  inspect(res.province is Some("北京市"), content="true")
  inspect(res.city is Some("市辖区"), content="true")
  inspect(res.area is Some("朝阳区"), content="true")
  inspect(res.addr is Some("汉庭酒店大山子店"), content="true")
  inspect(res.adcode is Some("110105"), content="true")
  inspect(res.area_pos, content="0")
  // umap value 与候选 6 位 adcode 等值比较（__init__.py:189 → matcher.py:17）
  let gl = cands_of("鼓楼区")
  inspect(cand_code(get_match_addr(gl, None, Some("320106"))), content="320106")
}

///|
test "m7_umap_unknown_falls_back_to_first" {
  // M-7 回落支路（matcher.py:16-18：`res if res else self.attr_infos[0]`）：
  // umap 中 adcode 选不中任何候选 → 回落候选首元素（与无 umap 行为一致，
  // V-05 口径）；umap 键不存在同样回落。
  let cy = cands_of("朝阳区")
  inspect(cand_code(get_match_addr(cy, None, Some("999999"))), content="220104")
  let res_unknown = extract(
    "朝阳区汉庭酒店大山子店",
    pos_sensitive=true,
    umap=Map([("朝阳区", "999999")]),
  )
  let res_other_key = extract(
    "朝阳区汉庭酒店大山子店",
    pos_sensitive=true,
    umap=Map([("不存在区", "110105")]),
  )
  let res_absent = extract(
    "朝阳区汉庭酒店大山子店",
    pos_sensitive=true,
  )
  inspect(res_unknown.adcode is Some("220104"), content="true")
  inspect(res_other_key.adcode is Some("220104"), content="true")
  inspect(res_absent.adcode is Some("220104"), content="true")
  inspect(res_unknown.province is Some("吉林省"), content="true")
}

///|
test "m7_umap_value_width_and_empty_boundary" {
  // M-7 value 边界（T-04 rubric 缺口回归锁；上游锚点 matcher.py:16-18
  // `res if res else self.attr_infos[0]` + __init__.py:45-46
  // AddrInfo 构造期 `self.adcode = adcode[:6]`）：
  // 候选 adcode 恒为 6 位（构造期截断），而 umap value 由调用方原样传入、
  // 与候选做等值比较（__init__.py:189 → matcher.py:17）——故 value 位宽
  // 不是 6 位（如误传 12 位全码）或为空串时，等值比较必然不命中 → 回落
  // 候选首元素，与无 umap 行为一致（V-05 口径）。
  // 上游实跑取证（仓库根；cd chinese_province_city_area_mapper；
  // `python -W ignore -c "from cpca import transform; ..."`，
  // 2026-10-17，cpca 0.5.5）：
  //   umap={'朝阳区': '110105000000'}（12 位）
  //     → {'省': '吉林省', '市': '长春市', '区': '朝阳区',
  //        '地址': '汉庭酒店大山子店', 'adcode': '220104'}
  //   umap={'朝阳区': ''}（空串）
  //     → {'省': '吉林省', '市': '长春市', '区': '朝阳区',
  //        '地址': '汉庭酒店大山子店', 'adcode': '220104'}
  // 两条均回落首元素 220104（吉林省/长春市），非 110105。
  let cy = cands_of("朝阳区")
  // 白盒：first_adcode 与 6 位候选 adcode 等值比较（M-7 选择支路语义）。
  // 12 位全码 / 空串均不命中 → 回落 cands[0] = 220104。
  inspect(
    cand_code(get_match_addr(cy, None, Some("110105000000"))),
    content="220104",
  )
  inspect(cand_code(get_match_addr(cy, None, Some(""))), content="220104")
  // 公开入口：12 位 value → 回落首元素（不按 110105 选）。
  let res_wide = extract(
    "朝阳区汉庭酒店大山子店",
    pos_sensitive=true,
    umap=Map([("朝阳区", "110105000000")]),
  )
  inspect(res_wide.adcode is Some("220104"), content="true")
  inspect(res_wide.province is Some("吉林省"), content="true")
  inspect(res_wide.city is Some("长春市"), content="true")
  inspect(res_wide.area is Some("朝阳区"), content="true")
  inspect(res_wide.addr is Some("汉庭酒店大山子店"), content="true")
  // 公开入口：空串 value → 同样回落首元素。
  let res_empty = extract(
    "朝阳区汉庭酒店大山子店",
    pos_sensitive=true,
    umap=Map([("朝阳区", "")]),
  )
  inspect(res_empty.adcode is Some("220104"), content="true")
  inspect(res_empty.province is Some("吉林省"), content="true")
  inspect(res_empty.city is Some("长春市"), content="true")
  // 反证口径：6 位 value 命中选择支路 → 110105（证明回落不是"永远取首元素"，
  // 等值比较在位宽正确时确实生效；与 m7_umap_selects_candidate_by_adcode 同锁）。
  let res_exact = extract(
    "朝阳区汉庭酒店大山子店",
    pos_sensitive=true,
    umap=Map([("朝阳区", "110105")]),
  )
  inspect(res_exact.adcode is Some("110105"), content="true")
}
