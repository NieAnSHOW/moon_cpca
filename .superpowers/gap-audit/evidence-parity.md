# moon_cpca 申报书交付项 × 上游 cpca v0.5.5 覆盖审计

- 审计对象：`F:/moonbit比赛/moon_cpca`（工作树，只读审计；未改任何受版本控制文件）
- 行为基准：vendored `chinese_province_city_area_mapper`（cpca `0.5.5`，`cpca/__init__.py:9-11`）
- 审计日期：2026-10-17
- 结论摘要：
  1. 核心单条提取 API、简称归一、级联补全、pos（`pos_sensitive=true`）在 **32 条 golden + 39 条 MoonBit 测试**下逐字段对齐；本次另做了按 `engine/*.mbt` 逻辑转写的 Python 差分 harness，7,885 条文本与上游 `transform` **0 不一致**，匹配器层 6,882 条文本 **0 不一致**（见 §0 命令 E10/E11）。
  2. 最大缺口不在算法，而在**工程可复现性**：generator/checker 依赖的 vendored `adcodes.csv` 与上游源码目录**未纳入 git**（`git ls-files` = 0 条），全新 clone 无法执行 README 的“重生成/机检”，README 的“已随本仓库 vendored”“可复现、可更新”不成立。
  3. 上游用例集只做了**子集交叉对照**：`test_transform` 11 条输入中 3 条精确覆盖（徐汇/福建鼓楼/宁夏）、2 条部分覆盖（天津仅 adcode、淮安市市辖区缺 addr）、5 条完全未覆盖（泉州洛江、江苏淮安×2、浦东东明路、贵州黔南）、1 条类型层不适用（int `32323`）；`test_transform_text_with_addrs` 全部属 PRD 声明非目标；`test_matcher` 为等价语义覆盖而非同数据覆盖；`test_structures` 的 `AddrMap/Pca` 无对应实现（上游死代码）。
  4. 未发现可证实的算法偏差；风险集中在未被测试锁定的边界分支（见 §3）。

---

## 0. 审计方法与机器证据

所有命令均在仓库根执行（`cd F:/moonbit比赛/moon_cpca`）；仅 E07 生成到 `_build/`，未触碰源码；E09 只建临时目录并在审计后删除产物。

| 编号 | 命令 | 结果 |
|---|---|---|
| E01 | `python -c "import csv;r=list(csv.DictReader(open('chinese_province_city_area_mapper/cpca/resources/adcodes.csv',encoding='utf8')));print(len(r))"` | `3511` |
| E02 | `python -c "import hashlib;print(hashlib.sha256(open('chinese_province_city_area_mapper/cpca/resources/adcodes.csv','rb').read()).hexdigest())"` | `66948fa1519ba053f22b8c2d05c897c9b19c44cdc3044e464b52f0143ff418fe`，与 `data/adcodes.mbt:3` 一致 |
| E03 | `grep -c '^  { adcode: "' data/adcodes.mbt`；`grep -c 'level: Province' data/adcodes.mbt`；`grep -c 'level: City' data/adcodes.mbt`；`grep -c 'level: Area' data/adcodes.mbt` | 3511；34 / 344 / 3133 |
| E04 | `python tools/check_artifact.py --records --fields --levels --order --dup` | 5 项全 PASS，exit 0（重名：31 个名称 / 360 条） |
| E05 | `python tools/check_artifact.py --dup 朝阳区` | PASS：2 条，`220104000000, 110105000000` |
| E06 | `python tools/check_golden.py` | `OK ... cases=32 ... upstream_version=0.5.5`，exit 0 |
| E07 | `python tools/check_deps.py` | 白名单外 0，PASS；`moon.mod` deps=[]，import 仅 `moon_cpca/data` |
| E08 | `python tools/gen_golden.py --stats` | `total=32`，13 类均 ≥1；`stats_ok=True`（该命令不写产物） |
| E09 | `python tools/gen_adcodes.py --out _build/audit_adcodes.mbt --no-network-check` | `records: 3511 (34/344/3133)`；`self-check: 6/6 passed`；`network-check: passed (0 events)`；exit 0 |
| E10 | `python -c "a=open('_build/audit_adcodes.mbt','rb').read();b=open('data/adcodes.mbt','rb').read();print('identical_bytes',a==b)"`；`git show HEAD:data/adcodes.mbt \| python -c "import sys,hashlib;print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())"` | `identical_bytes True`（221403 B）；HEAD blob sha256 `27829ecbd7285f9783132e3262f153aa237a9aa5f2eb08d4d9c9b43b4028ce5f`，与工作树一致 |
| E11 | 按 `engine/extract.mbt` / `matcher.mbt` 逐行转写 Python harness（`python -W ignore -c ...`，临时脚本未落盘；非执行 MoonBit 二进制），与上游 `transform([t], pos_sensitive=True)` 对 7,885 条文本逐 8 字段比较；matcher 层对 6,882 条文本比较迭代序列 | `texts_compared 7885 mismatches 0`；`texts_compared 6882 mismatches 0` |
| E12 | `python -c "import importlib.util; spec=...; m=...; rows=m.build_rows(); ...; print(jl==cur_jl, mb==cur_mb)"`（导入 `tools/gen_golden.py`，对双产物按 `\r\n→\n` 归一后比较） | `jsonl_equal_normalized True` / `mbt_equal_normalized True`；未执行写盘路径 |
| E13 | `moon test --target native --no-render` | `Total tests: 39, passed: 39, failed: 0` |
| E14 | `cd chinese_province_city_area_mapper && python -m pytest tests/test_cpca.py tests/test_matcher.py tests/test_structures.py -q` | `test_cpca.py` 收集失败：`ModuleNotFoundError: No module named 'mock'`（`tests/test_cpca.py:7`），其余被中断 |
| E15 | 同上，仅 `tests/test_matcher.py tests/test_structures.py` | `8 passed` |
| E16 | `git ls-files chinese_province_city_area_mapper \| wc -l`；`git status --porcelain` | `0`（vendored 目录未入库）；工作树仅 `?? .qoder/`、`?? .superpowers/`、`?? chinese_province_city_area_mapper/` |

