# Profile expansion + Normalization

`settings.json` uses one `profile`, then optional overrides.  
**JSON Schema `default` is annotation only.** Compilers must implement this document.

## Canonical clone path

```bash
git clone <mk-agentos>
cd mk-agentos
cp settings.example.json settings.json   # ROOT file only
# edit verify.commands + project.name
```

- **Canonical example:** repo-root `settings.example.json`  
  (`$schema` → `packages/agent-contract-kit/src/ack/_assets/spec/settings.schema.json`)
- Package-local `packages/agent-contract-kit/settings.example.json` is for **in-package tests only**; do not copy it to repo root (broken relative `$schema`).

## Normalization (effective config) — precedence

Apply in order:

1. Start from **profile expansion table** below (complete arrays, not “+” deltas).
2. Overlay top-level `project` (if present).
3. Overlay top-level `verify` → sets `layers.loop.verify` **wholesale** (replaces profile verify).
4. Overlay top-level `human` → sets `human.require_confirm_for` base list.
5. Overlay `layers.*` field-by-field (nested objects shallow-merge one level; `verify.commands` if present replaces entirely).
6. Overlay `adapters.*`.
7. **Forced unions / invariants (always last):**
   - `human.require_confirm_for` := unique( effective ∪ `{"secrets"}` )
   - If `context.memory.enabled === true` then `backend` ∈ {`amh`,`file`} (not `none`)
   - If `graph.mode === solo` then `graph.edges` must not be `builtin:dual-review`
   - If `graph.mode === dual-review` then `graph.edges` must not be `builtin:solo`; `agents.executor` + `agents.reviewer` required
   - Profiles `solo-strict` | `dual-review` | `governed` require non-empty effective `loop.verify.commands`
8. Reject if invariants fail (schema + compiler double-check).

**Conflict rule:** never “average” two verify lists. Last write wins per steps 3–5; then invariants.

## Profile expansion table (complete values)

### `solo`

| Key | Value |
|-----|--------|
| prompt.briefing_template | minimal |
| prompt.require_goal | true |
| context.on_session_start | ["settings-summary", "git-status"] |
| context.memory.enabled | false |
| context.memory.backend | none |
| harness.preset | light |
| harness.block_force_push | true |
| harness.block_rm_rf | true |
| harness.install_hooks | false |
| loop.max_failed_attempts | 2 |
| loop.require_system_gap_on_wall | true |
| loop.require_system_gap_on_wrap | false |
| loop.verify.commands | [] (allowed empty only for `solo`) |
| graph.mode | solo |
| graph.edges | builtin:solo |
| human.require_confirm_for (before secrets union) | ["git_push", "delete"] |
| adapters.filesystem_briefing | true |
| adapters.langgraph | false |

### `solo-strict`

| Key | Value |
|-----|--------|
| prompt.briefing_template | default |
| prompt.require_goal | true |
| context.on_session_start | ["settings-summary", "git-status", "project-state", "open-gaps"] |
| context.memory.enabled | false |
| context.memory.backend | none |
| harness.preset | standard |
| harness.block_force_push | true |
| harness.block_rm_rf | true |
| harness.install_hooks | false |
| loop.max_failed_attempts | 2 |
| loop.require_system_gap_on_wall | true |
| loop.require_system_gap_on_wrap | true |
| loop.verify.commands | **required non-empty** via settings `verify` or `layers.loop.verify` |
| graph.mode | solo |
| graph.edges | builtin:solo |
| human.require_confirm_for (before secrets union) | ["git_push", "delete", "deploy"] |
| adapters.filesystem_briefing | true |
| adapters.langgraph | false |

### `dual-review`

| Key | Value |
|-----|--------|
| prompt.briefing_template | default |
| prompt.require_goal | true |
| context.on_session_start | ["settings-summary", "git-status", "project-state", "open-gaps", "last-handoff"] |
| context.memory.enabled | false |
| context.memory.backend | none |
| harness.preset | standard |
| harness.block_force_push | true |
| harness.block_rm_rf | true |
| harness.install_hooks | false |
| loop.max_failed_attempts | 2 |
| loop.require_system_gap_on_wall | true |
| loop.require_system_gap_on_wrap | true |
| loop.verify.commands | **required non-empty** |
| graph.mode | dual-review |
| graph.edges | builtin:dual-review |
| graph.agents | user must set executor + reviewer (no silent default vendor) |
| human.require_confirm_for (before secrets union) | ["git_push", "delete", "deploy"] |
| adapters.filesystem_briefing | true |
| adapters.langgraph | false |

### `governed`

| Key | Value |
|-----|--------|
| prompt.briefing_template | council |
| prompt.require_goal | true |
| context.on_session_start | ["settings-summary", "git-status", "project-state", "open-gaps", "last-handoff"] |
| context.memory.enabled | false |
| context.memory.backend | none |
| harness.preset | governed |
| harness.block_force_push | true |
| harness.block_rm_rf | true |
| harness.install_hooks | false |
| loop.max_failed_attempts | 2 |
| loop.require_system_gap_on_wall | true |
| loop.require_system_gap_on_wrap | true |
| loop.verify.commands | **required non-empty** |
| graph.mode | dual-review |
| graph.edges | builtin:dual-review |
| graph.agents | user must set executor + reviewer |
| human.require_confirm_for (before secrets union) | ["git_push", "delete", "deploy", "governance_edit"] |
| adapters.filesystem_briefing | true |
| adapters.langgraph | false |

After expansion, **always** add `secrets` to `human.require_confirm_for`.

## Layer mapping

| Layer | Settings keys |
|-------|----------------|
| Prompt | `layers.prompt.*` + briefing template id |
| Context | `layers.context.*` |
| Harness | `layers.harness.*` + `human.require_confirm_for` |
| Loop | `layers.loop.*` + top-level `verify` |
| Graph | `layers.graph.*` (`solo` = loop-only graph) |

## Security notes

- `verify.commands` are **shell** — only use trusted `settings.json`.
- `project.name` is a **slug**, not a path.
- `secrets` confirmation cannot be removed by omitting it from user lists (forced union).

## Briefing template ids

`minimal` / `default` / `council` are **symbols**. Asset files may land later; until then compilers record the id only (no missing-file error).
