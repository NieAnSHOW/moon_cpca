# 设计文档：moon_cpca 交付收口单元

> **文档编号**：DESIGN-2026-03
> **状态**：📝 草稿（C-01 已裁决：wrapper 权威 + checker 更新；设计就绪 P7，见 §九）
> **关联 PRD**：`docs/superpowers/prds/202610171403-moon_cpca-交付收口-prd.md`（20 FR / 5 US / 10.6 单份 PRD）

---

## P6 Step 0 门禁

**设计文档必须存在。** 理由：

1. **不可逆或高影响变更**：模块名从 `moon_cpca` 改为 `vicoproplus/moon_cpca` 是公开身份与 import 路径的一次性破坏；mooncakes 首发不可撤回（只能后续弃用版本）。
2. **真实分叉**：生成物格式稳定性策略、CI job 结构、vendored 快照范围、发布包内容都存在至少两个可行方案，且选择会改变验收口径。
3. **验收可达性承载**：G-01 依赖干净 clone 的再生入口，G-03 依赖 CI 目标结构与 wasm-gc 执行载体；这些不是实现细节，而是验收能否被观察的结构条件。

**不重新拆分 PRD**：PRD §10.6 已裁定「单份 PRD，无需拆分」。本设计只承接该 PRD，不产生兄弟 PRD，不改变 FR 边界。

---

## 一、用户当前理解 / 认知校准

维护者当前的理解是「本机 `moon test` 通过、引擎行为正确，交付基本完成」。校准后的实际状态：

- **本机工作树 ≠ 可交付仓库**：`chinese_province_city_area_mapper/` 未入库，`git ls-files` 计数为 0；干净 clone 无法运行数据与 golden 生成（证据：`.superpowers/gap-audit/evidence-parity.md:35`）。
- **本机通过 ≠ 发布可用**：`moon publish --dry-run` 在 manifest 校验阶段退出 255；模块名缺作者前缀，且缺 readme/repository（证据：`.superpowers/gap-audit/evidence-packaging.md:14`）。
- **native 通过 ≠ 跨目标可验证**：CI 只覆盖 native；wasm-gc 本机测试启动报 `0xc0000139`，js 的 `node` 垫片指向不存在的路径（证据：`.superpowers/gap-audit/evidence-packaging.md:19-21`、`.github/workflows/ci.yml:23-27`）。
- **32 条 golden（T-09 后为 40 条）≠ 上游用例全覆盖**：上游 11 条单条输入中 5 条未覆盖、2 条部分覆盖；`test_umap` 第 2 条未覆盖（证据：`.superpowers/gap-audit/evidence-parity.md:49-75`）。
- **README 示例 ≠ 可运行示例**：仓库无 example 包；E16 诊断命令只重定向 stdout，stderr 四项不会进入报告文件（证据：`README.md:82`、`.superpowers/gap-audit/evidence-parity.md:174`）。

**校准结论**：本单元是「交付面收口」，不是引擎功能开发。设计必须以「干净 clone 可观察、注册表可观察、CI 可观察、逐条覆盖可观察」为第一优先级。

---

## 二、目标

引用 PRD §二 G-01～G-05，不在本文重复验收值。

| 目标 | 设计承接 | 可观察路径 |
|------|----------|------------|
| G-01 干净 clone 可复现 | D-02 快照 + D-03 wrapper 权威 + D-10 dev 依赖 | 全新 clone 执行 `python tools/regen.py`，退出 0 且 `git diff --exit-code` 为 0 |
| G-02 v0.1.0 发布 | D-01 原子改名 + D-06 包内容 + D-11 文档 | dry-run 输出 `202 Accepted` + `Dry run completed successfully`（exit 255 不单独判失败）；真实发布 200；`moon view ... --versions` 含 0.1.0；消费方 build 0 |
| G-03 跨目标可验证 | D-04 CI 结构 + D-08 wasm-gc 执行 + D-09 js 状态 | CI 运行记录逐 job 可检索；wasm-gc 有用例计数；js 非空二选一 |
| G-04 上游逐条对齐 | D-05 覆盖映射权威文档 + 机器检查 | 14 行映射逐行可定位；golden 覆盖 10 条字符串输入 + 2 条 umap；差异 0 |
| G-05 文档与示例可执行 | D-11 example/README/CHANGELOG + D-12 诊断命令 | example 在 native 运行；README 五段；报告含四项 |

---

## 三、关键约束

### 3.1 技术约束

