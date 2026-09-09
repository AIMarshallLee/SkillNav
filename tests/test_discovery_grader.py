import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("grader", Path(__file__).with_name("verify_discovery_eval.py"))
grader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grader)


class DiscoveryGraderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skillnav-grader-")
        self.root = Path(self.temp.name).resolve()
        (self.root / "A/S01").mkdir(parents=True)
        (self.root / "A/S01/answer.txt").write_text("71\n")
        self.label = {"id": "S01", "route": "direct", "kind": "text", "required_skills": []}
        self.row = {"id": "S01", "status": "completed", "decision": "direct", "reason": "Simple arithmetic",
                    "artifacts": ["answer.txt"], "skills_loaded": [], "skills_applied": [], "manual_handoffs": 0}
        (self.root / "input-manifest.json").write_text("{}")

    def tearDown(self):
        self.temp.cleanup()

    def grade(self):
        labels = json.dumps([self.label])
        (self.root / "labels.json").write_text(labels)
        (self.root / "protocol.json").write_text(json.dumps({"skills_per_case": 364,
            "labels_sha256": hashlib.sha256(labels.encode()).hexdigest()}))
        (self.root / "A/results.json").write_text(json.dumps([self.row]))
        return grader.verify(self.root, "A")

    def test_correct_file_does_not_claim_verified_host_process(self):
        result = self.grade()
        self.assertEqual(result["artifacts_passed"], 1)
        self.assertFalse(result["host_receipts_verified"])
        self.assertNotIn("passed", result)

    def test_fabricated_application_text_is_not_host_verification(self):
        self.label.update(route="skill", kind="invoice", required_skills=["amber-kit"])
        (self.root / "A/S01/result.json").write_text(json.dumps({"format": "bill-audit/1", "input_rows": 3,
            "duplicate_refs": ["INV-17"], "payable_total": "17.50"}))
        self.row.update(decision="skill", artifacts=["result.json"], skills_loaded=["amber-kit"],
                        skills_applied=[{"name": "amber-kit", "kind": "instructions", "evidence": "done"}])
        result = self.grade()
        self.assertEqual(result["declared_decisions_passed"], 1)
        self.assertFalse(result["host_receipts_verified"])
        self.assertEqual(result["behavioral_acceptance"], "not_established_by_this_checker")

    def test_malformed_fields_have_clear_validation_failure(self):
        for field, value in [("id", None), ("id", {}), ("artifacts", [1]), ("skills_loaded", 3),
                             ("skills_applied", [{"name": []}])]:
            with self.subTest(field=field, value=value):
                original = self.row[field]
                self.row[field] = value
                with self.assertRaises(ValueError):
                    self.grade()
                self.row[field] = original
