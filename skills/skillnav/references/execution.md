# Execution contract and local recovery

Track the goal, input(s), deliverable, immutable requirements, checks, allowed side
effects and step dependencies in the current task. The host executes real tools;
SkillNav does not implement a universal skill invocation API. Loading instructions
by a permitted file read is supported by the Agent Skills integration pattern, but
each host's enablement, policy and tool rules still apply.

## Preflight and file contracts

Before committing to a specialized route, resolve four questions from actual task/host
evidence: does the input match the skill's required format, are its tools available,
are its dependencies present, and will its output meet this task? Read only the selected
candidate and relevant input metadata. A keyword match or dependency listed in a README
is not verification. Record missing/unknown requirements; use a suitable authorized
alternative when available. Do not install software or fabricate a host tool to pass.
Keep this short and internal unless a gap requires the user's decision.

Simple tasks may check the result directly. For multi-file handoffs, repeatable trials
or easily confused report/output roles, use `scripts/task_contract.py`. The host writes
a small task-local contract from the user's requirements before execution, then calls:

```sh
python scripts/task_contract.py preflight --root /allowed/task --contract /allowed/task/contract.json
# Execute the actual authorized workflow with host tools.
python scripts/task_contract.py check --root /allowed/task --contract /allowed/task/contract.json
```

The helper is standard-library-only and read-only. It does not execute a candidate,
probe tools, install dependencies, grant authorization or save an inventory. Example:

```json
{
  "version": 1,
  "inputs": [{"id": "sales", "path": "sales.csv", "format": "csv",
    "checks": [{"type": "csv_columns", "expected": ["product", "amount"]}]}],
  "requirements": [{"id": "python", "kind": "host_tool", "status": "verified",
    "evidence": "Python interpreter availability confirmed by the current host"}],
  "artifacts": [
    {"id": "totals", "path": "totals.csv", "role": "deliverable", "format": "csv",
      "checks": [{"type": "csv_columns", "expected": ["product", "total"]},
        {"type": "csv_row_count", "expected": 2}]},
    {"id": "report", "path": "check.md", "role": "report", "format": "text",
      "checks": [{"type": "markdown_headings", "expected": ["# Checks"]}]}
  ]
}
```

Replace these illustrative criteria with this task's actual requirements; the user
does not fill out JSON. Inputs and outputs are distinct task-relative paths with unique
IDs. Each file has a nonempty check list, and at least one output is a deliverable.
A report cannot satisfy another output's path or checks. Existing file identities are
also checked to reject case/Unicode aliases; final reads check opened identities again.
Preflight cannot identify aliases between output files that do not yet exist.
For creation, the generated
skill entry and the trial output are deliverables; the trial report is a separate file.

`preflight` checks input bytes/schema and the host's requirement observations. Verified
observations need evidence; missing/unknown requirements do not pass. These observations
are supplied by the host and are not independently authenticated by the helper. They
never replace current invocation policy, safety review or an applicable human approval.
`check` reads actual output bytes and reports each ID/role/path, result/reason and fingerprint.
It accepts no caller-supplied `passed` flags and does not follow a report's links.
Each receipt includes the contract's SHA-256 so the host can compare the preflight and
final contract. The helper does not keep the earlier receipt or compare it automatically.
The JSON field is `receipt["contract"]["sha256"]`, not a top-level `contract_sha256`.
Require two present 64-character SHA-256 strings before comparing; two missing/null
values never prove an unchanged contract.

Limits: 256 KiB contract, 1 MiB per file, at most 64 input/output files and 16 MiB total
reads per call including the contract; additional JSON/CSV shape limits apply. Paths
must be relative to the task root (the CLI contract path may be absolute inside it).
Use a canonical root: ancestor symlinks, symlinks, hardlinks and special files are refused.
This is a bounded check in a stable local directory, not a defense against every hostile
filesystem race. Oversized/unsupported input needs an appropriate authorized checker.

Supported checks are exact text, required/forbidden text, exact JSON, CSV column order
and data-row count, and ordered ATX Markdown heading lines outside fenced/indented code.
The heading check is not a full Markdown parser; use an appropriate parser for HTML
containers, Setext headings or other unsupported syntax. Every file must also be nonempty.
Use independent arithmetic, source-to-output comparison or appropriate tests for criteria
these primitives do not cover. A heading/row-count check alone cannot prove the amounts,
factual accuracy, visual quality, execution history or overall task success.

Keep the original contract unchanged through execution and recovery. A demonstrated
contract-authoring error requires preserving the old check result and explaining the
correction; never loosen criteria to fit an incorrect artifact. If input/source files
change after preflight, recheck them before the dependent execution. Missing checks or
an unreadable/bounded-out file leave that criterion unverified; they are not a pass.
Do not put credentials/customer originals into a contract or publish private receipts.

For complex recovery, `scripts/workflow.py` is an optional pure-Python helper:

```python
from workflow import Workflow
w = Workflow(["row_count", "exact_total"])
w.add_step("normalize")
w.add_step("report", dependencies=["normalize"])
```

The host calls `begin` only after checking enablement, availability and implicit
invocation policy. It calls `executed` after the real tool returns, then `checked`
with actual independent check results. Never fill success fields in advance.
`fingerprint_artifact` verifies a real file inside a permitted root and hashes it;
a hash proves identity, not semantic correctness. Callers still check task criteria.

`recover` separates diagnosis from retry. It requires new evidence and an actual
change; two additional attempts per failed step and two replacements task-wide are
the ceilings. Repeating the same failed plan stops earlier. Valid upstream checks
remain; affected downstream checks are invalidated. Permissions and missing facts
stop the dependent step. A user-only skill restriction prevents a replacement.

External calls with uncertain results MUST query state. Existing objects are verified,
not recreated. Unknown state stops replay; even a confirmed-absent result needs a
safe, authorized/idempotent retry. Local test doubles can exercise this decision,
but do not prove integration with a real payment, email or publishing service.

The helper stores no files and cannot prove that a model supplied honest booleans or
retained its instance. Host approvals and actual tool/artifact receipts provide the
boundary; the helper is deterministic bookkeeping, not a new security system.

Quality examples: CSV field names, independent row count and decimal totals; code
regression tests; document readability and requirement coverage. Keep required checks
stable through recovery. Label model style judgments separately. A user can reject a
technically valid result; preserve both states.

## A short, truthful decision receipt

The user should be able to distinguish the choice and the actual work without reading
an execution transcript. Say why the selected route adds value before using it; after
execution, name what was actually applied and the concrete checks. If the direct path
was sufficient, say no Skill was needed. Recommendations stay recommendations.

For script skills, tie use to a real execution receipt and the resulting checked file.
For instruction skills, tie it to the actual project rule/template applied to output.
File loading alone, a selected name or a model-generated success flag does not establish
use. Do not claim "all skills compared" after reading one candidate page. Keep these
receipts in the normal answer unless a separate evaluation artifact was requested.
