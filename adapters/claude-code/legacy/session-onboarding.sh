#!/usr/bin/env bash
# mk-agentos Session Onboarding — SessionStart hook
# Injects context capsule (project state + failures + blockers) into every session.
# Agent reads ground truth directly, not Chair's summary.
#
# Budget: ≤8KB. Priority: blockers > failures > tasks > decisions > paths.
# Handoff.md is NEVER injected — agent reads it LAST if needed.

set -euo pipefail

# Find project root
if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    PROJECT_DIR="$CLAUDE_PROJECT_DIR"
elif git rev-parse --show-toplevel &>/dev/null; then
    PROJECT_DIR=$(git rev-parse --show-toplevel)
else
    PROJECT_DIR="$(pwd)"
fi

# Only inject if project has mk-agentos structure
[ ! -f "$PROJECT_DIR/project-state.yaml" ] && exit 0

# Reset session reads (First-Read Lock starts fresh each session)
EVIDENCE_DIR="$PROJECT_DIR/evidence"
[ -d "$EVIDENCE_DIR" ] && echo "" > "$EVIDENCE_DIR/.session-reads" 2>/dev/null

# Build capsule
CAPSULE=""

# 1. Project state summary
if command -v python3 &>/dev/null; then
    STATE_SUMMARY=$(python3 -c "
import yaml, json, os
ps_path = '$PROJECT_DIR/project-state.yaml'
if os.path.exists(ps_path):
    ps = yaml.safe_load(open(ps_path))
    project = ps.get('project', '?')
    preset = ps.get('preset', '?')
    tasks = ps.get('tasks', [])
    task_summary = []
    for t in tasks:
        task_summary.append(f\"  {t.get('id','?')}: {t.get('status','?')} — {t.get('name','?')}\")
    blockers = [t for t in tasks if t.get('status') == 'BLOCKED']
    print(f'Project: {project} | Preset: {preset} | Tasks: {len(tasks)} | Blocked: {len(blockers)}')
    if task_summary:
        print('Tasks:')
        print(chr(10).join(task_summary[:10]))
    if blockers:
        print('⚠️ BLOCKED:')
        for b in blockers:
            print(f\"  {b.get('id')}: {b.get('blocked_reason', '?')}\")
" 2>/dev/null)
    [ -n "$STATE_SUMMARY" ] && CAPSULE="${CAPSULE}${STATE_SUMMARY}\n"
fi

# 2. Recent failures
ATTEMPT_LOG="$PROJECT_DIR/evidence/attempt-log.jsonl"
if [ -f "$ATTEMPT_LOG" ] && [ -s "$ATTEMPT_LOG" ]; then
    FAIL_COUNT=$(grep -c '"failed"' "$ATTEMPT_LOG" 2>/dev/null || echo 0)
    if [ "$FAIL_COUNT" -gt 0 ]; then
        RECENT_FAILS=$(tail -5 "$ATTEMPT_LOG" | jq -r 'select(.status=="failed") | "  \(.ts // "?"): \(.description // .attempt // "?")"' 2>/dev/null)
        CAPSULE="${CAPSULE}⚠️ Recent failures ($FAIL_COUNT total):\n${RECENT_FAILS}\n"
    fi
fi

# 3. Open challenges
DECISION_LOG="$PROJECT_DIR/evidence/decision-log.jsonl"
if [ -f "$DECISION_LOG" ] && [ -s "$DECISION_LOG" ]; then
    OPEN=$(grep '"open"' "$DECISION_LOG" 2>/dev/null | grep '"challenge"' | tail -3 | jq -r '"  \(.challenger // "?"): \(.description // "?")"' 2>/dev/null)
    [ -n "$OPEN" ] && CAPSULE="${CAPSULE}⚠️ Open challenges:\n${OPEN}\n"
fi

# 4. Required reads
CAPSULE="${CAPSULE}Required reads (mutation locked until read):\n"
CAPSULE="${CAPSULE}  1. project-state.yaml\n"
CAPSULE="${CAPSULE}  2. evidence/attempt-log.jsonl\n"
[ -f "$PROJECT_DIR/evidence/decision-log.jsonl" ] && CAPSULE="${CAPSULE}  3. evidence/decision-log.jsonl\n"
[ -f "$PROJECT_DIR/context-index.yaml" ] && CAPSULE="${CAPSULE}  4. context-index.yaml\n"
CAPSULE="${CAPSULE}  ⚠️ evidence/handoff.md — read LAST (may have optimistic bias)\n"

# 5. Profile (from profile-detector if available)
DETECTOR="${HOME}/GitHub/mk-agentos/bin/profile-detector.sh"
if [ -x "$DETECTOR" ]; then
    PROFILE=$("$DETECTOR" 2>/dev/null || echo "unknown")
    CAPSULE="${CAPSULE}Profile: ${PROFILE}\n"
fi

# Output as additionalContext
if [ -n "$CAPSULE" ]; then
    # Escape for JSON
    ESCAPED=$(echo -e "$CAPSULE" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null | sed 's/^"//;s/"$//')
    echo "{\"hookSpecificOutput\":{\"additionalContext\":\"[mk-agentos Onboarding]\\n${ESCAPED}\"}}"
fi

exit 0