| 编号 | 约束 | 证据 / 指针 | 设计影响 |
|------|------|-------------|----------|
| T1 | MoonBit 工具链 `0.1.20261012`；native 可构建/执行，wasm-gc 可构建，js 运行器缺失 | `moon version`；`.superpowers/gap-audit/evidence-packaging.md:14-21` | 目标矩阵按 native / wasm-gc / js 分开；wasm-gc 执行是发布阻断项 |
| T2 | 运行时零第三方依赖：`moon.mod` deps 为空，`engine` 仅 import `moon_cpca/data` | `tools/check_deps.py`；`engine/moon.pkg:2` | 新增 `example/` 只能 import 本模块内部包；Python 依赖只进 dev 需求 |
| T3 | mooncakes 模块名必须是 `<author>/<module_name>` | `moon.mod:1`；`moon publish --dry-run` 输出 | 一次性改为 `vicoproplus/moon_cpca`，import 路径同步 |
| T4 | 上游与数据为 MIT；必须保留 LICENSE 与归属 | `chinese_province_city_area_mapper/LICENSE:1`；`README.md:7-12` | vendored 快照必须含 `LICENSE`；README/CHANGELOG 保留出处 |
| T5 | GitHub ubuntu runner 的 wasm-gc 执行能力未验证 | PRD §10.5；本机 `moon test --target wasm-gc --no-render` 报 `0xc0000139` | D-08 设定发布阻断；不把 unresolved 当通过 |
| T6 | `moon package` 会收 docs/tools/testdata/probe/申报书；当前 33 文件 / 242,866 B；全量 vendored 后 57 文件 / 678,048 B | `.superpowers/gap-audit/evidence-packaging.md:570` | D-06 接受包内容，内容裁剪记为开放问题 |
| T7 | golden 生成依赖 pandas 与 pyahocorasick；本机可导入，仓库未声明 | `python -c "import pandas, ahocorasick"` 退出 0 | D-10 新增 `requirements-dev.txt` 与 README 安装命令 |
| T8 | `moon.mod` 的 `preferred_target = "native"` | `moon.mod:5` | 只是默认目标；CI 显式指定 native/wasm-gc/js，不冲突 |

### 3.2 平台接缝（PS1-PS3）

| 编号 | 结论 | 理由 |
|------|------|------|
| PS1 | N/A — no platform-forked capabilities | 库代码没有按平台分叉的能力；目标差异只体现在编译器/运行器是否可执行，不是业务条件分支 |
| PS2 | N/A — no inline platform branches | 无业务侧平台条件分支；不新建接缝层 |
| PS3 | N/A — no existing seam comparison | 仓库无平台接缝层可对照 |

### 3.3 测试环境分支（TB1-TB3）

| 编号 | 结论 | 理由 |
|------|------|------|
| TB1 | N/A — no platform branches | 不存在条件编译/运行时平台判断分支；native/wasm-gc/js 由 `moon` 目标参数选择，不进入代码 |
| TB2 | N/A — no unreachable branch | 同上 |
| TB3 | N/A — no guard refactor | 同上 |

### 3.4 渲染接缝（RS1-RS4）

| 编号 | 结论 | 理由 |
|------|------|------|
| RS1 | N/A — no cross-engine shared UI files | 无 UI/页面/布局代码 |
| RS2 | N/A — no layout-sensitive attributes | 同上 |
| RS3 | N/A — no first edge/bottom-docked element | 同上 |
| RS4 | N/A — no render-surface assertions | 本单元无渲染断言 |

### 3.5 运行时原语与传输（E5-E8）

| 编号 | 结论 | 理由 |
|------|------|------|
| E5 | N/A — no platform runtime primitives | 引擎只使用 MoonBit 字符串/数组/Map 与编译期常量；无文件、网络、环境变量、系统 API |
| E6 | N/A — no primitive × target matrix | 同上；目标差异是工具链执行能力，不是原语可用性 |
| E7 | N/A — no no-evidence primitive dependency | 同上 |
| E8 | N/A — no cross-runtime transfer mechanism | 无跨运行时传输、流式、分帧、长连接 |

### 3.6 成本与合规

- **成本**：新增 4 个 job 会增加 CI 分钟数；wasm-gc 运行器安装可能增加 job 时间；包体增加 minimal snapshot 的原始字节约 178 KB（`wc -c` 合计 181,807 B），最终以 `moon package` 归档为准。
- **合规**：MIT 许可与上游归属不可移除；发布凭证不进入仓库/包；运行时无敏感数据流（PRD §10.7 已写「无」）。

---

## 四、非目标

引用 PRD §三。设计不改变以下边界：

- 算法行为（匹配顺序、消歧、addr 截断）不变。
- 多地址 `transform_text_with_addrs` 不做，留未来 PRD。
- 街道/门牌号、经纬度/逆地理、在线数据更新不做。
- 发布包内容瘦身不作为本单元交付项；只记录开放问题。
- 超出 PRD 已列缺口的 P2 quirk 回归不做。
- 原样运行上游 Python 测试套件不作为交付条件；只对齐输入与期望值。
- 引擎内部结构不重构。

---

## 五、验收场景

引用 PRD §四 US-01～US-05；下表只给设计承载与可达性，不重复验收条目。

| US | 设计承载 | 可观察路径 | 可达性结论 |
|----|----------|------------|------------|
| US-01 干净 clone 复现 | D-02 快照 + D-03 wrapper 权威 + D-04 quality-gates + D-10 dev 依赖 | 全新 clone → 安装 dev 依赖 → `python tools/regen.py` → `git diff --exit-code` → `check_artifact.py` / `check_golden.py` | 可达：wrapper + checker 更新；U-06 记录当前 checker 拒绝格式化产物 |
| US-02 发布 0.1.0 | D-01 原子改名 + D-06 包内容 + D-11 文档 | dry-run 输出 202 + 成功标记 → 真实发布 200 → `moon view ... --versions` → tag/CI 记录 | 可达；注册表 403 为外部假设 |
| US-03 跨目标消费 | D-01 包路径 + D-04 CI jobs + D-08 wasm-gc + D-09 js | 消费方 `moon add` → native build/run → wasm-gc build + 用例计数 → js 状态 | wasm-gc 执行依赖 runner；失败即阻断 |
| US-04 上游逐条对齐 | D-05 覆盖映射 + 机器检查 | `python tools/check_coverage.py` 0；`check_golden.py cases=N`；差异 0 | 可达；映射表是权威派生文档 |
| US-05 文档/示例/诊断 | D-11 example/README/CHANGELOG + D-12 命令 | `moon run --target native example`；README 五段；报告四项 | 可达 |

