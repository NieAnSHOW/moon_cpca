# 打包/发布就绪性机械证据（moon_cpca）

- 采集时间：2026-10-17 12:56–12:58 (+08:00)
- 工作目录：`F:/moonbit比赛/moon_cpca`
- 工具链：`moon 0.1.20261012 (748b63c 2026-10-12)`，`Feature flags enabled: rr_moon_mod,rr_moon_pkg`
- 约束遵守情况：未编辑任何项目源文件；未 commit / 未 push；`moon publish` 仅以 `--dry-run` 调用一次；未登录、未触网发布。
- 副作用披露：`moon info` 在源码树生成了 3 个未跟踪的 `pkg.generated.mbti`（`data/`、`engine/`、`testdata/`），本报告完成后已删除以恢复现场（`_build/` 内容除外，见 #5 说明）。

## 主表

| # | 检查项 | 命令 | 退出码 | 结果/证据 |
|---|---|---|---|---|
| 1 | 远端 / 分支 / 最近提交 | `git remote -v`；`git status --short --branch`；`git log --oneline -3` | 0 / 0 / 0 | 远端仅 `origin https://github.com/vicoplus/moon_cpca.git`（fetch+push）；分支 `main...origin/main [ahead 13]`；未跟踪：`.qoder/`、`chinese_province_city_area_mapper/`；HEAD `e1a4375 T-08: 回填独立审计结论（APPROVED, rubric 15/15）` |
| 2 | 发布干跑 | `moon publish --dry-run < /dev/null`（90s 超时） | 255 | 未提示登录、未触网；输出 2 条 manifest 警告 + `module name must be in the form of <author>/<module_name>` + `Error: \`moon publish\` failed`；耗时 1.12s。发布在本地校验阶段即失败 |
| 3 | 凭证存在性 / 登录帮助 | `test -f ~/.moon/credentials.json`；`moon login --help` | 0 / 0 | `C:\Users\Administrator/.moon` 下 `credentials.json` **EXISTS**（仅判存在，未读内容）；`moon login` 选项仅 `-h/--help`、`--target-dir`、`-q`、`-v`、`--trace`、`--dry-run`。另：`moon whoami` → `Logged in as vicoproplus`（exit 0） |
| 4 | 顶层命令清单 | `moon help` | 0 | `package` / `doc` / `fmt` / `check` **均存在**。完整 34 条命令见附录 A.4 |
| 5 | 格式检查（不落盘源码） | `moon fmt --check` | 255 | **10 个文件**被判定需格式化；结尾 `Failed with 0 warnings, 0 errors.` + `Error: failed when formatting project`。源文件未被修改（`git status` 前后无源码变更）。注意：`--check` 把格式化副本写到 `_build/wasm-gc/release/format/`（mtime 12:56:49 = 本次命令），这些副本与源码存在**类型差异**（副本含 `Int32`，源码为 `Int`），且末尾出现 10 次 `failed to execute \`git --no-pager diff ...\`` |
| 6 | native 静态检查 | `moon check --target native` | 0 | `Finished. moon: ran 7 tasks, now up to date`；**0 warning / 0 error** |
| 7 | wasm-gc 构建 | `moon build --target wasm-gc` | 0 | `Finished. moon: ran 3 tasks, now up to date`（tail 20 行仅此 1 行） |
| 8 | wasm-gc 测试 | `moon test --target wasm-gc --no-render`（120s 超时） | 255 | 测试二进制无法启动：`The test executable exited with exit code: 0xc0000139`；未输出任何用例统计（未到断言阶段） |
| 9 | js 测试 | `moon test --target js --no-render`（60s 超时） | 255 | `The system cannot find the path specified.` + `The test executable exited with exit code: 1`。环境侧事实：PATH 上的 `C:\Users\Administrator\.bunpm\bin\node.cmd` 内容为 `"D:\nvm4w\nodejs\bun" %*`，而 `D:/nvm4w/nodejs/bun` **MISSING**；`bun 1.4.3` 可用；`deno`/`wasmtime` NOT FOUND |
| 10 | 生成接口文件 | `moon info` | 0 | `Finished. moon: ran 3 tasks, now up to date`；生成 6 个 `.mbti`（3 个源码树 `pkg.generated.mbti` + 3 个 `_build/native/debug/check/*`）。`engine` 与 `data` 的完整公开面见附录 B |
| 11 | mooncakes 命名约定（缓存） | `find ~/.moon -name moon.mod`（仅 1 个：core）；缓存包为 zip，改用 `unzip -p <zip> moon.mod` | 0 | `~/.moon` 仅 1 个 `moon.mod`（`lib/core`，`name = "moonbitlang/core"`）；`registry/cache` 下 5 个已缓存包 manifest 均为 `<owner>/<module>` 形式（见附录 A.11） |
| 12 | 公开 API / 测试块计数 | `grep -rn "^pub fn\|^pub struct\|^pub enum" engine data testdata`；`grep -rn "^test " engine data testdata` | 0 / 0 | 公开声明 **14 行**（含 3 个 `pkg.generated.mbti` 的 7 行；排除生成文件后为 **7**）；`test` 块 **39** 个（engine 33 / data 4 / testdata 2） |

## 关键结论（仅为上表事实的直接归纳）

1. **发布被模块名硬阻断**：`moon.mod` 的 `name = "moon_cpca"` 不满足 `<author>/<module_name>`；同时缺 `readme`、`repository` 两个 manifest 字段（两条 Warning）。干跑未进入网络阶段。
2. **本地 z 字形链路**：`moon check --target native` 与 `moon build --target wasm-gc` 均 0 退出，但**两个目标都无法跑测试**：wasm-gc 是加载器错误 `0xc0000139`，js 是 `node` 垫片指向不存在的 `D:\nvm4w\nodejs\bun`。因此本仓库当前**没有可复现的测试通过证据**（本次采集范围内）。
3. **`moon fmt --check` 不可作为干净门禁**：退出 255 且报 10 个文件，但 diff 内容包含 `Int`→`Int32` 等语义级差异，并伴随 `failed to execute ... git diff` 错误，说明比较基线（`_build/wasm-gc/release/format`）与工作树不一致，不能用其文件计数直接断言"10 个文件格式不合规"。
4. **包结构**：`engine`/`data`/`testdata` 三个包，无 `moon.pkg.json`，使用新版 `moon.pkg`；`data/moon.pkg` 与 `testdata` 之外无外部依赖声明（`engine` 仅依赖 `moon_cpca/data`）。
5. **公开面极小**：生产 API 仅 `engine.extract` + `engine.Location`，`data` 为 `adcodes`/`Rec`/`Level`；测试数据包的 `testdata` 也公开了 3 项（`golden_cases`、`golden_upstream_version`、`location_as_expected`）。