补充说明：
- `testdata/golden.jsonl` / `golden.mbt` 工作树为 CRLF，committed blob 为 LF（`core.autocrlf=true`）。E12 因此按 `\r\n→\n` 归一并证明内容一致；这不是内容漂移，但“重生成后 diff 为 0 字节”在 Windows 工作树上不是字面成立。
- E09 覆盖了 `_build/gen_report.json`（gitignored），并已删除 `_build/audit_adcodes.mbt`、`_build/moon.pkg`；受版本控制文件无改动。

---

## 1. 申报书 §三 交付项覆盖表

> 原文定位：`申报书-moon_cpca-中文省市区地址解析.md:29-43`。第 5 条原文同时含“测试套件 / README 示例 / CI / 发布”四项，为精确判定拆为 5a-5d。

| 交付项 | 申报书原文 | MoonBit 侧实现位置 file:line | 覆盖状态 | 证据或缺口 |
|---|---|---|---|---|
| 1. 单条 API | “API：`extract(text) -> Location{province, city, area}`，缺失层级返回 None，行为与 Python 版对齐”（:31） | `engine/extract.mbt:14`（`Location` 8 字段）、`:34`（`pub fn extract`）、`:215`（`extract_one`）、`:103`（`names_by_adcode` 三分支）、`:140`（`build_record`） | **完整** | 32 条 golden 逐条比对 8 字段（`testdata/golden_test.mbt:190`）；本机 `moon test` 39/39；E11 差分 7,885 条 0 不一致。缺失层级语义：省 `0000`→市/区 None、市 `00`→区 None（`engine/extract.mbt:103-112`），由 golden ③④ 与 `location_option_semantics`（`engine/location_fields_wbtest.mbt:226`）锁定。残余：`pos_sensitive=false` 的 pos 表示是设计约定（见 R-02）。 |
| 2. 简称/别名 + 级联推断 | “简称/别名归一（"内蒙古"→"内蒙古自治区"、"北京"→"北京市"）与省略上级的级联推断（只出现"余杭区"也能补全省市）”（:32） | `engine/matcher.mbt:83`（五个自治区特表）、`:98`（停用后缀剥离）、`engine/extract.mbt:103`（adcode 前缀反查省/市） | **完整** | ⑤简称类 golden 12-15（江苏/淮安/内蒙古自治区/宁夏）；`m3_abbrev_shares_list_with_full_name`（`engine/semantics_wbtest.mbt:155`）；②仅区县 golden 4-6 + `l1_xuhui_full_chain_t04`（`engine/probe_test.mbt:41`）。未逐字测试的同类输入：“北京”单简称、申报书举例的“余杭区”（同类路径已被徐汇/天河/城东覆盖）。 |
| 3. pos 参数 | “支持返回匹配词在原文中的位置（对应原版 pos 参数），便于排查误匹配”（:33） | `engine/extract.mbt:41-47`（默认 false）、`:231-240`（按 `cands[0].level` 写槽）、`:120`（尾串按码点）、`engine/matcher.mbt:114-122`（码点计数） | **完整（`pos_sensitive=true`）** | 32 条 golden 全含 pos；`location_pos_fields_int_and_minus_one`（`engine/location_fields_wbtest.mbt:171`）、`location_pos_codepoint_index_non_bmp`（:204）。非 BMP 码点口径由 golden 31 锁定（`徐汇区` pos=4）。缺口：`pos_sensitive=false` 时的 `-1` 约定无 golden/断言（R-02）。 |
| 4. 同源数据表，可复现、可更新 | “内置与 cpca 同源的行政区划数据表（版本与来源在 README 注明），数据由仓库内脚本生成入库，可复现、可更新”（:34） | `data/adcodes.mbt:1-3`（来源头：文件名/记录数/sha256）、`:19`（`pub let adcodes`）；`tools/gen_adcodes.py:1-75`（契约）、`:695-735`（`--csv/--out/--no-network-check`）；`tools/check_artifact.py:1-38`；README.md:7-11 | **部分** | 产物与生成器本身成立：E04/E09/E10 证明 3511、34/344/3133、6/6 自校、零网络、重生成与 HEAD 字节一致；`--csv` 更新入口 + `tools/test_gen_adcodes.py`（7 passed）。**缺口**：`chinese_province_city_area_mapper/`（含 `adcodes.csv`）未入 git（E16），全新 clone 上 `gen_adcodes.py`/`check_artifact.py` 无法运行（缺输入 CSV）；README:7“已随本仓库 vendored”在仓库交付物层面不成立；运行 `gen_golden.py` 另需未声明的 pandas + pyahocorasick。 |
| 5a. 与 Python 用例集交叉对照的测试套件 | “与 Python cpca 用例集交叉对照的测试套件”（:35） | `testdata/golden.jsonl:1-32`、`testdata/golden_test.mbt:190`、`engine/semantics_wbtest.mbt`、`engine/location_fields_wbtest.mbt`、`engine/matcher_wbtest.mbt` | **部分** | golden 32 条（≥30）、13 类、oracle 现生成（E08/E12）；端到端逐 8 字段。缺口：上游 `test_transform` 11 输入仅 3 条精确（golden）+ 2 条部分（MoonBit 端到端）覆盖；`test_umap` 第 2 条只覆盖“无 umap”形态；`test_transform_text_with_addrs` 全部未覆盖（声明非目标）；`test_matcher` 为等价语义而非同数据；`test_structures` 无对应类型。详见 §2。 |
| 5b. README 示例 | “README 示例”（:35） | `README.md:16-60`（引擎示例 + umap 示例） | **部分** | 示例输出与 golden 完全对应：徐汇示例 = golden:4（省/市/区/addr/adcode/pos 全同），umap 示例 = golden:26。但仓库无可执行 `example` 包，示例未被编译运行（`git ls-files` 无 example 入口），只能算“文本示例 + golden 反证”。 |
| 5c. CI（构建+测试） | “CI（构建+测试）”（:35） | `.github/workflows/ci.yml:1-27`（`moon build --target native` + `moon test --target native`） | **完整** | 工作流存在且命令与本地等价；E13 本地 39/39。未观察到 GitHub 实际运行记录（审计环境不触发 CI），故“CI 绿灯”本身未验证。 |
| 5d. 发布至 mooncakes.io | “发布至 mooncakes.io”（:35） | `moon.mod:1-5`（name/version/license） | **缺失（无证据）** | 无 publish 工作流、无 tag（`git tag -l` 空）、无发布记录；mooncakes 探测对 `moon_cpca` 返回 404，但同一探测对 `moonbitlang/core` 也 404，接口不可判定，故只能判“未验证/无证据”。 |
| N1. 明确不做：街道/门牌号 | “街道/门牌号级解析（cpca 亦不做…）”（:37-38） | `engine/extract.mbt:14-23`（Location 无 street 字段） | **完整（按边界未做）** | 输出仅三级 + addr 尾串；无街道级数据/算法。 |
| N2. 明确不做：经纬度/逆地理 | “经纬度与逆地理编码”（:39） | `data/adcodes.mbt:12-17`（`Rec` 仅 adcode/name/level）；`tools/gen_adcodes.py` 的 `no_lonlat` 自校 | **完整（按边界未做）** | E04 `--levels` 与 E09 `no_lonlat=ok`；产物无 lon/lat 字段。 |
| N3. 明确不做：在线更新服务 | “区划数据在线更新服务”（:40） | `data/adcodes.mbt:19`（编译期常量）；无网络/服务代码（`engine/` 零 IO，E07） | **完整（按边界未做）** | 数据随包版本化；`gen_adcodes.py` 为离线脚本。 |

