# Bounded discovery

Resolve paths relative to this installed skill. With a project virtual environment:

```sh
python scripts/scan_skills.py --format summary
python scripts/scan_skills.py --root /explicit/skill/root --query report --limit 20
```

The second command is syntax, not a real local path. Quote real paths. Without `--root`,
the scanner discovers `.agents/skills` from cwd through its Git root, the user's
`~/.agents/skills`, and `/etc/codex/skills`. No Git means cwd only. It does NOT scan an
entire workspace. `--root` replaces defaults; `--include-defaults` adds them back.
Plugin, built-in, legacy or administrative roots require exact host-provided or
user-declared paths. No config files are read. If a root itself is a symlink, the real
target must also be declared as a root before it can be traversed.

Only SKILL.md headers are read. Discovery stops at each skill folder. Hidden folders,
scripts, references and assets are pruned; declare a needed hidden skill root directly.
Directory visits are bounded (10,000 / depth 32). Unreadable, missing, malformed,
out-of-bounds, looped and limited entries appear in `issues` and root summaries.
Safe YAML supports quoted and multiline strings. Aliases/anchors are intentionally
unsupported; headers are at most 32 KiB. Legacy name mismatches remain visible with
warnings. Same-name files remain distinct; real-file aliases share `origins`.

JSON is the default. `--format summary` includes coverage, records and issues.
`--query` is a literal name/description filter. Pagination includes matching count,
offset and next offset; totals always describe the scan before filtering. No implicit
page limit, no cache and no persistent inventory. Exit 0 allows partial discovery;
`--strict` exits 1 if any issue exists. Missing PyYAML exits 2, without installing it.

Optional `--host-catalog` reads an explicitly prepared, sanitized JSON list:

```json
[{"name":"example","description":"Example capability","locator":"host://example",
  "source":"host","scope":"session","enabled":"unknown"}]
```

Use only actual host observations, not invented or automatically enabled entries.
`enabled` is `enabled`, `disabled`, or `unknown`. The script merges exact real-path
matches with scanned records, but never opens a host locator or automatically follows
its links. Conflicting enablement is reported and disabled wins. A supplied catalog is
not a live runtime check. Absence from it does not prove absence from the host.

Never redirect a real private inventory into Git. When the host can use its own
metadata directly, no catalog file is needed at all. Summaries sent to the model may
be processed by the host provider; the scanner's lack of network calls is not an
all-offline claim for the full workflow.