---

## 六、未知项 / 待验证假设

延续 PRD §10.5，并补充设计层未验证项。所有项在首个依赖步骤前设决策 checkpoint；未过 checkpoint 不得写成已验证。

| 编号 | 声明 | 类型 | 当前证据 | 依赖 | 处置 |
|------|------|------|----------|------|------|
| U-01 | mooncakes 账号 `vicoproplus` 对模块名 `vicoproplus/moon_cpca` 具有首发权限 | 依赖假设 | `moon whoami` 仅证明登录身份；注册表授权未验证 | FR-06、FR-07、FR-20 | 真实首发 200 即证实；403 保留服务端原文并暂停，不换名重试 |
| U-02 | GitHub Actions ubuntu runner 可执行 wasm-gc 测试二进制 | 依赖假设 | 本机 `moon test --target wasm-gc --no-render` 报 `0xc0000139`；runner 未跑过 | G-03、FR-08 | 首次 CI 运行检查用例计数；失败即发布阻断，需补 loader/runner 后重跑；不登记 unresolved |
| U-03 | `Int`/`Int32` 在当前工具链中是同宽兼容别名，格式化不改变公开调用语义 | 设计待验证 | `moon fmt` 证据显示 `Int` → `Int32`；尚无 `.mbti` 与消费方样本 | FR-10、D-07 | `moon info` 检查 `.mbti`；消费方示例 `moon check`；不通过则按 D-07 fallback |
| U-04 | wasm-gc 执行的具体载体（runner 自带加载器 / 安装 wasmtime / 容器） | 设计待验证 | 本机加载器失败；未在 CI 验证 | D-08、FR-08 | 首次 CI 运行回填；机制失败不得降级为目标可用 |
| U-05 | 发布包内容与体积在 mooncakes 接受范围内 | 设计待验证 | 当前 probe 33 文件 / 242,866 B；全量 vendored 678,048 B；minimal 预计约 424 KB 原始字节 | D-06、FR-06 | 发布前 `moon package` 实测；超限则复开包内容决策 |
| U-06 | 生成器格式化路径与检查器兼容性：`moon fmt` 按包作用；当前 `check_artifact.py` 拒绝格式化后的尾逗号；golden 检查器接受格式化 golden；raw `gen_adcodes.py` 自检通过 | 已核验（A 级临时 clone 实跑） | 探针：`moon fmt data/adcodes.mbt` 修改 data 包三文件；clean clone 全项目 `moon fmt` 为 11 个内容差异文件 / 14 个 status 项（3 项仅 EOL）；`check_artifact.py` exit 2，首行 `'  { adcode: "500233000000", name: "忠县", level: Area, },'`；`tools/check_artifact.py:60-64` 的 `ENTRY_RE` 期望 `level: Area },`；`check_golden.py` 对格式化 golden exit 0；raw `gen_adcodes.py` self-check 6/6、network 0 | FR-02、FR-03、D-03、C-01 | 已裁决：FR-02 把 checker 更新列为交付项；wrapper 负责 fmt 与检查顺序；不得改 checker 绕过而不纳入 FR-02 |

> 决策 checkpoint：U-01 在真实发布前；U-02/U-04 在 CI 首次完整运行前；U-03 在 `moon fmt` 落地前；U-05 在发布前；U-06 已核验，C-01 已裁决（wrapper + checker 更新）。未过 checkpoint 的项不得写成「已通过」。

---

## 七、设计决策

每行含：决策（which/why）、否决替代、PRD 回链、代价、复开条件、验收可达性检查。

