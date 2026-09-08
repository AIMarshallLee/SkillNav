#!/usr/bin/env python3
"""Opt-in local routing state. JSON input, bounded fields, no network or model calls.

Authorization receipts are HOST ATTESTATIONS, not cryptographic proof of a human.
The host must check the actual user message; an arbitrary local caller can forge them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import tempfile
import time
from urllib.parse import quote
import uuid

SCHEMA_VERSION = 1
MAX_OUTCOMES = 200
OBSERVATION_DAYS = 30
FORMATS = {"markdown", "docx", "pdf", "slides", "text", "json", "csv", "html"}
TOKEN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}\Z")
FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")
WRITE_ACTIONS = {"enable", "preference", "outcome", "feedback", "controls", "forget", "clear-project", "clear-all"}
FIELDS = {
    "status": set(),
    "enable": {"authorization"},
    "context": {"project", "task_type", "environment", "candidates", "overrides"},
    "preference": {"scope", "project", "task_type", "key", "value", "authorization"},
    "outcome": {"task_id", "step_id", "project", "task_type", "skill_id", "fingerprint", "host", "environment",
                "stage", "check", "blocker", "key", "value"},
    "feedback": {"task_id", "step_id", "project", "feedback", "authorization"},
    "controls": {"learning", "reading", "authorization"},
    "forget": {"preference_id", "authorization"},
    "clear-project": {"project", "authorization"},
    "clear-all": {"authorization"},
}


class StateError(ValueError):
    pass


def default_path():
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/SkillNav/state.sqlite3"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "SkillNav/state.sqlite3"
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "skillnav/state.sqlite3"


def local_id(value):
    """Local identity, NOT anonymization or encryption; no automatic project inference."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def skill_id(source, locator):
    return local_id(json.dumps([source, locator], ensure_ascii=False, separators=(",", ":")))


def token(value, field):
    if not isinstance(value, str) or not TOKEN.fullmatch(value):
        raise StateError("invalid_" + field)
    return value


def rule(key, value):
    if key == "output_format" and value in FORMATS:
        return
    if key in ("prefer_skill", "exclude_skill") and isinstance(value, str) and FINGERPRINT.fullmatch(value):
        return
    if key == "confirmation" and value in ("ask_before_external", "ask_before_write"):
        return
    raise StateError("invalid_rule")


def authorize(receipt, action, task_id=None):
    if (not isinstance(receipt, dict)
            or set(receipt) - {"origin", "message_ref", "verified_by_host", "action", "task_id"}
            or receipt.get("origin") != "direct_user"
            or receipt.get("verified_by_host") is not True
            or receipt.get("action") != action
            or (task_id and receipt.get("task_id") != task_id)):
        raise StateError("unverified_user_authorization")
    token(receipt.get("message_ref"), "message_ref")
    return receipt["message_ref"]


def fallback(error):
    return {"ok": False, "memory": "unavailable", "saved": False, "error": error,
            "fallback": "route_without_memory", "defaults": {}, "preferences": [], "outcomes": []}