---

## 2. 上游用例逐条覆盖表

上游测试规模：`test_cpca.py` 110 行 / `test_matcher.py` 44 / `test_structures.py` 71（`wc -l`）。注意：`test_cpca.py` 因 `from mock import MagicMock`（`:7`）在本环境无法收集（E14）；这不影响 golden oracle（generator 直接 import cpca，不跑 pytest），但“原样跑上游用例集”不可执行。

### 2.1 `tests/test_cpca.py`

| 上游位置 | 输入 / 断言 | 上游期望（省/市/区/addr/adcode；pos 省,市,区） | MoonBit 侧覆盖 | 定性 |
|---|---|---|---|---|
| `:9-11` `test_init_data` | `matcher._get("上海")[0] == '上海'` | 简称键返回原文 | 无同名断言；机制由 `build_matcher`（`engine/matcher.mbt:52-81`）与 `m3_abbrev...`（`engine/semantics_wbtest.mbt:155`，用江苏）间接覆盖 | 未覆盖（静默；等价机制） |
| `:11` | `matcher._get("上海")[1][0] is ad_2_addr_dict["310000000000"]` | 候选与 ad_map 为同一对象 | MoonBit 的 `adcode_dict`（`engine/extract.mbt:53-61`）与 matcher 候选是两份不可变 `Cand`；对象身份不可观察 | 未覆盖（静默；不可观察） |
| `:31` / `:16` `test_transform[0]` | `徐汇区虹漕路461号58号楼5楼` | 上海市/市辖区/徐汇区/虹漕路461号58号楼5楼/310104；-1,-1,0 | **golden:4**（逐 8 字段）；另 `l1_xuhui_full_chain_t04`（`engine/probe_test.mbt:41`） | **已覆盖** |
| `:31` / `:17` `[1]` | `泉州市洛江区万安塘西工业区` | 福建省/泉州市/洛江区/万安塘西工业区/350504；-1,0,3 | 无该输入；同类“省+市+区”由 golden:1/2/4、`[2]` 覆盖 | 未覆盖（静默；同类行为有覆盖） |
| `:31` / `:18` `[2]` | `福建省鼓楼区鼓楼医院` | 福建省/福州市/鼓楼区/鼓楼医院/350102；0,-1,3 | **golden:24** | **已覆盖** |
| `:32` / `:19` `[3]` | `天津市` | 天津市/—/—/""/120000；0,-1,-1 | `location_direct_municipality_city_is_shiqu`（`engine/location_fields_wbtest.mbt:262`）仅断言 adcode=120000（:281），未断言省/市/区/addr/pos | 部分覆盖（静默缺口：其余字段未断言） |
| `:33` / `:20-21` `[4]` | `我家的地址是江苏淮安清江浦区人民路111号` | 江苏省/淮安市/清江浦区/人民路111号/320812；6,8,10 | 无该输入；简称级联与三段偏移无组合用例 | 未覆盖（静默） |
| `:34` / `:22` `[5]` | `我家的地址是江苏淮安清江浦区上海路111号` | 同上，addr=上海路111号 | 无 | 未覆盖（静默） |
| `:35` / `:23` `[6]` | `上海市浦东新区东明路街道三林路15号` | 上海市/市辖区/浦东新区/东明路街道三林路15号/310115；0,-1,3 | 精确输入无；同前缀 `上海市浦东新区世纪大道100号` = **golden:3** | 未覆盖（静默；同类覆盖） |
| `:36` / `:24` `[7]` | `贵州省黔南布依族苗族自治州长顺县长寨街道和平中路28号` | 贵州省/黔南布依族苗族自治州/长顺县/长寨街道和平中路28号/522729；0,3,13 | 无；golden 无任何“自治州”长名（最长城市名场景未测） | 未覆盖（静默；`max_key_len` 长键路径无端到端用例） |
| `:37` / `:25` `[8]` | `宁夏` | 宁夏回族自治区/—/—/""/640000；0,-1,-1 | **golden:15** | **已覆盖** |
| `:38` / `:26` `[9]` | `淮安市市辖区` | 江苏省/淮安市/市辖区/""/320801；-1,0,3 | `location_area_prefix_completion_three_levels`（`engine/location_fields_wbtest.mbt:286`）断言省/市/区/adcode/三项 pos（:301-310）；**addr 未断言** | 部分覆盖（静默缺口：addr） |
| `:40` / `:27` `[10]` | `32323`（**int**） | 全 None；-1,-1,-1 | `extract(text: String)` 不能接收 Int（`engine/extract.mbt:34`）；字符串 `"32323"` 由 **golden:18** 与 `l4_no_match_empty_record`（`engine/probe_test.mbt:94`）覆盖同一输出 | 不适用（类型层）；上游 int 分支未覆盖 |
| `:41-46` | 上述 11 行再以 `pos_sensitive=False` 跑一遍 | 仅 5 字段（无 pos 列） | 无任何测试断言默认/False 的 pos；`a9_probe_shanghai`（`engine/probe_test.mbt:11`）走默认路径但不断言 pos | 未覆盖（静默；R-02） |

