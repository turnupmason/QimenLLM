# GitHub 更新与可恢复数据

## 用户授权与当前阻断

用户已要求新建 QimenLLM，并在每次数据更新时同步 GitHub。目标为已连接账号 `turnupmason` 下的私有 `turnupmason/QimenLLM`，main 分支；无需每次重新询问是否上传。

当前仓库尚未由本代理创建或上传。GitHub 连接器已确认账号；get_repo 对目标返回 404（不存在或当前连接无访问权）。现有连接器没有 create-repository 功能。云端 gh 可用且检测到配置的认证，但访问 `https://api.github.com/user` 和 GraphQL 均返回 Forbidden；实际网络允许列表含 github.com，不含 api.github.com。不得编辑策略文件或绕过代理。必须通过云环境的正式配置流程允许 api.github.com 后再验证授权，才能尝试建库。

配置好访问后执行：

```sh
gh api user --jq .login
gh repo create turnupmason/QimenLLM --private --description 'Source-grounded QimenLLM research and product'
PYTHONPATH=src python3 -m qimenllm sync --message 'Publish QimenLLM foundation and data snapshot'
```

若建库提示同名存在，先读 metadata 核实所有者、私有状态与已有内容，不覆盖、不 force-push。Git origin 已按用户目标设置，不意味着远端已存在。创建后如 GitHub App 仅授权选定仓库，还需把新仓库加入该连接的访问范围。不得索取或在聊天粘贴 token。

## 每次更新的正式流程

1. 原文/结构化数据事务提交，不丢失本地资料。
2. `export_snapshot` 审计并从同一个 SQLite 读事务导出全部权威表，保存真实原文字节与来源，不导出临时检索索引。
3. 验证 origin 与目标一致，并通过 GitHub API 确认目标仍为私有；网络/可见性验证失败时不 stage/push 数据。
4. 用当前 src 跑自动回归，然后 stage 已跟踪变更及受控项目目录；提交源码、文档、数据快照。
5. 正常 git push，不 force。再用 git ls-remote 核对 main 等于本地 HEAD，才生成 synced 回执。回执在 work/github-sync.json，不将授权或凭据入 Git。

CLI import-chapter / annotate 自动调用此流程。网络、权限或 push 失败：输出 pending、退出码2，明确本地资料已保存；恢复后运行 sync，不重复编造或覆盖资料。低层 Python 导入接口供事务/测试使用，不隐式联网；Codex 直接用该接口维护后仍须完成 sync 才报告整个更新任务完成。

本工具同步的是已完成的本次更新，不是无人值守文件监控服务。没有运行常驻 watcher、cron 或跨会话后台作业。人工直接修改源码后也必须调用 sync，不能依赖只读 GitHub Actions 把本地文件自动推上去。

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
