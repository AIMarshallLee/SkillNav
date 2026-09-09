import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr


SCRIPT = Path(__file__).resolve().parents[1] / "skills/skillnav/scripts/create_skill.py"
spec = importlib.util.spec_from_file_location("create_skill", SCRIPT)
creator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(creator)


class CreateSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skillnav-create-")
        # The implementation checks every lexical ancestor; use the real
        # temporary path because macOS may expose /var through a system alias.
        self.root = Path(self.temp.name).resolve()
        self.output = self.root / "skills"
        self.output.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write_spec(self, **overrides):
        data = {
            "name": "weekly-report",
            "description": '生成中文周报并保留 "引号"。',
            "instructions": "第一步：读取输入。\n第二步：核对结果。",
        }
        data.update(overrides)
        path = self.root / "spec.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def test_creation_preserves_instructions_and_quoted_chinese_metadata(self):
        instructions = "保留原文：中文、\"双引号\"、反斜杠 \\。\n请逐项核对。"
        result = creator.create_skill(self.write_spec(instructions=instructions), self.output)
        skill = self.output / "weekly-report"
        self.assertTrue(result["valid"])
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n" + instructions))
        self.assertIn('description: "生成中文周报并保留 \\"引号\\"。"', text)
        self.assertEqual(creator.validate_skill(skill)["allow_implicit_invocation"], True)

    def test_explicit_only_policy_is_preserved(self):
        skill = self.output / "explicit"
        data = self.write_spec(name="explicit", allow_implicit_invocation=False)
        creator.create_skill(data, self.output)
        self.assertFalse(creator.validate_skill(skill)["allow_implicit_invocation"])
        self.assertIn("false", (skill / "agents/openai.yaml").read_text())

    def test_existing_destination_is_refused_without_changes(self):
        destination = self.output / "weekly-report"
        destination.mkdir()
        marker = destination / "marker"
        marker.write_text("keep")
        with self.assertRaises(creator.SkillError) as error:
            creator.create_skill(self.write_spec(), self.output)
        self.assertEqual(str(error.exception), "destination_exists")
        self.assertEqual(marker.read_text(), "keep")

    def test_traversal_and_symlink_paths_are_rejected(self):
        with self.assertRaises(creator.SkillError):
            creator.create_skill(self.write_spec(name="../escape"), self.output)
        outside = self.root / "outside"
        outside.mkdir()
        link = self.root / "linked-output"
        link.symlink_to(self.output, target_is_directory=True)
        with self.assertRaises(creator.SkillError) as error:
            creator.create_skill(self.write_spec(), link)
        self.assertEqual(str(error.exception), "output_root_symlink")
        self.assertFalse((outside / "weekly-report").exists())

    def test_bad_spec_and_obvious_placeholders_are_rejected(self):
        for field in ("description", "instructions"):
            for placeholder in ("TODO", "FIXME", "TBD"):
                with self.subTest(field=field, placeholder=placeholder), self.assertRaises(creator.SkillError):
                    creator.create_skill(self.write_spec(**{field: placeholder}), self.output)
                self.assertEqual(list(self.output.iterdir()), [])
        bad = self.root / "bad.json"
        bad.write_text('{"name":"x","description":"ok","instructions":"TODO: fill"}')
        with self.assertRaises(creator.SkillError) as error:
            creator.create_skill(bad, self.output)
        self.assertEqual(str(error.exception), "unfilled_placeholder")
        unknown = self.write_spec(extra="no")
        with self.assertRaises(creator.SkillError):
            creator.create_skill(unknown, self.output)
        accepted = self.write_spec(instructions="Find TODO comments and collect FIXME markers.")
        creator.create_skill(accepted, self.output)

    def test_hardlinked_inputs_and_windows_absolute_links_are_rejected(self):
        source = self.write_spec()
        hardlink = self.root / "spec-hardlink.json"
        hardlink.hardlink_to(source)
        with self.assertRaises(creator.SkillError) as error:
            creator.create_skill(hardlink, self.output)
        self.assertEqual(str(error.exception), "spec_hardlink")
        hardlink.unlink()
        skill = self.output / "linked"
        (skill / "agents").mkdir(parents=True)
        (skill / "agents/openai.yaml").write_text(
            'interface:\n  display_name: "linked"\n  short_description: "A sufficiently long summary"\n  default_prompt: "Use $linked safely."\npolicy:\n  allow_implicit_invocation: true\n')
        (skill / "SKILL.md").write_text(
            '---\nname: "linked"\ndescription: "A skill"\n---\nSee [drive](C:/outside.md)', encoding="utf-8")
        with self.assertRaises(creator.SkillError) as error:
            creator.validate_skill(skill)
        self.assertEqual(str(error.exception), "markdown_link_absolute")

        creator.create_skill(self.write_spec(name="hardlinked"), self.output)
        hard_skill = self.output / "hardlinked"
        external = self.root / "external.md"
        external.write_text("external", encoding="utf-8")
        original_md = hard_skill / "SKILL.md"
        original_md.unlink()
        original_md.hardlink_to(external)
        with self.assertRaises(creator.SkillError) as error:
            creator.validate_skill(hard_skill)
        self.assertEqual(str(error.exception), "skill_markdown_hardlink")
        creator.create_skill(self.write_spec(name="hard-openai"), self.output)
        hard_openai = self.output / "hard-openai/agents/openai.yaml"
        external_yaml = self.root / "external.yaml"
        external_yaml.write_text(hard_openai.read_text(), encoding="utf-8")
        hard_openai.unlink()
        hard_openai.hardlink_to(external_yaml)
        with self.assertRaises(creator.SkillError) as error:
            creator.validate_skill(self.output / "hard-openai")
        self.assertEqual(str(error.exception), "openai_yaml_hardlink")

    def test_skill_body_and_name_limits_are_enforced(self):
        oversized = self.write_spec(name="a" * 65)
        with self.assertRaises(creator.SkillError) as error:
            creator.create_skill(oversized, self.output)
        self.assertEqual(str(error.exception), "invalid_name")
        skill = self.output / "large-body"
        (skill / "agents").mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            '---\nname: "large-body"\ndescription: "A skill"\n---\n' + "x" * (creator.MAX_INSTRUCTIONS_BYTES + 1), encoding="utf-8")
        (skill / "agents/openai.yaml").write_text(
            'interface:\n  display_name: "large-body"\n  short_description: "A sufficiently long summary"\n  default_prompt: "Use $large-body safely."\npolicy:\n  allow_implicit_invocation: true\n')
        with self.assertRaises(creator.SkillError) as error:
            creator.validate_skill(skill)
        self.assertEqual(str(error.exception), "instructions_too_large")

    def test_name_and_generated_summary_boundaries_are_checked(self):
        with self.assertRaises(creator.SkillError):
            creator.create_skill(self.write_spec(name="double--dash"), self.output)
        creator.create_skill(self.write_spec(description="short"), self.output)
        yaml_text = (self.output / "weekly-report/agents/openai.yaml").read_text()
        summary = yaml_text.split("short_description: ", 1)[1].splitlines()[0]
        self.assertGreaterEqual(len(json.loads(summary)), 25)
        self.assertLessEqual(len(json.loads(summary)), 64)

    def test_empty_body_and_invalid_utf8_are_rejected(self):
        skill = self.output / "empty"
        (skill / "agents").mkdir(parents=True)
        (skill / "SKILL.md").write_text('---\nname: "empty"\ndescription: "An empty skill"\n---\n')
        (skill / "agents/openai.yaml").write_text(
            'interface:\n  display_name: "empty"\n  short_description: "A sufficiently long summary"\n  default_prompt: "Use $empty safely."\npolicy:\n  allow_implicit_invocation: true\n')
        with self.assertRaises(creator.SkillError) as error:
            creator.validate_skill(skill)
        self.assertEqual(str(error.exception), "empty_instructions")
        (skill / "SKILL.md").write_text('---\nname: "empty"\ndescription: "An empty skill"\n---\ncontains\x00nul')
        with self.assertRaises(creator.SkillError) as error:
            creator.validate_skill(skill)
        self.assertEqual(str(error.exception), "instructions_control_character")
        invalid = self.root / "invalid.json"
        invalid.write_bytes(b"{\xff")
        with self.assertRaises(creator.SkillError) as error:
            creator.create_skill(invalid, self.output)
        self.assertEqual(str(error.exception), "spec_invalid_utf8")

    def test_json_controls_surrogates_and_duplicate_keys_return_clean_errors(self):
        for index, raw, expected in (
            ("nul", '{"name":"nul","description":"ok","instructions":"bad\\u0000text"}', "instructions_control_character"),
            ("surrogate", '{"name":"surrogate","description":"ok","instructions":"\\ud800"}', "instructions_invalid_utf8"),
            ("duplicate", '{"name":"one","name":"two","description":"ok","instructions":"do it"}', "duplicate_spec_key"),
        ):
            path = self.root / f"{index}.json"
            path.write_text(raw, encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                status = creator.main(["create", "--spec", str(path), "--output-root", str(self.output)])
            self.assertEqual(status, 2)
            self.assertIn(expected, stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())
        self.assertEqual(list(self.output.iterdir()), [])

    def test_missing_and_escaping_markdown_links_are_caught(self):
        skill = self.output / "linked"
        skill.mkdir()
        (skill / "agents").mkdir()
        (skill / "SKILL.md").write_text(
            '---\nname: "linked"\ndescription: "A skill"\n---\nSee [missing](references/nope.md)',
            encoding="utf-8")
        (skill / "agents/openai.yaml").write_text(
            "interface: {}\npolicy:\n  allow_implicit_invocation: true\n", encoding="utf-8")
        with self.assertRaises(creator.SkillError) as error:
            creator.validate_skill(skill)
        self.assertEqual(str(error.exception), "markdown_link_missing")
        (skill / "references").mkdir()
        (skill / "references/nope.md").write_text("ok")
        (skill / "SKILL.md").write_text(
            '---\nname: "linked"\ndescription: "A skill"\n---\nSee [escape](../../outside.md)',
            encoding="utf-8")
        with self.assertRaises(creator.SkillError) as error:
            creator.validate_skill(skill)
        self.assertEqual(str(error.exception), "markdown_link_escapes_skill")

    def test_absolute_and_in_root_symlink_links_are_rejected(self):
        skill = self.output / "linked"
        (skill / "agents").mkdir(parents=True)
        (skill / "agents/openai.yaml").write_text(
            'interface:\n  display_name: "linked"\n  short_description: "A sufficiently long summary"\n  default_prompt: "Use $linked safely."\npolicy:\n  allow_implicit_invocation: true\n')
        (skill / "SKILL.md").write_text(
            '---\nname: "linked"\ndescription: "A skill"\n---\nSee [absolute](/tmp/x.md)', encoding="utf-8")
        with self.assertRaises(creator.SkillError) as error:
            creator.validate_skill(skill)
        self.assertEqual(str(error.exception), "markdown_link_absolute")
        (skill / "references").mkdir()
        (skill / "SKILL.md").write_text(
            '---\nname: "linked"\ndescription: "A skill"\n---\nSee [local](references/alias.md)', encoding="utf-8")
        (skill / "references/alias.md").symlink_to(skill / "references/nope.md")
        with self.assertRaises(creator.SkillError) as error:
            creator.validate_skill(skill)
        self.assertEqual(str(error.exception), "markdown_link_symlink")

    def test_angle_bracket_link_with_spaces_is_checked(self):
        skill = self.output / "linked"
        (skill / "agents").mkdir(parents=True)
        (skill / "references").mkdir()
        (skill / "agents/openai.yaml").write_text(
            'interface:\n  display_name: "linked"\n  short_description: "A sufficiently long summary"\n  default_prompt: "Use $linked safely."\npolicy:\n  allow_implicit_invocation: true\n')
        (skill / "SKILL.md").write_text(
            '---\nname: "linked"\ndescription: "A skill"\n---\nSee [guide](<references/a guide.md>)', encoding="utf-8")
        guide = skill / "references/a guide.md"
        guide.write_text("guide", encoding="utf-8")
        self.assertTrue(creator.validate_skill(skill)["valid"])
        external = self.root / "guide-external.md"
        external.write_text("guide", encoding="utf-8")
        guide.unlink()
        guide.hardlink_to(external)
        with self.assertRaises(creator.SkillError) as error:
            creator.validate_skill(skill)
        self.assertEqual(str(error.exception), "markdown_link_hardlink")

    def test_failed_creation_leaves_no_partial_destination(self):
        # A generated skill containing a missing local link fails validation
        # after exclusive destination reservation and is cleaned up.
        spec_path = self.write_spec(instructions="Read [missing](guide.md).")
        with self.assertRaises(creator.SkillError) as error:
            creator.create_skill(spec_path, self.output)
        self.assertEqual(str(error.exception), "markdown_link_missing")
        self.assertFalse((self.output / "weekly-report").exists())
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
