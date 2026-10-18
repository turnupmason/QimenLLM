# 附录三《现场预测表演纪实》：精校叙事与所供九宫重排表

新文件15047 UTF-8原字节/5513字符/140行LF，末尾LF。SHA256 `0649e0a09cc615c9c379e3fb5f43a20038329546ec8a829dbbdac11b8322981e`；作者杜新会、末尾张志春按语分别保留，confirmed/user_attestation。uploads、SQLite BLOB、snapshot raw完整存源；appendix-demo-clean/接收27与书中篇次三分开，旧二/一顺序和键保持。

## 叙事对应与时序

旧复合源df4a878fe719c57ef9138608a24ff12bda6c0cdbdfd577247badbdf6935fd340的172–276与新1–140，分别分开旧241–254图碎片、新91–107重排表、旧230明确页眉后，去空白叙事4387字符完全相同。完整引用、双侧选择器、排除规则与hash及30条记录新旧范围/ID/kind/phase存在demo_curated.json和真实context_group。

仍是原case-ea86d002d73e8c074ba86bccdab0a73833d4690b8dda2a7230547b15bfabe416的一个完整现场故事，出版与事故两事件共家族；三人会后来访不变三个求测案例。现场首断数量后才给书名，北/东北建议与会后编辑信只北分别保留。53官讼/小辈破财初断、55–57否定及本人澄清、59车祸续断、61过去事故反馈保持顺序。81约三千元不确认官讼及原因，83/85春天两死三伤属于会后续断/反馈，不倒灌59。75/79蔚然信与9月18日签署、140的2000年2月第一书改名出版按语后置，“全部应验”仍为按语评价，不扩大未报分支。108–138编号解释保持post_feedback；原首次视图、case/event/record/chart行逐字段不动。

## 新文件提供的九宫表示

91行明写“九宫盘面（根据提供的文字原盘重排）”。因此这不是新独立原图/扫描，也不覆盖旧残缺列位。92–107按所供表抄存9宫36个字面单元，demo_gold.json独立手抄全36单元、表行与列定位逐项核对。原述21:30/四柱/白露上元/阴9/甲午/天心/开门只保存，不校历。

| 宫 | 八神原字 | 门位或中宫原字 | 星位原字 |
|---|---|---|---|
| 巽四 | 地 | 伤乙 | 任癸 |
| 离九 | 武 | 杜丁 | 冲戊 |
| 坤二 | 虎 | 景癸 | 辅丙 |
| 震三 | 天 | 生乙 | 蓬丁 |
| 中五 | — | 中宫原文：壬 | — |
| 兑七 | 合 | 死戊 | 英庚 |
| 艮八 | 符 | 休辛 | 心己 |
| 坎一 | 蛇 | 开庚 | 柱乙 |
| 乾六 | 阴 | 壬惊丙 | 芮辛 |

生乙与壬惊丙等均不按算法/后文擅改；center_text与门位区分，不把中宫原文壬变成门或新神。九宫对应所供表，不冒称独立程序复算或本书纸本一致。

通过现有QimenService.reference、CLI/WSGI以palace查询新表，每宫返回本次source hash和确切字节片段/表列。学习整篇返回与旧case/event/chart_id/记录的关系。两个旧chart_id保留旧片段且case-chart仍not_covered，不拿新重排表升级其状态。没有创建新case/event/chart/候选或规则；新表是来源参考知识，自动角色绑定空。这样可读新表，也无需改旧数据/旧gold/旧测试或新增投影器。

```sh
PYTHONPATH=src python3 scripts/import_shenqi_demo.py
PYTHONPATH=src python3 -m qimenllm learn '附录三精校来源'
PYTHONPATH=src python3 -m qimenllm reference demo_clean_palaces_reference --filters '{}'
PYTHONPATH=src python3 -m qimenllm reference demo_clean_palaces_reference --filters '{"palace":5}'
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## 实际验收

14专项通过，涵盖全部新旧字节选择器、4387叙事对照、30原记录文本/phase/ID对应、原case/2event/chart关联、重排声明和验证范围、9宫36独立gold及单元出处、否定/续断/信/后加按语、事前隔离与旧not_covered、无重复业务表、4参考注释与篇次、逐宫查询/来源确认/learn、真实CLI/WSGI、幂等/坏源/坏关联/旧行及快照。全量`PYTHONPATH=src python3 -m unittest discover -s tests -v`实际493项通过、0失败/错误；精确SHA四CI随后实测补录。

版本9fe01f72-44f1-4b6d-b793-f2b9b748f16c，manifest SHA256 60c681252486135c1dd5b730d1d31677757437d9b01f1e7e330624a597195401。25表旧行逐字段保留、25旧源逐字节相同、52快照文件恢复再导出一致。新增2语境/2边界，累计26来源、1183知识项/3275片段、554语境/371边界；2674概念/32方法/39编译族、98故事/94家族/106事件/104来源盘记录、1579记录/1902证据、196当前候选/203历史不变。正式rules/训练/release0，旧source/curation/cases/gold/报告和总指令不改，无schema/目录/workflow增删。原tests.yml与source_chart.py保持，历史工作流审查见SHENQI_TRAVEL.md。专业问事、独立历法/现实效力和模型训练等未完成，不因重排来源冒称完成。

远端内容验收：`b2eb8ca22ea7007ca77ffc713720c2ae001f7920` 已核对main一致、401文件blob匹配；[Actions 39086352970](https://github.com/turnupmason/QimenLLM/actions/runs/39086352970) 的Ubuntu/macOS × Python3.11/3.12四job全部success，四份日志均实际Ran 493 tests / OK。通过已连接GitHub接口非强制更新，未增删workflow。这里记录实际验收的内容提交；本验收文档提交自身须按精确新SHA另查四CI，不以旧CI替代。
