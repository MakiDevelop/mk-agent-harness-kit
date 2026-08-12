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
  spec/              # JSON Schema (P0 — stubs)
  templates/         # YAML examples (solo + dual-review)
  examples/          # dogfood exports (sanitized)
  cli/               # ack validate / gap (P1 — empty)
  adapters/          # optional filesystem, etc.
  docs/              # portable docs only (no home-lab IPs)
```

## Relation to mk-agentos

| Parent (`mk-agentos`) | This package |
|-----------------------|--------------|
| Personal agent OS, hooks, board, council-dispatch | Portable contract layer |
| Dogfood & hard enforcement | Spec + validate + templates |
| May stay private | Intended extractable / public later |

**Rule:** OS may call kit; kit must not depend on OS paths (`~/.claude`, mini2, 91app, …).

## Quick start (when P0 schemas land)

```bash
# planned
ack validate examples/solo-loop.yaml
ack validate examples/dual-review.yaml
```

Today: read `DESIGN.md` + `templates/*.yaml` stubs; schemas are placeholders.

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
