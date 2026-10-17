# 当前项目状态

更新：2026-10-16（America/New_York；执行主机 UTC 已为 2026-10-17）。当前阶段：**Phase 0 工程验收完成，等待用户第一章**。

## 本轮完成

- 全新 `/workspace/QimenLLM`，独立 Git main/Python 工程；没有读取或导入已有 Qimen 项目。
- 持久 AGENTS、项目使命、架构、资料/案例政策、模型路线、评估、设备方案、roadmap、决策和文献接收说明。
- SQLite schema v1、多书来源、不可变原文字节/修订、知识状态/条件/方法分歧、完整案例/事件/多盘/作者过程、家族级划分与冻结约束。
- 可运行 import-chapter / annotate / audit / backup；UTF-8、哈希、幂等、明确冲突、完整索引、来源追溯。
- 统一 QimenService、起盘/历法/模型未实现接口、条件选择与角色门槛、结构化事实引用检查、固定渲染与最后检查；CLI/API 同路，学习模式读取实际入库原文。
- 本地研究 WSGI API，无维护写路由；真实临时回环 HTTP 冒烟后关闭监听。
- doctor 设备脚本、跨设备版本/备份/私网 SSH 方案；离线构建 wheel 并安装到隔离目标目录，验证包内 migration 和安装后 init。

## 覆盖与实际结果

| 项目 | 本轮结果 |
|---|---|
| 已入库书 / 章 / 原文 | 0 / 0 / 0 |
| 已结构化知识 / 规则 | 0 / 0 |
| 已编译奇门规则 | 0 |
| 完整案例 / 事件 / 盘 / 训练任务 | 均为 0 |
| 当前数据版本 | empty-v1（操作链初始空版本） |
| 自动工程回归 | **51 项通过，0 失败**，云 Linux / Python 3.12.14 |
| 原文/数据库 audit | ok=true，errors=[]，所有领域计数为 0 |
| 真实 HTTP | /health=ok；/v1/ask=blocked；/v1/learn=awaiting_sources；均 HTTP 200 |
| compileall | 通过 |
| wheel 构建/隔离安装/init | 通过，未联网安装依赖 |
| 模型实验 / 训练 | 无 |
| 家庭 4090 / Mac 实测 | 未连接、未验证 |

执行命令和日志见根目录 README 以及 artifacts/validation.json、tests.log、audit.log、http-smoke.log、wheel-build.log、wheel-install.log。后者为本次交付产物，默认不进 Git。

归档保存在 artifacts/QimenLLM-Phase0.zip，并附 release.json、manifest.json、schema.sql 和 SHA256SUMS.txt。当前云账户无权创建聊天指定的 `/codex/.../output`，故无法生成该路径下的附件下载链接；不是测试或源码失败。

测试样本都是临时中性工程数据，不属于知识库，不是奇门专业正确性测试。结构通过、正常阻断与空流程响应不计成功断案；专业评分和现实准确率均未评估。

## 失败与修正

首轮 42 项中有 1 项错误：重复导入返回对象缺少 source_id，导致二次使用来源失败。已补齐同一来源 ID 并保持正文/版本幂等；随后回归及本轮最终 51 项全通过。没有未解决测试失败。

初始空库在 v1 定稿前经领域计数和版本数断言后重建；没有用户资料、旧库或冻结测试受影响。v1 定稿后不再改已应用 migration；下一次 schema 变化需新迁移。

## 尚未完成 / 不得宣称

没有专业基础事实库、历法节气/四柱算法、奇门排盘、真实用神规则、作者案例数据、自动自然语言理解、专业推理模型、自由中文事实校验、正式训练数据发布、微调、续断对话管理、教学课程、公众 Web/账户/TLS/限流、家庭训练远程接入或生产部署。Phase 0 的接口不等于这些能力已实现。

来源标注仍需 Codex 精读用户资料；复杂条件编译、图像原盘媒体导入、语义信息泄漏审计、正式训练任务哈希/发布清单、续断训练时间权限、自动异地备份和 checkpoint 恢复留待后续阶段具备材料后实现。

## 下一步及停止点

用户提供《神奇之门》第一章或完整知识点，章名及有的来源信息随文提供；多条输入标记本章结束。按 IMPORT_PROTOCOL 完整保存、哈希与来源、整块结构化、关联与条件审查，对实际可编译的内容加来源测试并更新本文件。本轮不执行任何后续文献导入、模型下载或训练。

## 后续指令：GitHub 新仓库与持续同步

用户已要求创建 QimenLLM，且每次数据更新同步 GitHub。已确认连接账号 turnupmason；目标私有 turnupmason/QimenLLM。已新增可恢复实际数据快照/恢复工具、CLI 更新后自动同步及远端 SHA 校验、持久规则和配置。schema v1 不变，不迁移或改写原文。

当前远端创建和首次上传仍未完成：现有连接器没有建库接口；gh 到 api.github.com 被云网络策略拒绝（Forbidden），本地策略仅允许 github.com 等域名而没有 api.github.com。必须通过云环境正式配置流程补充访问，再重试建库与 push。不得说“GitHub 已同步”。当前资料仍为 0，专业能力边界不变。

此次追加后的回归总数为 **59 项，全通过**（Phase 0 原有 51 项 + 快照/同步 8 项）。已验证真实原文字节及所有权威表导出/恢复后相同、数据不变文件不变、损坏快照拒绝、冻结分组保留、公开仓库不推送、远端 SHA 不符不报告成功，以及 CLI 上传失败仍保存本地资料。实际空库导出及原库 audit 均通过；真实 sync 尝试退出码2/pending，日志见 artifacts/sync-regression.log、github-sync-attempt.log 和 github-sync-validation.json。没有实际成功的远端写入，创建/首次 push 待访问恢复后完成。