---

## 附录 A：原始输出

### A.1 git

```
$ git remote -v
origin	https://github.com/vicoplus/moon_cpca.git (fetch)
origin	https://github.com/vicoplus/moon_cpca.git (push)
EXIT=0

$ git status --short --branch
## main...origin/main [ahead 13]
?? .qoder/
?? chinese_province_city_area_mapper/
EXIT=0

$ git log --oneline -3
e1a4375 T-08: 回填独立审计结论（APPROVED, rubric 15/15）
df62d6c T-08 fix R2: E5 证据指针订正 + NFR 数值统一 + fmt 归因精确化
fda7481 T-08 fix R1: S1 静态门实测 + NFR 方法披露 + CO5 口径统一
EXIT=0
```

### A.2 `moon publish --dry-run`

```
$ moon publish --dry-run < /dev/null 2>&1
Warning: 'readme' field is not set or empty in module manifest
Warning: 'repository' field is not set or empty in module manifest
module name must be in the form of <author>/<module_name>
Error: `moon publish` failed
EXIT=255

Wall time: 1.12 seconds
```

未出现 login / token / 网络提示；未发生交互输入（stdin 已重定向 `/dev/null`）。

`moon.mod` 原文：

```
name = "moon_cpca"
version = "0.1.0"
license = "MIT"

preferred_target = "native"
```

### A.3 凭证与登录帮助

```
$ echo "HOME=$HOME"; ls -d ~/.moon
HOME=
C:\Users\Administrator/.moon

$ test -f ~/.moon/credentials.json && echo "EXISTS" || echo "MISSING"
EXISTS

$ moon whoami
Logged in as vicoproplus
EXIT=0
```

```
$ moon login --help
Log in to your account

Usage: moon.exe login [OPTIONS]

Options:
  -h, --help  Print help

Common Options:
      --target-dir <TARGET_DIR>  The target directory. Defaults to `<project-root>/_build`, or `<source-dir>/_build/<file-name>` for a standalone file
  -q, --quiet                    Suppress output
  -v, --verbose                  Increase verbosity
      --trace                    Trace the execution of the program
      --dry-run                  Do not actually run the command
EXIT=0
```

### A.4 `moon help`（命令清单）

```
The build system and package manager for MoonBit.

Usage: moon [OPTIONS] <COMMAND>

Commands:
  new                    Create a new MoonBit module
  build                  Build the current package
  check                  Check the current package, but don't build object files
  prove                  Prove the current package
  run                    Run a main package
  runwasm                Deprecated: use moon run --target wasm locally or moonx for registry packages
  test                   Test the current package
  clean                  Remove local build outputs or configured global caches
  fmt                    Format source code
  doc                    Generate documentation or searching documentation for a symbol
  explain                Explain compiler diagnostics and language topics
  info                   Generate public interface (`.mbti`) files for all packages in the module or workspace
  bench                  Run benchmarks in the current package
  add                    Add a dependency
  remove                 Remove a dependency
  install                Install a binary package globally or install project dependencies (deprecated without args)
  tree                   Display the dependency tree
  fetch                  Download a package to .repos directory (unstable)
  search                 Search modules and package summaries in the registry
  view                   View a registry module or a user's published modules
  work                   Workspace maintenance commands
  login                  Log in to your account
  whoami                 Show login status and username
  register               Register an account at mooncakes.io
  publish                Publish the current module
  package                Package the current module
  deprecate              Deprecate or restore all existing versions of a published module
  update                 Update the package registry index
  coverage               Code coverage utilities
  generate-build-matrix  Generate build matrix for benchmarking (legacy feature)
  upgrade                Upgrade toolchains
  shell-completion       Generate shell completion for bash/elvish/fish/pwsh/zsh to stdout
  version                Print version information and exit
  help                   Print this message or the help of the given subcommand(s)

Options:
  -V, --version  Print all version information and exit
  -h, --help     Print help

Common Options:
  -C <DIR>
          Change to DIR before doing anything else (must appear before the subcommand). Relative paths in other options and arguments are interpreted relative to DIR. Example: `moon -C a run .` runs the same as invoking `moon run .` from within `a`
      --target-dir <TARGET_DIR>
          The target directory. Defaults to `<project-root>/_build`, or `<source-dir>/_build/<file-name>` for a standalone file
  -q, --quiet
          Suppress output
  -v, --verbose
          Increase verbosity
      --trace
          Trace the execution of the program
      --dry-run
          Do not actually run the command
  -Z, --unstable-feature <UNSTABLE_FEATURE>
          Unstable flags to MoonBuild [env: MOON_UNSTABLE=] [default: ]
EXIT=0
```

### A.5 `moon fmt --check`（退出 255）

完整输出 1881 行；下列为逐文件清单（`diff --git` 行）与结尾原文。未应用任何格式化。