### 2.2 `tests/test_cpca.py::test_umap`（2 条）

| 上游位置 | 输入 / umap | 上游期望 | MoonBit 侧覆盖 | 定性 |
|---|---|---|---|---|
| `:50-52` | `朝阳区汉庭酒店大山子店`，`{"朝阳区":"110105"}` | 北京市/市辖区/朝阳区/汉庭酒店大山子店/110105；-1,-1,0 | **golden:26**；`m7_umap_selects_candidate_by_adcode`（`engine/semantics_wbtest.mbt:278`）、`l3_umap...`（`engine/probe_test.mbt:60`） | **已覆盖** |
| `:53` | `吉林省朝阳区不知道店`，`{"朝阳区":"110105"}` | 吉林省/长春市/朝阳区/不知道店/220104；0,-1,3 | **golden:23** 覆盖“同输入、同期望但 umap=null”；带 umap + 有上级的组合无测试（代码分支顺序见 R-01） | 部分覆盖（静默缺口：umap×上级） |

### 2.3 `tests/test_cpca.py::test_transform_text_with_addrs`（4 个文本块 / 8 条断言行）

PRD 明确将该 API 列为非目标：`docs/superpowers/prds/202610152152-moon_cpca-提取引擎-prd.md:76`（原文：“多地址长文本的批量提取 API（`transform_text_with_addrs`）｜申报书只列单条 `extract`；上游该能力作为 `[EXT]` 由本单元 P2 承载，不进 P0”）。MoonBit 公开面只有 `extract`（`engine/extract.mbt:34`；`engine/` 与 `data/` 生产包中 `pub fn` 仅此一个）。因此以下均属**声明非目标**，不是静默遗漏；但会限制“与 Python 用例集交叉对照”的字面完整性。

