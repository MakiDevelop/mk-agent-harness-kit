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
| `council-dispatch-guard` | PreToolUse Bash detects direct Council CLI dispatch | — |
| `no-progress-guard` | PreToolUse loop warnings and blocks from progress counters | reads `progress.json` |
| `preset-auto-upgrade` | PostToolUse upgrades light → standard or standard → governed | `decision-log.jsonl`, `project-state.yaml` |
| `progress-tracker` | PostToolUse records session progress counters | `progress.json`, `.progress.lock` |
| `session-onboarding` | SessionStart supplies a ≤8 KB context capsule | clears `.session-reads` |
| `state-validator` | PreToolUse validates project-state transitions | — |

`first-read-lock` only activates when `project-state.yaml` exists. `light` allows;
`standard` requires a read of `project-state.yaml`, plus `evidence/attempt-log.jsonl`
when that log exists and is non-empty; `governed` adds `evidence/decision-log.jsonl`
(same rule) and `context-index.yaml` when it exists. An absent optional file never
blocks by itself (legacy parity with `first-read-lock.sh`). It deliberately
uses only the minimal regex `^preset:\\s*(\\S+)`; quotes, comments, YAML nesting, and
multiline syntax are unsupported rather than requiring PyYAML.

`council-dispatch-guard` is deliberately legacy-compatible string analysis: it splits
shell segments, strips common wrappers, and blocks `codex exec` or prompt-mode
`gemini`, `grok`, and `agy`. Its dispatcher and blocked CLI lists are configurable at
`layers.harness.council`. This preserves the known OL-014 weakness: it is not a shell
parser, so heredoc and quoted-content false positives remain possible.

`preset-auto-upgrade` uses the first trigger in this order: a flat task with
`status: BLOCKED`, two JSONL records whose `status` is `failed`, then a `file_edits`
maximum of three. It changes only the top-level `preset:` line and appends its decision.

`session-onboarding` uses the shared minimal project-state parser. It supports top-level
`project` / `preset` scalars and a `tasks:` list of flat mappings (`id`, `status`,
`name`, `blocked_reason`), with quoted values and comment lines. Multiline values,
flow-style YAML, and nested lists are intentionally unsupported. Optional
An optional operator-supplied command can append one more line to the capsule, but it is
read **only** from the environment variable `ACK_ONBOARDING_EXTRA_COMMAND` (set it in your
own hook wiring), never from `settings.json`: settings live in the repository, and a
command that runs automatically at SessionStart must not be repository-controlled.
It runs with a 10-second timeout; failures and timeouts are ignored.

## `progress.json` schema v2

The tracker writes alongside `vault.jsonl`: `{"schema_version":2,"sessions":{"<session>":{"file_edits":{},"failure_by_command":{},"call_hashes":{}}}}`. It uses a locked temporary-file rename. Call keys use SHA-256 first 16 hex characters over `tool_name + ":" + json.dumps(tool_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`; this is jq `-Sc` compatible. Thresholds live at `layers.harness.no_progress` (12/6/3/2), with `MK_NO_PROGRESS_EDIT_BLOCK` and `MK_NO_PROGRESS_EDIT_WARN` taking precedence.

## State-validator rules

| Transition | Required field |
| --- | --- |
| Edit to `VERIFIED` | `verifier_id`, `evidence_id` |
| Edit to `ACCEPTED` | `accepted_by` |
| Edit `tech_verified: true` | `evidence_id` |
| Edit `business_aligned: true` | `aligned_by` |
| Write `VERIFIED` task | verifier, evidence (task or acceptance criterion), tech and business true |
| Write `ACCEPTED` task | accepted_by |

Write parsing is deliberately fail-open when the compact YAML/JSON parser cannot parse content. YAML booleans are recognized only as `true` (case-insensitive), unlike PyYAML's broader YAML 1.1 behavior.
