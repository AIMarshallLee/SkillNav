# P0 合成验收样例

本目录包含真实 Codex 测试产生的合成产物与检查材料，不是真实客户案例。

- [周报](weekly/weekly.md)与[试用报告](weekly/trial.md)：由真实创建/试用流程产生，角色分开。
- [销售汇总](table/totals.csv)与[核对报告](table/check.md)：执行本地项目脚本后独立核算。
- [澄清要求后的内容稿](content-clarified/release.md)与[报告](content-clarified/check.md)：从隔离项目包运行。
- `content-first-ambiguous/` 保留第一次歧义请求下两版的不同处理，不作为严格格式通过率依据。
- [候选审查](review/review.md)：仅静态检查，报告明确未执行和未验证范围。
- `contract-check/` 是**刻意含错的检查输入**：`answer.json` 中 19.81 与契约要求 19.80 不符；
  `report.md` 是预先准备、声称成功的报告。它们不是 SkillNav 生成的正确业务结果。
  [实际检查回执](contract-check/check-result.json)拒绝错误交付物，即使报告标题检查通过。

公开副本的临时目录脱敏说明、原始与公开哈希见
[副本来源](../../evidence/p0/example-provenance.json)。宿主实际调用与判定边界见
[本轮验收](../../p0-validation.md)。
