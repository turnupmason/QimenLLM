# QimenLLM 持久执行约束

本仓库是全新项目。项目使命及用户章程见 `docs/PROJECT_CHARTER.md`；开始工作先读 `docs/STATUS.md`，再读相关专题文档。用户的新指令优先，不能自行继承其他项目、插件内古籍、Excel、案例或算法。

1. 原文按输入字节完整保存，引用可追溯；修订追加版本，不改旧文。不得用模型记忆、网络或未授权文献补齐知识。
2. 用户已一并确认既往与未来提供的原文、基础知识及案例事实，并声明独立确认；维护导入默认confirmed，不再请求原文二次人工确认。确认依据记user_attestation；不冒称软件亲自外查，不补未写结局。来源接受、结构化、适用条件、规则编译、程序复算、专业评估分别报告。程序不能复算不等于资料错误。完整新指令见docs/user_instructions/source_confirmation_2026-10-17.txt。
3. 完整案例保留故事、多事件、多盘、作者显式分析、预测、反馈与续断；不虚构内部推理。不把事后信息提前放进训练输入。
4. 条件未知不能视为满足；方法隔离；只有适用、有来源、经来源与测试验证编译的规则可绑定角色。禁止凭年龄替代人物关系。
5. 盘面计算独立于模型；同一不可变盘对象供入口、校验和界面使用。基础事实、证据与最终文字均需程序验证。
6. 正式问事只通过 `QimenService.ask`。CLI、API、未来 Web、评估必须共用。模块存在不等于已集成，阻断或结构校验不算专业断案成功。
7. 事件家族级划分，跨书重复事件同组；冻结评估不得修改或泄漏。格式、生成、知识、证据错误分别统计。
8. 不提前训练或锁定模型。训练前检测实际 GPU 主机、许可、数据版本、显存与基线，记录完整实验及检查点。
9. 不自行暴露公网端口、购买云资源或连接家庭电脑。用户隐私不默认进入日志或训练。研究版权不等于全文公开权限。
10. 修改后运行相应回归测试，更新 STATUS 与必要决策；报告实际命令、通过/失败、未验证项、真实调用链、迁移及数据影响。不得以计划或代码文件替代验收。
11. 用户已长期授权每次源码、文献或结构化数据更新同步至私有 `turnupmason/QimenLLM`，无需再次询问。先审计、导出可恢复快照、测试、commit/push 并核对远端 main；本地提交不算同步。CLI import/annotate 自动尝试，失败保留资料并返回 pending/退出码2。若仅命令行 API 被限制，按 GITHUB_SYNC 的连接器核验私有状态后使用已验证的正常 Git HTTPS 完成上传，不绕过策略、不停留在本地。原文通过快照备份，密钥、个人问事及模型产物不入 Git。

运行：`PYTHONPATH=src python3 -m unittest discover -s tests -v`。
资料/案例规则见 KNOWLEDGE_POLICY / CASE_POLICY；架构与迁移见 ARCHITECTURE / SCHEMA；评估见 EVALUATION_PROTOCOL；设备与远程接入见 HARDWARE。
当前已接收《神奇之门》26份章级来源输入，累计98故事/94家族/106事件/104来源盘记录。本轮附录三精校源SHA256 0649e0a09cc615c9c379e3fb5f43a20038329546ec8a829dbbdac11b8322981e，15047字节/5513字符/140行LF；书中篇次三、接收排序27，旧一/二键与次序不改。叙事去空白/旧页眉并分开图表后4387字符相同，30记录对应原故事、两事件共家族，不克隆案盘。文件明确标为文字原盘重排的九宫表逐宫36字面单元与独立gold保存，生乙/中宫壬/壬惊丙不按引擎修字。新表由既有reference读取，旧碎片/原chart_id及case-chart not_covered不升级；不是新纸本原图或复算。初次否定、续断、会后信/部分财务与死伤、后置解释和2000按语保持时序。沿import_chapter/add_annotations新增2语境/2边界，无新方法/索引/案例/候选/训练；schema、目录、workflow、旧gold和总指令不改。验收见STATUS与ingestion/SHENQI_DEMO.md。

本会话后续指令：用户确认全书资料提供完毕，要求按原计划开始建模；先Mac本地研究，明确本轮只在本地、不推送GitHub（当前公开由用户主动设置）。此项暂覆盖第11条自动同步，勿改可见性。严格沿Master第11节/Phase2与4门槛推进；已有候选模型试跑不等于最终模型锁定、完整专业基线、微调或现实验证。持久新指令见docs/user_instructions/model_research_2026-10-17.txt，开发过程见docs/MODEL_BASELINE.md。

此前用户曾明确目标（现已修订，见末段）：Qwen3.8-27B + LoRA/QLoRA，50个epoch（完整训练集学习50遍）。此型号及次数优先于早期“不预锁型号”的一般建议；既往4B只作接线试验。先Mac、本轮仅本地继续有效；训练资料/同27B基线/内存与保存恢复门槛不跳过，不把50步当50epoch。见docs/user_instructions/qwen38_27b_50epochs_2026-10-17.txt与training/qwen38_27b_lora_plan.json。

