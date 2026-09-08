---
name: ledger-report
description: Turn normalized CSV line items into a readable Markdown, HTML or JSON report with exact totals. Requires item, quantity, unit_price and line_total columns.
---

# Ledger report

For local synthetic data only, first verify the input has item,quantity,unit_price,
line_total. If not, find a suitable normalization step before using this skill. Use
`python scripts/report.py INPUT.csv OUTPUT --format markdown|html|json`. Choose the
format from the user's current request or valid project preference; default Markdown.
Never overwrite input or an existing output. Independently verify every line total,
grand total, item count and report readability. Do not label this synthetic fixture as
a real financial, customer or business result. No network or installation needed.
