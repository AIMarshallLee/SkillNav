# SkillNav 0.1.0 本地验收记录

日期：2026-09-08。软件仍为 **0.1.0 本地候选**，按需求文档 V2.0 与 V2.1
增量实现。本记录区分代码测试、真实 Codex 隔离任务、模型陈述和未验证事项。
所有公开样例都是合成数据；没有真实客户验收、使用量或收益证据。

## 环境、实现和扫描范围

实际开发环境：macOS 26.5.2 / arm64，Python 3.11.9，SQLite 3.45.1，
PyYAML 6.0.3，Codex CLI 0.153.4，Git 2.50.1。分支 `feat/skillnav-v0.1.0`。
宿主行为试验使用 Codex 桌面任务的隔离子上下文，未指定模型或推理强度覆盖；
没有单独捕获运行时模型标识和每任务 Token，因此不作为严格性能基准。
Linux、Windows 和其他宿主没有实机验证。

| 文件 | 作用与实际边界 |
| --- | --- |
| `skills/skillnav/SKILL.md` | 显式单入口；选择、实际执行、交接、检查、有限修复、记忆控制 |
| `agents/openai.yaml` | SkillNav 自身禁止隐式调用；不能代替下游显式引用 |
| `scripts/scan_skills.py` | 只读声明目录和有界 YAML 头，区分磁盘存在、宿主可见、启用与依赖 |
| `scripts/state.py` | 默认关闭的私有 SQLite 状态；同意、作用域、反馈、纠正、删除与并发修订 |
| `scripts/workflow.py` | 可选的内存执行状态和恢复预算；不运行命令，不是独立编排服务 |
| `references/` | 扫描、状态 JSON 和执行／恢复说明 |
| `tests/` | 确定性回归、两个脚本 Skill、真实宿主任务准备器和产物检查器 |

扫描严格限定项目 `skills` 时为 **1 个可读记录、0 个问题**；磁盘记录的启用和
宿主可见性仍为 unknown。它不是用户全机技能盘点。测试覆盖多来源同名、同文件
去重、分页、中文路径、链接循环／越界、不可读文件、特殊文件及异常 YAML。
宿主插件或未声明目录可能不在结果中；无依赖时明确报告并用宿主清单继续。

## 自动化检查

