# moon_cpca 上游用例覆盖映射 v1

> 版本：v1
> 权威来源：`chinese_province_city_area_mapper/tests/test_cpca.py`（vendored 快照）
> 机器校验：`python tools/check_coverage.py --doc docs/moon_cpca-upstream-coverage.md`

行数契约：14 行 = 11 条 `test_transform`（含整型 `32323` 类型层 N/A）+ 2 条 `test_umap` + 1 条 `pos_sensitive=false` 契约。
状态枚举仅 `精确` / `类型层 N/A`；所有字符串输入状态为 `精确`。
`moonbit_case_id` 稳定语法：golden 行 `golden:<exact input>`；wbtest 行 `engine/<file>.mbt:<test name>`。
「上游期望 8 字段」为 JSON 形态的 `province/city/area/addr/adcode/province_pos/city_pos/area_pos`（`null` = 上游 `None`），与 `testdata/golden.jsonl` 的 `expected` 逐字一致。

| 序号 | 来源 | 输入 | 上游期望 8 字段 | moonbit_case_id | 状态 |
|------|------|------|------------------|------------------|------|
| 1 | test_transform（test_cpca.py:31-46） | 徐汇区虹漕路461号58号楼5楼 | {"province":"上海市","city":"市辖区","area":"徐汇区","addr":"虹漕路461号58号楼5楼","adcode":"310104","province_pos":-1,"city_pos":-1,"area_pos":0} | `golden:徐汇区虹漕路461号58号楼5楼` | 精确 |
| 2 | test_transform（test_cpca.py:31-46） | 泉州市洛江区万安塘西工业区 | {"province":"福建省","city":"泉州市","area":"洛江区","addr":"万安塘西工业区","adcode":"350504","province_pos":-1,"city_pos":0,"area_pos":3} | `golden:泉州市洛江区万安塘西工业区` | 精确 |
| 3 | test_transform（test_cpca.py:31-46） | 福建省鼓楼区鼓楼医院 | {"province":"福建省","city":"福州市","area":"鼓楼区","addr":"鼓楼医院","adcode":"350102","province_pos":0,"city_pos":-1,"area_pos":3} | `golden:福建省鼓楼区鼓楼医院` | 精确 |
| 4 | test_transform（test_cpca.py:31-46） | 天津市 | {"province":"天津市","city":null,"area":null,"addr":"","adcode":"120000","province_pos":0,"city_pos":-1,"area_pos":-1} | `golden:天津市` | 精确 |
| 5 | test_transform（test_cpca.py:31-46） | 我家的地址是江苏淮安清江浦区人民路111号 | {"province":"江苏省","city":"淮安市","area":"清江浦区","addr":"人民路111号","adcode":"320812","province_pos":6,"city_pos":8,"area_pos":10} | `golden:我家的地址是江苏淮安清江浦区人民路111号` | 精确 |
| 6 | test_transform（test_cpca.py:31-46） | 我家的地址是江苏淮安清江浦区上海路111号 | {"province":"江苏省","city":"淮安市","area":"清江浦区","addr":"上海路111号","adcode":"320812","province_pos":6,"city_pos":8,"area_pos":10} | `golden:我家的地址是江苏淮安清江浦区上海路111号` | 精确 |
| 7 | test_transform（test_cpca.py:31-46） | 上海市浦东新区东明路街道三林路15号 | {"province":"上海市","city":"市辖区","area":"浦东新区","addr":"东明路街道三林路15号","adcode":"310115","province_pos":0,"city_pos":-1,"area_pos":3} | `golden:上海市浦东新区东明路街道三林路15号` | 精确 |
| 8 | test_transform（test_cpca.py:31-46） | 贵州省黔南布依族苗族自治州长顺县长寨街道和平中路28号 | {"province":"贵州省","city":"黔南布依族苗族自治州","area":"长顺县","addr":"长寨街道和平中路28号","adcode":"522729","province_pos":0,"city_pos":3,"area_pos":13} | `golden:贵州省黔南布依族苗族自治州长顺县长寨街道和平中路28号` | 精确 |
| 9 | test_transform（test_cpca.py:31-46） | 宁夏 | {"province":"宁夏回族自治区","city":null,"area":null,"addr":"","adcode":"640000","province_pos":0,"city_pos":-1,"area_pos":-1} | `golden:宁夏` | 精确 |
| 10 | test_transform（test_cpca.py:31-46） | 淮安市市辖区 | {"province":"江苏省","city":"淮安市","area":"市辖区","addr":"","adcode":"320801","province_pos":-1,"city_pos":0,"area_pos":3} | `golden:淮安市市辖区` | 精确 |
| 11 | test_transform（test_cpca.py:31-46，整型输入） | 32323 | {"province":null,"city":null,"area":null,"addr":null,"adcode":null,"province_pos":-1,"city_pos":-1,"area_pos":-1} | `golden:32323` | 类型层 N/A |
| 12 | test_umap（test_cpca.py:52，umap={"朝阳区":"110105"}） | 朝阳区汉庭酒店大山子店 | {"province":"北京市","city":"市辖区","area":"朝阳区","addr":"汉庭酒店大山子店","adcode":"110105","province_pos":-1,"city_pos":-1,"area_pos":0} | `golden:朝阳区汉庭酒店大山子店` | 精确 |
| 13 | test_umap（test_cpca.py:53，umap={"朝阳区":"110105"}） | 吉林省朝阳区不知道店 | {"province":"吉林省","city":"长春市","area":"朝阳区","addr":"不知道店","adcode":"220104","province_pos":0,"city_pos":-1,"area_pos":3} | `golden:吉林省朝阳区不知道店` | 精确 |
| 14 | pos_sensitive=false 契约 | 11 条 test_transform 输入 × pos_sensitive=false/缺省 | 无 pos 列（不适用） | `engine/location_fields_wbtest.mbt:location_pos_default_minus_one` | 类型层 N/A |

注：

- 第 11 行输入为整型 `32323`（上游 `addr_list` 末项 `# 测试错误数据`）：上游期望 8 字段即 `_assert_line(... 10, None, None, None, None, None, -1, -1, -1)`；MoonBit 侧 `transform` 入参为 `String`，整型在类型层不可表达，故状态记 `类型层 N/A`，其字符串形（`"32323"`）已由 golden 行覆盖。
- 第 12/13 行为 `test_umap` 的两条输入；上游同一 `umap={"朝阳区":"110105"}` 调用下，第一条经 umap 命中 `110105`（北京市/市辖区），第二条按自然匹配得 `220104`（吉林省/长春市/朝阳区）。
- 第 14 行是 `pos_sensitive=false`（含缺省）契约：上游 `pos_sensitive` 默认 `False`（`cpca/__init__.py:90`），此路径下输出无 pos 列，故 8 字段列不适用；MoonBit 侧以 `engine/location_fields_wbtest.mbt:location_pos_default_minus_one` 覆盖：同输入分别走「不传 `pos_sensitive`」与「显式 `pos_sensitive=false`」两路，断言 `province_pos`/`city_pos`/`area_pos` 全为 `-1`。
- `golden:` 行的 `expected` 读自 `testdata/golden.jsonl`（上游 cpca 0.5.5 实跑生成），已与上游 `_assert_line` 逐字段核对一致。
