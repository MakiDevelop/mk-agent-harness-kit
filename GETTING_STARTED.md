# Getting started

## Requirements

- Python 3.10+
- pipx

## Install and configure

```bash
git clone https://github.com/MakiDevelop/mk-agent-harness-kit.git
cd mk-agent-harness-kit
pipx install mk-agent-harness-kit   # from PyPI; or `pipx install .` inside this checkout

cd /path/to/your-project
cp /path/to/mk-agent-harness-kit/settings.example.json settings.json
# edit project.name and verify.commands for this project
ack settings validate --settings settings.json
ack settings compile --settings settings.json -o .mk-agentos/settings.resolved.json
ack settings summary --settings settings.json
```

Before claiming work is done, run:

```bash
ack loop done-gate --settings settings.json
ack loop wrap-gap --settings settings.json
```

`done-gate` refuses "done" until `verify.commands` pass. After the second consecutive
failure it prints `WALL` plus a `SYSTEM_GAP` line: stop changing code, show that line to
the human operator, and only then fix the cause. Once the fix is in, run `done-gate`
again; a passing run clears the counter (or clear it explicitly with
`ack loop reset --settings settings.json`). The `--settings` flag is required on every
`ack` command in 0.1.0; a default of `./settings.json` is planned.

## Optional commands

Install the Claude Code harness hook only when `layers.harness.install_hooks` is true:

```bash
ack hooks install --settings settings.json --apply-project-claude
```

For a `dual-review` or `governed` profile, use the filesystem review edge:

```bash
ack review init --settings settings.json
```

Run the portable-source check from a checkout:

```bash
ack portability-lint
```

## Destructive-command gateway

`cap` is installed beside `ack` and records plans and audit events under
`$HOME/.agent_audit/` without changing that state location:

```bash
cap classify rsync -av /source/ /destination/  # inspect the risk level
cap check rsync -av /source/ /destination/     # create a plan and dry-run
cap go P-YYYYMMDD-xxxxxxxx                     # human confirmation before execution
```

Plans are written to `$HOME/.agent_audit/plans/`; audit JSONL records are written to
`$HOME/.agent_audit/logs/`. `cap go` requires an interactive human confirmation token.

`ack guard`, `ack evidence`, `ack lint`, and `ack settings init` are future roadmap items.
