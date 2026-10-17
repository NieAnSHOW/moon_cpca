// moon_cpca 提取引擎 — 公开入口（T-02 匹配核心 + T-04 补全/umap/addr/空记录）
// 签名与结构体逐字取自引擎 spec §4.1 / §4.2。
// 本文件实现 transform 单记录路径（上游 _get_one_addr = _extract_addrs 的
// 首个产出，chinese_province_city_area_mapper/cpca/__init__.py:169-170；
// new_entry_when_not_belong=False、truncate_pos=True）。
// 匹配核心（候选索引 + 窗枚举 + 去重 + 消歧）在包内 matcher.mbt。
// T-04 落地面（brief Interfaces M-7..M-10）：
//   M-8 前缀补全 update_res_by_adcode / adcode_name（__init__.py:229-248）
//   M-9 addr = 最后一个匹配词 end_index 之后的子串（__init__.py:195/199/224）
//   M-10 空记录 = 全 None + pos 全 -1（__init__.py:152-158,176-178,219-221）
//   adcode 输出口径 = 6 位（12 位截前 6，__init__.py:45-46；Cand.adcode6 构造期截断）

///|
pub struct Location {
  province : String?
  city : String?
  area : String?
  addr : String?
  adcode : String?
  province_pos : Int32
  city_pos : Int32
  area_pos : Int32
}

///|
/// 单入口 + 可选标记参数（T-01 步 2 裁定，承接引擎 PRD C7-1；不拆双入口）。
/// `pos_sensitive` / `umap` 在函数体内为 Option 类型，缺省 None。
/// `umap` = 地名 → adcode（上游 transform 文档 __init__.py:97：
/// 「字典的 key 为区名，value 为 adcode，比如 {"朝阳区": "110105"}」；
/// value 与候选的 6 位 adcode 等值比较，锚 __init__.py:189 → matcher.py:17
/// `attr.adcode == first_adcode`，而 attr.adcode 已在构造期截为 6 位）。
/// 不传 umap 与传空 umap 行为一致（上游默认 `umap={}`，__init__.py:90；
/// 空字典 get → None → get_match_addr 走「无上级取候选首元素」分支）。
pub fn extract(
  text : String,
  pos_sensitive? : Bool,
  umap? : Map[String, String],
) -> Location {
  let pos_on = match pos_sensitive {
    Some(true) => true
    _ => false
  }
  extract_one(text, pos_on, umap)
}

///|
/// 上游 ad_2_addr_dict（__init__.py:80 `ad_map[record_dict["adcode"]] = addr_info`，
/// 由 __init__.py:87 的 _init_data 一次性构造）：key = 数据表 12 位 adcode，
/// value = AddrInfo（本引擎侧同形 = Cand，__init__.py:37-48 的 name/adcode 字段；
/// adcode 同样在构造期截前 6 位，锚 __init__.py:46）。
/// 按数据行序写入、同 key 后写覆盖前写 = Python dict 同语义。
/// 零网络 / 零文件 IO / 零环境变量读取（E13）：来源为兄弟数据包编译期常量。
let adcode_dict : Map[String, Cand] = build_adcode_dict(@adcodes.adcodes)

///|
fn build_adcode_dict(records : Array[@adcodes.Rec]) -> Map[String, Cand] {
  let m : Map[String, Cand] = Map([])
  for rec in records {
    m[rec.adcode] = {
      name: rec.name,
      adcode6: first_n(rec.adcode, 6),
      level: rec.level,
    }
  }
  m
}

///|
/// 右侧补零至 12 位（上游 _fill_adcode，__init__.py:229-230
/// `'{:0<12s}'.format(adcode)`）：省 2 位 / 市 4 位前缀补成完整 12 位码后查表。
fn fill_adcode(part : String) -> String {
  let buf = StringBuilder()
  let mut n = 0
  for ch in part {
    buf.write_char(ch)
    n = n + 1
  }
  let mut i = n
  while i < 12 {
    buf.write_char('0')
    i = i + 1
  }
  buf.to_string()
}

