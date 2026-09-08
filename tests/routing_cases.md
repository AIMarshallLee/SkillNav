# Routing and host acceptance protocol

`routing_cases.json` contains 30 labelled synthetic tasks: T01–T10 training-side
examples and T11–T30 held-out validation. Freeze labels and source version before a
run. Do not rewrite expected outcomes to turn a failure into success. A later repair
requires disclosing reuse of a previously seen validation case.

`prepare_comparison.py` creates NEW A/B/C temporary workspaces with the same inputs,
skills, permissions and scoped preference information. It does not execute tasks or
write successful result logs. `verify_comparison.py WORKSPACE A|B|C` checks actual
artifacts, exact numeric expectations, preserved inputs/skills and declared boundaries.
Inspect command receipts separately; the manifest is not an independent proof of the
model's claimed routes or manual handoff count.

- A: native Codex, native skills and memory remain available; no SkillNav helpers.
- B: SkillNav, no SkillNav persistent memory reads/writes.
- C: SkillNav, test-only opt-in state lookup. Preference information is ALSO included
  in equal task prompts for A/B, rather than disadvantaging the native baseline.

Use the same inherited model/settings with no model override. Keep host-native memory
unchanged; do not ingest synthetic personas into a real user's native memory. Report
platform, repeated-run count, failures, actual handoffs, unavailable timing/context
metrics and denominator. This task batch measures quality and process, not a causal
claim that SkillNav remembers better than native Codex. Fresh-context adaptation is a
separate experiment with synthetic consent and correction events.

Host agents receive goals and input paths, not gold labels, previous answers or other
groups' outputs. Read-only boundary responses are test artifacts explicitly requested
by the evaluator, not covert production usage logs.

## E01–E10

| ID | Input / conditions | Expected observable behavior |
| --- | --- | --- |
| E01 | Only SkillNav named; fresh raw CSV | Real report; no downstream manual invocation |
| E02 | Raw CSV needs normalization then reporting | Two actual skills; checked intermediate file passed to reporter |
| E03 | Reporter fixture has a total-accumulation defect | Detect incorrect total; repair only authorized derived output; verify again |
| E04 | Scoped default conflicts with current format/quality | Current requirements and quality prevail; no lasting override |
| E05 | Disabled, disk-only unknown, explicit-only fixtures | No automatic use; disclose distinct status and use a lawful alternative |
| E06 | Missing capability in a bounded test catalog | Check actual external source/version/license; no installation without confirmation |
| E07 | Synthetic endpoint commits then returns timeout | Query authoritative local endpoint state, one object, no duplicate create |
| E08 | Only approved parser cannot decode input | Diagnose and stop without unchanged retries; retain upstream/input |
| E09 | Synthetic HTML preference, JSON correction, new context, other project, deletion | Real formats change; no cross-project inheritance or deleted-rule resurrection |
| E10 | Memory off; trivial request; recommendation-only | Normal delivery, direct answer, or read-only advice respectively |

E07 uses a **local test double**, not an actual external service. E01/E02 are fixture
skills installed only into the isolated project; real user-directory discovery is a
separate installation gate. The tests do not claim generic host or connector support.

Additional required cases in automated tests: unavailable/safe YAML dependency,
permission failures, symbolic links, scope escape, source injection, missing consent,
unknown feedback, three distinct acceptances, multi-step/retry deduplication, aging,
retention, schema/corruption/lock failure, scoped delete, full clear, revisions,
multiple exclusions and bounded recovery.
