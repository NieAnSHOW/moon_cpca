# 最小编译探针记录（moon_cpca 环境证据）

> 本文件是在 `F:/moonbit比赛/moon_cpca` 上做的本机工具链与环境探针的**唯一归档记录**。文档链（PRD / design / spec）中的行号指针指向本文件；行号变动即指针失效，修改时须同步核对引用方。

---

## 1. 本机工具链事实

- `moon version` → `moon 0.1.20261012 (748b63c 2026-10-12)`，特性 `rr_moon_mod` / `rr_moon_pkg`。
- 机器：win32 10.0.19045 x64（非管理员/非开发者模式，`moon new` 时 symlink 创建被拒 os error 1314，仅影响模板附带的 `README.md -> README.mbt.md`，不影响构建）。
- `moon` 可执行位置：`C:/Users/Administrator/.moon/bin/moon.exe`。

## 2. 目标可用性矩阵

| 命令 | 结果 |
|------|------|
| `moon build`（`preferred_target = "native"`） | ✅ `Finished. moon: ran N tasks` |
| `moon test --target native` | ✅ 正常输出 `Total tests: N, passed: N, failed: 0` |
| `moon run <pkg> --target native` | ✅ 正常执行并打印输出 |
| `moon test`（默认 wasm 目标） | ❌ 测试可执行退出码 `0xc0000139`（wasm 运行通道本机不可用） |
| `moon test --target js` | ❌ `The system cannot find the path specified` |
| `moon info` | ✅ 生成 `pkg.generated.mbti` |

结论：**本机验收统一用 `--target native`**；wasm / js 两项在交付环境验证前登记 `[LOCAL_DEAD_LINK]`（分类 = 能力未验证），不冒充通过。

## 3. 零依赖工程可用性

零第三方依赖的 `moon.mod`（无 import 块）工程在本机可直接 build / test —— 探针工程 `F:/Temp/zdprobe`：

```
moon version   → moon 0.1.20261012 (748b63c 2026-10-12)
moon build     → Finished. moon: ran 9 tasks, now up to date
moon test      → Total tests: 0, passed: 0, failed: 0
```

历史说明：早期（moon 0.1.20260915 时期）零依赖工程曾报 `Cannot inject the standard library moonbitlang/core: Cannot load the core file`，
当时的临时处置是执行一次 `moon add moonbitlang/x` 触发 registry 依赖解析以恢复 core 注入。
**在当前工具链（0.1.20261012）该 workaround 已非必需**，实现期不得把该依赖写进 `moon.mod`（依赖白名单纪律见引擎 spec §2 / §6 E13）。

## 4. 大数据表常量可行性

按「3511 条行政区划记录 + level 枚举」形态生成的编译期常量数组，本机实测可编译、可测、可断言：

| 探针 | 结果 |
|------|------|
| 工程 `F:/Temp/seatprobe`（`seat.mbt` = 3511 条记录 + `pub enum Level`） | ✅ `moon test` → `Total tests: 1, passed: 1, failed: 0` |
| `inspect(recs.length(), content="3511")` 快照断言 | ✅ 通过 |
| 首条 = `500233000000 / 忠县` | ✅ 逐字命中 |
| level 三档计数 | ✅ 省 34 / 市 344 / 区县 3133（与上游 CSV 直接统计一致） |
| 产物编译耗时 | ✅ < 0.4 s |
| 经纬度标识命中数 | ✅ 0 |
| 重名区县（朝阳区）记录条数 | ✅ 2（同名多条并存形态成立） |

## 5. 子包 import 形态（MoonBit 包 = 目录）

探针工程 `F:/Temp/impprobe`：`data/` 目录含（可为空的）`data/moon.pkg` 与 `data/adcodes.mbt`，`cmd/main/moon.pkg` 写：

```
import {
  "vicoproplus/impprobe/data" @adcodes,
}
```

`cmd/main/main.mbt` 调 `@adcodes.nums.length()` → `moon run cmd/main` 输出 `3` ✅。

反例：写 `"vicoproplus/impprobe/data/adcodes"`（把文件当包）→ `Cannot find import` ❌。

结论：**import 目标是目录，别名须显式声明**；产物路径 `data/adcodes.mbt` 的权威 import 形态 = `"<module>/data" @adcodes`。

## 6. 字符串索引口径（pos 对齐用）

| 探针 | 结果 |
|------|------|
| Python 3：`'上海😀市徐汇区虹漕路'.index('徐汇区')` / `len(...)` | `4` / `10`（**码点索引**，😀 占 1 位） |
| 同串 UTF-16 码元长度 | `11` |
| MoonBit `String::char_length()` | `10`（**与上游 pos 同口径**） |
| MoonBit `String::length()` | `11`（UTF-16 码元，**不可用于 pos**） |

探针工程 `F:/Temp/posprobe`：`posprobe_test.mbt` 断言 `char_length = 10` / `length = 11` → `moon test` 通过 ✅。

结论：与 Python 行为对齐的位置值一律**按 Char 迭代计数**，禁用 `length()`。

## 7. 模板与语言坑（实现期需绕开）

- `moon new` 生成的 `cmd/main/moon.pkg` 把 import 全注释掉，直接调 `@hello.hello()` 报 `Package "hello" not found`；
  需自己写 import 且加 `options("is-main": true)`，否则 `fn main` 报 `Unexpected main function in the non-main package`。
- `derive(Show)` 已 deprecated → 用 `derive(Debug)`。
- 同包 `*_test.mbt` 可直接调同包符号，但会触发 `test_unqualified_package` 警告（写 `@pkg.symbol` 更稳）。
- 上游 oracle 可跑：`cd chinese_province_city_area_mapper && python -c "from cpca import transform; ..."`（需 `pip install pyahocorasick`，已装 2.3.1；Python 3.12.10）。