///|
/// 前缀反查区划名（上游 adcode_name，__init__.py:233-235
/// `addr = ad_2_addr_dict.get(_fill_adcode(part_adcode)); return None if addr is None
/// else addr.name`）：查不到 = None。
fn adcode_name(part : String) -> String? {
  match adcode_dict.get(fill_adcode(part)) {
    Some(addr) => Some(addr.name)
    None => None
  }
}

///|
/// 按【最终 adcode】反查省/市/区三级名（上游 update_res_by_adcode，
/// __init__.py:238-248 逐行移植；M-8 / V-07 / V-08）：
/// - 末级 adcode 以 "0000" 结尾 → 只写省（省级单独命中：市/区保持 None，V-08）；
/// - 以 "00" 结尾 → 写省 + 市；
/// - 否则三级全写（省 adcode[:2] / 市 adcode[:4] / 区 全串）。
/// 上游命中循环【从不】写名字段（__init__.py:191-196 只写 pos / last_info /
/// adcode / truncate_index），名字唯一来源即本函数，故 T-02 的「按选中记录级别
/// 直写自有字段」中间态由这里整体取代。
/// 直辖市形态（V-08）由数据行自然给出：如 110108 → adcode_name("11")="北京市"、
/// adcode_name("1101")="市辖区"，无需特判。
fn names_by_adcode(adcode6 : String) -> (String?, String?, String?) {
  let p = adcode_name(first_n(adcode6, 2))
  if adcode6.has_suffix("0000") {
    (p, None, None)
  } else if adcode6.has_suffix("00") {
    (p, adcode_name(first_n(adcode6, 4)), None)
  } else {
    (p, adcode_name(first_n(adcode6, 4)), adcode_name(adcode6))
  }
}

///|
/// 取码点下标 start 之后的尾串（含 start；start ≥ 码点数时为空串）。
/// addr 专用口径：入参是【码点下标】而非 UTF-16 码元下标（R10：禁用
/// String::length()/slice 的码元口径），故按 Char 迭代重建。
/// 对应上游 `sentence[truncate_index + 1:]`（__init__.py:199/224，
/// Python str 索引 = 码点索引，V-11）。
fn tail_after_codepoint(text : String, start : Int32) -> String {
  let buf = StringBuilder()
  let mut i = 0
  for ch in text {
    if i >= start {
      buf.write_char(ch)
    }
    i = i + 1
  }
  buf.to_string()
}

///|
/// 输出记录构造 = 上游 res 字典的两次「产出前落库」（__init__.py:198-200 与
/// 223-225，两处形态相同）：
/// - adcode 为 None（全程无被接受匹配 / 空输入，__init__.py:176-178,219-221）
///   → 空记录 empty_record（省/市/区/地址/adcode 全 None，pos 三槽 -1，M-10）；
/// - adcode 非 None → 前缀补全三级名 + addr = 最后匹配词 end_index 之后子串
///   （有匹配即有 addr，空尾串为 Some("")，④③ 等类 golden A 级期望）+
///   adcode = 6 位末级码。
fn build_record(
  adcode : String?,
  truncate_index : Int32,
  text : String,
  province_pos : Int32,
  city_pos : Int32,
  area_pos : Int32,
) -> Location {
  match adcode {
    None => empty_location(province_pos, city_pos, area_pos)
    Some(a) =>
      filled_location(a, truncate_index, text, province_pos, city_pos, area_pos)
  }
}

///|
/// empty_record（__init__.py:152-158）：省/市/区/地址/adcode 全 None，
/// pos 三槽由调用方线程携带（无匹配时恒为初值 -1，M-10 / V-10）。
fn empty_location(
  province_pos : Int32,
  city_pos : Int32,
  area_pos : Int32,
) -> Location {
  let loc : Location = {
    province: None,
    city: None,
    area: None,
    addr: None,
    adcode: None,
    province_pos,
    city_pos,
    area_pos,
  }
  loc
}

