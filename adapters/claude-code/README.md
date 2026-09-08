# Claude Code capability-gateway hook

`pre-bash-cap-gateway.sh` is a small routing hook: it sends `rsync`, `rm`, `mv`,
`chmod`, and `chown` commands to the `cap` command available on `PATH`. The hook has
no risk-classification or confirmation logic; those decisions remain in the packaged
`cap` tools.

Install the kit first so `cap`, `safe_rsync`, and `safe_move` are on `PATH`, then add
the hook command to Claude Code settings, for example:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "/path/to/pre-bash-cap-gateway.sh" }
        ]
      }
    ]
  }
}
```

Keep the hook script outside this adapter documentation or provide it from your own
managed configuration; this repository deliberately does not duplicate a host hook.

## Stateful `ack guard` hooks

`ack-guard-hook.sh` is a thin adapter: it forwards Claude's original hook JSON to
`ack guard` and translates only its envelope back to Claude's permission protocol.
Point `ACK_EVIDENCE_DIR` at an existing evidence directory if continuity with a
legacy vault is needed. Example `settings.json` wiring:

```json
{
  "hooks": {
    "PreToolUse": [{"matcher":"Edit|Write|Bash","hooks":[{"type":"command","command":"/path/to/ack-guard-hook.sh first-read-lock"}]}],
    "PostToolUse": [
      {"matcher":"Read","hooks":[{"type":"command","command":"/path/to/ack-guard-hook.sh read-tracker"}]},
      {"matcher":"*","hooks":[{"type":"command","command":"/path/to/ack-guard-hook.sh evidence"}]}
    ]
  }
}
```

If `ack` itself errors, the adapter allows the tool and appends the diagnostic to
`guard-errors.log`; it does not turn adapter failure into a user lockout.
