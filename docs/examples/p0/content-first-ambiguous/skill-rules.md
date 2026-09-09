---
name: release-notes
description: "Apply this team's release note format."
---
Read notes.txt as prefix|message lines. Write release.md with # 更新草稿 and exactly these ordered headings: ## 新增, ## 修复, ## 待确认. feature and fix messages go under the first two headings as '- message', preserving source order. Drop internal lines. Keep unknown lines complete under 待确认 as '- prefix|message'. Write 无 in empty sections. End with 状态：草稿. Do not invent dates.