最新修订（优先于上段固定50遍/先Mac训练）：用户上传professional_training_summary_2026-10-17.txt，明确目标是学习专业方法而非作者原话复现；随后撤回50个epoch硬要求，并改为Codex在Mac完成专业数据与评估准备，用户可在RTX4090训练。Qwen3.8-27B + LoRA/QLoRA目标保留，轮数/适配位置等由高质量任务、实际硬件与验证集决定，不能用test调参。旧作者原话复现启动器已退役，0正式epoch/0正式更新；旧冻结资料和数值探测保留。当前数据审读清单不是可训练release，不得拿清单或原文拼接当五类专业SFT任务。见docs/PROFESSIONAL_TRAINING.md和docs/user_instructions/validation_driven_training_2026-10-17.txt、rtx4090_data_handoff_2026-10-17.txt。本轮仅本地仍有效，不自行连接4090或推送公开仓库。

专业数据当前已进入首批逐任务审读：lost_method_release_v5是现行32个来源审读子任务，8整案/14阶段，22train/4validation/4test/2development；其余90故事仍待专业样本整理。来源/角色/读盘/综合/应期/续断及完整上下文遵循docs/PROFESSIONAL_TRAINING；未知的空亡/马星等可作为明确给定的作者前提供方法子任务使用，不能冒充计算结果或无辅助首断。旧v1–v4均未用于模型/训练，拒绝或替代原因单独记录，勿继续启动旧稿。原DB/52快照/旧gold与家族划分保持，无formal SFT授权或新问事路径。

最新执行状态（2026-10-17，覆盖下文“仅本地”和“仅4090训练”历史限制）：用户已恢复GitHub同步，并要求先Mac27B的读盘/方法基线、真实LoRA微调和验证比较，效果及逻辑通过后再进行4090系统训练。新指令见docs/user_instructions/all_cases_pilot_github_2026-10-17.txt、mac_method_pilot_2026-10-17.txt。原Master、旧来源、旧冻结划分与旧作业不改；不得恢复作者原话/固定50遍启动器。

全书98完整故事已导出按既有94家族冻结的完整档案：65train/15validation/15test/3development。所有106事件/1579记录/104原盘完整保存，故事档案含结局且永不作为模型输入。可训练派生任务125条：32个钱物丢失审读方法子任务+93个其他来源原盘字面读取任务；分布80train/21validation/20test/4development，涉及96故事。另2故事的3张旧原盘不在现有投影覆盖范围，完整档案保留，不补造盘面。125不等于125独立案例或全书综合方法已审读。见data/splits/book_preparation_v1.json和data/provenance/book_training_coverage_v1.json。

钱物丢失限定研究试验沿v5冻结32任务，不移动家族。Mac先测试无适配器27B，再使用最后全注意力层q/v的rank4 LoRA进行最多3遍、验证无改善停止的工程/方法试验；训练只读22train/4validation，test封存。缓存全模型等价和真实任务下一更新恢复等价必须实际通过；loss只选候选，仍需比较同题生成的专业解释。正式规则和完整D/E系统对照尚未完成，不以source_given_conditions替代。QimenService.ask的显式MethodRequest研究分支承担全部生成评估，正式问事门槛保持。

全书基础任务覆盖现行为book_preparation_v2：98故事都保留完整档案并有基础学习任务，共127条，82train/21validation/20test/4development；故事分组仍65/15/15/3、94家族归属不动。组成是钱物丢失32方法任务、其他原表93字面读取、卫星局部来源完整性1题、附录三用户重排表1题。后两题限定资料阅读，不模拟历史首断，不补造完整盘；三个旧原盘not_covered状态保持。卫星题不提供后来报道或204行后置补充，重排题逐字核对独立gold的36单元，不按算法改生乙/壬惊丙。原v1全部任务与档案逐字保留，v2只在train增加两个来源审读任务。专业方法深度审读仍8案32题，其余90案的基础任务不能冒充完整断案监督。钱物丢失Mac试验数据仍固定v5的22train/4validation，未用新增两题或test。

最新实际Mac结果（2026-10-18）：有限方法LoRA已完成3遍/66更新，94,208参数；验证NLL下降不能替代来源审读。同题六请求3协议接受/3生成截断，四validation均有专业问题，comparison_v1.mac_limited_method_review_pass=false/systematic_training_ready=false，test未开。4090 train入口须核对同基座/数据的Mac通过回执，在GPU初始化前拒绝缺失或失败门槛；不把该候选升级为正式训练或专业模型。训练实际旧代码见affe4d7 commit；后续恢复游标修复不改旧实验代码哈希。模型附件无正常登录时保持pending，不将权重放普通Git。
