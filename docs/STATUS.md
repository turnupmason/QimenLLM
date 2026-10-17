# 当前项目状态

更新：2026-10-17。本轮《神奇之门·行人走失预测》，技术键missing-person/排序14，不推断印刷章号；累计13份章级输入。最高要求仍见PROJECT_CHARTER及user_instructions/master_spec_2026-10-17.txt。

## 本章来源与工程

用户TXT49372原始字节/22812字符/477行、末尾LF，SHA256 5eca2a1a0914691ec439040a9b538fb8e4385fa5cf8ac5286bc5ae86d25b6574。源字节在uploads、SQLite BLOB与snapshot raw完整保存，Unicode框线、标点、未给出行盘的末句不补写。confirmed/user_attestation，未声称系统亲自外查。

17完整语境组、7技术边界、9来源候选均reference_only；走失时间和问测时间、明确六亲关系、年命兼取、方向/安危/找回/归期方法分开，年龄不替代人物关系。新增10完整故事/10家族/10事件/11已给原盘、111过程记录/111证据。案例二双盘为同一失踪，后六次求测只有摘要不造盘；三为事后比较，五/九错误原断保留，十先保存失验与来信再保存作者回信及研讨，推测死亡日不升级为实际死亡日。混合段完整原文和精确分句字节范围同时保留；后验内容不进入首次预测。

原盘为四行无标签Unicode格，沿source_chart同ID读取，99宫以独立字面gold逐格核对，星门前缀、中心干和原书芮/禽表述差别不改。完整调用链沿既有import_chapter、install_curated、import_cases、install_candidates、QimenService与CLI/WSGI API，无schema迁移或workflow增删。详见ingestion/SHENQI_MISSING.md。

## 累计权威库

| 资源 | 数量 |
|---|---:|
| 书 / 章级输入 / 原始文档 | 1 / 13 / 13 |
| 概念索引 / 方法 | 2090 / 22 |
| 知识项 / 来源片段 | 904 / 2374 |
| 完整案例 / 家族 / 事件 / 原书盘 | 59 / 56 / 65 / 63 |
| 案例记录 / 证据 | 1052 / 1373 |
| 来源审读历史 / 数据版本记录 | 20 / 60 |
| 正式角色rules / 训练任务 / 冻结release | 0 / 0 / 0 |
| schema | v1，无迁移 |

数据版本078f00ff-c883-4edb-b975-6ff4f0250153，snapshot manifest SHA256 df2f3d540f6e379d9a3664654d690ac7be2793eb2ebd851ff1dfc663c9a8592d。旧25权威表全部行逐字段仍在，12旧原文逐字节相同；当前快照39文件，恢复再导出一致。旧章source/curation/cases/gold均未修改。

## 已实际验收

`PYTHONPATH=src python3 -m unittest discover -s tests -v`本机291项通过，0失败/错误，含本章16专项。覆盖全99宫独立gold、混合原段和分句出处、后验隔离、双盘/缺盘、错误原断和未应期限、SQL条件不绑定、旧数据保留、幂等/拒改及快照恢复。现有WSGI API读取11原盘、CLI目录读取10完整故事。旧经营测试的历史43故事/45盘检查限定排序≤12的原11份输入，未来新增章不改变这个历史基准。

远端沿已连接GitHub接口非强制更新main；新提交SHA、所有文件blob和Ubuntu/macOS × Python3.11/3.12四CI必须在提交后实际核验，尚未完成时不称远端成功。实际证据见data/provenance/missing_validation.json与本地work/github-sync.json。

## 未完成和后续

独立历法/节气/四柱、全面排盘/空亡马星/完整寄宫、正式用神激活、专业综合断案/应期、模型微调和现实预测评估、公众Web均未完成。正式ask仍由QimenService阻断；原文保存与投影通过不等于模型学会或现实预测准确。未提前训练或加入其他古籍。历史入库报告保留原验收事实，下一章继续既有增量处理。
