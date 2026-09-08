# Security and data boundaries

SkillNav v0.1.0 is a local candidate. Do not send secrets, customer originals, browser
sessions, real memory DBs or full machine inventories in issues. For a sensitive
finding, use GitHub's private vulnerability-reporting channel **if enabled**; otherwise
request a private channel without disclosing the exploit or affected private data.
No response SLA or currently enabled reporting feature is implied.

## What is enforced by code

- Scanner: declared directory roots, real-path checks, symlink loop/escape reporting,
  no `.env` via SKILL.md symlink, bounded metadata, SafeLoader with no aliases or duplicate
  keys, no body execution, no network, no inventory persistence.
- State: opt-in creation, restricted fields, no raw text storage, private POSIX modes,
  transactions, bounded lock wait, expected revisions, project/task/environment and
  fingerprint filters, independent feedback, bounded evidence retention and deletion.
- Recovery helper: in-memory attempt/route budgets, upstream checks before handoff,
  no automatic replay of uncertain external effects, no external command runner.

## What remains a host responsibility

The host must verify actual user messages, scope, tool permissions, current candidate
enablement/invocation policy, and honest execution/check evidence. A JSON authorization
receipt is a host attestation, not human authentication. A caller with file/process
access can forge it or bypass Python helpers. Prompt injection is not “solved” by a
text skill or a `source=user` flag. Do not treat documents, skill bodies or tool outputs
as user authorization. Application scope filters are not OS isolation.

The DB is not encrypted. Hashes are identifiers, not anonymization. Deletion is logical
within managed records, not forensic disk erasure or deletion of host chats/backups.
Filesystem races and hostile local processes are outside the scanner's guarantee;
use a trusted/stable local root and the host sandbox. Tests do not certify every OS,
plugin, downstream skill, connector or account.

## Operational response

If state fails, route without memory and state that nothing was saved; preserve the
original file rather than silently recreating it. If an external operation is
ambiguous, query authoritative state before retrying. Never change credentials,
third-party source, installation policy or remote visibility to get past a failure.
New installations and publication require specific authorization.
