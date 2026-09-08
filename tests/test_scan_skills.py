import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "skills/skillnav/scripts/scan_skills.py"
spec = importlib.util.spec_from_file_location("scan_skills", SCRIPT)
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skillnav-scan-")
        self.root = Path(self.temp.name).resolve()
        self.skills = self.root / "skills"
        self.skills.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def skill(self, name="alpha", header=None, root=None, body="Never execute this body."):
        directory = (root or self.skills) / name
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "SKILL.md"
        path.write_text("---\n" + (header or f"name: {name}\ndescription: useful test") + "\n---\n" + body, encoding="utf-8")
        return path

    def run_scan(self, roots=None, **kwargs):
        roots = roots or [self.skills]
        return scan.finalize(scan.scan([{"path": str(p), "source": f"source-{i}", "scope": "test"}
                                         for i, p in enumerate(roots)], **kwargs))

    def codes(self, report):
        return [i["code"] for i in report["issues"]]

    def test_normal_file_states_remain_separate(self):
        path = self.skill()
        r = self.run_scan()
        s = r["skills"][0]
        self.assertEqual(s["path"], str(path))
        self.assertEqual(s["read_status"], "readable")
        self.assertEqual(s["disk_status"], "present")
        self.assertEqual((s["enabled"], s["host_visible"], s["dependencies"]), ("unknown", "unknown", "not_checked"))

    def test_multiline_quoted_chinese_metadata(self):
        self.skill("alpha", 'name: "alpha"\ndescription: >-\n  整理中文\n  和 "quoted" 信息: safely')
        self.assertEqual(self.run_scan()["skills"][0]["description"], '整理中文 和 "quoted" 信息: safely')

    def test_empty_and_missing_roots(self):
        r = self.run_scan([self.skills, self.root / "missing"])
        self.assertEqual(r["skills"], [])
        self.assertIn("missing", self.codes(r))

    def test_malformed_metadata_does_not_interrupt_valid_skill(self):
        self.skill("alpha", "name: [broken\ndescription: nope")
        self.skill("beta")
        r = self.run_scan()
        self.assertEqual(r["counts"]["readable_files"], 1)
        self.assertIn("invalid_yaml", self.codes(r))

    def test_missing_metadata_and_empty_description(self):
        self.skill("alpha", "description: no name")
        self.skill("beta", 'name: beta\ndescription: ""')
        self.assertEqual(set(self.codes(self.run_scan())), {"invalid_name", "invalid_description"})

    def test_same_name_different_sources_are_preserved(self):
        self.skill()
        other = self.root / "other"
        self.skill(root=other)
        r = self.run_scan([self.skills, other])
        self.assertEqual(len(r["skills"]), 2)
        self.assertNotEqual(r["skills"][0]["source"], r["skills"][1]["source"])

    def test_spaces_and_chinese_path(self):
        p = self.root / "中文 技能"
        self.skill(root=p)
        self.assertEqual(self.run_scan([p])["counts"]["readable_files"], 1)

    def test_permission_failure_isolated(self):
        denied = self.skill()
        self.skill("beta")
        original = scan.read_header
        def read(path):
            if path == denied:
                raise PermissionError()
            return original(path)
        with patch.object(scan, "read_header", side_effect=read):
            r = self.run_scan()
        self.assertIn("permission_denied", self.codes(r))
        self.assertEqual(r["counts"]["readable_files"], 1)

    def test_directory_permission_failure(self):
        with patch.object(Path, "iterdir", side_effect=PermissionError()):
            r = self.run_scan()
        self.assertEqual(r["roots"][0]["status"], "permission_denied")

    def test_symlink_directory_loop_and_dangling_link(self):
        (self.skills / "loop").symlink_to(self.skills, target_is_directory=True)
        (self.skills / "dangling").symlink_to(self.root / "missing")
        self.skill()
        r = self.run_scan()
        self.assertIn("symlink_loop", self.codes(r))
        self.assertIn("missing", self.codes(r))
        self.assertEqual(r["counts"]["readable_files"], 1)

    def test_self_symlink_detected(self):
        p = self.skills / "loop"
        p.symlink_to(p)
        self.assertIn("symlink_loop", self.codes(self.run_scan()))

    def test_outside_target_not_read_until_declared(self):
        outside = self.root / "outside"
        self.skill(root=outside)
        (self.skills / "link").symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.run_scan()["skills"], [])
        self.assertIn("outside_allowed_roots", self.codes(self.run_scan()))
        self.assertEqual(self.run_scan([self.skills, outside])["counts"]["readable_files"], 1)

    def test_root_symlink_requires_target_declaration(self):
        self.skill()
        link = self.root / "linked-root"
        link.symlink_to(self.skills, target_is_directory=True)
        self.assertIn("outside_allowed_roots", self.codes(self.run_scan([link])))
        self.assertEqual(self.run_scan([link, self.skills])["counts"]["readable_files"], 1)

    def test_same_real_file_dedup_retains_origins(self):
        p = self.skill()
        other = self.skills / "alias"
        other.mkdir()
        (other / "SKILL.md").symlink_to(p)
        r = self.run_scan()
        self.assertEqual(len(r["skills"]), 1)
        self.assertEqual(len(r["skills"][0]["origins"]), 2)

    def test_do_not_read_env_even_through_skill_link(self):
        p = self.skills / ".env"
        p.write_text("---\nname: secret\ndescription: confidential\n---")
        d = self.skills / "evil"
        d.mkdir()
        (d / "SKILL.md").symlink_to(p)
        r = self.run_scan()
        self.assertIn("non_skill_symlink_target", self.codes(r))
        self.assertNotIn("confidential", json.dumps(r))

    def test_no_body_read_or_leak(self):
        p = self.skill(body="")
        with p.open("ab") as f:
            f.write(b"\xff" * 1000000)
        r = self.run_scan()
        self.assertEqual(r["counts"]["readable_files"], 1)
        self.assertNotIn("body", r["skills"][0])

    def test_unsafe_yaml_alias_and_duplicate_keys(self):
        self.skill("alpha", 'name: alpha\ndescription: !!python/object/apply:os.system ["echo bad"]')
        self.skill("beta", "name: beta\ndescription: &a safe\nextra: *a")
        self.skill("gamma", "name: gamma\nname: overwritten\ndescription: safe")
        codes = self.codes(self.run_scan())
        self.assertIn("invalid_yaml", codes)
        self.assertIn("yaml_alias_not_supported", codes)
        self.assertIn("invalid_or_duplicate_yaml_key", codes)

    def test_oversized_or_unclosed_header(self):
        self.skill("alpha", "name: alpha\ndescription: " + "x" * 40000)
        p = self.skill("beta")
        p.write_text("---\nname: beta\ndescription: never closed")
        codes = self.codes(self.run_scan())
        self.assertIn("frontmatter_too_large", codes)
        self.assertIn("unclosed_frontmatter", codes)

    def test_special_file_does_not_block(self):
        import os
        d = self.skills / "pipe"
        d.mkdir()
        os.mkfifo(d / "SKILL.md")
        self.assertIn("not_regular_file", self.codes(self.run_scan()))

    def test_stable_results_and_explicit_pagination(self):
        self.skill("alpha")
        self.skill("beta")
        self.assertEqual(self.run_scan(), self.run_scan())
        r = scan.finalize(self.run_scan(), "useful", 0, 1)
        self.assertEqual(r["counts"]["unique_records"], 2)
        self.assertEqual(r["selection"]["matching_records"], 2)
        self.assertEqual(r["selection"]["next_offset"], 1)

    def test_scan_budget_disclosed(self):
        self.skill()
        self.assertIn("scan_limit", self.codes(self.run_scan(max_dirs=1)))

    def test_host_metadata_merge_disable_conflict(self):
        path = self.skill()
        catalog = self.root / "host.json"
        items = [{"name": "alpha", "description": "host", "locator": str(path), "source": "host", "scope": "session", "enabled": v}
                 for v in ("enabled", "disabled", "enabled")]
        items.append({"name": "remote", "description": "host only", "locator": "host://remote", "source": "plugin", "scope": "session"})
        catalog.write_text(json.dumps(items))
        r = self.run_scan()
        scan.merge_host_catalog(r, catalog)
        r = scan.finalize(r)
        self.assertEqual(r["skills"][0]["enabled"], "disabled")
        self.assertEqual(r["skills"][1]["read_status"], "host_metadata_only")
        self.assertIn("host_enablement_conflict", self.codes(r))

    def test_host_bad_entry_does_not_discard_valid(self):
        catalog = self.root / "host.json"
        catalog.write_text(json.dumps([{}, {"name":"ok", "description":"metadata", "locator":"host://ok", "source":"host", "scope":"session"}]))
        r = self.run_scan()
        scan.merge_host_catalog(r, catalog)
        self.assertEqual(len(r["skills"]), 1)
        self.assertIn("invalid_host_entry", self.codes(r))

    def test_defaults_stop_at_git_root(self):
        repo = self.root / "repo"
        cwd = repo / "nested" / "sub"
        cwd.mkdir(parents=True)
        result = subprocess.CompletedProcess([], 0, stdout=str(repo) + "\n")
        with patch.object(subprocess, "run", return_value=result):
            roots = scan.default_roots(cwd, self.root / "home", self.root / "admin")
        self.assertEqual([r["scope"] for r in roots[:3]], [str(cwd), str(cwd.parent), str(repo)])
        self.assertEqual(len(roots), 5)

    def test_cli_missing_dependency_and_partial_strict(self):
        p = subprocess.run([sys.executable, "-S", str(SCRIPT), "--root", str(self.skills)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(json.loads(p.stderr)["error"], "missing_pyyaml")
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root / "missing"), "--strict"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(json.loads(p.stdout)["counts"]["readable_files"], 0)


if __name__ == "__main__":
    unittest.main()
