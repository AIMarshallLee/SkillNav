# 检查报告

## 产物与规则

产物：release.md。应用当前项目 `.agents/skills/release-notes/SKILL.md` 的格式规则；通过用户明确调用的 SkillNav 入口处理。

宿主提供了该项目技能，且本次用户说明测试宿主确认该根技能启用。项目 `agents/openai.yaml` 的 `allow_implicit_invocation: true` 允许调用。SkillNav 自身为显式调用策略，本次 `$skillnav` 已满足。实际使用可用的 `exec_command` 工具和指定 Python（标准库），未调用虚构的技能执行 API。

## 原记录与顺序

以下逐行保留全部原记录及其顺序。发布稿按项目规则省略 internal 行，该事实仍在本报告保留；其余记录保持源顺序，未新增日期或事实。

```text
feature|新增离线导出
internal|调整临时缓存
fix|修复空标题
unknown|兼容情况待确认
```

## 工具与文件核验

以下结果来自本次 Python 对落盘文件的读取、固定预期文本比较及断言，并非独立人工验收。

- 发布稿全文与本次输入对应的预期结果一致：通过。
- 标题名称与顺序符合项目规则：通过。
- unknown 行完整保留：通过。
- internal 行按项目规则省略：通过。
- 文件以草稿状态结束：通过。
- 原输入字节未改变：通过。

notes.txt 处理前后 SHA-256：`5228a5a5beafc4094b5c935a953e4224268008341e26440bc40e09218b2c0f19`。
release.md SHA-256：`ba4893b3b37bc13138a60edfb57bec5dc3aa658b0dbfd018ceffa8a8a016d588`。

## 模型说明与验证边界

规则解释：release.md 遵守项目技能的 internal 省略要求；check.md 保存完整来源，以兼顾本次保留原记录事实和顺序的要求。

本次三个栏目均非空，空栏目写“无”的分支未由本次输入验证。未进行用户验收。本次仅创建 release.md、check.md，未联网、安装、对外操作、改写原输入或技能源文件，也未访问长期记忆。
