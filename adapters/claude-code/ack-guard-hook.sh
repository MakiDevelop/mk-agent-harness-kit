#!/usr/bin/env bash
# Thin Claude Code adapter: decisions live in ``ack guard``, never here.
set -u
name=${1:?usage: ack-guard-hook.sh <name>}
input=$(cat)
errfile=$(mktemp 2>/dev/null || echo /dev/null)
# stderr is kept apart from the envelope so a stray warning cannot corrupt the JSON.
if ! envelope=$(printf '%s' "$input" | ack guard "$name" --stdin-json 2>"$errfile"); then
  evidence=${ACK_EVIDENCE_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}/.mk-agentos/evidence}
  mkdir -p "$evidence" 2>/dev/null || true
  { printf '[%s] guard=%s exit=fail\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$name"; cat "$errfile" 2>/dev/null; printf '%s\n' "$envelope"; } >> "$evidence/guard-errors.log" 2>/dev/null || true
  cat "$errfile" >&2 2>/dev/null || true
  printf '%s\n' "$envelope" >&2
  rm -f "$errfile" 2>/dev/null || true
  exit 0
fi
rm -f "$errfile" 2>/dev/null || true
python3 - "$envelope" <<'PY'
import json, sys
try:
    item = json.loads(sys.argv[1])
except (IndexError, json.JSONDecodeError):
    print("ack guard returned invalid envelope", file=sys.stderr)
    raise SystemExit(0)
decision, reason = item.get("decision"), item.get("reason", "")
if decision in {"deny", "ask"}:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision, "permissionDecisionReason": reason}}, ensure_ascii=False))
elif decision == "warn":
    print(reason, file=sys.stderr)
PY
