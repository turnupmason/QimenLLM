全书基础任务覆盖已更新为[book_preparation_v2](data/splits/book_preparation_v2.json)：98故事、127任务，82训练/21验证/20测试/4开发；其中32是本章方法任务，其余为带明确范围的原表/局部资料阅读。各故事的专业方法审读程度见[覆盖清单](data/provenance/book_training_coverage_v2.json)。

[钱物丢失章的Mac与4090试验入口](docs/METHOD_PILOT.md) · [本轮实际数据与工程验收](data/provenance/book_pilot_validation_v1.json)

当前建模进度：全书98完整故事/94家族已固定划分（65训练/15验证/15测试/3开发）；[全书数据准备清单](data/splits/book_preparation_v1.json)可从原快照重建。125条派生任务中，32为钱物丢失五类方法子任务、93为其他原盘字面读取，不能当作125独立案例或全书断案能力。正在按用户要求先Mac 27B基线→限定LoRA→同题验证，再决定4090系统训练。独立现实预测准确率尚无成绩。见[专业训练状态](docs/PROFESSIONAL_TRAINING.md)。

# QimenLLM

古籍知识、确定性计算、完整案例与可替换语言模型结合的研究工程。**当前累计接收《神奇之门》二十六份章级来源输入，98个完整故事/106事件/104来源盘记录。本轮附录三精校叙事与旧纪实一致，另有所供九宫文字重排表，已逐宫保存并关联原故事、两目标事件和30条时序记录。旧碎片、初次否定、续断及后来按语保持，不重复计案盘。独立公历起盘、正式用神、专业问事及模型训练尚未完成。**

本地研究进度：用户宣布本书资料已提供完毕，授权按总指令开始模型研究，先使用M2/24GB。现已接通本地MLX候选推理和受控开发评估；正式完整条件规则、盲测与训练仍受阶段门槛约束。当前仓库公开是用户主动设置，本轮明确仅本地，不同步GitHub。见[建模开发记录](docs/MODEL_BASELINE.md)。

用户已统一确认既往及未来提供的资料与历史事实，并声明已独立确认。维护导入默认confirmed，不再请求原文二次确认；确认依据与程序复算、模型评估分开记录，详见[现行来源政策](docs/KNOWLEDGE_POLICY.md)及[附录三精校与重排表报告](docs/ingestion/SHENQI_DEMO.md)及[附录一精校来源报告](docs/ingestion/SHENQI_LEARNING.md)及[附录二精校来源报告](docs/ingestion/SHENQI_BIOGRAPHY.md)及[附录报告](docs/ingestion/SHENQI_APPENDIX.md)及[后记报告](docs/ingestion/SHENQI_AFTERWORD.md)及[准确率评估知识报告](docs/ingestion/SHENQI_ACCURACY.md)及[人生机遇报告](docs/ingestion/SHENQI_LIFE.md)及[地理环境报告](docs/ingestion/SHENQI_GEOGRAPHY.md)及[天时气象报告](docs/ingestion/SHENQI_WEATHER.md)及[体育竞赛报告](docs/ingestion/SHENQI_SPORTS.md)及[官司诉讼报告](docs/ingestion/SHENQI_LITIGATION.md)及[刑事案件报告](docs/ingestion/SHENQI_CRIMINAL.md)及[钱物丢失报告](docs/ingestion/SHENQI_LOST.md)及[行人走失报告](docs/ingestion/SHENQI_MISSING.md)及[出行出国报告](docs/ingestion/SHENQI_TRAVEL.md)及[经营求财报告](docs/ingestion/SHENQI_BUSINESS.md)及[上一轮工作就业报告](docs/ingestion/SHENQI_EMPLOYMENT.md)。

执行约束见 [AGENTS](AGENTS.md)，[原始用户总指令](docs/user_instructions/master_spec_2026-10-17.txt)，[本次重申总指令](docs/user_instructions/master_spec_reaffirmed_2026-10-17.txt)，[当前进度](docs/STATUS.md)，[首章入库报告](docs/ingestion/SHENQI_CHAPTER01.md)、[第二份报告](docs/ingestion/SHENQI_CHAPTER02.md)、[第四、五章报告](docs/ingestion/SHENQI_CHAPTERS0405.md)、[应用概述报告](docs/ingestion/SHENQI_APPLICATION_OVERVIEW.md)、[疾病案例报告](docs/ingestion/SHENQI_HEALTH.md)、[婚恋案例报告](docs/ingestion/SHENQI_MARRIAGE.md)。没有读取或继承旧项目。

