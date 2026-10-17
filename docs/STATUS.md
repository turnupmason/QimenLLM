# 当前项目状态

更新：2026-10-17。本轮《神奇之门·出行出国预测》，技术键travel-abroad/排序13，不推印刷章号。累计12份章级输入。最高要求仍见PROJECT_CHARTER及user_instructions/master_spec_2026-10-17.txt。

## 本轮来源和数据

用户TXT原始31026字节/350行，SHA256 c273c803eb78a02cfb3c6c00065da81312c1851a679a1e3bca4911acdbc3bc55。uploads、SQLite BLOB、snapshot raw完整保存，Unicode框线和末尾未完句不改。confirmed/user_attestation，不冒称系统独立查访。16语境组、8条件候选均reference_only；保留方向、交通方式、出发/归期、庚格例外等完整条件。

新增6完整故事/6家族/6事件/7原盘/99记录/99证据。案例四10月电话复盘读取同一2月历史盘，反馈和续断在首测之后。案例六电话盘和拟起飞盘为同一旅行两盘，7月反馈及雨情后置分析不提前，不造延误起飞第三盘。沿QimenService同ID投影，63宫保留原文行列和芮禽己字面，不擅改重复己。详细报告ingestion/SHENQI_TRAVEL.md。

| 资源 | 累计数量 |
|---|---:|
| 书 / 章 / 原始文档 | 1 / 12 / 12 |
| 概念索引 / 方法 | 2011 / 21 |
| 结构化知识项 / 来源片段 | 871 / 2208 |
| 完整案例 / 家族 / 事件 / 原书盘 | 49 / 46 / 55 / 52 |
| 案例记录 / 证据关联 | 941 / 1262 |
| 来源审读历史 / 数据版本记录 | 19 / 55 |
| 正式角色rules / training_tasks / releases | 0 / 0 / 0 |
| schema | v1，无迁移 |

数据版本817f677d-f7b2-4b42-bd4b-4211f86c200d；snapshot manifest SHA256 6ec09b9999585b26454b0b8f9f02c3eb3f40f5cf92af3f691bc5756be5d971d0。25权威表旧行逐字段全部保留，11旧原文文件字节未变；新快照38文件，恢复再导出逐字节一致。

## 实际验收

本机执行 `PYTHONPATH=src python3 -m unittest discover -s tests -v`：275项通过，0失败，含10项新增出行专项。旧经营测试43/45全库历史数量检查改为排除新travel-abroad后仍精确43/45；旧原文与案例不变。新检查包括字节/引文、7盘同ID、时序隔离、SQL候选不绑定、幂等、拒绝不可变改写和快照恢复。CLI真实读取6案例，WSGI API沿原app/service读取7盘；没有开放公网端口。

本机Git HTTPS缺少登录凭据，采用已连接GitHub接口上传；远端main精确SHA、文件blob和Ubuntu/macOS × Python3.11/3.12四CI仍须在提交后实际核对，不能以本地通过代替远端成功。证据见data/provenance/travel_validation.json。

## workflow审计

.github/workflows/tests.yml从初始化78d5b9a已存在，保留常规四环境回归。上一章临时business-ingest-staging.yml在26f0061新增、23bac5e删除，当前main仅有tests.yml。本轮不新增或删除workflow。完整SHA及用途见入库报告。

## 未完成

独立公历/节气/四柱及全面排盘、空亡马星、完整寄宫泛化、正式用神激活、专业断案和应期、SFT/LoRA、公众Web及现实预测评估仍未完成。正式问事沿QimenService.ask阻断，未提前训练、未引入其他古籍。历史入库报告保留原验收事实。


远端实际验收：内容提交 `1a5153325ba6221db8c41cb97f25d4a457f3887a` 已核对main一致；[Actions 39071724067](https://github.com/turnupmason/QimenLLM/actions/runs/39071724067) 的Ubuntu/macOS × Python3.11/3.12四job全部success。Ubuntu3.12日志实际Ran 275 tests / OK。原始字节、结构化文件和快照blob均按本地生成值核对；使用已连接GitHub Git Data接口非强制更新main，未新建workflow。此处记录已验收的内容提交；本验收文档后续提交本身仍按精确SHA另查CI，不用旧CI冒充新提交。
