# SkillNav

**该不该用 Skill？用哪个？到底用了没？**

你已经装了很多 Skill，却未必记得哪个适合当前任务。调用一次 `$skillnav`：
简单任务直接完成；需要项目规范、专用工具或成熟流程时，按任务补充检索、核对
可用性并实际执行，最后简短说明用了什么、检查了什么。作者：**Marshall Lee**。

Codex 本身已有技能匹配和规划能力。本项目提供明确的判断入口、适合大量候选的
有界检索，以及可核对的使用说明；可选记忆用于保存经同意的项目偏好。
目前没有证据证明它普遍比原生 Codex 更准、更快或更省 Token。

软件版本 **0.1.0，开发候选，尚无正式 Release**。需求文档 V2.0/V2.1 是文档版本。
适用范围与实际结果见 [验证记录](docs/verification.md)。不保证每次选对，
不替代模型、工具运行时、权限或 Codex 原生记忆，不要求独立模型 Key 或服务端。
本轮三点改进与大目录对照见 [路由验证](docs/routing-validation.md)。

## 先说清楚记忆和权限

**默认不创建长期记忆，也能完成任务。** 首次启用前展示具体路径并取得同意。
你可以直接说：

- “这次既不读取也不写入记忆”——本次完全绕过状态文件。
- “这次不要记”——本次不写记录；已有记忆是否读取另行区分。
- “关闭学习”——停止新记录；不自动关闭已有记忆读取。
- “关闭记忆读取”——保留数据，但不用它选择方案。
- “这个项目以后报告用 Markdown”——保存明确的项目／报告偏好。
- “只这次用 HTML”——本次覆盖，不改长期默认。
- “你记住了什么”“忘掉那条”“清空这个项目”“清空 SkillNav 记忆”。

状态位置：macOS `~/Library/Application Support/SkillNav/state.sqlite3`；Linux
`${XDG_STATE_HOME:-~/.local/state}/skillnav/state.sqlite3`；Windows
`%LOCALAPPDATA%\SkillNav\state.sqlite3`。数据不进 Git 或技能目录。

只保存受限结构化的项目 ID、任务类别、技能身份/指纹、检查与反馈等；不保存客户
正文、原始聊天或凭证。SQLite 未加密；本地作用域过滤不是恶意进程之间的隔离。
脚本不主动联网、不遥测、不上传作者服务器，但交给宿主的摘要可能进入模型上下文。
删除承诺限于 SkillNav 自管数据的逻辑删除，不包含宿主聊天、备份或磁盘残留。

执行当前任务、记录偏好、安装技能、对外发送和发布是不同授权。记住“不喜欢被打断”
不会扩大权限。下游被禁用或只允许显式引用时，SkillNav 不会绕过其策略。

## 安装与引用

需要支持本地 Skills 的 Codex、Python **3.11+**。扫描依赖固定为 PyYAML 6.0.3；
状态与运行记录辅助代码只用标准库。当前已测环境为 macOS arm64、Python 3.11.9、
Codex CLI 0.153.4；Windows/Linux 尚未实机验证。

