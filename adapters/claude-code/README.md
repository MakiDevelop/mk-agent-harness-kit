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
