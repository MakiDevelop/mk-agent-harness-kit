#!/usr/bin/env bash
# Thin Claude Code adapter: decisions live in ``ack guard``, never here.
set -u
name=${1:?usage: ack-guard-hook.sh <name>}
input=$(cat)
# The guard CLI owns decisions; this adapter only forwards and translates them.
# stderr is captured separately so diagnostics reach guard-errors.log without
# ever corrupting the JSON envelope on stdout.
errfile=$(mktemp 2>/dev/null || echo /dev/null)
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
python3 - "$envelope" "$input" "$name" <<'PY'
import json, sys
try:
    item = json.loads(sys.argv[1])
except (IndexError, json.JSONDecodeError):
    print("ack guard returned invalid envelope", file=sys.stderr)
    raise SystemExit(0)
try:
    payload = json.loads(sys.argv[2])
except (IndexError, json.JSONDecodeError):
    payload = {}
event = payload.get("hook_event_name")
if not isinstance(event, str) or not event:
    name = sys.argv[3] if len(sys.argv) > 3 else ""
    event = "SessionStart" if name == "session-onboarding" else ("PostToolUse" if name in {"read-tracker", "evidence", "preset-auto-upgrade", "progress-tracker"} else "PreToolUse")
decision, reason, context = item.get("decision"), item.get("reason", ""), item.get("context")
if event == "SessionStart" and isinstance(context, str) and context:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": "[harness Onboarding]\n" + context}}, ensure_ascii=False))
if decision in {"deny", "ask"}:
    if event == "PreToolUse":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "permissionDecision": decision, "permissionDecisionReason": reason}}, ensure_ascii=False))
    else:
        print(reason, file=sys.stderr)
elif decision == "warn":
    print(reason, file=sys.stderr)
PY
