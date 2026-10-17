# 当前项目状态

更新：2026-10-17。本轮《神奇之门·体育竞赛预测》，sports-competition/接收排序18，累计17份章级输入；源文明确第十二章，不混淆印刷章号与接收顺序。继续遵守AGENTS及总指令docs/user_instructions/master_spec_reaffirmed_2026-10-17.txt，旧原件保留，不重置阶段。

## 本章来源和案例

TXT26814原字节/11246字符/276行，末尾LF；SHA256 784f49224b8a540850dde469a0fe720d23ee4ab551fa9600dca6137eb4fb5a2b。uploads、SQLite BLOB、snapshot raw逐字节完整保存，Unicode框线/铺庚/⑥/以应地盘等原字不改。来源confirmed/user_attestation，不冒称软件亲自核实比赛或人物。

10完整语境组/8技术边界/4参考候选；7完整故事/7家族/7事件/7完整原盘、67过程记录/67证据。一般角色、同国号码取用过程、中立赛场远近主客与东道主语境分别保留，均reference_only，不默认日干/时干唯一取法或自动专业角色绑定。

第二例甲戌局仅有文字描述及初断，未给完整九宫盘；初断不挂乙亥盘，保持一个比赛事件及一个已给完整盘。第三例先试宫数，再八门，再九星的取舍保留。第四例十枚或十六枚原断不事后收窄。第五例90分钟1:1/加时1:1/点球决胜5:3按来源报告分阶段；离九铺庚规范星名None并标未映射，不擅校辅。第六例克罗地亚胜2:1原断与法国胜2:1结果明确分开，237行整段及精确字节分句隔离事后月令与干生克解释。第七例⑥原编号保留。

沿既有import_chapter/install_curated/import_cases/install_candidates及QimenService/CLI/WSGI读取；source_chart按本章SHA只读投影，63宫独立人工字面gold同时核对结构化盘与同ID服务读取。完整源表不等于全部规范星名已映射，程序未重排/复算或验证专业效力。没有schema迁移、新目录或workflow增删；旧章源文/curation/cases/gold及总指令不改。详见ingestion/SHENQI_SPORTS.md。

## 当前权威库

| 资源 | 数量 |
|---|---:|
| 书 / 章级输入 / 原始文档 | 1 / 17 / 17 |
| 概念索引 / 方法 | 2344 / 26 |
| 知识项 / 来源片段 | 1015 / 2833 |
| 完整故事 / 家族 / 事件 / 原书盘 | 85 / 82 / 91 / 90 |
| 案例记录 / 证据关联 | 1341 / 1664 |
| 来源审读历史 / 数据版本记录 | 24 / 80 |
| 正式角色rules / 训练任务 / 冻结release | 0 / 0 / 0 |
| schema | v1，无迁移 |

数据版本17df382d-d0bb-4e3b-95a4-4eb968dc8c36；snapshot manifest SHA256 1dd8fc85d71ef1d7aa27e5ca1bae462324516b17ee87ed37015e9b6ed73ad102。旧25权威表全部旧行逐字段仍在，16旧原文逐字节不变；43文件快照恢复再导出一致。资料接受与程序映射、专业编译和现实评估分开。

## 已实际运行的验收

本章18专项已通过，覆盖字节/引文/分句、63宫独立gold与同ID投影、甲戌缺盘、号码方法尝试、金牌候选值、比分阶段、胜队错断及后验隔离、铺庚未映射、候选条件不激活、CLI/WSGI真实读取、旧行/幂等/拒改/快照恢复。完整回归命令`PYTHONPATH=src python3 -m unittest discover -s tests -v`实际358项通过、0失败/错误；CLI实际读取7案、WSGI实际读取全部7盘。远端精确SHA四CI验收另记data/provenance/sports_validation.json，未验证部分不冒称完成。

通过已连接GitHub接口非强制更新main，按精确SHA逐blob核验并检查Ubuntu/macOS × Python3.11/3.12四CI；原有.github/workflows/tests.yml保留，无本章一次性workflow。历史workflow解释见ingestion/SHENQI_TRAVEL.md。

## 未完成

独立公历/节气/四柱/全面排盘、正式用神激活、专业断案与应期、模型训练/现实预测评估和公众Web仍未完成。正式问事只通过QimenService.ask，参考查询或阻断不算专业成功。未引入其他书、外部赛果或模型记忆改源。完成本章验收后等待用户下一章。


远端内容验收：`3363433473346717c576ddd0f57d0d880365a8e0` 已核对main一致、309文件blob匹配；[Actions 39080312629](https://github.com/turnupmason/QimenLLM/actions/runs/39080312629) 的Ubuntu/macOS × Python3.11/3.12四job全部success，四份日志均实际Ran 358 tests / OK。通过已连接GitHub接口非强制更新，未增删workflow。这里记录已实际验收的内容提交；本验收文档后续提交本身仍须按精确新SHA另查四CI，不以旧CI替代。