| ID | 决策（which / why） | 否决替代 | PRD 回链 | 代价 | 复开条件 | 验收可达性检查 |
|----|---------------------|----------|----------|------|----------|----------------|
| D-01 | **原子改名**：`moon.mod` 改为 `vicoproplus/moon_cpca`；`engine/moon.pkg`、`testdata/moon.pkg`、README、检查脚本与包路径一次性同步；不留别名 | 兼容 shim；双模块过渡；登录 `vicoplus` 保留旧名 | FR-05、FR-07、FR-15；PRD D1 | 所有内部 import 与文档一次改完；旧名命中数必须为 0 | 出现真实外部消费方依赖旧名 | `moon check` 0；dry-run 输出 `202 Accepted` + `Dry run completed successfully`（exit 255 不单独判失败）；旧 import 字面量命中 0；消费方 `moon add` 0 |
| D-02 | **最小 vendored 快照（逐字 8 路径）**：`cpca/__init__.py`、`cpca/matcher.py`、`cpca/structures.py`、`cpca/exceptions.py`、`cpca/resources/__init__.py`、`cpca/resources/adcodes.csv`、`LICENSE`、`tests/test_cpca.py`；`resources/__init__.py` 供 `pkg_resources.resource_stream('cpca.resources', ...)` 导入；`drawer.py` 不入快照；gitignore `__pycache__/`、`.pytest_cache/` | 全量上游（含 1 MB addr.csv/docs）；构建时联网拉取；只提交 CSV；含 `drawer.py` | FR-01、FR-02、FR-03；PRD D2 | 8 个文件；原始字节合计 181,807 B；包体增加约 178 KB | 上游 oracle 需要更多文件才能重生成 | 干净 clone 8 路径逐字存在；`git ls-files` 行数 = 8；缓存/drawer 命中 0；`import cpca` 成功 |
| D-03 | **wrapper 权威再生入口**：`python tools/regen.py` 固定顺序为 `gen_adcodes.py`（raw，自检 6/6）→ `moon fmt data/` → `check_artifact.py`（更新解析器，接受格式化尾逗号）→ `gen_golden.py`（raw）→ `moon fmt testdata/` → `check_golden.py` → `git diff --exit-code`。wrapper 是唯一验收权威；raw 生成器是下层入口，不承担逐字节契约。选择 Python 而非 shell/Make：仓库已依赖 Python，Windows 与 CI 均可执行 | 生成器手写 fmt-stable 文本；只跑两个裸命令不 fmt；不做 fmt 门禁；在 checker 侧放宽解析但不纳入 FR-02 | FR-02、FR-03、FR-04、FR-09、FR-10；PRD D5；C-01、U-06 | 新增一个 stdlib Python 脚本；`check_artifact.py` 解析器更新为 FR-02 交付项 | checker 解析器无法安全接受格式化形态，或 wrapper 顺序无法稳定复现 | `python tools/regen.py` 0；`git diff --exit-code` 0；`check_artifact.py` 0；`check_golden.py` 0；`moon fmt --check` 0 |
| D-04 | **CI 四 job**：`native`、`wasm-gc` 为 required；`quality-gates` 为 required；`js` 为 non-blocking。每个 job 名称即状态标识 | 单 matrix + `continue-on-error`；一个 job 跑全部目标 | FR-08、FR-09、FR-19；PRD D3 | runner 分钟数增加；job 间无共享缓存时重复下载工具链 | 目标集合变化或 runner 成本受限 | GitHub run 页逐 job 可检索；native/wasm-gc/quality 红即整体红；js 状态可见 |
| D-05 | **覆盖映射独立权威文档 + 机器检查**：`docs/moon_cpca-upstream-coverage.md`，标题含版本，14 行；`tools/check_coverage.py` 校验每个 `moonbit_case_id` 在 golden 或 wbtest 中存在 | 写进 PRD/spec；自由表格；只靠人工核对 | FR-11、FR-12、FR-13、FR-14；AD1-AD3 | 一份文档 + 一个 stdlib 检查脚本 + CI 步骤 | 上游输入集合变化或新增用例载体 | `python tools/check_coverage.py --doc ...` 0；映射 14 行；golden 覆盖 10 字符串 + 2 umap；`check_golden` cases=N |
| D-06 | **v0.1.0 接受当前包内容**：当前 33 文件 / 242,866 B；新增 example/requirements-dev/coverage/CHANGELOG 与最小 vendored 快照后预计约 424 KB 原始字节；全量 vendored 的 57 文件 / 678,048 B 不作为本单元目标；裁剪留开放问题 | 立即重构包结构；用未验证的排除机制；拆多个发布包 | FR-06；PRD §三非目标、§七开放问题 | 包体增大；minimal snapshot 原始约 178 KB | mooncakes 体积限制或用户要求裁剪 | `moon package --list` 可见预期文件；归档可安装；体积记录在 CHANGELOG |
| D-07 | **Int/Int32 策略**：采纳 `moon fmt`；用 `moon info` 检查 `.mbti`，用消费方 sample `moon check` 验证调用形式；README/CHANGELOG 记录拼写变化；位宽/别名等价在 spec 验证。**Fallback**：若 U-03 显示签名/别名不等价，保留 `Int` 拼写并评估对生成物排除 fmt；`moon fmt` 无可验证的 per-file ignore，排除会与 FR-10 冲突，因此必须复开 FR-10 交 PRD 裁决，不得静默排除 | 拒绝格式化；手改生成物保留 `Int`；把 `Int32` 直接当无变化；静默排除生成物 | FR-10；PRD D5 | 公开签名可能显示 `Int32`；需消费方回归；fallback 可能阻塞格式化收口 | `.mbti` 显示不兼容或消费方编译失败 | `moon info` 产物；consumer `moon check` 0；README/CHANGELOG 有记录；U-03 失败则设计冻结 |
| D-08 | **wasm-gc 执行强制**：CI 的 wasm-gc job 必须产生用例计数；runner 缺 loader 时安装 wasm runtime 或用容器，失败即阻断发布 | 只构建不执行；标记 unresolved；跳过该 job | G-03、FR-08；PRD D3 | runner 安装时间；机制未在本机验证 | runner 无法提供任何可用 loader | CI 日志有 `Total tests` 或等价计数；失败时整体红；无 unresolved |
| D-09 | **js 非阻断**：CI 安装真实 Node；没有可用运行器时 job 记录 `unresolved + 具名原因`，README 同步；只有 js 允许 unresolved | 把 js 设为 required；静默跳过；写 green 无运行记录 | FR-19；PRD D3 | 一个 non-blocking job；状态维护成本 | Node 在 runner 可用 | js job 状态可见；README 行非空二选一 |
| D-10 | **Python dev 依赖声明**：仓库根 `requirements-dev.txt` 声明兼容 Python 3.12 的 `pandas==2.3.1`、`pyahocorasick==2.3.1`、`setuptools`（`pkg_resources` 兼容；`cpca/__init__.py:68` 需要）；README 给安装命令；不复用上游 2020 年 pin | 直接复用上游 `requirements.txt`；不声明依赖；漏 setuptools | FR-03；PRD 10.5 | 一个新文件；安装时间 | 当前 Python 版本与依赖不兼容 | `python -c "import pandas, ahocorasick, pkg_resources"` 0；`gen_golden.py` 0 |
| D-11 | **README/example/CHANGELOG**：`example/` 为 main 包（T-10 执行期修正：`pkgtype(kind: "executable")`，不是 `options("is-main": true)` —— 后者被 moon `0.1.20261012` formatter 改写），只 import 改名后的 engine；README 五段；CHANGELOG 0.1.0；example 入包，体积按 D-06 | 只留 README 代码块；把 example 放进 testdata；不写 CHANGELOG | FR-15、FR-16、FR-18 | example 入包；文档维护成本 | 发布包体积或入口形态变化 | `moon run --target native example` 0；stdout 与 README 逐行一致；五段可检索 |
| D-12 | **E16 命令修正**：README 改为 `2>`（仅 stderr；不得用 `2>&1`），不改测试代码；成功时报告文件为空 | 让测试直接写文件；只改文案不验证；用 `2>&1` 捕获 stdout | FR-17 | 一行命令 | 测试输出通道变化 | 构造不一致后报告文件存在且四项可检索；成功时文件为空 |

