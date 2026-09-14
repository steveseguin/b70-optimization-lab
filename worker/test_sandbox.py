"""CPU-only tests. Git fixtures are ordinary temporary repositories, not worktrees."""
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("worker_sandbox", Path(__file__).with_name("sandbox.py"))
S = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(S)
IMAGE = "sha256:" + "a" * 64
CID = "b" * 64


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "original"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        (self.repo / "hello.txt").write_text("first\nsecond\n")
        (self.repo / "delete me.txt").write_text("delete this\n")
        (self.repo / "script.sh").write_text("#!/bin/sh\nexit 0\n")
        self.git("add", "--", ".")
        self.git("commit", "-qm", "fixture")
        self.commit = self.git("rev-parse", "HEAD").decode().strip()
        self.run = self.root / "run"

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def snapshot(self):
        return S.prepare_snapshot(self.repo, self.commit, self.run)

    def sandbox(self):
        self.snapshot()
        with patch.object(S.os, "getuid", return_value=1000), patch.object(S.os, "getgid", return_value=1000):
            env = S.DockerSandbox(self.run, IMAGE)
        env.image_id, env.container_id = IMAGE, CID
        return env


class SnapshotTests(Fixture):
    def test_snapshot_pins_source_and_has_no_git(self):
        metadata = self.snapshot()
        self.assertEqual(metadata["source_commit"], self.commit)
        self.assertFalse((self.run / "workspace/.git").exists())
        self.assertEqual(S._regular_tree(self.run / "baseline"), S._regular_tree(self.run / "workspace"))
        self.assertEqual(self.git("status", "--porcelain"), b"")

    def test_dirty_source_mutable_ref_and_existing_run_rejected(self):
        with self.assertRaises(S.SandboxError):
            S.prepare_snapshot(self.repo, "HEAD", self.run)
        (self.repo / "untracked").write_text("preserve")
        with self.assertRaises(S.SandboxError):
            self.snapshot()
        (self.repo / "untracked").unlink()
        self.snapshot()
        with self.assertRaises(FileExistsError):
            self.snapshot()

    def test_source_symlink_rejected(self):
        (self.repo / "link").symlink_to("/etc/passwd")
        self.git("add", "--", "link")
        self.git("commit", "-qm", "link")
        self.commit = self.git("rev-parse", "HEAD").decode().strip()
        with self.assertRaises(S.SandboxError):
            self.snapshot()

    def test_output_inside_repo_or_symlink_ancestor_rejected_before_writes(self):
        with self.assertRaises(S.SandboxError):
            S.prepare_snapshot(self.repo, self.commit, self.repo / "forbidden-run")
        self.assertFalse((self.repo / "forbidden-run").exists())
        (self.root / "alias").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(S.SandboxError):
            S.prepare_snapshot(self.repo, self.commit, self.root / "alias/run")
        self.assertFalse(self.run.exists())
        self.assertEqual(self.git("status", "--porcelain"), b"")

    def test_archive_escape_and_links_rejected(self):
        for number, (name, kind) in enumerate((("../escape", tarfile.REGTYPE),
                                              ("/escape", tarfile.REGTYPE),
                                              ("link", tarfile.SYMTYPE),
                                              ("link", tarfile.LNKTYPE),
                                              ("device", tarfile.CHRTYPE),
                                              (".git/config", tarfile.REGTYPE))):
            archive = self.root / f"bad-{number}.tar"
            with tarfile.open(archive, "w") as tar:
                info = tarfile.TarInfo(name)
                info.type, info.linkname = kind, "/etc/passwd"
                tar.addfile(info)
            with self.subTest(name=name, kind=kind), self.assertRaises(S.SandboxError):
                S.safe_extract(archive, self.root / f"unpack-{number}")
        self.assertFalse((self.root / "escape").exists())

    def test_size_limit(self):
        with patch.object(S, "MAX_SOURCE_BYTES", 1), self.assertRaises(S.SandboxError):
            self.snapshot()


