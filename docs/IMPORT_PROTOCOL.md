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

只有用户明确确认原文时才加 `--confirmed`。同文重入返回 duplicate 与同一 source/revision，不生成新正文；确认可独立追加 review。不同文不会替换，须显式 `--revision 2` 等下一版本。原文文件以 bytes 读取，不经过 shell 转义或字符替换。

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

脚本从仓库真实原文字节快照读取，校验确定SHA，按相同book/chapter键导入，再安装人工精读的chapter01_curated.json。作者/版本未知，confirmed=false；同文重放不增加正文、概念、编译条目或数据版本。不同哈希拒绝，不用于下一章。默认尝试GitHub同步；受限网络按GITHUB_SYNC由Codex完成推送。

可信维护过程中可用 --local-only 分阶段检查或针对临时库重建；这会明确输出github_sync=pending，不能据此交付。全部工作完成后必须导出当前快照、测试、推送并核对远端。脚本不执行训练、不读取其他书或旧项目。

本次正文完整保留，但用户尚未明确校勘确认，状态pending与教学算法源码测试独立；不需为继续保存已提供材料额外确认。后续章节仍按用户输入顺序，不能直接套用首章算法填缺失规则。细节见 ingestion/SHENQI_CHAPTER01.md。

## 第二章重放

```sh
PYTHONPATH=src python3 scripts/import_shenqi_chapter02.py
```

只接受本次第二章确切原文字节SHA，保留已有book键、chapter-02和顺序2；无confirmed推定。安装使用显式chapter02 compiler profile，分别保存上下文、质量记录、完整演算例及8编译族。不自动读其他书，纸上十步仅流程参考，公历转换没有给算法就不编造。

跨章运行需要首章既有数据：新设备优先恢复完整current快照，或分别重放两章脚本。--local-only只供分阶段维护/临时验证，会输出pending；最终仍必须导出、测试、push和远端核对。新增结构化JSON及来源/验收也纳入自动同步的受控目录。新章继续按用户完整章节输入，不把第二章两张教学盘当历史断案或训练反馈。

## 第四、第五章合并附件重放

```sh
PYTHONPATH=src python3 scripts/import_shenqi_chapters0405.py
```

默认读取已保存的完整附件utf8原字节，校验parent SHA、45,389字节边界和两个chapter SHA，再幂等重放原文与显式profile。第四章正文标题没有章号，取用户文件名标号；第五章有印刷标题号。以前未带号输入的技术chapter键不回改，不据此要求用户补所谓缺章。--local-only只供分阶段维护，交付仍须sync。

原始命令式文本/古歌/引书全部作为资料，不执行其操作要求、不授权外书导入。整理metadata用schema既有analysis类别表示method并保留原标签；乙墓两种convention是工程键而非臆造原书方法名。新chapter profile不把类象或参考断语编成角色绑定。数据与原文件的LF/空白受.gitattributes保护，不因git diff格式检查改写原文。
