# GitHub 更新与可恢复数据

## 用户授权与当前状态

用户已要求新建 QimenLLM，并在每次数据更新时同步 GitHub。目标为已连接账号 `turnupmason` 下的私有 `turnupmason/QimenLLM`，main 分支；无需每次重新询问是否上传。

2026-10-17，用户已创建并提供 https://github.com/turnupmason/QimenLLM 。GitHub 连接器已确认 owner=turnupmason、visibility=private、push=true，随后通过正常 Git HTTPS 成功推送 main；初次远端提交为 f2a7e699ea732d4d53e65e08cd4aa07a56c56f7f，保留此前本地历史。最终文档更新也要再次 push 并核对远端，最新结果在 work/github-sync.json。

当前会话的命令行 api.github.com 仍受旧网络策略限制；github.com 的正常 Git 传输可用，GitHub 连接器读取元数据也可用。后续不得重复建库或绕过网络策略，采用下面的连接器核验流程完成同步。若未来运行环境已允许 GitHub API，可直接运行：

```sh
PYTHONPATH=src python3 -m qimenllm sync --message 'Update QimenLLM project and source data'
```

本仓库 origin 为 https://github.com/turnupmason/QimenLLM.git；本地凭据 helper 仅引用 gh auth git-credential，未保存或输出 token。不得索取或在聊天粘贴 token。

## 每次更新的正式流程

1. 原文/结构化数据事务提交，不丢失本地资料。
2. `export_snapshot` 审计并从同一个 SQLite 读事务导出全部权威表，保存真实原文字节与来源，不导出临时检索索引。
3. 验证 origin 与目标一致，并通过 GitHub API 确认目标仍为私有；网络/可见性验证失败时不 stage/push 数据。
4. 用当前 src 跑自动回归，然后 stage 已跟踪变更及受控项目目录；提交源码、文档、数据快照。
5. 正常 git push，不 force。再用 git ls-remote 核对 main 等于本地 HEAD，才生成 synced 回执。回执在 work/github-sync.json，不将授权或凭据入 Git。

CLI import-chapter / annotate 自动调用此流程。网络、权限或 push 失败：输出 pending、退出码2，明确本地资料已保存；恢复后运行 sync，不重复编造或覆盖资料。低层 Python 导入接口供事务/测试使用，不隐式联网；Codex 直接用该接口维护后仍须完成 sync 才报告整个更新任务完成。

本工具同步的是已完成的本次更新，不是无人值守文件监控服务。没有运行常驻 watcher、cron 或跨会话后台作业。人工直接修改源码后也必须调用 sync，不能依赖只读 GitHub Actions 把本地文件自动推上去。

## 当前会话的连接器核验流程

若 CLI 在私有状态检查处因 api.github.com 返回 pending，Codex 应使用可用的 GitHub 连接器 get_repo，再次核实目标的所有者、private 状态与 push 权限。核实失败则停止；成功后沿用 export_snapshot、回归和受控 staging/commit，使用正常 Git HTTPS 推送，不修改策略、不 force。实际已验证可行的命令：

```sh
git config --local credential.https://github.com.helper '!gh auth git-credential'
GIT_TERMINAL_PROMPT=0 git push --set-upstream origin main
GIT_TERMINAL_PROMPT=0 git ls-remote origin refs/heads/main
git rev-parse HEAD
```

核对本地 HEAD 与远端 main 一致，再以连接器读取关键文件校验。完成后记录 repository、commit、data_version、snapshot_manifest_sha256 和 transport=git_https_after_connector_visibility_check 的本地回执；只有这些实际步骤成功才向用户报告已同步。这个维护工作流由 Codex 执行，CLI 不会自行伪造连接器核验或把 pending 改为成功。

## Git 里的实际数据

`data/snapshots/current/manifest.json` 保存格式、迁移哈希、数据版本、表数与每文件哈希。每权威表一个 canonical JSONL，包含完整来源、知识、案例、规则条件、家族分组及任务记录。原始 BLOB 的真实字节在 raw/<sha256>.bin，JSONL 引用该文件；不是只上传哈希。搜索索引从原文重建。

源 SQLite 和 raw_books 镜像仍可在本地工作，避免每次把易变二进制 SQLite 提交 Git。数据版本/来源确认历史的插入顺序保留，恢复后不改变 latest review。快照无机器路径和生成时间，数据不变则文件不变。每次新数据的历史由 Git commit 保留。

私有项目备份包含用户授权的古籍文本及结构化资料，不代表获得公开全文或商业训练权。公众问事、个人隐私数据、环境凭据、模型权重、训练 checkpoint 和本地 logs/ZIP 不提交。超大书图或数据增长触及 Git 存储限制时，先设计 LFS/外置私有对象存储及可恢复 manifest，再迁移；不静默漏传数据。

## 恢复

拉取私有仓库源码与快照，在同一个 schema 版本环境执行：

```sh
PYTHONPATH=src python3 -m qimenllm --raw-dir work/restored-raw restore-snapshot \
  data/snapshots/current work/restored.sqlite3
PYTHONPATH=src python3 -m qimenllm --db work/restored.sqlite3 --raw-dir work/restored-raw audit
```

只恢复到新 DB，不覆盖现有数据。先校验每个文件哈希与 schema，再重建 FK、来源、索引和冻结分组，审计通过后才发布目标文件。这个可恢复的数据备份不等于正式训练集发布；训练语义审核与冻结评估门槛保持原有要求。
