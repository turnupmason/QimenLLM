最新执行状态（2026-10-17，覆盖下文“仅本地”和“仅4090训练”历史限制）：用户已恢复GitHub同步，并要求先Mac27B的读盘/方法基线、真实LoRA微调和验证比较，效果及逻辑通过后再进行4090系统训练。新指令见docs/user_instructions/all_cases_pilot_github_2026-10-17.txt、mac_method_pilot_2026-10-17.txt。原Master、旧来源、旧冻结划分与旧作业不改；不得恢复作者原话/固定50遍启动器。

全书98完整故事已导出按既有94家族冻结的完整档案：65train/15validation/15test/3development。所有106事件/1579记录/104原盘完整保存，故事档案含结局且永不作为模型输入。可训练派生任务125条：32个钱物丢失审读方法子任务+93个其他来源原盘字面读取任务；分布80train/21validation/20test/4development，涉及96故事。另2故事的3张旧原盘不在现有投影覆盖范围，完整档案保留，不补造盘面。125不等于125独立案例或全书综合方法已审读。见data/splits/book_preparation_v1.json和data/provenance/book_training_coverage_v1.json。

钱物丢失限定研究试验沿v5冻结32任务，不移动家族。Mac先测试无适配器27B，再使用最后全注意力层q/v的rank4 LoRA进行最多3遍、验证无改善停止的工程/方法试验；训练只读22train/4validation，test封存。缓存全模型等价和真实任务下一更新恢复等价必须实际通过；loss只选候选，仍需比较同题生成的专业解释。正式规则和完整D/E系统对照尚未完成，不以source_given_conditions替代。QimenService.ask的显式MethodRequest研究分支承担全部生成评估，正式问事门槛保持。

# 专业数据准备与训练交接

执行原Master及2026-10-17专业训练总结。当前分工：Codex在Mac准备并审查数据，用户可在RTX4090执行训练。目标仍为Qwen3.8-27B + LoRA/QLoRA；用户已撤回固定50遍要求，轮数、适配位置及停止条件在专业任务与全系统基线完成后确定，只用训练/验证集选择。

professional_inventory.py只读重开全书、验证原字节与引用、保留完整事件/原盘/时间阶段和冻结家族划分，并生成五类证据审读队列。它不自动给作者步骤打新标签，不把unknown或事后分析提升成预测时已知，不导出messages，不产生可训练release。

```sh
python3 training/professional_inventory.py --db work/demo.sqlite3 --family-manifest data/splits/author_initial_release_v2.json --output work/professional-source-review-v1
```

该输出路径已存在时拒绝覆盖，请选择新版本路径。当前完整数据核对已通过，语义任务审读与正式发布未完成；不能将source-review-events.jsonl交给训练器直接学习。

历史author_release.py和两个冻结release用于追溯；旧train_mac_author_lora.py启动器已退役，直接调用会在任何模型/数据读取前退出。epoch_protocol.py的50遍测试只是完整遍数计量的一个测试样例，不是当前训练要求。旧精确前缀缓存只适用于最终层适配，不套用到将来的多层LoRA。

现行五类任务验收、对照组、来源和时序边界见../docs/PROFESSIONAL_TRAINING.md。现行计划为qwen38_27b_lora_plan.json；其中未确定超参数为null，不代表零轮训练结果。权重、训练产物、原始审读清单留本地；本轮不推送GitHub，不自行连接4090。


首批专业子任务已形成：钱物丢失8案、14披露阶段、32任务，当前有效冻结版本为lost_method_release_v5.json（22train/4validation/4test/2development）。用神/读盘/综合/应期/续断分别6/8/6/6/6。method_release.py只读核对逐项权限、来源字节、未来边界、一般知识与案例叙述隔离及九宫字面事实，不改数据库，不授权正式SFT。给定作者条件的任务与无辅助预测分开。

```sh
PYTHONPATH=src python3 training/method_release.py --db work/demo.sqlite3 --review data/structured/shenqi/lost_method_task_review_v5.json --family-manifest data/splits/author_initial_release_v2.json --output work/lost-method-release-v5 --manifest data/splits/lost_method_release_v5.json
```

现行输出已经存在，此命令会拒绝覆盖；如需只读重建核对，请使用临时新路径或调用build并逐哈希比较。不要用v1–v4试稿替代v5；这些稿次均未被用于模型或训练。全书专业样本仍有90故事待整理，不能把首批32当作全书发布。
