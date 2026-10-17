# 当前项目状态

更新：2026-10-17。本轮《神奇之门·天时气象预测》，weather-prediction/接收排序19，累计18份章级输入；本源未给印刷章号。继续遵守AGENTS和docs/user_instructions/master_spec_reaffirmed_2026-10-17.txt，旧总指令保留，不重置阶段。

## 本章来源与案例

TXT19857原字节/8301字符/156行，末尾LF；SHA256 6093f9a89bd2eb889c392242892528a9022c6d9565f74be8912e2a8724663697。uploads、SQLite BLOB、snapshot raw原字节保留，Unicode框线/原盘中宫/原盘单字等不改。confirmed/user_attestation，软件未亲自调查历史天气或人物。

13完整语境组/8技术边界/5参考候选；5完整故事/5事件/5原盘、36过程记录/36证据，新增4家族。原书现代科学说明、九星主天时兼看干门神、晴风/雨雪/河水的组合和排除条件完整保留，均reference_only，不宣称现代天气预测模型或洪水评估能力。

第四例104–106明确沿体育章第五例同一局；不同天气目标事件与体育事件共用原家族，保留原family描述、旧行与旧源图。新天气图离九辅庚、体育旧图铺庚按各源字面保留，分别是来源图记录，不当两份独立起局或互相更正；两个chart_id各自投影，不跨事件挂证据。第一例42行混合预测/结果附精确字节分句；第二例三种六爻只叙述不补图或扩增样本。第三例9时停雨/9:15揭牌/10时再雨保留，第四例三四级风预测与仅有风结果分开，第五例来电时与次日用事盘分开。

沿既有import_chapter/install_curated/import_cases/install_candidates与QimenService/CLI/WSGI读取。source_chart按确切SHA支持原盘中宫/原盘单字的三行格式，45宫独立人工字面gold同时核对结构化与同ID投影，未重排或公历复算。不改旧章source/curation/cases/gold/总指令；无schema迁移、新目录或workflow增删。见ingestion/SHENQI_WEATHER.md。

## 当前权威库

| 资源 | 数量 |
|---|---:|
| 书 / 章级输入 / 原始文档 | 1 / 18 / 18 |
| 概念索引 / 方法 | 2410 / 27 |
| 知识项 / 来源片段 | 1041 / 2906 |
| 完整故事 / 家族 / 事件 / 来源原盘 | 90 / 86 / 96 / 95 |
| 案例记录 / 证据关联 | 1377 / 1700 |
| 来源审读历史 / 数据版本记录 | 25 / 85 |
| 正式角色rules / 训练任务 / 冻结release | 0 / 0 / 0 |
| schema | v1，无迁移 |

数据版本c6d4ab96-fd92-4ac1-b752-884d262ada41；snapshot manifest SHA256 c2004debc01d5aef38ddbecee07fa58a7428ff19ce8c3cba46554655ec1e16fe。旧25权威表全部旧行逐字段仍在，17旧原文逐字节不变；44文件快照恢复再导出一致。95是来源盘记录数，包含原文明示共局的不同源图，不据盘数扩大独立预测样本。

## 已实际运行的验收

本章17专项已通过，涵盖原字节/引文/分句、45宫独立gold和同ID读取、跨章家族与源图变体、六爻叙述不造图、时段/全天范围、风级未逐项确认、一般法正反条件、候选不激活、CLI/WSGI真实读取、旧行/幂等/拒改/快照恢复。全量命令`PYTHONPATH=src python3 -m unittest discover -s tests -v`实际375项通过、0失败/错误；CLI实际读取5案、WSGI实际读取全部5盘。远端精确SHA四CI验收另记data/provenance/weather_validation.json，未验证部分不冒称成功。

通过已连接GitHub接口非强制更新main，逐blob核验并检查Ubuntu/macOS × Python3.11/3.12四CI。原有.github/workflows/tests.yml保留，不新增一次性作业；历史workflow解释仍见ingestion/SHENQI_TRAVEL.md。

## 未完成

独立公历/节气/四柱/全面排盘、正式用神激活、专业断案与应期、模型训练/现实预测评估及公众Web未完成。正式问事仍通过QimenService.ask，资料读取或阻断不算专业预测成功。未用外部天气资料或模型记忆补源。完成验收后等待用户下一章。


远端内容验收：`79ec410a15204831890b4099ea88c410341a84a2` 已核对main一致、321文件blob匹配；[Actions 39080835687](https://github.com/turnupmason/QimenLLM/actions/runs/39080835687) 的Ubuntu/macOS × Python3.11/3.12四job全部success，四份日志均实际Ran 375 tests / OK。通过已连接GitHub接口非强制更新，未增删workflow。这里记录已实际验收的内容提交；本验收文档后续提交本身仍须按精确新SHA另查四CI，不以旧CI替代。
