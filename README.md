# QimenLLM

古籍知识、确定性计算、完整案例与可替换语言模型结合的研究工程。**当前累计接收《神奇之门》十一份章级输入、43个完整故事/49事件/45已给原盘（本轮新增14个经营求财故事/18事件/16原盘）；支持符号计算、来源候选检查、案例阅读和原盘投影对照。独立公历起盘、正式用神激活、专业问事及模型训练尚未完成。**

用户已统一确认既往及未来提供的资料与历史事实，并声明已独立确认。维护导入默认confirmed，不再请求原文二次确认；确认依据与程序复算、模型评估分开记录，详见[现行来源政策](docs/KNOWLEDGE_POLICY.md)及[本轮工作就业报告](docs/ingestion/SHENQI_EMPLOYMENT.md)。

执行约束见 [AGENTS](AGENTS.md)，[完整用户总指令](docs/user_instructions/master_spec_2026-10-17.txt)，[当前进度](docs/STATUS.md)，[首章入库报告](docs/ingestion/SHENQI_CHAPTER01.md)、[第二份报告](docs/ingestion/SHENQI_CHAPTER02.md)、[第四、五章报告](docs/ingestion/SHENQI_CHAPTERS0405.md)、[应用概述报告](docs/ingestion/SHENQI_APPLICATION_OVERVIEW.md)、[疾病案例报告](docs/ingestion/SHENQI_HEALTH.md)、[婚恋案例报告](docs/ingestion/SHENQI_MARRIAGE.md)。没有读取或继承旧项目。

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

累计350个上下文块、39编译符号族、267来源/技术边界、16符号教学例；129当前候选对应136不可变历史条，正式角色rules仍0。29完整故事/28家族/31事件/29已给原盘、475记录/796证据；缺盘不造。作者已写反馈按用户声明确认；未记载结果不补。本轮5盘235字段比较，4盘一致、调动盘2处携干差异保留，训练任务0。217个旧有向参考键仍保留原句和条件，详见[覆盖](docs/KNOWLEDGE_COVERAGE.md)。

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

本轮《经营求财预测》接收与复算边界见[本章报告](docs/ingestion/SHENQI_BUSINESS.md)；重复导入脚本 `PYTHONPATH=src python3 scripts/import_shenqi_business.py`，本章所有真实原盘均通过 `case-chart` 同一服务读取（明确比较方法后才尝试对照）。