```
$ moon fmt --check
warning: in the working copy of 'F:\moonbit比赛\moon_cpca\_build\wasm-gc\release\format\testdata\golden.mbt', LF will be replaced by CRLF the next time Git touches it
diff --git "a/F:\\moonbit比赛\\moon_cpca\\testdata\\golden.mbt" "b/F:\\moonbit比赛\\moon_cpca\\_build\\wasm-gc\\release\\format\\testdata\\golden.mbt"
diff --git "a/F:\\moonbit比赛\\moon_cpca\\engine\\matcher.mbt" "b/F:\\moonbit比赛\\moon_cpca\\_build\\wasm-gc\\release\\format\\engine\\matcher.mbt"
diff --git "a/F:\\moonbit比赛\\moon_cpca\\engine\\extract.mbt" "b/F:\\moonbit比赛\\moon_cpca\\_build\\wasm-gc\\release\\format\\engine\\extract.mbt"
diff --git "a/F:\\moonbit比赛\\moon_cpca\\engine\\probe_test.mbt" "b/F:\\moonbit比赛\\moon_cpca\\_build\\wasm-gc\\release\\format\\engine\\probe_test.mbt"
diff --git "a/F:\\moonbit比赛\\moon_cpca\\testdata\\golden_test.mbt" "b/F:\\moonbit比赛\\moon_cpca\\_build\\wasm-gc\\release\\format\\testdata\\golden_test.mbt"
diff --git "a/F:\\moonbit比赛\\moon_cpca\\engine\\matcher_wbtest.mbt" "b/F:\\moonbit比赛\\moon_cpca\\_build\\wasm-gc\\release\\format\\engine\\matcher_wbtest.mbt"
diff --git "a/F:\\moonbit比赛\\moon_cpca\\moon.mod" "b/F:\\moonbit比赛\\moon_cpca\\_build\\wasm-gc\\release\\format\\moon.mod"
diff --git "a/F:\\moonbit比赛\\moon_cpca\\engine\\semantics_wbtest.mbt" "b/F:\\moonbit比赛\\moon_cpca\\_build\\wasm-gc\\release\\format\\engine\\semantics_wbtest.mbt"
diff --git "a/F:\\moonbit比赛\\moon_cpca\\engine\\location_fields_wbtest.mbt" "b/F:\\moonbit比赛\\moon_cpca\\_build\\wasm-gc\\release\\format\\engine\\location_fields_wbtest.mbt"
diff --git "a/F:\\moonbit比赛\\moon_cpca\\data\\moon.pkg" "b/F:\\moonbit比赛\\moon_cpca\\_build\\wasm-gc\\release\\format\\data\\moon.pkg"
...
failed to execute `git --no-pager diff --color=always --no-index F:\moonbit比赛\moon_cpca\data\moon.pkg F:\moonbit比赛\moon_cpca\_build\wasm-gc\release\format\data\moon.pkg`
Failed with 0 warnings, 0 errors.
Error: failed when formatting project
EXIT=255
```

代表性命中（`extract.mbt`，显示 b 侧 `Int32` 与 a 侧 `Int` 的差异）：

```
@@ -155,9 +161,9 @@ fn build_record(
 fn empty_location(
-  province_pos : Int,
-  city_pos : Int,
-  area_pos : Int,
+  province_pos : Int32,
+  city_pos : Int32,
+  area_pos : Int32,
 ) -> Location {
```

```
$ grep -c 'Int32' engine/extract.mbt _build/wasm-gc/release/format/engine/extract.mbt \
    engine/location_fields_wbtest.mbt _build/wasm-gc/release/format/engine/location_fields_wbtest.mbt
engine/extract.mbt:0
_build/wasm-gc/release/format/engine/extract.mbt:15
engine/location_fields_wbtest.mbt:0
_build/wasm-gc/release/format/engine/location_fields_wbtest.mbt:6

$ stat -c '%y %n' engine/extract.mbt _build/wasm-gc/release/format/engine/extract.mbt ...
2026-10-17 11:39:53 engine/extract.mbt
2026-10-17 12:56:49 _build/wasm-gc/release/format/engine/extract.mbt
```

`data/moon.pkg` 的完整 diff（仅多一个空行）：

```
diff --git "a/...\data\moon.pkg" "b/...\_build\wasm-gc\release\format\data\moon.pkg"
--- "a/...\data\moon.pkg"
+++ "b/...\_build\wasm-gc\release\format\data\moon.pkg"
@@ -0,0 +1 @@
+
```

`_build` 已被忽略：`git check-ignore -v _build` → `.gitignore:1:_build/	_build`。

### A.6 `moon check --target native`

```
$ moon check --target native 2>&1
Finished. moon: ran 7 tasks, now up to date
EXIT=0
```

无任何 warning/error 文本。

### A.7 `moon build --target wasm-gc`

```
$ moon build --target wasm-gc 2>&1 | tail -20
Finished. moon: ran 3 tasks, now up to date
EXIT=0
```

### A.8 `moon test --target wasm-gc --no-render`

```
$ moon test --target wasm-gc --no-render 2>&1 | tail -30
Error: failed to run test for target WasmGC

Caused by:
    Failed to run the test: F:\moonbit比赛\moon_cpca\_build\wasm-gc\debug\test\data\data.blackbox_test.wasm
    The test executable exited with exit code: 0xc0000139
EXIT=255
```

无 `Total tests`/`passed`/`failed` 行 —— 未执行到任何用例断言。

### A.9 `moon test --target js --no-render`

```
$ moon test --target js --no-render 2>&1 | tail -10
The system cannot find the path specified.
Error: failed to run test for target Js

Caused by:
    Failed to run the test: F:\moonbit比赛\moon_cpca\_build\js\debug\test\data\data.blackbox_test.js
    The test executable exited with exit code: 1
EXIT=255
```

运行时探测：

```
$ for c in node npm deno wasmtime; do ... "$c" --version ...; done
node       The system cannot find the path specified.
npm        The system cannot find the path specified.
deno       NOT FOUND
wasmtime   NOT FOUND

$ command -v node
C:\Users\Administrator\.bunpm\bin\node.cmd
$ cat C:/Users/Administrator/.bunpm/bin/node.cmd
@echo off
"D:\nvm4w\nodejs\bun" %*
$ test -e "D:/nvm4w/nodejs/bun" && echo EXISTS || echo MISSING
D:/nvm4w/nodejs/bun MISSING
$ bun --version
1.4.3
```

### A.10 `moon info` 与 `.mbti` 位置

```
$ moon info
Finished. moon: ran 3 tasks, now up to date
EXIT=0

$ find . -name "*.mbti" -not -path "./.git/*" | sort
./_build/native/debug/check/data/data.mbti
./_build/native/debug/check/engine/engine.mbti
./_build/native/debug/check/testdata/testdata.mbti
./data/pkg.generated.mbti
./engine/pkg.generated.mbti
./testdata/pkg.generated.mbti
```

### A.11 mooncakes 缓存命名约定

```
$ find "C:/Users/Administrator/.moon" -name "moon.mod"
C:/Users/Administrator/.moon/lib/core/moon.mod
# 数量 = 1

$ cat C:/Users/Administrator/.moon/lib/core/moon.mod
name = "moonbitlang/core"
version = "0.10.15+943464bfa"
readme = "README.md"
repository = "https://github.com/moonbitlang/core"
license = "Apache-2.0"
keywords = [ "core", "standard library" ]
warnings = "+test_unqualified_package+unqualified_local_using+missing_doc+..."
```

缓存包为 zip（无解包后的 `moon.mod`），逐个取出 manifest：

