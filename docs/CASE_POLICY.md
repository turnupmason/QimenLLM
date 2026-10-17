# 完整历史案例政策

一个故事整体保存，原文 span 可指向整个章节；案例可覆盖多事件，一个事件可在多书出现，一个事件可有任意数量的盘，不固定成一张或两张。不得破坏故事来扩增样本。

`cases → case_events → events → charts / case_records → evidence_links`。事件归 event_family，跨书同一故事及其多盘、续断、派生任务必须同家族。发现重复有疑问时先隔离，未解决不发布训练/评估集。family 合并或修正需要审计迁移与重建划分，不绕开 append-only 约束。

每个案例保留背景、人物关系、问测时刻/口径、原书盘、原始对话、作者用神、盘面事实、宫内跨宫关系、生克旺衰格局类象、证据取舍、断语、应期、反馈、续断与结局。未写的项目为 unknown，不补造；原书资料完整可与程序解析/复算未知并存。

`case_records.kind` 区分 dialogue / author_reasoning / role_selection / prediction / timing / feedback / continuation / outcome，sequence 为同一事件内原书可识别顺序，knowledge_phase 为 pre_prediction / prediction / post_feedback / unknown；reported_at 只存实际提供时间。顺序未知时不能凭结果推演伪造。

explicitness 区分 author_explicit、not_explicit、agent_hypothesis。text 可保存实际作者步骤；payload 存宫位、用神、证据取舍、应期等结构化内容；原文引用独立可回看。模型假设不得写成作者显式推理。后续扩充的观察验证状态需区分作者报告和独立确认。

原书盘以整体 JSON、原文/图定位及哈希存储，original_unparsed 表明尚不能解析，不等同于错误。跨事件挂盘、跨事件证据引用由 FK/trigger 阻止。确定性复算应另建 engine 盘与差异记录，不能覆盖原盘或以结局调盘。

训练样本按 event_family 在单一 release 内划分。目标和输入分离；当前保守投影仅允许事前 author_explicit dialogue，且严格早于目标 cutoff，拒绝预测、反馈、续断、未知时序及目标本身作为输入。完整背景 JSON 不自动注入，避免叙述隐藏结局。已知反馈后的续断训练将扩展逐任务的时间权限及测试，目前只保存资料，不导出此类输入。

当前 schema 能保存候选任务、输入记录与目标来源，但尚未实现正式训练样本发布、上下文分块、任务哈希/发布清单生成器和全语义泄漏审计。记录 phase 本身也须人工按原书核实；SQL 无法判断一个被错误标为事前的句子是否暗含结局。不能仅凭 FK 通过就宣称训练数据可用。

冻结后不可改 split、unfreeze 或追加任务输入；同家族跨组违反唯一约束。新发现来源或家族重复必须新 release，冻结集不静默改写。

每次完整案例验收检查：全文、所有盘与对应事件、逐轮对话、作者显式依据、预测反馈边界、来源完整性、跨书重复、候选任务隔离；不能因程序不能复算就否定用户已确认资料。

第二章两张完整起局示例没有问事背景、作者断语、预测或反馈，当前归为worked_example知识记录，整体保存原文范围和source chart，不创建虚构event/case来凑数。历史charts表保持0不表示源盘丢失；其结构化九宫保存在对应完整教学例。将来真实断案资料按本政策独立入库。

应用概述首个历史叙事已按此政策入库：卫星故事52–68行及204同案补充为1case/1event/1family/1局部original_unparsed盘，10记录/17证据；作者报告结果与独立确认分开。before_prediction只开放52、54行，不返回作者结论/反馈/后文/无限制背景或含分析原盘；该视图不是训练任务发布。原盘JSON记录预定时间/地点，SQL专用索引暂未填，绝不据此否定或覆盖原盘。后续已识别同事件明确复用全局family_key，家族元数据冲突拒绝，需要审计后处理。原始教学例仍不是历史charts；累计历史案例1，不提前创建训练任务。
