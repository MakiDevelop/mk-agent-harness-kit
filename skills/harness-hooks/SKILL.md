---
name: harness-hooks
description: Install or respect mk-agentos portable harness hooks from settings.json. Use when install_hooks, ack_hooks, force push block, rm -rf block, or PreToolUse harness is mentioned.
---

# Harness hooks (M3)

## Rules for agents

1. **Do not** run `ack_hooks.py install --global` unless human explicitly orders it with understanding of global Claude settings.
2. Prefer project install:

```bash
# only if settings have install_hooks:true OR human said --i-understand is ok
python3 packages/agent-contract-kit/cli/ack_hooks.py install \
  --settings settings.json --apply-project-claude
```

3. If a hook **denies** force-push / rm -rf, treat as hard stop — propose safe alternative, do not bypass with encoding tricks.
4. If a hook **asks** (git push / deploy / secrets path), wait for human.
5. After install, keep `.mk-agentos/settings.resolved.json` in sync when settings change (`ack_settings.py compile`).

## Uninstall

```bash
python3 packages/agent-contract-kit/cli/ack_hooks.py uninstall --settings settings.json
```

Only when human requests.
