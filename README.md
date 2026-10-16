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
