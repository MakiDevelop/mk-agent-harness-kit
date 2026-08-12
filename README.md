# agent-contract-kit

> **Status:** incubator skeleton (2026-08-12)  
> **Host repo:** `mk-agentos` (private OS / lab)  
> **Goal:** portable **contracts + loops + gaps** for single-agent and multi-agent systems — not another runtime.

## What this is

A thin kit for describing and validating how agents work:

| Concept | Single agent | Multi-agent |
|---------|--------------|-------------|
| **Node** | one worker | specialized workers / tools / gates |
| **Loop** | do → verify → stop | inside each node |
| **Edge** | optional self-loop | handoffs with contracts |
| **System gap** | harness holes | harness + graph holes |

**Loop is the minimal graph** (one node, optional edge back to itself).  
Same schemas. Same CLI. No second product.

## What this is not

- Not a model API wrapper  
- Not a replacement for LangGraph / AutoGen / Crew  
- Not a memory backend (AMH / memhall stay outside)  
- Not Maki’s personal OS (that is the parent `mk-agentos` repo)

LangGraph (etc.) = **how the graph runs**.  
This kit = **what edges may carry, how failure cuts, how gaps are recorded**.

## Layout

```text
packages/agent-contract-kit/
  README.md          # this file
  DESIGN.md          # boundaries, layers, non-goals
  spec/              # settings.schema.json (+ future edge schemas)
  templates/         # YAML examples (solo + dual-review)
  examples/          # dogfood exports (sanitized)
  cli/ack_settings.py  # validate / compile / summary (M1)
  cli/ack_loop.py      # verify / done-gate / wrap-gap / wall (M2)
  cli/ack_hooks.py     # opt-in install harness PreToolUse (M3)
  cli/ack_review.py    # dual-review briefing/answer gates (M4)
  hooks/pretool-harness.py
  skills/loop-enforcement/
  skills/harness-hooks/
  skills/dual-review-fs/
  tests/             # unit tests for CLI
  adapters/          # optional filesystem, etc.
  docs/              # PROFILES, COMPILE, LOOP, PORTABILITY
```

## Relation to mk-agentos

| Parent (`mk-agentos`) | This package |
|-----------------------|--------------|
| Personal agent OS, hooks, board, council-dispatch | Portable contract layer |
| Dogfood & hard enforcement | Spec + validate + templates |
| May stay private | Intended extractable / public later |

**Rule:** OS may call kit; kit must not depend on OS paths (`~/.claude`, mini2, 91app, …).

## Quick start (settings-first)

From **repo root** (canonical):

```bash
cp settings.example.json settings.json
# edit verify.commands — must be real checks for solo-strict+
```

Schema: `spec/settings.schema.json`  
Profile expansion: `docs/PROFILES.md`  
In-package `settings.example.json` is **self-test only** (fail-closed placeholder verify); do not copy to repo root.

```bash
python3 packages/agent-contract-kit/cli/ack_settings.py validate --settings settings.json
python3 packages/agent-contract-kit/cli/ack_settings.py compile --settings settings.json -o .mk-agentos/settings.resolved.json
python3 packages/agent-contract-kit/cli/ack_settings.py summary --settings settings.json

# Loop enforcement (before claim done)
python3 packages/agent-contract-kit/cli/ack_loop.py done-gate --settings settings.json
python3 packages/agent-contract-kit/cli/ack_loop.py wrap-gap --settings settings.json

# optional harness hooks (requires install_hooks:true or --i-understand)
python3 packages/agent-contract-kit/cli/ack_hooks.py install --settings settings.json --apply-project-claude

# dual-review (profile dual-review|governed)
python3 packages/agent-contract-kit/cli/ack_review.py init --settings settings.json
python3 packages/agent-contract-kit/cli/ack_review.py handoff-gate --settings settings.json
python3 packages/agent-contract-kit/cli/ack_review.py accept-gate --settings settings.json

python3 packages/agent-contract-kit/tests/test_ack_settings.py
python3 packages/agent-contract-kit/tests/test_ack_loop.py
python3 packages/agent-contract-kit/tests/test_ack_hooks.py
python3 packages/agent-contract-kit/tests/test_ack_review.py
```

Skills: loop-enforcement, harness-hooks, dual-review-fs  
Docs: LOOP.md, HARNESS.md, GRAPH.md

Graph YAML templates (`templates/solo-loop.yaml`, `dual-review.yaml`) remain illustrative until edge schemas land.

## Provenance (inspiration, not runtime deps)

Steamed from Maki’s production governance (2026):

- Edge Contract (schema / budget / error / timeout / evidence)  
- System-gap exit format (harness + graph)  
- Council / wrap-up pipeline graphs  
- Instruction freshness checks  

Upstream working copies (lab, not required to use kit):

- `~/.claude/docs/governance/graph-engineering.md`  
- `~/.claude/docs/governance/edge-contract.template.md`  
- `~/.claude/docs/governance/graphs/`  

## License (intent)

TBD before first public release (likely Apache-2.0 or MIT).  
Until then: same as parent repo; **do not treat as public API**.

## Tracking

- OPEN-LOOPS: `OL-022`  
- BACKLOG: `B-025`  
- Activation: Maki ratify before implementation beyond skeleton  