```
=== bobzhang/crescent/0.11.1.zip ===
name = "bobzhang/crescent"
version = "0.11.1"
readme = "README.md"
repository = "https://github.com/moonbit-community/crescent"
license = "Apache-2.0"

=== mizchi/x/0.6.1.zip ===
name = "mizchi/x"
version = "0.6.1"
readme = "README.md"
repository = "https://github.com/mizchi/x"
license = "Apache-2.0"

=== moonbit-community/yaml/0.0.3.zip ===
# 该包为旧格式，只有 moon.mod.json：
{
  "name": "moonbit-community/yaml",
  "version": "0.0.3",
  "readme": "README.md",
  "repository": "https://github.com/moonbit-community/yaml.mbt",
  "license": "MIT",
  "keywords": [],
  "description": "",
  "source": "src"
}

=== vicoproplus/moon_ua_parser/0.2.0.zip ===
name = "vicoproplus/moon_ua_parser"
version = "0.2.0"
readme = "README.mbt.md"
repository = "https://github.com/vicoproplus/moon_ua_parser"
license = "Apache-2.0"

=== moonbitlang/async/0.21.3.zip ===
name = "moonbitlang/async"
version = "0.21.3"
readme = "README.md"
repository = "https://github.com/moonbitlang/async"
license = "Apache-2.0"

=== moonbitlang/x/0.5.5.zip ===
name = "moonbitlang/x"
version = "0.5.5"

=== vicoproplus/moon_ua_parser_middleware_core/0.1.0.zip ===
name = "vicoproplus/moon_ua_parser_middleware_core"
version = "0.1.0"
```

结论（仅命名形式）：所有已发布模块均为 `<owner>/<module>`；owner 段存在大小写混合（`Kaida-Amethyst`，目录 `cache/Kaida-Amethyst/python/0.1.4.zip`）。本地 `moon_cpca` 无 owner 段。

### A.12 公开 API / 测试块计数

```
$ grep -rn "^pub fn\|^pub struct\|^pub enum" engine data testdata
engine\extract.mbt:14:pub struct Location {
engine\extract.mbt:34:pub fn extract(
engine\pkg.generated.mbti:5:pub fn extract(String, pos_sensitive? : Bool, umap? : Map[String, String]) -> Location
engine\pkg.generated.mbti:10:pub struct Location {
data\adcodes.mbt:5:pub enum Level {
data\adcodes.mbt:12:pub struct Rec {
data\pkg.generated.mbti:10:pub enum Level {
data\pkg.generated.mbti:16:pub struct Rec {
testdata\golden.mbt:12:pub struct GExpected {
testdata\golden.mbt:23:pub struct GCase {
testdata\golden.mbt:35:pub fn location_as_expected(loc : @engine.Location) -> GExpected {
testdata\pkg.generated.mbti:13:pub fn location_as_expected(@engine.Location) -> GExpected
testdata\pkg.generated.mbti:18:pub struct GCase {
testdata\pkg.generated.mbti:26:pub struct GExpected {
EXIT=0
# 合计 14 行；排除 *_generated.mbti 后 7 行

$ grep -rn "^test " engine data testdata | wc -l
39

# 按文件
      4 data\adcodes_test.mbt
      8 engine\location_fields_wbtest.mbt
      5 engine\matcher_wbtest.mbt
      9 engine\probe_test.mbt
     11 engine\semantics_wbtest.mbt
      2 testdata\golden_test.mbt
```

注：上表 `^pub fn|^pub struct|^pub enum` 不含 `pub let`（`data.adcodes`、`testdata.golden_cases`、`testdata.golden_upstream_version` 三项未计入）。

---

## 附录 B：包公开 API 全文（`moon info` 产物）

**`engine/pkg.generated.mbti`**（23 行）：

```moonbit
// Generated using `moon info`, DON'T EDIT IT
package "moon_cpca/engine"

// Values
pub fn extract(String, pos_sensitive? : Bool, umap? : Map[String, String]) -> Location

// Errors

// Types and methods
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

// Type aliases

// Traits
```

**`data/pkg.generated.mbti`**（24 行）：

```moonbit
// Generated using `moon info`, DON'T EDIT IT
package "moon_cpca/data"

// Values
pub let adcodes : Array[Rec]

// Errors

// Types and methods
pub enum Level {
  Province
  City
  Area
}

pub struct Rec {
  adcode : String
  name : String
  level : Level
}

// Type aliases

// Traits
```

**`testdata/pkg.generated.mbti`**（39 行，附列供交叉核对）：

```moonbit
// Generated using `moon info`, DON'T EDIT IT
package "moon_cpca/testdata"

import {
  "moon_cpca/engine",
}

// Values
pub let golden_cases : Array[GCase]
pub let golden_upstream_version : String
pub fn location_as_expected(@engine.Location) -> GExpected

// Types and methods
pub struct GCase {
  input : String
  category : String
  umap : Array[(String, String)]?
  upstream_version : String
  expected : GExpected
}

pub struct GExpected {
  province : String?
  city : String?
  area : String?
  addr : String?
  adcode : String?
  province_pos : Int
  city_pos : Int
  area_pos : Int
}
```

包依赖声明（`moon.pkg`，非 json 版式）：

```
--- engine/moon.pkg ---
import {
  "moon_cpca/data" @adcodes,
}
--- data/moon.pkg ---
（空文件）
--- testdata/moon.pkg ---
import {
  "moon_cpca/engine",
}
```

---

## 未获取到的事实（第一轮）

1. **发布端的真实校验结果**：`moon publish --dry-run` 在本地 manifest 校验即失败（模块名格式），未触达网络/注册表，因此没有 registry 冲突、版本占用、token 权限等任何远端事实。
2. **任何测试通过/失败数**：wasm-gc 与 js 两个目标均在启动测试二进制时失败（`0xc0000139` / node 路径缺失），未输出用例统计。native 目标本次未按指令执行测试，故亦无用例通过证据。
3. **`moon fmt --check` 的"真实需格式化文件数"**：命令给出 10 个文件，但 diff 含 `Int`→`Int32` 语义差异与 `failed to execute ... git diff` 错误，无法据此判定这 10 个文件仅是格式问题；未做 `moon fmt`（会改源）以取得干净结果。
4. **完整 1881 行 fmt diff**：报告仅保留逐文件清单与代表性命中（`extract.mbt` 类型差异、`data/moon.pkg` 全量 diff）。
5. **解包态 mooncakes 缓存包**：`~/.moon` 下 `moon.mod` 仅 1 个（core），其余缓存为 zip，故以 `unzip -p` 读取；`moonbit-community/yaml` 只有旧式 `moon.mod.json`，无 `moon.mod`。
6. **`node`/`npm` 可用性**：PATH 上的两个 `.cmd` 垫片均无法启动（`node.cmd` 指向不存在的 `D:\nvm4w\nodejs\bun`）；未尝试修复或改用 `bun` 重跑 —— 超出只读采集范围。

