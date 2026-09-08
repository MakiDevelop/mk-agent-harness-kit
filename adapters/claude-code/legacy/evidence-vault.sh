#!/usr/bin/env bash
# mk-agentos Evidence Vault — Global PostToolUse hook
# Appends a hash-chained JSONL record for every tool invocation.
# Writes to project evidence/ if in a git repo, otherwise ~/.claude/evidence/

set -euo pipefail

# Determine vault location: project-local if in git repo, else global
if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && [ -d "${CLAUDE_PROJECT_DIR}/evidence" ]; then
    VAULT_DIR="${CLAUDE_PROJECT_DIR}/evidence"
elif git rev-parse --show-toplevel &>/dev/null; then
    GIT_ROOT=$(git rev-parse --show-toplevel)
    VAULT_DIR="${GIT_ROOT}/evidence"
    mkdir -p "$VAULT_DIR"
else
    VAULT_DIR="${HOME}/.claude/evidence"
    mkdir -p "$VAULT_DIR"
fi

VAULT_FILE="${VAULT_DIR}/vault.jsonl"
LOCK_FILE="${VAULT_DIR}/.vault.lock"

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"' 2>/dev/null || echo "unknown")
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null || echo "unknown")
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}' 2>/dev/null || echo '{}')
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exit_code // "n/a"' 2>/dev/null || echo "n/a")
CWD=$(pwd)

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

if [ -f "$VAULT_FILE" ] && [ -s "$VAULT_FILE" ]; then
    PREV_HASH=$(tail -1 "$VAULT_FILE" | jq -r '.hash // "genesis"' 2>/dev/null || echo "genesis")
else
    PREV_HASH="genesis"
fi

RECORD_BODY=$(jq -nc \
    --arg ts "$TIMESTAMP" \
    --arg sid "$SESSION_ID" \
    --arg tool "$TOOL_NAME" \
    --argjson input "$TOOL_INPUT" \
    --arg exit "$EXIT_CODE" \
    --arg cwd "$CWD" \
    --arg prev "$PREV_HASH" \
    '{ts: $ts, session: $sid, tool: $tool, input: $input, exit_code: $exit, cwd: $cwd, prev_hash: $prev}')

HASH=$(echo -n "${RECORD_BODY}" | shasum -a 256 | cut -d' ' -f1)

FINAL_RECORD=$(echo "$RECORD_BODY" | jq -c --arg h "$HASH" '. + {hash: $h}')

(
    flock -w 5 200 2>/dev/null || true
    echo "$FINAL_RECORD" >> "$VAULT_FILE"
) 200>"$LOCK_FILE"

exit 0
