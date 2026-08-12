#!/usr/bin/env python3
"""ack_settings — validate / compile mk-agentos settings.json.

Implements packages/agent-contract-kit/docs/PROFILES.md Normalization.
No network. No home-lab assumptions.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    print("error: jsonschema required (pip install jsonschema)", file=sys.stderr)
    sys.exit(2)

KIT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = KIT_ROOT / "spec" / "settings.schema.json"

PROFILES: dict[str, dict[str, Any]] = {
    "solo": {
        "layers": {
            "prompt": {"briefing_template": "minimal", "require_goal": True},
            "context": {
                "on_session_start": ["settings-summary", "git-status"],
                "memory": {"enabled": False, "backend": "none"},
            },
            "harness": {
                "preset": "light",
                "block_force_push": True,
                "block_rm_rf": True,
                "install_hooks": False,
            },
            "loop": {
                "max_failed_attempts": 2,
                "require_system_gap_on_wall": True,
                "require_system_gap_on_wrap": False,
                "verify": {"commands": []},
            },
            "graph": {"mode": "solo", "edges": "builtin:solo"},
        },
        "human": {"require_confirm_for": ["git_push", "delete"]},
        "adapters": {"filesystem_briefing": True, "langgraph": False},
    },
    "solo-strict": {
        "layers": {
            "prompt": {"briefing_template": "default", "require_goal": True},
            "context": {
                "on_session_start": [
                    "settings-summary",
                    "git-status",
                    "project-state",
                    "open-gaps",
                ],
                "memory": {"enabled": False, "backend": "none"},
            },
            "harness": {
                "preset": "standard",
                "block_force_push": True,
                "block_rm_rf": True,
                "install_hooks": False,
            },
            "loop": {
                "max_failed_attempts": 2,
                "require_system_gap_on_wall": True,
                "require_system_gap_on_wrap": True,
                "verify": {"commands": []},
            },
            "graph": {"mode": "solo", "edges": "builtin:solo"},
        },
        "human": {"require_confirm_for": ["git_push", "delete", "deploy"]},
        "adapters": {"filesystem_briefing": True, "langgraph": False},
    },
    "dual-review": {
        "layers": {
            "prompt": {"briefing_template": "default", "require_goal": True},
            "context": {
                "on_session_start": [
                    "settings-summary",
                    "git-status",
                    "project-state",
                    "open-gaps",
                    "last-handoff",
                ],
                "memory": {"enabled": False, "backend": "none"},
            },
            "harness": {
                "preset": "standard",
                "block_force_push": True,
                "block_rm_rf": True,
                "install_hooks": False,
            },
            "loop": {
                "max_failed_attempts": 2,
                "require_system_gap_on_wall": True,
                "require_system_gap_on_wrap": True,
                "verify": {"commands": []},
            },
            "graph": {"mode": "dual-review", "edges": "builtin:dual-review"},
        },
        "human": {"require_confirm_for": ["git_push", "delete", "deploy"]},
        "adapters": {"filesystem_briefing": True, "langgraph": False},
    },
    "governed": {
        "layers": {
            "prompt": {"briefing_template": "council", "require_goal": True},
            "context": {
                "on_session_start": [
                    "settings-summary",
                    "git-status",
                    "project-state",
                    "open-gaps",
                    "last-handoff",
                ],
                "memory": {"enabled": False, "backend": "none"},
            },
            "harness": {
                "preset": "governed",
                "block_force_push": True,
                "block_rm_rf": True,
                "install_hooks": False,
            },
            "loop": {
                "max_failed_attempts": 2,
                "require_system_gap_on_wall": True,
                "require_system_gap_on_wrap": True,
                "verify": {"commands": []},
            },
            "graph": {"mode": "dual-review", "edges": "builtin:dual-review"},
        },
        "human": {
            "require_confirm_for": [
                "git_push",
                "delete",
                "deploy",
                "governance_edit",
            ]
        },
        "adapters": {"filesystem_briefing": True, "langgraph": False},
    },
}

STRICT_PROFILES = frozenset({"solo-strict", "dual-review", "governed"})


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def schema_validate(settings: dict[str, Any], schema_path: Path) -> list[str]:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for err in sorted(validator.iter_errors(settings), key=lambda e: list(e.path)):
        loc = "/" + "/".join(str(p) for p in err.absolute_path) if err.absolute_path else "/"
        errors.append(f"{loc}: {err.message}")
    return errors


def _shallow_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            merged = deepcopy(out[k])
            merged.update(v)
            out[k] = merged
        else:
            out[k] = deepcopy(v)
    return out


def compile_settings(raw: dict[str, Any]) -> dict[str, Any]:
    """PROFILES.md Normalization steps 1–7."""
    profile = raw["profile"]
    if profile not in PROFILES:
        raise ValueError(f"unknown profile: {profile}")

    base = deepcopy(PROFILES[profile])
    effective: dict[str, Any] = {
        "profile": profile,
        "project": {"root": ".", "name": None},
        "layers": deepcopy(base["layers"]),
        "human": deepcopy(base["human"]),
        "adapters": deepcopy(base["adapters"]),
    }

    # 2. project
    if "project" in raw:
        effective["project"] = {**effective["project"], **deepcopy(raw["project"])}

    # 3. top-level verify → layers.loop.verify wholesale
    if "verify" in raw:
        effective["layers"]["loop"]["verify"] = deepcopy(raw["verify"])

    # 4. top-level human
    if "human" in raw:
        if "require_confirm_for" in raw["human"]:
            effective["human"]["require_confirm_for"] = list(
                raw["human"]["require_confirm_for"]
            )

    # 5. layers.* shallow one level
    if "layers" in raw:
        for section, ov in raw["layers"].items():
            if not isinstance(ov, dict):
                effective["layers"][section] = deepcopy(ov)
                continue
            cur = effective["layers"].setdefault(section, {})
            if not isinstance(cur, dict):
                effective["layers"][section] = deepcopy(ov)
                continue
            for k, v in ov.items():
                if k == "verify" and isinstance(v, dict):
                    cur["verify"] = deepcopy(v)
                elif isinstance(v, dict) and isinstance(cur.get(k), dict):
                    cur[k] = {**cur[k], **deepcopy(v)}
                else:
                    cur[k] = deepcopy(v)

    # 6. adapters
    if "adapters" in raw:
        effective["adapters"] = {
            **effective["adapters"],
            **deepcopy(raw["adapters"]),
        }

    # 7. forced unions / invariants
    confirms = list(effective["human"].get("require_confirm_for") or [])
    if "secrets" not in confirms:
        confirms.append("secrets")
    # stable unique preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for c in confirms:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    effective["human"]["require_confirm_for"] = uniq

    mem = effective["layers"]["context"].get("memory") or {}
    if mem.get("enabled") is True and mem.get("backend") in (None, "none"):
        raise ValueError(
            "invariant: context.memory.enabled=true requires backend amh|file"
        )

    graph = effective["layers"]["graph"]
    mode = graph.get("mode")
    edges = graph.get("edges")
    if mode == "solo" and edges == "builtin:dual-review":
        raise ValueError("invariant: graph.mode=solo cannot use builtin:dual-review")
    if mode == "dual-review" and edges == "builtin:solo":
        raise ValueError(
            "invariant: graph.mode=dual-review cannot use builtin:solo"
        )
    if mode == "dual-review":
        agents = graph.get("agents") or {}
        for seat in ("executor", "reviewer"):
            val = agents.get(seat)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(
                    f"invariant: dual-review requires non-empty graph.agents.{seat}"
                )
    if mode == "custom":
        agents = graph.get("agents") or {}
        if not isinstance(agents, dict) or not agents:
            raise ValueError("invariant: custom graph requires non-empty graph.agents")
        for seat, val in agents.items():
            if not isinstance(val, str) or not val.strip():
                raise ValueError(
                    f"invariant: custom graph.agents.{seat} must be non-empty string"
                )

    if profile in STRICT_PROFILES:
        cmds = (
            effective["layers"]
            .get("loop", {})
            .get("verify", {})
            .get("commands")
            or []
        )
        if not cmds:
            raise ValueError(
                f"invariant: profile {profile!r} requires non-empty loop.verify.commands"
            )

    # drop null project.name for cleanliness
    if effective["project"].get("name") is None:
        effective["project"].pop("name", None)

    return effective


def cmd_validate(args: argparse.Namespace) -> int:
    settings_path = Path(args.settings)
    schema_path = Path(args.schema)
    raw = load_json(settings_path)
    errors = schema_validate(raw, schema_path)
    if errors:
        print("SCHEMA FAIL", settings_path)
        for e in errors:
            print(" ", e)
        return 1
    try:
        compile_settings(raw)
    except ValueError as exc:
        print("COMPILE INVARIANT FAIL", settings_path)
        print(" ", exc)
        return 1
    print("OK", settings_path)
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    settings_path = Path(args.settings)
    schema_path = Path(args.schema)
    raw = load_json(settings_path)
    errors = schema_validate(raw, schema_path)
    if errors:
        print("SCHEMA FAIL", settings_path, file=sys.stderr)
        for e in errors:
            print(" ", e, file=sys.stderr)
        return 1
    try:
        effective = compile_settings(raw)
    except ValueError as exc:
        print("COMPILE INVARIANT FAIL:", exc, file=sys.stderr)
        return 1

    text = json.dumps(effective, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print("wrote", out)
    else:
        sys.stdout.write(text)
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    settings_path = Path(args.settings)
    schema_path = Path(args.schema)
    raw = load_json(settings_path)
    errors = schema_validate(raw, schema_path)
    if errors:
        print("SCHEMA FAIL", file=sys.stderr)
        for e in errors:
            print(" ", e, file=sys.stderr)
        return 1
    try:
        eff = compile_settings(raw)
    except ValueError as exc:
        print("COMPILE INVARIANT FAIL:", exc, file=sys.stderr)
        return 1

    layers = eff["layers"]
    print(f"profile: {eff['profile']}")
    print(f"project: {eff.get('project')}")
    print("layers:")
    for name in ("prompt", "context", "harness", "loop", "graph"):
        print(f"  {name}: {json.dumps(layers.get(name), ensure_ascii=False)}")
    print(f"human: {json.dumps(eff.get('human'), ensure_ascii=False)}")
    print(f"adapters: {json.dumps(eff.get('adapters'), ensure_ascii=False)}")
    return 0


def _add_common(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--settings", required=True, help="path to settings.json")
    sp.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA),
        help="path to settings.schema.json",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ack_settings",
        description="Validate/compile mk-agentos settings.json (agent-contract-kit)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="JSON Schema + compile invariants")
    _add_common(v)
    v.set_defaults(func=cmd_validate)

    c = sub.add_parser("compile", help="emit effective settings JSON")
    _add_common(c)
    c.add_argument("-o", "--output", help="write resolved JSON to path")
    c.set_defaults(func=cmd_compile)

    s = sub.add_parser("summary", help="print layer summary")
    _add_common(s)
    s.set_defaults(func=cmd_summary)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