---

# 追加采集（2026-10-17 12:59–13:01 +08:00）

约束：仍未编辑任何项目源文件、未 commit / 未 push。第 2 项因真实仓库 manifest 校验失败无法产包，改在 **临时 clone** 中打补丁后取得包内容（补丁仅存在于 `F:\Temp\tmp.ltRBz2yjfK\moon_cpca_fmt_probe`，真实仓库 `moon.mod` 未被改动）。

## 追加主表

| # | 检查项 | 命令 | 退出码 | 结果/证据 |
|---|---|---|---|---|
| 1 | 干净树格式状态 | `git clone --no-local . <temp>`；`moon fmt --check`（clone 内） | 0 / **255** | 干净 clone（无 `_build`）仍报 255，列 **10 个文件**；diff 含 `Int`→`Int32`。clone 内实测 `git diff --no-index` 退出 **1**（有差异），工具把它打印成 `failed to execute ...`（10 次）。→ **已提交源码在本工具链下并非 format-clean** |
| 1b | 格式化影响面（仅 clone） | `moon fmt`；`git diff --stat`、`git diff --numstat`；再 `moon check --target native` | 0 / 0 / 0 | `moon fmt` 改 **11 个文件内容**（`+4453 −4144`），`git status` 另有 3 个仅换行差异文件；`data/adcodes.mbt` 单文件 `+3668 −3511`；格式化后 `moon check` 仍 0（说明格式化产物可编译）。`--check` 的 10 文件 ≠ `fmt` 的 11/14 文件，两者口径不一致 |
| 2 | 打包帮助 | `moon package --help` | 0 | 仅 `--frozen`、`--list`、公共选项；**`--dry-run` 存在但未实现**（实测报 `dry-run is not implemented for package`，退出 255） |
| 2b | 真实仓库打包 | `moon package --list`；`moon package --dry-run` | 255 / 255 | `--list` 同样被 manifest 校验拦截：2 条 Warning + `module name must be in the form of <author>/<module_name>` + `Error: \`moon package\` failed`。**真实仓库当前无法产出包** |
| 2c | 包内容（补丁 probe） | clone 内改 `name=vicoproplus/moon_cpca` + 2 个 `moon.pkg` import 前缀，再 `moon package --list` / `moon package` | 0 / 0 | 归档 `_build/publish/vicoproplus-moon_cpca-0.1.0.zip`；**33 文件 / 242,866 B**（不含未跟踪目录）。含 `docs/`(8)、`engine/`(7)、`tools/`(6)、`testdata/`(4)、`data/`(3)、`probe/`(1)、`LICENSE`、`README.md`、`moon.mod`、`申报书…md`。**不含** `.github/`、`.superpowers/`、`.qoder/`（点目录被排除）。把真实未跟踪目录复制进 probe 后重打：**57 文件 / 678,048 B**，`chinese_province_city_area_mapper/` **被包含 24 个文件**，`.superpowers/` 仍 **0 个** |
| 2d | 模块改名连带面 | `moon package --list`（只改 `moon.mod`、未改 import） | 255 | `Cannot find import 'moon_cpca/data' in vicoproplus/moon_cpca/engine@0.1.0` → 改名必须同步改 `engine/moon.pkg`、`testdata/moon.pkg`（以及 README 示例，非构建项） |
| 3 | 文档帮助 / 构建 | `moon doc --help`；`moon doc` | 0 / 0 | `Finished. moon: ran 1 task, now up to date`；产出 `_build/doc/moon_cpca/` 共 **17 个文件**，含 `engine/`(5)、`data/`(5)、`testdata/`(5)、`module_index.json`、`README.md`、`_sidebar.md`、`resource.json`。`engine`、`data` 均有 `*-html` + `members.md` + `package_data.json` → 两包文档均生成成功 |
| 4 | 官方模板 manifest | `moon new --user vicoproplus --name probe_manifest probe_manifest`（+ `moon new --help`） | 0 | 生成 `vicoproplus/probe_manifest`；模板 `moon.mod` 含 `name/version/readme/repository/license/keywords/preferred_target/description`（全文见附录 C.4）。注意：`README.md -> README.mbt.md` 符号链接创建失败（`os error 1314`，无开发者模式/管理员权限） |
| 5 | native 测试计数 | `moon test --target native --no-render`（tail 5） | 0 | `Total tests: 39, passed: 39, failed: 0.`（另有 `Blocking waiting for file lock ...` 提示，因并发进程占用 `_build`） |
| 6 | 未推送提交 | `git diff --stat origin/main..main`；`git cherry -v origin/main main` | 0 / 0 | 13 个提交全部不在 upstream（cherry 全为 `+`）；累计 **15 文件 `+3065 −47`**；内容 = T-03..T-08 的引擎实现/测试/工具/CI/文档 | 

## 追加采集的结论（直接归纳）

1. **格式门禁结论翻转**：干净 clone 仍 255，说明**仓库提交态确实未格式化**（不是 `_build` 脏基线造成的假阳性）；但 `--check` 的文件清单不可信（10 个），实际 `moon fmt` 会改 11 个文件内容（另 3 个换行差异），其中 `data/adcodes.mbt` 一步就是 3.6k 行。格式化后编译/静态检查仍绿。
2. **打包链路在真实仓库完全不可达**：`moon publish --dry-run`、`moon package --list`、`moon package --dry-run` 全部 255；前两者卡在同一个 manifest 校验点，`--dry-run` 对 package 未实现。
3. **一旦 manifest 修好，包会含大量非库内容**：`docs/`(8)、`tools/`(6)、`probe/`(1)、`testdata/`(4) 与根目录中文申报书都会进包；未跟踪的 vendored 上游 `chinese_province_city_area_mapper/`（24 个文件，整目录磁盘占用 2.1MB）也会被打进 zip（归档随之从 242,866 B 增至 678,048 B）。`.superpowers/`、`.qoder/`、`.github/` 因是点目录被排除。
4. **改名成本已被实测**：`moon.mod` 改名后必须同步 `engine/moon.pkg`、`testdata/moon.pkg`，否则包关系求解直接失败。
5. **native 是唯一可执行的测试目标**：39/39 通过（与 `grep "^test "` 的 39 个块数量一致）。

