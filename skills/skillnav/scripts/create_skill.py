#!/usr/bin/env python3
"""Create and structurally validate small, local instruction skills.

This helper deliberately does not install, execute, or discover anything.  It
only consumes a bounded JSON specification and writes a new skill beneath an
already existing directory supplied by the caller.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any
from urllib.parse import unquote


MAX_SPEC_BYTES = 256 * 1024
MAX_INSTRUCTIONS_BYTES = 128 * 1024
MAX_DESCRIPTION_CHARS = 1024
MAX_NAME_CHARS = 64
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
PLACEHOLDER_RE = re.compile(r"(?im)(?:^\s*(?:TODO|FIXME|TBD)\s*:\s*(?:fill|complete|replace|insert|fix|$)|\b(?:YOUR|REPLACE|INSERT)[_\- ]+(?:TEXT|NAME|VALUE|HERE)\b|\[\s*(?:TODO|TBD|REPLACE|INSERT)[^\]]*\])")
LINK_RE = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class SkillError(ValueError):
    """A safe, user-facing validation or creation failure."""


def _unfilled(value: str) -> bool:
    return value.strip().upper() in {"TODO", "FIXME", "TBD"} or bool(PLACEHOLDER_RE.search(value))


def _regular(path: Path, label: str) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise SkillError(f"{label}_missing") from exc
    if stat.S_ISLNK(info.st_mode):
        raise SkillError(f"{label}_symlink")
    if not stat.S_ISREG(info.st_mode):
        raise SkillError(f"{label}_not_regular")
    if info.st_nlink > 1:
        raise SkillError(f"{label}_hardlink")


def _read_regular(path: Path, label: str, limit: int) -> str:
    """Read a bounded regular file without following a final symlink."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError as exc:
        raise SkillError(f"{label}_missing") from exc
    except OSError as exc:
        raise SkillError(f"{label}_unreadable") from exc
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise SkillError(f"{label}_not_regular")
        if os.fstat(fd).st_nlink > 1:
            raise SkillError(f"{label}_hardlink")
        data = bytearray()
        while len(data) <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > limit:
            raise SkillError(f"{label}_too_large")
        try:
            return bytes(data).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SkillError(f"{label}_invalid_utf8") from exc
    finally:
        os.close(fd)


def _validate_text(value: str, label: str) -> None:
    if CONTROL_RE.search(value):
        raise SkillError(f"{label}_control_character")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SkillError(f"{label}_invalid_utf8") from exc


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SkillError("duplicate_spec_key")
        result[key] = value
    return result


def _directory(path: Path, label: str, *, existing: bool = True) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        if existing:
            raise SkillError(f"{label}_missing") from exc
        return
    if stat.S_ISLNK(info.st_mode):
        raise SkillError(f"{label}_symlink")
    if not stat.S_ISDIR(info.st_mode):
        raise SkillError(f"{label}_not_directory")


def _assert_no_symlink_components(path: Path, stop: Path) -> None:
    """Reject symlink components between an explicit root and a child."""
    try:
        relative = path.relative_to(stop)
    except ValueError as exc:
        raise SkillError("path_outside_output_root") from exc
    current = stop
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise SkillError("path_contains_symlink")


def _assert_no_symlink_ancestors(path: Path) -> None:
    """Reject symlink path components from the filesystem anchor onward."""
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor or os.sep)
    for part in absolute.parts[1:] if absolute.anchor else absolute.parts:
        current /= part
        try:
            if current.is_symlink():
                raise SkillError("path_contains_symlink")
        except OSError as exc:
            raise SkillError("path_unreadable") from exc


