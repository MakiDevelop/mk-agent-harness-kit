# Loop enforcement (M2)

## Purpose

Turn compiled settings into a **hard done-gate**:

- Run `layers.loop.verify.commands` before claiming done  
- Count consecutive failures toward `max_failed_attempts`  
- On wall: print **SYSTEM_GAP** lines and refuse further “done”  
- On wrap: print `system-gap: none` or concrete gaps  

## CLI

```bash
# from project cwd (project.root in settings, default .)
python3 packages/agent-contract-kit/cli/ack_loop.py verify --settings settings.json
python3 packages/agent-contract-kit/cli/ack_loop.py done-gate --settings settings.json   # alias
python3 packages/agent-contract-kit/cli/ack_loop.py status --settings settings.json
python3 packages/agent-contract-kit/cli/ack_loop.py wrap-gap --settings settings.json
python3 packages/agent-contract-kit/cli/ack_loop.py reset --settings settings.json
```

Or use precompiled effective config:

```bash
python3 packages/agent-contract-kit/cli/ack_settings.py compile --settings settings.json -o .mk-agentos/settings.resolved.json
python3 packages/agent-contract-kit/cli/ack_loop.py verify --resolved .mk-agentos/settings.resolved.json
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Verify PASS — done-gate OPEN |
| 1 | Verify FAIL — not yet wall; fix and retry |
| 2 | WALL — max consecutive failures; stop code changes; report SYSTEM_GAP |
| 3 | No verify commands configured (incomplete policy for claiming done) |

## State file

`{project.root}/.mk-agentos/loop-state.json` (gitignored via root `.mk-agentos/`)

```json
{
  "consecutive_verify_failures": 0,
  "wall_hit": false,
  "last_verify": { "ok": true, "at": "...", "results": [] }
}
```

Success resets consecutive failures and clears `wall_hit`.

## Agent contract (normative)

1. Before saying a task is **done**, run `done-gate` / `verify` and require exit **0**.  
2. On exit **1**, fix failures; do not claim done.  
3. On exit **2**, **stop** editing; report SYSTEM_GAP lines; wait for human.  
4. On wrap-up / checkpoint, run `wrap-gap` and paste output (`system-gap: none` or gaps).  
5. Do not delete/reset state to fake green without human approval (`reset` is human tool).

## Security

- `verify.commands` are shell — only use trusted settings.  
- Commands run with `cwd=project.root`.  