## 运行与恢复

Python >=3.11、SQLite支持JSON/FTS5、Git。源码运行无第三方依赖。在仓库根目录执行：

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
# 全新设备从实际快照恢复；目标库必须不存在
PYTHONPATH=src python3 -m qimenllm restore-snapshot data/snapshots/current data/qimenllm.sqlite3
PYTHONPATH=src python3 -m qimenllm audit
PYTHONPATH=src python3 -m qimenllm learn '符头'
PYTHONPATH=src python3 -m qimenllm calculate earth_plate --args '{"dun":"阳遁","bureau":3}'
PYTHONPATH=src python3 -m qimenllm calculate bureau --args '{"solar_term":"冬至","day_ganzhi":"甲子","method":"chaibu"}'
PYTHONPATH=src python3 -m qimenllm calculate hour_ganzhi --args '{"day_stem":"丙","hour_branch":"戌"}'
PYTHONPATH=src python3 -m qimenllm calculate symbolic_chart --args '{"dun":"阴遁","bureau":8,"hour_ganzhi":"戊戌","method":"shenqi_ch2_paper_v1"}'
PYTHONPATH=src python3 -m qimenllm calculate star_month_strength --args '{"star":"天蓬星","month_branch":"寅","method":"shenqi_ch4_star_month_v1"}'
PYTHONPATH=src python3 -m qimenllm reference stem_responses --filters '{"heaven_stem":"戊","earth_stem":"丙"}'
PYTHONPATH=src python3 -m qimenllm calculate inner_outer --args '{"dun":"阳遁","palace":1}'
PYTHONPATH=src python3 -m qimenllm rule-candidates --domain health --context '{"target_relationship":"self"}'
PYTHONPATH=src python3 -m qimenllm case case-b3dd6097c4186c79d3b834cef63cad5cf7f195da0d7946de4495c1184b3e6459 --view before_prediction
PYTHONPATH=src python3 -m qimenllm cases --chapter-key health-prediction
PYTHONPATH=src python3 -m qimenllm cases --chapter-key marriage-prediction
PYTHONPATH=src python3 -m qimenllm cases --chapter-key work-employment
# 用目录返回的实际case_id/chart_id读取；明确比较方法才进行符号对照
# PYTHONPATH=src python3 -m qimenllm case-chart CASE_ID CHART_ID --comparison-method shenqi_ch2_paper_v1
PYTHONPATH=src python3 -m qimenllm ask '我最近想换工作'
```

学习返回原文和独立标记的整理说明。计算结果带SHA/出处，调用者明确给节气和干支等符号输入；尚不从公历自动确定。问事仍blocked，不能算成功断案。init仅建新空库；已有库不要删除重建。可选venv后安装 `python3 -m pip install -e .`。

## 研究API

```sh
PYTHONPATH=src python3 -m qimenllm serve --port 8765
PYTHONPATH=src python3 scripts/smoke_api.py --chapter01 --chapter02 --chapters0405 --application-overview --health --marriage --pregnancy --exam --employment
```

只监听127.0.0.1。GET /health；POST /v1/ask：`{"text":"问题"}`；/v1/learn：`{"term":"符头"}`；/v1/calculate：`{"operation":"earth_plate","args":{"dun":"阳遁","bureau":3}}`。POST /v1/reference为 `{"family":"stem_responses","filters":{"heaven_stem":"戊","earth_stem":"丙"}}`。POST /v1/rule-candidates为 `{"context":{"target_relationship":"self"},"domain":"health"}`；POST /v1/case为 `{"case_id":"已导入case_id","view":"before_prediction"}` 或full。候选检查不是专业激活，事前视图不含结果。POST /v1/cases为 `{"chapter_key":"health-prediction"}`，/v1/case-chart为 `{"case_id":"实际ID","chart_id":"实际ID","comparison_method":"shenqi_ch2_paper_v1"}`，比较方法可省略，仅读原盘。婚恋目录用chapter_key=marriage-prediction；事件可能未提供盘，须按events[].chart_ids选择。不把源表投影/对照当临床或专业问事结论。没有维护写路由，不是公众服务器。

问事只通过QimenService.ask，教学计算通过QimenService.calculate；CLI/API/集成测试共用核心模块，实际运行查询数据库。符号转盘可生成同一不可变Chart，标symbolic_verified而非engine_verified；不靠模型记忆补全。显式提供casting_method及context条件时ask也调用相同计算器，但仍不启用专业断案。

## 数据与目录

src/qimenllm/按knowledge/casting/retrieval/rules/cases/reasoning/models/verification/learning/api分层。docs保存持久规范，tests用临时库，scripts提供诊断、首章重放和HTTP检查；frontend、training目前仅预留集成说明。

data/qimenllm.sqlite3是本地运行库，raw_books是原字节镜像，二者不直接入Git。**实际原文字节与全部权威表**保存在data/snapshots/current，可恢复；整理和来源测试在data/structured/shenqi，来源与验收在data/provenance。schema v1见src/qimenllm/knowledge/migrations/001_initial.sql及[SCHEMA](docs/SCHEMA.md)。

累计554个上下文块（含来源对应及所供重排表）、39编译符号族、371来源/技术边界、16符号教学例；196当前条件候选对应203不可变历史条，正式角色rules仍0。98完整故事/94家族/106事件/104来源盘记录、1579记录/1902证据；缺盘不造。作者明确反馈按用户声明确认；未载结局不补。本轮5张人生机遇原盘45宫逐字读取，已知结果后验测、死亡年份错断及初五后验应期隔离；此前2张地理环境原盘18宫逐字读取，先考题无盘不造，两处墓地同家族且反馈范围有限；此前5张天气原盘45宫逐字读取，与体育章共局一案共用家族、辅庚/铺庚原文并存；此前7张体育竞赛原盘63宫逐字读取，铺庚星名保持未知，第六例错断保留；此前6张官司诉讼原盘54宫逐字读取并隔离后置解释；此前6张刑事案件原盘已逐盘读取，含同一银行案两种方法且后验比较隔离；钱物丢失8张原盘保留；行人走失11张四行盘保留；出行出国7张框线原盘保留；经营求财16张原表已逐盘读取，原书特殊中五“禽己”保留字面前缀；上一轮工作调动盘仍保留2处程序携干差异。训练任务0，旧217有向参考键仍保留原句和条件，详见[覆盖](docs/KNOWLEDGE_COVERAGE.md)。

## 每次更新同步GitHub

用户已长期授权同步至私有 https://github.com/turnupmason/QimenLLM 。实际库快照随代码版本化。导入/标注CLI和首章脚本默认尝试审计、导出、测试、commit/push并核对远端。失败pending/退出码2，原文仍保存。

```sh
PYTHONPATH=src python3 scripts/import_shenqi_chapter01.py
PYTHONPATH=src python3 scripts/import_shenqi_chapter02.py
PYTHONPATH=src python3 scripts/import_shenqi_chapters0405.py
PYTHONPATH=src python3 scripts/import_shenqi_application_overview.py
PYTHONPATH=src python3 scripts/import_shenqi_health.py
PYTHONPATH=src python3 scripts/import_shenqi_marriage.py
PYTHONPATH=src python3 scripts/import_shenqi_pregnancy.py
PYTHONPATH=src python3 scripts/import_shenqi_exam.py
PYTHONPATH=src python3 scripts/import_shenqi_employment.py
PYTHONPATH=src python3 -m qimenllm export-snapshot
PYTHONPATH=src python3 -m qimenllm sync --message 'Update project and source data'
```

各章重放脚本只接受对应已给原文的确切哈希（本次内联聊天另验父消息及正文切片），重放不重复入库；新章/修订另走导入。当前云会话若命令行API受限，Codex通过连接器核实私有状态，再正常Git HTTPS推送并核对远端；pending不算完成。维护和恢复见[GITHUB_SYNC](docs/GITHUB_SYNC.md)、[IMPORT_PROTOCOL](docs/IMPORT_PROTOCOL.md)。不提交密钥、私人问事或模型权重，不公开分发原书。

本轮《经营求财预测》接收与复算边界见[本章报告](docs/ingestion/SHENQI_BUSINESS.md)；重复导入脚本 `PYTHONPATH=src python3 scripts/import_shenqi_business.py
PYTHONPATH=src python3 scripts/import_shenqi_travel.py
PYTHONPATH=src python3 scripts/import_shenqi_missing.py
PYTHONPATH=src python3 scripts/import_shenqi_lost.py
PYTHONPATH=src python3 scripts/import_shenqi_criminal.py
PYTHONPATH=src python3 scripts/import_shenqi_litigation.py
PYTHONPATH=src python3 scripts/import_shenqi_sports.py
PYTHONPATH=src python3 scripts/import_shenqi_weather.py
PYTHONPATH=src python3 scripts/import_shenqi_geography.py
PYTHONPATH=src python3 scripts/import_shenqi_life.py`，本章所有真实原盘均通过 `case-chart` 同一服务读取（明确比较方法后才尝试对照）。

准确率评估方法论知识可直接使用现有学习入口读取：

```sh
PYTHONPATH=src python3 -m qimenllm learn '百分之七八十'
PYTHONPATH=src python3 -m qimenllm reference accuracy_method_disagreements_reference --filters '{}'
PYTHONPATH=src python3 scripts/import_shenqi_accuracy.py
```

作者的百分之七八十属于原书经验表述，两个分母/程度口径均保留；未提供实际百人样本或逐案评分表，不写成项目实测准确率。批评只报成功、承认错断、略去完全失败案例的三个原书段落同组保存。方法分歧只作来源参考，不更换现有算法默认值；本轮未增加案例、盘、正式规则或训练任务。

后记同样已进入现有学习接口，`PYTHONPATH=src python3 -m qimenllm learn '极其初步的'` 可读取研究纲领连同“不成熟、欢迎批评”的原段；`reference afterword_science_technology_reference --filters '{}'` 可读自然哲学、报刊转引与理论技术论述。重放使用 `PYTHONPATH=src python3 scripts/import_shenqi_afterword.py`。未增加案例或盘，未由感谢实例提供者猜测逐案归属，也未由收到后记宣告全书已经收齐。

本轮附录包含《学习奇门遁甲并不难》（张志春）、《从编辑、作家到易学专家》（宛北布衣）和现场表演纪实（杜新会）。前带准确率评估和后记排版变体，已关联旧源；三则学员摘要已关联求财、就业、钱物丢失旧案，未重复增加案例。现场纪实保留官讼初断被否定、改问本人后续断、会后信件和2000年出版按语。旧复合附件盘面列位缺失，原文/制表符/CRLF完整保存，旧碎片的`case-chart`仍返回not_covered；本次附录三另有所供重排表，通过`demo_clean_palaces_reference`逐宫读取，原片段不覆盖。

```sh
PYTHONPATH=src python3 -m qimenllm learn '五十分钟'
PYTHONPATH=src python3 -m qimenllm reference appendix_casting_convention_reference --filters '{}'
PYTHONPATH=src python3 -m qimenllm cases --chapter-key appendix-bundle
PYTHONPATH=src python3 scripts/import_shenqi_appendix.py
```

本篇“最多五十分钟”明确以蔡敦祺已有其他奇门基础为条件，教学目标和作者的准确率比较保留归属；不自动改变旧方法默认值或升级实测成绩。

附录二精校文件已独立保存原字节并关联旧复合源；去空白及旧页眉后2478字符完全一致，末句“代表人物之”断尾仍按源保留。`PYTHONPATH=src python3 -m qimenllm reference biography_clean_source_reference --filters '{}'` 可读整篇新来源，`learn 精校来源` 可查与旧5组语境的关系。重放使用 `PYTHONPATH=src python3 scripts/import_shenqi_biography.py`。来源接收数增加不代表新增一篇独立理论或实测样本。

附录一精校来源与旧复合源的总题及第一篇去空白/明确页眉后3988字符一致。原14语境、卢圣湘抽奖/尚瓴吉选举/赵国葆身份证三个旧案保持关联，不复制案盘；四难、三原则目标、作者取法和五十分钟已有基础的条件照源保留。`reference learning_clean_source_reference --filters '{}'` 可读新整篇，重放使用 `PYTHONPATH=src python3 scripts/import_shenqi_learning.py`。附录一接收排序26与附录二排序25分别保存，旧键、旧源和方法默认不变。

附录三文件明确标注“九宫盘面（根据提供的文字原盘重排）”。新表的36个字面单元有独立手抄gold，震三生乙、中宫原文壬、乾六壬惊丙均按所供字面保存。它是已有同盘的另一份用户重排表示，不是新增历史盘或已完成复算的原图。

```sh
PYTHONPATH=src python3 -m qimenllm reference demo_clean_palaces_reference --filters '{}'
PYTHONPATH=src python3 -m qimenllm reference demo_clean_palaces_reference --filters '{"palace":5}'
PYTHONPATH=src python3 -m qimenllm learn '附录三精校来源'
PYTHONPATH=src python3 scripts/import_shenqi_demo.py
```

叙事4387字符与旧源相同，30条源记录逐条对照。没有重复导入case/event/chart/候选，旧case-chart碎片覆盖状态不变，原案首次视图仍不透露后知反馈与盘。
