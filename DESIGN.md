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

## 8. Product UX: clone + one settings.json

**North star (Maki 2026-08-12):**

```text
git clone mk-agentos
cp settings.example.json settings.json   # only user file
# edit profile / verify.commands / project.name
→ enjoy prompt / context / harness / loop / graph engineering
```

### 8.1 User surface

| Artifact | Role |
|----------|------|
| Repo-root `settings.example.json` | **Canonical** template |
| `settings.json` | User copy (gitignore recommended) |
| `spec/settings.schema.json` | Validation |
| `docs/PROFILES.md` | Expansion + **Normalization** (source of truth for effective config) |

Users never need home-lab IPs, AMH, or multi-agent seats for `solo` / `solo-strict`.

### 8.2 Layer compiler (conceptual)

```text
settings.json
  → load + JSON Schema validate
  → expand profile (PROFILES.md)
  → apply Normalization precedence
  → emit effective settings (resolved JSON)
  → map to:
       prompt pack ids
       context boot list
       harness confirms + flags
       loop policy (verify, wall, gap)
       graph document ref (builtin:solo | builtin:dual-review | path)
```

Solo = `graph.mode: solo` = **minimal graph** (loop only).  
Dual-review = same engine + edge contracts between executor and reviewer.

### 8.3 Acceptance (product)

On a clean machine with git + Python 3 + `pip install jsonschema` + a coding agent:

1. Clone repo, copy root `settings.example.json` → `settings.json`
2. Set real `verify.commands` for the target project
3. `ack_settings.py validate` + `compile` succeed
4. Agent following `ack_loop done-gate` **must not** claim done while verify fails (**M2**)
5. Wrap/wall emits `system-gap: none` or concrete gaps via `ack_loop wrap-gap` (**M2**)  
No AMH required when `memory.enabled` is false (default).

### 8.4 Roadmap (activation-gated)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **Skeleton** | tree + DESIGN + README | **done 2026-08-12** |
| **M0 settings** | schema + examples + PROFILES + README UX | **done 2026-08-12** (Codex PASS) |
| **M0b product docs** | §8 + COMPILE.md | **done 2026-08-12** |
| **M1 CLI** | `cli/ack_settings.py` validate + compile | **done 2026-08-12** |
| **M2 loop enforcement** | `cli/ack_loop.py` + skill + LOOP.md | **done 2026-08-12** |
| **M3 harness opt-in** | `hooks/pretool-harness.py` + `ack_hooks` | **done 2026-08-12** |
| **M4 graph edges** | `ack_review` filesystem dual-review | **done 2026-08-12** |
| **M5 public clone** | LICENSE, GETTING_STARTED, portability lint | **this change** |

`READY` in OPEN-LOOPS ≠ auto-implement. Follow BACKLOG-ACTIVATION-PROTOCOL.

---

## 9. Success metrics

| Metric | Target |
|--------|--------|
| Clone UX | copy one JSON; no second config file required |
| Solo user | loop + verify + gap in &lt; 5 minutes |
| Multi user | dual-review mode + agents map validates |
| Portability | validate/compile without home-lab services |
| Attention (L4) | profiles hide complexity; advanced keys optional |

Ultimate (parent OS metric still holds):

> Reduce how often humans repeat the same reminder — via contracts, not slogans.

---

## 10. Open questions (for ratify)

1. Public package name: `agent-contract-kit` vs shorter brand?  
2. ~~License~~ → **Apache-2.0** (repo root `LICENSE`, M5)  
3. ~~CLI language~~ → **Python 3** + `jsonschema`  
4. When to flip GitHub repo visibility / extract kit subtree? **Chair decision** (M5 prepares surface only)  

Default: keep name; parent may stay private until Chair opens it; kit remains extractable.
