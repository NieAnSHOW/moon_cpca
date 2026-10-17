# moon_cpca

moon_cpca 是一个 MoonBit 编译期常量数据包：内置中国行政区划（省/市/区县，共 3511 条），由仓库内 vendored 的上游 CSV 离线生成，产物零运行时依赖、零网络。

## 数据来源

- 上游项目：[DQinYuan/chinese_province_city_area_mapper](https://github.com/DQinYuan/chinese_province_city_area_mapper.git)，MIT 许可。本包数据派生自其 `cpca/resources/adcodes.csv`（已随本仓库 vendored），按 MIT 归属要求注明出处；上游项目与数据为 MIT 许可的参考来源。
- 数据版本口径（来源标识，写入产物头注释，不含墙钟时间戳）：上游文件名 `adcodes.csv` + 记录数 `3511` + CSV 内容 sha256 `66948fa1519ba053f22b8c2d05c897c9b19c44cdc3044e464b52f0143ff418fe`。
- 生成入口：`python tools/gen_adcodes.py`（可选 `--csv` / `--out` / `--no-network-check`，路径默认相对仓库根解析）。生成器零网络，每次运行落盘诊断报告 `_build/gen_report.json`：成功 = 摘要 + 六项自校，失败 = 逐项明细。
- 产物：`data/adcodes.mbt`（编译期常量，等级 `Province`/`City`/`Area` 按 adcode 前 6 位后缀派生：`0000`→省、`00`→市、其余→区县，共 34/344/3133 条）。消费方在自己的包配置 `moon.pkg` 中声明 `import { "moon_cpca/data" @adcodes }`，随后以 `@adcodes.` 限定引用。
- 机检入口：`python tools/check_artifact.py`（只读比对产物与上游 CSV）：`--records` 记录数、`--fields` 逐条 adcode/name、`--levels` 三档计数与后缀规则、`--dup`（无参 = 重名统计，带名称 = 该名称条数与 12 位 adcode 集合）、`--order` 首条与抽查位置逐字一致。
- 本仓库代码以 MIT 许可发布（见 `LICENSE`）；数据来源同受上游 MIT 许可约束，归属原作者 DQinYuan/chinese_province_city_area_mapper。

后续段落（引擎示例）追加于本段之后。

## 提取引擎示例

消费方在自己的包配置 `moon.pkg` 中声明引擎包（包别名为 `@engine`）：

```text
import {
  "moon_cpca/engine" @engine,
}
```

可运行示例（放在 `pkgtype(kind: "executable")` 的包中）：

```moonbit
fn opt_str(v : String?) -> String {
  match v {
    Some(s) => s
    None => "None"
  }
}

fn main {
  let loc = @engine.extract("徐汇区虹漕路461号58号楼5楼", pos_sensitive=true)
  println("province = " + opt_str(loc.province)) // 上海市
  println("city = " + opt_str(loc.city))         // 市辖区
  println("area = " + opt_str(loc.area))         // 徐汇区
  println("addr = " + opt_str(loc.addr))         // 虹漕路461号58号楼5楼
  println("adcode = " + opt_str(loc.adcode))     // 310104
  println("province_pos = " + loc.province_pos.to_string()) // -1
  println("city_pos = " + loc.city_pos.to_string())         // -1
  println("area_pos = " + loc.area_pos.to_string())         // 0
}
```

`umap` 用于给同名区县指定优先 adcode（键 = 匹配原文，值 = 6 位 adcode）：

```moonbit
let with_umap = @engine.extract(
  "朝阳区汉庭酒店大山子店",
  pos_sensitive=true,
  umap=Map([("朝阳区", "110105")]),
)
println(opt_str(with_umap.province)) // 北京市
println(opt_str(with_umap.adcode))   // 110105
```

行为口径：

- `pos_sensitive=true` 时 `province_pos` / `city_pos` / `area_pos` = 匹配词起始的**码点序号**（不是 UTF-16 码元序号，与上游 Python 的字符索引一致）；缺省或 `pos_sensitive=false` 时三个 pos 均为 `-1`。
- `adcode` 为 6 位字符串（上游 12 位码截取前 6 位）。
- 全程无匹配（含空输入）：`province` / `city` / `area` / `addr` / `adcode` 全为 `None`，三个 pos 全为 `-1`。
- 已知 quirks 与上游 v0.5.5 一致：同名区无上级限定时取候选列表首元素；`addr` = 最后一个匹配词之后的子串（可能吞掉后续文本）。

上游归属：行为基准为 [DQinYuan/chinese_province_city_area_mapper](https://github.com/DQinYuan/chinese_province_city_area_mapper.git) 的 cpca v0.5.5（MIT 许可）。上游仅作 golden 行为基准，**不进运行时依赖**；本包运行时零第三方依赖、零网络。

golden 与诊断命令（均在仓库根执行）：

```bash
python tools/gen_golden.py          # 重生成 testdata/golden.jsonl + testdata/golden.mbt
python tools/gen_golden.py --stats  # 只输出条数与逐类计数，不写产物
python tools/check_golden.py        # 校验双产物一致
python tools/check_deps.py          # 校验运行时依赖白名单
```

golden 比对失败的报告路径约定为 `testdata/e16_failure_report.txt`，由固定命令产生，报告含四项：输入 / 期望 / 实际 / 首个不一致字段：

```bash
python tools/check_deps.py && moon build --target native && moon test --target native --no-render > testdata/e16_failure_report.txt
```
