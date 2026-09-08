# Getting started

## Requirements

- Python 3.10+
- pipx

## Install and configure

```bash
git clone https://github.com/MakiDevelop/mk-agent-harness-kit.git
cd mk-agent-harness-kit
pipx install .

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