源码仓库：[AIMarshallLee/SkillNav](https://github.com/AIMarshallLee/SkillNav)。
当前候选分支为 `feat/skillnav-v0.1.0`。已经持有本地代码时直接进入目录：

```sh
git clone --branch feat/skillnav-v0.1.0 https://github.com/AIMarshallLee/SkillNav.git
cd SkillNav
python3 -m venv .venv
.venv/bin/python -m pip install -r skills/skillnav/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Windows 的隔离解释器路径为 `.venv\Scripts\python.exe`，对应步骤尚未实测。
不要向全局 Python 安装测试依赖。

确认具体目标后，复制到用户技能目录（现有目标将报错，不覆盖）：

```sh
python3 - <<'PY'
from pathlib import Path
import shutil
source = Path('skills/skillnav')
target = Path.home() / '.agents/skills/skillnav'
if target.exists() or target.is_symlink():
    raise SystemExit('Target already exists; inspect and approve an update first.')
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
print(target)
PY
```

这仅复制本 Skill，不是通用安装器。也可使用宿主可信安装流程，在安装前核实来源、
提交与目标位置。复制后用项目 `.venv` 运行已安装脚本；若移除克隆目录，需要另备
含 PyYAML 的隔离解释器。状态脚本本身不需要 PyYAML。

在支持的 Codex 入口引用：

```text
$skillnav 把这份 CSV 整理成准确的项目报告，检查行数和金额。
```

SkillNav 设置 `policy.allow_implicit_invocation: false`。宿主自动刷新未出现时重新
启动 Codex，再检查可见性；复制成功不等于当前会话已经发现。开发时可在支持文件
激活的宿主显式提供 `skills/skillnav/SKILL.md` 的绝对路径。除该隔离方式外，已在用户
确认后安装到真实用户目录，并在新的 Codex CLI 会话中仅引用 `$skillnav` 完成双技能
接力。桌面端选择菜单是否刷新尚未单独验证，详见验证记录。

## 三个使用例子

**本地盘点：** `$skillnav 看看这个项目可以使用哪些数据处理技能，只读盘点。`
优先使用宿主清单；需要扫描时只读声明目录的必要元数据，报告来源、可读数量、
跳过项和未知状态。不会遍历全盘或把盘点记录提交到 Git。

**自动交付与纠正：** `$skillnav 把输入数据整理成报告并检查总额。`
在能力、输入和授权齐备时，自动加载合适技能，传递真实中间文件并检查产物。
允许记忆后说“这个项目以后报告给 HTML”，下次同类任务采用该默认；另一个项目
不会继承。当前明确要求、可用性与质量检查始终优先。

**缺口核验：** `$skillnav 我缺少一个适合这个任务的技能，先核验候选，不安装。`
先分清缺的是技能、工具、账号、依赖还是材料。外部发现只返回最多三个有用候选，
列来源、版本、许可、依赖和已检查范围；没有网络就明确未检索。

## 如何工作

1. 先检查必需输入，再判断 Skill 是否能提供具体帮助。简单计算、短句改写等通常
   直接完成，不扫描目录；缺文件时说明材料缺口。
2. 需要专门规则或工具时查找候选。初始清单被截短、缺描述或匹配不明时，用任务
   关键词及必要的中英文同义词补查；默认只返回 12 条，保留匹配总数与下一页。
3. 比较适配、可用性和调用策略，读取入选指令并实际执行。关键词命中数只辅助
   检索顺序，不是质量分数，也不代表有权调用。
4. 检查实际产物后交接。失败先诊断；每步最多两次额外尝试、全任务最多两次换路，
   没有新证据则更早停止。
5. 用一句简短说明区分直接完成、技能辅助、只做建议、受阻未完成。只读过正文
   不能记成已使用；脚本运行或具体规则的实际应用才计入。经许可才记录长期结果。

例如查找发票核对技能：

```sh
.venv/bin/python skills/skillnav/scripts/scan_skills.py \
  --root /path/to/allowed/skills \
  --search 发票 --search invoice --search duplicate --format candidates
```

路径是语法示例。它只检索声明目录中的元数据；扫描到的文件不自动视为已启用。
没有命中时应检查用词、语言和目录覆盖，不能立即宣称没有合适技能。

没有虚构的 `invoke_skill` API。指令型技能需正确应用其规则；脚本型技能需真实执行
证据。工具成功、客观检查和用户接受分别记录。未知远端结果先查询，不盲目重发。

明确规则与观察习惯分开：至少三个独立且通过检查、明确被接受的任务，才可能形成
低优先级观察。重试或同任务的三个步骤不算三个样本。技能指纹/环境改变需重查；
观察 30 天未用降权；最多保留 200 条最小步骤结果，失去证据的观察随之撤销。
这些阈值是工程默认，不是统计学或效果保证。

## 更新、删除与卸载

更新前检查远端版本、差异和本地改动，再批准具体版本；不自动 `git pull` 或批量升级。
保留已安装 Skill 的可回退副本，复制审核过的新版本并重新核验发现与低风险任务。
个人状态独立于统一技能代码，更新不会自动迁移未知 schema 或重建损坏数据。

删除记忆优先使用自然语言控制，由 SkillNav 定位准确项目／规则、调用状态脚本并
读回验证。“清空 SkillNav 记忆”清空偏好和结果，并同时关闭学习与读取；保留
schema/revision 元信息以阻止旧并发写入。不会生成隐藏备份。

卸载前决定是否保留记忆，必要时先清空。检查确认安装目标确为
`~/.agents/skills/skillnav` 后，只移除这个目录，不删除整个 `.agents`。卸载 Skill
不会自动删除私有数据库或项目虚拟环境。重启/刷新后核验宿主不可见。

高级状态命令、受限 JSON 输入与可审查的操作例子见
[记忆操作说明](skills/skillnav/references/memory.md)。所有数据写入要求当前修订号；
冲突、不可写或损坏会返回 `saved:false` 并退回无记忆执行，不假装保存成功。

## 验证与边界

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python skills/skillnav/scripts/scan_skills.py --root skills --strict
.venv/bin/python skills/skillnav/scripts/state.py status --no-memory
```

[验证记录](docs/verification.md) 分开列出自动测试、真实 Codex 隔离执行、
E01–E10、个性化新上下文测试和未验证项。合成数据测试不是真实客户验收。
本项目尚无真实用户采用、节省成本或跨平台成功率数据；也不会用 Star/安装量替代质量。

已知限制：宿主目录及插件覆盖可能不全；扫描器不读取配置来推测有效启用状态；
语义选择由当前模型完成；结构化授权回执不能阻止有本地权限的恶意调用者伪造；
执行追踪依赖实际宿主证据，纯文本技能不是不可绕过的控制系统。

## 贡献和许可

[贡献指南](CONTRIBUTING.md) · [安全说明](SECURITY.md) · [English](README.en.md)

Copyright 2026 Marshall Lee. 采用 [Apache License 2.0](LICENSE)。未附加禁止商用限制。
PyYAML 是通过依赖安装的 MIT 许可软件，未将其源码打包进本仓库。测试 Skill 为本项目
合成验收材料，不含客户原文或下载的第三方 Skill。许可与来源核验见验证记录。
