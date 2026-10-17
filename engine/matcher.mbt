// moon_cpca 提取引擎 — 匹配核心（T-02）
// 上游权威锚点（vendored，只读）：
//   chinese_province_city_area_mapper/cpca/matcher.py      （全文 1-96 行）
//   chinese_province_city_area_mapper/cpca/__init__.py:43-60（AddrInfo: adcode 截断 / rank / belong_to）
// 行为等价移植（引擎 spec §3 范式）：不复刻 Aho-Corasick 本体，只保证可观察
// 行为一致 —— 键集合相同、枚举序相同（end 下标升序，同 end 最长匹配在前）、
// 去重与消歧逐行对齐 matcher.py:71-95 / 13-20。上游 quirks 即契约，不做修正。

///|
/// 候选记录（上游 AddrInfo 的引擎侧形态）。adcode 在构造期截为前 6 位
/// （cpca/__init__.py:46 `self.adcode = adcode[:6]`）；level ⇔ 上游 rank
/// （Province=0 / City=1 / Area=2，数据 spec 保证与 adcode 后缀推导等价）。
priv struct Cand {
  name : String
  adcode6 : String
  level : @adcodes.Level
}

///|
/// 单个匹配区间（上游 matcher.MatchInfo，matcher.py:5-11）。
/// start_index / end_index 为码点下标（左闭右闭区间口径与上游一致，
/// matcher.py:74-76 的 end_index 与 start_index = end_index - len + 1）。
/// end_index 由 addr 尾串截取消费（T-04，__init__.py:195/199/224 的
/// truncate_index 线程：res[_ADDR] = sentence[truncate_index + 1:]）。
priv struct MatchInfo {
  cands : Array[Cand]
  start_index : Int32
  end_index : Int32
  origin_value : String
}

///|
/// 匹配器：候选索引 + 最长键码点长度（枚举窗上限）。
/// 对齐上游模块级单例 matcher（cpca/__init__.py:87）。
priv struct Matcher {
  index : Map[String, Array[Cand]]
  max_key_len : Int32
}

///|
/// 全局候选索引（进程内一次构建；零网络 / 零文件 IO / 零环境变量读取）。
let matcher : Matcher = build_matcher(@adcodes.adcodes)

///|
/// 候选索引构造（matcher.py:47-61 逐行移植）：
/// - 按数据行序逐条加入；键绑定顺序 = 列表共享，全名与简称指向同一列表；
/// - 全名键已存在（如 286 个「市辖区」、2 个「朝阳区」）→ 追加进既有共享列表
///   （matcher.py:60-61 的 `ac.get(name) or _first_add_addr` 复用分支）；
/// - 简称键重复绑定按 pyahocorasick add_word 语义【覆盖】而非合并：
///   吉林省（简称吉林）先加入，其后 吉林市（简称吉林）覆盖「吉林」键指向
///   吉林市的列表，而「吉林省」全名键不受影响（matcher.py:50-56）。
fn build_matcher(records : Array[@adcodes.Rec]) -> Matcher {
  let index : Map[String, Array[Cand]] = Map([])
  let mut max_key_len = 0
  for rec in records {
    let cand : Cand = {
      name: rec.name,
      adcode6: first_n(rec.adcode, 6),
      level: rec.level,
    }
    match index.get(rec.name) {
      // 全名键已存在：追加进共享列表，不再新建/覆盖任何键（matcher.py:60-61）
      Some(share) => share.push(cand)
      None => {
        let share : Array[Cand] = []
        share.push(cand)
        let abbr = abbr_name(rec.name)
        // 全名与简称共享同一列表；若简称键已被占用则覆盖（add_word 语义）
        index[abbr] = share
        index[rec.name] = share
        let name_len = char_len(rec.name)
        if name_len > max_key_len {
          max_key_len = name_len
        }
      }
    }
  }
  { index, max_key_len, }
}

///|
/// 简称推导（matcher.py:47-48 `_abbr_name` + stop_key `([省市]|特别行政区|自治区)$`，
/// cpca/__init__.py:63-65）：五个自治区走 special_abbre（matcher.py:35-41，
/// 例如 广西壮族自治区 若走后缀剥离会得到「广西壮族」，故必须走特表）；
/// 其余剥掉且仅剥掉一个尾部停用后缀。区/县不剥（__init__.py:64 注释：
/// 区县数目太多，去掉「区」字后极易误配）。
fn abbr_name(name : String) -> String {
  match name {
    "内蒙古自治区" => "内蒙古"
    "广西壮族自治区" => "广西"
    "西藏自治区" => "西藏"
    "新疆维吾尔自治区" => "新疆"
    "宁夏回族自治区" => "宁夏"
    _ => strip_stop_suffix(name)
  }
}

///|
/// 剥掉一个尾部停用后缀（stop_key 正则的等价实现）。先试长后缀
/// 「特别行政区」(5 字)、「自治区」(3 字)，再试「省/市」(1 字)；
/// 各分支互斥（长后缀均以「区」收尾，与 省/市 不可能同时命中），只剥一个。
fn strip_stop_suffix(name : String) -> String {
  if name.has_suffix("特别行政区") {
    return drop_last_n(name, 5)
  }
  if name.has_suffix("自治区") {
    return drop_last_n(name, 3)
  }
  if name.has_suffix("省") || name.has_suffix("市") {
    return drop_last_n(name, 1)
  }
  name
}

///|
/// 码点（Char）计数 —— pos 口径的唯一合法长度来源。
/// 禁用 `String::length()`（UTF-16 码元口径，spec §4.2 / R10）。
fn char_len(s : String) -> Int32 {
  let mut n = 0
  for _ in s {
    n = n + 1
  }
  n
}

