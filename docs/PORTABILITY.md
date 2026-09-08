# Portability rules

This package must remain usable **without** the parent `mk-agentos` tree.

## Allowed

- Relative imports within this package  
- Standard library / declared dependencies only  
- User-supplied absolute paths via CLI flags  

## Forbidden in kit source & examples

- Hardcoded `100.x.x.x`, Tailscale hosts, `mini2`, `dgx-ts`  
- Company tenant/shop identifiers  
- Secrets, tokens, private URLs  
- Assumptions that `~/.claude/CLAUDE.md` exists  

## Lint

```bash
python3 packages/agent-contract-kit/cli/ack_portability_lint.py
```

Exit 0 required before publishing kit changes. In a checkout it scans the logical
`cli/`, `hooks/`, `tests/`, `src/ack/_assets/templates/`, `skills/`, and `spec/`
sets, with shipped assets located under `src/ack/_assets/` (not denylist docs).
