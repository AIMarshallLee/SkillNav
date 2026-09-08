"""Installable artifact contracts, rather than host-behavior claims."""
import hashlib
from pathlib import Path
import re
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/skillnav"


class PackageTests(unittest.TestCase):
    def test_skill_metadata_and_explicit_policy(self):
        text = (SKILL / "SKILL.md").read_text()
        header = text.split("---", 2)[1]
        fields = yaml.safe_load(header)
        self.assertEqual(fields["name"], "skillnav")
        self.assertEqual(fields["metadata"]["version"], "0.1.0")
        self.assertTrue(1 <= len(fields["description"]) <= 1024)
        policy = yaml.safe_load((SKILL / "agents/openai.yaml").read_text())
        self.assertIs(policy["policy"]["allow_implicit_invocation"], False)
        self.assertIn("$skillnav", policy["interface"]["default_prompt"])

    def test_references_and_standalone_license_are_present(self):
        for target in re.findall(r"\]\((references/[^)]+)\)", (SKILL / "SKILL.md").read_text()):
            self.assertTrue((SKILL / target).is_file(), target)
        self.assertEqual((ROOT / "LICENSE").read_bytes(), (SKILL / "LICENSE").read_bytes())
        self.assertEqual(hashlib.sha256((ROOT / "LICENSE").read_bytes()).hexdigest(),
                         "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30")


if __name__ == "__main__":
    unittest.main()
