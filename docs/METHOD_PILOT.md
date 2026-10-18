全书基础任务覆盖现行为book_preparation_v2：98故事都保留完整档案并有基础学习任务，共127条，82train/21validation/20test/4development；故事分组仍65/15/15/3、94家族归属不动。组成是钱物丢失32方法任务、其他原表93字面读取、卫星局部来源完整性1题、附录三用户重排表1题。后两题限定资料阅读，不模拟历史首断，不补造完整盘；三个旧原盘not_covered状态保持。卫星题不提供后来报道或204行后置补充，重排题逐字核对独立gold的36单元，不按算法改生乙/壬惊丙。原v1全部任务与档案逐字保留，v2只在train增加两个来源审读任务。专业方法深度审读仍8案32题，其余90案的基础任务不能冒充完整断案监督。钱物丢失Mac试验数据仍固定v5的22train/4validation，未用新增两题或test。

# 钱物丢失章：先Mac方法试验，再4090系统训练

遵循原Master和最新mac_method_pilot用户指令。当前试验学习角色、证据组织、综合判断、应期和反馈续断，不是继续旧作者原话复写任务。原v5冻结任务和94家族分组不改；32任务为22训练/4验证/4测试/2开发。测试发票家族封存。

全书完整档案已按65训练/15验证/15测试/3开发归组；档案含未来反馈，只作审读和评分，绝不能作为训练输入。全书可导出的125任务中93只是字面读盘，32是已审读方法子任务。96故事有任务，另外2故事的3旧盘未被现有投影器覆盖，原文、盘payload与替代表达都保留。其余专业推理任务尚需逐项审读，不将档案或自动记录标签伪装成高质量监督。

## 可重建的数据

从GitHub拉取后，在仓库根目录执行下列操作，不需要下载模型：

```sh
PYTHONPATH=src python3 training/cuda_pilot.py prepare
PYTHONPATH=src python3 training/cuda_pilot.py audit
```

prepare先从52文件的原快照恢复新本地库，再重建四份章节任务与八份全书档案/任务。每份实际字节与Git中的冻结清单一致才成功；已有不同文件拒绝覆盖。输入训练器的只能是tasks/messages，不能是cases或source-review-events。

## Mac限定试验

实际使用已校验的MLX4bit `mlx-community/Qwen3.8-27B-4bit`，revision `10c35caafbb80f7dc6a7a432cdd11af10a6d4818`。不混用官方CUDA tokenizer/权重。当前Mac脚本只能开启development/validation，不提供test选项。

```sh
PYTHONPATH=src python scripts/run_mac_method_pilot.py \
  --model-path /absolute/local/model \
  --model-manifest /absolute/local/model-receipt.json \
  --output work/mac-lost-method-baseline-v1

PYTHONPATH=src python training/train_mac_method_lora.py \
  --model-manifest /absolute/local/model-receipt.json \
  --baseline work/mac-lost-method-baseline-v1/report.json \
  --output work/mac-lost-method-lora-v1

PYTHONPATH=src python scripts/run_mac_method_pilot.py \
  --model-path /absolute/local/model \
  --model-manifest /absolute/local/model-receipt.json \
  --adapter-path work/mac-lost-method-lora-v1/epoch-NN \
  --split validation --output work/mac-lost-method-after-v1
```

epoch-NN必须来自本次训练实际留下的候选检查点，不能照抄占位符。最终全注意力层q/v、rank4、scale2、学习率1e-4、batch1、最多3遍，完整验证无改善即停止；没有固定50遍。冻结前63层的完整输入激活缓存，仅适用于这个受限适配位置，不能套用到全层LoRA。先比较真实方法样本完整64层目标损失与缓存目标损失，再比较保存/恢复后的下一次更新；任一不等价就停止，探测更新重置后才计正式遍数。每优化更新保存适配器、优化器、RNG、游标、样本次序及调度位置，文件哈希防止错版本恢复。未完整缓存前中断应从新目录重建；有完整cache-index和检查点才用--resume恢复。

训练损失及验证NLL只是辅助指标。只选验证候选，不打开test。随后用相同payload、生成设置和同27B基座重跑验证题，逐条审读来源与方法，再决定是否值得扩展适配位置或转4090。最后层小适配器也不代表已经完成全模型专业训练。

## 4090后续入口

