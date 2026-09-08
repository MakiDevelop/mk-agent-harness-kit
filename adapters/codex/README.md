# Codex 實跑範例

這是 Codex 實際跑的，日期：2026-09-08。
kit commit：`b5da938`。
Python：`Python 3.12.13`；入口為 `PYTHONPATH=src python3 -m ack.cli`（未使用 pipx）。

路徑說明：輸出中的 `<kit>` 是本 repo checkout 的絕對路徑，為避免把個人主機路徑放進套件文件而以佔位符取代；其餘輸出逐字保留。

最小暫存專案位於 `/tmp/ack-codex-example.Eb22dD`，含 `hello.py` 與一個通過的 pytest；第二個失敗測試先註解、後解開以驗證 wall，再註解回去。`settings.json` 由範例複製，並將 `project.name` 改為 `codex-ack-example`、`verify.commands` 改為 `["python3 -m pytest -q"]`。以下為逐步原始輸出；每個區塊最後的 `[exit N]` 是該指令的退出碼。

```text
$ cp <kit>/settings.example.json settings.json
[exit 0]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.cli settings validate
usage: ack_settings validate [-h] --settings SETTINGS [--schema SCHEMA]
ack_settings validate: error: the following arguments are required: --settings
[exit 2]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.cli settings compile -o .mk-agentos/settings.resolved.json
usage: ack_settings compile [-h] --settings SETTINGS [--schema SCHEMA]
                            [-o OUTPUT]
ack_settings compile: error: the following arguments are required: --settings
[exit 2]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.cli settings summary
usage: ack_settings summary [-h] --settings SETTINGS [--schema SCHEMA]
ack_settings summary: error: the following arguments are required: --settings
[exit 2]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.cli loop done-gate
usage: ack_loop done-gate [-h] (--settings SETTINGS | --resolved RESOLVED)
ack_loop done-gate: error: one of the arguments --settings --resolved is required
[exit 2]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.cli settings validate --settings settings.json
OK settings.json
[exit 0]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.cli settings compile --settings settings.json -o .mk-agentos/settings.resolved.json
wrote .mk-agentos/settings.resolved.json
[exit 0]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.cli settings summary --settings settings.json
profile: solo-strict
project: {'root': '.', 'name': 'codex-ack-example'}
layers:
  prompt: {"briefing_template": "default", "require_goal": true}
  context: {"on_session_start": ["settings-summary", "git-status", "project-state", "open-gaps"], "memory": {"enabled": false, "backend": "none"}}
  harness: {"preset": "standard", "block_force_push": true, "block_rm_rf": true, "install_hooks": false, "council": {"dispatcher": "council-dispatch", "blocked_clis": {"codex": ["exec"], "gemini": ["-p", "-i", "--print", "--prompt", "--prompt-interactive"], "grok": ["-p", "-i", "--print", "--prompt", "--prompt-interactive"], "agy": ["-p", "-i", "--print", "--prompt", "--prompt-interactive"]}}, "no_progress": {"edit_block": 12, "edit_warn": 6, "call_block": 3, "fail_warn": 2}}
  loop: {"max_failed_attempts": 2, "require_system_gap_on_wall": true, "require_system_gap_on_wrap": true, "verify": {"commands": ["python3 -m pytest -q"]}}
  graph: {"mode": "solo", "edges": "builtin:solo"}
human: {"require_confirm_for": ["git_push", "delete", "deploy", "secrets"]}
adapters: {"filesystem_briefing": true, "langgraph": false}
[exit 0]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.cli loop done-gate --settings settings.json
project_root: /private/tmp/ack-codex-example.Eb22dD
running 1 verify command(s)…
  [OK] exit=0  python3 -m pytest -q
VERIFY PASS
done-gate: OPEN (verify green)
[exit 0]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.cli loop done-gate --settings settings.json
project_root: /private/tmp/ack-codex-example.Eb22dD
running 1 verify command(s)…
  [FAIL] exit=1  python3 -m pytest -q
VERIFY FAIL (1/2)
done-gate: CLOSED (fix then re-run verify)
[exit 1]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.cli loop done-gate --settings settings.json
project_root: /private/tmp/ack-codex-example.Eb22dD
running 1 verify command(s)…
  [FAIL] exit=1  python3 -m pytest -q
VERIFY FAIL (2/2) — WALL
done-gate: CLOSED
SYSTEM_GAP: {error_mode: verify failed max_failed_attempts times (wall)} → {control: loop.verify.commands|skill} → {ratify?: no}
Agent must STOP code changes, report system-gap, and not claim done.
[exit 2]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.cli loop wrap-gap --settings settings.json
SYSTEM_GAP: {error_mode: verify failed max_failed_attempts times (wall)} → {control: loop.verify.commands|skill} → {ratify?: no}
[exit 0]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.cli loop done-gate --settings settings.json
project_root: /private/tmp/ack-codex-example.Eb22dD
running 1 verify command(s)…
  [OK] exit=0  python3 -m pytest -q
VERIFY PASS
done-gate: OPEN (verify green)
[exit 0]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.cli loop status --settings settings.json
project_root: /private/tmp/ack-codex-example.Eb22dD
state_file: /private/tmp/ack-codex-example.Eb22dD/.mk-agentos/loop-state.json
consecutive_verify_failures: 0/2
wall_hit: False
last_verify: {"ok": true, "at": "2026-09-08T08:22:30+00:00", "results": [{"command": "python3 -m pytest -q", "exit_code": 0, "ok": true}]}
verify.commands: ['python3 -m pytest -q']
require_system_gap_on_wall: True
require_system_gap_on_wrap: True
[exit 0]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.capcli cap classify rm -r build
{"command":"rm","risk_level":"RED","risk_reasons":["recursive rm"]}
[exit 0]
```