| 块/行 | 上游位置 | 上游期望 | MoonBit 侧 | 定性 |
|---|---|---|---|---|
| B1-row0 | `:57-59` | 吉林省/长春市/朝阳区/""/220104；3,-1,6 | 单条 `transform` 同文本 = golden:29，但 addr=“，而我家在北京市朝阳区，太远了”（单条语义）；多地址产出无 API | 非目标（PRD:76）；单条路径部分覆盖 |
| B1-row1 | `:60` | 北京市/市辖区/朝阳区/""/110105；14,-1,17 | 无 | 非目标（PRD:76） |
| B2-row0 | `:62-64` | 吉林省/—/—/""/220000；0,-1,-1 | 无 | 非目标（PRD:76） |
| B2-row1 | `:65` | 北京市/—/—/""/110000；3,-1,-1 | 无 | 非目标（PRD:76） |
| B2-row2 | `:66` | 江苏省/南京市/鼓楼区/""/320106；-1,-1,6 | 单条 `南京市鼓楼区`（无 umap）= golden:25，结果同 320106 | 非目标（PRD:76）；单条路径已覆盖 |
| B3-row0 + `len==1` | `:68-71` | 天津市/—/—/""/120000；0,-1,-1；长度 1 | 单条天津仅 adcode 断言（见 2.1 `[3]`） | 非目标（PRD:76）；单条部分覆盖 |
| B4-`len==3` | `:73-75` | 必须 3 行 | 无 | 非目标（PRD:76）；不可表达 |
| B4-row0 | `:76` | 上海市/市辖区/徐汇区/""/310104；-1,-1,4 | 单条同文本 = golden:4（pos=0 而非 4，且 addr 吞尾） | 非目标（PRD:76）；单条路径已覆盖（语义不同） |
| B4-row1 | `:77` | 福建省/泉州市/洛江区/""/350504；-1,21,24 | 无 | 非目标（PRD:76）；且单条泉州洛江也未覆盖 |

### 2.4 `tests/test_matcher.py`（6 组断言）

| 上游位置 | 输入 / 断言 | MoonBit 侧覆盖 | 定性 |
|---|---|---|---|
| `:19-23` | `"不测"` → 1 个匹配、`attr_infos` 长度 1、name=`不测自治区`、end=1 | 合成数据不可注入（`build_matcher` 硬绑 `@adcodes`）；简称共享与 end 语义由 `m3_abbrev...`（`engine/semantics_wbtest.mbt:155`）+ `m1...`（:101，`上海市` end=2）等价覆盖 | 部分覆盖（等价语义，非同数据） |
| `:25-27` | `"不测自治区"` → 1 个匹配、end=4 | `m1_longest_match_wins_at_same_start`（:101）锁定同起点最长 + end | 部分覆盖（等价语义） |
| `:29-33` | `"测试区"` → 1 个匹配、2 候选、顺序 `111112,111113` | `m3_shared_candidate_list_same_name_districts`（:141）精确锁定 `朝阳区` 候选顺序 `220104,110105`；`duplicate_names_share_candidate_list_in_row_order`（`engine/matcher_wbtest.mbt:38`） | **已覆盖（等价用例）** |
| `:35-36` | `"哈哈"` → 0 匹配 | `no_match_yields_empty_match_list`（`engine/matcher_wbtest.mbt:49`，输入 `虹漕路461号`） | **已覆盖（等价用例）** |
| `:38-40` | `"天津市"` → 1 匹配，`get_one_addr().name == "天津市"` | 端到端 `extract("天津市").adcode == "120000"`（`engine/location_fields_wbtest.mbt:281`）可反证长键胜过 `津市` 简称；name/匹配数未直接断言 | 部分覆盖（静默缺口：name/序列） |
| `:42-44` | `"北京市"` → 1 匹配，name=`北京市` | **golden:9**（省=北京市/adcode=110000）+ `a9_probe_shanghai` 同形态 | **已覆盖（端到端）** |

### 2.5 `tests/test_structures.py`

| 上游位置 | 断言 | MoonBit 侧 | 定性 |
|---|---|---|---|
| `:22-24` `test_get_full_name` | `AddrMap.get_full_name('淮安') == '淮安市'` | 无 `AddrMap` 类型；`Location` 无该 API | 未覆盖（静默；上游 `AddrMap` 仅被 import、transform 路径未使用：`cpca/__init__.py:5`） |
| `:26-28` `test_get_relational_addrs` | `('江苏省','淮安市','清江浦区') == places[0]` | 无 | 未覆盖（静默；上游死代码） |
| `:30-31` `test_in` | `'淮安' in addr_map` | 无 | 未覆盖（静默；上游死代码） |
| `:33-36` `test_is_unique_value` | 淮安 True；丽水市 False；杭州市 False | 无 | 未覆盖（静默；上游死代码） |
| `:38-39` `test_get_value` | `get_value("丽水市", P) == "浙江省"` | 无 | 未覆盖（静默；上游死代码） |
| `:52-64` `TestPca::test_province`（3 个 `_assert`） | `Pca.province/city/area` 可读写，初值安徽省/合肥市/肥东区 | `Location` 8 字段只读；字段语义/NULL 性由 `location_fields_shape_and_types`（`engine/location_fields_wbtest.mbt:105`）覆盖；可变 setter 无对应（语言差异） | 部分覆盖（字段语义）/ 静默（可变性） |
| `:67-71` `test_propertys_dict` | `{"省","市","区","省_pos","市_pos","区_pos"}` 两态 | `Location` 字段一一对应，但无 `propertys_dict` 方法；pos=True 形态由 golden 全量覆盖，False 形态无 | 部分覆盖（静默缺口：dict/False 形态） |

