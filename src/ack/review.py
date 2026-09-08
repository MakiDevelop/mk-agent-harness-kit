#!/usr/bin/env python3
"""ack_review — filesystem dual-review adapter (M4).

Edge: executor → reviewer via briefing.md / answer.md on disk.
Enforces Edge Contract fields: TASK, CONTEXT, CONSTRAINTS, VERIFY, paths_or_diff_stat.
Reviewer answer is untrusted; accept-gate requires VERDICT PASS + evidence.

No network. No home-lab assumptions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import settings as ack_settings

STATE_DIR = ".mk-agentos"
REVIEWS_DIR = "reviews"
BRIEFING_NAME = "briefing.md"
ANSWER_NAME = "answer.md"
META_NAME = "meta.json"

REQUIRED_BRIEFING_HEADERS = (
    "TASK",
    "CONTEXT",
    "CONSTRAINTS",
    "VERIFY",
    "PATHS_OR_DIFF_STAT",
)

# Accept common aliases in markdown headings
HEADER_ALIASES = {
    "TASK": {"TASK"},
    "CONTEXT": {"CONTEXT"},
    "CONSTRAINTS": {"CONSTRAINTS", "CONSTRAINT"},
    "VERIFY": {"VERIFY", "VERIFICATION", "ACCEPTANCE"},
    "PATHS_OR_DIFF_STAT": {
        "PATHS_OR_DIFF_STAT",
        "PATHS",
        "DIFF",
        "DIFF_STAT",
        "PATHS_OR_DIFF",
        "FILES",
    },
}

VERDICT_RE = re.compile(
    r"(?im)^\s*(?:\*\*)?VERDICT(?:\*\*)?\s*[:：]\s*(PASS|FAIL|PASS_WITH_NITS)\s*$"
)
EVIDENCE_RE = re.compile(
    r"(?im)(^\s*#+\s*EVIDENCE\b|^\s*EVIDENCE\s*[:：]|\bevidence\s*[:：]|"
    r"\b(diff|test|log|path)\b\s*[=:：])"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_effective(settings: Path | None, resolved: Path | None) -> dict[str, Any]:
    if resolved:
        data = json.loads(Path(resolved).read_text(encoding="utf-8"))
        if "layers" not in data:
            raise SystemExit(f"resolved missing layers: {resolved}")
        return data
    if not settings:
        raise SystemExit("need --settings or --resolved")
    raw = ack_settings.load_json(Path(settings))
    schema = Path(os.environ.get("ACK_SETTINGS_SCHEMA", str(ack_settings.DEFAULT_SCHEMA)))
    errs = ack_settings.schema_validate(raw, schema)
    if errs:
        print("SCHEMA FAIL", file=sys.stderr)
        for e in errs:
            print(" ", e, file=sys.stderr)
        raise SystemExit(1)
    try:
        return ack_settings.compile_settings(raw)
    except ValueError as exc:
        print("COMPILE INVARIANT FAIL:", exc, file=sys.stderr)
        raise SystemExit(1) from exc


def project_root(effective: dict[str, Any], cwd: Path) -> Path:
    root = (effective.get("project") or {}).get("root") or "."
    p = Path(root)
    if not p.is_absolute():
        p = (cwd / p).resolve()
    return p


def graph_cfg(effective: dict[str, Any]) -> dict[str, Any]:
    return (effective.get("layers") or {}).get("graph") or {}


def require_dual_review(effective: dict[str, Any]) -> None:
    mode = graph_cfg(effective).get("mode")
    if mode not in ("dual-review", "custom"):
        raise SystemExit(
            f"REFUSED: graph.mode={mode!r} is not dual-review/custom. "
            "Set profile dual-review|governed or layers.graph.mode."
        )
    agents = graph_cfg(effective).get("agents") or {}
    if mode == "dual-review":
        if not agents.get("executor") or not agents.get("reviewer"):
            raise SystemExit(
                "REFUSED: dual-review requires graph.agents.executor and reviewer"
            )


def reviews_root(project: Path) -> Path:
    return project / STATE_DIR / REVIEWS_DIR


def session_dir(project: Path, session_id: str) -> Path:
    return reviews_root(project) / session_id


def current_pointer(project: Path) -> Path:
    return reviews_root(project) / "current.json"


def load_current(project: Path) -> dict[str, Any] | None:
    p = current_pointer(project)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def set_current(project: Path, session_id: str) -> None:
    reviews_root(project).mkdir(parents=True, exist_ok=True)
    current_pointer(project).write_text(
        json.dumps({"session_id": session_id, "updated_at": _utc_now()}, indent=2)
        + "\n",
        encoding="utf-8",
    )


def resolve_session(project: Path, session_id: str | None) -> tuple[str, Path]:
    if session_id:
        return session_id, session_dir(project, session_id)
    cur = load_current(project)
    if not cur or not cur.get("session_id"):
        raise SystemExit("no active review session; run: ack_review init")
    sid = str(cur["session_id"])
    return sid, session_dir(project, sid)


def parse_md_headers(text: str) -> dict[str, str]:
    """Map uppercase header name -> body text until next heading."""
    lines = text.splitlines()
    headers: dict[str, list[str]] = {}
    current: str | None = None
    heading_re = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
    alt_re = re.compile(r"^\s{0,3}([A-Za-z][A-Za-z0-9_ /-]+)\s*:\s*$")

    def norm(h: str) -> str:
        h = h.strip().strip("*").strip()
        h = re.sub(r"\s+", "_", h.upper())
        h = h.replace("-", "_")
        return h

    for line in lines:
        m = heading_re.match(line)
        if m:
            current = norm(m.group(1))
            headers.setdefault(current, [])
            continue
        m2 = alt_re.match(line)
        if m2 and len(m2.group(1)) < 40:
            current = norm(m2.group(1))
            headers.setdefault(current, [])
            continue
        if current is not None:
            headers[current].append(line)
    return {k: "\n".join(v).strip() for k, v in headers.items()}


def find_section(headers: dict[str, str], logical: str) -> str | None:
    aliases = HEADER_ALIASES[logical]
    for key, body in headers.items():
        key_n = key.replace("/", "_")
        if key_n in aliases or key in aliases:
            return body
        for a in aliases:
            if key_n == a or key_n.endswith("_" + a) or a in key_n.split("_"):
                # careful: only exact alias membership
                pass
        if key_n in aliases:
            return body
    # exact alias match only
    for a in aliases:
        if a in headers and headers[a].strip():
            return headers[a]
    for key, body in headers.items():
        if key in aliases and body.strip():
            return body
    return None


def check_briefing_text(text: str) -> list[str]:
    headers = parse_md_headers(text)
    errors: list[str] = []
    for logical in REQUIRED_BRIEFING_HEADERS:
        body = None
        for key, val in headers.items():
            kn = key.upper().replace("-", "_").replace(" ", "_")
            if kn in HEADER_ALIASES[logical] or any(
                kn == a or kn.endswith("_" + a) for a in HEADER_ALIASES[logical]
            ):
                # prefer exact
                if kn in HEADER_ALIASES[logical]:
                    body = val
                    break
        if body is None:
            for a in HEADER_ALIASES[logical]:
                for key, val in headers.items():
                    kn = key.upper().replace("-", "_").replace(" ", "_")
                    if kn == a:
                        body = val
                        break
                if body is not None:
                    break
        if body is None or not str(body).strip():
            errors.append(f"missing or empty section: {logical}")
        elif len(str(body).strip()) < 3:
            errors.append(f"section too short: {logical}")
    # reject unfilled scaffold from init
    placeholders = (
        r"\(What should be implemented",
        r"\(Allowed context:",
        r"\(What reviewer/executor must NOT do",
        r"\(How to know it's done",
        r"\(Paste `git diff --stat`",
        r"\(Paste git diff",
    )
    for pat in placeholders:
        if re.search(pat, text):
            errors.append("briefing still contains template placeholder text")
            break
    return errors


def check_answer_text(text: str) -> list[str]:
    errors: list[str] = []
    m = VERDICT_RE.search(text)
    if not m:
        errors.append("missing VERDICT: PASS|FAIL|PASS_WITH_NITS line")
    if not EVIDENCE_RE.search(text):
        errors.append(
            "missing evidence pointer (## EVIDENCE / evidence: / diff|test|log|path)"
        )
    # untrusted: must not claim done for executor without path-like tokens when PASS
    if m and m.group(1).upper() in ("PASS", "PASS_WITH_NITS"):
        if not re.search(r"(\.py|\.ts|\.js|\.go|\.rs|\.md|/|diff|test)", text, re.I):
            errors.append("PASS verdict without file/diff/test-like evidence tokens")
    return errors


def briefing_template(agents: dict[str, str], session_id: str) -> str:
    ex = agents.get("executor", "executor")
    rev = agents.get("reviewer", "reviewer")
    return f"""# Dual-review briefing

