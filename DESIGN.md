# DESIGN — agent-contract-kit

> v0.1 skeleton — 2026-08-12  
> Ratify gate: Maki (OPEN-LOOPS OL-022)

---

## 1. Problem

Teams add prompts, hooks, and multi-agent routing until:

- single agents skip verification and claim “done”  
- multi-agent handoffs lose schema, timeout, and evidence  
- failures are fixed with “next time remember” instead of system changes  

Existing runtimes (LangGraph, etc.) orchestrate **nodes**.  
They rarely force **edge contracts** or a shared **gap log**.

---

## 2. Solution (one layer)

**Agent Contract Kit** = portable specs + validation + templates for:

1. **Node** — unit of work (agent | tool | router | gate | script)  
2. **Loop policy** — do → verify → stop (inside a node)  
3. **Edge contract** — what may travel between nodes  
4. **System gap** — recorded harness/graph holes for human ratify  

Single-agent systems use (1)(2)(4).  
Multi-agent systems add (3). Same objects.

---

## 3. Layer stack (vocabulary)

| Layer | Engineers… | Kit concern? |
|-------|------------|--------------|
| Prompt | the request | examples only |
| Context | what the model sees | context_budget on edges |
| Harness | tools, rules, permissions | gap type `harness` |
| Loop | one agent’s cycle | LoopPolicy |
| Graph | coordination of many loops | Edge + Router |

Kit **names** all five; **implements** Loop + Graph contracts + gap audit.  
Harness *code* (hooks, memory servers) stays in host OS or user stack.

---

## 4. Core objects

```text
GraphDocument
  nodes: Node[]
  edges: Edge[]
  state: StateSchema
  meta: { name, version }

Node
  id, kind, loop?: LoopPolicy

Edge
  id, from, to, kind
  schema, context_budget, constraints
  verify, timeout, on_error, evidence
  ratify_required?

SystemGap
  mode, control, ratify_required, session_id?
```

**Loop = minimal graph:** one node; zero edges or one loop-back edge.

### Edge contract fields (v1 target)

Aligned with course + production template:

| Field | Question |
|-------|----------|
| schema | what shape travels? |
| context_budget | how much context? |
| constraints | what must downstream not do? |
| verify | how is success checked? |
| timeout | how long to wait? |
| on_error | retry / fallback / cut? |
| evidence | raw pointers (contract ≠ sole truth)? |

### System gap format (v1 target)

```text
{error_mode} → {control: hook|rule|docs|skill|registry|edge-contract|graph} → {ratify?}
```

Empty session must still emit `system-gap: none` (or machine-readable equivalent).

---

## 5. Non-goals (hard)

| Non-goal | Why |
|----------|-----|
| Ship a full agent runtime | reinvent LangGraph; kill focus |
| Bundle memory/RAG servers | host-specific; couple kit to lab |
| Require multi-agent | excludes solo users |
| Encode Maki CLAUDE.md as dependency | not portable |
| Auto-ratify governance changes | human authority |

---

## 6. Host vs package boundary

| Lives in `mk-agentos` (parent) | Lives in this package |
|--------------------------------|------------------------|
| board, evidence vault, hooks | JSON Schema + YAML templates |
| council-dispatch CLI (rich) | thin `ack validate` (planned) |
| AMH / profile routing | nothing |
| OPEN-LOOPS personal ops | optional *examples* only if sanitized |
| Dogfood graphs with private paths | sanitized copies under `examples/` |

**Import rule:** parent may `import` / shell-out to kit.  
Kit **must not** import parent modules or hardcode home-lab paths.

**Sanity lint (planned):** fail CI if kit tree matches `100\.\d+`, `91app`, `mini2-ts`, etc.

---

## 7. Adapters (optional, late)

| Adapter | Role |
|---------|------|
| filesystem | briefing.md ↔ answer.md edge checks |
| langgraph | map GraphDocument → StateGraph (stub) |
| generic-cli | env for any CLI agent |

MVP success **does not** require adapters — validate-only is enough.

---

## 8. Roadmap (activation-gated)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **Skeleton** | this tree + DESIGN + README | **done 2026-08-12** |
| **P0** | JSON Schema drafts + 2 templates filled | blocked on Maki ratify OL-022 |
| **P1** | `ack validate` CLI + fixtures/tests | after P0 |
| **P2** | freshness check (generic paths) + gap report | after P1 |
| **P3** | dogfood: export wrap-up / council as examples | after P1 |
| **P4** | public extract decision (subtree or new repo) | after portable proof |

`READY` in OPEN-LOOPS ≠ auto-implement. Follow BACKLOG-ACTIVATION-PROTOCOL.

---

## 9. Success metrics

| Metric | Target |
|--------|--------|
| Solo user | describe loop + verify + gap in &lt; 5 minutes |
| Multi user | one dual-review graph validates with full edge contracts |
| Portability | clone kit dir alone; no parent required for validate |
| Attention (L4) | core surface stays small; no dashboard in MVP |

Ultimate (parent OS metric still holds):

> Reduce how often humans repeat the same reminder — via contracts, not slogans.

---

## 10. Open questions (for ratify)

1. Public package name: `agent-contract-kit` vs shorter brand?  
2. License: Apache-2.0 vs MIT?  
3. First CLI language: Python (align parent) vs pure shell + check-jsonschema?  
4. When to open parent repo vs only publish this package?  

Default proposals: keep name; Apache-2.0; Python CLI; **keep parent private**, publish package later.
