# 附录一《学习奇门遁甲并不难》：精校独立来源

本次TXT11761 UTF-8原字节/4039字符/51行LF，末尾LF；SHA256 `10db674c708186c6408c9d38228b066456ed71adb6e5939e2e1102e2a2df15ef`。作者张志春，confirmed/user_attestation。完整保存uploads、SQLite BLOB和snapshot raw。书中篇次一与技术接收排序26独立；用户先给附录二（接收25），本次没有重命名或重排旧键。

## 同文核对和既有内容

旧复合源df4a878fe719c57ef9138608a24ff12bda6c0cdbdfd577247badbdf6935fd340的77–139行，与新1–51行去空白并仅排除旧93明确页眉后3988字符完全一致；包含附录总题，第一篇篇体3986字符。新旧选择器、哈希、完整引文、比较策略/哈希及14旧语境键存于learning_curated.json和真实context_group，旧CRLF源不覆盖。

已有四难（定局/起局/断卦/定应期）、三原则（化繁为简/去伪存真/规范统一）、三目标及研究方向、作者拆补按交节/时家排宫/中五寄坤二/天盘八神取法均完整保留。五十分钟以蔡敦祺已有其他奇门基础为条件，一般五小时/较置闰准确等归属作者经验，不生成项目成绩、学习保证或新算法默认。原字面“连门也人不了”不擅校为入不了，书内引文/刊载说明不变成外部书刊导入授权。

新45/47/49行学员摘要分别关联business-case-12、employment-election19961027、lost-case-07和既有family及来源哈希。卢圣湘抽奖、尚瓴吉选举、赵国葆身份证已经在旧章保存，不克隆故事、独立事件、盘、结果或预测次数；新摘要无盘，不移植旧图当本文件给了图。

## 增量与真实接入

仅新增一个来源输入、1整篇来源对应语境和1边界（2条reference_only注释），经已有import_chapter/add_annotations保存。没有新知识实体不再调用编译器注册方法；没有新案/候选不建空case/gold/candidate文件。原理论/概念/方法/案盘/候选保持，不启动训练。

```sh
PYTHONPATH=src python3 scripts/import_shenqi_learning.py
PYTHONPATH=src python3 -m qimenllm learn '附录一精校来源'
PYTHONPATH=src python3 -m qimenllm reference learning_clean_source_reference --filters '{}'
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

10专项通过：新原字节与双侧引用、3988全文比对、14旧语境真实解析、未重复方法/实体/案盘/候选/训练、2注释参考标志和原字面、真实CLI/WSGI/学习与确认、幂等及坏源/坏关联拒绝、旧行审计、精确快照恢复、篇次/接收排序与3家族真实关联/教学条件。全量`PYTHONPATH=src python3 -m unittest discover -s tests -v`实际479项通过、0失败/错误；精确SHA四CI随后按实测补录。

版本5b8798d1-d3bd-4393-b8b8-f07552fc4bdf，manifest SHA256 cb587698b63189caa0d6dee6defd1d090e42cf7547c7839ad5afe12e21d68b05。25表旧行逐字段全部保留、24旧源逐字节一致、51文件快照恢复再导出一致。累计25来源、1179知识项/3270片段、552语境（含来源对应）/369边界；2674索引/32方法/39编译族、98故事/94家族/106事件/104来源盘记录、1579记录/1902证据、196当前候选/203历史不变。正式rules/训练/release0；无schema、目录或workflow增删，旧source/curation/cases/gold/验收报告及用户总指令保留。历史workflow审查见SHENQI_TRAVEL.md。不由同文新增来源宣称全书收齐、模型掌握或现实准确率。

远端内容验收：`ec82f26b2da4ca6d23bb6ce425592c04760952fc` 已核对main一致、392文件blob匹配；[Actions 39085624927](https://github.com/turnupmason/QimenLLM/actions/runs/39085624927) 的Ubuntu/macOS × Python3.11/3.12四job全部success，四份日志均实际Ran 479 tests / OK。通过已连接GitHub接口非强制更新，未增删workflow。这里记录实际验收的内容提交；本验收文档提交自身须按精确新SHA另查四CI，不以旧CI替代。
