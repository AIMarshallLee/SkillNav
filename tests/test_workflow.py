import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("workflow", Path(__file__).resolve().parents[1] / "skills/skillnav/scripts/workflow.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class WorkflowTests(unittest.TestCase):
    def workflow(self, side_effect="local"):
        w = m.Workflow(["rows", "total"])
        w.add_step("normalize")
        w.add_step("report", dependencies=["normalize"], side_effect=side_effect)
        self.begin(w, "normalize")
        w.executed("normalize", success=True)
        w.checked("normalize", {"rows": True})
        return w

    def begin(self, w, step, skill="example"):
        w.begin(step, skill, enabled=True, available=True, implicit_allowed=True)

    def test_handoff_requires_actual_upstream_check(self):
        w = m.Workflow(["rows"])
        w.add_step("a")
        w.add_step("b", dependencies=["a"])
        with self.assertRaises(m.WorkflowError):
            self.begin(w, "b")

    def test_exit_success_does_not_mean_quality_passed(self):
        w = self.workflow()
        self.begin(w, "report")
        w.executed("report", success=True)
        self.assertFalse(w.accepted())
        w.checked("report", {"total": False})
        self.assertFalse(w.accepted())

    def test_local_repair_preserves_validated_upstream(self):
        w = self.workflow()
        self.begin(w, "report")
        w.executed("report", success=True)
        w.checked("report", {"total": False})
        decision = w.recover("report", diagnosis="wrong_format", new_evidence="columns mismatch", change="use normalized columns")
        self.assertEqual(decision["action"], "retry")
        self.assertEqual(w.steps["normalize"]["status"], "checked")
        self.begin(w, "report")
        w.executed("report", success=True)
        w.checked("report", {"total": True})
        self.assertTrue(w.accepted())

    def test_two_extra_attempts_limit(self):
        w = self.workflow()
        for i in range(3):
            self.begin(w, "report")
            w.executed("report", success=False)
            r = w.recover("report", diagnosis="format", new_evidence=f"new-{i}", change=f"fix-{i}")
        self.assertEqual(r["reason"], "step_retry_budget_exhausted")
        self.assertEqual(w.steps["report"]["attempts"], 3)

    def test_task_wide_route_change_limit(self):
        w = self.workflow()
        for i in range(3):
            step = f"later-{i}"
            w.add_step(step)
            self.begin(w, step)
            w.executed(step, success=False)
            r = w.recover(step, diagnosis="mismatch", new_evidence=f"new-{i}", change="switch", replacement="alternative")
        self.assertEqual(r["reason"], "route_change_budget_exhausted")
        self.assertEqual(w.route_changes, 2)

    def test_no_progress_stops_early(self):
        w = self.workflow()
        self.begin(w, "report")
        w.executed("report", success=False)
        r = w.recover("report", diagnosis="format", new_evidence="", change="repeat")
        self.assertEqual(r["reason"], "no_new_progress")

    def test_unknown_external_effect_queries_before_replay(self):
        w = self.workflow("external")
        self.begin(w, "report")
        w.executed("report", success=False, result_known=False)
        args = dict(diagnosis="network", new_evidence="timeout", change="retry")
        self.assertEqual(w.recover("report", **args)["action"], "query_status")
        self.assertEqual(w.recover("report", remote_state="unknown", **args)["action"], "stop")
        self.assertEqual(w.recover("report", remote_state="present", **args)["action"], "verify_existing")
        self.assertEqual(w.steps["report"]["attempts"], 1)

    def test_permission_cannot_be_routed_around(self):
        w = self.workflow()
        self.begin(w, "report")
        w.executed("report", success=False)
        self.assertEqual(w.recover("report", diagnosis="permission", new_evidence="denied", change="switch", replacement="other")["action"], "stop")

    def test_disabled_and_explicit_only_remain_ineligible(self):
        w = m.Workflow(["total"])
        w.add_step("a")
        for enabled, implicit in ((False, True), (True, False)):
            with self.assertRaises(m.WorkflowError):
                w.begin("a", "candidate", enabled=enabled, available=True, implicit_allowed=implicit)
        w.begin("a", "candidate", enabled=True, available=True, implicit_allowed=False, explicitly_selected=True)

    def test_user_only_skill_prevents_replacement(self):
        w = m.Workflow(["total"])
        w.add_step("a", only_skill="selected")
        self.begin(w, "a", "selected")
        w.executed("a", success=False)
        r = w.recover("a", diagnosis="format", new_evidence="wrong", change="switch", replacement="other")
        self.assertEqual(r["reason"], "user_skill_restriction")

    def test_next_attempt_must_match_approved_recovery_route(self):
        w = self.workflow()
        self.begin(w, "report", "old")
        w.executed("report", success=False)
        w.recover("report", diagnosis="format", new_evidence="schema", change="switch", replacement="new")
        with self.assertRaises(m.WorkflowError):
            self.begin(w, "report", "old")
        self.begin(w, "report", "new")
        self.assertEqual(w.steps["report"]["skill"], "new")

    def test_artifact_scope_and_real_fingerprint(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "result.md"
            p.write_text("actual content")
            self.assertEqual(m.fingerprint_artifact(p, d)["bytes"], 14)
            with self.assertRaises(m.WorkflowError):
                m.fingerprint_artifact(__file__, d)


if __name__ == "__main__":
    unittest.main()
