# 检查报告

产物：`release.md`。报告：`check.md`。

## 规则与调用条件

- 通过用户显式指定的 SkillNav 入口处理，应用当前项目 `.agents/skills/release-notes/SKILL.md` 的指令规则；未调用其他搜索、审查或创建技能。
- 宿主技能目录列出此项目技能；启用状态依据本次用户提供的测试宿主确认。实际读取的 `agents/openai.yaml` 为 `allow_implicit_invocation: true`。
- 实际文件读取、写入和 Python 执行均有工具返回结果。该技能是文本规则，不需要专门调用 API 或额外依赖。

## 规则冲突与模型处理说明

技能要求删除 internal 行，而用户明确要求保留原记录中的事实和顺序。以用户要求为准：release.md 开头保留全部四条原记录，逐字且按原顺序排列；其后按项目规则整理新增、修复、待确认三节。internal 记录保留在原始记录区，不放入分类列表。原始记录区是本次为满足用户要求增加的内容，因此不声称完全照搬技能的删除规则。

## 工具与文件检查结果

以下结果来自 Python 对实际文件的读取和断言；不是 release-notes 技能自带检查器的结论。哈希仅证明文件身份及前后未变，不单独证明语义正确。

- `input_format`：通过
- `all_source_records_exact_and_ordered`：通过
- `ordered_headings`：通过
- `categorized_content_exact`：通过
- `unchanged:notes.txt`：通过
- `unchanged:.agents/skills/release-notes/SKILL.md`：通过
- `unchanged:.agents/skills/release-notes/agents/openai.yaml`：通过

原记录共 4 条；完整原文区与 notes.txt 文本完全一致。分类部分与预期文本完全一致，包括固定标题顺序、完整 unknown 行和结尾“状态：草稿”。三节均非空，因此没有使用空节占位“无”；未添加日期。

release.md SHA-256：`d5639f7483480da478865754090c39ee248e10d2354427c8bbe8ed46e0a58cc1`。

输入及项目技能文件的前后 SHA-256：

- `notes.txt`：`5228a5a5beafc4094b5c935a953e4224268008341e26440bc40e09218b2c0f19`
- `.agents/skills/release-notes/SKILL.md`：`431d2b26fd936383ab70dad00e50f46f8f8eda7e51aa02600394768032d94f23`
- `.agents/skills/release-notes/agents/openai.yaml`：`8619a54e8c098122a7f3881394f84ca89b684366e848233a29ad18b6ec363935`

## 范围与结论

本次仅新增当前工作目录的 release.md、check.md；原输入和项目技能文件保持不变。未联网、安装或对外操作，未读取或写入长期记忆。

文件检查通过；模型判断为满足保留事实和原始顺序的要求，并按上述说明处理技能冲突。未取得用户验收，不将模型判断或检查通过表述为用户已接受。
