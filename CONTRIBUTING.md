# Contributing

Keep changes scoped to discovery, verified task delivery and opt-in routing state.
No service, extra model account, telemetry or global hook is needed for v0.1.0.

1. Inspect the current implementation and preserve unrelated work.
2. For behavior changes, add a meaningful temporary-fixture regression first.
3. Run `python -m unittest discover -s tests -v` in the isolated environment documented
   in the README. Do not test against private user skill inventories or state.
4. For skill behavior, also run a fresh real-host task and inspect actual artifacts.
   A deterministic script test is not semantic/host validation. Record model settings,
   fixture version, inputs, checks, failures and untested limits without personal paths.
5. Review the diff for credentials, raw conversations, taskbook attachments, state DBs,
   private inventories and downloaded third-party bundles before submission.

Use a feature branch. Explain what changed, why, focused tests, host evidence and
remaining uncertainty. Do not add permissions, enable implicit invocation, or change
privacy defaults as a side effect of another patch. No force pushes or unapproved
publication. Report bugs using synthetic inputs and minimal redacted evidence, never
an entire private database or Codex home directory.

Contributions are under the project's Apache-2.0 license. Preserve third-party notices
when applicable; do not copy skill packs without checking their actual license.
