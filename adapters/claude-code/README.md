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
    "PreToolUse": [
      {"matcher":"Edit|Write|Bash","hooks":[{"type":"command","command":"/path/to/ack-guard-hook.sh first-read-lock"}]},
      {"matcher":"Bash","hooks":[{"type":"command","command":"/path/to/ack-guard-hook.sh council-dispatch-guard"},{"type":"command","command":"/path/to/ack-guard-hook.sh no-progress-guard"}]},
      {"matcher":"Edit|Write","hooks":[{"type":"command","command":"/path/to/ack-guard-hook.sh state-validator"},{"type":"command","command":"/path/to/ack-guard-hook.sh no-progress-guard"}]}
    ],
    "PostToolUse": [
      {"matcher":"Read","hooks":[{"type":"command","command":"/path/to/ack-guard-hook.sh read-tracker"}]},
      {"matcher":"Bash|Edit|Write","hooks":[{"type":"command","command":"/path/to/ack-guard-hook.sh preset-auto-upgrade"}]},
      {"matcher":"Bash|Edit|Write","hooks":[{"type":"command","command":"/path/to/ack-guard-hook.sh progress-tracker"}]},
      {"matcher":"*","hooks":[{"type":"command","command":"/path/to/ack-guard-hook.sh evidence"}]}
    ],
    "SessionStart": [
      {"hooks":[{"type":"command","command":"/path/to/ack-guard-hook.sh session-onboarding"}]}
    ]
  }
}
```

The adapter takes `hook_event_name` from the payload, or maps each guard to its
documented event when absent. `ACK_ONBOARDING_EXTRA_COMMAND` (optional) may be exported
in the same wiring to append one operator-supplied line to the SessionStart capsule; it
is deliberately not a `settings.json` key.

If `ack` itself errors, the adapter allows the tool and appends the diagnostic to
`guard-errors.log`; it does not turn adapter failure into a user lockout.
