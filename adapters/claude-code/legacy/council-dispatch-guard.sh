#!/usr/bin/env bash
# mk-agentos Council Dispatch Guard — PreToolUse hook
# Blocks direct calls to Council CLI (codex exec / gemini / grok / agy).
# All Council dispatch must go through bin/council-dispatch.
#
# Exit 0 = allow, Exit 2 = block
#
# 2026-08-03 改寫：舊版用字面前綴比對，有兩個實證漏洞——
#   1. `gemini\s+-p` 只認緊接的 -p，`gemini -m <model> -p ...` 直接繞過
#   2. agy 只認行首或 ;&|( 之後，`timeout 180 agy ... -p ...` 直接繞過
# 兩者皆於 2026-08-03 popdaily council 實驗中無意觸發。
# 現改為：切出指令位置 → 剝掉 env 賦值與 wrapper → 比對第一個 token 的 basename。

set -uo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")

[ "$TOOL_NAME" != "Bash" ] && exit 0
[ -z "$COMMAND" ] && exit 0

# Allow council-dispatch itself（唯一合法入口）
echo "$COMMAND" | grep -q "council-dispatch" && exit 0

# 切成 segment：每個 shell 分隔符之後都是一個新的「指令位置」。
# 這同時保留了舊版避免誤擋的性質——prompt 內文提到 agy 不會是 segment 的第一個 token
# （2026-07-27 regression：內文含 "agy 第四席...audience-plus" 命中舊的寬鬆 regex）。
SEGMENTS=$(printf '%s\n' "$COMMAND" | sed -E 's/(\|\||&&|[;&|()`])/\n/g')

BLOCKED_CLI=""

while IFS= read -r seg; do
    [ -z "$seg" ] && continue

    # 剝掉前導的 env 賦值、wrapper 指令、以及 wrapper 自己的參數，
    # 直到第一個 token 是真正要執行的程式。
    guard=0
    while [ $guard -lt 20 ]; do
        guard=$((guard + 1))
        seg="${seg#"${seg%%[![:space:]]*}"}"      # ltrim
        first="${seg%%[[:space:]]*}"
        [ -z "$first" ] && break
        rest="${seg#*[[:space:]]}"
        [ "$rest" = "$seg" ] && break              # 只剩一個 token，不再剝

        case "$first" in
            # VAR=value 形式的 env 賦值
            [A-Za-z_]*=*)              seg="$rest" ;;
            # 常見 wrapper
            timeout|env|nice|nohup|stdbuf|command|exec|xargs) seg="$rest" ;;
            # wrapper 的參數（純數字如 timeout 180、旗標如 nice -n）
            -*|[0-9]*)                 seg="$rest" ;;
            *)                         break ;;
        esac
    done

    first="${seg%%[[:space:]]*}"
    [ -z "$first" ] && continue
    bin="${first##*/}"                             # basename，擋絕對路徑呼叫

    case "$bin" in
        codex)
            # codex 只有 exec 子指令算 dispatch
            echo "$seg" | grep -qE '(^|[[:space:]])exec([[:space:]]|$)' && BLOCKED_CLI="codex exec"
            ;;
        gemini|grok|agy)
            # 旗標可能出現在任何位置，不再要求緊接在指令名之後
            if echo "$seg" | grep -qE '(^|[[:space:]])(-p|-i|--print|--prompt|--prompt-interactive)([[:space:]]|=|$)'; then
                BLOCKED_CLI="$bin"
            fi
            ;;
    esac

    [ -n "$BLOCKED_CLI" ] && break
done <<< "$SEGMENTS"

if [ -n "$BLOCKED_CLI" ]; then
    echo "BLOCKED: Direct Council CLI dispatch is not allowed ($BLOCKED_CLI). Use bin/council-dispatch instead. (mk-agentos C1 anti-bypass)" >&2
    exit 2
fi

exit 0
