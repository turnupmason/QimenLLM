# 双设备开发与训练方案

## 本轮实测环境

本次运行在云 Linux 容器 `/workspace`，不是用户 Mac。完整原始探测在 `docs/ENVIRONMENT.json`。

| 项目 | 观察结果 |
|---|---|
| OS / 架构 | Linux kernel 6.18.55, x86_64, glibc 2.41 |
| CPU 型号 | AMD EPYC 9V74（宿主可见型号） |
| CPU | Python 可见 3 个；cgroup quota 200000/100000，约 2 CPU |
| 内存 | 宿主可见约 9.73 GiB；cgroup 上限 8 GiB |
| Python | 3.12.14 |
| Git | 2.52.0 |
| 文件系统 | overlay，约 31.45 GiB 总量（随会话变化） |
| GPU | 未找到 nvidia-smi；未运行 CUDA、未探测家庭 GPU |
| 工作区 | `/workspace/QimenLLM`，全新建立；已有 `/workspace/Qimen` 未读取或继承 |

用户报告：MacBook Air M2 / 24GB 统一内存；家庭 NVIDIA RTX 4090 / 24GB。以上是用户已知设备信息，不是本轮连接实测。家庭 OS、CPU、RAM、磁盘、驱动、CUDA、SSH地址及网络均未确定。

## 设备职责

| 设备/角色 | 用途 | 现状 |
|---|---|---|
| Mac 开发 | Codex、文献、数据库审查、轻测试、Web调试、小模型 | 未在本轮登录实测 |
| 家庭 GPU 训练 | CUDA 实验、基线、QLoRA/LoRA、checkpoint | 未连接、未配置远程网络 |
| 推理服务 | 开发期本地或经鉴权远程模型网关 | 尚未配置 |
| 公众服务器 | 账户、API、限流、生产推理调度及监控 | 尚未部署/购买 |

## 可执行的本地准备

Mac 或 Linux 在项目目录执行，不需要下载模型：

```sh
mkdir -p work
python3 scripts/doctor.py > work/device-report.json
python3 -m venv .venv
. .venv/bin/activate
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m qimenllm init
```

报告含设备路径，不上传公众。
Python >=3.11；若打包安装，使用独立 venv 和 `python -m pip install -e .`，只安装工程构建工具。当前源码运行无第三方运行依赖。Mac/CUDA 使用不同 venv，不同步 site-packages。

家庭 Windows 先确认版本、磁盘与 GPU 驱动；评估 WSL2 Linux CUDA，不能照搬 Linux 驱动安装命令。家庭 Linux 直接检测 nvidia-smi。后续在本人机器上记录 `nvidia-smi`、`python -m torch.utils.collect_env`，测试 CUDA tensor 与显存，选择兼容组合后才锁依赖。Phase 0 无安装或重启系统命令。

## Git 与数据同步

两机使用同一源码 commit/分支。当前 Git 仅本地，无远程仓库、无 push。未来使用用户选择的私有 Git 远程；模型、用户原文和数据库不无计划推送 Git。

SQLite 不通过网盘同时打开，也不让两机同时写同一 DB。文献维护端作为当前写入主端；训练只读发布快照。先执行：

```sh
mkdir -p artifacts/snapshots
PYTHONPATH=src python3 -m qimenllm audit
PYTHONPATH=src python3 -m qimenllm backup artifacts/snapshots/release-001.sqlite3
git rev-parse HEAD
```

连同 raw_books 镜像、来源清单、数据版本、冻结家族分组和快照 SHA-256 同步到 GPU。DB 本身也含原始字节。用 SHA-256 检查传输后文件；从备份复制到新路径后先 audit，再启动训练。原库不覆盖。家庭训练机不直接写主文献库。

## 远程接入，待用户实际配置

可选私有网络内 SSH 或 Tailscale + SSH；需要确定设备 OS、主机名、账户和授权后才执行接入。没有为本项目安装 VPN、添加防火墙规则或开放公网监听。

建立后采用 SSH key、主机指纹核对、最小权限账户和 VPN ACL。下面为参数化操作模板，不能把示例当已可连接地址：

```sh
ssh -o StrictHostKeyChecking=yes GPU_HOST_ALIAS
rsync -av --checksum -e ssh artifacts/snapshots/ GPU_HOST_ALIAS:QimenLLM-data/snapshots/
ssh -N -L 8765:127.0.0.1:8765 GPU_HOST_ALIAS
```

GPU_HOST_ALIAS 必须由用户在 SSH config 中实际设置。密钥不提交 Git，不禁用主机校验。模型开发服务在远端只绑定回环，通过加密隧道访问；仅隧道不替代未来应用鉴权。

## 运行、恢复和备份

未来经评测的训练命令由 experiment manifest 驱动，在 tmux/任务管理服务运行，不在 Mac 断线后丢失。远程以 `ssh GPU_HOST_ALIAS nvidia-smi`、tail 训练日志和 TensorBoard 隧道查看，敏感输入不写日志。checkpoint 包含 adapter/模型身份、优化器、scheduler、RNG、步数、数据版本和采样游标；至少做一次实际中断恢复测试后才声称支持训练恢复。

源码 Git + 数据只读快照 + 原文镜像 + 外置模型产物分别备份，至少设备外一份加密副本，记录哈希和恢复演练。Phase 0 只实现 SQLite 一致性 backup，自动异地备份和训练恢复尚未实现。

公众负载未来以延迟/吞吐/成本实测选择家用、独立推理机或云 GPU，不承诺 4090 能服务全部用户，也不提前消费云资源。
