# Mac 上的 Qwen3.8-27B 工程研究（历史记录）

当前修订：用户不再要求50个epoch，Mac改为优先准备数据，用户可在RTX4090训练。本文的49首轮作者原文复现任务、最后一层rank4配置与1650步方案仅保留为已撤销的工程试验记录，不是专业训练方案。旧启动器已退役，停止时0正式epoch/0更新。用户总结、现行数据门槛与验收见PROFESSIONAL_TRAINING.md。下面关于准备/执行的旧表述不代表仍在运行。

此前用户目标为 Qwen3.8-27B + LoRA/QLoRA，50 个完整 epoch，先 Mac，本轮不推送。用户澄清尚未下载，只希望在终端通过 Hugging Face 调用；程序已完成首次缓存和哈希核对。

## 已实际验证

固定官方 revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` 与 MLX 4bit revision `10c35caafbb80f7dc6a7a432cdd11af10a6d4818`，Apache-2.0。15 个本地文件共 16,081,490,933 字节，LFS 文件逐项对照远端 SHA-256，其余文件保存实际本地哈希。见 data/provenance/qwen38_27b_download_v1.json。未使用旧项目适配器或训练资料。

M2 / 24 GiB / MLX 0.32.4、mlx-lm 0.32.2：加载 14.77 秒，模型活跃内存 15,133,588,488 字节，实际生成“好”。最终全注意力层的 q_proj / v_proj、rank=4 / MLX scale=2 / dropout=0，94,208 可训练参数；64/256/512 token 中性环境样本反传通过，峰值最高 16,121,817,602 字节。保存并重开 4 个 adapter 张量和 Adam 状态，step=1 一致。它只验证运行环境，不计正式训练遍数；实际域样本恢复后继续更新的一致性由训练程序另测。

## 首轮派生训练资料的范围

完整书、98 故事、106 事件、全部原盘和续断仍在原库，原始字节、schema、ordered 时序状态、旧 gold 与快照均不修改。不能为了导出而把旧事件改为 verified。

data/provenance/author_initial_turn_review_v2.json 对 96 个初始候选逐项记录当前导出或暂缓决定；53 项获本次首轮语义权限，另有 4 项原盘在原文排在首断之后，本次保守拒绝自动提前。最终 49 个首轮子任务，33 train / 9 validation / 6 test / 1 development。它不是全书全部分析或完整专业问事发布，不表示其他资料无效。原库 training_tasks/dataset_releases 表仍为 0；本轮使用独立派生文件 release，明确与数据库计数分开。

只开放原文明确的事前对话和早于首断的原盘；不传案例题名、章节标签、无限制背景或后续反馈。v2逐项哈希开放31条原文给定的四柱/遁局/旬/值符使及赛前号码，不开放其他unknown对话。v1已冻结文件保留，按v2新发布，不回写旧集。仅三组具体人工审读的 unknown 首轮编号分析允许作为监督目标，从不作为输入；不批量提升 unknown。部分首断后才披露的预产期、成绩、反馈与应期暂不并入本轮。原始全文仍完整保存，未截改资料。

94 个事件家族统一分组。既往看过的 3 开发家族独立 development，不参加本轮训练或盲测。其余家族按固定 seed=17 的哈希次序分组，跨书重复、同案续断与各盘不跨组。冻结清单 data/splits/author_initial_release_v2.json；真实 JSONL 在本地 work/author-initial-release-v2。最长完整序列 1,742 token，没有截断。

## 实际训练方式与验收

training/train_mac_author_lora.py 先校验冻结清单及同型号 12 请求基线，再测完整历史任务：完整 27B 与缓存后的最后一层教师强制损失是否一致。所有更新只在第 64 层全注意力 q_proj / v_proj，因此前 63 层完全不变；其完整序列中间表示只需计算一次，逐字对应原始 token，保存 BF16 原精度、不额外量化或缩短。先通过数值一致性才可释放这部分冻结权重，减少每遍重复计算。此优化仅适用于当前适配位置，不能外推至多层/GatedDeltaNet 适配。

监督只在 assistant 目标 token 上计损失，输入 token 不计损失。batch=1、累积=1，每遍 33 个任务各一次，50 遍共 1,650 次更新；shuffle 每遍确定性改变，不 drop_last。AdamW / maximum LR=1e-4 / 首 33 步 warmup，之后 cosine 至 1e-5。每步真实计数；每 10 步以及每遍保存 adapter、优化器、调度位置、MLX/Python RNG、顺序、下一个游标、模型/资料/缓存哈希。

进入第一遍前，以两个实际域样本做一次可丢弃的中断恢复比对：连续第二步与重开状态后第二步的损失/所有 adapter 张量须一致，然后重置权重与优化器，正式计数从零开始。每遍只据 validation 的目标 token NLL 选择最佳检查点；最终第 50 遍也保留。test 在训练完成后评价最佳/最终模型，不用于选择检查点。标准 MLX 导出和原生 tail 恢复文件分开命名，不能把 wrapper 键名误当完整 27B 适配器。

NLL 是教师强制原文复现指标，不是作者判断正确率、全系统断案完成率或独立现实预测准确率。完整历法与专业条件角色仍有缺口，正式 ask 保持既有门槛。研究生成仍经统一 QimenService.ask 的显式 research 分支；27B 未训练/训练后使用同题、同盘、同检索/候选条件、禁用 thinking、固定 seed 和生成预算进行对照。第四组仍叫 candidate_conditions，不冒称完整正式角色规则已接通。

## 当前执行状态

机器可读计划见 training/qwen38_27b_lora_plan.json；实际日志和计数以其 actual_run_progress 指向的本地 progress.json 为准。中性硬件探测与保存重开已通过；12 请求同 27B 开发基线正在执行。尚未完成 50 遍，不提前填写训练成功或准确率。

13 项资料/epoch 安全回归通过；新增 MLX options 的 3 项及实际 Qwen 小型 decoder 的 loss/梯度等价、AdamW/RNG 恢复 2 项另行通过，合计 529 项。随机状态直接回写曾失败，已通过精确64位seed重建修复并实际验证下一次随机抽样和更新一致。已有全量 524 项实际通过，154.470 秒，0 失败/错误（该次发现测试时尚未加入 3 项 options，用单独 3 项补充）。旧 52 文件快照及本轮源代码差异另保留验证。只本地执行，无本轮 Actions、无 GitHub push。


补充验收：当前代码实际完整运行 534 项，0 失败/错误，101.606 秒；日志 work/qwen38-regression-final.log。v1/v2派生release均从原快照重建并匹配各自已冻结JSONL哈希。首轮6个测试家族已冻结逐项作者目标/文献反馈标签，使用 author_initial_heldout_v2.json，经同一 QimenService.ask 的明确研究权限调用；只能在固定symbolic_chart条件，禁止将train家族改名为test。v1的dun输入枚举在模型调用前被引擎拒绝，新v2仅规范为阳遁/阴遁，目标标签无更改。未微调模型先封存6请求，再执行训练；模型选择仅看validation，50遍后才解封比较，与已有3开发家族/12请求对照分开。原文反馈仅作书中叙述一致性，独立现实预测仍null。
