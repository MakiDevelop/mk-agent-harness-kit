#!/usr/bin/env bash
# mk-agentos M3 No-Progress Detector — PreToolUse guard
# Reads session-scoped progress.json counters and blocks if thresholds exceeded.
#
# Thresholds (Council 3 決議):
#   - Same file edited ≥ N times → BLOCKED（N 見下方，原為 5）
#   - Same test failure hash ≥ 2 times → WARNING (state-delta-aware gate pending)
#   - Identical tool+args hash ≥ 3 times → deny that call
#
# 2026-08-09 Maki 授權調高 file-edit 門檻：
#   原值 5 在「一份文件分段寫入」與「一支模組重構寫到一半」兩種正常情況下
#   都會誤擋，且第二種會把檔案留在無法編譯的中間狀態（實例：AMP repo 的
#   event_store.py 缺一行模組常數，54 passed / 7 NameError）。
#   誤擋的代價高於漏擋——它逼停的是正在進展的工作，不是迴圈。
#   改為可用環境變數覆寫，預設 block 12 / warn 6。
#   Check 2（相同 tool+args hash ≥ 3）維持不變——那才是真迴圈的訊號。
#
# Exit 0 = allow, Exit 2 = block

set -euo pipefail

FILE_EDIT_BLOCK_THRESHOLD="${MK_NO_PROGRESS_EDIT_BLOCK:-12}"
FILE_EDIT_WARN_THRESHOLD="${MK_NO_PROGRESS_EDIT_WARN:-6}"

# Determine tracker location
if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && [ -d "${CLAUDE_PROJECT_DIR}/evidence" ]; then
    TRACKER_DIR="${CLAUDE_PROJECT_DIR}/evidence"
elif git rev-parse --show-toplevel &>/dev/null; then
    GIT_ROOT=$(git rev-parse --show-toplevel)
    TRACKER_DIR="${GIT_ROOT}/evidence"
else
    TRACKER_DIR="${HOME}/.claude/evidence"
fi

TRACKER_FILE="${TRACKER_DIR}/progress.json"

# No tracker = no history = allow
[ ! -f "$TRACKER_FILE" ] && exit 0

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // .sessionId // ""' 2>/dev/null || echo "")
# Without a reliable session identity, fail open instead of sharing counters
# across unrelated sessions.
[ -z "$SESSION_ID" ] && exit 0

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // ""' 2>/dev/null || echo "")

# --- Check 1: File edit count ---
if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" ]] && [ -n "$FILE_PATH" ]; then
    case "$FILE_PATH" in
        */evidence/*|*/progress.json|*/vault.jsonl) ;;
        *)
            COUNT=$(jq -r --arg sid "$SESSION_ID" --arg f "$FILE_PATH" \
                '.sessions[$sid].file_edits[$f] // 0' \
                "$TRACKER_FILE" 2>/dev/null || echo 0)
            if [ "$COUNT" -ge "$FILE_EDIT_BLOCK_THRESHOLD" ]; then
                echo "BLOCKED: File '$FILE_PATH' has been modified $COUNT times this session. Likely stuck — stop and report to Maki. (mk-agentos M3, threshold: $FILE_EDIT_BLOCK_THRESHOLD)" >&2
                exit 2
            elif [ "$COUNT" -ge "$FILE_EDIT_WARN_THRESHOLD" ]; then
                # Warning only (logged to stderr but not blocking)
                echo "WARNING: File '$FILE_PATH' modified $COUNT times. Consider whether you're making progress. (mk-agentos M3)" >&2
            fi
            ;;
    esac
fi

# --- Check 2: Duplicate call hash ---
# Skip when tool_input empty (Grok may not send Claude-Code-shaped payloads)
TOOL_INPUT_RAW=$(echo "$INPUT" | jq -c '.tool_input // empty' 2>/dev/null || echo "")
if [ -n "$TOOL_INPUT_RAW" ] && [ "$TOOL_INPUT_RAW" != "null" ] && [ "$TOOL_INPUT_RAW" != "{}" ]; then
    CALL_HASH=$(echo -n "${TOOL_NAME}:$(echo "$INPUT" | jq -Sc '.tool_input')" | shasum -a 256 | cut -d' ' -f1 | head -c 16)
    CALL_COUNT=$(jq -r --arg sid "$SESSION_ID" --arg h "$CALL_HASH" \
        '.sessions[$sid].call_hashes[$h] // 0' \
        "$TRACKER_FILE" 2>/dev/null || echo 0)
    if [ "$CALL_COUNT" -ge 3 ]; then
        echo "BLOCKED: Identical tool call executed $CALL_COUNT times. You are in a loop — change approach or report BLOCKED. (mk-agentos M3, threshold: 3)" >&2
        exit 2
    fi
fi

# --- Check 3: Test failure repetition ---
if [ "$TOOL_NAME" = "Bash" ]; then
    COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")
    if echo "$COMMAND" | grep -qiE '(pytest|npm test|npm run test|jest|mocha|ruff|mypy|tsc|make test|go test|cargo test)'; then
        COMMAND_HASH=$(echo -n "$COMMAND" | shasum -a 256 | cut -d' ' -f1 | head -c 16)
        # Only failures for this session and exact command may block a retry.
        MAX_FAIL=$(jq --arg sid "$SESSION_ID" --arg ch "$COMMAND_HASH" \
            '[.sessions[$sid].failure_by_command[$ch].failure_hashes // {}
              | to_entries[] | .value] | max // 0' \
            "$TRACKER_FILE" 2>/dev/null || echo 0)
        if [ "$MAX_FAIL" -ge 2 ]; then
            FAIL_CMD=$(jq -r --arg sid "$SESSION_ID" --arg ch "$COMMAND_HASH" \
                '.sessions[$sid].failure_by_command[$ch].command // "unknown"' \
                "$TRACKER_FILE" 2>/dev/null || echo "unknown")
            echo "WARNING: Same test failure occurred $MAX_FAIL times for this exact command. Re-check state changes and assumptions before retrying. Shadow-only policy does not block this call. (mk-agentos M3, cmd: $FAIL_CMD)" >&2
        fi
    fi
fi

exit 0
