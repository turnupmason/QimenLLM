# 2026-10-17：CI 随机标识碰撞

原失败：[Actions run 39046797275](https://github.com/turnupmason/QimenLLM/actions/runs/39046797275)，提交31b40954a1d6550bd8dfa0d63d1f200eec734ca1。macOS/Python 3.11执行176项，1项失败；另外三项job被默认矩阵fail-fast取消，其unittest步骤均成功。不是四项独立测试失败。

疾病例1测试搜索整个before_prediction JSON，禁止年份1991。随机修订ID参与来源摘要生成，实际source_id为`span-43a2315a84b68c425eb3e38ab559e78fe2eac199155022a22e4ca78404c805b2`，其中数字触发误报。视图仍为4条合法事前记录；日志没有显示后续病史进入正文。反向的“应包含某年份”检查也可能从ID误通过，因此同时修复疾病、婚恋与应用案例的同类内容检查。

## 修复与限制

tests/support.py的case_content_text保留整个JSON结构，只将11种明确身份/摘要字段中格式完整匹配的UUID或前缀摘要值换为占位标记。字段名、源文、locator、非标识数字、未知字段及其任意嵌套内容仍可检索；格式错误的source_id也不隐藏。此辅助函数只用于测试断言，没有修改正式QimenService → case → inspect_case输出或入库规则。原有来源字节、时序、字段缺失、记录数量与多盘关联断言保留；不是通用语义泄漏检测器。

新增6项辅助函数测试，覆盖合法元数据碰撞、已知年份不能由ID满足、各嵌套路径的真实年份、非法ID/未知字段、正文摘要形文本与reasoning-2定位符、结构与输入不变。新增1项实际疾病事前视图测试注入原失败ID，证明旧断言会误报、新断言不误报，并证明意外background中的真实1991仍被发现。

workflow仅新增strategy.fail-fast:false。保留四个OS/Python组合、完整unittest命令和失败退出，不使用continue-on-error、不删失败测试。Node20弃用提示不是此次失败原因，未扩大依赖升级范围。

## 已实际执行

环境为云Linux/Python 3.12.14。完整日志在忽略的artifacts/ci-random-id，原失败日志同目录保存。

| 命令（项目根目录） | 实际结果 |
|---|---|
| `PYTHONPATH=src python3 -m unittest discover -s tests -p test_case_content_assertions.py -v` | 6项通过 |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p test_health_cases.py -v` | 16项通过 |
| `PYTHONPATH=src python3 -m unittest discover -s tests -v` | 183项通过，0失败 |
| `PYTHONPATH=src python3 -m qimenllm audit` | ok:true，errors:[] |
| `PYTHONPATH=src python3 -m qimenllm export-snapshot` | 成功，全部快照无Git差异 |
| `git diff --exit-code -- data src` | 退出0，权威数据及正式代码无改动 |

数据版本ec317e3d-b24d-4cd9-83c0-4dfed96857fb，导出manifest摘要455b9be07b1b0f792c9824278629d6ea8236c0d5e5243eeddc9cf896f2479c76不变。schema v1无迁移；原文、整理、gold、分组不改，未训练模型。知识仍为7份输入/13完整故事/14事件/13原盘，正式问事仍blocked，不产生新的专业能力声明。

本地结果不能代替跨平台验证。推送后按新main SHA读取push workflow及job，验收必须正好四个组合均completed/success。实际远端证据以本提交GitHub Actions及最终交付消息链接为准，同步SHA与run/job信息另存忽略的work/github-sync.json；不将本修复前的失败历史抹去或改称成功。