---

## 八、门禁记录

### 8.1 平台接缝 / 测试分支 / 渲染接缝

- **PS1-PS3：N/A** — 无平台分叉能力、无内联平台条件分支、无既有接缝层。目标差异（native/wasm-gc/js）是工具链执行环境差异，由 CI job 参数体现，不进入库代码。
- **TB1-TB3：N/A** — 无平台分支；不存在测试环境不可达的分支。
- **RS1-RS4：N/A** — 无 UI、无共享页面文件、无渲染断言。

### 8.2 传输形态（E8）

**N/A — no cross-runtime transfer mechanism.** 本单元无跨运行时数据流、无流式/长连接/分帧。

### 8.3 外部契约 SoT

**N/A — no external bridge.** 无外部系统桥接、无第三方 API 契约；mooncakes 注册表只通过 CLI 命令观察。

### 8.4 降级等价（FE1-FE3）

**N/A — no runtime fallback.** 产品运行路径没有主/降级分支；CI 的 js unresolved 是发布状态，不是产品降级行为，不能用它替代 js 运行结果。

### 8.5 跨契约交叉影响（ND1-ND3 / WB1-WB3）

#### 8.5.1 既有谓词全集（机检枚举）

| 谓词 | 命令 | 扫描域 |
|------|------|--------|
| 依赖白名单 | `python tools/check_deps.py` | `moon.mod` + `engine/moon.pkg` |
| 数据产物 | `python tools/check_artifact.py --records --fields --levels --order --dup` | `data/adcodes.mbt` + vendored CSV |
| golden 双产物 | `python tools/check_golden.py` | `testdata/golden.jsonl` + `testdata/golden.mbt` |
| 格式 | `moon fmt --check` | 仓库内 MoonBit 源文件、`moon.mod`、`moon.pkg` |
| 包内容 | `moon package --list` | 模块内非点目录文件 |
| 用例包 | `moon test --target native --no-render` | 含 test 块的包 |

#### 8.5.2 新实体干跑

| 新实体 | check_deps | check_artifact | check_golden | moon fmt | moon package | moon test | 裁决 |
|--------|------------|----------------|--------------|----------|--------------|-----------|------|
| `example/` + `example/moon.pkg` | 不命中（不在扫描域） | 不命中 | 不命中 | **命中**（必须 fmt-clean） | **命中**（入包） | 不命中（无 test 块） | 只 import `<module>/engine`；fmt 覆盖；包体按 D-06 接受；不扩展 check_deps 扫描域 |
| `requirements-dev.txt` | 不命中（非 moon manifest） | 不命中 | 不命中 | 不命中 | **命中**（入包） | 不命中 | 仅 host 工具依赖；README 说明；包体接受 |
| `docs/moon_cpca-upstream-coverage.md` | 不命中 | 不命中 | 不命中 | 不命中 | **命中**（docs 入包） | 不命中 | 作为 AD1 权威文档；由 check_coverage 读取 |
| `tools/check_coverage.py` | 不命中 | 不命中 | 不命中 | 不命中 | **命中**（tools 入包） | 不命中 | stdlib only；CI quality-gates 调用 |
| CI job 定义 | 不命中 | 不命中 | 不命中 | 不命中 | 不命中（`.github` 点目录排除） | 不命中 | 仅 `.github/workflows/ci.yml` 承载 |
| `CHANGELOG.md` | 不命中 | 不命中 | 不命中 | 不命中 | **命中**（根文件入包） | 不命中 | 0.1.0 段与 README 矩阵一致 |