class Store:
    def __init__(self, path=None, *, test_mode=False, clock=time.time, timeout=2.0):
        self.path = Path(path or default_path()).absolute()
        self.test_mode = test_mode
        self.clock = clock
        self.timeout = timeout

    def _location(self):
        real = self.path.resolve()
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise StateError("unsafe_state_symlink")
        if self.test_mode:
            roots = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve()}
            if not any(real.is_relative_to(p) for p in roots):
                raise StateError("test_state_must_be_in_temporary_directory")
        elif real != default_path().resolve():
            raise StateError("use_private_default_state_path")
        if not self.test_mode:
            for parent in real.parents:
                if (parent / ".git").exists() or parent.name == "skills":
                    raise StateError("state_must_be_outside_repositories_and_skill_roots")
        if self.path.exists() and not stat.S_ISREG(self.path.stat().st_mode):
            raise StateError("state_not_regular_file")
        if os.name == "posix" and self.path.exists():
            for p in (self.path, self.path.parent):
                info = p.stat()
                if info.st_uid != os.getuid() or info.st_mode & 0o077:
                    raise StateError("state_permissions_not_private")

    def _connect(self, write=False):
        self._location()
        mode = "rw" if write else "ro"
        conn = sqlite3.connect("file:" + quote(str(self.path)) + "?mode=" + mode,
                               uri=True, timeout=self.timeout, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = %d" % int(self.timeout * 1000))
        return conn

    def _settings(self, conn):
        row = conn.execute("SELECT * FROM settings WHERE singleton=1").fetchone()
        if row is None or row["schema_version"] != SCHEMA_VERSION:
            raise StateError("unsupported_schema_preserved")
        return dict(row)

    def _initialize(self):
        self._location()
        self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if os.name == "posix" and self.path.parent.stat().st_mode & 0o077:
            raise StateError("state_permissions_not_private")
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return  # A concurrent initialization must be rechecked transactionally.
        os.close(fd)
        conn = self._connect(write=True)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("CREATE TABLE settings (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                         "schema_version INTEGER NOT NULL, learning INTEGER NOT NULL, reading INTEGER NOT NULL, "
                         "revision INTEGER NOT NULL)")
            conn.execute("INSERT INTO settings VALUES(1, ?, 0, 0, 0)", (SCHEMA_VERSION,))
            conn.execute("""CREATE TABLE preferences (
                id TEXT PRIMARY KEY, scope TEXT NOT NULL, project TEXT NOT NULL, task_type TEXT NOT NULL,
                key TEXT NOT NULL, value TEXT NOT NULL, source TEXT NOT NULL, event_refs TEXT NOT NULL,
                active INTEGER NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
                last_used_at REAL NOT NULL, skill_id TEXT, fingerprint TEXT, environment TEXT)""")
            conn.execute("""CREATE TABLE outcomes (
                task_id TEXT NOT NULL, step_id TEXT NOT NULL, project TEXT NOT NULL, task_type TEXT NOT NULL,
                skill_id TEXT NOT NULL, fingerprint TEXT NOT NULL, host TEXT NOT NULL,
                environment TEXT NOT NULL, stage TEXT NOT NULL, stages TEXT NOT NULL,
                check_result TEXT NOT NULL, blocker TEXT NOT NULL, feedback TEXT NOT NULL,
                feedback_ref TEXT, feedback_at REAL, key TEXT, value TEXT,
                created_at REAL NOT NULL, updated_at REAL NOT NULL, PRIMARY KEY(task_id,step_id))""")
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def dispatch(self, action, payload, *, no_memory=False):
        if no_memory:
            return {"ok": True, "memory": "bypassed", "saved": False, "defaults": {},
                    "preferences": [], "outcomes": []}
        try:
            return self._dispatch(action, payload)
        except StateError as exc:
            return fallback(str(exc))
        except (sqlite3.Error, OSError, RuntimeError):
            # Do not echo database pages, user values, SQL or exception text.
            return fallback("state_io_or_database_error")
        except (ValueError, TypeError, KeyError):
            return fallback("invalid_request")

    def _dispatch(self, action, payload):
        if action not in FIELDS or not isinstance(payload, dict):
            raise StateError("invalid_action")
        allowed = FIELDS[action] | ({"expected_revision"} if action in WRITE_ACTIONS else set())
        if set(payload) - allowed:
            raise StateError("unknown_fields")
        self._location()
        if action in WRITE_ACTIONS:
            revision = payload.get("expected_revision")
            if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
                raise StateError("expected_revision_required")
        if action == "enable":
            authorize(payload.get("authorization"), action)
            if not self.path.exists():
                if revision != 0:
                    raise StateError("revision_conflict")
                self._initialize()
        if not self.path.exists():
            if action in WRITE_ACTIONS:
                raise StateError("memory_consent_required")
            return {"ok": True, "memory": "off", "saved": False, "exists": False,
                    "path": str(self.path), "revision": 0, "defaults": {}, "preferences": [], "outcomes": []}
        conn = self._connect(write=action in WRITE_ACTIONS)
        try:
            conn.execute("BEGIN IMMEDIATE" if action in WRITE_ACTIONS else "BEGIN")
            settings = self._settings(conn)
            if action in WRITE_ACTIONS:
                if payload["expected_revision"] != settings["revision"]:
                    raise StateError("revision_conflict")
                if action in ("preference", "outcome", "feedback") and not settings["learning"]:
                    raise StateError("learning_disabled")
            if action == "status":
                result = {"path": str(self.path), "exists": True, "revision": settings["revision"],
                          "learning": bool(settings["learning"]), "reading": bool(settings["reading"]),
                          "schema_version": settings["schema_version"],
                          "preference_count": conn.execute("SELECT COUNT(*) FROM preferences").fetchone()[0],
                          "outcome_count": conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]}
            elif action == "context":
                result = self._context(conn, settings, payload)
            else:
                result = self._write(conn, action, payload)
                conn.execute("UPDATE settings SET revision=revision+1 WHERE singleton=1")
                result["revision"] = settings["revision"] + 1
            conn.execute("COMMIT")
            return dict(result, ok=True, memory="available", saved=action in WRITE_ACTIONS)
        finally:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            conn.close()

    def _write(self, conn, action, p):
        now = self.clock()
        if action == "enable":
            conn.execute("UPDATE settings SET learning=1, reading=1 WHERE singleton=1")
            return {"learning": True, "reading": True}
        if action == "controls":
            authorize(p.get("authorization"), action)
            if not any(k in p for k in ("learning", "reading")):
                raise StateError("control_required")
            for key in ("learning", "reading"):
                if key in p:
                    if not isinstance(p[key], bool):
                        raise StateError("boolean_control_required")
                    conn.execute("UPDATE settings SET " + key + "=? WHERE singleton=1", (int(p[key]),))
            return {"controls_changed": True}
        if action == "preference":
            ref = authorize(p.get("authorization"), action)
            scope = p.get("scope")
            project = p.get("project")
            if scope == "personal" and project is None:
                project = ""
            elif scope == "project":
                token(project, "project")
                if project.startswith("session:"):
                    raise StateError("session_scope_is_ephemeral")
            else:
                raise StateError("invalid_scope")
            task_type = token(p.get("task_type"), "task_type")
            key, value = p.get("key"), p.get("value")
            rule(key, value)
            previous = conn.execute("SELECT * FROM preferences WHERE scope=? AND project=? AND task_type=? "
                                    "AND key=? AND source='explicit'" + (" AND value=?" if key == "exclude_skill" else ""),
                                    (scope, project, task_type, key, value) if key == "exclude_skill"
                                    else (scope, project, task_type, key)).fetchone()
            pref_id = previous["id"] if previous else str(uuid.uuid4())
            created = previous["created_at"] if previous else now
            # Remove the old learning association while preserving objective execution facts.
            if key == "exclude_skill":
                conn.execute("DELETE FROM preferences WHERE scope=? AND project=? AND task_type=? AND key=? AND value=?",
                             (scope, project, task_type, key, value))
            elif scope == "project":
                conn.execute("UPDATE outcomes SET key=NULL,value=NULL WHERE project=? AND task_type=? AND key=?", (project, task_type, key))
                conn.execute("DELETE FROM preferences WHERE project=? AND task_type=? AND key=?", (project, task_type, key))
            else:
                conn.execute("DELETE FROM preferences WHERE scope='personal' AND task_type=? AND key=?", (task_type, key))
            conn.execute("INSERT INTO preferences VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (pref_id, scope, project, task_type, key, value, "explicit", json.dumps([ref]),
                          1, created, now, now, None, None, None))
            return {"preference_id": pref_id}
        if action == "outcome":
            p = dict(p, step_id=p.get("step_id", "main"))
            for field in ("task_id", "step_id", "project", "task_type", "host", "environment"):
                token(p.get(field), field)
            for field in ("skill_id", "fingerprint"):
                if p.get(field) != "unknown" and (not isinstance(p.get(field), str) or not FINGERPRINT.fullmatch(p[field])):
                    raise StateError("invalid_" + field)
            if p.get("stage") not in ("recommended", "loaded", "executed", "blocked", "failed"):
                raise StateError("invalid_stage")
            if p.get("check") not in ("unknown", "passed", "failed", "partial", "not_run"):
                raise StateError("invalid_check")
            if p.get("blocker") not in ("none", "network", "permission", "dependency", "input", "unknown"):
                raise StateError("invalid_blocker")
            if p["check"] in ("passed", "partial") and p["stage"] != "executed":
                raise StateError("check_requires_execution")
            if p.get("key") is not None:
                rule(p["key"], p.get("value"))
            elif p.get("value") is not None:
                raise StateError("key_required")
            attribution = conn.execute("SELECT project,task_type FROM outcomes WHERE task_id=? LIMIT 1", (p["task_id"],)).fetchone()
            if attribution and (attribution["project"], attribution["task_type"]) != (p["project"], p["task_type"]):
                raise StateError("task_attribution_conflict")
            old = conn.execute("SELECT * FROM outcomes WHERE task_id=? AND step_id=?", (p["task_id"], p["step_id"])).fetchone()
            immutable = ("project", "task_type", "skill_id", "fingerprint", "host", "environment", "key", "value")
            if old and any(old[k] != p.get(k) for k in immutable):
                raise StateError("task_attribution_conflict")
            stages = json.loads(old["stages"]) if old else []
            if p["stage"] not in stages:
                stages.append(p["stage"])
            unchanged = old and (old["stage"], old["check_result"], old["blocker"]) == (p["stage"], p["check"], p["blocker"])
            conn.execute("INSERT OR REPLACE INTO outcomes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (p["task_id"], p["step_id"], p["project"], p["task_type"], p["skill_id"], p["fingerprint"],
                          p["host"], p["environment"], p["stage"], json.dumps(stages), p["check"], p["blocker"],
                          old["feedback"] if unchanged else "unknown", old["feedback_ref"] if unchanged else None,
                          old["feedback_at"] if unchanged else None, p.get("key"), p.get("value"),
                          old["created_at"] if old else now, now))
            if p["stage"] == "executed":
                conn.execute("UPDATE preferences SET last_used_at=? WHERE source='observed' AND project=? "
                             "AND task_type=? AND skill_id=? AND fingerprint=? AND environment=? AND key=? AND value=?",
                             (now, p["project"], p["task_type"], p["skill_id"], p["fingerprint"], p["environment"],
                              p.get("key"), p.get("value")))
            self._rebuild(conn, now)
            return {"task_id": p["task_id"], "step_id": p["step_id"], "feedback": old["feedback"] if unchanged else "unknown"}
        if action == "feedback":
            task = token(p.get("task_id"), "task_id")
            step = token(p.get("step_id", "main"), "step_id")
            project = token(p.get("project"), "project")
            ref = authorize(p.get("authorization"), action, task)
            if p.get("feedback") not in ("accepted", "rejected", "unknown"):
                raise StateError("invalid_feedback")
            old = conn.execute("SELECT * FROM outcomes WHERE task_id=? AND step_id=? AND project=?", (task, step, project)).fetchone()
            if old is None:
                raise StateError("feedback_task_not_found")
            conn.execute("UPDATE outcomes SET feedback=?,feedback_ref=?,feedback_at=?,updated_at=? WHERE task_id=? AND step_id=?",
                         (p["feedback"], ref, now, now, task, step))
            self._rebuild(conn, now)
            return {"task_id": task, "step_id": step, "feedback": p["feedback"]}
        authorize(p.get("authorization"), action)
        if action == "forget":
            pref_id = token(p.get("preference_id"), "preference_id")
            row = conn.execute("SELECT * FROM preferences WHERE id=?", (pref_id,)).fetchone()
            if row:
                # Remove all evidence that can reconstruct this scoped rule, not just the current aggregate.
                if row["key"] == "exclude_skill":
                    if row["scope"] == "personal":
                        conn.execute("DELETE FROM outcomes WHERE task_type=? AND key=? AND value=?",
                                     (row["task_type"], row["key"], row["value"]))
                    else:
                        conn.execute("DELETE FROM outcomes WHERE project=? AND task_type=? AND key=? AND value=?",
                                     (row["project"], row["task_type"], row["key"], row["value"]))
                    conn.execute("DELETE FROM preferences WHERE source='observed' AND task_type=? AND key=? AND value=? "
                                 "AND (?='personal' OR project=?)", (row["task_type"], row["key"], row["value"], row["scope"], row["project"]))
                elif row["scope"] == "personal":
                    conn.execute("DELETE FROM outcomes WHERE task_type=? AND key=?", (row["task_type"], row["key"]))
                    conn.execute("DELETE FROM preferences WHERE source='observed' AND task_type=? AND key=?",
                                 (row["task_type"], row["key"]))
                else:
                    conn.execute("DELETE FROM outcomes WHERE project=? AND task_type=? AND key=?",
                                 (row["project"], row["task_type"], row["key"]))
                    conn.execute("DELETE FROM preferences WHERE project=? AND task_type=? AND key=?",
                                 (row["project"], row["task_type"], row["key"]))
                conn.execute("DELETE FROM preferences WHERE id=?", (pref_id,))
            return {"forgotten": bool(row)}
        if action == "clear-project":
            project = token(p.get("project"), "project")
            conn.execute("DELETE FROM outcomes WHERE project=?", (project,))
            conn.execute("DELETE FROM preferences WHERE project=?", (project,))
            return {"cleared_project": project}
        if action == "clear-all":
            conn.execute("DELETE FROM outcomes")
            conn.execute("DELETE FROM preferences")
            conn.execute("UPDATE settings SET learning=0,reading=0 WHERE singleton=1")
            return {"cleared": True, "learning": False, "reading": False}
        raise StateError("invalid_action")

    def _rebuild(self, conn, now):
        conn.execute("DELETE FROM outcomes WHERE (task_id,step_id) NOT IN "
                     "(SELECT task_id,step_id FROM outcomes ORDER BY created_at DESC,task_id DESC,step_id DESC LIMIT ?)", (MAX_OUTCOMES,))
        previous = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM preferences WHERE source='observed'")}
        conn.execute("DELETE FROM preferences WHERE source='observed'")
        groups = {}
        for row in conn.execute("SELECT * FROM outcomes WHERE feedback='accepted' AND stage='executed' "
                                "AND check_result='passed' AND blocker='none' AND key IS NOT NULL "
                                "AND skill_id!='unknown' AND fingerprint!='unknown'"):
            group = tuple(row[k] for k in ("project", "task_type", "key", "value", "skill_id", "fingerprint", "environment"))
            groups.setdefault(group, []).append(dict(row))
        for group, rows in groups.items():
            if len({r["task_id"] for r in rows}) < 3:
                continue
            project, task_type, key, value, skill, fingerprint, environment = group
            if project.startswith("session:"):
                continue
            pref_id = local_id(json.dumps(group))
            latest = max(r["feedback_at"] for r in rows)
            old = previous.get(pref_id, {})
            conn.execute("INSERT INTO preferences VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (pref_id, "project", project, task_type, key, value, "observed",
                          json.dumps(sorted(r["task_id"] + "/" + r["step_id"] for r in rows)), 1, old.get("created_at", now),
                          latest, max(old.get("last_used_at", 0), latest), skill, fingerprint, environment))

    def _context(self, conn, settings, p):
        if not settings["reading"]:
            return {"defaults": {}, "preferences": [], "outcomes": [], "reading": False}
        project = token(p.get("project"), "project")
        task_type = token(p.get("task_type"), "task_type")
        environment = token(p.get("environment"), "environment")
        candidates = p.get("candidates")
        feasible = None
        if candidates is not None:
            if not isinstance(candidates, list) or len(candidates) > 1000:
                raise StateError("invalid_candidates")
            feasible = set()
            for item in candidates:
                if (not isinstance(item, dict) or set(item) != {"skill_id", "fingerprint", "enabled", "available"}
                        or not isinstance(item["enabled"], bool) or not isinstance(item["available"], bool)
                        or not FINGERPRINT.fullmatch(item["skill_id"]) or not FINGERPRINT.fullmatch(item["fingerprint"])):
                    raise StateError("invalid_candidate")
                if item["enabled"] and item["available"]:
                    feasible.add((item["skill_id"], item["fingerprint"]))
        preferences = []
        for row in conn.execute("SELECT * FROM preferences WHERE active=1 AND task_type=? "
                                "AND (scope='personal' OR (scope='project' AND project=?))", (task_type, project)):
            row = dict(row)
            if row["source"] == "observed":
                if row["environment"] != environment or self.clock() - row["last_used_at"] > OBSERVATION_DAYS * 86400:
                    continue
                if feasible is not None and (row["skill_id"], row["fingerprint"]) not in feasible:
                    continue
            if row["key"] == "prefer_skill" and feasible is not None and not any(s == row["value"] for s, _ in feasible):
                continue
            row["event_refs"] = json.loads(row["event_refs"])
            preferences.append(row)
        preferences.sort(key=lambda r: (r["source"] == "explicit", r["scope"] == "project", r["updated_at"], r["id"]))
        overrides = p.get("overrides", {})
        if not isinstance(overrides, dict):
            raise StateError("invalid_overrides")
        for key, value in overrides.items():
            rule(key, value)
        excluded = {r["value"] for r in preferences if r["key"] == "exclude_skill"}
        if "exclude_skill" in overrides:
            excluded.add(overrides["exclude_skill"])
        if "prefer_skill" in overrides:
            excluded.discard(overrides["prefer_skill"])
        if feasible is not None:
            feasible = {(s, f) for s, f in feasible if s not in excluded}
        preferences = [r for r in preferences if not (
            (r["source"] == "observed" and r["skill_id"] in excluded)
            or (r["key"] == "prefer_skill" and r["value"] in excluded))]
        defaults = {row["key"]: row["value"] for row in preferences if row["key"] != "exclude_skill"}
        defaults.update(overrides)
        defaults.pop("exclude_skill", None)
        outcomes = []
        for row in conn.execute("SELECT * FROM outcomes WHERE project=? AND task_type=? AND environment=? "
                                "ORDER BY updated_at DESC,task_id", (project, task_type, environment)):
            row = dict(row)
            if row["skill_id"] in excluded:
                continue
            if feasible is not None and (row["skill_id"], row["fingerprint"]) not in feasible:
                continue
            row["check"] = row.pop("check_result")
            row["stages"] = json.loads(row["stages"])
            outcomes.append(row)
        return {"defaults": defaults, "preferences": preferences, "outcomes": outcomes,
                "excluded_skill_ids": sorted(excluded),
                "revision": settings["revision"], "reading": True,
                "limits": "Hints only: host must enforce current instructions, project rules, safety and candidate availability."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=sorted(FIELDS))
    parser.add_argument("--db", type=Path, help="Override only with --test-mode in an OS temporary directory.")
    parser.add_argument("--test-mode", action="store_true")
    parser.add_argument("--no-memory", action="store_true", help="Do not read or write state, even for mutation commands.")
    args = parser.parse_args(argv)
    if args.no_memory:
        payload = {}
    elif args.action == "status":
        payload = {}
    else:
        try:
            raw = sys.stdin.buffer.read(65537)
            if len(raw) > 65536:
                raise ValueError()
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            print(json.dumps(fallback("invalid_or_oversized_json")))
            return 2
    result = Store(args.db, test_mode=args.test_mode).dispatch(args.action, payload, no_memory=args.no_memory)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
