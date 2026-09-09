# Bounded discovery

Start with host-exposed metadata and its coverage limits. If the catalog is truncated,
has names without useful descriptions or lacks a clear match for a specialized task,
query declared on-disk metadata. Set cwd to the known task root; do not enumerate the
surrounding workspace or run an unfiltered listing of skill roots before a query.
When PyYAML is unavailable, explain the dependency and continue with available host
metadata/authorized tools; do not force a new installation merely to discover skills.

Resolve paths relative to this installed skill. With a project virtual environment:

```sh
python scripts/scan_skills.py --format summary
python scripts/scan_skills.py --root /explicit/skill/root --query report --limit 20
python scripts/scan_skills.py --root /explicit/skill/root --search 发票 --search invoice --search duplicate --format candidates
```

The second command is syntax, not a real local path. Quote real paths. Without `--root`,
the scanner discovers `.agents/skills` from cwd through its Git root, the user's
`~/.agents/skills`, and `/etc/codex/skills`. No Git means cwd only. It does NOT scan an
entire workspace. `--root` replaces defaults; `--include-defaults` adds them back.
If the task restricts discovery roots, pass exactly those roots and omit defaults.
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
page limit for legacy JSON/query mode, no cache and no persistent inventory. Exit 0 allows partial discovery;
`--strict` exits 1 if any issue exists. Missing PyYAML exits 2, without installing it.

## Finding a relevant skill in a large catalog

Start with the benefit the task actually needs. Direct arithmetic or routine rewriting
does not need discovery merely because some skill mentions math or writing.
When a specialized task has no clear host match, especially with shortened/omitted
descriptions, use `--search` for a small set of task-derived terms. It accepts 1–12
terms of up to 128 characters each, normalizes Unicode/case and removes duplicates.
Terms are OR-matched against metadata only. More distinct matching terms sort first;
ties are stable by name and source path. `matched_terms` explains that order. This is
not translation, embeddings, a quality score or an automatic eligibility filter.

The host supplies appropriate synonyms and translations. For a Chinese invoice task,
"发票", "invoice", and "duplicate" can recover a skill with an English description
and an opaque name. Do not put customer values into search terms. A keyword match is
only a candidate; check scope, actual enablement/policy, dependencies and I/O before use.
No hits means no lexical match within these roots, not proof that no relevant skill exists.

Read candidate descriptions and check actual task fit, enablement, invocation policy,
dependencies and tools. Resolve identity by source and real path, not name alone.
Keyword-stuffed descriptions do not outrank those checks. Select the smallest suitable
combination; SkillNav is never its own downstream candidate. For an eligible skill,
read the full instructions, apply relevant risk review and actually execute/apply it.
Do not auto-load an explicit-only candidate because the user invoked SkillNav.

`--search` and `--format candidates` default to 12 results; `--limit` and `--offset`
control paging. Candidate view preserves scan totals, roots/statuses, match totals,
next page and distinct candidate paths. It summarizes issue codes with five examples;
use full JSON when the actual issues/origins need inspection. This limits what is sent
to the model; disk scanning still reads bounded metadata across the declared roots.
`--query` keeps its original single literal-filter behavior and cannot combine with
`--search`. Refine noisy terms before dumping many irrelevant pages into context.

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

## External discovery when local capabilities do not suffice

Separate missing instructions from missing input material, tools, dependencies or
accounts. Use existing authorized web/source tools with sanitized capability terms.
Check authors' repositories or official pages for actual SKILL.md, commit/version,
license, dependencies and installation method. Record unknowns instead of inventing
a marketplace API, a universal installer, platform equivalence or an availability claim.
Search is already requested in a find task; do not make the user find a search skill first.

Return at most 3 useful choices with the source link and a brief reason; the user should
not have to inspect a long catalog. Review new executable/external candidates using
[review](review.md) before installation/use. Download source into an inert review folder
only within authorized scope; retrieving source does not install or activate it.
Do not send raw task/customer content to external search or publish private inventories.

Recommend by default. Install only with the applicable specific approval for the exact
candidate/source/version/location, after source and dependency review. Use a verified
host installer or precise copy for the actual package; do not execute a candidate's
suggested installation command blindly. Recheck discovery, enablement and required tools
after installation. Missing network means external discovery is unavailable; deliver
what local capabilities can complete and state the actual gap. No new skill is created
automatically just because no suitable external candidate was found.
