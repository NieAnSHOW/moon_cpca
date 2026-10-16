// moon_cpca 提取引擎 — A9 冒烟探针（T-01 步 6，plan A9 未执行路径探针之前置态）
// 断言 FINAL 预期行为：extract("上海市") 应得 province = Some("上海市")。
// 断言形态沿用兄弟数据包约定（`inspect(cond, content="true")`，规避 Option Show
// 的 deprecated 警告）；引用形态用 `@engine.` 限定（规避 0025 警告）。
// T-01 骨架返回空记录（全 None）→ 本探针当前为**预期红**（A9 前置状态，
// plan 明确记录为预期失败）；T-02 实现匹配核心后本探针转绿。
// pos 断言归 T-02 步 5（探针②），此处不加。

///|
test "a9_probe_shanghai" {
  let province = @engine.extract("上海市").province
  inspect(province is Some("上海市"), content="true")
}
