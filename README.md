# QimenLLM

面向奇门遁甲专业知识、确定性工具、完整历史案例和可替换语言模型的全新工程。**当前仅 Phase 0：没有古籍知识、专业排盘、模型或断案能力。**

开发入口约束见 AGENTS.md；完整使命见 docs/PROJECT_CHARTER.md；进度见 docs/STATUS.md。本次没有读取或继承旧项目。

## 运行

要求 Python >=3.11、SQLite 支持 JSON/FTS5、Git。源码运行不需要安装第三方包：

```sh
cd QimenLLM
PYTHONPATH=src python3 -m qimenllm init
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m qimenllm audit
PYTHONPATH=src python3 -m qimenllm ask '我最近想换工作'
PYTHONPATH=src python3 -m qimenllm learn '九宫'
```

问事应返回 blocked；学习应返回 awaiting_sources。这是如实报告能力缺口，不能计为成功断案。打包安装可选 `python3 -m pip install -e .`，然后使用 qimenllm 命令；建议先建 venv。

## 最小研究 API

```sh
PYTHONPATH=src python3 -m qimenllm serve --port 8765
```

仅监听 127.0.0.1。GET /health；POST /v1/ask 的 JSON 为 `{"text":"问题"}`；POST /v1/learn 为 `{"term":"术语"}`。没有维护写入口，不是生产服务器。本轮没有留下常驻服务、创建网站或公开端口。

所有问事入口共用 QimenService.ask。测试用临时中性工程样本证明动态数据库规则确实到达模型适配器和校验器；不包含假装正式知识的奇门样本。真实算法和模型默认明确未实现/未配置。

## 目录

```text
QimenLLM/
├── AGENTS.md  README.md  pyproject.toml  Makefile
├── configs/                  # 开发与未来 GPU 配置模板，不启动训练
├── docs/                     # 章程、架构、政策、schema、设备、验收及状态
├── data/
│   ├── raw_books/            # 原文字节镜像，默认不进 Git
│   ├── structured/ rules/ cases/ provenance/ splits/
│   └── qimenllm.sqlite3      # 可重建的空领域库
├── src/qimenllm/
│   ├── calendar/ casting/ knowledge/ retrieval/ rules/ cases/
│   ├── models/ reasoning/ verification/ evaluation/
│   └── conversation/ learning/ api/
├── tests/                    # 自动回归；临时库，不污染 data/
├── scripts/doctor.py
├── frontend/                 # 仅接口接入说明
├── training/                 # 仅训练门槛说明
└── artifacts/                # 本轮验收产物，默认不进 Git
```

数据库：src/qimenllm/knowledge/migrations/001_initial.sql，补充约束在 knowledge/db.py。设计与关系图见 docs/SCHEMA.md；原文/案例接口见 docs/IMPORT_PROTOCOL.md、CASE_POLICY.md。

导入下一章前不用安装模型或连接 GPU。用户按完整章节提供材料后，Codex 将保存来源与哈希、审读标注、按来源支持编译并运行相应测试。本轮完成后等待《神奇之门》第一章。

## GitHub 持续同步

用户已要求每次源码和数据更新同步至私有 `turnupmason/QimenLLM`。import-chapter / annotate 会在本地保存成功后自动尝试导出、测试、commit、push 并核对远端。失败返回退出码 2 和 pending，原文仍已保存；不能把它当上传成功。源码以 Git 管理，实际文献/结构化库用可恢复快照进入 Git，不只上传计数或 schema。

```sh
PYTHONPATH=src python3 -m qimenllm export-snapshot
PYTHONPATH=src python3 -m qimenllm sync --message 'Update project and source data'
```

仓库已由用户创建，当前项目及实际空数据快照已上传到 https://github.com/turnupmason/QimenLLM 。当前会话若遇到命令行 GitHub API 的网络限制，Codex 使用 GitHub 连接器核实私有状态和权限，再以正常 Git HTTPS 上传并核对远端提交。具体操作、恢复命令和同步边界见 docs/GITHUB_SYNC.md。