class PatchTests(Fixture):
    def test_exported_patch_applies_text_add_delete_mode_binary_and_odd_paths(self):
        self.snapshot()
        workspace = self.run / "workspace"
        (workspace / "hello.txt").write_text("first\nchanged\n")
        (workspace / "delete me.txt").unlink()
        (workspace / "script.sh").chmod(0o755)
        (workspace / "new space.txt").write_text("new file\n")
        (workspace / "unicode-é\tfile.txt").write_text("odd path\n")
        (workspace / "new binary.dat").write_bytes(b"\x00\xffbinary\x00")
        receipt = S.export_patch(self.run)
        replay = self.root / "replay"
        shutil.copytree(self.run / "baseline", replay)
        subprocess.run(["git", "apply", "--check", str(self.run / "changes.patch")], cwd=replay, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "apply", str(self.run / "changes.patch")], cwd=replay, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(S._regular_tree(replay), S._regular_tree(workspace))
        self.assertEqual(len(receipt["changed_files"]), 6)
        self.assertTrue(receipt["source_repo_unchanged"])
        self.assertEqual(self.git("status", "--porcelain"), b"")

    def test_symlink_baseline_and_original_changes_rejected(self):
        self.snapshot()
        path = self.run / "workspace/link"
        path.symlink_to("/etc/passwd")
        with self.assertRaises(S.SandboxError):
            S.export_patch(self.run)
        path.unlink()
        (self.run / "baseline/hello.txt").write_text("bad baseline")
        with self.assertRaises(S.SandboxError):
            S.export_patch(self.run)
        shutil.copyfile(self.repo / "hello.txt", self.run / "baseline/hello.txt")
        (self.repo / "hello.txt").write_text("original edited elsewhere")
        with self.assertRaises(S.SandboxError):
            S.export_patch(self.run)

    def test_export_refuses_live_sandbox(self):
        self.snapshot()
        (self.run / "sandbox.json").write_text(json.dumps({"container_id": CID, "stopped": False}))
        with self.assertRaises(S.SandboxError):
            S.export_patch(self.run)


