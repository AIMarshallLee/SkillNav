#!/usr/bin/env python3
"""Bounded, read-only indicators for one local skill; never a safety certificate."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat


RULES = {
    "remote_code_execution": r"\b(?:curl|wget)\b[^\n]*\|\s*(?:ba|z|da)?sh\b|\b(?:ba|z)?sh\s*<\(\s*(?:curl|wget)\b",
    "network_access": r"\b(?:curl|wget)\b|\b(?:requests|httpx)\.(?:post|put|get|request)\s*\(|\b(?:fetch|urlopen)\s*\(",
    "destructive_command": r"\brm\s+(?:-[a-zA-Z]*[rf][a-zA-Z]*\s+)+|\b(?:rmtree|Remove-Item)\b",
    "credential_access": r"(?:~|\$HOME|\$\{HOME\})/\.(?:ssh|aws|config)|\b(?:keychain|find-generic-password|cookies\.sqlite)\b|(?:^|[/\s'\x22])\.env\b",
    "dynamic_execution": r"\b(?:eval|exec|compile|Invoke-Expression)\s*\(|\b(?:b64decode|frombase64string)\s*\(|\bnew\s+Function\s*\(",
    "persistent_change": r"\b(?:crontab|launchctl|schtasks|systemctl)\b|\.(?:bashrc|zshrc|bash_profile)\b",
    "privilege_or_permissions": r"\b(?:sudo|chmod|chown|Set-ExecutionPolicy)\b",
    "dependency_install": r"\b(?:pip3?|npm|pnpm|yarn|brew|apt-get)\s+(?:install|add)\b",
    "instruction_override": r"(?:ignore|disregard|override)\s+(?:all\s+)?(?:previous|prior|system|developer)\s+(?:instructions|rules|messages)|do not tell (?:the )?user|忽略.{0,12}(?:指令|规则)|绕过.{0,12}授权|不要告诉用户",
}
PATTERNS = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in RULES.items()}
PRUNED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".ssh", ".aws"}
SENSITIVE = re.compile(r"^(?:\.env(?:\..*)?|credentials.*|auth\.json|.*\.(?:pem|key|sqlite3?|db))$", re.IGNORECASE)
MAX_ENTRIES = 1024
MAX_FINDINGS = 64
MAX_ALLOWED_FILE_BYTES = 1024 * 1024
MAX_ALLOWED_TOTAL_BYTES = 16 * 1024 * 1024


def review(skill, *, max_files=128, max_file_bytes=131072, max_total_bytes=1048576, max_depth=8):
    if any(type(n) is not int or n <= 0 for n in (max_files, max_file_bytes, max_total_bytes)):
        raise ValueError("review_limits_must_be_positive_integers")
    if (max_files > MAX_ENTRIES or max_file_bytes > MAX_ALLOWED_FILE_BYTES
            or max_total_bytes > MAX_ALLOWED_TOTAL_BYTES):
        raise ValueError("review_limits_exceed_hard_ceiling")
    if type(max_depth) is not int or not 0 <= max_depth <= 32:
        raise ValueError("review_depth_must_be_between_0_and_32")
    root = Path(os.path.abspath(Path(skill).expanduser()))
    if root.resolve(strict=True) != root or not root.is_dir():
        raise ValueError("declare_a_real_skill_directory_without_symlink_components")
    try:
        entry = (root / "SKILL.md").lstat()
    except FileNotFoundError:
        raise ValueError("skill_entry_missing")
    if not stat.S_ISREG(entry.st_mode) or entry.st_nlink > 1:
        raise ValueError("skill_entry_must_be_regular_unlinked_file")
    files, skipped, findings = [], [], []
    categories = Counter()
    total_bytes, entry_count = 0, 0

    def skip(path, reason):
        skipped.append({"path": str(path.relative_to(root)) or ".", "reason": reason})

    def inspect(path):
        nonlocal total_bytes
        if len(files) >= max_files:
            skip(path, "file_count_limit")
            return
        if SENSITIVE.fullmatch(path.name):
            skip(path, "sensitive_file_not_read")
            return
        if path.resolve(strict=True) != path:
            skip(path, "symlink_not_followed")
            return
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            st = os.fstat(stream.fileno())
            if not stat.S_ISREG(st.st_mode):
                skip(path, "not_regular_file")
                return
            if st.st_nlink > 1:
                skip(path, "hardlink_not_read")
                return
            if st.st_size > max_file_bytes:
                skip(path, "file_too_large")
                return
            remaining = max_total_bytes - total_bytes
            if st.st_size > remaining:
                skip(path, "total_byte_limit")
                return
            data = stream.read(min(max_file_bytes, remaining) + 1)
            total_bytes += len(data)
            if len(data) > min(max_file_bytes, remaining):
                skip(path, "file_changed_or_byte_limit")
                return
        try:
            text = data.decode("utf-8-sig")
            if "\x00" in text:
                raise UnicodeError()
        except UnicodeError:
            skip(path, "non_text_file")
            return
        relative = str(path.relative_to(root))
        files.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        for line_number, line in enumerate(text.splitlines(), 1):
            for category, pattern in PATTERNS.items():
                if pattern.search(line):
                    categories[category] += 1
                    if len(findings) < MAX_FINDINGS:
                        findings.append({"path": relative, "line": line_number, "category": category,
                                         "requires_context_review": True})

    def visit(directory, depth):
        nonlocal entry_count
        if depth > max_depth:
            skip(directory, "depth_limit")
            return
        if directory.resolve(strict=True) != directory:
            skip(directory, "symlink_not_followed")
            return
        # Bound enumeration itself as well as file reads; do not list arbitrary trees.
        children = []
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry_count >= MAX_ENTRIES:
                    skip(directory, "entry_limit")
                    break
                entry_count += 1
                children.append(Path(entry.path))
        for path in sorted(children):
            try:
                st = path.lstat()
                if stat.S_ISLNK(st.st_mode):
                    skip(path, "symlink_not_followed")
                elif stat.S_ISDIR(st.st_mode):
                    if path.name in PRUNED:
                        skip(path, "dependency_or_state_directory")
                    else:
                        visit(path, depth + 1)
                elif stat.S_ISREG(st.st_mode):
                    inspect(path)
                else:
                    skip(path, "not_regular_file")
            except (OSError, RuntimeError):
                skip(path, "unreadable_or_changed")

    try:
        visit(root, 0)
    except (OSError, RuntimeError):
        skip(root, "unreadable_or_changed")
    manifest = sorted(files, key=lambda f: f["path"])
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    return {
        "skill_root": str(root), "review_type": "bounded_static_indicators",
        "automated_verdict": "indicators_found" if findings else "no_indicators_in_scanned_text",
        "coverage": {"complete": not skipped, "files_read": len(files), "bytes_read": total_bytes,
                     "entries_inspected": entry_count, "skipped_entries": len(skipped)},
        "limits": {"max_files": max_files, "max_file_bytes": max_file_bytes,
                   "max_total_bytes": max_total_bytes, "max_depth": max_depth,
                   "max_entries": MAX_ENTRIES, "max_findings": MAX_FINDINGS},
        "findings": findings, "findings_by_category": dict(sorted(categories.items())),
        "findings_truncated": sum(categories.values()) > len(findings),
        "files": manifest, "skipped": skipped, "snapshot_sha256": fingerprint,
        "snapshot_scope": "Only successfully read text files; skipped content is not fingerprinted",
        "source_verification": "not_performed", "execution_performed": False, "safety_certified": False,
        "limitations": [
            "Pattern indicators need contextual review; documentation and prohibitions can match.",
            "No matches do not establish safety. Obfuscation, dependencies, remote content and runtime behavior may be missed.",
            "No candidate code, imports, installs, network calls or state writes are performed.",
            "Use a trusted stable local directory and host sandbox; this is not isolation against hostile concurrent filesystem changes.",
            "Review actual source/provenance, task fit, enablement, permissions and any unreviewed executable content before use.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True, help="One explicit real local skill directory")
    parser.add_argument("--max-files", type=int, default=128)
    parser.add_argument("--max-file-bytes", type=int, default=131072)
    parser.add_argument("--max-total-bytes", type=int, default=1048576)
    parser.add_argument("--max-depth", type=int, default=8)
    args = parser.parse_args(argv)
    try:
        result = review(args.skill, max_files=args.max_files, max_file_bytes=args.max_file_bytes,
                        max_total_bytes=args.max_total_bytes, max_depth=args.max_depth)
    except (OSError, RuntimeError, ValueError) as exc:
        code = str(exc) if type(exc) is ValueError else "unreadable_or_invalid_skill_directory"
        print(json.dumps({"error": code}))
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 1 if result["findings"] or not result["coverage"]["complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