## 附录 C：追加采集原始输出

### C.1 干净 clone + `moon fmt --check`

```
$ PROBE=$(mktemp -d)/moon_cpca_fmt_probe
$ git clone --no-local . "$PROBE"
Cloning into 'F:/Temp/tmp.ltRBz2yjfK/moon_cpca_fmt_probe'...
CLONE_EXIT=0
# clone 内容：.git .gitattributes .github .gitignore LICENSE README.md data docs engine moon.mod probe testdata tools 申报书-....md
# 无 _build、无 chinese_province_city_area_mapper（未跟踪）

$ cd "$PROBE" && moon fmt --check > /tmp/fmt_probe.log 2>&1
EXIT=255

$ tail -20 /tmp/fmt_probe.log
...
failed to execute `git --no-pager diff --color=always --no-index F:\Temp\tmp.ltRBz2yjfK\moon_cpca_fmt_probe\testdata\golden_test.mbt F:\Temp\tmp.ltRBz2yjfK\moon_cpca_fmt_probe\_build\wasm-gc\release\format\testdata\golden_test.mbt`
Failed with 0 warnings, 0 errors.
Error: failed when formatting project

$ grep -c 'diff --git' /tmp/fmt_probe.log
10
$ grep -ac '^failed to execute' /tmp/fmt_probe.log
10
$ wc -l < /tmp/fmt_probe.log
1880
```

被点名的 10 个文件（a 侧 = clone 工作树）：

```
data/moon.pkg
engine/extract.mbt
engine/location_fields_wbtest.mbt
engine/matcher.mbt
engine/matcher_wbtest.mbt
engine/probe_test.mbt
engine/semantics_wbtest.mbt
moon.mod
testdata/golden.mbt
testdata/golden_test.mbt
```

类型改写证据（clone 内 `_build/.../format` 副本）：

```
@@ -24,8 +24,8 @@ priv struct Cand {
 priv struct MatchInfo {
   cands : Array[Cand]
-  start_index : Int
-  end_index : Int
+  start_index : Int32
+  end_index : Int32
   origin_value : String
 }

$ grep -c Int32 _build/wasm-gc/release/format/engine/matcher.mbt
10
$ grep -c Int32 _build/wasm-gc/release/format/engine/extract.mbt
15
```

`failed to execute` 的真实原因（同一对文件手工执行）：

```
$ git --no-pager diff --no-index engine/matcher.mbt _build/wasm-gc/release/format/engine/matcher.mbt > /dev/null 2>&1
GIT_DIFF_NO_INDEX_EXIT=1        # 1 = 文件有差异；moon 将其打印为 failed to execute
```

### C.2 clone 内实际执行 `moon fmt`（仅 probe，未触碰真实仓库）

```
$ moon fmt > /tmp/fmt_apply.log 2>&1
FMT_EXIT=0
Finished. moon: ran 14 tasks, now up to date

$ git diff --stat
 data/adcodes.mbt                  | 7179 +++++++++++++++++++------------------
 data/moon.pkg                     |    1 +
 engine/extract.mbt                |   47 +-
 engine/location_fields_wbtest.mbt |   76 +-
 engine/matcher.mbt                |   32 +-
 engine/matcher_wbtest.mbt         |    6 +-
 engine/probe_test.mbt             |   33 +-
 engine/semantics_wbtest.mbt       |  110 +-
 moon.mod                          |    2 +
 testdata/golden.mbt               | 1045 +++---
 testdata/golden_test.mbt          |   66 +-
# 11 files changed, 4453 insertions(+), 4144 deletions(-)

$ git diff --numstat
3668	3511	data/adcodes.mbt
1	0	data/moon.pkg
24	23	engine/extract.mbt
60	16	engine/location_fields_wbtest.mbt
18	14	engine/matcher.mbt
5	1	engine/matcher_wbtest.mbt
25	8	engine/probe_test.mbt
86	24	engine/semantics_wbtest.mbt
2	0	moon.mod
523	522	testdata/golden.mbt
41	25	testdata/golden_test.mbt

$ git status --short
 M data/adcodes.mbt
 M data/adcodes_test.mbt
 M data/moon.pkg
 M engine/extract.mbt
 M engine/location_fields_wbtest.mbt
 M engine/matcher.mbt
 M engine/matcher_wbtest.mbt
 M engine/moon.pkg
 M engine/probe_test.mbt
 M engine/semantics_wbtest.mbt
 M moon.mod
 M testdata/golden.mbt
 M testdata/golden_test.mbt
 M testdata/moon.pkg
# 14 个 status 条目，其中 3 个（adcodes_test.mbt / engine/moon.pkg / testdata/moon.pkg）仅换行差异（`git diff` 无内容）

$ moon check --target native
Finished. moon: ran 7 tasks, now up to date
CHECK_EXIT=0
```

格式化把 `Int` 落成 `Int32` 的源码级证据（clone 内）：

```
$ grep -c Int32 engine/extract.mbt
15
$ git --no-pager diff engine/extract.mbt | head -20
-  province_pos : Int
-  city_pos : Int
-  area_pos : Int
+  province_pos : Int32
+  city_pos : Int32
+  area_pos : Int32
```

### C.3 `moon package`（真实仓库 + probe）

```
$ moon package --help
Package the current module

Usage: moon.exe package [OPTIONS]

Options:
  -h, --help  Print help

Manifest Options:
      --frozen  Do not sync dependencies, assuming local dependencies are up-to-date
      --list    

Common Options:
      --target-dir <TARGET_DIR>  ...
  -q, --quiet
  -v, --verbose
      --trace
      --dry-run
EXIT=0

$ moon package --list
Warning: 'readme' field is not set or empty in module manifest
Warning: 'repository' field is not set or empty in module manifest
module name must be in the form of <author>/<module_name>
Error: `moon package` failed
EXIT=255

$ moon package --dry-run
dry-run is not implemented for package
Error: `moon package` failed
EXIT=255
```

probe（clone，manifest 改为 `vicoproplus/moon_cpca`，import 前缀同步）：

