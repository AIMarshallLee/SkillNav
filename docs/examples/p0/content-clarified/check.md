# 检查报告

结果：通过。

- 已应用当前项目 `.agents/skills/skillnav/SKILL.md` 的调用资格与执行检查流程，以及 `.agents/skills/release-notes/SKILL.md` 的发布稿规则。
- SkillNav 已由宿主暴露且由用户明确选择；其 `allow_implicit_invocation: false` 要求已满足。项目 release-notes 已由宿主暴露，其 `allow_implicit_invocation: true`，本次可调用。
- 输入为 `notes.txt`，共 4 条 `prefix|message` 记录；发布稿为 `release.md`，检查报告独立保存为 `check.md`。
- 已读取生成文件并与独立预期逐字比较，结果一致。
- 标题为“更新草稿”，依次包含“新增”“修复”“待确认”三个节，结尾为“状态：草稿”。
- feature、fix 各保留 1 项，事项原文及各节内源顺序保持不变。
- internal 排除 1 项；unknown 保留 1 项，完整呈现 `unknown|兼容情况待确认`。
- 各节均非空，无需填“无”；发布稿未添加日期、原始记录区或检查说明。
- 已比较输入及项目技能文件操作前后的 SHA-256，全部未变。
- 使用指定 Python 执行本地整理与检查；未联网、安装、调用其他辅助技能或读写长期记忆。
