# Phase 0 实际交付报告

结论：基础工程已运行并验收；QimenLLM 尚无专业排盘、问事或模型能力。现在停止 Phase 0，等待《神奇之门》第一章。

本报告记录初次 Phase 0 验收时的结果；后续用户要求的私有 GitHub 仓库已于 2026-10-17 成功上传到 https://github.com/turnupmason/QimenLLM ，最新回归总数和同步状态见 STATUS / GITHUB_SYNC。

## 1. 项目与环境

实际目录：`/workspace/QimenLLM`。云 Linux x86_64，Python 3.12.14、Git 2.52.0，容器内存上限 8 GiB、约 2 CPU 配额。不是用户 Mac；RTX 4090 仅按用户说明记录，未连接。已有 Qimen 目录未读取或继承。详见 HARDWARE / ENVIRONMENT.json。

交付归档与报告位于本项目 artifacts/。聊天指定的 `/codex/.../output` 路径在当前云账户下不可创建（OS PermissionError），因此不提供无法访问的聊天附件链接；项目源码、空库、日志和归档均实际保存在工作区。

目录和启动命令见 README。Git 为本地 main，代理本地提交身份 Codex，无远程或 push；精确 commit 写入交付 manifest，亦可用 `git log -1` 查看。

## 2. schema 与来源工具

DDL 在 `src/qimenllm/knowledge/migrations/001_initial.sql`；追加不可变触发器在 `knowledge/db.py`。SCHEMA.md 提供表映射与关系图。交付包含实际初始化空库和完整 SQL schema 导出，源码 init 可重建。

已实现多书/章节/原文 BLOB 与哈希、来源/确认/版本、概念/方法/知识状态、条件规则/分歧、完整案例/事件/多盘/逐步过程、预测反馈续断类型、事件家族划分/冻结和候选任务时间权限。没有预填书名、符号属性、规则和案例。

import-chapter 保留收到的 UTF-8 原始字节和镜像；相同输入幂等，差异内容须明确下一修订；annotate 保存完整上下文定位与结构化 payload，默认不编译；audit 验证 FK、哈希、镜像、索引、来源和盘哈希；backup 使用 SQLite 一致性备份。

## 3. 运行链

CLI/API → QimenService.ask → 问事上下文 → 未实现起盘状态 → 实际 SQLite 检索 → 条件/方法 → 角色门槛。缺少资料/盘时返回 blocked，不调用模型。

中性临时库 + 注入适配器的测试继续走模型 → 结构化事实检查 → 固定渲染 → 最终检查，证明模块真实接线。没有实际专业模型、自然语言理解或推断算法，structurally_verified 不代表专业完成。学习入口仅返回实际原文，作者/系统/模型讲解字段分开。

## 4. 实际执行与验收

在项目目录运行：

```sh
PYTHONPATH=src python3 -m qimenllm init
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m qimenllm audit
PYTHONPATH=src python3 -m qimenllm ask '工程空流程检查'
PYTHONPATH=src python3 scripts/smoke_api.py
PYTHONPATH=src python3 -m compileall -q src scripts
python3 -m pip wheel --no-index --no-deps --no-build-isolation . --wheel-dir work/wheels
```

实际：**51 tests，全部通过，0 失败**；audit ok=true、errors=[]、领域表均 0；问事 blocked；回环 HTTP 三个接口均返回预期状态并关闭；compileall 通过；wheel 构建通过，并用 `pip install --no-index --no-deps --target work/wheel-install <wheel>` 隔离安装，包内 SQL 及独立 init 通过。测试日志随包提供。

测试覆盖原文不可变/长输入不截断/来源/重复与版本、FK/跨事件多盘、事前事后隔离、家族/冻结、模块协议、真实运行时查询和模型上下文、生成/证据错误分离、API 共用入口、学习检索和默认隐私 trace。未使用虚构奇门规则冒充专业测试。

CI 已配置 macOS/Linux 和 Python 3.11/3.12，但未在此轮运行远端 CI、Mac 或家庭 GPU，不宣称跨设备实际通过。首轮曾发现重复导入来源 ID 返回错误，已修复并回归；最终无失败。

## 5. 变更影响与未验证

全部源码/文档/测试均为新项目新增。运行时影响限定统一问事/学习入口与可信资料维护工具。初次 schema v1，开发期空库定稿后重建，不涉及旧资料迁移；今后有数据时必须版本化迁移。没有修改原书或冻结集，因为当前两者均不存在。

知识覆盖 0，案例覆盖 0，已编译专业规则 0，模型实验 0。专业计算、综合分析、自然语言解释、实际训练/恢复和公众产品均未完成；详细清单见 STATUS。家庭接入只完成可执行操作方案，没有开启公网或购买资源。

## 6. 下一阶段接收方法

直接提供《神奇之门》第一章完整原文，可分条并注明本章结束。附上实际有的章名/页码/图盘，原书没有的信息不强迫补充。Codex 按 IMPORT_PROTOCOL 保存、标注、编译有充分来源的确定规则、测试并更新覆盖。当前等待资料，不提前训练或导入任何其他材料。
