"""Black-box tests for stateful ``ack guard`` commands."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]

def guard(name: str, root: Path, payload: dict, *extra: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "ack.cli", "guard", name, "--project-root", str(root), "--stdin-json", *extra], input=json.dumps(payload), text=True, capture_output=True, env={**os.environ, "PYTHONPATH": str(KIT / "src"), "HOME": str(root), **(env or {})}, check=False)

class TestGuards(unittest.TestCase):
    def test_progress_tracker_and_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = str(root / "work.py")
            edit = {"session_id":"s", "tool_name":"Edit", "tool_input":{"file_path":path}}
            for _ in range(6): self.assertEqual(json.loads(guard("progress-tracker", root, edit).stdout)["decision"], "allow")
            self.assertEqual(json.loads(guard("no-progress-guard", root, edit).stdout)["decision"], "warn")
            for _ in range(6): guard("progress-tracker", root, edit)
            self.assertEqual(json.loads(guard("no-progress-guard", root, edit).stdout)["decision"], "deny")
            excluded = {"session_id":"s", "tool_name":"Write", "tool_input":{"file_path":str(root / "evidence/a")}}
            guard("progress-tracker", root, excluded)
            state = json.loads((root / ".mk-agentos/evidence/progress.json").read_text())
            self.assertNotIn(str(root / "evidence/a"), state["sessions"]["s"]["file_edits"])

    def test_progress_call_failure_noop_and_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); call = {"session_id":"s","tool_name":"Bash","tool_input":{"command":"pytest -q","nested":{"中文":"值"}},"tool_response":{"exit_code":1,"stderr":"bad"}}
            self.assertEqual(json.loads(guard("no-progress-guard", root, call).stdout)["decision"], "noop")
            for _ in range(3): guard("progress-tracker", root, call)
            self.assertEqual(json.loads(guard("no-progress-guard", root, call).stdout)["decision"], "deny")
            failure = {"session_id":"s2","tool_name":"Bash","tool_input":{"command":"pytest -q"},"tool_response":{"exit_code":1,"stderr":"bad"}}
            for _ in range(2): guard("progress-tracker", root, failure)
            self.assertEqual(json.loads(guard("no-progress-guard", root, failure).stdout)["decision"], "warn")
            edit = {"session_id":"s3","tool_name":"Edit","tool_input":{"file_path":"/x"}}
            guard("progress-tracker", root, edit)
            self.assertEqual(json.loads(guard("no-progress-guard", root, edit, env={"MK_NO_PROGRESS_EDIT_BLOCK":"1"}).stdout)["decision"], "deny")
            # legacy jq `// "0"` parity: an explicit null exit_code is "0", not a failure
            null_exit = {"session_id":"s4","tool_name":"Bash","tool_input":{"command":"pytest -q"},"tool_response":{"exit_code":None,"stderr":None}}
            guard("progress-tracker", root, null_exit)
            state = json.loads((root / ".mk-agentos/evidence/progress.json").read_text())
            self.assertEqual(state["sessions"]["s4"]["failure_by_command"], {})

    def test_progress_call_hash_golden_matches_legacy_jq(self) -> None:
        # Golden value computed with the legacy pipeline on 2026-09-08:
        #   printf 'Bash:%s' "$(jq -Sc . input.json)" | shasum -a 256 | cut -c1-16
        # for input {"z":1,"a":{"路徑":"/tmp/測試 \"q\"","n":[3,1,2]},"m":null}.
        # If this ever changes, existing progress.json files stop matching.
        from ack.guard.progress_tracker import compact_sorted, hash16
        tool_input = {"z": 1, "a": {"路徑": '/tmp/測試 "q"', "n": [3, 1, 2]}, "m": None}
        self.assertEqual(compact_sorted(tool_input), '{"a":{"n":[3,1,2],"路徑":"/tmp/測試 \\"q\\""},"m":null,"z":1}')
        self.assertEqual(hash16("Bash:" + compact_sorted(tool_input)), "54c76ca0fab65b37")

    def test_state_validator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); state = root / "project-state.yaml"; state.write_text("tasks: []\n")
            base = {"tool_name":"Edit","tool_input":{"file_path":str(state),"old_string":"","new_string":""}}
            for text in ("status: VERIFIED", "status: ACCEPTED", "tech_verified: true", "business_aligned: true"):
                payload = {**base, "tool_input":{**base["tool_input"],"new_string":text}}
                self.assertEqual(json.loads(guard("state-validator", root, payload).stdout)["decision"], "deny")
            good = {**base, "tool_input":{**base["tool_input"],"new_string":"status: VERIFIED\nverifier_id: v\nevidence_id: e"}}
            self.assertEqual(json.loads(guard("state-validator", root, good).stdout)["decision"], "allow")
            content = "tasks:\n  - id: x\n    status: VERIFIED\n"
            write = {"tool_name":"Write","tool_input":{"file_path":str(state),"content":content}}
            denied = json.loads(guard("state-validator", root, write).stdout); self.assertEqual(denied["decision"], "deny"); self.assertIn("evidence_id", denied["reason"])
            write["tool_input"]["content"] = "{ not json"; skipped = json.loads(guard("state-validator", root, write).stdout)
            self.assertEqual(skipped["decision"], "allow"); self.assertIn("unparsable", skipped["reason"])
    def test_read_tracker_allow_and_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = guard("read-tracker", root, {"tool_name": "Read", "tool_input": {"file_path": "/tmp/a"}})
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(p.stdout)["decision"], "allow")
            self.assertEqual((root / ".mk-agentos/evidence/.session-reads").read_text(), "/tmp/a\n")
            self.assertEqual(json.loads(guard("read-tracker", root, {"tool_name": "Edit"}).stdout)["decision"], "noop")

    def test_evidence_chain_and_verify_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for n in (1, 2):
                p = guard("evidence", root, {"session_id": "s", "tool_name": "Read", "tool_input": {"n": n}, "tool_response": {"exit_code": 0}})
                self.assertEqual(json.loads(p.stdout)["decision"], "allow")
            vault = root / ".mk-agentos/evidence/vault.jsonl"
            lines = [json.loads(x) for x in vault.read_text().splitlines()]
            self.assertEqual(lines[1]["prev_hash"], lines[0]["hash"])
            ok = subprocess.run([sys.executable, "-m", "ack.cli", "guard", "evidence", "--project-root", str(root), "--verify"], text=True, capture_output=True, env={**os.environ, "PYTHONPATH": str(KIT / "src")})
            self.assertEqual(ok.returncode, 0, ok.stderr)
            vault.write_text(vault.read_text().replace('"n":2', '"n":9'))
            bad = subprocess.run([sys.executable, "-m", "ack.cli", "guard", "evidence", "--project-root", str(root), "--verify"], text=True, capture_output=True, env={**os.environ, "PYTHONPATH": str(KIT / "src")})
            self.assertEqual(bad.returncode, 1)
            self.assertIn("line 2", bad.stderr)

    def test_evidence_verify_lists_all_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for n in (1, 2, 3):
                guard("evidence", root, {"tool_name": "Read", "tool_input": {"n": n}})
            vault = root / ".mk-agentos/evidence/vault.jsonl"
            lines = vault.read_text().splitlines(); lines[0] = "not json"; lines[2] = lines[2].replace('"n":3', '"n":9'); vault.write_text("\n".join(lines) + "\n")
            out = subprocess.run([sys.executable, "-m", "ack.cli", "guard", "evidence", "--project-root", str(root), "--verify"], text=True, capture_output=True, env={**os.environ, "PYTHONPATH": str(KIT / "src")})
            self.assertEqual(out.returncode, 1); self.assertIn("line 1", out.stderr); self.assertIn("line 3", out.stderr); self.assertIn("3 break(s)", out.stderr)

    def test_first_read_lock_cases(self) -> None:
        payload = {"tool_name": "Edit", "tool_input": {}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(json.loads(guard("first-read-lock", root, payload).stdout)["decision"], "allow")
            (root / "project-state.yaml").write_text("preset: standard\n")
            (root / "evidence").mkdir()
            (root / "evidence/attempt-log.jsonl").write_text("{}\n")
            denied = json.loads(guard("first-read-lock", root, payload).stdout)
            self.assertEqual(denied["decision"], "deny")
            self.assertIn("project-state.yaml", denied["reason"])
            reads = root / ".mk-agentos/evidence/.session-reads"; reads.parent.mkdir(parents=True)
            reads.write_text(f"{root / 'project-state.yaml'}\n{root / 'evidence/attempt-log.jsonl'}\n")
            self.assertEqual(json.loads(guard("first-read-lock", root, payload).stdout)["decision"], "allow")
            self.assertEqual(json.loads(guard("first-read-lock", root, {"tool_name":"Bash","tool_input":{"command":"git status --short"}}).stdout)["decision"], "allow")
            (root / "project-state.yaml").write_text("preset: light\n")
            self.assertEqual(json.loads(guard("first-read-lock", root, payload).stdout)["decision"], "allow")

    def test_governed_requires_context_index(self) -> None:
        # Legacy parity: optional files (logs, context-index) are required only
        # when present; an absent optional file never blocks by itself.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "evidence").mkdir()
            (root / "project-state.yaml").write_text("preset: governed\n")
            for name in ("attempt-log.jsonl", "decision-log.jsonl"):
                (root / "evidence" / name).write_text("{}\n")
            reads = root / ".mk-agentos/evidence/.session-reads"; reads.parent.mkdir(parents=True)
            reads.write_text("\n".join(str(x) for x in [root / "project-state.yaml", root / "evidence/attempt-log.jsonl", root / "evidence/decision-log.jsonl"]) + "\n")
            # context-index.yaml absent → not required → allow
            out = json.loads(guard("first-read-lock", root, {"tool_name":"Write","tool_input":{}}).stdout)
            self.assertEqual(out["decision"], "allow")
            # context-index.yaml present but unread → deny naming it
            (root / "context-index.yaml").write_text("index: []\n")
            out = json.loads(guard("first-read-lock", root, {"tool_name":"Write","tool_input":{}}).stdout)
            self.assertEqual(out["decision"], "deny")
            self.assertIn("context-index.yaml", out["reason"])

    def test_standard_without_attempt_log_only_requires_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "project-state.yaml").write_text("preset: standard\n")
            denied = json.loads(guard("first-read-lock", root, {"tool_name":"Edit","tool_input":{}}).stdout)
            self.assertEqual(denied["decision"], "deny")
            self.assertNotIn("attempt-log", denied["reason"])
            reads = root / ".mk-agentos/evidence/.session-reads"; reads.parent.mkdir(parents=True)
            reads.write_text(f"{root / 'project-state.yaml'}\n")
            self.assertEqual(json.loads(guard("first-read-lock", root, {"tool_name":"Edit","tool_input":{}}).stdout)["decision"], "allow")

    def test_settings_evidence_dir_and_planned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); settings = root / "settings.json"
            settings.write_text(json.dumps({"profile":"solo", "layers":{"harness":{"evidence_dir":"state"}}}))
            p = guard("read-tracker", root, {"tool_name":"Read","tool_input":{"file_path":"x"}}, "--settings", str(settings))
            self.assertTrue((root / "state/.session-reads").is_file())
            self.assertEqual(json.loads(guard("no-progress-guard", root, {}).stdout)["decision"], "noop")

    def test_adapter_ack_missing_fails_open_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); evidence = root / "evidence"
            p = subprocess.run(["bash", str(KIT / "adapters/claude-code/ack-guard-hook.sh"), "first-read-lock"], input='{"tool_name":"Edit"}', text=True, capture_output=True, env={"PATH":"/usr/bin:/bin", "ACK_EVIDENCE_DIR":str(evidence), "HOME":str(root)}, check=False)
            self.assertEqual(p.returncode, 0)
            self.assertTrue((evidence / "guard-errors.log").is_file())

    def test_council_dispatch_guard_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = [("codex exec x", "deny"), ("timeout 30 codex exec x", "deny"), ("timeout 30s codex exec x", "deny"), ("nice -n 10 gemini --print x", "deny"), ("/usr/local/bin/codex exec x", "deny"), ("FOO=1 gemini -p x", "deny"), ("agy --prompt=x", "deny"), ("codex --help", "allow"), ("council-dispatch --seat codex", "allow"), ("cat <<'EOF'\ncouncil-dispatch\nEOF", "allow"), ('git commit -m "codex exec"', "allow"), ("codex exec x", "noop")]
            for command, decision in cases:
                tool = "Bash" if decision != "noop" else "Read"
                out = json.loads(guard("council-dispatch-guard", root, {"tool_name": tool, "tool_input": {"command": command}}).stdout)
                self.assertEqual(out["decision"], decision, command)

    def test_council_dispatch_guard_honours_custom_blocked_clis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); settings = root / "settings.json"
            settings.write_text(json.dumps({"profile": "solo", "layers": {"harness": {"council": {"blocked_clis": {"claude": ["-p"]}}}}}))
            payload = {"tool_name": "Bash", "tool_input": {"command": "claude -p 'do it'"}}
            out = json.loads(guard("council-dispatch-guard", root, payload, "--settings", str(settings)).stdout)
            self.assertEqual(out["decision"], "deny")
            self.assertIn("claude", out["reason"])
            # defaults still apply alongside the custom entry
            out = json.loads(guard("council-dispatch-guard", root, {"tool_name": "Bash", "tool_input": {"command": "gemini -p x"}}, "--settings", str(settings)).stdout)
            self.assertEqual(out["decision"], "deny")

    def test_preset_auto_upgrade_and_preserves_other_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "evidence").mkdir()
            original = "# keep\nproject: demo\npreset: light # old\ntasks:\n  - id: one\n    status: BLOCKED\n    name: wait\n"
            (root / "project-state.yaml").write_text(original)
            out = json.loads(guard("preset-auto-upgrade", root, {}).stdout)
            self.assertEqual(out["decision"], "warn")
            self.assertEqual((root / "project-state.yaml").read_text().replace("preset: standard\n", "preset: light # old\n"), original)
            self.assertEqual(json.loads((root / "evidence/decision-log.jsonl").read_text())["to"], "standard")

    def test_preset_auto_upgrade_other_paths_and_noops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "evidence").mkdir()
            (root / "project-state.yaml").write_text("preset: standard\ntasks: []\n")
            (root / "evidence/attempt-log.jsonl").write_text('{"status":"failed"}\n{"status":"failed"}\n')
            self.assertEqual(json.loads(guard("preset-auto-upgrade", root, {}).stdout)["decision"], "warn")
            (root / "project-state.yaml").write_text("preset: standard\ntasks: []\n")
            (root / "evidence/attempt-log.jsonl").write_text("")
            (root / "evidence/progress.json").write_text('{"file_edits":{"a":3}}')
            self.assertEqual(json.loads(guard("preset-auto-upgrade", root, {}).stdout)["decision"], "warn")
            (root / "project-state.yaml").write_text("preset: governed\n")
            self.assertEqual(json.loads(guard("preset-auto-upgrade", root, {}).stdout)["decision"], "noop")
            self.assertEqual(json.loads(guard("preset-auto-upgrade", Path(tmp) / "none", {}).stdout)["decision"], "noop")

    def test_session_onboarding_extra_command_only_from_env(self) -> None:
        # Security: a repository-controlled settings.json must never be able to
        # run a command at SessionStart; only the operator's environment can.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "evidence").mkdir()
            (root / "project-state.yaml").write_text("project: demo\npreset: light\n")
            settings = root / "settings.json"
            settings.write_text(json.dumps({"profile": "solo", "layers": {"harness": {"onboarding": {"extra_command": "echo INJECTED_FROM_REPO"}}}}))
            out = json.loads(guard("session-onboarding", root, {}, "--settings", str(settings), env={"ACK_ONBOARDING_EXTRA_COMMAND": ""}).stdout)
            self.assertNotIn("INJECTED_FROM_REPO", out.get("context") or "")
            out = json.loads(guard("session-onboarding", root, {}, env={"ACK_ONBOARDING_EXTRA_COMMAND": "echo FROM_OPERATOR_ENV"}).stdout)
            self.assertIn("FROM_OPERATOR_ENV", out["context"])

    def test_session_onboarding_capsule_noop_and_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); evidence = root / "evidence"; evidence.mkdir(); (evidence / ".session-reads").write_text("old\n")
            (root / "project-state.yaml").write_text("project: demo\npreset: standard\ntasks:\n  - id: a\n    status: BLOCKED\n    name: stalled\n    blocked_reason: waiting\n")
            (evidence / "attempt-log.jsonl").write_text('{"status":"failed","ts":"t","description":"bad"}\n')
            (evidence / "decision-log.jsonl").write_text('{"type":"challenge","status":"open","challenger":"c","description":"q"}\n')
            out = json.loads(guard("session-onboarding", root, {}, env={"ACK_EVIDENCE_DIR": str(evidence)}).stdout)
            self.assertEqual(out["decision"], "allow"); self.assertIn("Project: demo", out["context"]); self.assertEqual((evidence / ".session-reads").read_text(), "")
            self.assertEqual(json.loads(guard("session-onboarding", Path(tmp) / "none", {}, env={"ACK_EVIDENCE_DIR": str(evidence)}).stdout)["decision"], "noop")
            (root / "project-state.yaml").write_text("project: demo\npreset: standard\ntasks:\n" + "".join(f"  - id: {i}\n    status: BLOCKED\n    name: {'x'*1000}\n" for i in range(20)))
            self.assertLessEqual(len(json.loads(guard("session-onboarding", root, {}, env={"ACK_EVIDENCE_DIR": str(evidence)}).stdout)["context"].encode()), 8192)

    def test_adapter_session_context_and_env_evidence_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "project-state.yaml").write_text("project: demo\npreset: light\n")
            bin_dir = root / "bin"; bin_dir.mkdir()
            ack = bin_dir / "ack"; ack.write_text(f"#!/usr/bin/env bash\nexec {sys.executable} -m ack.cli \"$@\"\n"); ack.chmod(0o755)
            env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "PYTHONPATH": str(KIT / "src"), "ACK_EVIDENCE_DIR": str(root / "env-evidence"), "CLAUDE_PROJECT_DIR": str(root), "HOME": str(root)}
            settings = root / "settings.json"; settings.write_text('{"profile":"solo","layers":{"harness":{"evidence_dir":"settings-evidence"}}}')
            self.assertTrue((root / "env-evidence/.session-reads").parent.exists() is False)
            p = guard("read-tracker", root, {"tool_name":"Read","tool_input":{"file_path":"x"}}, "--settings", str(settings), env=env)
            self.assertEqual(p.returncode, 0); self.assertTrue((root / "env-evidence/.session-reads").is_file())
            p = subprocess.run(["bash", str(KIT / "adapters/claude-code/ack-guard-hook.sh"), "session-onboarding"], input='{"hook_event_name":"SessionStart"}', text=True, capture_output=True, env=env, cwd=root)
            self.assertIn("additionalContext", p.stdout)