session: {session_id}
executor: {ex}
reviewer: {rev}
created: {_utc_now()}

> Fill every section. Reviewer must not expand implementation scope.
> Answer is untrusted input for the executor.

## TASK

(What should be implemented / reviewed — one concrete goal)

## CONTEXT

(Allowed context: key paths, constraints of the problem, links to specs)

## CONSTRAINTS

(What reviewer/executor must NOT do — scope, paths, no drive-by refactors)

## VERIFY

(How to know it's done — commands, acceptance checks)

## PATHS_OR_DIFF_STAT

(Paste `git diff --stat` and/or key file paths under review)

"""


def cmd_init(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    effective = load_effective(
        Path(args.settings) if args.settings else None,
        Path(args.resolved) if args.resolved else None,
    )
    require_dual_review(effective)
    root = project_root(effective, cwd)
    agents = graph_cfg(effective).get("agents") or {}
    sid = args.session or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sdir = session_dir(root, sid)
    if sdir.exists() and not args.force:
        print(f"session exists: {sdir} (use --force)", file=sys.stderr)
        return 1
    sdir.mkdir(parents=True, exist_ok=True)
    briefing = sdir / BRIEFING_NAME
    if not briefing.exists() or args.force:
        briefing.write_text(briefing_template(agents, sid), encoding="utf-8")
    meta = {
        "session_id": sid,
        "created_at": _utc_now(),
        "agents": agents,
        "edge": "executor-to-reviewer",
        "transport": "filesystem",
        "status": "briefing_draft",
    }
    (sdir / META_NAME).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    set_current(root, sid)
    print("session:", sid)
    print("dir:", sdir)
    print("briefing:", briefing)
    print("next: fill briefing sections, then: ack_review check-briefing")
    return 0


def cmd_check_briefing(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    effective = load_effective(
        Path(args.settings) if args.settings else None,
        Path(args.resolved) if args.resolved else None,
    )
    require_dual_review(effective)
    root = project_root(effective, cwd)
    sid, sdir = resolve_session(root, args.session)
    path = sdir / BRIEFING_NAME
    if not path.is_file():
        print("missing briefing:", path, file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    errors = check_briefing_text(text)
    if errors:
        print("BRIEFING FAIL", path)
        for e in errors:
            print(" ", e)
        return 1
    print("BRIEFING OK", path)
    _update_meta(sdir, status="briefing_ready")
    return 0


def cmd_check_answer(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    effective = load_effective(
        Path(args.settings) if args.settings else None,
        Path(args.resolved) if args.resolved else None,
    )
    require_dual_review(effective)
    root = project_root(effective, cwd)
    sid, sdir = resolve_session(root, args.session)
    path = sdir / ANSWER_NAME
    if not path.is_file():
        print("missing answer:", path, file=sys.stderr)
        print("reviewer must write", ANSWER_NAME, file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    errors = check_answer_text(text)
    if errors:
        print("ANSWER FAIL", path)
        for e in errors:
            print(" ", e)
        return 1
    m = VERDICT_RE.search(text)
    verdict = m.group(1).upper() if m else "?"
    print("ANSWER OK", path, "VERDICT:", verdict)
    _update_meta(sdir, status=f"answer_{verdict.lower()}")
    return 0


def cmd_handoff_gate(args: argparse.Namespace) -> int:
    """Executor → reviewer: briefing OK (+ optional loop verify)."""
    cwd = Path.cwd()
    effective = load_effective(
        Path(args.settings) if args.settings else None,
        Path(args.resolved) if args.resolved else None,
    )
    require_dual_review(effective)
    root = project_root(effective, cwd)
    sid, sdir = resolve_session(root, args.session)

    # briefing
    bpath = sdir / BRIEFING_NAME
    if not bpath.is_file():
        print("HANDOFF CLOSED: missing briefing", file=sys.stderr)
        return 1
    berr = check_briefing_text(bpath.read_text(encoding="utf-8"))
    if berr:
        print("HANDOFF CLOSED: briefing incomplete", file=sys.stderr)
        for e in berr:
            print(" ", e, file=sys.stderr)
        return 1

    if not args.skip_loop_verify:
        loop_args = ["done-gate"]
        if args.settings:
            loop_args += ["--settings", args.settings]
        else:
            loop_args += ["--resolved", args.resolved]
        proc = subprocess.run(
            [sys.executable, "-m", "ack.cli", "loop", *loop_args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )
        print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        if proc.returncode != 0:
            print("HANDOFF CLOSED: loop done-gate not green", file=sys.stderr)
            return proc.returncode or 1

    agents = graph_cfg(effective).get("agents") or {}
    print("HANDOFF OPEN → reviewer")
    print(f"session: {sid}")
    print(f"briefing: {bpath}")
    print(f"reviewer seat: {agents.get('reviewer')}")
    print(f"reviewer writes: {sdir / ANSWER_NAME}")
    print("NOTE: answer is untrusted; executor must digest after review")
    _update_meta(
        sdir,
        status="awaiting_review",
        handoff_opened_at=_utc_now(),
        handoff_opened=True,
    )
    return 0


def cmd_accept_gate(args: argparse.Namespace) -> int:
    """Final accept: requires handoff + reviewer VERDICT PASS (not self-accept)."""
    cwd = Path.cwd()
    effective = load_effective(
        Path(args.settings) if args.settings else None,
        Path(args.resolved) if args.resolved else None,
    )
    require_dual_review(effective)
    root = project_root(effective, cwd)
    sid, sdir = resolve_session(root, args.session)

    meta: dict[str, Any] = {}
    meta_path = sdir / META_NAME
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}
    if not meta.get("handoff_opened"):
        print(
            "ACCEPT CLOSED: handoff-gate not completed (no self-accept / no skip handoff)",
            file=sys.stderr,
        )
        return 1

    bpath = sdir / BRIEFING_NAME
    apath = sdir / ANSWER_NAME
    if not bpath.is_file():
        print("ACCEPT CLOSED: missing briefing", file=sys.stderr)
        return 1
    if not apath.is_file():
        print(
            "ACCEPT CLOSED: missing reviewer answer (no self-accept)",
            file=sys.stderr,
        )
        return 1
    berr = check_briefing_text(bpath.read_text(encoding="utf-8"))
    if berr:
        print("ACCEPT CLOSED: briefing invalid", file=sys.stderr)
        for e in berr:
            print(" ", e, file=sys.stderr)
        return 1
    atext = apath.read_text(encoding="utf-8")
    aerr = check_answer_text(atext)
    if aerr:
        print("ACCEPT CLOSED: answer invalid", file=sys.stderr)
        for e in aerr:
            print(" ", e, file=sys.stderr)
        return 1
    m = VERDICT_RE.search(atext)
    verdict = m.group(1).upper() if m else ""
    if verdict == "FAIL":
        print("ACCEPT CLOSED: reviewer VERDICT FAIL — fix and re-review")
        _update_meta(sdir, status="answer_fail")
        return 1
    if verdict not in ("PASS", "PASS_WITH_NITS"):
        print("ACCEPT CLOSED: unknown verdict", file=sys.stderr)
        return 1

    print("ACCEPT OPEN")
    print(f"session: {sid}")
    print(f"reviewer_verdict: {verdict}")
    print("executor may merge/ship only within original CONSTRAINTS")
    _update_meta(sdir, status=f"accepted_{verdict.lower()}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    effective = load_effective(
        Path(args.settings) if args.settings else None,
        Path(args.resolved) if args.resolved else None,
    )
    root = project_root(effective, cwd)
    g = graph_cfg(effective)
    print(f"project_root: {root}")
    print(f"graph.mode: {g.get('mode')}")
    print(f"graph.agents: {g.get('agents')}")
    cur = load_current(root)
    print(f"current_session: {(cur or {}).get('session_id')}")
    if cur and cur.get("session_id"):
        sdir = session_dir(root, str(cur["session_id"]))
        print(f"session_dir: {sdir}")
        print(f"briefing: {(sdir / BRIEFING_NAME).is_file()}")
        print(f"answer: {(sdir / ANSWER_NAME).is_file()}")
        meta_p = sdir / META_NAME
        if meta_p.is_file():
            print(f"meta: {meta_p.read_text(encoding='utf-8').strip()}")
    return 0


def _update_meta(sdir: Path, **fields: Any) -> None:
    path = sdir / META_NAME
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data.update(fields)
    data["updated_at"] = _utc_now()
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _add_src(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--settings")
    g.add_argument("--resolved")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ack_review",
        description="Filesystem dual-review edge (briefing.md ↔ answer.md)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    i = sub.add_parser("init", help="create review session + briefing template")
    _add_src(i)
    i.add_argument("--session", help="session id (default: UTC timestamp)")
    i.add_argument("--force", action="store_true")
    i.set_defaults(func=cmd_init)

    cb = sub.add_parser("check-briefing", help="validate briefing edge contract sections")
    _add_src(cb)
    cb.add_argument("--session")
    cb.set_defaults(func=cmd_check_briefing)

    ca = sub.add_parser("check-answer", help="validate reviewer answer")
    _add_src(ca)
    ca.add_argument("--session")
    ca.set_defaults(func=cmd_check_answer)

    h = sub.add_parser(
        "handoff-gate",
        help="open handoff to reviewer if briefing (+ loop verify) OK",
    )
    _add_src(h)
    h.add_argument("--session")
    h.add_argument(
        "--skip-loop-verify",
        action="store_true",
        help="skip ack_loop done-gate (not recommended)",
    )
    h.set_defaults(func=cmd_handoff_gate)

    a = sub.add_parser(
        "accept-gate",
        help="accept only with reviewer VERDICT PASS (no self-accept)",
    )
    _add_src(a)
    a.add_argument("--session")
    a.set_defaults(func=cmd_accept_gate)

    s = sub.add_parser("status", help="show dual-review session state")
    _add_src(s)
    s.set_defaults(func=cmd_status)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
