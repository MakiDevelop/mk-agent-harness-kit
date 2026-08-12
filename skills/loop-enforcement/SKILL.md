---
name: loop-enforcement
description: Enforce mk-agentos loop policy from settings.json — run ack_loop done-gate before claiming done; emit system-gap on wall/wrap. Use when project has settings.json / agent-contract-kit, or user mentions verify gate, done-gate, system-gap, wall.
---

# Loop enforcement (portable)

## When

Any coding task in a repo that has:

- `settings.json` (from mk-agentos `settings.example.json`), or  
- `.mk-agentos/settings.resolved.json`

## Hard rules

1. **Before claiming done / complete / 完成**, run:

```bash
python3 packages/agent-contract-kit/cli/ack_loop.py done-gate --settings settings.json
```

(If kit is not at that relative path, use absolute path to `ack_loop.py` in the cloned mk-agentos tree, or `--resolved .mk-agentos/settings.resolved.json`.)

2. Interpret exit code:

| Exit | Action |
|------|--------|
| 0 | May claim done (only if user scope is satisfied) |
| 1 | Fix verify failures; re-run done-gate; **do not** claim done |
| 2 | **WALL** — stop code edits; print SYSTEM_GAP lines to user; wait |
| 3 | Configure `verify.commands` first; cannot claim done |

3. **Wrap / checkpoint / save**: run

```bash
python3 packages/agent-contract-kit/cli/ack_loop.py wrap-gap --settings settings.json
```

Paste the line(s) into the wrap summary (`system-gap: none` or `SYSTEM_GAP: …`).

4. Never run `ack_loop.py reset` unless the human explicitly asks.

## Optional compile step

```bash
python3 packages/agent-contract-kit/cli/ack_settings.py compile --settings settings.json -o .mk-agentos/settings.resolved.json
python3 packages/agent-contract-kit/cli/ack_loop.py done-gate --resolved .mk-agentos/settings.resolved.json
```

## Do not

- Skip done-gate because “tests probably pass”  
- Edit `.mk-agentos/loop-state.json` by hand to clear wall  
- Claim done when exit ≠ 0  
