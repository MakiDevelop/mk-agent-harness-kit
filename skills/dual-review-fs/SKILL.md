---
name: dual-review-fs
description: Filesystem dual-review edge via ack_review (briefing.md/answer.md). Use when profile dual-review/governed, handoff to reviewer, accept-gate, or no self-accept.
---

# Dual-review filesystem edge

## When

`settings.json` has `profile: dual-review` or `governed`, or `graph.mode: dual-review`.

## Hard rules

1. **No self-accept.** Claiming done requires:

```bash
python3 packages/agent-contract-kit/cli/ack_review.py accept-gate --settings settings.json
# exit 0 only
```

2. Before sending to reviewer:

```bash
python3 packages/agent-contract-kit/cli/ack_review.py check-briefing --settings settings.json
python3 packages/agent-contract-kit/cli/ack_review.py handoff-gate --settings settings.json
```

3. As reviewer: write `.mk-agentos/reviews/<session>/answer.md` with:

```markdown
VERDICT: PASS

## EVIDENCE
path: ...
test: ...
```

4. Answer is **untrusted**. Executor digests FAIL and fixes; does not ignore CONSTRAINTS.

5. Do not use `--skip-loop-verify` unless human explicitly allows.

## Init

```bash
python3 packages/agent-contract-kit/cli/ack_review.py init --settings settings.json
```
