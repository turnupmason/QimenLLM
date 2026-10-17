# 《神奇之门》第二章接收与验收范围

更新：2026-10-17（America/New_York）。章名“时家奇门的起局方法”，Phase 1；仅处理用户本项目提供的完整原文，没有导入所引他书或旧项目。

## 原文与来源

| 项目 | 记录 |
|---|---|
| 书 / 章键 | `shenqi-user-text-v1` / `chapter-02` |
| 原文修订 | 1 |
| 原始大小 | 22,354 bytes / 8,284 字符 / 416 逻辑行 |
| SHA-256 | `617c7936aeb2dff7b82a9d461ac030ec37011ee83e8c4169429288f10075ff92` |
| revision_id | `042b2b75-405e-4487-b7ba-cba197eff874` |
| 全章 source_id | `ef4dd33f-1394-473a-a354-f46cb55455c4` |
| 本轮结构化后数据版本 | `846ca783-fdb5-48c1-98b6-7590caaf7537` |
| 原文确认状态 | `pending`；编译和测试不冒充用户已校勘确认 |
| 作者 / 版本 / 页码 / 地点时区 | 本次材料未明确，不凭常识补齐 |
| 原文 GitHub 检查点 | 私有 `turnupmason/QimenLLM`，提交 `2ecdc5b`；此提交为完整原文保全检查点，本轮后续改动以最终同步核验为准 |

来源详见 [导入记录](../../data/provenance/shenqi_chapter02_import.json) 与 [结构化资料](../../data/structured/shenqi/chapter02_curated.json)。原始文本、表格、不明字串和空行按输入字节保存；整理说明和派生环序不得覆盖原文。研究及私有备份授权不等于公开全文权限。

## 上下文与覆盖

| 节 | 原始输入行 | 内容 |
|---|---|---|
| 第一节 掌上快速起局法 | 1–176 | 十二地支与九宫掌位、定局、时辰、五鼠遁、值符值使和神盘步骤 |
| 第二节 纸上快速起局法 | 177–416 | 十步流程、阳三与阴八两个完整文字盘和逐步排盘说明 |

本章 32 个上下文组包括覆盖全部输入的 30 个主体组和 2 个有意重叠组，用于隔离有向五行关系及旋转约定。9 个结构化数据集为 `palm_branches`、`palm_palaces`、`hour_windows`、`five_rat_hours`、`stem_combinations`、`rotation_conventions`、`explicit_palace_elements`、`chapter_element_relations`、`paper_workflow`；前 8 个为编译教学数据族，十步流程只作结构参考，不充当历法算法。

本章另有 22 项疑点或能力限制、3 个完整演算教学例、2 张来源完整文字盘、162 条上下文概念索引。两个完整例分别为原书给定的 1995 年 6 月 11 日 9:30 阳三丁巳盘、1995 年 8 月 13 日 20 点阴八戊戌盘；掌上阳二壬戌例没有给年份或具体节气，不反推补齐。

| 累计覆盖 | 两章合计 |
|---|---|
| 书 / 章 / 上下文组 | 1 / 2 / 72 |
| 编译教学数据族 | 20 |
| 疑点与限制 / 教学例 / 概念索引 | 43 / 14 / 425 |
| `knowledge_items` | 149；含上下文、限制、教学例与编译记录，不是 149 条断案规则 |
| `rules` / `cases` / `events` / `charts` / `training_tasks` | 均为 0 |

两张源盘随 `worked_example` 记录整体保存，不冒充历史问事 `charts` 或断案案例。概念数为带上下文索引条目数，不是去重概念数量；来源盘、程序重算盘和模型专业能力也分别计量。

## 实际计算链与命令

CLI、研究 API 和测试共用 `QimenService.calculate`。新增 `PaperCalculator` 从 SQLite 真实读取两章已编译数据和出处；已知日干可查五鼠遁，已知遁局及时干支且显式选择 `shenqi_ch2_paper_v1` 可转布天盘星及携干、八门、八神，保留同一盘的证据与哈希。

