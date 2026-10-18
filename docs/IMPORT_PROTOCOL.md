# 下一章的接收与导入

用户下一条消息可以给《神奇之门》的章节名、完整正文和实际有的页码/版次/图盘。没有提供的作者/版次/页码不强迫补、不猜。分多条发可注明“本章未完”，最后注明“本章结束”；在明确完整范围后统一标注。保存收到的全部原文，不为增加记录数拆散故事。

Codex 将按 KNOWLEDGE_POLICY 保存、审读和整块标注，然后运行审计及相关回归，报告资料/知识/规则/案例各自覆盖。下面为新章节的一般导入示例；首章已实际入库，专用重放流程见文末。

```sh
PYTHONPATH=src python3 -m qimenllm init
PYTHONPATH=src python3 -m qimenllm import-chapter work/chapter-001.txt \
  --book-key shenqi-user-edition-1 --book-title 神奇之门 \
  --chapter-key chapter-001 --chapter-title '用户提供的实际章名' \
  --sequence 1 --origin '用户本项目输入'
PYTHONPATH=src python3 -m qimenllm audit
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

用户已统一确认既往及未来资料。维护CLI和各章脚本默认confirmed，无需再加`--confirmed`或请求人工二次确认；`--unconfirmed`只供声明范围外的工程测试。既有七份资料已追加用户确认审计，新章沿同一政策。同文重入返回duplicate与同一source/revision，不生成新正文；声明幂等追加review。不同文不会替换，须显式`--revision 2`等下一版本。原文文件以bytes读取，不经过shell转义或字符替换。

结构化注释由 Codex 精读后形成 JSON 数组，CLI：

```sh
PYTHONPATH=src python3 -m qimenllm annotate REVISION_ID work/annotations.json
```

每项字段为 category、byte_start、byte_end、locator、payload（对象），可选 method_id。byte 范围必须在 UTF-8 字符边界，locator 来自实际段落/页码。标注按相同 JSON 内容幂等，默认 structured=1 / compiled=0 / reference_only=1。需编译的真实规则在已实现相应条件/算法和测试后单独维护，标注不会凭空造可执行奇门规则。

目前文本导入、全章索引和结构标注已可运行；扫描图片/复杂原盘解析、自动章节理解、自动规则编译尚未实现。收到图片时必须保留原始附件及另行实现有哈希的媒体导入，不把 OCR 当原文覆盖。

用户后续要求每次数据更新同步 GitHub。上述 import-chapter / annotate 现在保存成功后会自动导出并尝试同步指定私有仓库；网络/权限失败时输出 pending、返回退出码2，已保存资料不回滚。可访问 API 时运行 `PYTHONPATH=src python3 -m qimenllm sync --message 'Update source data'`；当前受限会话由 Codex 按 GITHUB_SYNC 使用连接器核验私有状态，再完成实际 Git push 与远端 commit 核对后报告完成。私有仓库首次上传已成功。

## 已接收首章的可复现重放

本次确切原文、整块整理及203个来源对照已版本化。新设备优先 restore-snapshot；要独立重建首章可运行：

```sh
PYTHONPATH=src python3 scripts/import_shenqi_chapter01.py
```

脚本从仓库真实原文字节快照读取，校验确定SHA，按相同book/chapter键导入，再安装精读的chapter01_curated.json。作者/版本未提供不补，confirmed=true；当前声明已应用后，同文重放不增加正文、概念、编译条目或数据版本。不同哈希拒绝，不用于下一章。默认尝试GitHub同步；受限网络按GITHUB_SYNC由Codex完成推送。

可信维护过程中可用 --local-only 分阶段检查或针对临时库重建；这会明确输出github_sync=pending，不能据此交付。全部工作完成后必须导出当前快照、测试、推送并核对远端。脚本不执行训练、不读取其他书或旧项目。

首章当前已按用户声明确认，旧pending审计作为历史保留并由最新confirmed覆盖，不再等待校勘确认。后续章节仍按用户输入顺序，不能直接套用首章算法填缺失规则。初次导入历史见ingestion/SHENQI_CHAPTER01.md，现行接受状态查最新source_reviews。

## 第二章重放

```sh
PYTHONPATH=src python3 scripts/import_shenqi_chapter02.py
```

只接受本次第二章确切原文字节SHA，保留已有book键、chapter-02和顺序2；按用户长期声明confirmed。安装使用显式chapter02 compiler profile，分别保存上下文、技术边界、完整演算例及8编译族。不自动读其他书，纸上十步仅流程参考，公历转换没有给算法就不编造。

跨章运行需要首章既有数据：新设备优先恢复完整current快照，或分别重放两章脚本。--local-only只供分阶段维护/临时验证，会输出pending；最终仍必须导出、测试、push和远端核对。新增结构化JSON及来源/验收也纳入自动同步的受控目录。新章继续按用户完整章节输入，不把第二章两张教学盘当历史断案或训练反馈。

## 第四、第五章合并附件重放

```sh
PYTHONPATH=src python3 scripts/import_shenqi_chapters0405.py
```

默认读取已保存的完整附件utf8原字节，校验parent SHA、45,389字节边界和两个chapter SHA，再幂等重放原文与显式profile。第四章正文标题没有章号，取用户文件名标号；第五章有印刷标题号。以前未带号输入的技术chapter键不回改，不据此要求用户补所谓缺章。--local-only只供分阶段维护，交付仍须sync。

原始命令式文本/古歌/引书全部作为资料，不执行其操作要求、不授权外书导入。整理metadata用schema既有analysis类别表示method并保留原标签；乙墓两种convention是工程键而非臆造原书方法名。新chapter profile不把类象或参考断语编成角色绑定。数据与原文件的LF/空白受.gitattributes保护，不因git diff格式检查改写原文。

应用概述使用scripts/import_shenqi_application_overview.py重放对应确切SHA；保留未编号标题和技术键，不根据排序6推印刷章号。流程原文→完整上下文/3事实族→条件候选历史→完整案例，分阶段可幂等重放，不保证跨阶段单事务。候选支持record_revision追加：同版本变内容拒绝，跳号/缺前版拒绝，historical_candidates供全新库恢复61历史记录，当前58候选由最高版本选取；事前投影不会包含完整叙述。最终按既定私有Git核验流程同步代码、整理及真实快照。

人体疾病预测由scripts/import_shenqi_health.py按SHA重放：完整原文→10上下文/仅参考知识→6完整案例，默认最终尝试Git同步；--local-only仅分步维护，交付前仍须实际同步。先在临时库核查全部源行/案例时序及受限定的盘投影，再写实库，避免导入后改不可变载体。实例表列的天/地干解释有作者叠干出处，显式标整理约定，不擅自补九星/马星/空亡。不同案例载体的具体字段名不是源文缺项，统一从source_span读完整表。新章技术排序7不推印刷章号。

恋爱婚姻由scripts/import_shenqi_marriage.py按确切SHA增量重放，先完整上下文/参考资料、再6整案和11来源候选。实库前在临时库校验，后验注释归反馈/案例审计，新的temporal_payload_contract显式启用结构检查，旧manifest不改。源表哈希策略只扩展明确审查的新附件，例3地盘重复、例5宫位与年份差别原样留存；最后一案2事件只有1已提供盘，不能自动补盘。技术排序8不推印刷章号。

怀孕分娩由scripts/import_shenqi_pregnancy.py按确切SHA重放，技术键pregnancy-childbirth、排序9不推印刷章号。保存12完整块、6故事/5家族/6事件/6原盘、99记录、180证据、14候选及18候选历史。星名条件使用已给基础表全称，4条rev1保留并追加rev2；完整事件家族防拆分。68独立条件期望与54原行gold分别验证；程序对照差异不拒收原书。新用户资料默认confirmed，仍不从确认声明推断缺失结局、自动执行医学建议或现实准确率。

求学考试以scripts/import_shenqi_exam.py按精确SHA重放，技术键education-examinations/排序10不推印刷章号。11语境块、5完整故事/5事件/5原盘、93记录、165证据、19参考候选/116独立条件期望；同事件多轮不拆出额外结果样本，估分与年命后知不能回填。五种方法隔离。字节与输入同文幂等，默认confirmed；实际交付必须完整导出、测试、push、核对远端及四CI。报告ingestion/SHENQI_EXAM.md。

工作就业以scripts/import_shenqi_employment.py重放，技术键work-employment/排序11。输入为可见聊天序列化，先核对父消息f2997487…及13:22434正文切片，再核对正文7a677644…；不声称附件原始哈希。14块/42参考条、5故事/6事件/5原盘、101记录/163证据、27参考候选及256条件变体。保留旧盘续断、再测缺盘和后置点评；原文确认与携干复算差异分别记录。默认confirmed与同步GitHub不变，--local-only仅分步维护；最终完整导出、测试、push及四CI验证。报告ingestion/SHENQI_EMPLOYMENT.md。

## 本轮经营求财新增章节的确切重放

`PYTHONPATH=src python3 scripts/import_shenqi_business.py` 从用户实际上传TXT的原始字节镜像读取，严格校验SHA256 `55cdc039b2e23b3cac1f71340aa433a9f3b50d15c230a67bc9649b9fcb296ee6`、56047字节与1366行；使用旧schema、确认策略、方法安装器、完整案例导入器和SQL候选，不强制新原文复核。技术键 business-finance/sequence12。14故事、18事件、16原盘；实例十二五事件只有三张给定盘。正常维护默认同步私有GitHub；--local-only仅供隔离测试，真实提交与远端main SHA/CI核验仍是验收条件。见ingestion/SHENQI_BUSINESS.md。


本轮《出行出国预测》沿现有schema v1与导入/服务链增量接续，12份章级输入累计49故事/46家族/55事件/52原盘；新增6故事/6事件/7盘、99记录、8参考候选。原字节SHA256 c273c803eb78a02cfb3c6c00065da81312c1851a679a1e3bca4911acdbc3bc55；案例四旧盘复读与案例六双盘/后置雨情严格隔离，正式规则/训练任务仍0。入口scripts/import_shenqi_travel.py，报告docs/ingestion/SHENQI_TRAVEL.md；不新增workflow，原有tests.yml保留。进度与实际验收以STATUS为准。


## 行人走失预测增量重放

scripts/import_shenqi_missing.py从原始上传镜像验证SHA256 5eca2a1a0914691ec439040a9b538fb8e4385fa5cf8ac5286bc5ae86d25b6574、49372字节/477行；missing-person/sequence14。10完整故事/10事件/11给定盘、111记录；17语境组、9参考候选，schema不变。原断、错断反馈、来信及事后复盘按来源阶段保存，缺盘不补，混合段落保留完整原文及准确分句字节范围。默认confirmed及同步GitHub；完整快照、全回归和精确新main四CI仍为交付条件。详见ingestion/SHENQI_MISSING.md。


## 钱物丢失预测增量重放

scripts/import_shenqi_lost.py验证上传原字节SHA256 ed3c80f32c213563bf35d9f9790e330ea04e4def404f6e6ca904006a94a9eaf9、34197字节/362行；lost-property/sequence15。8故事/8事件/8原盘/92记录；15语境组、5参考候选。末尾356–362校订附记原样保留，不算第九案；已上传乙休庚不再改盘。盲问揭示、逐轮找寻反馈与后置按语隔离。默认confirmed及同步GitHub，完整快照、回归和精确main四CI为交付条件。见ingestion/SHENQI_LOST.md。


## 刑事案件预测增量重放

scripts/import_shenqi_criminal.py验证源SHA256 289465c220a0701545b9f093b4b91d041d600a4c9da67bf58e33a10ece0f0ea9、37260字节/261行；criminal-cases/sequence16。5故事/5事件/6给定盘、62记录/64证据；17语境组、11参考候选。银行案置闰原断与事后拆补对照同家族，原始应期失准不改成命中；未提供系列案独立咨询盘不补。source_chart同ID投影及既有CLI/API入口不变，无schema迁移。默认confirmed及同步GitHub，完整快照、回归和精确新main四CI为验收条件。报告ingestion/SHENQI_CRIMINAL.md。


## 官司诉讼增量重放

源指纹见data/provenance/litigation_source_audit.json，完整30547原字节/267行保存在uploads和snapshot raw。scripts/import_shenqi_litigation.py沿import_chapter/install_curated/import_cases/install_candidates；chapter_key=litigation，sequence17是接收排序，不冒称书面章号。既有快照恢复到新库后：

```sh
PYTHONPATH=src python3 scripts/import_shenqi_litigation.py --restore-base --db work/litigation.sqlite3 --raw-dir work/litigation-raw --local-only
```

目标库须不存在；已包含本章的快照恢复后重放幂等，不删除历史。local-only仅维护暂存，不算GitHub交付。原盘在QimenService/CLI/WSGI既有目录和case-chart读取；第五例方法分歧与第六例后置解释阶段见本章报告。完整回归后核验私有仓库、非强制更新main、按精确SHA逐blob及四CI验收。不新增章级Actions。


## 体育竞赛增量重放

源文件26814原字节/276行，确切SHA见data/provenance/sports_source_audit.json，uploads/SQLite BLOB/snapshot raw保留。chapter_key=sports-competition，sequence18为接收顺序，源文实际标题第十二章。既有快照恢复到新库后重放：

```sh
PYTHONPATH=src python3 scripts/import_shenqi_sports.py --restore-base --db work/sports.sqlite3 --raw-dir work/sports-raw --local-only
```

目标库须不存在；已含本章的快照重放幂等。local-only仅暂存，正式交付必须审计/导出/完整回归/核实私有仓库/非强制更新main/精确SHA四CI。脚本复用既有import_chapter、install_curated、import_cases和install_candidates，读取沿QimenService/CLI/WSGI。甲戌缺完整盘不造；铺庚星名未知，完整原字行引用和可读取盘同时保留。不新增章级Actions；旧章manifest/gold/原文不可改。详见SHENQI_SPORTS报告。


## 天时气象增量重放

源文件19857原字节/156行，SHA见data/provenance/weather_source_audit.json，uploads/SQLite BLOB/snapshot raw完整保存。chapter_key=weather-prediction，sequence19仅接收排序，源文未给印刷章号。既有快照恢复到新库重放：

```sh
PYTHONPATH=src python3 scripts/import_shenqi_weather.py --restore-base --db work/weather.sqlite3 --raw-dir work/weather-raw --local-only
```

目标库须不存在；已含本章的快照重放幂等。脚本复用既有import_chapter/install_curated/import_cases/install_candidates；CLI/WSGI沿QimenService读取。第四例要求体育章既有家族共组；两来源盘及辅庚/铺庚变体分别保存，不改旧manifest/gold，不跨事件挂evidence_link。local-only仅维护暂存，最终需审计、导出、全量回归、核实私有仓库、非强制更新main、逐blob和精确SHA四CI；不新增章级workflow。详见ingestion/SHENQI_WEATHER.md。


## 地理环境增量重放

10912原字节/81行，确切SHA见data/provenance/geography_source_audit.json，uploads/SQLite BLOB/snapshot raw完整保存。chapter_key=geography-environment，sequence20仅接收排序，源文印刷标题第十五章。既有快照恢复到新库重放：

```sh
PYTHONPATH=src python3 scripts/import_shenqi_geography.py --restore-base --db work/geography.sqlite3 --raw-dir work/geography-raw --local-only
```

目标库须不存在；已含本章的快照重放幂等。沿现有import_chapter/install_curated/import_cases/install_candidates和QimenService/CLI/WSGI。第二故事两个事件同家族，前题无盘、后题一盘；不能把后题盘挂前题或补图。原文未报结局/内部推理不补，旧source/cases/curation/gold不改。local-only仅维护暂存；最终需完整审计、快照、全量回归、核实私有仓库、非强制更新main、精确SHA逐blob和四CI，不新增章级workflow。见ingestion/SHENQI_GEOGRAPHY.md。


## 人生机遇增量重放

37761原字节/273行，末尾LF，确切SHA见data/provenance/life_source_audit.json；uploads/SQLite BLOB/snapshot raw完整保存。chapter_key=life-opportunities，sequence21仅接收排序，印刷标题第十六章。既有快照恢复到新库后：

```sh
PYTHONPATH=src python3 scripts/import_shenqi_life.py --restore-base --db work/life.sqlite3 --raw-dir work/life-raw --local-only
```

目标库须不存在；已含本章的快照重放幂等。复用import_chapter/install_curated/import_cases/install_candidates及QimenService/CLI/WSGI。多轮断语、分析、反馈分kind/phase，未知和已知结果后验测不放首次输入；不得把现有本金回收/计划或错误年份重写成后续命中。旧source/cases/curation/gold/总指令不改。local-only只维护暂存，最终须审计/快照/全量回归/核实私有仓库/非强制更新main/精确SHA逐blob与四CI；不新增workflow。见ingestion/SHENQI_LIFE.md。

## 准确率评估知识重放

用户上传方法论TXT，SHA256 528174a11b617ab7d32b9c2a0a85e57a739851b4145f3a5bd544451857efbde3，9177字节/37行。使用 `PYTHONPATH=src python3 scripts/import_shenqi_accuracy.py`，沿现有import_chapter/install_curated，按accuracy-assessment/接收排序22保存13完整语境与9参考边界。无具体案例、原盘或逐案评分表，不调用import_cases/install_candidates，不建空case/gold文件；作者百分比不计算成实测分数。既有learn/reference接口可读。重放幂等，源字节变化拒绝；用户确认政策、私有同步、快照和全量回归要求不变。见ingestion/SHENQI_ACCURACY.md。

## 后记重放

`PYTHONPATH=src python3 scripts/import_shenqi_afterword.py` 校验本次5285字节/21行TXT，SHA256 ae609b92f0e1e1f475bece88879e811f7ded8161035e246003ecaa081f18a4eb，按afterword/排序23沿import_chapter/install_curated保存9完整语境/7边界。无案例或原盘，仅参考学习读取，沿既有快照、审计、全量回归与私有main同步。相同输入幂等；坏源拒绝。前作/转引不另导书报，不凭收到后记认定全书完整。见ingestion/SHENQI_AFTERWORD.md。

## 附录复合源重放

`PYTHONPATH=src python3 scripts/import_shenqi_appendix.py` 校验SHA256 df4a878fe719c57ef9138608a24ff12bda6c0cdbdfd577247badbdf6935fd340、48021字节/276行，沿import_chapter/install_curated/import_cases/install_candidates保存appendix-bundle/排序24。一份原附件包含重叠准确率/后记与三附录，不拆改源字节；appendix_source_links.json记录两旧文与三旧案对应，运行时语境亦含相同来源关系。新现场一故事两目标同家族、原图两event引用但同一个source_diagram_id。原图字面gold不冒称九宫gold；source_chart保持未覆盖，全文可读。新设备restore-snapshot后重放幂等，原CRLF变LF会拒绝；全量测试/审计/私有main和四CI要求保持。

## 附录二精校来源重放

`PYTHONPATH=src python3 scripts/import_shenqi_biography.py` 校验本次SHA256 b9f8fc44d2174f54cc962ed31dd794262cb1d54a1e6060fcdf279570e8abb716、7221字节/17行，将新LF附件按appendix-biography-clean/排序25保存。先核验旧复合源完整SHA和片段字节，再核验仅去空白与155页眉后同文；随后使用既有import_chapter/add_annotations保存来源对应语境及边界。没有新方法不调用install_curated注册重复方法，也不导case/candidate。`reference biography_clean_source_reference --filters '{}'` 可读新整篇，learn精校来源可查旧5语境关系。坏源/坏关联拒绝、重放幂等、旧行/快照/全量/远端四CI要求保持。

## 附录一精校来源重放

`PYTHONPATH=src python3 scripts/import_shenqi_learning.py` 校验本次SHA256 10db674c708186c6408c9d38228b066456ed71adb6e5939e2e1102e2a2df15ef、11761字节/51行LF；对旧复合源77–139行和93页眉作明确对照，然后沿import_chapter/add_annotations保存appendix-learning-clean/排序26。书中篇次一独立记录，旧附录二不改键或排序。curated含14旧语境/3旧家族对应，不重复导入案例、候选或方法。`reference learning_clean_source_reference --filters '{}'` 可读新全文；坏源/坏旧关联拒绝、同文幂等、快照/全量回归/私有main四CI要求保持。

## 附录三精校及所供重排表重放

`PYTHONPATH=src python3 scripts/import_shenqi_demo.py` 校验SHA256 0649e0a09cc615c9c379e3fb5f43a20038329546ec8a829dbbdac11b8322981e、15047字节/140行LF；叙事比较明确分开旧241–254碎片、新91–107重排表示及旧230页眉。沿import_chapter/add_annotations保存appendix-demo-clean/接收27、篇次三、2来源语境/2边界。curated包括30原记录对应、1case/2event/原chart_id及9宫字面出处；独立demo_gold.json不改旧gold。`reference demo_clean_palaces_reference --filters '{"palace":5}'` 真实按宫读取；旧case-chart保持not_covered，不增case/chart/方法/候选。坏源/坏旧关联拒绝、幂等/恢复/全量和私有main四CI要求保持。
