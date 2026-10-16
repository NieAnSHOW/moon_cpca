// 产物断言测试（运行面证据 A11 / 消费方构建证据 S2）
// 断言锚点：数据 spec §0 V-01 / V-02 / V-06，重名并存 spec §4.2（产物侧 12 位原值）
// 引用形态：`@data.` 限定引用（消除 T-01 观测的 0025 test_unqualified_package 警告）

///|
test "V01_total_record_count_is_3511" {
  inspect(@data.adcodes.length(), content="3511")
}

///|
test "V06_first_record_is_zhongxian_500233000000_area" {
  let first : @data.Rec = @data.adcodes[0]
  inspect(first.adcode, content="500233000000")
  inspect(first.name, content="忠县")
  inspect(first.level is @data.Area, content="true")
}

///|
test "chaoyang_districts_coexist_with_both_adcodes" {
  let rows = @data.adcodes.filter(fn(r) { r.name == "朝阳区" })
  inspect(rows.length(), content="2")
  let codes = rows.map(fn(r) { r.adcode })
  inspect(codes.contains("220104000000"), content="true")
  inspect(codes.contains("110105000000"), content="true")
}

///|
test "V02_level_counts_are_34_344_3133" {
  let mut n_province = 0
  let mut n_city = 0
  let mut n_area = 0
  for r in @data.adcodes {
    match r.level {
      @data.Province => n_province += 1
      @data.City => n_city += 1
      @data.Area => n_area += 1
    }
  }
  inspect(n_province, content="34")
  inspect(n_city, content="344")
  inspect(n_area, content="3133")
}
