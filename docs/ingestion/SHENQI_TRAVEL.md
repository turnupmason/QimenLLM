# 《神奇之门》出行出国预测：增量入库

来源为用户上传 `神奇之门_出行出国预测_精校完整版(1).txt` 原始UTF-8字节，31026 bytes / 350行，末尾LF，SHA-256 `c273c803eb78a02cfb3c6c00065da81312c1851a679a1e3bca4911acdbc3bc55`。原字节存uploads、SQLite BLOB和snapshot raw，不转录、不改框线。技术键travel-abroad、sequence13，不推断印刷章号。来源按user_attestation confirmed；不是系统亲自查访。末句“只是对这一点当时没有细看”按上传结束处保存，不补文。

## 文献与案例

第一节完整保存方向生克、车船飞机、出发时间、未动身问归期、在外吉凶及庚格/千里内外星法。16完整语境组覆盖全部非空行；8条件候选全部reference_only。交通工具、预测阶段、距离、日阴阳、合/墓/空亡例外保留原文，条件未知不能视为满足，尚不自动激活专业用神。

| 案例 | 原盘 | 时序与归属 |
|---|---:|---|
| 一 坐飞机安全 | 1 | 咨询日1月17日与拟起飞1月20日区分；月干代兄，不默认日干 |
| 二 出行吉凶 | 1 | 张粤执行；预断与后来失散、失物、破财报告分开 |
| 三 出行安全 | 1 | 杜新会执行；劝阻、司机对话、实际轮胎损坏/人员安全按原顺序 |
| 四 出国 | 1 | 杜新会初测，半年后杜新会与张粤读同一历史盘；电话反馈、续断依次保留；未婚不等于独立确认原断六月分手 |
| 五 外出旅游 | 1 | 取消出行与其他人缺车未成分别保存，不说实际发生车祸 |
| 六 出国考察 | 2 | 6月21日电话盘、6月24日拟出发盘属于同一次旅行；7月15日报告后雨情解释是后置分析，不造18点实际起飞第三盘 |

6故事/6家族/6事件/7盘，99逐段原文记录/99原文证据。全文故事由source_ranges保留，盘面原字与分析不丢失。记录显式作者内容，不虚构内心推理；保守首次预测输入不开放未知阶段、分析、反馈或整案背景。未生成训练任务。

## Unicode原盘投影

`QimenService.case_chart`沿现有只读原盘入口，按本章确切SHA启用框线解析。每宫保留原文三行、列号、出处；派生四列字面值不替换原文。63宫全部以同一chart_id读取，非独立公历复算。例六第一盘兑七“芮禽己”保留芮与附记禽、携干未知；中五己与兑七己照原字，不修盘、不根据结果推断。没有跨流派算法或schema迁移。

## 执行与验收

`scripts/import_shenqi_travel.py`复用import_chapter → install_curated → import_cases → install_candidates；默认同步GitHub，local-only只用于受控维护。新源模块和JSON文件沿上一章命名方式进入既有目录；没有新建workflow或数据库体系。旧25张权威表全部逐字段检查为新快照子集，11个旧原文文件保留。快照可恢复、再次导出一致；正式rules/training_tasks/releases仍0。

本地完整回归及远端提交/CI的实际验收结果见STATUS及data/provenance/travel_validation.json；未完成远端核验前不能把本地通过称为GitHub成功。

## 用户投诉的workflow审计

`.github/workflows/tests.yml`早在初始化提交 `78d5b9a4c27dd4ba66fed1b2e322785c75c64558` 已存在，作用是Ubuntu/macOS × Python3.11/3.12四环境常规回归，应该保留。

上一章曾临时添加 `.github/workflows/business-ingest-staging.yml`，新增提交 `26f00618480f20f21987b9c431b439224e821632`，仅监听当时经营章节的工作分支与该文件路径，用于恢复旧快照、执行导入、全回归、导出并提交快照。它是当时借助Actions执行入库的一次性作业，不是每章资料入库必须另建的目录或文件；移除提交为 `23bac5e03f8dad08132a97bc2688be1d63d38a72`，当前main已无此文件。本轮仅保留原有tests.yml，不删除历史、不再添加一次性工作流。


远端实际验收：内容提交 `1a5153325ba6221db8c41cb97f25d4a457f3887a` 已核对main一致；[Actions 39071724067](https://github.com/turnupmason/QimenLLM/actions/runs/39071724067) 的Ubuntu/macOS × Python3.11/3.12四job全部success。Ubuntu3.12日志实际Ran 275 tests / OK。原始字节、结构化文件和快照blob均按本地生成值核对；使用已连接GitHub Git Data接口非强制更新main，未新建workflow。此处记录已验收的内容提交；本验收文档后续提交本身仍按精确SHA另查CI，不用旧CI冒充新提交。
