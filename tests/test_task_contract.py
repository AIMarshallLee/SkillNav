import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/skillnav/scripts/task_contract.py"
spec = importlib.util.spec_from_file_location("task_contract", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class TaskContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skillnav-contract-")
        self.root = Path(os.path.realpath(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, data):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return target

    def contract(self, *, inputs=None, requirements=None, artifacts=None):
        return {"version": 1,
                "inputs": inputs if inputs is not None else [{"id": "source", "path": "source.md", "format": "text", "checks": [{"type": "contains", "expected": "week"}]}],
                "requirements": requirements if requirements is not None else [{"id": "python", "kind": "host_tool", "status": "verified", "evidence": "host inventory 2026-09-09"}],
                "artifacts": artifacts if artifacts is not None else [
                    {"id": "weekly", "path": "out/weekly.md", "role": "deliverable", "format": "text", "checks": [{"type": "markdown_headings", "expected": ["# Weekly", "## Summary"]}]},
                    {"id": "receipt", "path": "out/check.json", "role": "report", "format": "json", "checks": [{"type": "json_equals", "expected": {"ok": True}}]},
                ]}

    def save_contract(self, contract, name="contract.json"):
        return self.write(name, json.dumps(contract))

    def test_weekly_deliverable_and_separate_report_pass(self):
        self.write("source.md", "week 37 source")
        self.write("out/weekly.md", "# Weekly\nbody\n## Summary\ncomplete\n")
        self.write("out/check.json", '{"ok":true}')
        contract = self.save_contract(self.contract())
        preflight = m.preflight(self.root, contract)
        report = m.check(self.root, contract)
        self.assertTrue(preflight["ok"])
        self.assertEqual(preflight["artifacts"][0]["status"], "not_checked")
        self.assertTrue(report["ok"])
        self.assertEqual([(x["id"], x["role"], x["status"]) for x in report["artifacts"]],
                         [("weekly", "deliverable", "passed"), ("receipt", "report", "passed")])
        self.assertIn("sha256", report["artifacts"][0])
        self.assertIn("sha256", report["contract"])
        self.assertNotIn("expected", json.dumps(report))

    def test_report_cannot_substitute_for_deliverable(self):
        self.write("source.md", "week 37 source")
        self.write("out/weekly.md", "# Weekly\nbody\n## Summary\ncomplete\n")
        contract = self.contract(artifacts=[
            {"id": "same", "path": "out/weekly.md", "role": "deliverable", "format": "text", "checks": [{"type": "contains", "expected": "body"}]},
            {"id": "receipt", "path": "out/weekly.md", "role": "report", "format": "text", "checks": [{"type": "contains", "expected": "body"}]},
        ])
        with self.assertRaisesRegex(m.ContractError, "artifact_path_reused"):
            m.preflight(self.root, self.save_contract(contract))

    def test_preflight_rejects_empty_missing_input_and_unverified_requirement(self):
        contract = self.contract()
        self.write("source.md", b"")
        preflight = m.preflight(self.root, self.save_contract(contract))
        self.assertFalse(preflight["ok"])
        self.assertEqual(preflight["inputs"][0]["reason"], "file_empty")
        self.write("source.md", "week")
        (self.root / "source.md").unlink()
        missing = m.preflight(self.root, self.save_contract(contract, "missing.json"))
        self.assertEqual(missing["inputs"][0]["reason"], "file_missing")
        self.write("source.md", "week")
        for status in ("missing", "unknown"):
            candidate = self.contract(requirements=[{"id": "dep", "kind": "dependency", "status": status, "evidence": "host observation"}])
            report = m.preflight(self.root, self.save_contract(candidate, f"{status}.json"))
            self.assertFalse(report["ok"])
            self.assertEqual(report["requirements"][0]["observed_status"], status)
            self.assertEqual(report["requirements"][0]["reason"], "requirement_not_verified")

    def test_content_mismatch_and_unknown_or_empty_checks_fail(self):
        self.write("source.md", "week")
        self.write("out/weekly.md", "# Wrong")
        self.write("out/check.json", '{"ok":true}')
        report = m.check(self.root, self.save_contract(self.contract()))
        self.assertFalse(report["ok"])
        self.assertEqual(report["artifacts"][0]["reason"], "check_failed_markdown_headings")
        broken = self.contract(inputs=[{"id": "source", "path": "source.md", "format": "text", "checks": []}])
        with self.assertRaisesRegex(m.ContractError, "checks_required"):
            m.preflight(self.root, self.save_contract(broken, "empty.json"))
        broken["inputs"][0]["checks"] = [{"type": "made_up", "expected": "x"}]
        with self.assertRaisesRegex(m.ContractError, "unknown"):
            m.preflight(self.root, self.save_contract(broken, "unknown.json"))
        broken["inputs"][0]["checks"] = [{"type": "contains", "expected": "x", "passed": True}]
        with self.assertRaisesRegex(m.ContractError, "schema"):
            m.preflight(self.root, self.save_contract(broken, "model-passed.json"))

    def test_csv_and_json_content_rules(self):
        self.write("source.csv", "name,total\na,3\nb,4\n")
        self.write("out/result.json", '{"summary":{"rows":2},"ok":true}')
        contract = self.contract(
            inputs=[{"id": "source", "path": "source.csv", "format": "csv", "checks": [
                {"type": "csv_columns", "expected": ["name", "total"]}, {"type": "csv_row_count", "expected": 2}]}],
            artifacts=[{"id": "data", "path": "out/result.json", "role": "deliverable", "format": "json", "checks": [
                {"type": "json_equals", "expected": {"summary": {"rows": 2}, "ok": True}}]}],
        )
        report = m.check(self.root, self.save_contract(contract))
        self.assertTrue(report["ok"])
        contract["artifacts"][0]["checks"][0]["expected"]["ok"] = False
        wrong = m.check(self.root, self.save_contract(contract, "wrong-json.json"))
        self.assertEqual(wrong["artifacts"][0]["reason"], "check_failed_json_equals")
        contract["inputs"][0]["checks"][1]["expected"] = 3
        wrong_csv = m.preflight(self.root, self.save_contract(contract, "wrong-csv.json"))
        self.assertEqual(wrong_csv["inputs"][0]["reason"], "check_failed_csv_row_count")

    def test_schema_and_path_boundaries_reject_links_duplicates_and_outside_files(self):
        self.write("source.md", "week")
        self.write("out/weekly.md", "# Weekly\n## Summary")
        self.write("out/check.json", '{"ok":true}')
        duplicate = b'{"version":1,"version":1,"inputs":[],"requirements":[],"artifacts":[]}'
        duplicate_path = self.write("duplicate.json", duplicate)
        with self.assertRaisesRegex(m.ContractError, "duplicate_key"):
            m.preflight(self.root, duplicate_path)
        outside = self.contract(inputs=[{"id": "source", "path": "../escape.txt", "format": "text", "checks": [{"type": "contains", "expected": "week"}]}])
        with self.assertRaisesRegex(m.ContractError, "path_outside_root"):
            m.preflight(self.root, self.save_contract(outside, "outside.json"))
        self.write("real.md", "week")
        os.symlink(self.root / "real.md", self.root / "source-link.md")
        linked = self.contract(inputs=[{"id": "source", "path": "source-link.md", "format": "text", "checks": [{"type": "contains", "expected": "week"}]}])
        with self.assertRaisesRegex(m.ContractError, "path_symlink_rejected"):
            m.preflight(self.root, self.save_contract(linked, "link.json"))
        (self.root / "linked-dir-target").mkdir()
        self.write("linked-dir-target/source.md", "week")
        os.symlink(self.root / "linked-dir-target", self.root / "linked-dir")
        ancestor_link = self.contract(inputs=[{"id": "source", "path": "linked-dir/source.md", "format": "text", "checks": [{"type": "contains", "expected": "week"}]}])
        with self.assertRaisesRegex(m.ContractError, "path_symlink_rejected"):
            m.preflight(self.root, self.save_contract(ancestor_link, "ancestor-link.json"))
        os.link(self.root / "real.md", self.root / "source-hard.md")
        hard = self.contract(inputs=[{"id": "source", "path": "source-hard.md", "format": "text", "checks": [{"type": "contains", "expected": "week"}]}])
        report = m.preflight(self.root, self.save_contract(hard, "hard.json"))
        self.assertEqual(report["inputs"][0]["reason"], "file_hardlink_rejected")
        if hasattr(os, "mkfifo"):
            os.mkfifo(self.root / "source.fifo")
            special = self.contract(inputs=[{"id": "source", "path": "source.fifo", "format": "text", "checks": [{"type": "contains", "expected": "week"}]}])
            report = m.preflight(self.root, self.save_contract(special, "special.json"))
            self.assertEqual(report["inputs"][0]["reason"], "file_not_regular")

    def test_preflight_validates_all_declared_output_paths_and_separation(self):
        self.write("source.md", "week")
        contract = self.contract(artifacts=[{"id": "weekly", "path": "planned/output.md", "role": "deliverable", "format": "text", "checks": [{"type": "contains", "expected": "ready"}]}])
        self.assertTrue(m.preflight(self.root, self.save_contract(contract))["ok"])
        contract["artifacts"][0]["path"] = "../outside.md"
        with self.assertRaisesRegex(m.ContractError, "path_outside_root"):
            m.preflight(self.root, self.save_contract(contract, "output-outside.json"))
        contract["artifacts"][0]["path"] = str(self.root / "absolute.md")
        with self.assertRaisesRegex(m.ContractError, "artifact_path_not_relative"):
            m.preflight(self.root, self.save_contract(contract, "output-absolute.json"))
        contract["artifacts"][0]["path"] = "contract-reused.json"
        with self.assertRaisesRegex(m.ContractError, "artifact_path_contract_reused"):
            m.preflight(self.root, self.save_contract(contract, "contract-reused.json"))
        contract["artifacts"][0]["path"] = "source.md"
        with self.assertRaisesRegex(m.ContractError, "input_artifact_path_reused"):
            m.preflight(self.root, self.save_contract(contract, "input-output-reused.json"))
        contract["artifacts"][0]["path"] = "planned/output.md"
        contract["artifacts"][0]["id"] = "source"
        with self.assertRaisesRegex(m.ContractError, "input_artifact_id_reused"):
            m.preflight(self.root, self.save_contract(contract, "id-reused.json"))
        self.write("real-output.md", "ready")
        os.symlink(self.root / "real-output.md", self.root / "linked-output.md")
        contract["artifacts"][0]["id"] = "weekly"
        contract["artifacts"][0]["path"] = "linked-output.md"
        with self.assertRaisesRegex(m.ContractError, "path_symlink_rejected"):
            m.preflight(self.root, self.save_contract(contract, "linked-output.json"))

    def test_schema_types_and_strict_json_values_have_clean_errors(self):
        self.write("source.md", "week")
        base = self.contract()
        invalids = [
            ("version", True, "contract_version"),
            ("inputs.0.format", [], "input_0_format"),
            ("artifacts.0.role", {}, "artifact_0_role"),
            ("inputs.0.checks.0.type", [], "input_0_check_0_unknown"),
            ("requirements.0.kind", [], "requirement_0_kind"),
            ("requirements.0.status", {}, "requirement_0_status"),
            ("csv_columns", [{"type": "csv_columns", "expected": [["bad"]]}], "input_0_check_0_expected"),
        ]
        for index, (field, value, reason) in enumerate(invalids):
            candidate = json.loads(json.dumps(base))
            if field == "version":
                candidate["version"] = value
            elif field == "csv_columns":
                candidate["inputs"][0]["format"] = "csv"
                candidate["inputs"][0]["checks"] = value
            else:
                cursor = candidate
                parts = field.split(".")
                for part in parts[:-1]:
                    cursor = cursor[int(part)] if part.isdigit() else cursor[part]
                cursor[parts[-1]] = value
            with self.assertRaisesRegex(m.ContractError, reason):
                m.preflight(self.root, self.save_contract(candidate, f"type-{index}.json"))
        for name, raw, reason in (
            ("infinite", '{"version":1e999,"inputs":[],"requirements":[],"artifacts":[]}', "contract_invalid_json"),
            ("surrogate", '{"version":1,"inputs":[],"requirements":[],"artifacts":[],"x":"\\ud800"}', "json_invalid_unicode"),
            ("deep", "[" * 100 + "]" * 100, "json_nesting_limit"),
        ):
            with self.assertRaisesRegex(m.ContractError, reason):
                m.preflight(self.root, self.write(f"{name}.json", raw))

    def test_whitespace_and_strict_csv_are_rejected_and_json_boolean_is_not_integer(self):
        self.write("source.md", "   \n\t")
        report = m.preflight(self.root, self.save_contract(self.contract()))
        self.assertEqual(report["inputs"][0]["reason"], "text_blank")
        self.write("source.csv", 'a,b\n1\n')
        self.write("out/result.json", '{"ok":true}')
        csv_contract = self.contract(
            inputs=[{"id": "source", "path": "source.csv", "format": "csv", "checks": [{"type": "csv_row_count", "expected": 1}]}],
            artifacts=[{"id": "data", "path": "out/result.json", "role": "deliverable", "format": "json", "checks": [{"type": "json_equals", "expected": {"ok": 1}}]}],
        )
        report = m.check(self.root, self.save_contract(csv_contract, "strict-csv.json"))
        self.assertEqual(report["inputs"][0]["reason"], "csv_limits_or_header")
        self.assertEqual(report["artifacts"][0]["reason"], "check_failed_json_equals")
        self.write("source.csv", 'a,b\n"unterminated,2\n')
        malformed = m.preflight(self.root, self.save_contract(csv_contract, "malformed-csv.json"))
        self.assertEqual(malformed["inputs"][0]["reason"], "csv_invalid")

    def test_root_ancestor_link_is_rejected(self):
        linked = self.root.parent / (self.root.name + "-root-link")
        os.symlink(self.root, linked)
        self.addCleanup(linked.unlink)
        self.write("source.md", "week")
        with self.assertRaisesRegex(m.ContractError, "root_ancestor_symlink_rejected"):
            m.preflight(linked, self.save_contract(self.contract()))

    def test_file_count_and_total_read_budgets_are_bounded(self):
        inputs = [{"id": f"input{index}", "path": f"inputs/{index}.txt", "format": "text",
                   "checks": [{"type": "contains", "expected": "x"}]} for index in range(64)]
        contract = self.contract(inputs=inputs)
        with self.assertRaisesRegex(m.ContractError, "file_entries_limit"):
            m.preflight(self.root, self.save_contract(contract, "too-many-files.json"))
        budget = m._ReadBudget()
        budget.claim(m.MAX_TOTAL_READ_BYTES)
        with self.assertRaisesRegex(m.ContractError, "total_read_limit"):
            budget.claim(1)

    def test_cli_returns_json_without_traceback(self):
        self.write("source.md", "week")
        self.write("contract.json", "not json")
        from io import StringIO
        from contextlib import redirect_stdout
        output = StringIO()
        with redirect_stdout(output):
            code = m.main(["preflight", "--root", str(self.root), "--contract", str(self.root / "contract.json")])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["reason"], "contract_invalid_json")

    def test_fenced_or_indented_code_headings_do_not_satisfy_structure(self):
        self.write("source.md", "week")
        self.write("out/check.json", '{"ok":true}')
        contract = self.save_contract(self.contract())
        for body in ("```markdown\n# Weekly\n## Summary\n```\n",
                     "   ~~~~md\n# Weekly\n## Summary\n   ~~~~~\n",
                     "````\n```\n# Weekly\n## Summary\n````\n",
                     "    # Weekly\n    ## Summary\n"):
            with self.subTest(body=body):
                self.write("out/weekly.md", body)
                report = m.check(self.root, contract)
                self.assertFalse(report["ok"])
                self.assertEqual(report["artifacts"][0]["reason"], "check_failed_markdown_headings")
        self.write("out/weekly.md", "# Weekly\n```md\n## Example\n```\n## Summary\n")
        self.assertTrue(m.check(self.root, contract)["ok"])

    def test_case_aliases_cannot_share_deliverable_report_input_or_contract(self):
        self.write("source.md", "week")
        if not (self.root / "SOURCE.md").exists():
            self.skipTest("Filesystem is case-sensitive")
        self.write("out/Result.md", "week")
        row = {"id": "data", "path": "out/Result.md", "role": "deliverable", "format": "text",
               "checks": [{"type": "contains", "expected": "week"}]}
        report = dict(row, id="report", path="out/result.md", role="report")
        contract = self.save_contract(self.contract(artifacts=[row, report]))
        with self.assertRaisesRegex(m.ContractError, "file_identity_reused"):
            m.check(self.root, contract)
        for path in ("SOURCE.md", "CONTRACT.json"):
            row["path"] = path
            contract = self.save_contract(self.contract(artifacts=[row]))
            with self.assertRaisesRegex(m.ContractError, "file_identity_reused"):
                m.preflight(self.root, contract)

    def test_whitespace_is_not_requirement_evidence(self):
        self.write("source.md", "week")
        contract = self.contract()
        contract["requirements"][0]["evidence"] = " \t\n"
        with self.assertRaisesRegex(m.ContractError, "requirement_0_evidence"):
            m.preflight(self.root, self.save_contract(contract))


if __name__ == "__main__":
    unittest.main()
