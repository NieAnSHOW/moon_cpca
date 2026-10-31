# moon_cpca

moon_cpca 是一个 MoonBit 编译期常量数据包：内置中国行政区划（省/市/区县，共 3511 条），由仓库内 vendored 的上游 CSV 离线生成，产物零运行时依赖、零网络。

## 安装

```bash
moon add vicoproplus/moon_cpca@0.1.0
```

本包发布两个可消费包：`vicoproplus/moon_cpca/data`（区划常量表）与 `vicoproplus/moon_cpca/engine`（地址提取引擎）。消费方在自己的 `moon.pkg` 中声明引擎包（包别名 `@engine`）：

```text
import {
  "vicoproplus/moon_cpca/engine" @engine,
}
```

仅当需要从源码重新生成数据表 / golden 时，才需要 Python 开发依赖（运行时不需要）：

```bash
python -m pip install -r requirements-dev.txt
```

## 快速开始

仓库根执行 `moon run --target native example`（源码 `example/main.mbt`），退出码 0，stdout：

```text
province = 上海市
city = 市辖区
area = 徐汇区
addr = 虹漕路461号58号楼5楼
adcode = 310104
province_pos = -1
city_pos = -1
area_pos = 0
```

对应调用：

```moonbit
let loc = @engine.extract("徐汇区虹漕路461号58号楼5楼", pos_sensitive=true)
```

`umap` 用于给同名区县指定优先 adcode（键 = 匹配原文，值 = 6 位 adcode）：

```moonbit
let with_umap = @engine.extract(
  "朝阳区汉庭酒店大山子店",
  pos_sensitive=true,
  umap=Map([("朝阳区", "110105")]),
)
// with_umap.province = 北京市，with_umap.adcode = 110105
```

### golden 与诊断命令

golden 比对失败时，测试把「输入 / 期望 / 实际 / 首个不一致字段」四项打到 stderr；固定命令仅重定向 stderr 落盘到 `testdata/e16_failure_report.txt`（全绿时该文件为 0 字节）：

```bash
python tools/check_deps.py && moon build --target native && moon test --target native --no-render 2> testdata/e16_failure_report.txt
```

维护侧 golden 命令（均在仓库根执行）：

```bash
python tools/gen_golden.py          # 重生成 testdata/golden.jsonl + testdata/golden.mbt
python tools/gen_golden.py --stats  # 只输出条数与逐类计数，不写产物
python tools/check_golden.py        # 校验双产物一致
python tools/check_deps.py          # 校验运行时依赖白名单
```

## 兼容性

| 目标 | 状态 | 证据 |
|------|------|------|
| native | green | 本机 `moon run --target native example` 退出 0 且 stdout 与上文逐行一致；`moon test --target native --no-render` 40/40 通过 |
| wasm-gc | green | CI 迁移后首次完整运行 [run 41189175104](https://github.com/NieAnSHOW/moon_cpca/actions/runs/41189175104)（job `wasm-gc`，commit `5841095`）：`moon build --target wasm-gc` 退出 0，`moon test --target wasm-gc --no-render` 输出 `Total tests: 40, passed: 40, failed: 0`；本机测试二进制因 loader 报 `0xc0000139` 不可执行（`[LOCAL_DEAD_LINK]`，已由 CI 回补） |
| js | green | CI 迁移后首次完整运行 [run 41189175104](https://github.com/NieAnSHOW/moon_cpca/actions/runs/41189175104)（job `js`，commit `5841095`）：`moon test --target js --no-render` 输出 `Total tests: 40, passed: 40, failed: 0`，artifact `js-status` 内容为 `green`；本机 node 垫片缺失不可执行 |

native / wasm-gc 为本包支持目标；js 为非阻断目标，状态按 CI 运行记录显式二选一，不写默认值。

## 数据更新

- 数据文件：`chinese_province_city_area_mapper/cpca/resources/adcodes.csv`（vendored 上游快照，LF 行尾；内容 sha256 `de2acdf621afb9cef1232389166f420ae6da9cfab13172b39b0f2c50f8e48307`，与 `data/adcodes.mbt` 头注释逐字一致）。
- 记录数 3511：省 34 / 市 344 / 区县 3133（等级按 adcode 前 6 位后缀派生：`0000`→省、`00`→市、其余→区县）。
- vendored 快照逐字 8 路径（不随生成改写；含 `cpca/resources/__init__.py`，不含 `drawer.py`）：

```text
chinese_province_city_area_mapper/LICENSE
chinese_province_city_area_mapper/cpca/__init__.py
chinese_province_city_area_mapper/cpca/exceptions.py
chinese_province_city_area_mapper/cpca/matcher.py
chinese_province_city_area_mapper/cpca/structures.py
chinese_province_city_area_mapper/cpca/resources/__init__.py
chinese_province_city_area_mapper/cpca/resources/adcodes.csv
chinese_province_city_area_mapper/tests/test_cpca.py
```

- 唯一权威再生成入口（生成 → 格式化 → 三项机检 → `git diff` / `git status` 复核，共 8 步）：

```bash
python tools/regen.py
```

- 生成器零网络，产物为编译期常量 `data/adcodes.mbt`；每次运行落盘诊断 `_build/gen_report.json` 与 `_build/regen.log`，失败时 wrapper 打印首个失败行并非 0 退出。
- 机检入口：`python tools/check_artifact.py --records --fields --levels --order --dup`（记录数 / 逐条 adcode+name / 三档计数与后缀规则 / 顺序 / 重名）。

## 与上游差异

行为基准为 [DQinYuan/chinese_province_city_area_mapper](https://github.com/DQinYuan/chinese_province_city_area_mapper.git) 的 cpca v0.5.5（MIT 许可）。上游仅作 golden 行为基准，**不进运行时依赖**；本包运行时零第三方依赖、零网络、零文件 IO。

- `pos_sensitive=false`（缺省）时 `province_pos` / `city_pos` / `area_pos` 全为 `-1`；上游 `transform` 在 `pos_sensitive=false` 时**不返回** pos 列，本包固定返回 8 字段结构体，以 `-1` 表达「未提供 / 未命中」。
- 不提供多地址提取入口 `transform_text_with_addrs`（一次从长文本中提取多个地址）；该能力列为后续 PRD，当前 API 只做单条地址提取。
- 返回 `Location` 结构体而非 pandas `DataFrame`：零 pandas 依赖，字段固定为 `province` / `city` / `area` / `addr` / `adcode` / `province_pos` / `city_pos` / `area_pos`。
- `adcode` 为 6 位字符串（上游 12 位码截取前 6 位）；`pos_sensitive=true` 时三个 pos 为匹配词起始的**码点序号**（非 UTF-16 码元序号，与上游 Python 字符索引一致）。
- 全程无匹配（含空输入）：`province` / `city` / `area` / `addr` / `adcode` 全为 `None`，三个 pos 全为 `-1`。
- 已知 quirks 与上游 v0.5.5 一致：同名区无上级限定时取候选列表首元素；`addr` = 最后一个匹配词之后的子串（可能吞掉后续文本）。

数据来源与许可：数据派生自上游 `cpca/resources/adcodes.csv`（已随本仓库 vendored），按上游 MIT 许可注明出处；本仓库代码以 MIT 许可发布（见 `LICENSE`），归属原作者 DQinYuan/chinese_province_city_area_mapper。
