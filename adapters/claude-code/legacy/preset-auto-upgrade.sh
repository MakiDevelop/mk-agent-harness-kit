#!/usr/bin/env bash
# mk-agentos Preset Auto-Upgrade — PostToolUse hook
# Monitors for conditions that trigger automatic preset upgrade.
# Upgrade: automatic. Downgrade: requires human approval.
#
# Triggers (from preset-rules.yaml):
#   - Same failure 2 times → standard → governed
#   - File modified 3+ times (rework signal)
#   - Multi-session handoff detected
#   - project-state has BLOCKED tasks

set -euo pipefail

# Find project
if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    PROJECT_DIR="$CLAUDE_PROJECT_DIR"
elif git rev-parse --show-toplevel &>/dev/null; then
    PROJECT_DIR=$(git rev-parse --show-toplevel)
else
    exit 0
fi

[ ! -f "$PROJECT_DIR/project-state.yaml" ] && exit 0

# Read current preset
CURRENT_PRESET=$(python3 -c "
import yaml
ps = yaml.safe_load(open('$PROJECT_DIR/project-state.yaml'))
print(ps.get('preset', 'standard'))
" 2>/dev/null || echo "standard")

# Already governed? Nothing to upgrade
[ "$CURRENT_PRESET" = "governed" ] && exit 0

SHOULD_UPGRADE=false
REASON=""

# Check 1: BLOCKED tasks exist
if python3 -c "
import yaml, sys
ps = yaml.safe_load(open('$PROJECT_DIR/project-state.yaml'))
blocked = [t for t in ps.get('tasks', []) if t.get('status') == 'BLOCKED']
sys.exit(0 if blocked else 1)
" 2>/dev/null; then
    SHOULD_UPGRADE=true
    REASON="BLOCKED task detected"
fi

# Check 2: Repeated failures in attempt-log
ATTEMPT_LOG="$PROJECT_DIR/evidence/attempt-log.jsonl"
if [ -f "$ATTEMPT_LOG" ] && [ -s "$ATTEMPT_LOG" ]; then
    FAIL_COUNT=$(grep -c '"failed"' "$ATTEMPT_LOG" 2>/dev/null || echo 0)
    if [ "$FAIL_COUNT" -ge 2 ]; then
        SHOULD_UPGRADE=true
        REASON="$FAIL_COUNT failures in attempt-log"
    fi
fi

# Check 3: High file churn in progress tracker
PROGRESS="$PROJECT_DIR/evidence/progress.json"
if [ -f "$PROGRESS" ]; then
    MAX_EDITS=$(jq '[.file_edits // {} | to_entries[] | .value] | max // 0' "$PROGRESS" 2>/dev/null || echo 0)
    if [ "$MAX_EDITS" -ge 3 ]; then
        SHOULD_UPGRADE=true
        REASON="file edited $MAX_EDITS times (rework signal)"
    fi
fi

if [ "$SHOULD_UPGRADE" = true ]; then
    if [ "$CURRENT_PRESET" = "light" ]; then
        NEW_PRESET="standard"
    else
        NEW_PRESET="governed"
    fi

    # Log the upgrade to decision-log
    DECISION_LOG="$PROJECT_DIR/evidence/decision-log.jsonl"
    mkdir -p "$PROJECT_DIR/evidence"
    echo "{\"type\":\"preset_upgrade\",\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"from\":\"$CURRENT_PRESET\",\"to\":\"$NEW_PRESET\",\"reason\":\"$REASON\",\"actor\":\"harness\"}" >> "$DECISION_LOG"

    # Update project-state.yaml preset
    python3 -c "
import yaml
ps_path = '$PROJECT_DIR/project-state.yaml'
ps = yaml.safe_load(open(ps_path))
ps['preset'] = '$NEW_PRESET'
with open(ps_path, 'w') as f:
    yaml.safe_dump(ps, f, allow_unicode=True, default_flow_style=False)
" 2>/dev/null

    # Notify via stderr (non-blocking)
    echo "[mk-agentos] ⚠️ Preset auto-upgraded: $CURRENT_PRESET → $NEW_PRESET (reason: $REASON)" >&2
fi

exit 0
