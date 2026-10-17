///|
/// moon_cpca 可运行示例（README「快速开始」的权威输出源）。
/// 运行：`moon run --target native example`（仓库根执行）。
/// stdout 8 行与 README「快速开始」输出块逐行一致（T-10 / A-14）。
/// 说明：`String?` 在此以 `opt_str` 展平为原串（None → "None"），
/// 规避 Option 的 deprecated Show；本示例只依赖引擎公开入口。

///|
fn opt_str(v : String?) -> String {
  match v {
    Some(s) => s
    None => "None"
  }
}

///|
fn main {
  let loc = @engine.extract(
    "徐汇区虹漕路461号58号楼5楼",
    pos_sensitive=true,
  )
  println("province = " + opt_str(loc.province))
  println("city = " + opt_str(loc.city))
  println("area = " + opt_str(loc.area))
  println("addr = " + opt_str(loc.addr))
  println("adcode = " + opt_str(loc.adcode))
  println("province_pos = " + loc.province_pos.to_string())
  println("city_pos = " + loc.city_pos.to_string())
  println("area_pos = " + loc.area_pos.to_string())
}
