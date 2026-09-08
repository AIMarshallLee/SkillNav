#!/usr/bin/env python3
"""Read bounded skill metadata from declared roots; never execute skill content."""
from __future__ import annotations

import argparse
import errno
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

VERSION = "0.1.0"
MAX_HEADER_BYTES = 32768
MAX_CATALOG_BYTES = 2 * 1024 * 1024
PRUNED = {"node_modules", "__pycache__", "assets", "references", "scripts"}

try:
    import yaml
except ImportError:
    yaml = None


class MetadataError(ValueError):
    pass


def read_header(path):
    """Do not read Markdown bodies, special files, or unbounded headers."""
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise MetadataError("not_regular_file")
        first = stream.readline(MAX_HEADER_BYTES + 1)
        if first.decode("utf-8-sig").strip() != "---":
            raise MetadataError("missing_frontmatter")
        size = len(first)
        lines = []
        while size <= MAX_HEADER_BYTES:
            line = stream.readline(MAX_HEADER_BYTES - size + 1)
            size += len(line)
            if not line:
                raise MetadataError("unclosed_frontmatter")
            if size > MAX_HEADER_BYTES:
                break
            if line.strip() == b"---":
                return b"".join(lines).decode("utf-8")
            lines.append(line)
    raise MetadataError("frontmatter_too_large")


def parse_metadata(header):
    if yaml is None:
        raise MetadataError("missing_pyyaml")

    class UniqueSafeLoader(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            result = {}
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, str) or key in result:
                    raise MetadataError("invalid_or_duplicate_yaml_key")
                result[key] = self.construct_object(value_node, deep=deep)
            return result

    # Aliases add no value to discovery metadata and can cause expansion attacks.
    try:
        if any(isinstance(t, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken))
               for t in yaml.scan(header)):
            raise MetadataError("yaml_alias_not_supported")
        data = yaml.load(header, Loader=UniqueSafeLoader)
    except (yaml.YAMLError, RecursionError) as exc:
        raise MetadataError("invalid_yaml") from exc
    if not isinstance(data, dict):
        raise MetadataError("metadata_not_mapping")
    name, description = data.get("name"), data.get("description")
    if not isinstance(name, str) or not name.strip() or len(name) > 64:
        raise MetadataError("invalid_name")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        raise MetadataError("invalid_description")
    return name.strip(), description.strip()


def error_code(exc):
    if isinstance(exc, MetadataError):
        return str(exc)
    if isinstance(exc, PermissionError):
        return "permission_denied"
    if isinstance(exc, FileNotFoundError):
        return "missing"
    if isinstance(exc, RuntimeError) or getattr(exc, "errno", None) == errno.ELOOP:
        return "symlink_loop"
    if isinstance(exc, UnicodeError):
        return "invalid_utf8"
    return "io_error"


def default_roots(cwd=None, home=None, admin=None):
    cwd = Path(cwd or Path.cwd()).resolve()
    home = Path(home or Path.home())
    try:
        result = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                                capture_output=True, text=True, timeout=5, check=False)
        repo = Path(result.stdout.strip()).resolve() if result.returncode == 0 else cwd
    except (OSError, subprocess.TimeoutExpired):
        repo = cwd
    if not cwd.is_relative_to(repo):
        repo = cwd
    roots = []
    current = cwd
    while True:
        roots.append({"path": str(current / ".agents" / "skills"),
                      "source": "repository", "scope": str(current)})
        if current == repo:
            break
        current = current.parent
    roots.extend([
        {"path": str(home / ".agents" / "skills"), "source": "user", "scope": "user"},
        {"path": str(admin or "/etc/codex/skills"), "source": "admin", "scope": "system"},
    ])
    return roots


