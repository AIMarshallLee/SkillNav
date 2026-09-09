import json
from pathlib import Path
import tempfile
import unittest

from verify_bundle_eval import verify


class BundleGraderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skillnav-bundle-grader-")
        self.root = Path(self.temp.name).resolve()
        for name in ("direct", "find_execute", "review", "create/drafts/team-weekly-brief/agents"):
            (self.root / name).mkdir(parents=True)
        (self.root / "inputs.json").write_text("{}")
        (self.root / "direct/answer.txt").write_text("71")
        (self.root / "find_execute/result.json").write_text(json.dumps({
            "format": "bill-audit/1", "input_rows": 3,
            "duplicate_refs": ["INV-17"], "payable_total": "17.50"}))
        (self.root / "find_execute/notice.md").write_text(
            "# Billing notice\nAmount due: 17.50\nDuplicate references: INV-17\nStatus: draft\n")
        (self.root / "review/review.md").write_text("A report requires separate semantic review.")
        for path in ("SKILL.md", "agents/openai.yaml"):
            (self.root / "create/drafts/team-weekly-brief" / path).write_text("fixture")
        self.weekly = "# 团队周报\n## 本周完成\n- 完成报价模板\n## 下周计划\n- 核对采购清单\n## 待协调\n- 等待图纸确认\n## 需确认\n无\n状态：草稿\n"

    def tearDown(self):
        self.temp.cleanup()

    def test_trial_report_links_to_actual_weekly_output(self):
        (self.root / "create/actual-output.md").write_text(self.weekly)
        (self.root / "create/trial.md").write_text("Trial report: [actual result](actual-output.md).")
        result = verify(self.root)
        self.assertTrue(result["all_artifact_checks_passed"])
        self.assertEqual(result["creation_sample_outputs"], ["create/actual-output.md"])
        self.assertFalse(result["host_receipts_verified_by_this_checker"])
        self.assertFalse(result["review_semantics_verified_by_this_checker"])

    def test_unlinked_or_outside_output_does_not_satisfy_trial(self):
        (self.root / "outside.md").write_text(self.weekly)
        (self.root / "create/trial.md").write_text("[not a task output](../outside.md)")
        self.assertFalse(verify(self.root)["artifact_checks"]["creation_sample_output_contract"])
        (self.root / "create/trial.md").write_text(self.weekly)
        self.assertFalse(verify(self.root)["artifact_checks"]["creation_sample_output_contract"])


if __name__ == "__main__":
    unittest.main()
