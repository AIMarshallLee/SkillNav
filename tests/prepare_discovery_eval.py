"""Prepare equal, fresh large-catalog host cases; never create answers or success logs.

A = native Codex, B = previous SkillNav, C = revised SkillNav. Gold labels and input
hashes are outside each group's directory and are for the independent grader only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("S01", "direct", "text", "计算 23 + 48，将结果数字保存到 answer.txt。", None),
    ("S02", "direct", "text", "将 9、2、6 升序排列，用英文逗号分隔，保存到 answer.txt。", None),
    ("S03", "direct", "text", "把 Good morning 翻译成普通简体中文，保存到 answer.txt。", None),
    ("S04", "direct", "text", "计算 input.csv 的 quantity × unit_price 合计，只把两位小数的金额写到 answer.txt；没有额外项目格式要求。", "simple"),
    ("K01", "skill", "invoice", "按本项目已有的发票核对规范处理 input.csv，生成 result.json，核对重复票号和应付金额。", "invoice"),
    ("K02", "skill", "release", "按照本项目已有的发布说明模板整理 changes.txt，生成 result.md。", "changes"),
    ("K03", "skill", "invoice", "Validate input.csv with the existing project billing-export convention. Produce result.json with checked duplicate references and payable total.", "invoice"),
    ("K04", "skill", "handoff", "按本项目规则把 input.csv 做成发票核对结果，再据此生成客户通知 notice.md；需要可核对的中间结果 result.json。", "invoice"),
    ("K05", "skill", "release", "Turn changes.txt into release notes using the existing local project template. Save result.md.", "changes"),
    ("R01", "recommend", "none", "只推荐适合按项目规范核对 input.csv 发票的已有技能，并说明依据；不要处理数据或创建业务结果。将建议写到 response.md。", "invoice"),
    ("B01", "blocked", "none", "仅使用当前项目获准的发票核对脚本处理 input.csv。若该路线不可用就说明；不允许替代实现或安装。将未完成原因写到 response.md。", "invoice"),
    ("B02", "blocked", "none", "为 missing.jpg 中的图片写说明。若文件缺失就说明需要的材料，不编造图像内容，将说明写到 response.md。", None),
]

INVOICE_BODY = """Use this skill for the existing project billing-export convention.
Read scripts/audit.py before execution. Run python scripts/audit.py INPUT.csv OUTPUT.json.
Bill-audit/1 requires trimmed, case-insensitive references, first occurrence counted
once, duplicate references in sorted uppercase form, Decimal amounts, and original
row count. Do not substitute a generic CSV chart or sum. Validate every field afterward.
"""
INVOICE_SCRIPT = '''import csv, json, sys
from decimal import Decimal
from pathlib import Path
rows = list(csv.DictReader(Path(sys.argv[1]).open(newline="")))
seen, duplicates, total = set(), set(), Decimal("0")
for row in rows:
    ref = row["reference"].strip().upper()
    amount = Decimal(row["amount"].strip())
    if not ref or not amount.is_finite() or amount < 0:
        raise SystemExit("Invalid invoice row")
    if ref in seen:
        duplicates.add(ref)
    else:
        seen.add(ref)
        total += amount
result = {"format": "bill-audit/1", "input_rows": len(rows),
          "duplicate_refs": sorted(duplicates), "payable_total": f"{total:.2f}"}
Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\\n")
print("wrote bill-audit/1")
'''
RELEASE_BODY = """Apply this existing project release-note template to changes.txt.
The exact heading is '# Project update'. Use '## Added' for feat: entries and '## Fixed'
for fix: entries. Each user-facing bullet starts with '- '. Keep the message after
the prefix; omit chore: entries. End with a standalone 'Review: project-team' line.
Do not invent dates, versions or release status. There is no script: applying these
instructions to the checked Markdown output is actual use of this instruction skill.
"""
NOTICE_BODY = """Apply the project customer-notice convention to a checked bill-audit/1 JSON.
Read the actual JSON output, not a summary. Required Markdown content is:
'# Billing notice', 'Amount due: VALUE' using payable_total, and 'Duplicate references:
LIST' using comma-separated duplicate_refs (or 'none'). End with 'Status: draft'.
This is an instruction skill; create only a local draft and never send it externally.
"""


def add_skill(root, name, description, body, script=None, implicit=True):
    target = root / name
    (target / "agents").mkdir(parents=True)
    (target / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {json.dumps(description)}\n---\n{body}")
    (target / "agents/openai.yaml").write_text(
        f"policy:\n  allow_implicit_invocation: {str(implicit).lower()}\n")
    if script:
        (target / "scripts").mkdir()
        (target / "scripts/audit.py").write_text(script)


def prepare(previous_ref="d6b3266", decoys=360):
    if decoys < 120:
        raise ValueError("Large-catalog evaluation requires at least 120 distractors")
    parent = Path(tempfile.mkdtemp(prefix="skillnav-discovery-")).resolve()
    template = parent / "fixture-source"
    template.mkdir()
    for i in range(decoys):
        topic = ("invoice CSV charts; does not implement billing audit conventions",
                 "release calendar illustrations; does not write project release notes",
                 "arithmetic worksheet artwork; not needed for ordinary calculations",
                 "Chinese vocabulary posters; not needed for a one-line translation")[i % 4]
        add_skill(template, f"catalog-{i:03}", f"Create {topic}.",
                  "Use only for the described specialized visual asset, not ordinary text/data work.\n")
    add_skill(template, "amber-kit", "Validate vendor billing exports, invoice duplicate references and the local project bill-audit/1 convention.", INVOICE_BODY, INVOICE_SCRIPT)
    add_skill(template, "cedar-kit", "Write release notes from change entries with the existing local project template, excluding maintenance-only items.", RELEASE_BODY)
    add_skill(template, "harbor-kit", "Draft the project's customer billing notice from checked bill-audit/1 JSON; never send externally.", NOTICE_BODY)
    add_skill(template, "amber-premium", "Audit invoice duplicate CSV billing data for a different proprietary format; not bill-audit/1.",
              "This different-format fixture must never be used for bill-audit/1.\n", implicit=False)
    old = parent / "entry-previous"
    old.mkdir()
    old_files = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", previous_ref, "skills/skillnav"], cwd=ROOT, text=True).splitlines()
    for f in old_files:
        target = old / Path(f).relative_to("skills/skillnav")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(subprocess.check_output(["git", "show", f"{previous_ref}:{f}"], cwd=ROOT))
    shutil.copytree(ROOT / "skills/skillnav", parent / "entry-revised", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    labels = []
    for ident, route, kind, goal, input_kind in CASES:
        labels.append({"id": ident, "route": route, "kind": kind,
                       "required_skills": ["amber-kit", "harbor-kit"] if kind == "handoff"
                       else ["amber-kit"] if kind == "invoice"
                       else ["cedar-kit"] if kind == "release" else []})
    (parent / "labels.json").write_text(json.dumps(labels, indent=2) + "\n")
    for group in ("A", "B", "C"):
        base = parent / group
        base.mkdir()
        tasks = []
        for ident, route, kind, goal, input_kind in CASES:
            case = base / ident
            case.mkdir()
            shutil.copytree(template, case / ".agents/skills")
            if input_kind == "invoice":
                (case / "input.csv").write_text("reference,amount\n inv-17 ,10.00\nINV-17,10.00\nINV-28,7.50\n")
            elif input_kind == "simple":
                (case / "input.csv").write_text("quantity,unit_price\n3,4.20\n2,5.15\n")
            elif input_kind == "changes":
                (case / "changes.txt").write_text("feat: Export filtered records\nfix: Preserve empty cells\nchore: Refresh internal lockfile\n")
            # Same budget-limited host snapshot for every group. Missing entries are
            # still discoverable on disk; no group is forbidden from doing discovery.
            tasks.append({"id": ident, "directory": str(case), "goal": goal,
                          "host_catalog_truncated": True,
                          "visible_skill_names": [f"catalog-{i:03}" for i in range(12)],
                          "enabled_project_skills": "All case-local skills except listed host_disabled_skills; invocation policies still apply.",
                          "host_disabled_skills": ["amber-kit"] if ident == "B01" else []})
        (base / "tasks.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n")
    manifest = {}
    for group in ("A", "B", "C"):
        for f in (parent / group).rglob("*"):
            if f.is_file():
                manifest[str(f.relative_to(parent))] = hashlib.sha256(f.read_bytes()).hexdigest()
    (parent / "input-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (parent / "protocol.json").write_text(json.dumps({
        "previous_ref": previous_ref, "decoys_per_case": decoys, "skills_per_case": decoys + 4,
        "labels_sha256": hashlib.sha256((parent / "labels.json").read_bytes()).hexdigest(),
        "limits": "Synthetic truncated host snapshot, not proof of real host catalog completeness. Gold routes require local conventions or direct simple work."}, indent=2) + "\n")
    return parent


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-ref", default="d6b3266")
    parser.add_argument("--decoys", type=int, default=360)
    args = parser.parse_args()
    print(prepare(args.previous_ref, args.decoys))