def scan(roots, *, max_dirs=10000, max_depth=32):
    records, issues, scopes = {}, [], []
    allowed = []
    for root in roots:
        entry = dict(root, status="pending", directories=0, discovered=0, readable=0)
        scopes.append(entry)
        try:
            lexical = Path(os.path.abspath(Path(root["path"]).expanduser()))
            # Declaring a symlink does not authorize its otherwise undeclared target.
            resolved = lexical.resolve(strict=True)
            entry["path"] = str(lexical)
            entry["resolved_path"] = str(resolved)
            if not resolved.is_dir():
                raise MetadataError("not_directory")
            if resolved == lexical:
                allowed.append(resolved)
        except (OSError, RuntimeError, MetadataError) as exc:
            entry["status"] = error_code(exc)
            issues.append({"path": root["path"], "code": entry["status"]})

    def inside(path):
        return any(path.is_relative_to(root) for root in allowed)

    def issue(path, code):
        issues.append({"path": str(path), "code": code})

    def origin(entry, path):
        return {"source": entry["source"], "scope": entry["scope"],
                "root": entry["path"], "path": str(path)}

    total_dirs = 0
    for entry in scopes:
        if entry["status"] != "pending":
            continue
        root = Path(entry["path"])
        if not inside(Path(entry["resolved_path"])):
            entry["status"] = "outside_allowed_roots"
            issue(root, entry["status"])
            continue
        entry["status"] = "scanned"
        visited = set()

        def visit(path, depth, ancestors):
            nonlocal total_dirs
            try:
                real = path.resolve(strict=True)
                if not inside(real):
                    issue(path, "outside_allowed_roots")
                    return
                if real in ancestors:
                    issue(path, "symlink_loop")
                    return
                if real in visited:
                    issue(path, "duplicate_directory")
                    return
                if depth > max_depth or total_dirs >= max_dirs:
                    entry["status"] = "limited"
                    issue(path, "scan_limit")
                    return
                visited.add(real)
                total_dirs += 1
                entry["directories"] += 1
                children = sorted(real.iterdir(), key=lambda p: p.name)
                if any(p.name == "SKILL.md" for p in children):
                    skill_path = path / "SKILL.md"
                    entry["discovered"] += 1
                    record = {"name": None, "description": None, "path": str(skill_path),
                              "source": entry["source"], "scope": entry["scope"],
                              "origins": [origin(entry, skill_path)], "read_status": "pending",
                              "enabled": "unknown", "host_visible": "unknown",
                              "disk_status": "unknown", "dependencies": "not_checked"}
                    key = str(skill_path)
                    try:
                        target = skill_path.resolve(strict=True)
                        if not inside(target):
                            raise MetadataError("outside_allowed_roots")
                        if target.name != "SKILL.md":
                            raise MetadataError("non_skill_symlink_target")
                        key = str(target)
                        record["path"] = key
                        if key in records:
                            records[key]["origins"].append(origin(entry, skill_path))
                            if records[key]["read_status"] == "readable":
                                entry["readable"] += 1
                            return
                        record["disk_status"] = "present"
                        name, description = parse_metadata(read_header(target))
                        record.update(name=name, description=description, read_status="readable")
                        entry["readable"] += 1
                        # Retain useful legacy records; flag specification mismatches.
                        if (not all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name)
                                or name.startswith("-") or name.endswith("-") or "--" in name):
                            issue(skill_path, "nonstandard_name")
                        if target.parent.name != name:
                            issue(skill_path, "name_directory_mismatch")
                    except (OSError, RuntimeError, MetadataError, UnicodeError) as exc:
                        record["read_status"] = error_code(exc)
                        issue(skill_path, record["read_status"])
                    records[key] = record
                    return  # References/scripts/assets are not discovery roots.
                for child in children:
                    if child.name.startswith(".") or child.name in PRUNED:
                        if child.is_dir() or child.is_symlink():
                            issue(path / child.name, "pruned_directory")
                        continue
                    if child.is_symlink() or child.is_dir():
                        candidate = path / child.name
                        try:
                            target = candidate.resolve(strict=True)
                            if not inside(target):
                                issue(candidate, "outside_allowed_roots")
                            elif target.is_dir():
                                visit(candidate, depth + 1, ancestors | {real})
                        except (OSError, RuntimeError) as exc:
                            issue(candidate, error_code(exc))
            except (OSError, RuntimeError) as exc:
                issue(path, error_code(exc))
                if depth == 0:
                    entry["status"] = error_code(exc)

        visit(root, 0, set())
    return {"schema_version": 1, "version": VERSION, "roots": scopes,
            "skills": list(records.values()), "issues": issues,
            "limitations": [
                "Only declared roots; hidden and resource directories are pruned. Declare an exact root to include them.",
                "Disk presence does not establish host visibility, effective enablement or dependencies.",
                "Host catalogs are supplied observations, not an exhaustive live host query.",
                "No configuration, skill bodies, telemetry, network requests or persistent inventory.",
                "Headers limited to 32 KiB; YAML aliases unsupported; live filesystem changes may affect results.",
            ]}