///|
/// 取前 n 个码点（12 位 adcode → 6 位截断，cpca/__init__.py:46）。
fn first_n(s : String, n : Int32) -> String {
  let buf = StringBuilder()
  let mut i = 0
  for ch in s {
    if i < n {
      buf.write_char(ch)
      i = i + 1
    } else {
      break
    }
  }
  buf.to_string()
}

///|
/// 丢弃末尾 n 个码点（停用后缀剥离用；调用方保证 n ≤ char_len）。
fn drop_last_n(s : String, n : Int32) -> String {
  let buf = StringBuilder()
  let mut keep = char_len(s) - n
  for ch in s {
    if keep > 0 {
      buf.write_char(ch)
      keep = keep - 1
    } else {
      break
    }
  }
  buf.to_string()
}

///|
/// 由码点数组构造 text[start..=end] 子串（码点下标口径，UTF-16 安全）。
fn chars_between(chars : Array[Char], start : Int32, end : Int32) -> String {
  let buf = StringBuilder()
  for i in start..<=end {
    buf.write_char(chars[i])
  }
  buf.to_string()
}

///|
/// 窗枚举 + 区间去重（matcher.py iter，71-95 行逐行移植）。
///
/// 枚举序 = Aho-Corasick `iter` 的可观察序：end 下标升序；同一 end 内
/// 最长匹配在前、短匹配在后（AC 沿 fail 链从当前终态往回走，实测
/// pyahocorasick 同 end 先长后短）。对每个 end 回看
/// min(end+1, max_key_len)..=1 的窗口（起点升序 = 窗长降序），
/// 查候选索引命中即为一次匹配。
///
/// 去重（逐行对齐 matcher.py:77-92）：
/// - `end <= prev_end` 直接 continue（M-2 不重叠）；
/// - `start == prev_start` 时当前（更长的全称）匹配顶掉挂起项并立即产出，
///   挂起清空（M-4 同区间后写胜出 / 全称胜简称，matcher.py:81 注释）；
/// - 否则产出挂起项、当前成为新挂起；结尾冲刷最后的挂起项（94-95 行）。
fn iter_matches(
  text : String,
  index : Map[String, Array[Cand]],
  max_key_len : Int32,
) -> Array[MatchInfo] {
  let chars : Array[Char] = []
  for ch in text {
    chars.push(ch)
  }
  let results : Array[MatchInfo] = []
  let mut prev_start : Int32? = None
  let mut prev_end : Int32? = None
  let mut pending : MatchInfo? = None
  for end, _ch in chars {
    let hi = if end + 1 < max_key_len { end + 1 } else { max_key_len }
    // 同 end 内起点升序 = 窗长降序（最长先产出）：短后缀匹配随后被
    // `end <= prev_end` 吞掉（matcher.py:77），与上游同 end 先长后短一致。
    let lo = end - hi + 1
    for start in lo..<=end {
      let key = chars_between(chars, start, end)
      match index.get(key) {
        Some(cands) => {
          // matcher.py:77 — end <= prev_end：跳过（M-2 不重叠）
          let skip = match prev_end {
            Some(pe) => end <= pe
            None => false
          }
          if !skip {
            let cur : MatchInfo = {
              cands,
              start_index: start,
              end_index: end,
              origin_value: key,
            }
            match pending {
              Some(pm) => {
                let same_start = match prev_start {
                  Some(ps) => start == ps
                  None => false
                }
                if same_start {
                  // matcher.py:83-85 — 全称后到：产出全称，清空挂起（M-4）
                  results.push(cur)
                  pending = None
                } else {
                  // matcher.py:86-88 — 产出挂起项，当前成为新挂起
                  results.push(pm)
                  pending = Some(cur)
                }
              }
              None => pending = Some(cur)
            }
            prev_start = Some(start)
            prev_end = Some(end)
          }
        }
        None => ()
      }
    }
  }
  // matcher.py:94-95 — 冲刷最后的挂起项
  match pending {
    Some(pm) => results.push(pm)
    None => ()
  }
  results
}

///|
/// 归属判断（上游 AddrInfo.belong_to，cpca/__init__.py:58-60）：
/// `self.adcode.startswith(other.adcode[:(other.rank+1)*2])` ——
/// 用 6 位截断码做前缀比较，前缀长度 省 2 位 / 市 4 位 / 区 6 位。
fn belong_to(cand : Cand, parent : Cand) -> Bool {
  let n = match parent.level {
    @adcodes.Province => 2
    @adcodes.City => 4
    @adcodes.Area => 6
  }
  first_n(cand.adcode6, n) == first_n(parent.adcode6, n)
}

///|
/// 消歧（上游 MatchInfo.get_match_addr，matcher.py:13-20 逐行移植）：
/// - 有上级 last_info → 第一个 belong_to 的候选（M-5 前缀过滤）；
///   找不到 → None（transform 模式下该匹配被静默丢弃，__init__.py:190-191，
///   new_entry_when_not_belong=False）。
/// - 无上级且 umap 命中匹配原文 → 该 adcode 的候选，未命中回退候选首元素
///   （matcher.py:16-18，M-7 钩子；umap 仅在无上级时被查询）。
/// - 无上级无 umap → 候选首元素（M-6，数据行序，禁止排序）。
fn get_match_addr(
  cands : Array[Cand],
  parent : Cand?,
  first_adcode : String?,
) -> Cand? {
  match parent {
    Some(p) => {
      for c in cands {
        if belong_to(c, p) {
          return Some(c)
        }
      }
      None
    }
    None =>
      match first_adcode {
        Some(fa) => {
          for c in cands {
            if c.adcode6 == fa {
              return Some(c)
            }
          }
          Some(cands[0])
        }
        None => Some(cands[0])
      }
  }
}
