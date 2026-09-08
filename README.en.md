# SkillNav

**One explicit entry: choose skills, use them, hand off real outputs, and check delivery.**

SkillNav builds on Codex's existing skill mechanism. It supports bounded discovery,
minimal skill combinations, verified execution, limited recovery, and opt-in scoped
preferences. It is not a new model, permission system or skill runtime. Author:
**Marshall Lee**. Software **0.1.0**, local candidate; V2.0/V2.1 refer to requirements.

**Memory is off by default.** Execution does not require memory consent. Say “do not
read or write memory this time”, “stop learning”, “stop reading memory”, “forget that
preference”, “clear this project”, or “clear SkillNav memory”. Reading and writing are
separate controls. Clearing all removes preferences/outcomes and disables both.

The optional SQLite file is outside Git and skill directories: macOS
`~/Library/Application Support/SkillNav/state.sqlite3`, Linux
`${XDG_STATE_HOME:-~/.local/state}/skillnav/state.sqlite3`, Windows
`%LOCALAPPDATA%\SkillNav\state.sqlite3`. No raw conversations, customer documents,
credentials, telemetry or author server. State is not encrypted. Host-model processing
and other tools may involve networking. Logical deletion excludes host chats, backups
and storage remnants.

## Setup

Requires Python 3.11+ and a Codex host with authorized skill-file access. Tested on
macOS arm64, Python 3.11.9, Codex CLI 0.153.4. Windows/Linux are unverified.

The target repository is [AIMarshallLee/SkillNav](https://github.com/AIMarshallLee/SkillNav).
The local candidate has not been pushed; use an existing local copy until publication
is approved. From its root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r skills/skillnav/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

After approving the exact location, copy `skills/skillnav` to
`~/.agents/skills/skillnav`, refusing an existing destination. The [Chinese README](README.md)
contains the complete tested copy procedure. Use the project venv to run the installed
scanner, or another isolated interpreter with PyYAML. The state helper uses only the
standard library. Verify host discovery; restart if updates do not appear.

Invoke `$skillnav` plus the actual goal. Examples:

- “Inventory the data skills available to this project, read-only.”
- “Turn this CSV into a report and independently verify its totals.”
- “Check external candidates for the missing capability; do not install.”

Downstream skills are automatically used only if permitted by host enablement,
invocation policy and the task's authorization. Failed steps get at most two additional
attempts; the task gets at most two route changes. Unknown external side effects are
queried before any replay. Objective checks and user acceptance stay separate.

Explicit corrections affect the next matching project/task. One-off exceptions do not
rewrite defaults. Observations require three independently accepted and checked tasks;
retries and multiple steps are not separate samples. Version/environment changes,
30-day staleness and 200-outcome retention restrict reuse. No claimed universal routing
accuracy, user adoption, savings or all-platform compatibility.

## Updates and removal

Review upstream version and local changes before updating; no automatic upgrades.
Back up the installed skill, replace only that approved directory, and recheck
discovery and a low-risk task. Personal state remains separate. Unknown/corrupt schemas
are preserved and fail back to routing without memory.

Before uninstalling, choose whether to keep or clear memory. Confirm the exact installed
directory, then remove only `~/.agents/skills/skillnav` and verify it disappears from
the host. Uninstalling does not silently delete the DB or development venv.

[Verification and E01–E10](docs/verification.md) · [Memory controls and JSON API](skills/skillnav/references/memory.md)
· [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

Copyright 2026 Marshall Lee. [Apache-2.0](LICENSE). PyYAML is an external MIT-licensed
dependency, not vendored. Synthetic fixtures are original test material.