```text
$ PYTHONPATH=<kit>/src python3 -m ack.capcli cap check rsync -av src/ /tmp/dest/
<kit>/src/ack/_assets/bin/cap-check: line 126: $HOME/.agent_audit/plans/P-20260908-b370139b.json: Operation not permitted
cat: $HOME/.agent_audit/plans/P-20260908-b370139b.json: No such file or directory
<kit>/src/ack/_assets/bin/_cap_audit: line 27: $HOME/.agent_audit/logs/2026-09-08.jsonl: Operation not permitted
[exit 0]
```

```text
$ printf '{"tool_name":"Edit","tool_input":{}}' | PYTHONPATH=<kit>/src python3 -m ack.cli guard first-read-lock --project-root . --stdin-json
{"guard":"first-read-lock","decision":"allow","reason":"no mk-agentos project-state.yaml","context":null,"state_written":[]}
[exit 0]
```

```text
$ HOME=/tmp/ack-codex-example.Eb22dD PYTHONPATH=<kit>/src python3 -m ack.capcli cap check rsync -av src/ /tmp/dest/
{"plan_id":"P-20260908-bd8e920f","created_at":"2026-09-08T08:22:45Z","operator":"agent","command":"rsync","binary_path":"/usr/bin/rsync","args":["-av","src/","/tmp/dest/"],"sources":["/private/tmp/ack-codex-example.Eb22dD/src"],"dest":"/tmp/dest/","risk_level":"YELLOW","risk_reasons":["rsync write operation"],"safety_checks":{"empty_args":false,"wildcards":false,"sensitive_paths":false,"destructive_flags":[],"multi_source":false},"dry_run":{"files_transferred":0,"total_size_bytes":0,"exit_code":0},"status":"awaiting_approval","executed_at":null,"exec_exit_code":null}
[exit 0]
```

## Codex 的觀察

briefing 中不帶旗標的 `ack settings validate|compile|summary` 與 `ack loop done-gate` 都不能直接執行：CLI 強制要求 `--settings`（或 done-gate 的 `--resolved`）。對首次使用的 agent 而言，範例與 CLI 介面不一致，應在 quick start 補上完整可複製指令，或讓這些命令預設讀取工作目錄的 `settings.json`。

`cap check` 預設寫入 `$HOME/.agent_audit`。受 sandbox 限制時它印出三個明確的寫入失敗訊息，卻仍以 exit 0 結束、沒有 JSON/plan id；這對 agent 不夠明確，因為成功退出碼會被解讀為 plan 已建立。設定 `HOME` 為暫存專案後才取得 plan id。建議 cap 將 plan/audit 寫入失敗改為非零退出，或支援一個明確的 project-local audit 路徑旗標。

done-gate 的 WALL 與 `SYSTEM_GAP` 字樣很明確，但 wall 後修正測試再跑即可回到 OPEN；若「STOP code changes」是硬性治理語意，文件應補充「取得/記錄 system-gap 後可做修復並重新驗證」的恢復流程。
