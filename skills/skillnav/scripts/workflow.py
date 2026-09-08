"""Small in-memory execution contract and recovery budget; not a skill executor.

The host supplies real observations. This module does not grant permissions, run
commands, inspect arbitrary files, persist logs, or authenticate a model's statements.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


class WorkflowError(ValueError):
    pass


class Workflow:
    def __init__(self, checks):
        if not checks or any(not isinstance(c, str) or not c.strip() for c in checks):
            raise WorkflowError("acceptance_checks_required")
        self.required_checks = tuple(checks)
        self.steps = {}
        self.route_changes = 0

    def add_step(self, step, *, dependencies=(), side_effect="local", only_skill=None):
        if step in self.steps or any(d not in self.steps for d in dependencies):
            raise WorkflowError("invalid_step_or_dependency")
        if side_effect not in ("local", "external"):
            raise WorkflowError("invalid_side_effect")
        self.steps[step] = {"dependencies": tuple(dependencies), "side_effect": side_effect,
                            "only_skill": only_skill, "skill": None, "status": "pending",
                            "attempts": 0, "last_diagnosis": None, "artifacts": [], "checks": {}, "pending_skill": None}

    def begin(self, step, skill, *, enabled, available, implicit_allowed, explicitly_selected=False):
        s = self.steps[step]
        if s["status"] not in ("pending", "retry_allowed"):
            raise WorkflowError("step_not_ready")
        if s["pending_skill"] and skill != s["pending_skill"]:
            raise WorkflowError("recovery_route_mismatch")
        if any(self.steps[d]["status"] != "checked" for d in s["dependencies"]):
            raise WorkflowError("upstream_not_checked")
        if not enabled or not available or not (implicit_allowed or explicitly_selected):
            raise WorkflowError("skill_not_eligible")
        if s["only_skill"] and skill != s["only_skill"]:
            raise WorkflowError("user_skill_restriction")
        s.update(status="executing", skill=skill, attempts=s["attempts"] + 1, pending_skill=None)

    def executed(self, step, *, success, result_known=True):
        s = self.steps[step]
        if s["status"] != "executing":
            raise WorkflowError("execution_not_started")
        s["status"] = "executed" if success and result_known else ("unknown" if not result_known else "failed")

    def checked(self, step, checks, artifacts=()):
        s = self.steps[step]
        if s["status"] != "executed":
            raise WorkflowError("execution_required")
        if not checks or any(type(v) is not bool for v in checks.values()):
            raise WorkflowError("boolean_checks_required")
        # Caller checks task semantics; artifact hashes are evidence, not correctness proof.
        s["checks"] = dict(checks)
        s["artifacts"] = list(artifacts)
        s["status"] = "checked" if all(checks.values()) else "failed"

    def recover(self, step, *, diagnosis, new_evidence, change, replacement=None,
                remote_state="not_checked", safe_to_retry=False):
        s = self.steps[step]
        if s["status"] not in ("failed", "unknown"):
            raise WorkflowError("step_not_failed")
        if diagnosis in ("permission", "authorization", "missing_input"):
            return {"action": "stop", "reason": diagnosis}
        if s["side_effect"] == "external":
            # A status query is mandatory before considering any external replay.
            if remote_state == "not_checked":
                return {"action": "query_status", "reason": "external_result_requires_verification"}
            if remote_state == "present":
                return {"action": "verify_existing", "reason": "do_not_repeat_side_effect"}
            if remote_state != "absent" or not safe_to_retry:
                return {"action": "stop", "reason": "external_retry_not_proven_safe"}
        signature = (diagnosis, new_evidence, change, replacement)
        if not new_evidence or not change or signature == s["last_diagnosis"]:
            return {"action": "stop", "reason": "no_new_progress"}
        if s["attempts"] >= 3:
            return {"action": "stop", "reason": "step_retry_budget_exhausted"}
        if replacement and replacement != s["skill"]:
            if s["only_skill"] and replacement != s["only_skill"]:
                return {"action": "stop", "reason": "user_skill_restriction"}
            if self.route_changes >= 2:
                return {"action": "stop", "reason": "route_change_budget_exhausted"}
            self.route_changes += 1
        s.update(status="retry_allowed", last_diagnosis=signature, checks={}, artifacts=[], pending_skill=replacement or s["skill"])
        affected = {step}
        for name, downstream in self.steps.items():
            if any(d in affected for d in downstream["dependencies"]):
                downstream.update(status="pending", checks={}, artifacts=[])
                affected.add(name)
        return {"action": "retry", "affected": sorted(affected), "route_changes": self.route_changes,
                "remaining_extra_attempts": 3 - s["attempts"]}

    def accepted(self):
        checked = {k for s in self.steps.values() for k, value in s["checks"].items() if value}
        return bool(self.steps) and all(s["status"] == "checked" for s in self.steps.values()) and set(self.required_checks) <= checked


def fingerprint_artifact(path, allowed_root):
    root = Path(allowed_root).resolve(strict=True)
    artifact = Path(path).resolve(strict=True)
    if not artifact.is_relative_to(root) or not artifact.is_file():
        raise WorkflowError("artifact_outside_scope_or_not_file")
    digest = hashlib.sha256()
    with artifact.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            digest.update(block)
    return {"relative_path": str(artifact.relative_to(root)), "sha256": digest.hexdigest(), "bytes": artifact.stat().st_size}
