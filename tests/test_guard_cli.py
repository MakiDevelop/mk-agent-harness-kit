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