最终运行：**73 项测试通过**，该次 unittest 用时 **0.722 秒**。
这是本地自动测试用时，不是用户任务完成耗时。

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python skills/skillnav/scripts/scan_skills.py --root skills --strict
.venv/bin/python skills/skillnav/scripts/state.py status --no-memory
```

另用开发环境的 skill-creator `quick_validate.py` 检查通过；它不是本仓库运行依赖。
元数据、显式调用策略、引用存在和独立技能包的完整 Apache 许可证另有仓库内测试。

状态测试验证：没有同意不建库；本次不读不写完全绕过；关闭学习与关闭读取分开；
明确项目规则优先；当前例外不写回；检查通过和用户拒绝可并存；没有用户反馈仍为
unknown；三个独立且检查通过、被明确接受的任务才形成观察，同任务步骤和重试
不充当三个样本。还验证版本／环境改变、多项排除、30 天老化、200 条保留上限、
来源注入、损坏／锁定／不可写回退、删除证据、清空、并发冲突和旧写入不能复活规则。

恢复测试验证每步最多两次额外尝试、全任务最多两次换路、没有新信息提前停止、
只重做受影响步骤、下游须等上游检查、下一次执行必须匹配批准的恢复路线，以及
未知外部结果先查询。纯文本宿主仍须遵守这些规则，辅助脚本不是不可绕过的权限系统。

## 真实宿主执行：E01–E10

试验每次新建临时输入和测试 Skill。执行代理收到目标与 SkillNav 入口，自行选择
下游；测试宿主明确给出允许的文件激活方式和候选启用状态。脚本 Skill 实际运行，
产物再由主任务或独立检查器核对。没有给执行代理预置成功输出。

| 验收 | 实际结果与证据 | 验证范围 |
| --- | --- | --- |
| E01 单入口 | 只指定 SkillNav，生成 [报告](examples/handoff/item-report.md)，3 行、49.65 | Codex 隔离文件激活通过；真实用户目录发现待确认安装后验收 |
| E02 自动交接 | normalize-ledger → ledger-report；[规范化 CSV](examples/handoff/normalized.csv) 实际作为下游输入 | 两个真实脚本，输入保留，无用户手动接力 |
| E03 不合格输出 | 故障脚本首次总额 0.00；定位累加错误，只修复允许的派生报告至 [45.10](examples/recovery/items.md) | 3 行逐项复核；未改输入或测试 Skill 来源 |
| E04 偏好与当前要求 | 对照 T18/T20 当前 JSON 覆盖 HTML 默认；状态测试验证默认未被例外改写 | 客观格式检查；不以习惯降低金额检查 |
| E05 受限技能 | disabled、磁盘 unknown、explicit-only 分开处理；普通工具生成 [12.60 报告](examples/restricted-fallback/report.md) | 未将禁用技能标为执行；首轮过度阻塞失败见下文 |
| E06 外部缺口 | 实际核验 Vercel find-skills 的固定提交、SKILL.md 和 MIT 许可；给出候选，未安装 | 受限测试目录的能力缺口；不宣称用户全机缺此 Skill |
| E07 结果未知 | 合成本地服务 create 写入后 exit 75，查询确认 [唯一对象](examples/uncertain-effect/service.json)，未重发 | 本地服务替身通过；真实远端服务尚未验证 |
| E08 无进展停止 | 唯一获准解析器运行一次 exit 2，保留原始输入，输出 [未完成说明](examples/stopped/status.md) | 真实提前停止；预算耗尽另有确定性测试 |
| E09 新上下文纠正 | HTML → 明确纠正 JSON → 新上下文 JSON；换项目 Markdown；删除后新上下文 Markdown | 真实动作与状态读回，详见下一节 |
| E10 无记忆／简单／建议 | B 组正常交付，T01–T04 直接答案，T22/T23 仅建议，T27 跳过状态 | 真实文件与边界检查 |

E07 的 [原始合成端点代码](examples/uncertain-effect/endpoint.py) 和请求已保存。
重现时复制到新的临时目录，确保 `service.json` 不存在，再运行：

```sh
python endpoint.py create request.json service.json  # 预期 exit 75，已经写入一次
python endpoint.py status request.json service.json  # 应显示一个匹配对象
```

不要对仓库中已保存的结果再次 create。该脚本刻意没有生产服务的并发、认证或
幂等保障，只用于证明“未知结果先查询”的宿主行为。

E06 来源为 [Vercel skills 固定提交](https://github.com/vercel-labs/skills/tree/80feb48868972d518436f26711509bc78595b5cb)，
[find-skills 指令](https://github.com/vercel-labs/skills/blob/80feb48868972d518436f26711509bc78595b5cb/skills/find-skills/SKILL.md)
及 [MIT 许可证](https://github.com/vercel-labs/skills/blob/80feb48868972d518436f26711509bc78595b5cb/LICENSE)。
作者 Vercel，适合继续查找缺失技能。正文涉及 `npx skills`；安装器源码、依赖树、
安装目标行为没有完成审计，因此具体安装方法仍标为待核验，未执行安装命令。
这是建议候选，不是已批准安装项，也不代表全机缺少 find-skills。

## 个性化确实影响行动

测试同意与反馈均为明确标注的合成用户事件，只写 OS 临时目录的测试库；没有启用
真实用户的长期记忆，也没有改原生记忆。新上下文未收到前一次完整答案。

另对完全相同的三行输入，用三个独立项目明确保存 HTML、JSON、Markdown 默认，
再以同一个“生成检查后的项目报告”目标实际自动接力。三个项目分别得到
[HTML](examples/same-task-html/report.html)、[JSON](examples/same-task-json/report.json)、
[Markdown](examples/same-task-markdown/report.md)，总额均为 45.10，三行一致。
状态读回正确作用域和格式；每项检查 passed、用户反馈 unknown。

| 阶段 | 状态与实际产物 |
| --- | --- |
| 初始项目偏好 HTML | [HTML 报告](examples/html-before-correction/ledger-report.html)，3 行、45.10；客观检查通过，用户反馈 unknown |
| 用户明确改成 JSON | 项目规则读回 JSON；下一新上下文生成 [JSON](examples/json-after-correction/report.json)，2 行、26.20 |
| 另一个项目 | 未命中原项目规则，生成 [Markdown](examples/other-project/report.md)，2 行、16.30 |
| 删除原项目格式规则 | 删除及关联证据读回；再次新上下文 defaults 为空，生成 [Markdown](examples/after-deletion/report.md)，2 行、23.00 |

早期纠正实现会删除相关客观结果，训练代理曾补回一条 unknown 检查记录。
发现后已修复为“保留客观事实、解绑旧偏好关联”，并先加入失败回归再修复。
该早期补写不算新的学习样本；正式删除后没有补写或从历史恢复。其他复核修复还包括
多项技能排除须过滤历史、恢复时选定替代路径须与下一次 begin 一致。

## 三组对照与首轮失败

冻结 [30 例标注](../tests/routing_cases.json)，SHA-256：
`1d46f0842d5a3439bbbd92b6685b6286214a7cc0974e484dc154b4cfe5ba12ad`。
T01–T10 标为训练侧，T11–T30 最初留作验证；这不是模型训练。
三组使用相同业务输入、测试 Skill、任务权限和明确偏好信息，A 保留原生技能／记忆，
B 禁用 SkillNav 状态读写，C 读取测试状态。每组有 **26 个可交付任务、4 个边界任务**。
边界为缺材料、只建议、离线缺能力、唯一解析器不支持；正确停止可通过边界验收。

| 组／轮次 | 全量验收 | 可交付任务 | 边界任务 | 证据 |
| --- | --- | --- | --- | --- |
| A 原生首轮 | 30/30 | 26/26 | 4/4 | [逐例检查](evidence/native-first.json) |
| A 原生重复轮 | 28/30 | 24/26 | 4/4 | [缺产物记录](evidence/native-repeat.json) |
| B 无记忆首轮 | 28/30 | 24/26 | 4/4 | [逐例失败记录](evidence/skillnav-first.json) |
| B 修复后回归 | 30/30 | 26/26 | 4/4 | [逐例检查](evidence/skillnav-regression.json) |
| C 个性化 | 30/30 | 26/26 | 4/4 | [逐例检查](evidence/personalized.json) |
| C 个性化重复轮 | 30/30 | 26/26 | 4/4 | [逐例检查](evidence/personalized-repeat.json) |

B 首轮 T24/T25 错把“不能用受限 Skill”扩大成“不能完成普通报告”。修复了通用
选择规则：在普通工具已获准且有能力时，直接交付，仍不激活受限 Skill。
**修复后已复用见过的验证题，属于回归，不再是未见测试集成绩。** 金标准没有修改。
最初 A/B 结果清单的路径／handoff 字段作过格式纠正，原始清单保留在私有本地证据中；
没有因此重写业务产物或把失败改成通过。

A 重复轮 T26/T27 实际缺少报告，保留为失败，没有代替基线补做。
代理首次自报通过与文件证据不符；T26 已在清单中纠正，T27 原有 completed 陈述
仍被检查器判为缺产物。C 重复轮业务文件均已存在，但清单误用组相对路径，原始
[30 条路径协议错误](evidence/personalized-repeat-manifest-errors.json) 保留；仅把清单
转换为约定的案例相对路径后，业务产物检查 30/30，未重做报告。

A 两轮全量结果 30、28；B 首轮 28、修复后 30（版本不同，不能作为同版重复）；
C 两轮 30、30。样本量小、任务重复、执行批处理方式不同，不能据此认定优于原生。

各组清单均报告手动接力 0；隔离任务不需要用户逐个唤起下游。产物检查器独立核对
文件存在、格式、金额、项目行以及输入／Skill 来源哈希；路径选择和调用次数仍含
宿主／模型陈述成分，不是统一事件 API 的全量审计。首轮 B 的两次阻塞计为失败，
不能用“零手动接力”掩盖未交付。

各轮未统一采集完整任务耗时、工具选择步骤总数、用户纠正总次数、所有返工和
上下文成本，不补造数字。没有可以报告的节省时间、节省 Token 或优于原生的结论。
更多重复轮次仅能观察本合成任务池，仍不足以估计真实用户稳定成功率。

复现协议见 [routing_cases.md](../tests/routing_cases.md)。准备器只创建新输入并冻结
来源哈希，不运行任务或预写结果；执行需真实 Codex 上下文，之后运行独立检查器：

```sh
.venv/bin/python tests/prepare_comparison.py
.venv/bin/python tests/verify_comparison.py /path/to/new/workspace A
```

## 安装、许可与远端门槛

已把独立技能目录复制到临时 `.agents/skills/skillnav`，逐文件哈希比较、严格扫描，
再只移除该临时副本并核验不存在。真实用户目录尚未安装；需要用户先确认具体路径。
[最终临时安装检查](evidence/install-smoke.json) 核对 10 个文件；测试脚本曾误用
系统解释器及未声明的临时路径别名，已改用虚拟环境解释器与规范路径重新通过。
[README](../README.md) 给出隔离依赖、安装、引用、更新回退、记忆清空和卸载方法。
复制成功不等于当前 Codex 会话已发现，安装后仍需新会话显式引用验收。

仓库及独立 Skill 包均包含完整 Apache-2.0 原文，作者 Marshall Lee。
许可证 SHA-256 为 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`，
原文来源 [Apache](https://www.apache.org/licenses/LICENSE-2.0.txt)。
PyYAML 6.0.3 为 MIT 依赖，通过隔离环境安装；未附带第三方源码。
两个测试 Skill 和端点代码为本项目合成材料。外部发现候选没有被打包。

公开候选仅包含源码、说明、测试与合成证据；原任务书、私人路径、真实数据库、
凭据、扫描清单、虚拟环境和完整会话不进入候选。示例完整性见
[sha256.json](examples/sha256.json)。本地源码归档与独立技能归档属于候选文件，
不是 GitHub Release。
CSV 保留真实运行的 CRLF 和故意未清理的输入空格，Git 属性防止换行转换破坏哈希。

已查远端 `AIMarshallLee/SkillNav` 原本是公开空仓库；这不是本任务公开的结果。
本任务未推送、未合并、未改可见性、未创建 Release。发布前须展示具体差异与
检查结果并取得用户确认。真实用户自助安装、真实任务、跨平台、真实远端副作用
和长期重复使用仍待后续验证；不得写成已上线或已被市场验证。

宿主设计核验参考 [OpenAI 技能文档](https://learn.chatgpt.com/docs/build-skills)、
[Agent Skills 文件激活模式](https://agentskills.io/client-implementation/adding-skills-support)
和 [OpenAI 技能评测](https://developers.openai.com/blog/eval-skills)。这些文档说明平台
机制，不替 SkillNav 的实际质量背书。
