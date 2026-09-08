#!/usr/bin/env bash
# mk-agentos M2 State Machine Validator — PreToolUse hook
# Intercepts Edit/Write to project-state.yaml and enforces transition rules.
#
# Exit 0 = allow, Exit 2 = block (with reason on stderr)

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // ""' 2>/dev/null || echo "")

# Only intercept writes to project-state files
case "$FILE_PATH" in
    */project-state.yaml|*/project-state.yml|*/project-state.json) ;;
    *) exit 0 ;;
esac

# New file creation is allowed
[ ! -f "$FILE_PATH" ] && exit 0

# --- Edit tool: grep-based partial validation ---
if [ "$TOOL_NAME" = "Edit" ]; then
    OLD_STRING=$(echo "$INPUT" | jq -r '.tool_input.old_string // ""' 2>/dev/null || echo "")
    NEW_STRING=$(echo "$INPUT" | jq -r '.tool_input.new_string // ""' 2>/dev/null || echo "")

    # Detect status change TO VERIFIED
    if echo "$NEW_STRING" | grep -qiE 'status:\s*VERIFIED' && \
       ! echo "$OLD_STRING" | grep -qiE 'status:\s*VERIFIED'; then
        if ! echo "$NEW_STRING" | grep -qE 'verifier_id:\s*\S'; then
            echo "BLOCKED: Cannot push to VERIFIED without verifier_id (mk-agentos M2)" >&2
            exit 2
        fi
        if ! echo "$NEW_STRING" | grep -qE 'evidence_id:\s*\S'; then
            echo "BLOCKED: Cannot push to VERIFIED without evidence_id (mk-agentos M2)" >&2
            exit 2
        fi
    fi

    # Detect status change TO ACCEPTED
    if echo "$NEW_STRING" | grep -qiE 'status:\s*ACCEPTED' && \
       ! echo "$OLD_STRING" | grep -qiE 'status:\s*ACCEPTED'; then
        if ! echo "$NEW_STRING" | grep -qE 'accepted_by:\s*\S'; then
            echo "BLOCKED: Cannot push to ACCEPTED without accepted_by (mk-agentos M2)" >&2
            exit 2
        fi
    fi

    # Block tech_verified flip without evidence
    if echo "$NEW_STRING" | grep -qE 'tech_verified:\s*true' && \
       ! echo "$OLD_STRING" | grep -qE 'tech_verified:\s*true'; then
        if ! echo "$NEW_STRING" | grep -qE 'evidence_id:\s*\S'; then
            echo "BLOCKED: Cannot set tech_verified: true without evidence_id (mk-agentos M2)" >&2
            exit 2
        fi
    fi

    # Block business_aligned flip without sign-off
    if echo "$NEW_STRING" | grep -qE 'business_aligned:\s*true' && \
       ! echo "$OLD_STRING" | grep -qE 'business_aligned:\s*true'; then
        if ! echo "$NEW_STRING" | grep -qE 'aligned_by:\s*\S'; then
            echo "BLOCKED: Cannot set business_aligned: true without aligned_by (mk-agentos M2)" >&2
            exit 2
        fi
    fi

    exit 0
fi

# --- Write tool: full YAML validation ---
if [ "$TOOL_NAME" = "Write" ]; then
    CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // ""' 2>/dev/null || echo "")
    [ -z "$CONTENT" ] && exit 0

    python3 -c "
import yaml, sys

try:
    data = yaml.safe_load(sys.stdin)
except:
    sys.exit(0)

if not isinstance(data, dict) or 'tasks' not in data:
    sys.exit(0)

errors = []
for task in data.get('tasks', []):
    status = task.get('status', '')
    tid = task.get('id', '?')

    if status == 'VERIFIED':
        if not task.get('verifier_id'):
            errors.append(f'Task {tid}: VERIFIED requires verifier_id')
        if not task.get('evidence_id') and not any(
            ac.get('evidence_id') for ac in task.get('acceptance_criteria', [])
        ):
            errors.append(f'Task {tid}: VERIFIED requires evidence_id')
        if task.get('tech_verified') is not True:
            errors.append(f'Task {tid}: VERIFIED requires tech_verified: true')
        if task.get('business_aligned') is not True:
            errors.append(f'Task {tid}: VERIFIED requires business_aligned: true')

    if status == 'ACCEPTED':
        if not task.get('accepted_by'):
            errors.append(f'Task {tid}: ACCEPTED requires accepted_by')

if errors:
    print('BLOCKED by mk-agentos M2 State Validator:', file=sys.stderr)
    for e in errors:
        print(f'  - {e}', file=sys.stderr)
    sys.exit(2)
" <<< "$CONTENT"
    exit $?
fi

exit 0
