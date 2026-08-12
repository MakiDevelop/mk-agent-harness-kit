# Graph / dual-review filesystem adapter (M4)

## Purpose

When `graph.mode` is `dual-review` (profiles `dual-review` / `governed`):

1. Executor fills **briefing.md** (edge contract sections)  
2. Loop verify must be green (`ack_loop done-gate`)  
3. **handoff-gate** opens path to reviewer  
4. Reviewer writes **answer.md** with `VERDICT:` + evidence  
5. **accept-gate** allows ship only if reviewer PASS (no self-accept)

## CLI

```bash
python3 packages/agent-contract-kit/cli/ack_review.py init --settings settings.json
# edit .mk-agentos/reviews/<id>/briefing.md
python3 packages/agent-contract-kit/cli/ack_review.py check-briefing --settings settings.json
python3 packages/agent-contract-kit/cli/ack_review.py handoff-gate --settings settings.json
# reviewer writes answer.md
python3 packages/agent-contract-kit/cli/ack_review.py check-answer --settings settings.json
python3 packages/agent-contract-kit/cli/ack_review.py accept-gate --settings settings.json
python3 packages/agent-contract-kit/cli/ack_review.py status --settings settings.json
```

## Briefing required sections

| Section | Meaning |
|---------|---------|
| TASK | work to do |
| CONTEXT | allowed context |
| CONSTRAINTS | must-not |
| VERIFY | acceptance / commands |
| PATHS_OR_DIFF_STAT | files or `git diff --stat` |

Aliases accepted: `PATHS`, `DIFF`, `FILES`, etc.

## Answer required

- Line: `VERDICT: PASS` | `FAIL` | `PASS_WITH_NITS`  
- Evidence markers: `## EVIDENCE`, `evidence:`, or path/diff/test tokens  

## Layout

```text
{project}/.mk-agentos/reviews/
  current.json
  <session_id>/
    briefing.md
    answer.md
    meta.json
```

## Relation to other layers

| Layer | Tool |
|-------|------|
| Settings / graph.mode | `ack_settings` |
| Loop verify before handoff | `ack_loop done-gate` (called by handoff-gate) |
| Dual-review edge | `ack_review` |
| Bash danger | `ack_hooks` (optional) |

## Limits

- Does not invoke reviewer models (orchestration is human/agent runtime)  
- Markdown structure heuristics, not a full AST  
- `custom` mode allowed if agents map present; builtin edge YAML not required  
