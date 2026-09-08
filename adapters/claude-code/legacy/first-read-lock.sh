#!/usr/bin/env bash
# mk-agentos First-Read Lock — PreToolUse guard
# Blocks mutation tools (Edit/Write/Bash) until Agent has Read required files.
#
# Required reads (by preset):
#   light:    no lock (warn only)
#   standard: project-state.yaml + attempt-log.jsonl
#   governed: project-state.yaml + attempt-log.jsonl + decision-log.jsonl + context-index.yaml
#
# Exit 0 = allow, Exit 2 = block

set -euo pipefail

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")

# Only check mutation tools
case "$TOOL_NAME" in
    Edit|Write) ;;
    Bash)
        # Allow read-only Bash commands
        COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")
        case "$COMMAND" in
            ls*|cat*|head*|tail*|wc*|grep*|find*|echo*|pwd*|git\ log*|git\ status*|git\ diff*)
                exit 0 ;;
        esac
        ;;
    *) exit 0 ;;
esac

# Find project root
if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    PROJECT_DIR="$CLAUDE_PROJECT_DIR"
elif git rev-parse --show-toplevel &>/dev/null; then
    PROJECT_DIR=$(git rev-parse --show-toplevel)
else
    exit 0  # Not in a project, don't lock
fi

# Only enforce if project has mk-agentos structure
[ ! -f "$PROJECT_DIR/project-state.yaml" ] && exit 0

# Determine preset
PRESET="standard"
if command -v python3 &>/dev/null; then
    PRESET=$(python3 -c "
import yaml, os
ps = yaml.safe_load(open('$PROJECT_DIR/project-state.yaml'))
print(ps.get('preset', 'standard'))
" 2>/dev/null || echo "standard")
fi

# Light preset: no lock
[ "$PRESET" = "light" ] && exit 0

# Build required reads list based on preset
REQUIRED=()
REQUIRED+=("project-state.yaml")

ATTEMPT_LOG="$PROJECT_DIR/evidence/attempt-log.jsonl"
[ -f "$ATTEMPT_LOG" ] && [ -s "$ATTEMPT_LOG" ] && REQUIRED+=("attempt-log.jsonl")

if [ "$PRESET" = "governed" ]; then
    DECISION_LOG="$PROJECT_DIR/evidence/decision-log.jsonl"
    [ -f "$DECISION_LOG" ] && [ -s "$DECISION_LOG" ] && REQUIRED+=("decision-log.jsonl")

    [ -f "$PROJECT_DIR/context-index.yaml" ] && REQUIRED+=("context-index.yaml")
fi

# Check session reads
READS_FILE="$PROJECT_DIR/evidence/.session-reads"
if [ ! -f "$READS_FILE" ]; then
    READS=""
else
    READS=$(cat "$READS_FILE" 2>/dev/null || echo "")
fi

MISSING=()
for req in "${REQUIRED[@]}"; do
    if ! echo "$READS" | grep -q "$req"; then
        MISSING+=("$req")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    MISSING_LIST=$(printf ", %s" "${MISSING[@]}")
    MISSING_LIST=${MISSING_LIST:2}
    echo "BLOCKED [First-Read Lock]: You must Read the following files before using mutation tools: ${MISSING_LIST}. This ensures you have the full picture before making changes. (mk-agentos C3, preset: $PRESET)" >&2
    exit 2
fi

exit 0
