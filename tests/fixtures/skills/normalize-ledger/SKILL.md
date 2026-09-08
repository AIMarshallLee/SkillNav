---
name: normalize-ledger
description: Normalize a synthetic CSV ledger into checked decimal line items before reporting. Handles item, quantity and unit_price fields.
---

# Normalize ledger

For local synthetic data only, run `scripts/normalize.py INPUT.csv OUTPUT.csv` with
Python 3.11+. Do not overwrite input. Quantity must be a positive integer; price must
be nonnegative with at most two decimals. Trim item names, preserve row order, and
write item,quantity,unit_price,line_total. After execution independently inspect input
and output: row count, clean names, quantities and exact decimal line totals. The
output is suitable for a downstream report skill. No network or installation needed.