Linux/WSL2、Python3.12，使用CUDA可用的PyTorch。training/requirements-cuda.txt固定运行库版本；需要匹配本机驱动的CUDA wheel。安装后先确认CUDA，脚本不以CPU或另一型号冒充4090。NF4双重量化、BF16计算、冻结基座、多层文本适配；仅按匹配到的真实混合架构模块插入，不训练视觉层。官方型号在其[固定config](https://huggingface.co/Qwen/Qwen3.8-27B/blob/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0/config.json)中使用qwen3_5混合架构；量化流程依据[PEFT官方指南](https://huggingface.co/docs/peft/en/developer_guides/quantization)。

```sh
python -m pip install -r training/requirements-cuda.txt
PYTHONPATH=src python training/cuda_pilot.py prepare
PYTHONPATH=src python training/cuda_pilot.py preflight
PYTHONPATH=src python training/cuda_pilot.py baseline
PYTHONPATH=src python training/cuda_pilot.py train
```

此处尚未在真实4090上执行。preflight实际完整上下文反传与下一更新恢复必须通过，不能拿Mac或小张量测试代替；不自动降模型或截短任务。训练只读train/validation，最大12遍是可修改的研究上限，非已确定最优值；验证无改善停止。恢复使用同run最新完整checkpoint，改变配置/代码/数据需新实验。训练完成后先查看各epoch-validation.json并按原文填写验证审读文件：

```json
{
  "split": "validation",
  "evaluation_sha256": "实际验证报告的SHA256",
  "reviewer": "实际审读者",
  "selection_reason": "比较候选的理由，不能看test",
  "tasks": {
    "实际task_id（四题逐项填写）": {
      "method_correct": true,
      "evidence_supported": true,
      "source_note": "逐题核对的来源、适用条件和不足；示例true不能直接照用"
    }
  }
}
```

```sh
PYTHONPATH=src python training/cuda_pilot.py select \
  --checkpoint work/lost-4090-run001/epoch-NNN --review /absolute/validation-review.json
PYTHONPATH=src python training/cuda_pilot.py test
PYTHONPATH=src python training/publish_pilot.py
```

选择回执固定后，才比较同题基础模型与适配模型的test生成；开启标记在生成前写入，失败也不静默反复调试盲测。当前章只有一个验证家族、一个测试家族，结果不可外推为全书或真实世界预测准确率。

## 评分与GitHub

所有生成均经QimenService.ask → 显式MethodRequest研究分支 → 同模型gateway。正式问事路径不降低起盘/规则/事实门槛。base、原盘、原盘+一般条文、原盘+作者给定条件四个研究输入分别记录；最后一组仍不是正式条件规则D组，完整D/E对照目前blocked。

同时记录完成/拒答/生成失败、引用错误、结构化字面事实分母与匹配、明确用神结构目标，以及人工审读的方法正确性。模型用自然语言说对事实但未返回observations时，结构化匹配数为0，不代表自然语言事实全部错误。协议通过也不能代表专业完成。作者方法复现、书中反馈一致和独立现实准确率三条轴分开；未评估的值必须null。书中结果仅供评分，不提前进输入。

用户已恢复GitHub同步。代码、冻结清单、来源快照与实际实验摘要入main；每个选定模型用版本化适配器、数据/基座/代码/配置哈希追溯。publish_pilot.py只上传所选适配器及受控实验文件到Release，重新下载核对，再提交main中的实验清单；需要本机gh已登录。普通Git不放基座/优化器/任意产物，未完成上传时明确pending，不能说“模型已更新”。不增加一次性workflow。

同一候选的六道开发/验证生成完成后，由执行代理逐来源审读四道validation，保存包含reviewer/source_basis、四题source_fidelity_pass/task_completion_pass/no_unsupported_factual_claims/source_note和精确after_report_sha256的审读JSON，再使用training/compare_method_runs.py比较：

```sh
python3 training/compare_method_runs.py \
  --before data/provenance/mac_lost_method_baseline_v1.json \
  --after work/mac-lost-method-after-v1/report.json \
  --review work/mac-lost-method-after-v1/source-review.json \
  --output data/provenance/mac_lost_method_comparison_v1.json
```

脚本拒绝不同模型、来源、输入或生成设置，拒绝缺失语义审读；结构化满分也不能自动证明方法正确。局部方法通过与完整D/E系统、全书专业任务审读、独立现实准确率分别记录。
