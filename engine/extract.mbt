// moon_cpca 提取引擎 — 公开入口骨架（T-01）
// 签名与结构体逐字取自引擎 spec §4.1 / §4.2。
// 本骨架最小实现：返回空记录（全 None + pos 全 -1，对齐上游 empty_record 口径，
// 权威锚点 chinese_province_city_area_mapper/cpca/__init__.py:152-158）。
// 匹配核心（候选索引 + 窗枚举 + 去重 + 消歧）由 T-02 在本包内实现。

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
  // T-01 骨架占位：显式消费兄弟数据包，维持 moon.pkg 依赖契约（import 白名单项
  // "moon_cpca/data" @adcodes）的编译期存续；T-02 匹配核心将从
  // @adcodes.adcodes 构建候选索引并替换本实现。
  let _ = @adcodes.adcodes
  let _ = text
  let _ = pos_sensitive
  let _ = umap
  {
    province: None,
    city: None,
    area: None,
    addr: None,
    adcode: None,
    province_pos: -1,
    city_pos: -1,
    area_pos: -1,
  }
}
