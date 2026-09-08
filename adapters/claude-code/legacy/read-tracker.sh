#!/usr/bin/env bash
# mk-agentos First-Read Lock — PostToolUse Read tracker
# Records which files the Agent has Read in this session.
# Works with first-read-lock.sh to enforce onboarding.

set -euo pipefail

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")

[ "$TOOL_NAME" != "Read" ] && exit 0

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null || echo "")
[ -z "$FILE_PATH" ] && exit 0

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null || echo "unknown")

# Determine tracker location
if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && [ -d "${CLAUDE_PROJECT_DIR}/evidence" ]; then
    TRACKER_DIR="${CLAUDE_PROJECT_DIR}/evidence"
elif git rev-parse --show-toplevel &>/dev/null; then
    TRACKER_DIR="$(git rev-parse --show-toplevel)/evidence"
else
    TRACKER_DIR="${HOME}/.claude/evidence"
fi

mkdir -p "$TRACKER_DIR"
READS_FILE="${TRACKER_DIR}/.session-reads"

# Append the read path (dedup handled by the lock checker)
echo "$FILE_PATH" >> "$READS_FILE" 2>/dev/null

exit 0
