"""Regression checks for the independent P0 host-run grader."""
from pathlib import Path
import tempfile
import unittest

from verify_p0_eval import verify


class P0GraderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "before"
        for name in ("weekly", "table", "content"):
            (self.target / name).mkdir(parents=True)
        (self.root / "inputs.json").write_text("{}")

    def write_outputs(self):
        for path, content in {
            "weekly/weekly.md": "# 团队周报\n## 本周完成\n- 完成报价模板\n## 下周计划\n- 核对采购清单\n## 待协调\n- 等待图纸确认\n## 需确认\n无\n状态：草稿\n",
            "weekly/trial.md": "Trial report: see [weekly](weekly.md).",
            "table/totals.csv": "product,total\n台灯,7.50\n笔记本,12.30\n",
            "table/check.md": "Checked separately.",
            "content/release.md": "# 更新草稿\n## 新增\n- 新增离线导出\n## 修复\n- 修复空标题\n## 待确认\n- unknown|兼容情况待确认\n状态：草稿\n",
            "content/check.md": "Checked separately.",
            "weekly/drafts/team-weekly-brief/SKILL.md": "Synthetic entry only; this grader checks presence.",
            "weekly/drafts/team-weekly-brief/agents/openai.yaml": "policy: {}",
        }.items():
            file = self.target / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(content)

    def test_report_cannot_substitute_for_actual_weekly_output(self):
        self.write_outputs()
        self.assertTrue(verify(self.root, "before")["all_passed"])
        output = self.target / "weekly/weekly.md"
        (self.target / "weekly/trial.md").write_text(output.read_text())
        output.unlink()
        result = verify(self.root, "before")
        self.assertTrue(result["checks"]["weekly_trial_report"])
        self.assertFalse(result["checks"]["weekly_output"])
        self.assertFalse(result["all_passed"])

    def test_correct_shape_with_wrong_amount_fails(self):
        self.write_outputs()
        (self.target / "table/totals.csv").write_text("product,total\n台灯,7.50\n笔记本,12.31\n")
        result = verify(self.root, "before")
        self.assertFalse(result["checks"]["table_totals"])
        self.assertFalse(result["all_passed"])


if __name__ == "__main__":
    unittest.main()