```
$ moon package --list
Running moon check ...
Finished. moon: ran 7 tasks, now up to date
Check passed
LICENSE
README.md
data\adcodes.mbt
data\adcodes_test.mbt
data\moon.pkg
docs\superpowers\designs\202610152151-moon_cpca-区划数据表-design.md
docs\superpowers\designs\202610152152-moon_cpca-提取引擎-design.md
docs\superpowers\plans\2026-10-16-moon_cpca-区划数据表.md
docs\superpowers\plans\2026-10-16-moon_cpca-提取引擎.md
docs\superpowers\prds\202610152151-moon_cpca-区划数据表-prd.md
docs\superpowers\prds\202610152152-moon_cpca-提取引擎-prd.md
docs\superpowers\specs\202610152151-moon_cpca-区划数据表-spec.md
docs\superpowers\specs\202610152152-moon_cpca-提取引擎-spec.md
engine\extract.mbt
engine\location_fields_wbtest.mbt
engine\matcher.mbt
engine\matcher_wbtest.mbt
engine\moon.pkg
engine\probe_test.mbt
engine\semantics_wbtest.mbt
moon.mod
probe\PROBE.md
testdata\golden.jsonl
testdata\golden.mbt
testdata\golden_test.mbt
testdata\moon.pkg
tools\check_artifact.py
tools\check_deps.py
tools\check_golden.py
tools\gen_adcodes.py
tools\gen_golden.py
tools\test_gen_adcodes.py
申报书-moon_cpca-中文省市区地址解析.md
Package to F:\Temp\tmp.ltRBz2yjfK\moon_cpca_fmt_probe\_build\publish\vicoproplus-moon_cpca-0.1.0.zip
EXIT=0

$ moon package
...
Package to F:\Temp\tmp.ltRBz2yjfK\moon_cpca_fmt_probe\_build\publish\vicoproplus-moon_cpca-0.1.0.zip
EXIT=0

$ unzip -Z1 ...zip | cut -d/ -f1 | sort | uniq -c
      3 data
      8 docs
      7 engine
      1 LICENSE
      1 moon.mod
      1 probe
      1 README.md
      4 testdata
      6 tools
      1 申报书-moon_cpca-中文省市区地址解析.md
$ unzip -Z1 ...zip | wc -l
33
$ ls -l _build/publish/vicoproplus-moon_cpca-0.1.0.zip
-rwxrwxrwx ... 242866 ... vicoproplus-moon_cpca-0.1.0.zip
```

把真实未跟踪目录复制进 probe 后重打：

```
$ cp -r "F:/moonbit比赛/moon_cpca/.superpowers" . && cp -r "F:/moonbit比赛/moon_cpca/chinese_province_city_area_mapper" . && cp -r "F:/moonbit比赛/moon_cpca/.qoder" .
$ moon package --list | grep -c 'superpowers\|chinese_province'
32
$ moon package
Package to ...\vicoproplus-moon_cpca-0.1.0.zip
EXIT=0

$ ls -l _build/publish/*.zip
-rwxrwxrwx ... 678048 ... vicoproplus-moon_cpca-0.1.0.zip

$ unzip -Z1 ...zip | cut -d/ -f1 | sort | uniq -c
     24 chinese_province_city_area_mapper
      3 data
      8 docs
      7 engine
      1 LICENSE
      1 moon.mod
      1 probe
      1 README.md
      4 testdata
      6 tools
      1 申报书-moon_cpca-中文省市区地址解析.md
$ unzip -Z1 ...zip | wc -l
57
$ unzip -Z1 ...zip | grep -c '^\.superpowers/'
0
$ unzip -Z1 ...zip | grep -c '^chinese_province_city_area_mapper/'
24
$ unzip -Z1 ...zip | grep -c '^\.github'
0
```

vendored 目录的过滤账（58 → 24）：

```
$ find chinese_province_city_area_mapper -type f | wc -l
58
$ find chinese_province_city_area_mapper/.git -type f | wc -l
28
$ find chinese_province_city_area_mapper -path '*__pycache__*' -type f | wc -l
4
$ find chinese_province_city_area_mapper -maxdepth 1 -name '.*' -type f | wc -l
2
# 58 − 28 − 4 − 2 = 24（.git/、__pycache__/、根点文件被排除）
```

改名未同步 import 时的报错（只改 moon.mod）：

```
$ moon package --list
Running moon check ...
Error: Failed to calculate build plan

Caused by:
    0: Failed to solve package relationship
    1: Cannot find import 'moon_cpca/data' in vicoproplus/moon_cpca/engine@0.1.0

moon check failed
Error: `moon package` failed
EXIT=255
```

### C.4 `moon new` 官方模板

```
$ moon new --help
Create a new MoonBit module

Usage: moon.exe new [OPTIONS] <PATH>

Arguments:
  <PATH>  The path of the new project

Options:
      --user <USER>  The username of the module. Default to the logged-in username
      --name <NAME>  The name of the module. Default to the last part of the path
  -h, --help  Print help
EXIT=0

$ moon new --user vicoproplus --name probe_manifest probe_manifest < /dev/null
Warning: failed to create file symlink: probe_manifest\README.md -> README.mbt.md. You may need to enable developer mode or have administrator privileges. 客户端没有所需的特权。 (os error 1314)
Initialized empty Git repository in F:/Temp/probe_manifest/.git/
Created vicoproplus/probe_manifest at probe_manifest
EXIT=0
```

生成的 `moon.mod`（逐字）：

```
// Learn more about moon.mod configuration:
// https://docs.moonbitlang.com/en/latest/toolchain/moon/module.html
//
// To add a dependency, run this command in your terminal:
//   moon add moonbitlang/x
//
// Or manually declare it in `import`, for example:
// import {
//   "moonbitlang/x@0.4.6",
// }

name = "vicoproplus/probe_manifest"

version = "0.1.0"

readme = "README.mbt.md"

repository = ""

license = "Apache-2.0"

keywords = []

preferred_target = "wasm"

description = ""
```

生成的文件树：`.git/`、`.githooks/{pre-commit,README.md}`、`.gitignore`、`AGENTS.md`、`LICENSE`、`moon.mod`、`moon.pkg`（空）、`probe_manifest.mbt`、`probe_manifest_test.mbt`、`probe_manifest_wbtest.mbt`、`README.mbt.md`（`README.md` 符号链接因权限失败未建）。

### C.5 native 测试

```
$ moon test --target native --no-render 2>&1 | tail -5
Blocking waiting for file lock F:\moonbit比赛\moon_cpca\_build\.moon-lock ...
Total tests: 39, passed: 39, failed: 0.
EXIT=0
```