**命中裁决**：

- `example/` 的 fmt 命中：纳入 `moon fmt --check`，不接受豁免；example 代码必须和库代码同标准。
- `example/` 的 package 命中：D-06 接受；example 是交付物的一部分（README 示例可运行）。
- `docs/`、`tools/`、`requirements-dev.txt`、`CHANGELOG.md` 的 package 命中：D-06 接受；裁剪是开放问题，不在本单元改变。
- `example/moon.pkg` 不在 check_deps 扫描域：这是刻意的范围裁决；example 不是发布运行时依赖面，其依赖由 `moon check` 编译证明。若未来扩展 check_deps 到全部包，必须同时把 `<module>/engine` 加入内部包白名单并重跑干跑。

#### 8.5.3 承载面表（WB1-WB3）

| 接线需求 | 承载面 | 否决候选 | 验收观察路径 |
|----------|--------|----------|--------------|
| 模块改名 | `moon.mod` + 各 `moon.pkg` + README/脚本 | 只改 `moon.mod`（会断 import） | `moon check`、`moon publish --dry-run`、旧字面量检索 0 |
| 再生入口 | `tools/regen.py` 调用既有生成器 | 裸命令作为权威；Makefile（Windows 无 make） | wrapper 退出 0 + `git diff` 0 |
| 跨目标状态 | `.github/workflows/ci.yml` 的 job 结构 | 单 job matrix；`continue-on-error` 混用 | run 页逐 job 状态 |
| 覆盖映射 | `docs/moon_cpca-upstream-coverage.md` + `tools/check_coverage.py` | 写进 PRD/spec；人工表格 | check_coverage 0 + 映射 14 行 |
| 示例 | `example/` + `example/moon.pkg` | README 片段；testdata 里的示例 | `moon run --target native example` |
| 诊断命令 | `README.md` 命令 | 改测试代码写文件 | 报告文件四项 |

**下游允许触碰清单（从承载表推导）**：`moon.mod`、`engine/moon.pkg`、`testdata/moon.pkg`、`README.md`、`CHANGELOG.md`、`.gitattributes`、`.github/workflows/ci.yml`、`tools/regen.py`、`tools/check_coverage.py`、`docs/moon_cpca-upstream-coverage.md`、`example/**`、`requirements-dev.txt`、`data/adcodes.mbt`（生成）与 `testdata/golden.jsonl`/`testdata/golden.mbt`（生成）。`engine/*.mbt` 只允许格式化带来的改动，不允许语义改动。

### 8.6 权威派生文档（AD1-AD3）

- **AD1 独立权威文档**：`docs/moon_cpca-upstream-coverage.md`，标题 `moon_cpca 上游用例覆盖映射 v1`，含版本、适用范围、14 行逐条正文。
- **AD2 可机检断言**：`python tools/check_coverage.py --doc docs/moon_cpca-upstream-coverage.md`；断言行数 = 14、状态枚举仅「精确」「类型层 N/A」、每个 `moonbit_case_id` 在 golden 或 wbtest 中命中；失败 exit 1；接入 CI `quality-gates` job。
- **AD3 指针链**：spec 逐字引用上述完整标题；plan 携带同一路径；code review 按 AD2 命令核验；下游只引用标题，不复制表格正文。

### 8.7 跨单元时序（CT1）

**N/A — single PRD, no sibling units.** PRD §10.6 已裁定单份 PRD；无兄弟单元共享接口或时序依赖。

### 8.8 双形态契约（DC-E）

**裁决：`tools/regen.py` 为唯一验收权威；裸 `gen_adcodes.py` / `gen_golden.py` 是下层入口，不承担逐字节契约。** 同步方式：wrapper 按 D-03 顺序执行 raw 生成 → `moon fmt` 包级格式化 → 更新后的 `check_artifact.py` / `check_golden.py` → `git diff --exit-code`。`check_artifact.py` 的解析器更新是 FR-02 的交付项，不是绕过。U-06 记录当前解析器拒绝格式化尾逗号，因此该更新是必需项。

### 8.9 契约两两互查（MS1-MS2）

约束清单：C1 `moon fmt --check` 覆盖提交文件；C2 裸生成命令逐字节一致；C3 vendored 快照入库；C4 包体可控；C5 模块名唯一；C6 wasm-gc 执行强制；C7 运行时零第三方依赖；C8 `preferred_target=native`；C9 example 入包；C10 Python dev 依赖；C11 覆盖映射 14 行。

| 对 | 同时满足会不会撞 | 裁决 |
|----|------------------|------|
| C1 × C2 | **曾会，已裁决**：裸生成器写旧格式，fmt 后字节不同；自格式化又被当前 `check_artifact.py` 拒绝 | C-01 已裁决：wrapper 为权威；`check_artifact.py` 解析器更新为 FR-02 交付项；raw 生成器降为下层，不承担逐字节契约；U-06 记录探针证据 |
| C3 × C4 | **有张力**：快照入库增大包体 | D-02 最小快照 + D-06 接受约 178 KB 原始增量；裁剪留开放问题 |
| C5 × 旧 import/文档 | **会**：只改清单会断 import | D-01 原子改名；旧字面量命中 0；`moon check` 与 dry-run 双证 |
| C6 × runner 风险 | **会**：runner 无 loader 时无法执行 | D-08 设为发布阻断；补 loader/runner 后重跑；不登记 unresolved |
| C7 × C10 | 不会：dev 依赖不进 `moon.mod`/`engine/moon.pkg` | D-10；check_deps 扫描域不变；example 不在扫描域 |
| C8 × 跨目标 | 不会：`preferred_target` 只是默认值 | D-04 显式 `--target`；native/wasm-gc/js 分别验证 |
| C1 × C9 | 不会：example 纳入 fmt | example 必须 fmt-clean；D-11 |
| C2 × C11 | 不会：覆盖文档不参与 golden 生成 | check_coverage 独立读取；静态 14 行 |
| C5 × C4 | 不会：改名不改包体结构 | D-01 + D-06 |