def merge_host_catalog(report, path):
    """Only read an explicitly supplied sanitized catalog; do not probe host locators."""
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_CATALOG_BYTES + 1)
        if len(raw) > MAX_CATALOG_BYTES:
            raise MetadataError("host_catalog_too_large")
        items = json.loads(raw)
        if not isinstance(items, list):
            raise MetadataError("host_catalog_not_list")
    except (OSError, ValueError, UnicodeError) as exc:
        report["issues"].append({"path": str(path), "code": error_code(exc) if isinstance(exc, OSError)
                                  else (str(exc) if isinstance(exc, MetadataError) else "invalid_host_catalog")})
        return
    report["host_catalog"] = {"path": str(path), "entries_supplied": len(items)}
    for index, item in enumerate(items):
        required = ("name", "description", "locator", "source", "scope")
        if (not isinstance(item, dict)
                or any(not isinstance(item.get(k), str) or not item[k].strip() for k in required)
                or item.get("enabled", "unknown") not in ("enabled", "disabled", "unknown")
                or len(item["name"]) > 64 or len(item["description"]) > 1024):
            report["issues"].append({"path": str(path), "code": "invalid_host_entry", "index": index})
            continue
        locator = item["locator"]
        # Exact absolute real-path matching only; never follow catalog-supplied links.
        found = next((s for s in report["skills"] if s["path"] == locator), None)
        if found is None:
            found = {"name": item["name"], "description": item["description"], "path": locator,
                     "source": item["source"], "scope": item["scope"], "origins": [],
                     "read_status": "host_metadata_only", "disk_status": "not_checked",
                     "dependencies": "not_checked", "enabled": "unknown", "host_visible": "unknown"}
            report["skills"].append(found)
        found["origins"].append({"source": item["source"], "scope": item["scope"], "path": locator})
        if found["name"] and found["name"] != item["name"]:
            report["issues"].append({"path": locator, "code": "host_metadata_conflict"})
        old = found["enabled"]
        new = item.get("enabled", "unknown")
        # Conflicting observations must never make a disabled skill executable.
        if old != "unknown" and new != "unknown" and old != new:
            report["issues"].append({"path": locator, "code": "host_enablement_conflict"})
        found["enabled"] = "disabled" if "disabled" in (old, new) else (new if new != "unknown" else old)
        found["host_visible"] = "visible"


def finalize(report, query=None, offset=0, limit=None):
    skills = sorted(report["skills"], key=lambda s: ((s["name"] or "").casefold(), s["path"]))
    for skill in skills:
        skill["origins"] = sorted({json.dumps(o, sort_keys=True): o for o in skill["origins"]}.values(),
                                  key=lambda o: json.dumps(o, sort_keys=True))
    report["issues"] = sorted(report["issues"], key=lambda i: json.dumps(i, sort_keys=True))
    report["counts"] = {"unique_records": len(skills),
                        "readable_files": sum(s["read_status"] == "readable" for s in skills),
                        "host_visible": sum(s["host_visible"] == "visible" for s in skills),
                        "issues": len(report["issues"])}
    matched = [s for s in skills if not query or query.casefold() in
               ((s["name"] or "") + " " + (s["description"] or "")).casefold()]
    page = matched[offset:None if limit is None else offset + limit]
    report["selection"] = {"query": query, "matching_records": len(matched), "offset": offset,
                           "returned": len(page), "next_offset": offset + len(page)
                           if offset + len(page) < len(matched) else None,
                           "comparison": "literal_filter_only_not_semantic_ranking"}
    report["skills"] = page
    return report


def summary(report):
    lines = [f"SkillNav {VERSION}: {report['counts']['unique_records']} records; "
             f"{report['counts']['readable_files']} readable files; {report['counts']['issues']} issues."]
    for root in report["roots"]:
        lines.append("Root: " + json.dumps(root, ensure_ascii=False))
    lines.append("Selection: " + json.dumps(report["selection"], ensure_ascii=False))
    for skill in report["skills"]:
        lines.append(json.dumps({k: skill[k] for k in ("name", "description", "path", "source", "scope",
                           "read_status", "enabled", "host_visible", "dependencies")}, ensure_ascii=False))
    lines.extend("Issue: " + json.dumps(i, ensure_ascii=False) for i in report["issues"])
    lines.extend("Limit: " + line for line in report["limitations"])
    # JSON lines escape untrusted control characters in all variable fields.
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--root", action="append", default=[], help="Declared skill root; repeatable. Replaces defaults.")
    parser.add_argument("--include-defaults", action="store_true", help="Include standard roots with explicit roots.")
    parser.add_argument("--host-catalog", help="Explicit sanitized JSON metadata list, never a Codex config file.")
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    parser.add_argument("--query", help="Literal case-insensitive name/description filter, not semantic routing.")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-dirs", type=int, default=10000)
    parser.add_argument("--max-depth", type=int, default=32)
    parser.add_argument("--strict", action="store_true", help="Exit 1 for any reported issue; default permits partial results.")
    args = parser.parse_args(argv)
    if args.offset < 0 or (args.limit is not None and args.limit <= 0) or args.max_dirs <= 0 or args.max_depth < 0:
        parser.error("offset/depth must be nonnegative; limit/max-dirs must be positive")
    if yaml is None:
        print(json.dumps({"error": "missing_pyyaml", "action": "Use a project venv and install the skill's requirements.txt."}), file=sys.stderr)
        return 2
    roots = default_roots() if not args.root or args.include_defaults else []
    roots += [{"path": p, "source": "explicit", "scope": "declared"} for p in args.root]
    report = scan(roots, max_dirs=args.max_dirs, max_depth=args.max_depth)
    if args.host_catalog:
        merge_host_catalog(report, args.host_catalog)
    finalize(report, args.query, args.offset, args.limit)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json" else summary(report))
    return 1 if args.strict and report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
