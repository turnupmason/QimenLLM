# 《神奇之门》后记：完整语境增量入库

用户上传神奇之门_后记_精校完整版.txt，5285 UTF-8原字节/1793字符/21行，末尾LF。SHA256 `ae609b92f0e1e1f475bece88879e811f7ded8161035e246003ecaa081f18a4eb`。uploads、SQLite BLOB、snapshot raw逐字节保存；afterword/接收排序23，无印刷章号不补。confirmed/user_attestation，不冒称系统外查了作者经历、历史宗教解释或人物职务。

## 完整语境

| 语境 | 原文行 | 保留内容 |
|---|---:|---|
| 原题 | 1–2 | 后记 |
| 前作背景 | 3–4 | 1993年6月作家出版社出版《未知之门》与邵伟华研究介绍 |
| 本书目的 | 5–6 | 理论与应用、传统哲学技术、取合理精华弃迷信、去神秘化与书名解释 |
| 神秘化原因 | 7–8 | 作者提出的统治、谋生保守及儒道宗教交织三类解释 |
| 科学与技术 | 9–14 | 自然哲学、社会制度与李约瑟难题、吴大猷报刊转引、反对义理与应用割裂连续三段 |
| 纲领及自限 | 15–16 | 科学价值/技术特征愿景连同初步、幼稚、不成熟与欢迎批评完整同段 |
| 学习与实例致谢 | 17–18 | 资料、同仁、学员、师友名单与部分同仁提供实例的自述 |
| 作序致谢 | 19–20 | 唐明邦、叶梓铨及原书所述职务 |
| 署名地点 | 21 | 张志春于石家庄，无日期 |

新增9完整语境组、7来源边界、16参考知识项、47概念索引、1参考方法注册；全部21行及每一非空段覆盖。无历史案例、事件、盘、逐案供稿表，不增加cases/events/charts/records/candidates/gold或训练任务。书内说人人可掌握是作者论述，不转为项目能力保证。

## 来源与解释边界

1993是前作出版时间；1998年3月20日是《光明日报》《如何面对“李约瑟难题”》转引时间，不推本书出版、版次或署名日期。《未知之门》《中国科学技术发展史》和报刊仅为本篇提及，不另导新文献。吴大猷观点保留“转引自”、人名、报/日期/篇名与完整原段，未冒称已核原报。历史宗教/政治社会解释保留作者归属，不编排盘或取用规则。

研究目的与初步幼稚不成熟的限制相互关联，不只抽科学价值或成功实例而丢掉作者自限。师友十人名单、两位作序者和其职务原述完整保存，致谢未给哪人提供哪例，不猜与旧案同名者相同、不标当前任职或本项目背书。该书则是、我会的王修义师傅等字面照源，不改指代/会字或补组织。作者署名无年月，日期空；收到后记不代表已依据全书目录核齐材料。

## 实际接入与恢复

沿import_chapter/install_curated、QimenService.learning.learn/reference、CLI/WSGI；默认参考标注、无编译/正式角色激活，不改算法和metrics。无schema迁移、新目录或workflow增删。原.github/workflows/tests.yml保留；历史一次性工作流的精确路径与增加/删除提交已见SHENQI_TRAVEL.md，本轮未再建。

```sh
PYTHONPATH=src python3 scripts/import_shenqi_afterword.py
PYTHONPATH=src python3 -m qimenllm learn '极其初步的'
PYTHONPATH=src python3 -m qimenllm reference afterword_science_technology_reference --filters '{}'
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

13专项通过：源字节/引文/全行、前作日期与无日期署名、目的自限同段、三类解释归属、连续理论技术语境与二手引文链、致谢名单/职务边界、源字面、无新案例/书/规则/训练、confirmed学习/CLI/WSGI真实调用、计算不变/空实测指标、旧行/幂等/坏源拒绝/快照恢复。全量`PYTHONPATH=src python3 -m unittest discover -s tests -v`实际442项通过、0失败/错误；精确SHA四CI随后按实测记录，不假称远端成功。

数据版本f916ccff-c72c-4589-af31-c6edf805ffb1，snapshot manifest SHA256 171e633f1e2dd4f3ae5b6c7015a310da13e0191b87454b1590e23aaa1ab92051。25表所有旧行逐字段保留、21旧原文逐字节相同、48快照文件恢复再导出一致。累计22输入、2577概念/31方法、1125知识项/3180来源片段、520语境组/349边界；97故事/93家族/104事件/102原盘、1549记录/1872证据、194当前候选/201历史和39编译族未改。正式rules/训练/release均0。旧章原文/curation/cases/gold/验收报告及用户总指令保留；独立历法、专业问事和现实评估等门槛未变。

远端内容验收：`99141d287c8640d463d86aeaa07a6b5922197e57` 已核对main一致、363文件blob匹配；[Actions 39083543472](https://github.com/turnupmason/QimenLLM/actions/runs/39083543472) 的Ubuntu/macOS × Python3.11/3.12四job全部success，四份日志均实际Ran 442 tests / OK。通过已连接GitHub接口非强制更新，未增删workflow。这里记录实际验收的内容提交；本验收文档提交自身须按精确新SHA另查四CI，不以旧CI替代。
