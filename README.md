# mk-agent-harness-kit

> **Your AI coding agent says "done" when it isn't, edits the same file nine times, and runs `rm -rf` on a guess.**
> ACK stops that — with contracts and gates your agent can't talk its way around, not with a longer prompt.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

---

## Status

This 0.1.0 release provides `ack settings`, `ack loop`, `ack review`, `ack hooks`,
`ack portability-lint`, the `cap` destructive-command gateway, and `ack guard`.
`ack guard read-tracker`, `ack guard evidence`, `ack guard first-read-lock`,
`ack guard council-dispatch-guard`, `ack guard preset-auto-upgrade`, and
`ack guard session-onboarding`, `ack guard progress-tracker`, `ack guard no-progress-guard`,
and `ack guard state-validator` are available; `ack lint` and `ack settings init` remain planned.

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
ack settings validate   → your settings.json against the schema; profile invariants checked
ack loop done-gate      → runs YOUR verify commands; "done" is refused until they pass
ack loop wrap-gap       → prints the system-gap lines a wrap-up must carry after a wall
ack review accept-gate  → two-agent review over the filesystem; self-approval refused
ack hooks install       → opt-in Claude Code PreToolUse hook: blocks force-push / rm -rf, asks before push, delete, deploy, secrets
ack portability-lint    → the kit's own check that nothing home-lab-specific leaked in
ack guard <name>        → stateful Claude Code hook guard with a JSON decision envelope
cap check <command>     → BLOCKED / YELLOW / RED classification, plan creation, and rsync dry-run for agent review; `cap go` needs a human at a TTY
```

Roadmap (not in 0.1.0): `ack lint` (rule-file enforcement audit), `ack settings init`.

Pick a profile: `solo` (one agent, minimal), `solo-strict`, `dual-review` (executor + reviewer), `governed` (human acceptance gate). Upgrade is automatic when scope grows; downgrade needs a human.

**What ACK is not:** not a runtime, not a memory server, not a prompt library. Memory is [AMH](https://github.com/MakiDevelop/agent-memory-hall)'s job and is optional here. Dispatching work to other agents is a separate tool.

---

## Quick Start (5 minutes)

```bash
pipx install mk-agent-harness-kit        # from PyPI; puts `ack` and `cap` on PATH (or `pipx install .` from a checkout)
cd your-project
cp /path/to/settings.example.json settings.json
# edit settings.json: set verify.commands to your real test / lint / typecheck
ack settings validate --settings settings.json
ack loop done-gate --settings settings.json
```

Wire it to your agent (one block in `~/AGENTS.md`, works for any agent that reads it):

```markdown
## Harness
Before claiming a task is done: run `ack loop done-gate --settings settings.json`. If it fails, you are not done.
```

Claude Code users can additionally install hooks that call the same commands automatically:

```bash
# set layers.harness.install_hooks: true in settings.json first
ack hooks install --settings settings.json --apply-project-claude
```

The hook reads the same compiled settings `ack` writes to `.mk-agentos/`; uninstalling it changes nothing about what `ack loop` or `ack review` decide.

---

## Layout

```
settings.json          what you edit
.mk-agentos/           what ack writes (state and review sessions) — commit or ignore, your call
src/ack/_assets/spec/settings.schema.json   shipped schema (also validates settings.json)
```

Full walkthrough: **[GETTING_STARTED.md](GETTING_STARTED.md)** · Design and non-goals: **[DESIGN.md](DESIGN.md)**

---

## Related

- [agent-memory-hall](https://github.com/MakiDevelop/agent-memory-hall) — what the agent remembers between sessions
- [mk-agentos](https://github.com/MakiDevelop/mk-agentos) — the lab this kit was extracted from

License: Apache-2.0
