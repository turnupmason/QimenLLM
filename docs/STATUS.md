# 当前项目状态

更新：2026-10-17。本轮《神奇之门·钱物丢失预测》，技术键lost-property/排序15，不推断印刷章号；累计14份章级输入。用户重申Master Specification原件已在现有user_instructions目录按字节保存，旧版原件保留。新附件除排版仅去掉旧末句立即启动Phase0命令，本轮继续既有项目，不重建/重置或启动训练。

## 本章来源与工程

TXT34197字节/13507字符/362行，SHA256 ed3c80f32c213563bf35d9f9790e330ea04e4def404f6e6ca904006a94a9eaf9。uploads、SQLite BLOB与snapshot raw保留全部原字节及末尾编辑附记；收到的例三乙休庚不二次更改，不声称见过原扫描。confirmed/user_attestation，系统未亲自外查。

15完整语境组/6技术边界/5来源候选，均reference_only。8故事/8家族/8事件/8原盘、92过程记录/92证据；一般失主/失物、找回、位置、偷盗遗忘、应期分条件，案例多取法不改成无条件绑定。例三先盲问后透露皮衣；例六每次反馈/找不到/续断按说话者原序，最后车内位置事前未断出；例七先旅行后身份证，张志春按语在反馈后，实际旅行结局未报；例八未找回仅截至原书叙述时。混合问答整段保留并给出逐句说话者和准确字节出处；作者对被盗问题的回答不升级为外部核实。

三行原字标签盘沿source_chart与QimenService同ID投影，72宫同时和独立字面gold核对；中五原干、门星前缀、原始三行/列号均保留。新增脚本import_shenqi_lost.py复用import_chapter、install_curated、import_cases、install_candidates；CLI/WSGI读取沿既有服务链，无schema迁移、新目录或workflow增删。见ingestion/SHENQI_LOST.md。

## 累计权威库

| 资源 | 数量 |
|---|---:|
| 书 / 章级输入 / 原始文档 | 1 / 14 / 14 |
| 概念索引 / 方法 | 2173 / 23 |
| 知识项 / 来源片段 | 930 / 2509 |
| 完整故事 / 家族 / 事件 / 原书盘 | 67 / 64 / 73 / 71 |
| 案例记录 / 证据 | 1144 / 1465 |
| 来源审读历史 / 数据版本记录 | 21 / 65 |
| 正式角色rules / 训练任务 / 冻结release | 0 / 0 / 0 |
| schema | v1，无迁移 |

数据版本da05c74d-cc3d-4642-b37b-b575f952353f；snapshot manifest SHA256 6f6c7fa5e2c06f7bd878233e1aea5d44df785d6b6b9ac743e65bf1b9ed9df7f0。旧25权威表逐字段全部行保留、13份旧原文逐字节不变，40文件快照恢复再导出一致。旧章节source/cases/curation/gold不覆盖，旧总指令原件不覆盖。

## 已实际验证

`PYTHONPATH=src python3 -m unittest discover -s tests -v`：本机307项通过，0失败/错误，含本章16专项。覆盖全部原字节及来源/分句、72宫独立gold与服务投影、盲问与多轮时序、说话者、来源编辑附记、5候选条件不激活、全部旧不可变行保留、幂等/拒改、恢复、CLI及WSGI共用入口。没有用阻断的正式ask或参考候选匹配冒充专业预测成功。

新总指令文件SHA256 e3988844b89e78cce3e4305e65e9d681e4c3cc3e62ed24535c90afe7afd72e57，39123字节；档案docs/user_instructions/master_spec_reaffirmed_2026-10-17.txt与附件逐字节相同。

远端同步通过已连接GitHub接口非强制更新main；提交后须按精确SHA、所有文件blob与Ubuntu/macOS × Python3.11/3.12四CI实际核验。尚未核验前不宣称远端成功。数据验收见data/provenance/lost_validation.json，本地回执work/github-sync.json。

## 能力边界及下一步

独立历法/节气/四柱和全面排盘/空亡马星/寄宫、正式用神激活、专业综合断案/应期、模型训练和现实预测评估、公众Web均未完成。正式ask仍由QimenService阻断；文献接受、结构化投影、程序复算和模型专业效果分别报告。没有引入其他古籍或家庭GPU连接。历史验收报告保留，完成同步后继续等用户下一章。


远端内容验收：`a86dccb3fcb46d221d29706b7a1ce91c91ec2586` 已核对main一致、273文件blob匹配；[Actions 39073906226](https://github.com/turnupmason/QimenLLM/actions/runs/39073906226) 的Ubuntu/macOS × Python3.11/3.12四job全部success，四份日志均实际Ran 307 tests / OK。经已连接GitHub接口非强制更新，未增删workflow。此处记录已实际验收的内容提交；本验收文档后续提交本身仍须按精确新SHA另查四CI，不以旧CI代替。
