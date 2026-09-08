"""Create NEW isolated fixtures for real host evaluation; never fake execution logs."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import tempfile

FIXTURES = Path(__file__).resolve().parent / "fixtures/skills"


def prepare(scenario="handoff"):
    root = Path(tempfile.mkdtemp(prefix=f"skillnav-{scenario}-")).resolve()
    shutil.copytree(FIXTURES, root / ".agents/skills")
    for d in (root / ".agents/skills").iterdir():
        (d / "agents").mkdir(exist_ok=True)
        (d / "agents/openai.yaml").write_text("policy:\n  allow_implicit_invocation: true\n")
    with (root / "input.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["item", "quantity", "unit_price"])
        writer.writerows([["  Lake labels  ", 9, " 1.35 "], ["Dune folders", 3, "7.40"], ["Map cards", 5, "2.15"]])
    if scenario == "recovery":
        p = root / ".agents/skills/ledger-report/scripts/report.py"
        p.write_text(p.read_text().replace("total += expected", "total += Decimal(0)"))
    if scenario == "restricted":
        (root / ".agents/skills/ledger-report/agents/openai.yaml").write_text("policy:\n  allow_implicit_invocation: false\n")
    return root


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", choices=["handoff", "recovery", "restricted", "personalization"], default="handoff")
    args = p.parse_args()
    print(json.dumps({"workspace": str(prepare(args.scenario))}))