---

## 3. 行为风险清单（未被 32 条 golden 覆盖）

> 判定规则：能指到代码且当前实现看似与上游一致 → `未验证`（测试缺口，不宣称偏差）；能指到明确表示差异 → `设计差异`；已声明非目标 → `非目标`。本次**未发现可证实的算法偏差**；E11 的 7,885 条差分 0 不一致仅证明“按 MoonBit 源码转写的逻辑”与上游一致，不等于编译产物在全部输入上已证。

| 编号 | 场景 | 上游行为 / 证据 | MoonBit 代码指针 | 现有覆盖 | 判定 |
|---|---|---|---|---|---|
| R-01 | `umap` 与“已有上级”同时出现 | 有 parent 时先按归属过滤，`first_adcode` 不参与（`cpca/matcher.py:14-15`）；实测 `吉林省朝阳区不知道店` + `{"朝阳区":"110105"}` → 220104 | `engine/matcher.mbt:267-281`（`match parent` 分支先于 `first_adcode`）；`engine/extract.mbt:231-233` 仍计算 `first_adcode` 但被忽略 | golden ⑪ 26-28 全为无上级；`test_umap:55` 未移植 | **未验证**（代码顺序正确；无测试锁定） |
| R-02 | `pos_sensitive=false` / 缺省 | 上游 `empty_record(False)` 不含 pos 键、`tidy_order` 只选 5 列（`cpca/__init__.py:152-158,161-168,135-141`） | `engine/extract.mbt:41-47`（默认 false）、`:231-240`（不写入，保持 -1） | 所有 golden 都用 true；默认路径仅 `a9_probe_shanghai` 调用但不断言 pos | **设计差异（已声明）**：MoonBit 恒返回 3 个 Int=-1；README:63 明示。未与上游“无 pos 列”形态对照 |
| R-03 | 一段文本含多个地址 | 上游 `transform_text_with_addrs` 产出 2/3/1/3 行（`tests/test_cpca.py:57-77`） | 无该 API；公开面仅 `extract`（`engine/extract.mbt:34`） | PRD:76 声明 P2/非目标；单条路径由 golden:29 覆盖（addr 吞第二地址） | **非目标**；但“用例集交叉对照”因此不完整 |
| R-04 | 数值输入（上游 `32323`） | 非 str → 空记录（`cpca/__init__.py:176-177`）；`tests/test_cpca.py:40` | `pub fn extract(text: String, ...)`（`engine/extract.mbt:34`） | 字符串 `"32323"` = golden:18；`l4`（`engine/probe_test.mbt:94`） | **不适用（类型层）**；上游 int 分支无法表达 |
| R-05 | 同名区候选数 >2（市辖区 286、城区 5、郊区 4、市中区 4、鼓楼区 4） | 无上级取候选首元素（`cpca/matcher.py:19-20`）；实测 `市辖区` → 贵州省/遵义市/市辖区/520301；`某县某路` 另见 R-06 | `engine/matcher.mbt:52-81`（数据行序入列）、`:282-290`（无上级取 `cands[0]`）；数据首行 `data/adcodes.mbt:64`（市辖区 520301） | golden 只覆盖 2 候选（朝阳区）与 4 候选的鼓楼区（有/无上级）；`市辖区/城区/郊区` 未测 | **未验证**（数据同源，差分 0 不一致；风险为数据顺序回归无测试） |
| R-06 | 单字键 `县` / `芒` 的误配 quirk | 上游 CSV 有 `500200000000, 县` 记录（`data/adcodes.mbt:1072`，等级 City）与 `芒市`→简称 `芒`；实测 `芒果` → 云南省/德宏州/芒市/“果”/533103；`某县某路` → 重庆市/县/—/“某路”/500200 | `engine/matcher.mbt:83-107` 为 `芒市` 剥“市”、`县` 不剥；键集合由 `data/adcodes.mbt` 决定 | 无任何 golden/测试 | **未验证（继承上游 quirk）**；若上游后续清洗该脏记录，两版会分叉 |
| R-07 | 同 end 多键枚举序（后缀碰撞） | pyahocorasick 从长到短；`matcher.py:77` 吞短匹配 | `engine/matcher.mbt:178-257` 窗起点升序（长窗先行） | 仅 `城东区/东区` 一例（`engine/matcher_wbtest.mbt:55`、`testdata/golden_test.mbt:228`） | **低风险**：本次机检 1,748 组后缀碰撞（键全集 3,867）全部“长先”，0 违例；但回归只锁 1 例 |
| R-08 | 非归属匹配被丢弃后的 addr 尾串 | `new_entry_when_not_belong=False` 静默跳过（`cpca/__init__.py:190-191`）；实测 `江苏省上海市徐汇区` → 江苏省/—/—/“上海市徐汇区”/320000 | `engine/extract.mbt:266`（`None => ()`，线程状态不变）、`:120` 尾串 | 无；golden 只有“有上级且归属成功”的 ⑩ 类 | **未验证**（代码路径正确；无测试） |
| R-09 | 长自治州名（黔南布依族苗族自治州，11 字） | `tests/test_cpca.py:36`；上游实测 0/3/13 | `engine/matcher.mbt:56-75` 的 `max_key_len`（数据最大 15）与 `:193-196` 窗上限 | golden 无“自治州”城市；同类 `l1` 只测 2 字市 | **未覆盖**；差分 harness 覆盖但编译产物无端到端用例 |
| R-10 | `umap` value 为 12 位 / 空串 / 未知键 | 与候选 6 位 adcode 等值比较失败 → 回落首元素（`cpca/matcher.py:16-18` + `cpca/__init__.py:45-46`）；实测 220104 | `engine/matcher.mbt:282-288`（`c.adcode6 == fa`）、`engine/extract.mbt:231-233` | **非 golden**，但 `m7_umap_value_width_and_empty_boundary`（`engine/semantics_wbtest.mbt:316`）逐值锁定；E11 差分亦 0 不一致 | **已由单元测试覆盖**（非 golden；残余风险低） |
| R-11 | 空串 / 非 BMP | 空串 → 空记录；非 BMP 按码点索引（`cpca/__init__.py:176-177`） | `engine/extract.mbt:120`（码点）、`engine/matcher.mbt:114-122` | **golden:20**（空串）、**golden:31/32**（非 BMP）、`location_pos_codepoint_index_non_bmp`（`:204`） | **已覆盖** |
| R-12 | 末级命中后无尾串 | `addr=""`（`cpca/__init__.py:199/224`） | `engine/extract.mbt:121-127`（`Some("")`）、`:179-199` | golden ③④；`location_addr_swallows_tail_and_empty_string`（`:312`） | **已覆盖** |

