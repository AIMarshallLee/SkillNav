# Execution contract and local recovery

Track the goal, input(s), deliverable, immutable requirements, checks, allowed side
effects and step dependencies in the current task. The host executes real tools;
SkillNav does not implement a universal skill invocation API. Loading instructions
by a permitted file read is supported by the Agent Skills integration pattern, but
each host's enablement, policy and tool rules still apply.

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
