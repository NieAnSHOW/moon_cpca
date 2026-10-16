// moon_cpca 提取引擎 — 公开入口（T-02）
// 签名与结构体逐字取自引擎 spec §4.1 / §4.2。
// 本文件实现 transform 单记录路径（上游 _get_one_addr = _extract_addrs 的
// 首个产出，chinese_province_city_area_mapper/cpca/__init__.py:169-170；
// new_entry_when_not_belong=False、truncate_pos=True）。
// 匹配核心（候选索引 + 窗枚举 + 去重 + 消歧）在包内 matcher.mbt。
// T-02 最小输出口径：命中级别自有字段 = 选中记录名 + pos + adcode；
// 跨级补全（update_res_by_adcode 的 adcode_name 链）与 addr 尾串截取由 T-04 完成。

///|
pub struct Location {
  province : String?
  city : String?
  area : String?
  addr : String?
  adcode : String?
  province_pos : Int
  city_pos : Int
  area_pos : Int
}

///|
/// 单入口 + 可选标记参数（T-01 步 2 裁定，承接引擎 PRD C7-1；不拆双入口）。
/// `pos_sensitive` / `umap` 在函数体内为 Option 类型，缺省 None。
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
/// transform 单记录路径（__init__.py:173-226 主循环的 _get_one_addr 形态）：
/// - last_info 贯穿线程：每个被接受的匹配更新 last_info / adcode（190-194 行）；
/// - pos 槽位按候选首元素级别（matcher.get_rank = attr_infos[0].rank，
///   matcher.py:22-23），仅在 pos_sensitive 时写入（pos_setter，161-166 行）；
/// - 字段按选中记录级别写入（T-02 用选中记录名；T-04 换 update_res_by_adcode
///   的 adcode_name 口径，238-248 行）；
/// - 县级命中：产出并重置（197-205 行）；transform 只取首条产出 → 直接返回；
/// - 归属过滤无候选：静默跳过，last_info 不变（190-191 行 + 206 分支不触发）；
/// - 全程无匹配：返回空记录（全 None + pos -1，对齐 empty_record，152-158 行）。
fn extract_one(
  text : String,
  pos_sensitive : Bool,
  umap : Map[String, String]?,
) -> Location {
  let mut province : String? = None
  let mut city : String? = None
  let mut area : String? = None
  let mut province_pos = -1
  let mut city_pos = -1
  let mut area_pos = -1
  let mut adcode : String? = None
  let mut last_info : Cand? = None
  let matches = iter_matches(text, matcher.index, matcher.max_key_len)
  for m in matches {
    // umap 仅在无上级时被 get_match_addr 查询（matcher.py:14-18 的分支次序）
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
        // T-02 最小字段：选中记录级别自有字段 = 选中记录名
        match cur.level {
          @adcodes.Province => province = Some(cur.name)
          @adcodes.City => city = Some(cur.name)
          @adcodes.Area => area = Some(cur.name)
        }
        last_info = Some(cur)
        adcode = Some(cur.adcode6)
        // 县级命中：产出并重置（__init__.py:197-205）；
        // transform 经 _get_one_addr 只取首条 → 首个县级产出即最终记录
        let is_county = match cur.level {
          @adcodes.Area => true
          _ => false
        }
        if is_county {
          return {
            province,
            city,
            area,
            addr: None, // addr 尾串截取（__init__.py:199）由 T-04 完成
            adcode,
            province_pos,
            city_pos,
            area_pos,
          }
        }
      }
      // 找不到归属候选：静默跳过（transform 模式，__init__.py:190-191）
      None => ()
    }
  }
  {
    province,
    city,
    area,
    addr: None, // addr 由 T-04 完成（__init__.py:219-226 收尾产出）
    adcode,
    province_pos,
    city_pos,
    area_pos,
  }
}