class ContainerTests(Fixture):
    def identity(self, env, running=True):
        return {"Id": CID, "Image": IMAGE, "Name": "/" + env.name,
                "Config": {"Labels": {"local-coding-worker.owner": env.owner}}, "State": {"Running": running}}

    def test_create_command_is_cpu_network_and_mount_isolated(self):
        env = self.sandbox()
        args = env.create_command()
        for flag, value in (("--network", "none"), ("--cap-drop", "ALL"), ("--pids-limit", "128"),
                            ("--cpus", "2"), ("--memory", "2g"), ("--memory-swap", "2g"),
                            ("--security-opt", "no-new-privileges")):
            self.assertEqual(args[args.index(flag) + 1], value)
        self.assertIn("--read-only", args)
        mounts = [args[i + 1] for i, value in enumerate(args) if value == "--mount"]
        self.assertEqual(mounts, [f"type=bind,src={env.run_dir / 'workspace'},dst=/workspace"])
        self.assertNotIn("--device", args)
        self.assertNotIn("--gpus", args)
        self.assertNotIn("--privileged", args)
        self.assertNotIn("docker.sock", " ".join(args))
        self.assertNotIn(str(self.repo), " ".join(args))
        self.assertEqual(set(S.CHILD_ENV), {"PATH", "LC_ALL"})

    def test_mutable_image_and_root_user_rejected(self):
        self.snapshot()
        with self.assertRaises(S.SandboxError):
            S.DockerSandbox(self.run, "python:latest")
        with patch.object(S.os, "getuid", return_value=0), self.assertRaises(S.SandboxError):
            S.DockerSandbox(self.run, IMAGE)

    def test_identity_mismatch_never_stops_any_container(self):
        env = self.sandbox()
        wrong = self.identity(env)
        wrong["Image"] = "sha256:" + "c" * 64
        calls = []
        def docker(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, json.dumps([wrong]).encode(), b"")
        with patch.object(env, "_docker", side_effect=docker), self.assertRaises(S.SandboxError):
            env.stop()
        self.assertEqual(calls, [("inspect", CID)])
        self.assertFalse(env.stop_attempted)

    def test_single_owned_stop_and_no_repeat(self):
        env = self.sandbox()
        calls = []
        def docker(*args, **kwargs):
            calls.append(args)
            running = not any(call[0] == "stop" for call in calls)
            return subprocess.CompletedProcess(args, 0, json.dumps([self.identity(env, running)]).encode(), b"")
        with patch.object(env, "_docker", side_effect=docker):
            env.stop()
            env.stop()
        self.assertEqual([c for c in calls if c[0] == "stop"], [("stop", "--time", "10", CID)])
        self.assertTrue(env.stopped)

    def test_timeout_aborts_and_stops_before_another_command(self):
        env = self.sandbox()
        result = {"output": "", "returncode": 124, "timed_out": False}
        with patch.object(env, "_verify_identity", return_value=self.identity(env)), \
             patch.object(S, "_bounded_command", return_value=result) as execute, \
             patch.object(env, "stop") as stop:
            with self.assertRaises(S.SandboxError):
                env.execute({"command": "sleep 999"})
            with self.assertRaises(S.SandboxError):
                env.execute({"command": "echo should-not-run"})
            self.assertEqual(execute.call_count, 1)
            stop.assert_called_once()
            args = execute.call_args.args[0]
            self.assertIn("/usr/bin/timeout", args)
            self.assertIn("--kill-after=5", args)

    def test_only_exact_command_submits_not_command_output(self):
        env = self.sandbox()
        class Submitted(Exception):
            pass
        exceptions = types.ModuleType("minisweagent.exceptions")
        exceptions.Submitted = Submitted
        result = {"output": "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n", "returncode": 0, "timed_out": False}
        with patch.object(env, "_verify_identity", return_value=self.identity(env)), \
             patch.object(S, "_bounded_command", return_value=result) as execute, \
             patch.dict(sys.modules, {"minisweagent.exceptions": exceptions}):
            self.assertEqual(env.execute({"command": "cat a-file"}), result)
            with self.assertRaises(Submitted):
                env.execute({"command": S.COMPLETE})
            self.assertEqual(execute.call_count, 1)

    def test_bounded_output_drains_and_truncates(self):
        result = S._bounded_command([sys.executable, "-c", "print('x'*50000)"], 5)
        self.assertEqual(result["returncode"], 0)
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["output_bytes_received"], 50001)
        self.assertLess(len(result["output"]), 10100)

    def test_host_wall_timeout_kills_tool(self):
        result = S._bounded_command([sys.executable, "-c", "import time; time.sleep(10)"], 0.05)
        self.assertTrue(result["timed_out"])
        self.assertNotEqual(result["returncode"], 0)

    def test_real_default_agent_completion_protocol(self):
        try:
            from minisweagent.agents.default import DefaultAgent
        except ImportError:
            self.skipTest("install the worker's pinned mini-swe-agent to run this integration check")
        env = self.sandbox()
        class CompletingModel:
            def query(self, messages):
                return {"role": "assistant", "content": "complete", "extra": {"actions": [{"command": S.COMPLETE}]}}
            def format_message(self, **kwargs):
                return kwargs
            def get_template_vars(self):
                return {}
            def serialize(self):
                return {}
        with patch.object(env, "_verify_identity", return_value=self.identity(env)), \
             patch.object(S, "_bounded_command") as execute:
            agent = DefaultAgent(CompletingModel(), env, system_template="You are a fixture.",
                                 instance_template="{{task}}", step_limit=2, cost_limit=0)
            result = agent.run("Complete without a shell command")
        self.assertEqual(result["exit_status"], "Submitted")
        self.assertEqual(agent.n_calls, 1)
        self.assertEqual(agent.messages[-1]["role"], "exit")
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