### 8.10 文档契约纪律（DC-A ~ DC-E）

| 编号 | 结论 |
|------|------|
| DC-A | 本文引用使用 FR/US/G 编号与稳定路径；`file:line` 仅作为证据指针，不作为契约锚 |
| DC-B | 状态只在文首状态行陈述；无被覆盖的旧结论并存 |
| DC-C | 本文没有「已完成/已验证」类完成断言；事实均附命令或证据路径 |
| DC-D | 计数（20 FR、14 行、8 文件、33 文件等）来自 PRD 或机检命令/证据；不另造手写计数 |
| DC-E | 双形态（wrapper vs 裸命令）已裁决：`tools/regen.py` 权威，裸命令下层；`check_artifact.py` 更新为 FR-02 交付项，见 §8.8/U-06 |

### 8.11 设计决策追溯（FR × 决策 × 验收可达性）

| FR | 优先级 | 决策 | 技术路径 | 交付结构 |
|----|--------|------|----------|----------|
| FR-01 | P0 | D-02 | 快照入库 + gitignore 缓存 | 8 文件最小集；`git ls-files` ≥ 8 |
| FR-02 | P0 | D-02、D-03 | wrapper 顺序：raw gen → fmt data → checker → diff | `python tools/regen.py`；checker 更新；clean clone |
| FR-03 | P0 | D-03、D-05 | wrapper 顺序：raw gen_golden → fmt testdata → check_golden | `python tools/regen.py`；`cases=N` 动态 |
| FR-04 | P1 | D-03 | `.gitattributes` LF + wrapper 固定 fmt 步骤 | 三文件字面 diff 0 |
| FR-05 | P0 | D-01 | manifest + import + docs 原子改 | 旧名命中 0；dry-run 202 + 成功标记 |
| FR-06 | P0 | D-01、D-06 | 发布 + 注册表检视 | `moon view --versions` 含 0.1.0 |
| FR-07 | P0 | D-01、D-06 | 消费方安装 + native 调用 | 全新消费方 build 0 |
| FR-08 | P0 | D-04、D-08 | native/wasm-gc required job | CI run 页逐 job 计数 |
| FR-09 | P0 | D-04、D-05 | 七个质量门禁步骤 | quality-gates job |
| FR-10 | P0 | D-03、D-07 | wrapper 唯一格式化生成物；无 per-file ignore | `.mbti` + consumer check |
| FR-11 | P0 | D-05 | 11 条输入映射 | 覆盖文档 + wbtest/golden |
| FR-12 | P0 | D-05 | 2 条 umap 映射 | 覆盖文档 + wbtest/golden |
| FR-13 | P1 | D-05 | pos_sensitive=false 契约 | 覆盖文档 + wbtest |
| FR-14 | P1 | D-05 | 14 行映射 + 机器检查 | check_coverage 0 |
| FR-15 | P1 | D-01、D-11 | README 五段 + 新模块名 | README 可检索 |
| FR-16 | P1 | D-11 | example 包 | `moon run` 输出一致 |
| FR-17 | P1 | D-12 | README 诊断命令 | 报告四项 |
| FR-18 | P2 | D-11 | CHANGELOG 0.1.0 | 与 README 矩阵一致 |
| FR-19 | P1 | D-09 | js non-blocking job | js 行二选一 |
| FR-20 | P0 | D-01、D-04 | push/tag + CI 记录 | `rev-list` 0 + tag + run |

**时序可达性**：下表把 FR 组映射到可观察时点，避免「实现完成但验收时点不可达」。

| 时点 | FR | 可观察前提 |
|------|----|------------|
| CI 首次完整运行 | FR-08、FR-09、FR-19 | workflow 已推送；runner 可用 |
| v0.1.0 发布前 | FR-01～FR-04、FR-10 | 干净 clone + dev 依赖 + wrapper |
| v0.1.0 发布时 | FR-05～FR-07、FR-20 | 清单改名完成；注册表可用；tag/push 完成 |
| 交付验收时 | FR-11～FR-18 | golden 扩展 + 覆盖文档 + example |

---

## 九、矛盾裁决与遗留

### C-01 裸生成命令逐字节一致 × fmt 门禁（已裁决）

