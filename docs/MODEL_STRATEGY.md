# 模型与训练路线

当前：无模型权重、无 API 凭据调用、无训练数据、无训练作业。ModelGateway 可替换协议已接入统一 service；默认 UnconfiguredModelGateway 明确 unavailable。

## 选择前的门槛

1. 实测家庭 GPU 机器 OS、CPU、内存、磁盘、4090 显存/驱动及 CUDA/PyTorch 组合；Mac 环境另立。
2. 核对候选精确版本、权重获取途径和商业/微调/分发许可。Qwen 等仅为候选，不提前锁定模型。
3. 在同一事件冻结题集测原始模型，再测盘、检索、完整条件规则系统。强 API 可作为研究基线，但需隐私授权与成本预算。
4. 记录上下文、结构化协议遵循、显存峰值、tokens/s、首 token 延迟、截断/失败、长案例证据保全、专业任务评分；相同输入、版本及生成设置公平比较。

优先实测约 7B–9B，是否采用更大模型由测量决定；24GB 不等于任意上下文和优化器都可训练。Mac M2 24GB 可做轻量推理，不取代 4090 训练。

## 分层分工

确定性工具负责固定事实和盘；运行时数据库负责来源、条件与方法；模型负责理解、证据组织和专业解释。LoRA/QLoRA 学习问事、步骤、类象条件、证据取舍、专业判断、应期与续断，不要求权重背诵盘面。

根据实测兼容性建立独立 CUDA 环境，可评估 PyTorch / Transformers / PEFT / TRL / bitsandbytes；不在 Phase 0 安装巨型依赖。选择后锁定精确版本和模型 revision，保存 lock/环境导出、GPU 信息、随机种子及训练配置；无偏好数据不启用偏好优化或 RL。

## 数据与实验记录

完整事件家族隔离，训练候选需原文/规则/案例 ID、时刻可知输入、目标、证据、split、审核、版本/哈希。案例不能无声截断或靠重复扩增。人工确认的作者依据与模型猜测分开。

每次实验清单必须包含：experiment_id、Git commit、模型及 tokenizer revision/许可、数据 release/清单哈希、训练/验证家族、LoRA rank/alpha/dropout/target_modules、epoch、optimizer steps、学习率与优化器、batch、gradient accumulation、上下文长度、截断策略、随机种子、精度/量化、设备/软件版本、峰值显存、速度、loss、checkpoint/resume、独立测试结果和基线差异。

训练和推理 artifact 只存版本化 manifest 与外置权重引用，不无计划进入 Git。保留模型、适配器、tokenizer、优化器、scheduler、RNG 及数据游标，实际测试中断后恢复一致性。详细接入见 HARDWARE。

## 成功标准

同条件对照显示可复现专业提升，基础事实与条件错误不退化、格式错误单独改善，盲测完成率与正确性同时报告。loss 降低、20 步优化或流畅断语均不够。历史复现、作者叙述结果与独立现实预测三者不能互相代替。
