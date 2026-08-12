# Settings compile pipeline

## Inputs

| Input | Required |
|-------|----------|
| `settings.json` (or `--settings` path) | yes |
| `spec/settings.schema.json` | yes (shipped) |
| `docs/PROFILES.md` rules | yes (implemented in compiler code, not parsed from MD) |

## Outputs

### 1. Validation result

- exit 0: schema OK + profile invariants OK  
- exit 1: print JSON-pointer-ish paths + messages  

### 2. Effective settings (`*.resolved.json`)

Full object after Normalization (PROFILES.md § Normalization).  
Always includes:

- expanded `layers.*`
- `human.require_confirm_for` **with `secrets`**
- non-empty `loop.verify.commands` when profile requires it

### 3. Layer summary (human + agent readable)

```yaml
profile: solo-strict
layers:
  prompt: { briefing_template: default, require_goal: true }
  context: { on_session_start: [...], memory: { enabled: false } }
  harness: { preset: standard, block_force_push: true, ... }
  loop: { max_failed_attempts: 2, verify: { commands: [...] }, ... }
  graph: { mode: solo, edges: builtin:solo }
human:
  require_confirm_for: [git_push, delete, deploy, secrets]
```

Agents should prefer **resolved** file over raw `settings.json` when both exist.

## CLI (M1 — planned until shipped)

When `cli/ack_settings.py` lands:

```bash
python3 packages/agent-contract-kit/cli/ack_settings.py validate --settings settings.json
python3 packages/agent-contract-kit/cli/ack_settings.py compile --settings settings.json -o .mk-agentos/settings.resolved.json
python3 packages/agent-contract-kit/cli/ack_settings.py summary --settings settings.json
```

Until then: validate with `jsonschema` against `spec/settings.schema.json`; expansion rules in PROFILES.md are normative for implementers.

## Mapping to five layers

| Layer | Effective fields | Runtime effect (later phases) |
|-------|------------------|-------------------------------|
| Prompt | `layers.prompt` | briefing template id / require goal |
| Context | `layers.context` | session boot checklist |
| Harness | `layers.harness` + `human` | confirms + block flags |
| Loop | `layers.loop` | verify commands, wall, system-gap |
| Graph | `layers.graph` | solo vs dual-review edge set |

## Non-goals of compile

- Does not run verify commands  
- Does not install hooks  
- Does not call LLMs  
- Does not require network  

Compile is pure config → effective config.
