// moon_cpca 提取引擎 — 匹配核心白盒测试（T-02）
// 直接断言 iter_matches 的枚举序 / 去重（M-2 / M-4）与候选索引构造 quirk
// （pyahocorasick add_word 覆盖语义，matcher.py:50-61）的可观察行为。
// 白盒形态（*_wbtest.mbt）：与 engine 包同作用域，可访问 priv 结构。

///|
test "iter_enumeration_order_and_same_start_dedup" {
  // 上海市徐汇区：上海(起点0) 与 上海市(起点0) 同起点 → 全称胜出（M-4）；
  // 徐汇区(起点3) 独立区间照常产出。start_index 为码点下标（左闭右闭口径，
  // 端点 = start + char_len(origin) - 1，故 0/2 与 3/5）。
  let ms = iter_matches("上海市徐汇区", matcher.index, matcher.max_key_len)
  inspect(ms[0].origin_value, content="上海市")
  inspect(ms[0].start_index, content="0")
  inspect(ms[1].origin_value, content="徐汇区")
  inspect(ms[1].start_index, content="3")
}

///|
test "jilin_abbr_key_overwrite_quirk" {
  // 「吉林」简称键唯一归属，重复绑定按 add_word 语义【覆盖】而非合并。
  // 数据行序：吉林市（行 2455）先加入 → 简称键吉林→[吉林市]；
  // 吉林省（行 3362）后加入 → 简称键被覆盖为→[吉林省]（matcher.py:50-56），
  // 而「吉林市」全名键不受影响。上游同序处理，可观察行为一致。
  let bare = iter_matches("吉林", matcher.index, matcher.max_key_len)
  inspect(bare[0].origin_value, content="吉林")
  inspect(bare[0].cands[0].name, content="吉林省")
  inspect(bare[0].cands[0].level is @adcodes.Province, content="true")
  let full = iter_matches("吉林省", matcher.index, matcher.max_key_len)
  inspect(full[0].origin_value, content="吉林省")
  inspect(full[0].cands[0].name, content="吉林省")
  let city = iter_matches("吉林市", matcher.index, matcher.max_key_len)
  inspect(city[0].origin_value, content="吉林市")
  inspect(city[0].cands[0].name, content="吉林市")
  inspect(city[0].cands[0].level is @adcodes.City, content="true")
}

///|
test "duplicate_names_share_candidate_list_in_row_order" {
  // 朝阳区同名候选共享列表，顺序 = 数据行序（adcodes.mbt 行 450 长春 220104
  // 在行 1500 北京 110105 之前）；无上级取候选首元素（M-6），禁止排序。
  let ms = iter_matches("朝阳区", matcher.index, matcher.max_key_len)
  inspect(ms[0].origin_value, content="朝阳区")
  inspect(ms[0].cands[0].name, content="朝阳区")
  inspect(ms[0].cands[0].adcode6, content="220104")
  inspect(ms[0].cands[1].adcode6, content="110105")
}

///|
test "no_match_yields_empty_match_list" {
  let ms = iter_matches("虹漕路461号", matcher.index, matcher.max_key_len)
  inspect(ms is [], content="true")
}

///|
test "same_end_suffix_collision_longest_wins" {
  // 同 end 后缀碰撞：「城东区」内含短键「东区」（攀枝花 510402）。
  // pyahocorasick 同 end 先长后短（实测），短匹配被 end <= prev_end 吞掉
  // （matcher.py:77）→ 只产出「城东区」（西宁 630102）。
  // 回归锁：修复前窗枚举最短先行，会把「城东区」错产成「东区」。
  let ms = iter_matches("城东区", matcher.index, matcher.max_key_len)
  let mut n = 0
  for m in ms {
    inspect(m.origin_value, content="城东区")
    inspect(m.start_index, content="0")
    n = n + 1
  }
  inspect(n, content="1")
}
