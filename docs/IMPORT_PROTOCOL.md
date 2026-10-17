# 下一章的接收与导入

用户下一条消息可以给《神奇之门》的章节名、完整正文和实际有的页码/版次/图盘。没有提供的作者/版次/页码不强迫补、不猜。分多条发可注明“本章未完”，最后注明“本章结束”；在明确完整范围后统一标注。保存收到的全部原文，不为增加记录数拆散故事。

Codex 将按 KNOWLEDGE_POLICY 保存、审读和整块标注，然后运行审计及相关回归，报告资料/知识/规则/案例各自覆盖。以下命令只是下一阶段使用说明，本轮没有执行任何真实文献导入。

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

目前文本导入、全章索引和结构标注已可运行；扫描图片/复杂原盘解析、自动章节理解、自动规则编译不在 Phase 0 已实现范围。收到图片时必须保留原始附件及另行实现有哈希的媒体导入，不把 OCR 当原文覆盖。

用户后续要求每次数据更新同步 GitHub。上述 import-chapter / annotate 现在保存成功后会自动导出并尝试同步指定私有仓库；网络/权限失败时输出 pending、返回退出码2，已保存资料不回滚。可访问 API 时运行 `PYTHONPATH=src python3 -m qimenllm sync --message 'Update source data'`；当前受限会话由 Codex 按 GITHUB_SYNC 使用连接器核验私有状态，再完成实际 Git push 与远端 commit 核对后报告完成。私有仓库首次上传已成功。
