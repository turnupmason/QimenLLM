# QimenLLM

古籍知识、确定性计算、完整案例与可替换语言模型结合的研究工程。**当前Phase 1：已接收《神奇之门》“时家奇门演局的规律”七节，支持有来源的基础教学计算与原文检索；完整排盘、专业问事和模型训练尚未完成。**

执行约束见 [AGENTS](AGENTS.md)，[完整用户总指令](docs/user_instructions/master_spec_2026-10-17.txt)，[当前进度](docs/STATUS.md)，[首章入库报告](docs/ingestion/SHENQI_CHAPTER01.md)。没有读取或继承旧项目。

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
PYTHONPATH=src python3 -m qimenllm ask '我最近想换工作'
```

学习返回原文和独立标记的整理说明。计算结果带SHA/出处，调用者明确给节气和干支等符号输入；尚不从公历自动确定。问事仍blocked，不能算成功断案。init仅建新空库；已有库不要删除重建。可选venv后安装 `python3 -m pip install -e .`。

## 研究API

```sh
PYTHONPATH=src python3 -m qimenllm serve --port 8765
PYTHONPATH=src python3 scripts/smoke_api.py --chapter01
```

只监听127.0.0.1。GET /health；POST /v1/ask：`{"text":"问题"}`；/v1/learn：`{"term":"符头"}`；/v1/calculate：`{"operation":"earth_plate","args":{"dun":"阳遁","bureau":3}}`。没有维护写路由，不是公众服务器。

问事只通过QimenService.ask，教学计算通过QimenService.calculate；CLI/API/集成测试共用核心模块，实际运行查询数据库。教学对象不是完整Chart，不靠模型记忆补全。

## 数据与目录

src/qimenllm/按knowledge/casting/retrieval/rules/cases/reasoning/models/verification/learning/api分层。docs保存持久规范，tests用临时库，scripts提供诊断、首章重放和HTTP检查；frontend、training目前仅预留集成说明。

data/qimenllm.sqlite3是本地运行库，raw_books是原字节镜像，二者不直接入Git。**实际原文字节与全部权威表**保存在data/snapshots/current，可恢复；整理和来源测试在data/structured/shenqi，来源与验收在data/provenance。schema v1见src/qimenllm/knowledge/migrations/001_initial.sql及[SCHEMA](docs/SCHEMA.md)。

首章40个上下文块、12编译族、21疑点/边界、11演算教学例；历史问事案例、用神规则、训练任务仍0，详见[覆盖](docs/KNOWLEDGE_COVERAGE.md)。

## 每次更新同步GitHub

用户已长期授权同步至私有 https://github.com/turnupmason/QimenLLM 。实际库快照随代码版本化。导入/标注CLI和首章脚本默认尝试审计、导出、测试、commit/push并核对远端。失败pending/退出码2，原文仍保存。

```sh
PYTHONPATH=src python3 scripts/import_shenqi_chapter01.py
PYTHONPATH=src python3 -m qimenllm export-snapshot
PYTHONPATH=src python3 -m qimenllm sync --message 'Update project and source data'
```

首章脚本只接受本次确切哈希，重放不重复入库；新章/修订另走导入。当前云会话若命令行API受限，Codex通过连接器核实私有状态，再正常Git HTTPS推送并核对远端；pending不算完成。维护和恢复见[GITHUB_SYNC](docs/GITHUB_SYNC.md)、[IMPORT_PROTOCOL](docs/IMPORT_PROTOCOL.md)。不提交密钥、私人问事或模型权重，不公开分发原书。
