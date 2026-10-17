# 当前项目状态

更新：2026-10-17。本轮《神奇之门·刑事案件预测》，criminal-cases/排序16，不推印刷章号；累计15份章级输入。继续遵守用户重申总指令docs/user_instructions/master_spec_reaffirmed_2026-10-17.txt和既有仓库规则，不重置阶段或提前训练。

## 本章来源和案例

TXT37260原字节/14484字符/261行，SHA256 289465c220a0701545b9f093b4b91d041d600a4c9da67bf58e33a10ece0f0ea9。uploads、SQLite BLOB、snapshot raw完整保存；原字己已、妍头等不擅改。confirmed/user_attestation，不冒称软件外查报刊或案件。

17完整语境组/7技术边界/11参考候选；5完整故事/5家族/5事件/6原盘、62过程记录/64证据。一般案情角色玄武/天蓬/辛、特征工具、方向、无名尸、能否破案、庚格及自首经验按条件保存，全部reference_only，不自动作为现实人物认定或取证依据。

银行案置闰阳3原断与事后拆补阳2对照分别保存，两个chart_id同一事件/家族；6月24日/7月4日原断应期与9月9/10日结果不改成命中，187行应期未准和当时未看出的承认单列。拆补盘、后验案情及张志春按语不进入首次预测。服装案已抓两名小孩是107行才透露；被盗额与最终损失分开。抢劫案可望抓获原断和实际击毙分开。末例基本合乎实际不升级为每条推断获证，至今未破仅原书时点。

沿既有import_chapter、install_curated、import_cases、install_candidates和QimenService/CLI/WSGI读取；source_chart同ID投影，54宫与独立字面gold同时核对原盘及服务结果，原字前缀/中五原干/禽壬保留。无schema迁移、新目录或workflow增删。详见ingestion/SHENQI_CRIMINAL.md。

## 当前权威库

| 资源 | 数量 |
|---|---:|
| 书 / 章级输入 / 原始文档 | 1 / 15 / 15 |
| 概念索引 / 方法 | 2240 / 24 |
| 知识项 / 来源片段 | 965 / 2620 |
| 完整故事 / 家族 / 事件 / 原书盘 | 72 / 69 / 78 / 77 |
| 案例记录 / 证据关联 | 1206 / 1529 |
| 来源审读历史 / 数据版本记录 | 22 / 70 |
| 正式角色rules / 训练任务 / 冻结release | 0 / 0 / 0 |
| schema | v1，无迁移 |

数据版本29d1843d-9581-4928-a37d-fbf2d6d4cb65；snapshot manifest SHA256 c8c94663baac21483469b0a743c180952bcb01488b11409fbe56f1a919a8fdd7。旧25权威表每条旧行逐字段仍在，14旧原文逐字节不变；41文件快照恢复再导出一致。旧章source/cases/curation/gold和总指令原件不覆盖。

## 已实际运行的验收

`PYTHONPATH=src python3 -m unittest discover -s tests -v`本机323项通过、0失败/错误，含本章16专项。覆盖原字节/引文/分句、54宫独立gold和同ID读取、两种方法与后知隔离、失准应期、金额与前置逮捕反馈、击毙与抓获区别、未破案件观察截止、源字面、11候选条件不激活、旧行保留/幂等/拒改及快照恢复。既有CLI目录实际读取5案，WSGI API读取全部6盘；没有用ask阻断或参考查询冒充专业预测完成。

通过已连接GitHub接口非强制更新main，提交后必须按精确SHA核对全部文件blob和Ubuntu/macOS × Python3.11/3.12四CI；未完成时不声称远端成功。验收记录data/provenance/criminal_validation.json，本地回执work/github-sync.json。

## 未完成

独立历法/节气/四柱及全面排盘/空亡马星/完整寄宫、正式用神激活、专业综合断案和应期、模型训练/现实效果评估、公众Web均未完成。原书和作者意见不等于程序独立验证或现实侦查依据，按源23–25行保留其明确限制。正式问事仍由QimenService.ask阻断，未引入其他古籍。历史验收报告保留，完成同步后等待用户下一章。


远端内容验收：`ef08ac337201d5acc71ad5032525f06979c22eff` 已核对main一致、285文件blob匹配；[Actions 39074750056](https://github.com/turnupmason/QimenLLM/actions/runs/39074750056) 的Ubuntu/macOS × Python3.11/3.12四job全部success，四份日志均实际Ran 323 tests / OK。通过已连接GitHub接口非强制更新，未增删workflow。这里记录已实际验收的内容提交；本验收文档后续提交本身仍须按精确新SHA另查四CI，不以旧CI替代。
