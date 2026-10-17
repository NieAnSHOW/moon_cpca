# Changelog

本文件记录 moon_cpca 的对外可见变更。版本号遵循语义化版本。

## 0.1.0

首个发布版本：中国省/市/区县常量数据包 + 单条地址提取引擎，零运行时第三方依赖、零网络、零文件 IO。

### 数据

- 数据文件：`chinese_province_city_area_mapper/cpca/resources/adcodes.csv`（vendored 上游 cpca v0.5.5 快照，LF 行尾）。
- 记录数 3511：省 34 / 市 344 / 区县 3133。
- CSV 内容 sha256：`de2acdf621afb9cef1232389166f420ae6da9cfab13172b39b0f2c50f8e48307`（与 `data/adcodes.mbt` 头注释逐字一致）。
- 再生成入口：`python tools/regen.py`（生成 → 格式化 → 机检 → `git diff`/`git status` 复核）。

### 公开 API

- `@engine.extract(text, pos_sensitive?, umap?) -> Location`：单条地址提取入口（`pos_sensitive` / `umap` 为可选标记参数）。
- `@engine.Location`：8 字段结构体 `province` / `city` / `area` / `addr` / `adcode`（`String?`）+ `province_pos` / `city_pos` / `area_pos`（`Int`，未匹配为 `-1`；与 spec §3.9 及 `engine/pkg.generated.mbti` 逐字一致）。
- `@adcodes.adcodes` / `@adcodes.Rec`：编译期区划常量表（`data` 包）。

### 与上游差异

- `pos_sensitive=false`（缺省）时三个 pos 全为 `-1`；上游 `transform` 在 `pos_sensitive=false` 时**不返回** pos 列。
- 不提供多地址提取入口 `transform_text_with_addrs`（列为后续 PRD）。
- 返回 `Location` 结构体而非 pandas `DataFrame`（零 pandas 依赖）。
- 其余行为（匹配语义、`addr` 尾串、`adcode` 6 位、码点 pos、`umap` 消歧）与上游 v0.5.5 一致，由 golden 40 条逐条 8 字段对齐。

### 目标支持状态

| 目标 | 状态 | 证据 |
|------|------|------|
| native | green | 本机 `moon run --target native example` 退出 0 且 stdout 与 README 逐行一致；`moon test --target native --no-render` 40/40 通过 |
| wasm-gc | green | CI 首次完整运行 [run 39060316841](https://github.com/vicoplus/moon_cpca/actions/runs/39060316841)（job `wasm-gc`，commit `c6a7e74`）：`moon build --target wasm-gc` 退出 0，`moon test --target wasm-gc --no-render` 输出 `Total tests: 40, passed: 40, failed: 0`；本机测试二进制因 loader 报 `0xc0000139` 不可执行（已由 CI 回补） |
| js | green | CI 首次完整运行 [run 39060316841](https://github.com/vicoplus/moon_cpca/actions/runs/39060316841)（job `js`，commit `c6a7e74`）：`moon test --target js --no-render` 输出 `Total tests: 40, passed: 40, failed: 0`，artifact `js-status` 内容为 `green`；本机 node 垫片缺失不可执行 |