```sh
PYTHONPATH=src python3 -m qimenllm calculate hour_branch --args '{"clock_hour":9,"clock_minute":30}'
PYTHONPATH=src python3 -m qimenllm calculate hour_ganzhi --args '{"day_stem":"癸","hour_branch":"巳"}'
PYTHONPATH=src python3 -m qimenllm calculate symbolic_chart --args '{"dun":"阳遁","bureau":3,"hour_ganzhi":"丁巳","method":"shenqi_ch2_paper_v1"}'
```

时段映射仅使用调用者给出的钟表读数，软件明确采用起点含、终点不含的区间约定；这不是原书已说明的换日制度。`hour_ganzhi` 的日干由调用者提供，不自行推定子时属哪天。两者均不处理时区换算、夏令时、真太阳时、公历日柱或节气天文计算。

显式 `Inquiry.casting_method='shenqi_ch2_paper_v1'` 且 context 给出 `dun`、`bureau`、`hour_ganzhi` 时，正式 `ask` 可经同一计算模块取得不可变 `Chart`，状态为 `symbolic_verified`。该状态只验证符号输入下的盘层旋转；`ask` 仍返回 `blocked`，不会跳过完整历法、正式盘验证及角色规则门槛调用模型断案。

## 不得省略的限制

- 中五地干及天禽本宫保留；天禽随天芮实际转入外宫，不在原五重复放星。中心旬首按本章明例取天禽值符、死门值使；值使仍从原五计数，不能从寄二起数。值符目标原五与寄二布局分别记录，关联第一章第 404 行依据；最终值使到五时返回 `not_covered`，不猜寄门细则。
- 外八宫顺时针环 `1,8,3,4,9,2,7,6` 是由掌位及两个完整实例归纳的 `source_derived` 约定，有支持来源；星门固定相对序在阴阳遁中均按顺时针转布，值使锚点按阴阳顺逆数，神盘阳顺阴逆，这三种方向不得混用。
- 本章选小值符随大值符的方法，不抹去第一章每旬移动神盘的另一说。宫位五行仅新增原文明载离九火、坤二土、兑七金；水克火有新来源，金克木是首章同向重复支持，不是分歧，不补全其余五行关系。
- 五鼠遁的甲丙戊庚壬“五阳干”与第一章甲乙丙丁戊“五阳时”分开；五组干合化保存传统陈述，未给实际成立条件，不自动改写天干元素或认定所有同现干已化气。
- 两完整来源盘的日期、四柱及节气判断仍标原书给定、未独立历法复算；十步第一步没有提供转换算法。无时区、换日和交节细则时不声称自动公历起盘。空亡、马星及完整派生格局未实现，`complete_chart=false`、`calendar_recomputed=false`、`professional_analysis_completed=false`。
- “蛇夭矫”等只保留本例天地干组合及名称，不补通用断语、用神和应期。三例没有具体问事背景、人物关系、预测、反馈或续断，完整历史断案仍为 0；作者便捷实用及准确率主张不计平台实证指标。

## 实际验证与收尾

新增章节回归已实际执行：`PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_shenqi_chapter02.py' -v`，**15 项通过，0 失败**，日志为 `artifacts/chapter02-development-tests.log`。涵盖完整来源盘逐宫星干门神、五鼠遁、钟表边界、中心原宫与寄宫、同入口 API/ask、缺数据与方法拒绝、可恢复快照及并发状态隔离等。

这些检查证明给定符号条件下与来源一致及模块真实集成，不等于未见新问事评分、独立公历起盘、模型专业评估或现实预测准确率。全套最终测试、审计、快照恢复和本轮最终 GitHub 提交核验以 [STATUS](../STATUS.md) 及最终 validation 记录为准，不把预计测试数写成通过结果。

本轮不训练、不扩充未给章节；完成实际验证和私有仓库同步后等待用户下一部分资料。持续更新按 [GitHub 同步规范](../GITHUB_SYNC.md) 执行。
