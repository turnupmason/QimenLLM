# 附录二《从编辑、作家到易学专家》：精校独立来源接收

本次TXT7221 UTF-8原字节/2495字符/17行LF，末尾LF，SHA256 `b9f8fc44d2174f54cc962ed31dd794262cb1d54a1e6060fcdf279570e8abb716`。作者署名宛北布衣，被报道者张志春；确认依据user_attestation，软件不冒称外查履历/职务/科学性。原文件分别存uploads、SQLite BLOB、snapshot raw；appendix-biography-clean/排序25仅为技术接收键。

## 与旧源逐篇核对

旧复合源SHA256 df4a878fe719c57ef9138608a24ff12bda6c0cdbdfd577247badbdf6935fd340的140–171行，与新文件1–17行去空白并只排除旧155行明确页眉后，2478字符完全一致，词句差异0。biography_curated.json及真实context_group保存旧新选择器、完整引用、对照策略/哈希与旧5语境键。旧CRLF字节及其全部知识记录不改；新LF字节保持独立，不用相等比较覆盖源。

已有语境包括篇名署名、1996会议开篇、1997访问与履历书目、六大论、笔名和访问结语，本次全部对应。六大论及人物信息已在原附录入库，因此不重新增加概念、方法、理论或人物实体。旧157行/新11行末尾均为“代表人物之”，不擅补“一”；所有原有日期、职务、引书和赞誉归属原报道，不当当前任职、机构背书或新实证。

## 增量范围与现有接入

只增加一个原始来源输入、1完整来源对应语境及1来源边界（2条reference_only注释）。沿已有import_chapter/add_annotations，这是IMPORT_PROTOCOL原有参考标注链；没有新方法不额外注册阅读方法，无新case/gold/candidates空壳或新目录。事实/人物概念、方法、案例、事件、盘、候选和旧5语境均不复制。来源输入累计24不等于24篇独立理论或24次预测。

```sh
PYTHONPATH=src python3 scripts/import_shenqi_biography.py
PYTHONPATH=src python3 -m qimenllm learn '精校来源'
PYTHONPATH=src python3 -m qimenllm reference biography_clean_source_reference --filters '{}'
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

现有QimenService学习/reference、CLI和WSGI实际读取新全文、source确认及旧对应关系；专业绑定空、实测准确率空。9专项通过，涵盖源字节/双选择器/2478字符比对、旧5语境在库、无重复实体/案例/候选、参考标志与断尾、实际调用、重放/坏源/坏关联拒绝、旧行及快照恢复。全量`PYTHONPATH=src python3 -m unittest discover -s tests -v`实际469项通过、0失败/错误；精确SHA四CI随后实测补录。

版本cd6ca5ad-6fa3-449a-bc51-9de45014fde3，manifest SHA256 ea4e35b1f02ad682b312abcda2276dca9f51cd25aba4e5b1884cde961dd71d48。25表全部旧行逐字段保留、23旧原文逐字节一致、50文件快照恢复再导出一致。累计24来源、1177知识项/3267片段、551语境（含来源对应）/368边界；2674概念/32方法/39编译族、98故事/94家族/106事件/104来源盘记录、1579记录/1902证据、196当前候选/203历史不变。正式rules/训练/release0，无schema、目录或workflow增删；旧source/curation/cases/gold/报告和用户总指令保留。历史workflow审查见SHENQI_TRAVEL.md；未声称全书收齐、模型掌握或独立现实准确率。