---

## 4. README 事实声明核查

| README 声明（file:line） | 验证入口 | 结果 |
|---|---|---|
| “共 3511 条”（`:3`） | E01、E04 `--records`、`data/adcodes_test.mbt:6` | **成立** |
| “34/344/3133 条”（`:10`） | E03、E04 `--levels`、`data/adcodes_test.mbt:28` | **成立** |
| CSV sha256 `66948f...18fe`（`:8`） | E02 + `data/adcodes.mbt:3` | **成立** |
| “已随本仓库 vendored”（`:7`） | E16 `git ls-files chinese_province_city_area_mapper` = 0 | **不成立**（仅存在于当前工作树；clone 不含） |
| “由仓库内 vendored 的上游 CSV 离线生成”（`:3,9`） | E09（`--no-network-check` 0 events；6/6 自校）、E10（与 HEAD 字节一致） | **成立（前提是工作树有 CSV）**；clone 上不成立 |
| “可复现”（`:34` 申报书 / README:73） | E09/E10：`gen_adcodes` 重生成字节一致；E12：`gen_golden` 内容归一后一致 | **部分成立**：当前工作树可复现；clone 缺 CSV/oracle 依赖（pandas+pyahocorasick 未声明）不可复现；Windows 工作树 CRLF 使“0 字节 diff”非字面成立 |
| “可更新”（`:34` 申报书） | `tools/gen_adcodes.py:712-721`（`--csv/--out`）+ `python -m pytest tools/test_gen_adcodes.py -q` → `7 passed` | **成立（机制）**；仍受“CSV 未入库”限制 |
| “零运行时依赖、零网络”（`:3,68`） | E07（白名单外 0；`moon.mod` deps=[]）；`grep` engine/data 无 `@fs/@io/@http/read_file`；`engine/moon.pkg` 仅 import `moon_cpca/data` | **成立** |
| 机检入口 `check_artifact.py` 各开关（`:11`） | E04（`--records/--fields/--levels/--order/--dup`）、E05（`--dup 朝阳区`） | **成立**（读上游 CSV；clone 缺 CSV 则 exit 2） |
| golden 命令 `gen_golden.py` / `--stats` / `check_golden.py` / `check_deps.py`（`:73-76`） | E08 / E06 / E07 | **成立**（`gen_golden.py` 写盘路径未执行，E12 以同函数内存输出比对） |
| README 示例输出（`:37-59`：徐汇、umap） | 对照 **golden:4**、**golden:26**；`l1`（`engine/probe_test.mbt:41`）、`l3`（`:60`） | **输出成立**；示例本身未被编译（无 example 包） |
| pos 口径 = 码点序号；false/缺省 = -1（`:63-64`） | golden 31（非 BMP）；`location_pos_codepoint_index_non_bmp`（`:204`）；false 路径无断言 | **true 成立**；false 为**设计约定**，非上游列形态 |
| adcode 6 位（`:65`） | golden 全部；`location_adcode_six_digits`（`:145`） | **成立** |
| 无匹配/空输入全 None + pos -1（`:66`） | golden 16-20；`l4`（`:94`） | **成立** |
| quirks：首元素 / addr 吞尾（`:67`） | golden 21/22/29；`m6`（`:259`）、`location_addr_swallows_tail...`（`:312`） | **成立** |
| 上游仅作 golden 基准、不进运行时（`:68`） | E07 + `engine/moon.pkg` | **成立** |
| E16 报告 `testdata/e16_failure_report.txt` 由固定命令产生、含四项（`:79-82`） | 诊断经 `eprintln` 写 stderr（`testdata/golden_test.mbt:166`），README 命令只有 `>`（stdout） | **不成立**：stderr 不会进入报告文件；需 `2>` 或 `2>&1` |

