"""Read-only, bounded file-contract checks for a single authorized task root.

This tool never executes candidate code, calls a network service, writes records, or
discovers host tools. Requirement rows are supplied host observations only; they do
not prove authorization or that a tool/dependency is genuine.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import stat
import sys
from pathlib import Path


MAX_CONTRACT_BYTES = 256 * 1024
MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_READ_BYTES = 16 * 1024 * 1024
MAX_FILES = 64
MAX_JSON_DEPTH = 24
MAX_JSON_ITEMS = 256
MAX_STRING_BYTES = 16 * 1024
MAX_CSV_ROWS = 10000
MAX_CSV_FIELDS = 256
ID_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
FORMATS = {"text", "json", "csv"}
ROLES = {"deliverable", "report"}
REQUIREMENT_KINDS = {"host_tool", "dependency"}
REQUIREMENT_STATUSES = {"verified", "missing", "unknown"}
RULE_FORMATS = {
    "equals": {"text"},
    "contains": {"text"},
    "not_contains": {"text"},
    "json_equals": {"json"},
    "csv_columns": {"csv"},
    "csv_row_count": {"csv"},
    "markdown_headings": {"text"},
}


class ContractError(ValueError):
    """A stable diagnostic reason, deliberately without file contents."""


class _DuplicateKey(ValueError):
    pass


def _reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey()
        result[key] = value
    return result


def _strict_json(data, *, reason):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError(f"{reason}_not_utf8") from exc
    try:
        def finite_float(raw):
            value = float(raw)
            if not math.isfinite(value):
                raise ValueError()
            return value
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicates,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
            parse_float=finite_float,
        )
    except _DuplicateKey as exc:
        raise ContractError(f"{reason}_duplicate_key") from exc
    except (ValueError, json.JSONDecodeError, OverflowError, RecursionError) as exc:
        raise ContractError(f"{reason}_invalid_json") from exc
    try:
        _bound_json(value, 0)
    except (RecursionError, UnicodeError) as exc:
        raise ContractError(f"{reason}_invalid_json") from exc
    return value


def _bound_json(value, depth):
    if depth > MAX_JSON_DEPTH:
        raise ContractError("json_nesting_limit")
    if isinstance(value, str):
        try:
            too_large = len(value.encode("utf-8")) > MAX_STRING_BYTES
        except UnicodeError as exc:
            raise ContractError("json_invalid_unicode") from exc
        if too_large:
            raise ContractError("json_string_limit")
    elif isinstance(value, list):
        if len(value) > MAX_JSON_ITEMS:
            raise ContractError("json_array_limit")
        for item in value:
            _bound_json(item, depth + 1)
    elif isinstance(value, dict):
        if len(value) > MAX_JSON_ITEMS:
            raise ContractError("json_object_limit")
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractError("json_key_invalid")
            _bound_json(key, depth + 1)
            _bound_json(item, depth + 1)


def _root_path(root):
    if not isinstance(root, (str, os.PathLike)):
        raise ContractError("root_invalid")
    root = os.path.abspath(os.fspath(root))
    root_status = None
    for index, ancestor in enumerate((root, *Path(root).parents)):
        try:
            status = os.lstat(ancestor)
        except OSError as exc:
            raise ContractError("root_missing") from exc
        if stat.S_ISLNK(status.st_mode):
            raise ContractError("root_ancestor_symlink_rejected")
        if index == 0:
            root_status = status
    if not stat.S_ISDIR(root_status.st_mode):
        raise ContractError("root_not_directory")
    return root


def _path_under_root(root, value):
    if not isinstance(value, (str, os.PathLike)):
        raise ContractError("path_invalid")
    value = os.fspath(value)
    if not value or "\x00" in value:
        raise ContractError("path_invalid")
    candidate = value if os.path.isabs(value) else os.path.join(root, value)
    candidate = os.path.abspath(candidate)
    try:
        if os.path.commonpath((root, candidate)) != root:
            raise ContractError("path_outside_root")
    except ValueError as exc:
        raise ContractError("path_outside_root") from exc
    relative = os.path.relpath(candidate, root)
    if relative == "." or relative == os.pardir or relative.startswith(os.pardir + os.sep):
        raise ContractError("path_outside_root")
    # Do not resolve through a link. Check only root and its authorized descendants;
    # system ancestors are outside the caller's granted task root.
    current = root
    for part in Path(relative).parts:
        current = os.path.join(current, part)
        try:
            current_status = os.lstat(current)
        except FileNotFoundError:
            break
        except OSError as exc:
            raise ContractError("path_unreadable") from exc
        if stat.S_ISLNK(current_status.st_mode):
            raise ContractError("path_symlink_rejected")
    return candidate, Path(relative).as_posix()


class _ReadBudget:
    def __init__(self):
        self.used = 0
        self.identities = {}

    def claim(self, size):
        if self.used + size > MAX_TOTAL_READ_BYTES:
            raise ContractError("total_read_limit")
        self.used += size

    def claim_file(self, status, role):
        identity = (status.st_dev, status.st_ino)
        previous = self.identities.get(identity, set())
        if previous and (role == "artifact" or "artifact" in previous):
            raise ContractError("file_identity_reused")
        self.identities.setdefault(identity, set()).add(role)


def _read_regular(root, value, limit, budget=None, identity_role=None):
    candidate, relative = _path_under_root(root, value)
    try:
        before = os.lstat(candidate)
    except FileNotFoundError as exc:
        raise ContractError("file_missing") from exc
    except OSError as exc:
        raise ContractError("file_unreadable") from exc
    if not stat.S_ISREG(before.st_mode):
        raise ContractError("file_not_regular")
    if before.st_nlink != 1:
        raise ContractError("file_hardlink_rejected")
    if before.st_size <= 0:
        raise ContractError("file_empty")
    if before.st_size > limit:
        raise ContractError("file_size_limit")
    if budget is not None:
        budget.claim(before.st_size)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(candidate, flags)
    except OSError as exc:
        raise ContractError("file_unreadable") from exc
    try:
        with os.fdopen(descriptor, "rb") as handle:
            after = os.fstat(handle.fileno())
            if (not stat.S_ISREG(after.st_mode) or after.st_nlink != 1 or
                    (before.st_dev, before.st_ino, before.st_size) !=
                    (after.st_dev, after.st_ino, after.st_size)):
                raise ContractError("file_changed_or_unsafe")
            if budget is not None and identity_role is not None:
                budget.claim_file(after, identity_role)
            data = handle.read(limit + 1)
    except ContractError:
        raise
    except OSError as exc:
        raise ContractError("file_unreadable") from exc
    if len(data) > limit:
        raise ContractError("file_size_limit")
    return data, {"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _exact_keys(value, keys, reason):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ContractError(reason)


def _id(value, reason):
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise ContractError(reason)
    return value


def _nonempty_string(value, reason):
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > MAX_STRING_BYTES:
        raise ContractError(reason)
    return value


def _validate_checks(checks, file_format, reason):
    if not isinstance(checks, list) or not checks:
        raise ContractError(f"{reason}_checks_required")
    if len(checks) > 32:
        raise ContractError(f"{reason}_checks_limit")
    validated = []
    for index, check in enumerate(checks):
        _exact_keys(check, ("type", "expected"), f"{reason}_check_{index}_schema")
        check_type = check["type"]
        if not isinstance(check_type, str) or check_type not in RULE_FORMATS:
            raise ContractError(f"{reason}_check_{index}_unknown")
        if file_format not in RULE_FORMATS[check_type]:
            raise ContractError(f"{reason}_check_{index}_incompatible")
        expected = check["expected"]
        if check_type in {"equals", "contains", "not_contains"}:
            _nonempty_string(expected, f"{reason}_check_{index}_expected")
        elif check_type == "csv_row_count":
            if type(expected) is not int or expected < 0 or expected > MAX_CSV_ROWS:
                raise ContractError(f"{reason}_check_{index}_expected")
        elif check_type == "csv_columns":
            if (not isinstance(expected, list) or not expected or len(expected) > MAX_CSV_FIELDS or
                    any(not isinstance(column, str) for column in expected) or len(set(expected)) != len(expected)):
                raise ContractError(f"{reason}_check_{index}_expected")
            for column in expected:
                _nonempty_string(column, f"{reason}_check_{index}_expected")
        elif check_type == "markdown_headings":
            if not isinstance(expected, list) or not expected or len(expected) > 128:
                raise ContractError(f"{reason}_check_{index}_expected")
            for heading in expected:
                _nonempty_string(heading, f"{reason}_check_{index}_expected")
                if not re.fullmatch(r"#{1,6}[ \t]+\S.*", heading):
                    raise ContractError(f"{reason}_check_{index}_expected")
        validated.append({"type": check_type, "expected": expected})
    return validated


def _validate_file_entry(value, *, artifact, index):
    keys = ("id", "path", "role", "format", "checks") if artifact else ("id", "path", "format", "checks")
    prefix = "artifact" if artifact else "input"
    _exact_keys(value, keys, f"{prefix}_{index}_schema")
    entry_id = _id(value["id"], f"{prefix}_{index}_id")
    path = _nonempty_string(value["path"], f"{prefix}_{index}_path")
    if not isinstance(value["format"], str) or value["format"] not in FORMATS:
        raise ContractError(f"{prefix}_{index}_format")
    result = {"id": entry_id, "path": path, "format": value["format"],
              "checks": _validate_checks(value["checks"], value["format"], f"{prefix}_{index}")}
    if artifact:
        if not isinstance(value["role"], str) or value["role"] not in ROLES:
            raise ContractError(f"artifact_{index}_role")
        result["role"] = value["role"]
    return result


def validate_contract(value):
    _exact_keys(value, ("version", "inputs", "requirements", "artifacts"), "contract_schema")
    if type(value["version"]) is not int or value["version"] != 1:
        raise ContractError("contract_version")
    if not isinstance(value["inputs"], list) or not value["inputs"] or len(value["inputs"]) > 128:
        raise ContractError("inputs_required")
    if not isinstance(value["requirements"], list) or len(value["requirements"]) > 128:
        raise ContractError("requirements_schema")
    if not isinstance(value["artifacts"], list) or not value["artifacts"] or len(value["artifacts"]) > 128:
        raise ContractError("artifacts_required")
    if len(value["inputs"]) + len(value["artifacts"]) > MAX_FILES:
        raise ContractError("file_entries_limit")
    inputs = [_validate_file_entry(entry, artifact=False, index=index) for index, entry in enumerate(value["inputs"])]
    artifacts = [_validate_file_entry(entry, artifact=True, index=index) for index, entry in enumerate(value["artifacts"])]
    if len({entry["id"] for entry in inputs}) != len(inputs):
        raise ContractError("input_id_reused")
    if len({entry["id"] for entry in artifacts}) != len(artifacts):
        raise ContractError("artifact_id_reused")
    if len({entry["path"] for entry in artifacts}) != len(artifacts):
        raise ContractError("artifact_path_reused")
    if {entry["id"] for entry in inputs} & {entry["id"] for entry in artifacts}:
        raise ContractError("input_artifact_id_reused")
    if not any(entry["role"] == "deliverable" for entry in artifacts):
        raise ContractError("deliverable_required")
    requirements = []
    for index, requirement in enumerate(value["requirements"]):
        _exact_keys(requirement, ("id", "kind", "status", "evidence"), f"requirement_{index}_schema")
        if not isinstance(requirement["kind"], str) or requirement["kind"] not in REQUIREMENT_KINDS:
            raise ContractError(f"requirement_{index}_kind")
        if not isinstance(requirement["status"], str) or requirement["status"] not in REQUIREMENT_STATUSES:
            raise ContractError(f"requirement_{index}_status")
        evidence = _nonempty_string(requirement["evidence"], f"requirement_{index}_evidence")
        if not evidence.strip():
            raise ContractError(f"requirement_{index}_evidence")
        requirements.append({"id": _id(requirement["id"], f"requirement_{index}_id"),
                             "kind": requirement["kind"], "status": requirement["status"],
                             "evidence": evidence})
    if len({entry["id"] for entry in requirements}) != len(requirements):
        raise ContractError("requirement_id_reused")
    return {"version": 1, "inputs": inputs, "requirements": requirements, "artifacts": artifacts}


def _validate_paths(root, contract, contract_path):
    _contract_absolute, contract_relative = _path_under_root(root, contract_path)
    input_paths = set()
    artifact_paths = set()
    for entry in contract["inputs"]:
        if os.path.isabs(entry["path"]):
            raise ContractError("input_path_not_relative")
        _absolute, relative = _path_under_root(root, entry["path"])
        entry["path"] = relative
        input_paths.add(relative)
    for entry in contract["artifacts"]:
        if os.path.isabs(entry["path"]):
            raise ContractError("artifact_path_not_relative")
        _absolute, relative = _path_under_root(root, entry["path"])
        entry["path"] = relative
        artifact_paths.add(relative)
        if relative == contract_relative:
            raise ContractError("artifact_path_contract_reused")
    if len(artifact_paths) != len(contract["artifacts"]):
        raise ContractError("artifact_path_reused")
    if input_paths & artifact_paths:
        raise ContractError("input_artifact_path_reused")
    # Catch existing case/Unicode aliases before execution on filesystems that use
    # them. Planned outputs may not exist; opened identities are checked again later.
    identities = _ReadBudget()
    declared = [(contract_relative, "contract")]
    declared.extend((entry["path"], "input") for entry in contract["inputs"])
    declared.extend((entry["path"], "artifact") for entry in contract["artifacts"])
    for relative, role in declared:
        absolute, _ = _path_under_root(root, relative)
        try:
            status = os.lstat(absolute)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ContractError("path_unreadable") from exc
        if role == "artifact" and (not stat.S_ISREG(status.st_mode) or status.st_nlink != 1):
            raise ContractError("artifact_file_unsafe")
        identities.claim_file(status, role)
    return contract


def load_contract(root, contract_path, budget=None):
    root = _root_path(root)
    data, metadata = _read_regular(root, contract_path, MAX_CONTRACT_BYTES, budget, "contract")
    return root, _validate_paths(root, validate_contract(_strict_json(data, reason="contract")), contract_path), metadata


def _check_entry(root, entry, *, artifact, budget=None):
    result = {"id": entry["id"], "path": entry["path"]}
    if artifact:
        result["role"] = entry["role"]
    try:
        data, metadata = _read_regular(root, entry["path"], MAX_FILE_BYTES, budget,
                                       "artifact" if artifact else "input")
        _apply_checks(data, entry)
        result.update(metadata, status="passed", reason="ok")
    except ContractError as exc:
        result.update(status="failed", reason=str(exc))
    return result


def _apply_checks(data, entry):
    file_format = entry["format"]
    if file_format == "text":
        try:
            parsed = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContractError("text_not_utf8") from exc
    elif file_format == "json":
        parsed = _strict_json(data, reason="content")
    else:
        try:
            parsed = []
            reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
            for row in reader:
                parsed.append(row)
                if len(parsed) > MAX_CSV_ROWS + 1 or len(row) > MAX_CSV_FIELDS:
                    raise ContractError("csv_limits_or_header")
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ContractError("csv_invalid") from exc
        if not parsed or not parsed[0] or any(len(row) != len(parsed[0]) for row in parsed):
            raise ContractError("csv_limits_or_header")
    if file_format == "text" and not parsed.strip():
        raise ContractError("text_blank")
    for check in entry["checks"]:
        check_type, expected = check["type"], check["expected"]
        if check_type == "equals":
            passed = parsed == expected
        elif check_type == "contains":
            passed = expected in parsed
        elif check_type == "not_contains":
            passed = expected not in parsed
        elif check_type == "json_equals":
            passed = _json_equal(parsed, expected)
        elif check_type == "csv_columns":
            passed = parsed[0] == expected
        elif check_type == "csv_row_count":
            passed = len(parsed) - 1 == expected
        else:  # markdown_headings
            passed = _markdown_headings(parsed) == expected
        if not passed:
            raise ContractError(f"check_failed_{check_type}")


def _markdown_headings(text):
    """ATX heading lines outside fenced/indented code, not a full Markdown parser."""
    headings = []
    fence_char, fence_length = None, 0
    for line in text.splitlines():
        if fence_char is not None:
            if re.fullmatch(r" {0,3}" + re.escape(fence_char) + "{" + str(fence_length) + r",}[ \t]*", line):
                fence_char = None
            continue
        opener = re.fullmatch(r" {0,3}(`{3,}|~{3,})(.*)", line)
        if opener and (opener[1][0] != "`" or "`" not in opener[2]):
            fence_char, fence_length = opener[1][0], len(opener[1])
            continue
        if re.fullmatch(r" {0,3}#{1,6}[ \t]+\S.*", line):
            headings.append(line.strip())
    return headings


def _json_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(_json_equal(actual[key], expected[key]) for key in actual)
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(_json_equal(left, right) for left, right in zip(actual, expected))
    return actual == expected


def _preflight_contract(root, contract, budget):
    inputs = [_check_entry(root, entry, artifact=False, budget=budget) for entry in contract["inputs"]]
    requirements = [{"id": entry["id"], "kind": entry["kind"],
                     "observed_status": entry["status"],
                     "status": "passed" if entry["status"] == "verified" else "failed",
                     "reason": "observed_verified" if entry["status"] == "verified" else "requirement_not_verified"}
                    for entry in contract["requirements"]]
    artifacts = [{"id": entry["id"], "role": entry["role"], "path": entry["path"],
                  "status": "not_checked", "reason": "preflight_schema_only"} for entry in contract["artifacts"]]
    ok = all(row["status"] == "passed" for row in inputs + requirements)
    return {"ok": ok, "action": "preflight", "inputs": inputs, "requirements": requirements, "artifacts": artifacts,
            "limits": "Read-only checks: 1 MiB per file, 64 input/artifact entries, 16 MiB total reads. Host requirements are observations, not authorization or tool attestation."}


def preflight(root, contract_path):
    budget = _ReadBudget()
    root, contract, contract_metadata = load_contract(root, contract_path, budget)
    report = _preflight_contract(root, contract, budget)
    report["contract"] = contract_metadata
    return report


def check(root, contract_path):
    budget = _ReadBudget()
    root, contract, contract_metadata = load_contract(root, contract_path, budget)
    report = _preflight_contract(root, contract, budget)
    artifacts = [_check_entry(root, entry, artifact=True, budget=budget) for entry in contract["artifacts"]]
    report["action"] = "check"
    report["artifacts"] = artifacts
    report["contract"] = contract_metadata
    report["ok"] = report["ok"] and all(row["status"] == "passed" for row in artifacts)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check"))
    parser.add_argument("--root", required=True, help="Explicit authorized task root; no traversal occurs outside it.")
    parser.add_argument("--contract", required=True, help="Explicit JSON contract path inside --root.")
    args = parser.parse_args(argv)
    try:
        result = preflight(args.root, args.contract) if args.action == "preflight" else check(args.root, args.contract)
    except ContractError as exc:
        result = {"ok": False, "action": args.action, "reason": str(exc),
                  "limits": "No file contents, candidate execution, network access, persistence, or authorization attestation."}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