def _load_spec(path: Path) -> dict[str, Any]:
    _assert_no_symlink_ancestors(path)
    _regular(path, "spec")
    try:
        data = json.loads(_read_regular(path, "spec", MAX_SPEC_BYTES), object_pairs_hook=_json_object)
    except SkillError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SkillError("invalid_spec_json") from exc
    if not isinstance(data, dict):
        raise SkillError("spec_not_object")
    allowed = {"name", "description", "instructions", "allow_implicit_invocation"}
    unknown = set(data) - allowed
    if unknown:
        raise SkillError("unknown_spec_fields")
    for key in ("name", "description", "instructions"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise SkillError(f"invalid_{key}")
        _validate_text(data[key], key)
    name = data["name"]
    if len(name) > MAX_NAME_CHARS or not NAME_RE.fullmatch(name) or "--" in name:
        raise SkillError("invalid_name")
    description = data["description"]
    if len(description) > MAX_DESCRIPTION_CHARS:
        raise SkillError("description_too_large")
    instructions = data["instructions"]
    _validate_text(instructions, "instructions")
    if len(instructions.encode("utf-8")) > MAX_INSTRUCTIONS_BYTES:
        raise SkillError("instructions_too_large")
    if _unfilled(instructions) or _unfilled(description):
        raise SkillError("unfilled_placeholder")
    policy = data.get("allow_implicit_invocation", True)
    if not isinstance(policy, bool):
        raise SkillError("invalid_allow_implicit_invocation")
    return {"name": name, "description": description, "instructions": instructions,
            "allow_implicit_invocation": policy}


def _quoted(value: str) -> str:
    # JSON string syntax is a safe, YAML-compatible double-quoted scalar.
    return json.dumps(value, ensure_ascii=False)


def _skill_markdown(spec: dict[str, Any]) -> str:
    return "---\nname: " + _quoted(spec["name"]) + "\ndescription: " + _quoted(spec["description"]) + "\n---\n" + spec["instructions"]


def _openai_yaml(spec: dict[str, Any]) -> str:
    summary = f"{spec['name']}: {spec['description']}"
    if len(summary) < 25:
        summary = f"{summary} workflow instructions"
    if len(summary) < 25:
        summary = f"Skill for {spec['name']} task: {spec['description']}"
    summary = summary[:64]
    return ("interface:\n"
            f"  display_name: {_quoted(spec['name'])}\n"
            f"  short_description: {_quoted(summary)}\n"
            f"  default_prompt: {_quoted('Use $' + spec['name'] + ' to complete the requested task and verify the result.')}\n"
            "policy:\n"
            f"  allow_implicit_invocation: {'true' if spec['allow_implicit_invocation'] else 'false'}\n")


def _safe_child(root: Path, name: str) -> Path:
    _directory(root, "output_root")
    _assert_no_symlink_ancestors(root)
    root = root.absolute()
    _assert_no_symlink_components(root, root)
    destination = root / name
    if destination.exists() or destination.is_symlink():
        raise SkillError("destination_exists")
    _assert_no_symlink_components(destination, root)
    return destination


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        raise SkillError("missing_frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise SkillError("unclosed_frontmatter")
    try:
        metadata = _yaml_load(text[4:end + 1])
    except Exception as exc:
        raise SkillError("invalid_frontmatter") from exc
    if not isinstance(metadata, dict) or set(metadata) != {"name", "description"}:
        raise SkillError("invalid_frontmatter_fields")
    return metadata, text[end + 5:]


def _yaml_load(text: str) -> Any:
    """Load the tiny YAML files without aliases or duplicate mapping keys."""
    import yaml

    class UniqueSafeLoader(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            result = {}
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, str) or key in result:
                    raise SkillError("duplicate_yaml_key")
                result[key] = self.construct_object(value_node, deep=deep)
            return result

    if any(isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken))
           for token in yaml.scan(text)):
        raise SkillError("yaml_alias_not_supported")
    try:
        return yaml.load(text, Loader=UniqueSafeLoader)
    except (yaml.YAMLError, RecursionError) as exc:
        raise SkillError("invalid_yaml") from exc


def _validate_links(skill_dir: Path, markdown: str) -> None:
    for raw in LINK_RE.findall(markdown):
        raw = raw.strip()
        if raw.startswith("<"):
            close = raw.find(">")
            if close < 0:
                raise SkillError("unsupported_markdown_link")
            target = raw[1:close]
            if raw[close + 1:].strip() and not raw[close + 1:].lstrip().startswith(('"', "'", "(")):
                raise SkillError("unsupported_markdown_link")
        else:
            target = raw.split(None, 1)[0]
        target = unquote(target)
        if not target or target.startswith(("#", "/", "\\")):
            if target.startswith(("/", "\\")):
                raise SkillError("markdown_link_absolute")
            continue
        if re.match(r"^[A-Za-z]:", target):
            raise SkillError("markdown_link_absolute")
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
            continue  # External URI; this helper is not a complete Markdown parser.
        if "?" in target:
            raise SkillError("unsupported_markdown_link")
        target = target.split("#", 1)[0]
        current = skill_dir.absolute()
        for part in target.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                if current == skill_dir.absolute():
                    raise SkillError("markdown_link_escapes_skill")
                current = current.parent
                continue
            if "\\" in part:
                raise SkillError("unsupported_markdown_link")
            current /= part
            try:
                if current.is_symlink():
                    raise SkillError("markdown_link_symlink")
            except OSError as exc:
                raise SkillError("markdown_link_unreadable") from exc
        target_path = current
        if not target_path.is_relative_to(skill_dir.absolute()):
            raise SkillError("markdown_link_escapes_skill")
        try:
            _regular(target_path, "markdown_link")
        except SkillError as exc:
            if str(exc) == "markdown_link_missing":
                raise SkillError("markdown_link_missing") from exc
            if str(exc) == "markdown_link_hardlink":
                raise SkillError("markdown_link_hardlink") from exc
            raise SkillError("markdown_link_not_regular") from exc


