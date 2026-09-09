# SkillNav

**只说要完成什么，SkillNav 帮你找方法、查风险、把事情办完。**

不用先记住“技能搜索”“技能审查”“技能创建”的入口。调用一次 `$skillnav`，
它根据任务使用需要的能力，交付结果和必要的检查说明。简单任务直接完成；
需要复用流程时，按你的要求创建并试用新技能。

```text
$skillnav 帮我把这份销售表整理成周报，核对金额和行数。
```

| 你可以直接说 | 它负责什么 |
| --- | --- |
| 帮我完成这个任务 | 直接处理，或找到合适技能、检查相关风险、执行并核对结果 |
| 帮我找个能做这个的技能 | 查找、比较，给出最多三个有依据的选择 |
| 看看这个技能能不能用 | 检查来源、代码和权限风险，说明发现及未验证部分；审查本身不运行候选代码 |
| 把这个流程变成可复用技能 | 创建完整草稿，检查结构，实际试用后说明结果；安装单独处理 |

内置本地搜索、基础静态风险检查、创建与结构校验脚本，以及相应工作流程。
**基础模式无需另装搜索、审查或创建技能。** 外部搜索、来源核验和实际任务执行
使用宿主已有且获准的工具；本包不会凭空提供账号、连接器或所有领域能力。

作者：**Marshall Lee**。软件 **0.1.0 开发候选，尚无正式 Release**。
没有证明普遍优于原生 Codex，也不承诺“审查过就绝对安全”。
当前单入口集成验收见 [能力验证](docs/bundle-validation.md)；
历史 [首版验证](docs/verification.md) 和 [大目录检索验证](docs/routing-validation.md)
保留失败、修复及证据边界。

**记忆默认关闭。** 普通任务不会偷偷保存偏好；创建技能也不等于同意记录长期记忆。
已有授权范围内持续完成任务；新增安装、账号变更和对外操作按具体授权处理。

## 安装与引用

需要支持本地 Skills 的 Codex、Python **3.11+**。扫描和创建结构校验依赖 PyYAML 6.0.3；
静态审查、状态与运行记录辅助代码只用标准库。当前已测环境为 macOS arm64、Python 3.11.9、
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

## 如何工作

1. 检查材料与目标。简单任务直接完成，避免为了用技能而搜索。
2. 需要时从已授权目录检索；目录截断或描述不全时，按任务词细化或翻页。
3. 核对适配性、可用性与调用策略，对相关来源、脚本和副作用做风险检查。
4. 实际执行并核对产物，再交给下一步。创建任务则生成草稿并进行真实试用。
5. 交付文件和简短说明：实际做了什么、检查了什么、哪些仍需处理。

技能审查读取指定来源、检查常见风险信号，不能证明没有漏洞。它不会为了测试安全
而执行未知脚本。技能创建辅助脚本只写入指定的新目录，不覆盖已有技能，不自动
安装；结构检查通过与真实任务试用通过分开报告。

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

## 可选的项目偏好

允许记忆后，可以说“这个项目以后用 Markdown”“只这次用 HTML”“这次不读写
记忆”“停止学习”“忘掉这条”或“清空 SkillNav 记忆”。读取与写入分别控制，
当前任务要求优先。一个简单格式默认不需要创建新技能。

首次启用前说明具体私有存储位置并取得同意。只保存受限结构化信息，不存客户正文、
原始聊天或凭证。状态不加密；删除仅涉及 SkillNav 自管记录，不代表清除宿主聊天
或备份。完整控制、存储路径及限制见 [记忆说明](skills/skillnav/references/memory.md)。

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