///|
/// 有被接受匹配时的产出（__init__.py:198-200 / 223-225 两处同形）：
/// 名字 = 最终 adcode 前缀反查（M-8），addr = truncate_index 之后尾串（M-9，
/// 空尾串 = Some("")，③④⑤⑩ 等类 golden A 级期望），adcode = 6 位末级码。
fn filled_location(
  adcode6 : String,
  truncate_index : Int32,
  text : String,
  province_pos : Int32,
  city_pos : Int32,
  area_pos : Int32,
) -> Location {
  let (p, c, ar) = names_by_adcode(adcode6)
  let loc : Location = {
    province: p,
    city: c,
    area: ar,
    addr: Some(tail_after_codepoint(text, truncate_index + 1)),
    adcode: Some(adcode6),
    province_pos,
    city_pos,
    area_pos,
  }
  loc
}

///|
/// transform 单记录路径（__init__.py:173-226 主循环的 _get_one_addr 形态）：
/// - last_info / adcode / truncate_index 贯穿线程：每个被接受的匹配更新三者
///   （190-195 行；truncate_index 只随【被接受】匹配前进 → addr 吞掉两个被
///   接受匹配之间的文本，V-09 quirk，不修正）；
/// - pos 槽位按候选首元素级别（matcher.get_rank = attr_infos[0].rank，
///   matcher.py:22-23），仅在 pos_sensitive 时写入（pos_setter，161-166 行）；
/// - 字段值由 build_record 按最终 adcode 前缀反查（M-8，238-248 行）；
/// - 县级命中：产出并重置（197-205 行）；transform 经 _get_one_addr(next)
///   只取首条产出 → 首个县级产出即最终记录，直接返回；
/// - 归属过滤无候选：静默跳过，线程状态不变（190-191 行 + 206 分支不触发，
///   new_entry_when_not_belong=False）；
/// - 全程无被接受匹配：收尾 adcode is None → 空记录（152-158,219-221 行）；
///   有匹配但无县级命中：收尾落库路径（223-225 行）产出市/省级记录。
fn extract_one(
  text : String,
  pos_sensitive : Bool,
  umap : Map[String, String]?,
) -> Location {
  let mut province_pos = -1
  let mut city_pos = -1
  let mut area_pos = -1
  let mut last_info : Cand? = None
  let mut adcode : String? = None
  let mut truncate_index = -1
  let matches = iter_matches(text, matcher.index, matcher.max_key_len)
  for m in matches {
    // umap 仅在无上级时被 get_match_addr 查询（matcher.py:14-18 的分支次序；
    // __init__.py:189 first_adcode = umap.get(match_info.origin_value) ——
    // 键 = 匹配原文，简称命中时同样按原文查）
    let first_adcode : String? = match umap {
      Some(u) => u.get(m.origin_value)
      None => None
    }
    match get_match_addr(m.cands, last_info, first_adcode) {
      Some(cur) => {
        // set_pos（__init__.py:192）：槽位 = 候选首元素级别
        if pos_sensitive {
          match m.cands[0].level {
            @adcodes.Province => province_pos = m.start_index
            @adcodes.City => city_pos = m.start_index
            @adcodes.Area => area_pos = m.start_index
          }
        }
        last_info = Some(cur)
        adcode = Some(cur.adcode6)
        truncate_index = m.end_index
        // 县级命中：产出并重置（__init__.py:197-205）；
        // transform 经 _get_one_addr 只取首条 → 首个县级产出即最终记录
        let is_county = match cur.level {
          @adcodes.Area => true
          _ => false
        }
        if is_county {
          return build_record(
            adcode, truncate_index, text, province_pos, city_pos, area_pos,
          )
        }
      }
      // 找不到归属候选：静默跳过（transform 模式，__init__.py:190-191）
      None => ()
    }
  }
  build_record(adcode, truncate_index, text, province_pos, city_pos, area_pos)
}
