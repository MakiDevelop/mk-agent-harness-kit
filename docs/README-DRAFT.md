<!-- 草稿註：現有 ACK 只有 settings / loop / review / hooks / portability-lint 五支。
     `ack settings init`、`ack guard *`、`ack evidence *`、`ack lint *`、`cap` 進 pipx 都是階段 1–4 新增，README 寫的是完成後的樣子。 -->
# mk-agent-harness-kit

> **Your AI coding agent says "done" when it isn't, edits the same file nine times, and runs `rm -rf` on a guess.**
> ACK stops that — with contracts and gates your agent can't talk its way around, not with a longer prompt.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

---

## The Problem

Everyone who runs an agent for more than an afternoon has said these sentences out loud:

1. "You didn't run the tests. Don't tell me it's done."
2. "You've edited that file six times. Stop and tell me what's wrong."
3. "Read the config before you change it."
4. "Don't push. Don't delete. Ask first."
5. "I told you that yesterday."

Prompts don't fix this. The agent agrees, then forgets. What fixes it is a **gate the agent has to pass**, enforced by a program that doesn't care how confident the agent sounds.

ACK is that gate. It doesn't run your agent. It sits next to whatever agent you already use — Claude Code, Codex, Gemini CLI, a local model — and refuses to let it claim what it can't prove.

---

## What ACK Does

One `settings.json`. One command `ack`. Everything it decides is written to `.mk-agentos/` as plain JSON you can read and diff.

```
ack loop done-gate      → runs YOUR verify commands; "done" is refused until they pass
ack guard no-progress   → same file edited N times / same failing command → BLOCKED
ack guard first-read    → mutation locked until the agent has read the ground-truth files
ack guard state         → VERIFIED needs a verifier id and an evidence id, or it doesn't go in
cap check <command>     → GREEN / YELLOW / RED classification for destructive shell commands
ack evidence verify     → hash-chained log of every tool call; tamper shows
ack lint                → your CLAUDE.md / AGENTS.md: which rules are actually enforced, which are wishes
ack review accept-gate  → two-agent review over the filesystem; self-approval refused
```

Pick a profile: `solo` (one agent, minimal), `solo-strict`, `dual-review` (executor + reviewer), `governed` (human acceptance gate). Upgrade is automatic when scope grows; downgrade needs a human.

**What ACK is not:** not a runtime, not a memory server, not a prompt library. Memory is [AMH](https://github.com/MakiDevelop/agent-memory-hall)'s job and is optional here. Dispatching work to other agents is a separate tool.

---

## Quick Start (5 minutes)

```bash
pipx install mk-agent-harness-kit        # puts `ack` and `cap` on PATH
cd your-project
ack settings init                        # writes settings.json from the solo profile
# edit settings.json: set verify.commands to your real test / lint / typecheck
ack settings validate
ack loop done-gate                       # try it: fails until verify.commands pass
```

Wire it to your agent (one block in `~/AGENTS.md`, works for any agent that reads it):

```markdown
## Harness
Before claiming a task is done: run `ack loop done-gate`. If it fails, you are not done.
Before any shell command that deletes, moves, or pushes: run `cap check "<command>"`.
```

Claude Code users can additionally install hooks that call the same commands automatically:

```bash
ack hooks install --apply-project-claude
```

The hooks hold no logic. They call `ack`. Uninstalling them changes nothing about what `ack` decides.

---

## A real run (Codex)

```
$ codex exec "fix the failing auth test" 
...
$ ack loop done-gate
verify: pytest -q                 FAIL (2 failed, 41 passed)
done-gate: REFUSED — wall counter 1/2
$ ack loop status
consecutive_failures: 1   policy: stop at 2, report system-gap
```

The second refusal prints a system-gap line for your wrap-up instead of letting the agent try a third time.

---

## Layout

```
settings.json          what you edit
.mk-agentos/           what ack writes (state, evidence, review sessions) — commit or ignore, your call
adapters/claude-code   thin hooks; adapters/codex, adapters/gemini: how to wire each
spec/settings.schema.json
```

Full walkthrough: **[GETTING_STARTED.md](GETTING_STARTED.md)** · Design and non-goals: **[docs/DESIGN.md](docs/DESIGN.md)**

---

## Related

- [agent-memory-hall](https://github.com/MakiDevelop/agent-memory-hall) — what the agent remembers between sessions
- [mk-agentos](https://github.com/MakiDevelop/mk-agentos) — the lab this kit was extracted from

License: Apache-2.0
