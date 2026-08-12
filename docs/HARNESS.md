# Harness hooks (M3)

## Purpose

Opt-in **portable** PreToolUse guard driven by effective settings:

| Setting | Effect |
|---------|--------|
| `harness.block_force_push` | deny `git push --force`, `reset --hard`, aggressive `clean -f` |
| `harness.block_rm_rf` | deny `rm -rf` / recursive force remove |
| `human.require_confirm_for` | `ask` for git_push / deploy / delete / secrets / … |
| secrets | always treated as confirm category |

## Opt-in only

`harness.install_hooks` defaults **false**.

```bash
# in settings.json
"layers": { "harness": { "install_hooks": true } }
```

Or one-shot:

```bash
python3 packages/agent-contract-kit/cli/ack_hooks.py install \
  --settings settings.json --i-understand --apply-project-claude
```

**Never** writes `~/.claude/settings.json` unless `--global --i-understand`.

## Install layout

```text
{project.root}/.mk-agentos/
  hooks/pretool-harness.py
  settings.resolved.json
  claude-settings.fragment.json
{project.root}/.claude/settings.json   # only with --apply-project-claude
```

## CLI

```bash
python3 packages/agent-contract-kit/cli/ack_hooks.py status --settings settings.json
python3 packages/agent-contract-kit/cli/ack_hooks.py install --settings settings.json --apply-project-claude
python3 packages/agent-contract-kit/cli/ack_hooks.py test-cmd --settings settings.json --command 'git push --force origin main'
python3 packages/agent-contract-kit/cli/ack_hooks.py uninstall --settings settings.json
```

## Protocol

Hook reads Claude-style JSON on stdin (`tool_name` + `tool_input.command`).  
Deny/ask via stdout JSON `hookSpecificOutput.permissionDecision`.

## Limits (honest)

- Matcher is **Bash** command-string heuristics (not full shell AST).  
- Does not replace OS sandbox / Seatbelt.  
- Other tools (Edit/Write) not covered in M3 — use agent discipline + M2 loop.  
