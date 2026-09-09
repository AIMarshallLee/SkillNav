> 公开合成样例。关联 JSON 中的临时目录已脱敏；原始与公开副本哈希见 [副本说明](../../../evidence/p0/example-provenance.json)。报告为模型生成，工具行为另经主任务核对。

# team-weekly-brief 试用报告

已创建草稿技能，并读取最终技能全文、应用其规则完成真实文件试用。技能尚未安装；本次没有验证宿主注册后的自动选择行为。

## 交付与验收标准

| 角色 | 文件 | 验收标准 |
| --- | --- | --- |
| 可复用技能 | [drafts/team-weekly-brief/SKILL.md](drafts/team-weekly-brief/SKILL.md) | 包含输入输出、逐行分类、内部记录排除、固定格式和交付检查；元数据有效 |
| 实际周报 | [weekly.md](weekly.md) | 从 sample.md 生成，符合 rules.md；不以本报告代替 |
| 试用报告 | [trial.md](trial.md) | 区分实际文件检查、模型判断和未验证项 |
| 机器检查结果 | [checks/results.json](checks/results.json) | 读取实际产物并逐项对照来源，记录指纹与输入保全结果 |

## 调用与工具证据

- 本次由用户原生 `$skillnav` 显式入口提供技能；已读取安装包的 SKILL.md、创建/执行/审查流程和 agents/openai.yaml。SkillNav 的 `allow_implicit_invocation: false` 与此次显式调用相容。
- 按明确创建请求直接创建，没有发现或调用其他技能，没有扫描候选目录。用户对当前 .agents/skills 的启用说明未被扩大解释为 drafts 已安装。
- 使用真实可用的 exec_command、apply_patch 和用户指定 Python；Python 实测为 3.11.9。未使用虚构的技能调用 API。
- SkillNav 自带 create_skill.py 实际创建指定目录，validate 实际返回退出码 0；见 [结构检查原始输出](checks/structure.json)。生成技能的调用策略为 `allow_implicit_invocation: true`，没有额外依赖或可执行资源。
- 用户明确授权新草稿的真实试用。因此在本会话完整读取生成指令后，按其指令生成文件；这属于指令技能的实际应用，不是独立宿主调用回执。

## 工具与文件检查结果

以下结果来自实际工具执行及文件读取，非预填成功字段。

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| 技能结构 | valid=true，退出码 0 | [structure.json](checks/structure.json) |
| 有界静态扫描 | 读取 2 个文件，无跳过、无模式命中，退出码 0；safety_certified=false | [review.json](checks/review.json) |
| sample.md 真实试用 | 通过；四节条目数 1/1/1/0，内部记录排除，需确认为“无” | [weekly.md](weekly.md)、[results.json](checks/results.json) |
| 合成边界试用 | 通过；保留未知前缀及无前缀记录、原顺序和重复事项；忽略空行，空章节写“无” | [输入](checks/boundary-input.md)、[产物](checks/boundary-weekly.md) |
| 仅内部记录试用 | 通过；四节均为“无”，末行为草稿状态 | [输入](checks/internal-only-input.md)、[产物](checks/internal-only-weekly.md) |
| 输入保全 | rules.md、sample.md 前后 SHA-256 一致 | [基线](checks/input-before.json)、[results.json](checks/results.json) |

[verify.py](checks/verify.py) 只读取试用输入和实际周报，断言固定标题、章节顺序、末行及每节完整内容，检查分类、原文、顺序和空节。它不生成周报，也不读取报告作为通过依据；实际运行退出码为 0。检查代码由本模型编写，属于与生成动作分离的确定性文件检查，不是另一位审查者或另一模型的独立验收。

## 模型执行说明与判断

读取最终技能后，本模型对 sample.md 的 done/next/blocked 记录去前缀、保留原文并分别归入前三节；排除 internal；把空的第四节写为“无”，追加固定草稿状态。这些处理已落实到 weekly.md，并由检查脚本重新读取验证。

源规则未单独定义无前缀文本与只有已知前缀的空事项。技能采用保守约定：前者完整进入需确认，后者保留空列表项而不补写事实。无前缀分支已试用；空事项、缺失文件和完全空文件分支未单独试用，不宣称已覆盖。

模型阅读判断：该包仅包含本次编写的工作流程与 UI 元数据，适用于授权范围内的本地文本转换。静态扫描无命中不代表安全认证；本次样例通过不代表所有输入均正确。没有用户验收或对外使用证据。

## 范围与复用

任务写入限定在当前工作目录；原输入及安装的 SkillNav 源文件未修改。没有联网、安装、对外操作、长期记忆读写或其他搜索/审查/创建技能调用。检查材料保留在当前 checks 目录，样例内容未复制进技能包。

复用示例：`按 drafts/team-weekly-brief/SKILL.md 整理指定记录文件，将周报保存为指定输出文件。` 安装不在本次范围内，尚未执行。
