# 首轮本地模型研究记录

本轮依据用户总指令第04、10、11、12、17节及后续明确授权执行：全书资料已提供完毕，开始尝试建模，先用Mac；当前公开仓库由用户主动设置，本轮只本地、不上传GitHub。原总指令文件、来源数据与历史gold保持。

## 当前阶段与门槛

当前是Phase 2缺口审计及Phase 4开发预实验准备。正式五级对照仍按原计划：基础模型 → 确定性盘面 → 正确知识检索 → 完整条件规则 → 相同系统微调后对照。当前完整历法和正式用神未完成，不能用候选辅助实验替代第四级或宣布正式专业基线验收。

权威数据仍为9fe01f72-44f1-4b6d-b793-f2b9b748f16c：1书、26来源、98故事、94家族、106事件、104来源盘记录；rules/training_tasks/dataset_releases均0，无schema或权威库迁移。快照canonical manifest SHA256仍60c681252486135c1dd5b730d1d31677757437d9b01f1e7e330624a597195401；含末尾LF的manifest文件SHA256为9a25c2820b56303a589a32af2b1a8f6b370d250fb482a98b62338bfebf1c032e。用户声明全书输入结束不等于软件已逐纸本独立核页。

## 全书只读审计

`scripts/audit_model_readiness.py`可重复执行，完整性审计通过。104条盘引用中101可投影、3未覆盖；明确指定shenqi_ch2_paper_v1时，现有支持字段比较35 matches、4 mismatch、57 conditional、8 not_covered。57项属于投影缺少结构化比较元数据，不据此声称原文没有四柱或局数；4差异保留源字及每个source/computed字段，不判断为原书错误或迎合算法改盘。

对本轮人工审读的三个开发任务，在比较的临时对象中补入原文明确给定的遁、局、时干支，三个原盘受支持字段均matches。未修改原chart或投影元数据；没有验证公历、交节、空亡、马星或所有图符语义。详细逐字段证据见data/provenance/model_development_chart_checks_v1.json。

196条当前条件候选在空上下文下全部conditional，正式绑定为空。此项只证明缺失条件门槛得到保留，不证明专业用神引擎已经完成。

## 开发任务与权限

baseline_development_v3.json固定3开发家族，91其他家族reserved_unreviewed；不是已审核训练集、正式dataset_release或盲测成绩。v3清单SHA256为6c43228e83db2e71eb658ef2a385088cb93a007fbaea4006d93eb0d0e37b5a78。跨书再引同案须沿用家族分配；保留待审读不代表对未来基础模型预训练污染作保证。

开发题包括：出行安全的用神/返途事故/人员安全、来人未透露问事的首次判断、婚姻案例后续一轮的用神和成婚年份。输入只释放逐条审过的来源片段、确实早于本轮断语的对话和原盘；不释放标题、整故事、未知背景或目标记录。晚轮反馈仅能在晚轮的明确cutoff前使用，不回灌首次视图。

婚姻案例按原文保留作者在1996年所说“明年四五月”（1997）与反馈“1998年五月”的不同金标准。作者复现与反馈一致率有不同的目标和分母，不互相改答案。三个任务共7个作者字段、4个反馈字段，字段不是独立事件数。作者和用户确认来源的结果不等于本软件前瞻独立随访。

v1接线试跑保留在work/mac-baseline-run-001，基础臂遗漏部分原文所报时间元数据；不用于性能比较。v2统一每臂的原始已知信息、所给符号、声明背景、输出字段、模型、参数与预算，仅工具层有区别。v2进一步暴露方法上下文枚举与候选DSL接线不合；v3修正旅行方法枚举、婚恋缺失条件保留unknown，添加实际候选状态回归。三版开发金标准不改，旧输出和中断保留；最终预实验使用v3，同一轮所有臂采用相同修正与协议。输出提示明确区分预测答案与盘事实，避免将预测填入fact_claims；未作输出修补或挑选重试。

## 真实调用与实验范围

