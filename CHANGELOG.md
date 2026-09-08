# Changelog

All notable changes to mk-agent-harness-kit. Format loosely follows Keep a Changelog.

## 0.1.0 — 2026-09-08

First public release. Extracted from `mk-agentos/packages/agent-contract-kit` (history
preserved via `git subtree split`), then made installable and given the guards.

### Added
- Single console entry point `ack` with subcommands `settings`, `loop`, `review`, `hooks`,
  `portability-lint`, `guard`.
- `ack guard <name> --stdin-json`: nine Claude Code hook guards ported 1:1 from the
  original bash hooks, each emitting one JSON decision envelope
  (`allow | deny | ask | warn | noop`): `read-tracker`, `evidence`, `first-read-lock`,
  `council-dispatch-guard`, `preset-auto-upgrade`, `session-onboarding`,
  `progress-tracker`, `no-progress-guard`, `state-validator`.
- `ack guard evidence --verify`: walks the hash chain and lists every break.
- Capability gateway shipped as package data and exposed on PATH:
  `cap`, `cap-check`, `cap-go`, `safe_move`, `safe_rsync`.
- Thin Claude Code adapter `adapters/claude-code/ack-guard-hook.sh` (no decision logic;
  fails open and logs to `guard-errors.log` if `ack` itself errors).
- Shipped assets under `src/ack/_assets/` (settings schema, example settings, harness hook,
  YAML templates) resolved with `importlib.resources`.
- `layers.harness.evidence_dir`, `layers.harness.council`, `layers.harness.no_progress`
  settings keys; `ACK_EVIDENCE_DIR`, `MK_NO_PROGRESS_*`, `ACK_ONBOARDING_EXTRA_COMMAND`
  environment overrides.
- `docs/GUARDS.md`; CI on Python 3.10–3.13.

### Compatibility
- Evidence records hash byte-for-byte like the legacy `jq`-based hook (verified against a
  42,305-line real vault: zero self-hash mismatches).
- `progress.json` schema v2 and its 16-char hashes match the legacy tracker (`jq -Sc`
  canonicalisation reproduced with `json.dumps(sort_keys=True, ...)`).
- Legacy `cli/ack_*.py` paths remain as deprecated shims for one release.

### Fixed
- Evidence vault locking now uses `fcntl.flock`; the legacy hook relied on the `flock`
  binary, which does not exist on macOS, so concurrent writes silently interleaved.
- `datetime.timezone.utc` instead of `datetime.UTC` to honour `requires-python >= 3.10`.

### Security
- `session-onboarding` no longer accepts an extra command from `settings.json`
  (repository-controlled input executed automatically at SessionStart). The optional
  command is read only from the operator's environment (`ACK_ONBOARDING_EXTRA_COMMAND`);
  a settings file still carrying `layers.harness.onboarding` now fails validation.

### Known limits
- Project-state parsing is a deliberate minimal subset (top-level scalars, `tasks:` list
  of flat mappings, one nested `acceptance_criteria` list). Unsupported YAML fails open in
  `state-validator`, as the legacy hook did.
- `council-dispatch-guard` is string analysis, not a shell parser (legacy parity).
- The Claude adapter script is not part of the wheel yet; use it from a checkout.
