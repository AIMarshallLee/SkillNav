"""Independently grade actual artifacts; manifest claims alone cannot pass delivery."""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

LABELS = Path(__file__).with_name("routing_cases.json")


def verify(parent, group):
    parent = Path(parent).resolve()
    root = parent / group
    manifest = json.loads((root / "results.json").read_text())
    if not isinstance(manifest, list):
        raise ValueError("Results must be an array")
    results = {r["id"]: r for r in manifest}
    if len(results) != len(manifest):
        raise ValueError("Duplicate task IDs")
    labels = json.loads(LABELS.read_text())
    original = json.loads((parent / "input-manifest.json").read_text())
    altered = [p for p, digest in original.items() if p.startswith(group + "/") and
               (not (parent / p).is_file() or hashlib.sha256((parent / p).read_bytes()).hexdigest() != digest)]
    graded = []
    for index, label in enumerate(labels, 1):
        task_id = label["id"]
        task = results.get(task_id)
        errors = []
        case = root / task_id
        if not task:
            graded.append({"id": task_id, "passed": False, "errors": ["missing_result"]})
            continue
        paths = []
        for value in task.get("artifacts", []):
            p = (case / value).resolve()
            if not p.is_relative_to(case) or not p.is_file() or ".agents" in p.relative_to(case).parts:
                errors.append("invalid_artifact")
            else:
                paths.append(p)
        if any(p.startswith(group + "/" + task_id + "/") for p in altered):
            errors.append("input_or_skill_modified")
        kind, fmt = label["kind"], label["expected_format"]
        if fmt is not None and task.get("status") != "completed":
            errors.append("delivery_not_completed")
        if kind == "simple":
            expected = {1: "71", 2: "早上好", 3: "2,6,9", 4: "120"}[index]
            p = case / "answer.txt"
            actual = p.read_text().strip().replace(" ", "").replace("，", ",") if p.exists() else ""
            if actual != expected:
                errors.append("simple_answer_mismatch")
        elif fmt is not None:
            extension = {"markdown": ".md", "html": ".html", "json": ".json"}[fmt]
            reports = [p for p in paths if p.suffix == extension]
            if not reports:
                errors.append("expected_report_format_missing")
            else:
                total = Decimal(((index % 5) + 1)) * Decimal("2.35") + Decimal("12.30")
                content = reports[-1].read_text()
                if f"{total:.2f}" not in content:
                    errors.append("grand_total_missing_or_wrong")
                for suffix in ("A", "B"):
                    if f"Sample {index} {suffix}" not in content:
                        errors.append("item_missing")
                for number in (f"{Decimal(((index % 5) + 1))*Decimal('2.35'):.2f}", "12.30"):
                    if number not in content:
                        errors.append("line_total_missing_or_wrong")
                if fmt == "json":
                    try:
                        data = json.loads(content)
                        rows = data.get("rows", data.get("items", []))
                        if len(rows) != 2:
                            errors.append("json_item_count")
                    except (ValueError, AttributeError):
                        errors.append("invalid_json")
                if fmt == "html" and not re.search(r"<(?:html|table|h1)\b", content, re.I):
                    errors.append("not_readable_html")
        else:
            if not (case / "response.md").is_file():
                errors.append("missing_boundary_response")
            if task.get("status") not in ("blocked", "recommended"):
                errors.append("boundary_claimed_completed")
            if any(p.name != "response.md" for p in paths):
                errors.append("unexpected_business_artifact")
        if kind in ("disabled", "explicit_only") and "ledger-report" in task.get("skills_used", []):
            errors.append("reported_restricted_skill_use")
        if task.get("manual_handoffs") != 0:
            errors.append("manual_handoff_or_unknown")
        graded.append({"id": task_id, "split": label["split"], "kind": kind,
                       "passed": not errors, "errors": errors,
                       "status": task.get("status"), "artifacts": task.get("artifacts", []),
                       "manual_handoffs_reported": task.get("manual_handoffs")})
    return {"group": group, "total": len(graded), "passed": sum(r["passed"] for r in graded),
            "delivery_tasks": sum(l["expected_format"] is not None for l in labels),
            "boundary_tasks": sum(l["expected_format"] is None for l in labels),
            "altered_inputs_or_skills": len(altered), "results": graded,
            "limits": "Artifact checks are independent; routing/process counts are host-reported and require receipt review. Single run is not a stable accuracy or improvement estimate."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace")
    parser.add_argument("group", choices=["A", "B", "C"])
    args = parser.parse_args()
    result = verify(args.workspace, args.group)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] == result["total"] else 1)