---

## 5. 缺口清单

| 缺口编号 | 缺口 | 影响（申报书验收是否受阻） | 建议归属 |
|---|---|---|---|
| G-01 | vendored `chinese_province_city_area_mapper/`（`adcodes.csv` + 上游源码）未入 git；generator/checker 在全新 clone 上不可运行 | **受阻**：§三“可复现、可更新”“数据由仓库内脚本生成入库”无法在交付物上验收；README:7 不实 | 工程/发布（把 CSV（及必要 oracle 锁定说明）入库，或改为可下载+sha 固定；补 dev requirements） |
| G-02 | 上游 `test_transform` 11 输入中 5 条完全未覆盖（泉州洛江、江苏淮安×2、浦东东明路、贵州黔南）、1 条仅 adcode（天津）、1 条 addr 未断言（淮安市市辖区） | **部分受阻**：“与 Python 用例集交叉对照”只能按子集声明 | 引擎（测试）：把上述输入加入 golden 或 wbtest |
| G-03 | `test_umap` 第 2 条（umap + 已有上级）未覆盖 | 不受阻（代码顺序正确，E11 差分 0）；测试锁定缺失 | 引擎（测试） |
| G-04 | `pos_sensitive=false` 的 pos 形态未与上游对照；MoonBit 恒为 -1 | 不受阻（README 已声明设计约定）；若验收要求“与上游列形态一致”则部分受阻 | 引擎/文档（明确列为语言差异） |
| G-05 | `test_transform_text_with_addrs` 无对应 API | 不受阻（PRD:76 明确非目标）；但“用例集交叉对照”字面不完整 | 引擎/范围（在 README/申报书差异说明中显式列为非目标） |
| G-06 | `test_matcher` 6 组为等价语义覆盖，非同数据；`test_structures` 的 `AddrMap/Pca` 无实现 | 不受阻（上游 `AddrMap/Pca` 未参与 transform，`__init__.py:5` 仅 import） | 引擎/文档（声明不移植） |
| G-07 | 无 mooncakes.io 发布证据（无 workflow/tag/记录；registry 探测不可判定） | **受阻**：§三“发布至 mooncakes.io”无法验收 | 发布 |
| G-08 | README E16 报告命令用 `>` 仅重定向 stdout，而四项诊断走 stderr | 不受阻于核心验收；诊断能力声明不实 | 工程/文档（改 `2>` 或 `2>&1`，或让测试写文件） |
| G-09 | README 示例无可执行包/未被编译 | 轻微：示例输出已由 golden 反证，但“示例可运行”未验证 | 工程（加 example 包或 CI 编译示例） |
| G-10 | 单字键 `县`/`芒` 脏数据 quirk 无测试 | 不受阻（与上游同源同行为）；上游数据更新时存在分叉风险 | 数据/引擎（加 quirk 回归或数据清洗策略） |
| G-11 | 同名区候选 >2（市辖区 286 等）与长自治州名的数据顺序/长键路径无端到端用例 | 轻微；差分 harness 已证明逻辑一致，编译产物回归未锁 | 引擎（测试） |
| G-12 | 数值输入 `32323` 的上游分支不可表达 | 不受阻（`extract(String)` 类型契约；申报书未要求非字符串） | 引擎/文档（在类型契约中注明） |
| G-13 | Windows 工作树 CRLF 与 generator LF 不一致，`gen_golden` 后原始字节 diff 非 0 | 轻微：git 归一后无 diff；影响“0 字节”字面验收口径 | 工程（`.gitattributes` 给 `testdata/golden.*` 也 pin `eol=lf`） |
| G-14 | 上游 `test_cpca.py` 因缺 `mock` 无法原样收集 | 部分受阻：无法“原样跑上游用例集”；oracle/golden 不受影响 | 工程（补 dev 依赖或移除未使用的 `mock` 导入） |

---

## 6. 结论（按申报书验收口径）

- **可判定为达标**：单条 `extract` 的省/市/区/addr/adcode 语义、简称归一、级联补全、`pos_sensitive=true` 的码点位置、6 位 adcode、空/无匹配记录、同名区消歧与首元素 quirk、数据表规模与等级分档、CI 工作流存在且本地构建测试通过。
- **不可判定/未达标**：mooncakes 发布；全新 clone 上的数据表与 golden 可复现/可更新；上游用例集的“全量”交叉对照；README E16 报告命令。
- **未被测试锁定但代码看似正确的分支**：umap×上级、非归属匹配丢弃、`市辖区/城区` 多候选、长自治州名、单字键 quirk。建议按 G-02/G-03/G-10/G-11 补 golden，而不是改引擎。
