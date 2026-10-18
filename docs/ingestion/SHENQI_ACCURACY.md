# 《神奇之门》奇门预测准确率评估：方法论增量入库

用户上传神奇之门_奇门预测准确率评估_精校完整版.txt，9177 UTF-8原字节/3105字符/37行，末尾LF。SHA256 `528174a11b617ab7d32b9c2a0a85e57a739851b4145f3a5bd544451857efbde3`；uploads、SQLite BLOB、snapshot raw逐字节保存。chapter_key=accuracy-assessment，接收排序22，未提供印刷章号不猜。confirmed/user_attestation，系统未独立外查引书、引语或现实准确率。

## 入库知识与完整语境

| 范围 | 原文行 | 保存方式 |
|---|---:|---|
| 标题与开篇实践主张 | 1–4 | 作者归属 |
| 三条高层次理由、比较与类比限制 | 5–16 | 三理由完整同组；保留“是否科学，尚待研究”，理论比较不替代实践 |
| 百分之七八十的两种含义 | 17–18 | 人/事比例与单人多事/一事准确程度分别保留原句和字节位置 |
| 出版成功例、错断与省略全错例 | 19–24 | 三立场同块保存，不遮掩差别 |
| 四类失准原因与总结 | 25–37 | 操作者、方法分歧、科学性、问事关系和取时结语逐段完整保存 |

13完整语境组、9方法/评估边界、22条参考知识项、50概念索引和1来源参考方法注册；每一非空段和全部37行覆盖。知识可通过已有学习/reference读取，不是只留文件。没有具体历史案、事件、原盘或实际实验，因此新增案例/事件/盘/案例记录/候选/评估run均0，不造百人数据、空case/gold/candidate附件或训练任务。

17行“根据我们的初步实践经验”的归属和“掌握得比较好、比较纯熟”条件保留。两种原述分母/程度不能简单合并；实际样本数、命中数、项目实测准确率为null。19行批评只报成功造成百发百中误解，21承认测错/反断，23承认略去完全失准，三段原文同组，不能只抽第一立场或据出版集推总体分数；原书省略失败的做法不授权本项目删失败。

## 方法与限制

29行分别保存五家族：起局（置闰/不置闰/拆补/交节及置闰时点）、八神参照系（追大值符或地盘六甲十时辰一宫）、九星旺相休囚与五行是否一致、中五寄宫（三类：永坤；阳艮阴坤；春艮生/夏巽杜/秋坤死/冬乾开）、格局与取用。每项精确原句带byte_start/byte_end，均reference_only_not_compiled、selected_default=null。未替换原有casting方法、星旺衰结果或默认寄宫，不以某派主张改旧源和gold。

刘广斌《奇门预测学》、锡孟樨《奇门法窍》、四库馆臣与列宁引述仅保存为本源内引文，不另导书、核定未给版本或补证。31行理论科学性仍待研究验证、33同刻多事/问时偶然性与关系经验、35取时联系全部保留。疲劳/熟练度等提议不自动洗掉错断；关系或好奇不改成拒绝问事、事后剔除或经验证概率；不以本章不用生时一般论述覆盖上章明确出生盘的来源范围。

## 接入、快照与回归

沿现有import_chapter/install_curated、QimenService.learning.learn/reference、CLI/WSGI，无新框架、schema迁移、目录或workflow；核心计算器和metrics未改。默认标注method_id为空、由context_group记录参考方法范围，沿既有参考标注语义；不伪编译以填字段。

```sh
PYTHONPATH=src python3 scripts/import_shenqi_accuracy.py
PYTHONPATH=src python3 -m qimenllm learn '百分之七八十'
PYTHONPATH=src python3 -m qimenllm reference accuracy_rate_meanings_reference --filters '{}'
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

15专项实际通过：原文/全部字节引用/全行上下文、两种口径与无百人样本、三出版立场、五分歧族、限制与归属、无新案例/书/规则、实际CLI/WSGI/来源确认/完整assessment读取、旧计算结果相同与metrics仍无实测率、旧行/幂等/坏源与哈希拒绝、快照逐文件恢复。开发初次测试将参考标注按编译method_id筛选导致0行，已按既有来源revision查询修正测试，不改运行语义或数据；详见validation。全量`PYTHONPATH=src python3 -m unittest discover -s tests -v`实际429项通过、0失败/错误；精确SHA四远端CI随后按实测写入。

数据版本b79a2c25-dd1e-4ecd-b0cb-10956fe080de，manifest SHA256 ed62a8ee475dee77a8175a5efffe3542b3904614b996407665eff776f6fc2e0b。25表旧行逐字段均在、20旧原文字节一致、47快照文件恢复再导出一致。累计21输入、2530概念/30方法、1109知识项/3163来源片段、511语境组/342边界；97故事/93家族/104事件/102原盘、1549记录/1872证据、194当前候选/201历史与39编译符号族保持。正式rules/训练/release均0。

既有`.github/workflows/tests.yml`保留，本次无workflow增删。历史一次性workflow的确切路径/增加与删除commit已在SHENQI_TRAVEL.md审查，本轮未重新创建。未改旧章source/curation/cases/gold/验收报告、旧总指令或冻结规则。独立公历、专业用神/断案/现实准确率与训练尚未完成。
