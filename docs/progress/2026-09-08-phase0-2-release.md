# 2026-09-08 — 拆倉、cap、九守衛、0.1.0 發佈

> 範圍：整個 repo 的誕生日。Risk：public + PyPI 不可逆。Outcome：0.1.0 上架，CI 綠，雙 review approve。

## 觸發點

Maki：「把我們做的 Agent 框架做一下整理 → 整理並推上 repo → 打包成下載即用的框架 repo → 我比較在意發佈」。盤點結果（mk-agentos `docs/FRAMEWORK-MAP.md`）顯示 ACK、cap、九個 Claude hook、Evidence Vault 散在四處，決定以 ACK 為骨架打包。

## 時間軸（commits）

| 階段 | Commits | 內容 |
|---|---|---|
| 0 拆倉 | 9258d97 → 2edbd6e 62a568b 08fce1c 7efd8cd 9558f22 0b22661 | subtree split；pyproject + `src/ack/`；`_assets` SSOT；shim；tests；README |
| 1 cap | 1126080 de8ad76 | 八個 bash 進 `_assets/bin/`，`ack.capcli` 以 bash 執行，lint 納入無副檔名 |
| 2a | 604e00b 2987ace ca0a124 5549d0f | `ack guard` 骨架 + read-tracker / evidence / first-read-lock；adapter；legacy 對照；tests |
| 2b | 67f962f 89bf413 | council-dispatch-guard / preset-auto-upgrade / session-onboarding；`_projectstate.py` |
| 2c + 安全 | c827009 d3a2f98 be37fd6 b5da938 | progress-tracker / no-progress-guard / state-validator；**extra_command 改只認 env**（repo 可控 RCE） |
| 發佈 | 279d7f7 4ef533e bf2baf7 + tag v0.1.0 | CI / release workflow / CHANGELOG / metadata / Codex 實跑範例 / PyPI 名 |

## 驗證

- 67 passed（本機 + CI 3.10–3.13 兩輪）
- evidence hash：對 Chair 真實 vault 42,305 行逐行重算，0 自身 hash 不符（34 處 prev 斷鏈是原版 macOS 無 flock 的歷史問題）
- progress.json：call_hash16 對 `jq -Sc` 預算值 `54c76ca0fab65b37` 一致；真檔副本 278 sessions 追加後保留
- council-dispatch-guard：九個命令與原版 bash 判定完全相同
- 從 PyPI 乾淨 venv 安裝 0.1.0：`ack` / `cap` 可跑
- Review：每階段 Codex 實作 → AGY（gemini-3.7-flash-high）或 llm-hub（gemini-3.1-pro）獨立審；2c 與安全修正雙 approve

## Open issues / 0.1.1

1. `--settings` 無預設（Codex dogfood）
2. `cap check` 寫入 `$HOME/.agent_audit` 失敗仍 exit 0
3. adapter 未打包進 wheel
4. README 相對連結在 PyPI 頁面會壞
5. CI actions 升版（Node 20 棄用）
6. no-progress-guard 對進度紀錄檔誤擋 → exempt_globs
7. 階段 3 lint 二合一；階段 4 dogfood 兩週（起算 09-08）

## 參考

- 交接包：`~/Documents/agent-council/2026-09-08-harness-kit-proposal/00-HANDOFF-README.md`
- 地圖：`~/GitHub/mk-agentos/docs/FRAMEWORK-MAP.md`
- 本機 review 證據：`evidence/review/P0*.md P1*.md P2a*.md P2b*.md P2c*.md P3*.md`（gitignored）