- **冲突**：旧 PRD FR-02/FR-03 要求裸 `gen_adcodes.py` / `gen_golden.py` 的输出与提交态逐字节一致；FR-10 要求 `moon fmt --check` 0；现有生成器输出被 fmt 改写（`data/adcodes.mbt` +3668/−3511，`Int` → `Int32`）。
- **U-06 探针结论**：生成器自格式化不可行。临时 clone 中 `moon fmt` 可接受 PATH，但按包作用；格式化后的 `data/adcodes.mbt` 被 `check_artifact.py` 以尾逗号拒绝，exit 2，首个失败行 `'  { adcode: "500233000000", name: "忠县", level: Area, },'`；`tools/check_artifact.py:60-64` 的 `ENTRY_RE` 末段为 `level: (?P<level>Province|City|Area) \},$`，不接受 `level: Area, },`。`check_golden.py` 对格式化 golden 通过（exit 0），故失败点是数据产物检查器，不是 golden 检查器。
- **裁决**：P5 已修订 FR-02/FR-03：`tools/regen.py` 为唯一权威再生入口，裸生成器降为下层入口，不承担逐字节契约；`check_artifact.py` 解析器更新为 FR-02 的交付项（接受格式化尾逗号），不是绕过。wrapper 固定顺序：raw gen → `moon fmt` 包级格式化 → 更新后的 checker → `git diff --exit-code`。
- **U-06 证据**：见下表；`gen_adcodes.py` raw 自检 6/6，`check_golden.py` 对格式化 golden 0；当前数据检查器 exit 2 作为更新依据。
- **未否决 PRD**：本设计按修订后的 FR-02/FR-03 执行，不静默改写；旧「裸生成器逐字节」契约由 PRD §10.6 显式取代。

### U-06 探针证据

探针均在临时 clone 执行，真实仓库未改动。

| 探针 | 命令 | 退出码 | 观测 |
|------|------|--------|------|
| 格式化帮助 | `moon fmt --help` | 0 | 接受 `[PATH]...`；说明为「Paths to packages, files selecting their containing package」；不能只选一个生成文件而不触及其所在包 |
| 按文件格式化 | `moon fmt data/adcodes.mbt` | 0 | 修改 `data/adcodes.mbt`、`data/adcodes_test.mbt`、`data/moon.pkg`；未触及 engine/testdata 包 |
| 全项目格式化 | clean clone 内 `moon fmt`；`git diff --numstat` 与 `git status --short` | 0 | 11 个内容差异文件；`git status --short` 14 项（3 项仅 EOL/stat）；覆盖 data/engine/testdata/moon.mod/moon.pkg |
| 格式化后数据检查 | `python tools/check_artifact.py --records --fields --levels --order --dup` | 2 | 首个失败：第 21 行 `'  { adcode: "500233000000", name: "忠县", level: Area, },'` 不是合法记录行；`ENTRY_RE` 期望 `level: Area },` 无尾逗号 |
| 生成器原始自检 | `python tools/gen_adcodes.py --out adcodes_formatted_probe.mbt --no-network-check` | 0 | records 3511；self-check 6/6；network events 0 |
| 格式化探针产物 | `moon fmt adcodes_formatted_probe.mbt` | 0 | 与格式化后的 `data/adcodes.mbt` diff 为 0；但 `check_artifact.py` 仍拒绝该形态（exit 2） |
| golden 再生 + 格式化 | `python tools/gen_golden.py`；`moon fmt testdata/golden.mbt`；`python tools/check_golden.py` | 0 / 0 / 0 | 32 cases；golden 双产物一致；golden 检查器接受格式化形态 |

### C-02 vendored 快照 × 包体（已裁决）

- **冲突**：D-02 快照入库会增大发布包。
- **裁决**：最小快照（8 文件，181,807 B 原始字节）；D-06 接受 v0.1.0 包内容；裁剪留 PRD §七开放问题。

### 遗留外部假设

- U-01 mooncakes 403：未验证，真实发布前 checkpoint。
- U-02/U-04 wasm-gc runner 与执行载体：未验证，首次 CI 前 checkpoint；失败即发布阻断。
- U-03 Int/Int32 等价：未验证，fmt 落地前 checkpoint。
- U-05 包体上限：未验证，发布前 `moon package` 实测。
- U-06 生成器格式化路径与检查器兼容性：**已核验（A 级）**；当前 `check_artifact.py` 拒绝格式化尾逗号，已作为 FR-02 的 checker 更新交付项；C-01 已裁决，设计就绪 P7。

> C-01 已裁决；其余为外部环境/注册表假设，按 PRD 10.5 与本文 §六跟踪。设计可进入 P7，但 U-01/U-02/U-04 仍须按 checkpoint 验证。

---

## 十、交付面清单（供 spec 承接）

- 必改/新增：`moon.mod`、`engine/moon.pkg`、`testdata/moon.pkg`、`README.md`、`CHANGELOG.md`、`.gitattributes`、`.github/workflows/ci.yml`、`tools/regen.py`、`tools/check_artifact.py`（解析器更新）、`tools/check_coverage.py`、`docs/moon_cpca-upstream-coverage.md`、`example/`、`requirements-dev.txt`。
- 生成物：`data/adcodes.mbt`、`testdata/golden.jsonl`、`testdata/golden.mbt`（由 `tools/regen.py` 权威入口改写，禁止手改）。
- 只允许格式化改动的文件：`engine/*.mbt`、`testdata/golden_test.mbt` 等 `moon fmt` 覆盖的源文件；禁止语义编辑。
- 不入库：`__pycache__/`、`.pytest_cache/`、`_build/`。

---

**文档结束**
