"""Grade actual artifacts separately from host-declared skill decisions and use.

Invocation truth also requires reading the original host tool receipts. A generated
results.json is not an independent audit of its author's claimed process.
"""
import argparse
import hashlib
import json
from pathlib import Path


def verify(parent, group):
    parent = Path(parent).resolve()
    root = parent / group
    labels = json.loads((parent / "labels.json").read_text())
    protocol = json.loads((parent / "protocol.json").read_text())
    if hashlib.sha256((parent / "labels.json").read_bytes()).hexdigest() != protocol["labels_sha256"]:
        raise ValueError("Gold labels changed after preparation")
    manifest = json.loads((root / "results.json").read_text())
    if not isinstance(manifest, list) or any(not isinstance(r, dict) for r in manifest):
        raise ValueError("Results must be an array of records")
    for row in manifest:
        if not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError("Each result requires a nonempty string id")
        for field in ("artifacts", "skills_loaded"):
            if not isinstance(row.get(field), list) or any(not isinstance(x, str) for x in row[field]):
                raise ValueError(f"{row['id']}: {field} must be an array of strings")
        if not isinstance(row.get("skills_applied"), list) or any(
                not isinstance(x, dict) or not isinstance(x.get("name"), str)
                for x in row["skills_applied"]):
            raise ValueError(f"{row['id']}: skills_applied requires records with string names")
    results = {r["id"]: r for r in manifest}
    if len(results) != len(manifest) or set(results) != {r["id"] for r in labels}:
        raise ValueError("Missing, extra or duplicate task IDs")
    originals = json.loads((parent / "input-manifest.json").read_text())
    altered = [name for name, digest in originals.items() if name.startswith(group + "/")
               and (not (parent / name).is_file()
                    or hashlib.sha256((parent / name).read_bytes()).hexdigest() != digest)]
    graded = []
    for label in labels:
        ident, kind = label["id"], label["kind"]
        case, result = root / ident, results[ident]
        artifact_errors, decision_errors = [], []
        paths = []
        for name in result.get("artifacts", []):
            path = (case / name).resolve()
            if not path.is_relative_to(case) or not path.is_file() or ".agents" in path.relative_to(case).parts:
                artifact_errors.append("invalid_artifact_path")
            else:
                paths.append(path)
        if any(name.startswith(group + "/" + ident + "/") for name in altered):
            artifact_errors.append("input_or_skill_changed")

        def read(name):
            path = case / name
            if path not in paths:
                artifact_errors.append("missing_expected_artifact:" + name)
                return ""
            return path.read_text()

        if kind == "text":
            expected = {"S01": "71", "S02": "2,6,9", "S03": "早上好", "S04": "22.90"}[ident]
            if read("answer.txt").strip().replace(" ", "").replace("，", ",") != expected:
                artifact_errors.append("answer_mismatch")
        elif kind in ("invoice", "handoff"):
            try:
                data = json.loads(read("result.json"))
                if data != {"format": "bill-audit/1", "input_rows": 3,
                            "duplicate_refs": ["INV-17"], "payable_total": "17.50"}:
                    artifact_errors.append("invoice_contract_mismatch")
            except ValueError:
                artifact_errors.append("invalid_invoice_json")
            if kind == "handoff":
                notice = read("notice.md")
                for text in ("# Billing notice", "Amount due: 17.50", "Duplicate references: INV-17", "Status: draft"):
                    if text not in notice:
                        artifact_errors.append("notice_contract_mismatch:" + text)
        elif kind == "release":
            report = read("result.md")
            for text in ("# Project update", "## Added", "## Fixed", "- Export filtered records",
                         "- Preserve empty cells", "Review: project-team"):
                if text not in report:
                    artifact_errors.append("release_contract_mismatch:" + text)
            if "lockfile" in report or "chore:" in report:
                artifact_errors.append("internal_change_in_release_notes")
        else:
            response = read("response.md")
            if not response.strip():
                artifact_errors.append("empty_boundary_response")
            if any(p.name != "response.md" for p in paths):
                artifact_errors.append("unexpected_business_artifact")
            if ident == "R01" and "amber-kit" not in response:
                decision_errors.append("suitable_recommendation_missing")

        expected_status = {"direct": "completed", "skill": "completed",
                           "recommend": "recommended", "blocked": "blocked"}[label["route"]]
        if result.get("status") != expected_status:
            decision_errors.append("status_mismatch")
        if result.get("decision") != label["route"]:
            decision_errors.append("decision_mismatch")
        if not isinstance(result.get("reason"), str) or not result["reason"].strip():
            decision_errors.append("decision_reason_missing")
        applied = result.get("skills_applied", [])
        if not isinstance(applied, list) or any(not isinstance(a, dict) for a in applied):
            decision_errors.append("invalid_application_receipt")
            applied = []
        names = [a.get("name") for a in applied]
        if set(names) != set(label["required_skills"]):
            decision_errors.append("reported_application_mismatch")
        for entry in applied:
            if entry.get("kind") not in ("script", "instructions") or not entry.get("evidence"):
                decision_errors.append("application_evidence_missing")
        if any(name not in result.get("skills_loaded", []) for name in names):
            decision_errors.append("reported_application_without_loading")
        if label["route"] == "direct" and result.get("skills_loaded"):
            decision_errors.append("unnecessary_downstream_loading")
        if result.get("manual_handoffs") != 0:
            decision_errors.append("manual_handoff_or_unknown")
        graded.append({"id": ident, "expected_decision": label["route"],
                       "artifacts_passed": not artifact_errors, "artifact_errors": artifact_errors,
                       "declared_decision_passed": not decision_errors, "decision_errors": decision_errors,
                       "reported_applied_skills": names,
                       "artifact_and_declaration_checks_passed": not artifact_errors and not decision_errors})
    return {"group": group, "cases": len(graded), "skills_per_case": protocol["skills_per_case"],
            "artifacts_passed": sum(r["artifacts_passed"] for r in graded),
            "declared_decisions_passed": sum(r["declared_decision_passed"] for r in graded),
            "artifact_and_declaration_checks_passed": sum(r["artifact_and_declaration_checks_passed"] for r in graded),
            "host_receipts_verified": False,
            "behavioral_acceptance": "not_established_by_this_checker",
            "altered_inputs_or_skills": len(altered),
            "labels_sha256": protocol["labels_sha256"], "results": graded,
            "limits": "Synthetic metadata-truncation scenario. File checks are independent; declared routing/application needs host tool-receipt review. One run cannot establish superiority or stable real-user accuracy."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace")
    parser.add_argument("group", choices=["A", "B", "C"])
    args = parser.parse_args()
    try:
        result = verify(args.workspace, args.group)
    except ValueError as exc:
        print(json.dumps({"error": "invalid_evaluation_data", "detail": str(exc)}))
        raise SystemExit(2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["artifact_and_declaration_checks_passed"] == result["cases"] else 1)
