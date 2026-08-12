# Public surface (M5)

## Public product (what strangers should use)

| Path | Role |
|------|------|
| `GETTING_STARTED.md` (repo root) | Clone + settings.json walkthrough |
| `settings.example.json` | Canonical user template |
| `packages/agent-contract-kit/` | Portable contracts + CLIs + skills |
| `LICENSE` | Apache-2.0 |

## Lab / host (maintainers; not required for clone UX)

| Path | Role |
|------|------|
| `bin/council-dispatch`, `bin/board`, … | Personal multi-agent OS tools |
| `phase0/`, `docs/OPEN-LOOPS.yaml`, `evidence/` | Research & dogfood |
| `docs/CHAIR-MEMORY-PROTOCOL*` | Memory governance for host |

New contributors improving **product** should prefer changes under `packages/agent-contract-kit/` and root onboarding files.

## Publish checklist

1. `python3 packages/agent-contract-kit/cli/ack_portability_lint.py` → exit 0  
2. Kit tests green:  
   `python3 packages/agent-contract-kit/tests/test_ack_settings.py`  
   `python3 packages/agent-contract-kit/tests/test_ack_loop.py`  
   `python3 packages/agent-contract-kit/tests/test_ack_hooks.py`  
   `python3 packages/agent-contract-kit/tests/test_ack_review.py`  
3. `GETTING_STARTED.md` matches current CLIs  
4. No secrets in tree  
5. **Making the GitHub repo public** is a separate Chair decision (this M5 prepares the surface; it does not flip visibility by itself)

## Extract option

`packages/agent-contract-kit/` is designed to be extractable to a standalone public repo later (subtree split). Parent monorepo may remain private lab while kit is published.
