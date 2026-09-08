#!/usr/bin/env bash
# mk-agentos M3 No-Progress Detector — PostToolUse tracker
# Tracks session-scoped file modification counts, test failure hashes, and
# duplicate call hashes.
# Writes counters to progress.json alongside the evidence vault.

set -euo pipefail

# Determine tracker location (same logic as evidence-vault.sh)
if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && [ -d "${CLAUDE_PROJECT_DIR}/evidence" ]; then
    TRACKER_DIR="${CLAUDE_PROJECT_DIR}/evidence"
elif git rev-parse --show-toplevel &>/dev/null; then
    GIT_ROOT=$(git rev-parse --show-toplevel)
    TRACKER_DIR="${GIT_ROOT}/evidence"
    mkdir -p "$TRACKER_DIR"
else
    TRACKER_DIR="${HOME}/.claude/evidence"
    mkdir -p "$TRACKER_DIR"
fi

TRACKER_FILE="${TRACKER_DIR}/progress.json"
LOCK_FILE="${TRACKER_DIR}/.progress.lock"

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // .sessionId // ""' 2>/dev/null || echo "")
# Missing identity must not fall back to a shared bucket: that recreates the
# cross-session contamination this tracker is intended to prevent.
[ -z "$SESSION_ID" ] && exit 0

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // ""' 2>/dev/null || echo "")
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exit_code // "0"' 2>/dev/null || echo "0")
STDERR=$(echo "$INPUT" | jq -r '.tool_response.stderr // ""' 2>/dev/null || echo "")

# macOS ships lockf rather than flock. Re-exec this script under lockf while
# preserving the hook payload on stdin. A lock timeout skips tracking.
if [ "${M3_LOCK_HELD:-0}" != "1" ] && ! command -v flock >/dev/null 2>&1; then
    if command -v lockf >/dev/null 2>&1; then
        printf '%s' "$INPUT" \
            | M3_LOCK_HELD=1 lockf -t 5 "$LOCK_FILE" bash "$0" \
            || true
    fi
    exit 0
fi

(
    # Tracking is fail-open, but unlocked writes are forbidden. If the lock is
    # unavailable, skip this event instead of corrupting shared projection.
    if [ "${M3_LOCK_HELD:-0}" != "1" ] && ! flock -w 5 200 2>/dev/null; then
        exit 0
    fi

    # Initialization belongs inside the same lock as all later updates.
    if [ ! -f "$TRACKER_FILE" ]; then
        echo '{"schema_version":2,"sessions":{}}' > "$TRACKER_FILE"
    fi

    TMP_FILE="${TRACKER_FILE}.tmp.$$"

    # Lazily initialize this session. Legacy top-level counters are ignored.
    jq --arg sid "$SESSION_ID" \
        '.schema_version = 2
         | .sessions = (.sessions // {})
         | .sessions[$sid] = (.sessions[$sid] // {
             "file_edits": {},
             "failure_by_command": {},
             "call_hashes": {}
           })' \
        "$TRACKER_FILE" > "$TMP_FILE" \
        && mv "$TMP_FILE" "$TRACKER_FILE"

    # Track file edits (Edit/Write)
    if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" ]] && [ -n "$FILE_PATH" ]; then
        # Skip tracking for evidence/progress files themselves
        case "$FILE_PATH" in
            */evidence/*|*/progress.json|*/vault.jsonl) ;;
            *)
                CURRENT=$(jq -r --arg sid "$SESSION_ID" --arg f "$FILE_PATH" \
                    '.sessions[$sid].file_edits[$f] // 0' "$TRACKER_FILE")
                NEW_COUNT=$((CURRENT + 1))
                jq --arg sid "$SESSION_ID" --arg f "$FILE_PATH" --argjson c "$NEW_COUNT" \
                    '.sessions[$sid].file_edits[$f] = $c' \
                    "$TRACKER_FILE" > "$TMP_FILE" \
                    && mv "$TMP_FILE" "$TRACKER_FILE"
                ;;
        esac
    fi

    # Track test failures (Bash with test-like commands that fail)
    if [ "$TOOL_NAME" = "Bash" ] && [ "$EXIT_CODE" != "0" ]; then
        if echo "$COMMAND" | grep -qiE '(pytest|npm test|npm run test|jest|mocha|ruff|mypy|tsc|make test|go test|cargo test)'; then
            COMMAND_HASH=$(echo -n "$COMMAND" | shasum -a 256 | cut -d' ' -f1 | head -c 16)
            FAIL_HASH=$(echo -n "${EXIT_CODE}:${STDERR}" | shasum -a 256 | cut -d' ' -f1 | head -c 16)
            CURRENT=$(jq -r --arg sid "$SESSION_ID" --arg ch "$COMMAND_HASH" --arg fh "$FAIL_HASH" \
                '.sessions[$sid].failure_by_command[$ch].failure_hashes[$fh] // 0' \
                "$TRACKER_FILE")
            NEW_COUNT=$((CURRENT + 1))
            jq --arg sid "$SESSION_ID" --arg ch "$COMMAND_HASH" --arg fh "$FAIL_HASH" \
                --argjson c "$NEW_COUNT" --arg cmd "$COMMAND" \
                '.sessions[$sid].failure_by_command[$ch] =
                    (.sessions[$sid].failure_by_command[$ch] // {
                        "command": $cmd,
                        "failure_hashes": {}
                    })
                 | .sessions[$sid].failure_by_command[$ch].command = $cmd
                 | .sessions[$sid].failure_by_command[$ch].failure_hashes[$fh] = $c' \
                "$TRACKER_FILE" > "$TMP_FILE" && mv "$TMP_FILE" "$TRACKER_FILE"
        fi
    fi

    # Track duplicate calls only when tool_input is meaningful
    # (Grok may omit Claude-Code-shaped tool_input → empty hash would lock session)
    TOOL_INPUT_RAW=$(echo "$INPUT" | jq -c '.tool_input // empty' 2>/dev/null || echo "")
    if [ -n "$TOOL_INPUT_RAW" ] && [ "$TOOL_INPUT_RAW" != "null" ] && [ "$TOOL_INPUT_RAW" != "{}" ]; then
        CALL_HASH=$(echo -n "${TOOL_NAME}:$(echo "$INPUT" | jq -Sc '.tool_input')" | shasum -a 256 | cut -d' ' -f1 | head -c 16)
        CURRENT=$(jq -r --arg sid "$SESSION_ID" --arg h "$CALL_HASH" \
            '.sessions[$sid].call_hashes[$h] // 0' "$TRACKER_FILE")
        NEW_COUNT=$((CURRENT + 1))
        jq --arg sid "$SESSION_ID" --arg h "$CALL_HASH" --argjson c "$NEW_COUNT" \
            '.sessions[$sid].call_hashes[$h] = $c' \
            "$TRACKER_FILE" > "$TMP_FILE" \
            && mv "$TMP_FILE" "$TRACKER_FILE"
    fi

) 200>"$LOCK_FILE"

exit 0
