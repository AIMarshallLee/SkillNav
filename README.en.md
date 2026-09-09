# SkillNav

**One entry: find a way, review relevant risks, and finish the task.**

Tell `$skillnav` what you want done. It handles simple work directly, finds suitable
skills when helpful, reviews relevant source and permissions, executes the authorized
work and checks the result. Ask it to turn a repeatable workflow into a skill when you
want one; creation and testing are separate from installation.

Bundled local discovery, static risk indicators, instruction-skill creation and
structural validation require no additional search/review/creator skill. External
source checks and actual execution still use the host's authorized tools and accounts.
The entry stays short; detailed workflows load only when needed.

- “Complete this task and verify the result.”
- “Find a suitable skill for this workflow.”
- “Review this skill without running its code.”
- “Turn these rules into a reusable skill and try it on the sample.”

Author **Marshall Lee**. Software **0.1.0**, development candidate, no formal Release.
No proven general accuracy, speed or token-cost advantage over native Codex is claimed.
Static matches need contextual review; no matches do not certify safety. Structural
validation does not prove behavioral success. See [bundled-mode validation](docs/bundle-validation.md),
[large-catalog validation](docs/routing-validation.md) and [initial evidence](docs/verification.md).

**Memory is off by default.** Execution and draft creation do not grant memory consent.
Scoped preferences are optional; current requests outrank them. Reading and writing
are separate controls. No raw conversations, customer documents, credentials, telemetry
or author server. State is not encrypted; host processing may involve networking.
See [memory controls and limitations](skills/skillnav/references/memory.md).

## Setup

Requires Python 3.11+ and a Codex host with authorized skill-file access. Tested on
macOS arm64, Python 3.11.9, Codex CLI 0.153.4. Windows/Linux are unverified.

The source repository is [AIMarshallLee/SkillNav](https://github.com/AIMarshallLee/SkillNav),
candidate branch `feat/skillnav-v0.1.0`. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r skills/skillnav/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

After approving the exact location, copy `skills/skillnav` to
`~/.agents/skills/skillnav`, refusing an existing destination. The [Chinese README](README.md)
contains the complete tested copy procedure. Use the project venv to run the installed
scanner/creation validator, or another isolated interpreter with PyYAML. The static
review and state helpers use only the standard library. Verify host discovery; restart
if updates do not appear.

After explicit user approval, the real user-directory installation was verified in a
fresh Codex CLI session using only `$skillnav`, including a checked two-skill handoff.
The desktop skill picker was not separately inspected.

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

[Large-catalog routing validation](docs/routing-validation.md) separates artifact
correctness, appropriate skill decisions and actual use evidence, including failures.

Copyright 2026 Marshall Lee. [Apache-2.0](LICENSE). PyYAML is an external MIT-licensed
dependency, not vendored. Synthetic fixtures are original test material.