正式入口仍是QimenService.ask；本地ResearchRequest显式进入独立标记的研究分支，统一调用同一排盘计算器、SQL来源读取、条件检查器和本地模型。HTTP/API不能启用research关键词，默认问事仍受engine_verified和正式绑定门槛阻断。

四个开发臂为base、symbolic_chart、chart_knowledge、candidate_conditions。第四项明确只是条件候选诊断；完整条件规则臂blocked，SFT/LoRA未运行。检索臂由审过的理论片段白名单提供，属于正确检索的人工选片对照；未宣称自动检索排序已完成。来源切片必须在所有本库case范围之外，整章检索不进入预测上下文。隐藏问事题没有用其后来揭露的领域选择检索，知识及条件均为空；相同上下文的重复臂不能冒充新增证据。

结果协议分别验证JSON/schema、枚举类型、引用是否为释放原句、声明的盘面事实是否等于程序值。引用字面匹配不验证推理成立；空答案/拒答不计正确，结构有效也不算专业完成。保存原始失败输出、耗时、首token、tokens/s、峰值MLX内存和截断；超上下文直接失败，不静默裁案。

## Mac候选与重现

实测Apple M2、24GiB统一内存、Metal可用；推荐GPU工作集约19.07GB。候选是Qwen/Qwen3-4B-Instruct-2507的MLX社区4bit转换，repo mlx-community/Qwen3-4B-Instruct-2507-4bit，revision 50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b；官方基础模型查询revision cdbee75f17c01a7cc42f958dc650907174af0554，未下载BF16基座。两者模型卡标Apache-2.0，许可证检查依据只涉及模型，不替代古籍公开使用权。

全部13文件共2,278,972,236字节；权重SHA256 2a73c6c248601ab904e035548abd8e6abb65ea27dcb5f342fb0a8910eb44173f，tokenizer LFS亦逐哈希核验；其他文件本地SHA记录完整。模型仅是首个可替换开发候选，未锁定最终产品模型。未安装全局环境、未调用付费API、未起公网或本地模型服务、未连接4090、未训练权重。推理HF离线模式，资料不发送给模型服务。

独立venv与权重都在聊天工作目录work/下，不进入Git。实际依赖锁见data/provenance/mac_model_requirements_v1.txt；Python3.12.2、mlx0.32.4、mlx-lm0.32.2、transformers5.20.1。正式4090训练环境仍须另立并实测，不能由Mac推理成绩替代。

执行入口（在仓库根目录；路径根据已下载的本地文件设置）：