### C.6 `moon doc`

```
$ moon doc --help
Generate documentation or searching documentation for a symbol

Usage: moon.exe doc [OPTIONS] [SYMBOL]

Options:
      --serve        Start a web server to serve the documentation
  -b, --bind <BIND>  The address of the server [default: 127.0.0.1]
  -p, --port <PORT>  The port of the server [default: 3000]
  -h, --help         Print help
...
EXIT=0

$ moon doc > /tmp/doc.log 2>&1
EXIT=0
Finished. moon: ran 1 task, now up to date

$ find _build/doc -maxdepth 3
_build/doc/moon_cpca/data/adcodes.mbt.html
_build/doc/moon_cpca/data/members.md
_build/doc/moon_cpca/data/package_data.json
_build/doc/moon_cpca/data/resource.json
_build/doc/moon_cpca/engine/extract.mbt.html
_build/doc/moon_cpca/engine/matcher.mbt.html
_build/doc/moon_cpca/engine/members.md
_build/doc/moon_cpca/engine/package_data.json
_build/doc/moon_cpca/engine/resource.json
_build/doc/moon_cpca/testdata/golden.mbt.html
_build/doc/moon_cpca/testdata/members.md
_build/doc/moon_cpca/testdata/package_data.json
_build/doc/moon_cpca/testdata/resource.json
_build/doc/moon_cpca/module_index.json
_build/doc/moon_cpca/README.md
_build/doc/moon_cpca/resource.json
_build/doc/moon_cpca/_sidebar.md
$ find _build/doc -type f | wc -l
17
```

### C.7 未推送提交

```
$ git diff --stat origin/main..main
 .github/workflows/ci.yml                           |  27 +
 README.md                                          |  69 +++
 .../plans/2026-10-16-moon_cpca-提取引擎.md         | 186 +++++++
 engine/extract.mbt                                 | 224 ++++++--
 engine/location_fields_wbtest.mbt                  | 328 ++++++++++++
 engine/matcher.mbt                                 |  16 +-
 engine/probe_test.mbt                              |  90 +++-
 engine/semantics_wbtest.mbt                        | 358 +++++++++++++
 testdata/golden.jsonl                              |  32 ++
 testdata/golden.mbt                                | 568 +++++++++++++++++++++
 testdata/golden_test.mbt                           | 260 ++++++++++
 testdata/moon.pkg                                  |   3 +
 tools/check_deps.py                                | 172 +++++++
 tools/check_golden.py                              | 402 +++++++++++++++
 tools/gen_golden.py                                | 377 +++++++++++++++
# 15 files changed, 3065 insertions(+), 47 deletions(-)

$ git cherry -v origin/main main
+ aab8285 T-03: golden 生成器+双产物一致性专检+比对骨架（oracle 现生成 32 条/13 类；启用⑥⑦⑧全字段比对；同 end 枚举序 load-bearing 探针转绿；步7 裁定 (b) 延后全量慢速集）
+ a4cbeba T-03 fix R1: check_golden 去重复方法块+docstring 与实现对齐
+ 80d3222 T-04: 补全·umap·addr 截断·空记录（M-7..M-10 落地；golden 全 13 类 32 条全字段比对全绿）
+ cc6bfe9 T-05: 依赖白名单机检 tools/check_deps.py（E13）+ golden 比对 E16 失败诊断报告
+ bf0a5b7 T-05 fix R1: check_deps 解析 moon.mod import 块形态 + 剥离 @version 后缀（E13 T2 违规模板）
+ 6535d5b T-06: M-1..M-7 匹配语义白盒测试 + Location 字段/NULL 性测试（golden 全量回归 38/38 绿）
+ b2c307d T-07: README 引擎示例段（追加）+ CI build/test 配置
+ da64d5b T-06 fix R1: umap value 位宽/空串边界回归锁（T-04 rubric 缺口）
+ 7c37ed3 T-07 fix R1: README moon.pkg 示例围栏标注（T07-I1）
+ 39e6504 T-08: 终验记录（E1-E16 三要素回填）+ 批末扫描
+ fda7481 T-08 fix R1: S1 静态门实测 + NFR 方法披露 + CO5 口径统一
+ df62d6c T-08 fix R2: E5 证据指针订正 + NFR 数值统一 + fmt 归因精确化
+ e1a4375 T-08: 回填独立审计结论（APPROVED, rubric 15/15）
EXIT=0
```

（cherry 输出中哈希为完整 40 位，此处按 `git log --oneline` 风格截断展示；全部前缀为 `+`，即均未进入 `origin/main`。）

---

## 未获取到的事实（追加采集后更新）

1. **真实仓库的包产物**：`moon package` / `--list` 在真实仓库均 255（manifest 校验），真实 `moon.mod` 未改名，因此**没有真实包路径/体积**；表中的 33 文件/242,866 B 与 57 文件/678,048 B 均来自临时 clone 的补丁 probe（`name` 与两个 `moon.pkg` import 被改）。
2. **registry 侧事实**：`publish --dry-run` 仍停在本地校验，未触网；版本占用、owner 权限、token scope、readme 渲染等均未知。
3. **wasm-gc / js 测试结果**：两目标仍在启动阶段失败（`0xc0000139`、node 垫片缺失），无任何用例计数；仅 native 得到 `39/39`。
4. **`moon fmt` 是否应被采纳**：已证明格式化会改写 11 个文件（含 `Int`→`Int32` 与 3.6k 行的 `data/adcodes.mbt` 重排）且格式化后仍可编译，但**未在真实仓库执行**，也未评估 `Int`→`Int32` 对公开 `.mbti` 的影响（本报告不推测）。
5. **`moon package --dry-run` 语义**：该工具链明确返回 `dry-run is not implemented for package`，故无法用 dry-run 取得包清单，只能用 `--list`（probe 中）。
6. **`.superpowers/` 是否会被真实打包**：probe 中 0 条目（点目录被排除），但未在真实仓库验证（真实仓库无法产包）。
7. **符号链接**：`moon new` 在无开发者模式/管理员权限下无法创建 `README.md -> README.mbt.md`（`os error 1314`）；未以提权方式重试。
8. **完整 diff**：`moon fmt` 在 probe 中产生的 4453/4144 行改动未逐行附上（仅 stat/numstat + 代表性 hunk）；真实仓库无任何 diff。