def validate_skill(skill_path: Path) -> dict[str, Any]:
    skill_path = skill_path.absolute()
    _directory(skill_path, "skill")
    _assert_no_symlink_ancestors(skill_path)
    md = skill_path / "SKILL.md"
    agents = skill_path / "agents"
    yaml_path = agents / "openai.yaml"
    _regular(md, "skill_markdown")
    _directory(agents, "agents")
    _regular(yaml_path, "openai_yaml")
    text = _read_regular(md, "skill_markdown", MAX_SPEC_BYTES)
    metadata, body = _parse_frontmatter(text)
    if (not isinstance(metadata.get("name"), str) or len(metadata["name"]) > MAX_NAME_CHARS
            or metadata["name"] != skill_path.name or not NAME_RE.fullmatch(metadata["name"])
            or "--" in metadata["name"]):
        raise SkillError("invalid_skill_name")
    if not isinstance(metadata.get("description"), str) or not metadata["description"].strip() or len(metadata["description"]) > MAX_DESCRIPTION_CHARS:
        raise SkillError("invalid_skill_description")
    _validate_text(metadata["description"], "skill_description")
    if not body.strip():
        raise SkillError("empty_instructions")
    _validate_text(body, "instructions")
    if len(body.encode("utf-8")) > MAX_INSTRUCTIONS_BYTES:
        raise SkillError("instructions_too_large")
    if _unfilled(body) or _unfilled(metadata["description"]):
        raise SkillError("unfilled_placeholder")
    _validate_links(skill_path, text)
    try:
        config = _yaml_load(_read_regular(yaml_path, "openai_yaml", MAX_SPEC_BYTES))
    except Exception as exc:
        raise SkillError("invalid_openai_yaml") from exc
    if (not isinstance(config, dict) or set(config) != {"interface", "policy"}
            or not isinstance(config.get("interface"), dict)
            or set(config["interface"]) != {"display_name", "short_description", "default_prompt"}
            or not all(isinstance(config["interface"].get(key), str) and config["interface"][key].strip()
                       for key in ("display_name", "short_description", "default_prompt"))
            or not 25 <= len(config["interface"]["short_description"]) <= 64
            or not isinstance(config.get("policy"), dict)
            or set(config["policy"]) != {"allow_implicit_invocation"}):
        raise SkillError("invalid_openai_yaml")
    for key in ("display_name", "short_description", "default_prompt"):
        _validate_text(config["interface"][key], f"openai_{key}")
    policy = config["policy"].get("allow_implicit_invocation")
    if not isinstance(policy, bool):
        raise SkillError("invalid_policy")
    return {"valid": True, "path": str(skill_path), "name": metadata["name"],
            "allow_implicit_invocation": policy,
            "limitations": ["Structural validation does not prove behavior or user acceptance.",
                            "Validation handles supported inline local Markdown links only; it is not a full Markdown parser and does not verify remote URIs.",
                            "Validation and creation assume the supplied root remains stable during the operation."]}


def create_skill(spec_path: Path, output_root: Path) -> dict[str, Any]:
    spec = _load_spec(spec_path.absolute())
    destination = _safe_child(output_root.absolute(), spec["name"])
    # Reserve the final directory before writing. mkdir is exclusive and thus
    # cannot replace a directory created by a concurrent caller.
    try:
        destination.mkdir()
    except FileExistsError as exc:
        raise SkillError("destination_exists") from exc
    created_files: list[tuple[Path, int]] = []
    success = False
    try:
        agents = destination / "agents"
        agents.mkdir()
        for path, content in ((destination / "SKILL.md", _skill_markdown(spec)),
                              (agents / "openai.yaml", _openai_yaml(spec))):
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
            created_files.append((path, os.fstat(fd).st_ino))
            try:
                encoded = content.encode("utf-8")
                position = 0
                while position < len(encoded):
                    position += os.write(fd, encoded[position:])
            finally:
                os.close(fd)
        validate_skill(destination)
        success = True
    finally:
        if not success:
            for path, inode in created_files:
                try:
                    current = path.lstat()
                    if (stat.S_ISREG(current.st_mode) and current.st_ino == inode
                            and not stat.S_ISLNK(current.st_mode)):
                        path.unlink()
                except OSError:
                    pass
            try:
                (destination / "agents").rmdir()
            except OSError:
                pass
            try:
                destination.rmdir()
            except OSError:
                pass
    return validate_skill(destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or validate a bounded instruction skill")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--spec", type=Path, required=True)
    create.add_argument("--output-root", type=Path, required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--skill", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = create_skill(args.spec, args.output_root) if args.command == "create" else validate_skill(args.skill)
    except (OSError, SkillError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