```sh
PYTHONPATH=src python3 scripts/audit_model_readiness.py --db work/demo.sqlite3 --raw-dir work/demo-raw --output work/readiness-new.json
PYTHONPATH=src ../mac-model-venv/bin/python scripts/run_mac_baseline.py --db work/demo.sqlite3 --suite data/structured/shenqi/baseline_development_v3.json --suite-sha256 6c43228e83db2e71eb658ef2a385088cb93a007fbaea4006d93eb0d0e37b5a78 --model-path ../models/qwen3-4b-instruct-2507-4bit --model-manifest ../mac-model-files.json --output work/mac-baseline-run-new
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

输出目录必须新建，避免覆盖旧实验。脚本重新核验全模型文件和任务清单；无自动权重下载，记录运行代码哈希。当前运行记录在work/mac-baseline-run-003/report.json；最终汇总和验收见data/provenance/mac_baseline_validation_v1.json，以实际完成状态为准。

候选依据：[官方模型卡](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)、[转换模型卡](https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit)、[MLX-LM源码](https://github.com/ml-explore/mlx-lm)。

## 按原阶段计划接续

1. Phase2：逐项补齐有来源的时间元数据解析、历法约定/边界、未覆盖布局与规则条件编译；差异分类为方法差异、投影或实现问题，保留未知。正式角色须来源、条件、例外、方法和独立金标准测试俱全，不能一键提升196候选。
2. Phase3/4：继续逐事件审读输入cutoff、作者判断与结果目标，登记已见开发题；冻结独立家族任务release，加入新盘/新问题，先于后续书和训练固定对照口径。
3. Phase4：同一模型/设置完成原计划四级正式系统对照，分别统计协议、盘、检索、条件、证据、作者判断、反馈与缺失。对人工选片辅助与自动检索分别试验，不能把流畅输出当专业正确。
4. Phase5：达到高质量数据、冻结盲测、模型许可和真实GPU门槛再决定微调。当前这些阶段门槛尚未满足，未启动LoRA。未来20余古籍逐本版本化，不默认混书/流派，不从这3个已见开发题估计总体预测能力。
5. 独立现实表现须另立前瞻登记：发布时间、可知背景、明确预测目标/期限、完整随访、失访和失败全记；当前现实预测准确率null。

## 已验证工程结果

新增18项研究回归全部通过，完整旧493项加新增18项共511项实际通过，耗时67.112秒（work/model-regression-accepted.log）。测试包括实际SQL读取/同一ask接入、所有臂原始已知信息相同、首次隐藏问题无后知领域提示、晚轮cutoff、整案禁止检索、模型协议/字面引用/事实、reserved家族和哈希、HTTP不能开启research、正式问事门槛保留。重导出52快照文件逐字节相同。开发时修正了一项误期待“applicable”的测试：未明确方法时正确结果应保留disputed；未改规则来迁就测试。远端内容基于90e624c9e21a29d9aff2f81ba3f35aba983097cf，当前未push，无本轮Actions CI；不使用旧CI作为本地新增实现的远端证明。

## 本轮实际预实验结果

M2本地完成3任务×4臂=12真实请求，10不同payload（隐藏问事题的三个工具臂没有可释放知识，payload相同，重复不当新增独立样本）。所有请求固定同一候选revision、温度0、seed17、最大输出768与8192上下文预算，最大输入5809 tokens，无静默截断。

| 开发配置 | 请求 | 作者字段匹配/7 | 文献反馈字段匹配/4 | 协议与证据无错的输出 |
|---|---:|---:|---:|---:|
| 基础模型 | 3 | 0 | 0 | 1 |
| 加所给符号盘 | 3 | 1 | 0 | 0 |
| 加受限理论片段检索 | 3 | 2 | 0 | 0 |
| 加来源条件候选检查 | 3 | 2 | 1 | 0 |

这些是开发题的原始字段一致数，包含证据层未过的回答，不是专业正确率或提升证明。三家族不足以估计泛化；没有用这三题选出最终模型或启动训练。总计research_generated1、research_evidence_error10、generation_error1；那1次通过协议的输出作者字段仍0匹配，专业完成0。

事后按原payload逐项复核：1处未释放的source_id、13处引用不是所释放片段中的逐字连续原句、5处声明为计算事实却不等于Chart对象、1次回答枚举超出协议。同一输出可有多项错误，不能把错误项数当请求数。没有做输出修补、挑选成功重试或据此改作者答案。年份判断、角色判断、引用与盘计算分开；三个盘的受支持字段本身已对照一致，不把盘之后的引用/判断失误归为排盘错误。更细的知识覆盖与推理因果归因仍需完整规则及自动检索对照。

观测MLX峰值3,660,774,452字节（约3.66GB），生成速度22.81–31.00 tokens/s。同期运行回归，速度仅供本机可运行性参考，不是独立硬件性能基准。原始12输出、每个字段、模型13文件哈希、每次耗时及代码哈希保存于data/provenance/mac_baseline_run003.json；摘要与协议错误分类在mac_baseline_validation_v1.json。当前代码哈希与本次实际运行记录逐项相符。

下一步优先完成Phase2来源支持的正式角色编译和时间/盘面缺口，审读扩充真实任务与冻结家族release；改进引用协议与检索覆盖后，再按原四级正式系统对照评估。当前完整条件规则仍blocked、微调not_run、独立现实预测准确率null。
