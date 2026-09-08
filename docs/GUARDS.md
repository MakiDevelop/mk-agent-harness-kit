# Guards

`ack guard <name> --stdin-json` reads a Claude hook JSON object and writes exactly
one envelope: `{"guard":"<name>","decision":"allow|deny|ask|warn|noop","reason":"…","context":null,"state_written":[]}`.
The command exits 0 after every decision, including `deny`; invalid input or settings
exit 2. Names are closed in `ack.guard.GUARDS`.

Project root resolves as `--project-root`, `CLAUDE_PROJECT_DIR`, git top level, then
the current directory. Evidence state resolves as `ACK_EVIDENCE_DIR`, then
`layers.harness.evidence_dir` in `--settings`, then
`<project-root>/.mk-agentos/evidence/`. A relative configured directory is relative
to the project root.

| Guard | Event / decision | State |
| --- | --- | --- |
| `read-tracker` | PostToolUse Read records `tool_input.file_path`; other events noop | `.session-reads` |
| `evidence` | PostToolUse writes a compact UTF-8 SHA-256 hash-chain record | `vault.jsonl`, `.vault.lock` |
| `first-read-lock` | PreToolUse Edit/Write/Bash blocks mutation before required reads | reads `.session-reads` |
| `council-dispatch-guard` | planned (`legacy/council-dispatch-guard.sh`) | — |
| `no-progress-guard` | planned (`legacy/no-progress-guard.sh`) | — |
| `preset-auto-upgrade` | planned (`legacy/preset-auto-upgrade.sh`) | — |
| `progress-tracker` | planned (`legacy/progress-tracker.sh`) | — |
| `session-onboarding` | planned (`legacy/session-onboarding.sh`) | — |
| `state-validator` | planned (`legacy/state-validator.sh`) | — |

`first-read-lock` only activates when `project-state.yaml` exists. `light` allows;
`standard` requires a read of `project-state.yaml`, plus `evidence/attempt-log.jsonl`
when that log exists and is non-empty; `governed` adds `evidence/decision-log.jsonl`
(same rule) and `context-index.yaml` when it exists. An absent optional file never
blocks by itself (legacy parity with `first-read-lock.sh`). It deliberately
uses only the minimal regex `^preset:\\s*(\\S+)`; quotes, comments, YAML nesting, and
multiline syntax are unsupported rather than requiring PyYAML.
