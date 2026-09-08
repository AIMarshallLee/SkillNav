"""Behavior contracts first: all state lives in disposable private directories."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

SCRIPT = Path(__file__).resolve().parents[1] / "skills/skillnav/scripts/state.py"
spec = importlib.util.spec_from_file_location("state", SCRIPT)
state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state)


def authorization(action, task_id=None):
    result = {"origin": "direct_user", "message_ref": "test-user-message-1",
              "verified_by_host": True, "action": action}
    if task_id:
        result["task_id"] = task_id
    return result


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skillnav-test-")
        self.db = Path(self.temp.name) / "private" / "state.sqlite3"
        self.now = 1700000000
        self.s = state.Store(self.db, test_mode=True, clock=lambda: self.now)

    def tearDown(self):
        self.temp.cleanup()

    def call(self, action, **payload):
        if action not in ("status", "context"):
            payload.setdefault("expected_revision", self.s.dispatch("status", {}).get("revision", 0))
        return self.s.dispatch(action, payload)

    def enable(self):
        return self.call("enable", authorization=authorization("enable"))

    def prefer(self, value="markdown", project="project-a", **extra):
        args = dict(scope="project", project=project, task_type="report", key="output_format",
                    value=value, authorization=authorization("preference"))
        args.update(extra)
        return self.call("preference", **args)

    def context(self, project="project-a", **extra):
        return self.call("context", project=project, task_type="report", environment="env-a", **extra)

    def outcome(self, task_id="task-1", **extra):
        args = dict(task_id=task_id, project="project-a", task_type="report", skill_id="a" * 64,
                    fingerprint="b" * 64, host="codex-test", environment="env-a", stage="executed",
                    check="passed", blocker="none", key="output_format", value="markdown")
        args.update(extra)
        return self.call("outcome", **args)

    def accept(self, task_id):
        return self.call("feedback", task_id=task_id, project="project-a", feedback="accepted",
                         authorization=authorization("feedback", task_id))

    def learn(self):
        for i in range(3):
            self.outcome(f"task-{i}")
            self.accept(f"task-{i}")

    def test_no_consent_creates_nothing(self):
        self.assertEqual(self.context()["memory"], "off")
        self.assertFalse(self.prefer()["ok"])
        self.assertFalse(self.db.parent.exists())

    def test_project_and_task_scope(self):
        self.enable()
        self.prefer()
        self.assertEqual(self.context()["defaults"]["output_format"], "markdown")
        self.assertEqual(self.context("project-b")["defaults"], {})
        self.assertEqual(self.call("context", project="project-a", task_type="code", environment="env-a")["defaults"], {})

    def test_reverse_correction_replaces_long_term_default(self):
        self.enable()
        self.prefer()
        self.prefer("docx")
        self.s = state.Store(self.db, test_mode=True, clock=lambda: self.now)
        self.assertEqual(self.context()["defaults"]["output_format"], "docx")
        self.assertEqual(len(self.context()["preferences"]), 1)

    def test_current_exception_does_not_rewrite(self):
        self.enable()
        self.prefer()
        before = self.db.read_bytes()
        self.assertEqual(self.context(overrides={"output_format": "docx"})["defaults"]["output_format"], "docx")
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(self.context()["defaults"]["output_format"], "markdown")

    def test_explicit_project_overrides_personal(self):
        self.enable()
        self.prefer("pdf", scope="personal", project=None)
        self.prefer("markdown")
        self.assertEqual(self.context()["defaults"]["output_format"], "markdown")
        self.assertEqual(self.context("project-b")["defaults"]["output_format"], "pdf")

    def test_tool_success_and_silence_do_not_learn(self):
        self.enable()
        for i in range(5):
            self.outcome(f"task-{i}")
        self.assertEqual(self.context()["defaults"], {})
        self.assertTrue(all(o["feedback"] == "unknown" for o in self.context()["outcomes"]))

    def test_three_independent_acceptances_only(self):
        self.enable()
        for _ in range(3):
            self.outcome()
            self.accept("task-1")
        self.assertEqual(self.context()["defaults"], {})
        for i in (2, 3):
            self.outcome(f"task-{i}")
            self.accept(f"task-{i}")
        self.assertEqual(self.context()["defaults"]["output_format"], "markdown")
        self.assertEqual(self.context()["preferences"][0]["source"], "observed")

    def test_passed_check_and_rejection_coexist(self):
        self.enable()
        self.outcome()
        self.call("feedback", task_id="task-1", project="project-a", feedback="rejected",
                  authorization=authorization("feedback", "task-1"))
        record = self.context()["outcomes"][0]
        self.assertEqual((record["check"], record["feedback"]), ("passed", "rejected"))

    def test_environment_and_version_change_invalidate_success(self):
        self.enable()
        self.learn()
        new_env = self.call("context", project="project-a", task_type="report", environment="env-b")
        self.assertEqual(new_env["defaults"], {})
        fresh = self.context(candidates=[{"skill_id": "a" * 64, "fingerprint": "c" * 64,
                                         "enabled": True, "available": True}])
        self.assertEqual(fresh["defaults"], {})
        self.assertEqual(fresh["outcomes"], [])

    def test_disabled_or_removed_skill_not_reused(self):
        self.enable()
        self.learn()
        self.assertEqual(self.context(candidates=[])["defaults"], {})
        self.assertEqual(self.context(candidates=[{"skill_id": "a" * 64, "fingerprint": "b" * 64,
                                                 "enabled": False, "available": True}])["defaults"], {})

    def test_observations_age_after_thirty_days(self):
        self.enable()
        self.learn()
        self.now += 31 * 86400
        self.assertEqual(self.context()["defaults"], {})
        self.prefer("docx")
        self.now += 100 * 86400
        self.assertEqual(self.context()["defaults"]["output_format"], "docx")

    def test_untrusted_memory_injection_rejected(self):
        self.enable()
        for origin in ("web", "skill", "tool", "model"):
            receipt = dict(authorization("preference"), origin=origin)
            self.assertFalse(self.prefer(authorization=receipt)["ok"])
        self.assertFalse(self.prefer(authorization={"source": "user"})["ok"])
        self.assertEqual(self.context()["defaults"], {})

    def test_learning_off_and_reading_off_are_distinct(self):
        self.enable()
        self.prefer()
        self.call("controls", learning=False, authorization=authorization("controls"))
        self.assertFalse(self.prefer("pdf")["ok"])
        self.assertEqual(self.context()["defaults"]["output_format"], "markdown")
        self.call("controls", reading=False, authorization=authorization("controls"))
        self.assertEqual(self.context()["defaults"], {})

    def test_no_memory_mode_does_not_read_or_write(self):
        self.enable()
        self.prefer()
        before = self.db.read_bytes()
        self.assertEqual(self.s.dispatch("context", {}, no_memory=True)["defaults"], {})
        self.assertFalse(self.s.dispatch("preference", {}, no_memory=True)["saved"])
        self.assertEqual(self.db.read_bytes(), before)

    def test_delete_removes_evidence_and_cannot_relearn_on_restart(self):
        self.enable()
        self.learn()
        pref_id = self.context()["preferences"][0]["id"]
        self.call("forget", preference_id=pref_id, authorization=authorization("forget"))
        self.s = state.Store(self.db, test_mode=True, clock=lambda: self.now)
        self.assertEqual(self.context()["defaults"], {})
        self.assertEqual(self.context()["outcomes"], [])
        self.outcome("new-task")
        self.accept("new-task")
        self.assertEqual(self.context()["defaults"], {})

    def test_correction_then_forget_does_not_restore_prior_observation(self):
        self.enable()
        self.learn()
        self.prefer("docx")
        pref_id = self.context()["preferences"][0]["id"]
        self.call("forget", preference_id=pref_id, authorization=authorization("forget"))
        self.outcome("later")
        self.assertEqual(self.context()["defaults"], {})

    def test_clear_project_preserves_other_project(self):
        self.enable()
        self.prefer()
        self.prefer("pdf", project="project-b")
        self.call("clear-project", project="project-a", authorization=authorization("clear-project"))
        self.assertEqual(self.context()["defaults"], {})
        self.assertEqual(self.context("project-b")["defaults"]["output_format"], "pdf")

    def test_correction_preserves_checks_but_removes_old_learning_association(self):
        self.enable()
        self.learn()
        self.prefer("docx")
        old = self.context()["outcomes"]
        self.assertEqual(len(old), 3)
        self.assertTrue(all(o["check"] == "passed" and o["feedback"] == "accepted" for o in old))
        self.assertTrue(all(o["key"] is None and o["value"] is None for o in old))
        self.assertEqual(self.context()["defaults"]["output_format"], "docx")

    def test_clear_all_disables_learning_and_clears_everything(self):
        self.enable()
        self.learn()
        self.call("clear-all", authorization=authorization("clear-all"))
        status = self.call("status")
        self.assertFalse(status["learning"])
        self.assertEqual(status["outcome_count"], 0)
        self.assertEqual(status["preference_count"], 0)

    def test_stale_writer_cannot_restore_deleted_data(self):
        self.enable()
        old_revision = self.call("status")["revision"]
        self.call("clear-all", authorization=authorization("clear-all"))
        self.enable()
        self.assertEqual(self.prefer(expected_revision=old_revision)["error"], "revision_conflict")

    def test_concurrent_writers_report_conflict_instead_of_losing_updates(self):
        self.enable()
        revision = self.call("status")["revision"]
        def write(i):
            store = state.Store(self.db, test_mode=True)
            return store.dispatch("preference", dict(scope="project", project=f"project-{i}",
                task_type="report", key="output_format", value="pdf", expected_revision=revision,
                authorization=authorization("preference")))
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(write, range(4)))
        self.assertEqual(sum(r["ok"] for r in results), 1)
        self.assertTrue(all(r["ok"] or r["error"] == "revision_conflict" for r in results))
        for i, result in enumerate(results):
            if not result["ok"]:
                self.prefer("pdf", project=f"project-{i}")
        self.assertEqual(self.call("status")["preference_count"], 4)

    def test_feedback_is_bound_to_task_and_project(self):
        self.enable()
        self.outcome()
        self.assertFalse(self.call("feedback", task_id="task-1", project="project-b", feedback="accepted",
                                   authorization=authorization("feedback", "task-1"))["ok"])
        self.assertFalse(self.call("feedback", task_id="task-1", project="project-a", feedback="accepted",
                                   authorization=authorization("feedback", "task-2"))["ok"])

    def test_retry_cannot_change_task_attribution(self):
        self.enable()
        self.outcome()
        self.assertFalse(self.outcome(project="project-b")["ok"])

    def test_retention_revokes_unsupported_observations(self):
        self.enable()
        self.learn()
        for i in range(200):
            self.now += 1
            self.outcome(f"unaccepted-{i}")
        self.assertEqual(self.call("status")["outcome_count"], 200)
        self.assertEqual(self.context()["defaults"], {})

    def test_corrupt_and_future_schema_are_not_recreated(self):
        self.db.parent.mkdir()
        self.db.write_bytes(b"not a sqlite database")
        self.db.chmod(0o600)
        self.db.parent.chmod(0o700)
        before = self.db.read_bytes()
        self.assertEqual(self.context()["memory"], "unavailable")
        self.assertFalse(self.enable()["ok"])
        self.assertEqual(self.db.read_bytes(), before)

    def test_no_raw_text_fields_or_unknown_rule_keys(self):
        self.enable()
        self.assertFalse(self.prefer(key="customer_body", value="secret")["ok"])
        self.assertFalse(self.outcome(raw_task="private content")["ok"])

    def test_multi_step_task_does_not_count_as_three_tasks(self):
        self.enable()
        for i in range(3):
            self.assertTrue(self.outcome("same-task", step_id=f"step-{i}")["ok"])
            self.call("feedback", task_id="same-task", step_id=f"step-{i}", project="project-a",
                      feedback="accepted", authorization=authorization("feedback", "same-task"))
        self.assertEqual(self.context()["defaults"], {})
        self.assertEqual(len(self.context()["outcomes"]), 3)

    def test_future_schema_preserved(self):
        import sqlite3
        self.enable()
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE settings SET schema_version=999")
        before = self.db.read_bytes()
        self.assertEqual(self.context()["error"], "unsupported_schema_preserved")
        self.assertEqual(self.db.read_bytes(), before)

    def test_network_blocker_is_not_positive_evidence(self):
        self.enable()
        for i in range(3):
            self.outcome(f"task-{i}", stage="blocked", check="not_run", blocker="network")
            self.accept(f"task-{i}")
        self.assertEqual(self.context()["defaults"], {})

    def test_unwritable_and_locked_state_falls_back(self):
        import sqlite3
        from unittest.mock import patch
        self.enable()
        with patch.object(self.s, "_connect", side_effect=PermissionError()):
            self.assertFalse(self.prefer()["saved"])
        locked = sqlite3.connect(self.db, isolation_level=None)
        locked.execute("BEGIN IMMEDIATE")
        try:
            self.s.timeout = 0.01
            self.assertFalse(self.prefer()["saved"])
        finally:
            locked.execute("ROLLBACK")
            locked.close()

    def test_excluded_skills_filter_history_and_keep_multiple_exclusions(self):
        self.enable()
        self.learn()
        self.prefer("a" * 64, key="exclude_skill")
        self.prefer("c" * 64, key="exclude_skill")
        ctx = self.context(candidates=[{"skill_id": "a" * 64, "fingerprint": "b" * 64,
                                       "enabled": True, "available": True}])
        self.assertEqual(ctx["outcomes"], [])
        self.assertEqual(ctx["excluded_skill_ids"], ["a" * 64, "c" * 64])
        self.assertEqual(self.context("project-b").get("excluded_skill_ids"), [])

    def test_personal_exclusion_and_current_exception(self):
        self.enable()
        self.prefer("a" * 64, key="exclude_skill", scope="personal", project=None)
        self.assertEqual(self.context("project-b")["excluded_skill_ids"], ["a" * 64])
        self.assertEqual(self.context(overrides={"prefer_skill": "a" * 64})["excluded_skill_ids"], [])
        self.assertEqual(self.context()["excluded_skill_ids"], ["a" * 64])


if __name__ == "__main__":
    unittest.main()
