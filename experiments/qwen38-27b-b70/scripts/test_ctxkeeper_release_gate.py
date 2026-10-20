"""CPU-only evidence and cleanup-boundary tests; no Docker/systemd/GPU calls."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
CHECK = HERE / "ctxkeeper-release-gate-check.py"
RUNNER = HERE / "ctxkeeper-release-gate.sh"
spec = importlib.util.spec_from_file_location("release_gate", CHECK)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "verifier").mkdir()
        (self.root / "agent").mkdir()
        self.details = {"void": False, "n": 40, "fixed": 40, "clean": 38,
                        "audit": {"asked": 7, "right": 6}}
        self.put("verifier/details.json", self.details)
        self.put("agent/timing.json", [{"cmd": "work"}])
        self.put("agent/usage.json", {"hit_lm_call_cap": False})
        self.put("status.json", {"gates": {g: {"status": "not_run"} for g in ("G1", "G2", "G3", "G4")}})

    def put(self, path, obj):
        (self.root / path).write_text(json.dumps(obj))

    def command(self, *args, stdin=""):
        return subprocess.run([sys.executable, "-B", str(CHECK), *map(str, args)],
                              input=stdin, text=True, capture_output=True)

    def demo(self, passed=4, history=300000, total=4):
        log = self.root / "demo.out"
        checks = ["[PASS] check" for _ in range(passed)] + ["[FAIL] check" for _ in range(total - passed)]
        log.write_text("\n".join(checks) + f"\n{passed}/{total} checks passed; history about {history:,} tokens\n")
        return str(log)

    def test_g1_registered_boundaries(self):
        self.assertTrue(gate.g1(self.root, 2700)[0])
        self.assertFalse(gate.g1(self.root, 2701)[0])
        for field, value in (("n", 39), ("fixed", 39), ("clean", 37), ("void", True),
                             ("audit", {"asked": 7, "right": 5}), ("audit", {"asked": 0, "right": 6})):
            with self.subTest(field=field, value=value):
                self.put("verifier/details.json", {**self.details, field: value})
                self.assertFalse(gate.g1(self.root, 60)[0])

    def test_g1_client_errors_and_caps_fail(self):
        for timing in ([], [{"error": "HTTP 500"}]):
            self.put("agent/timing.json", timing)
            self.assertFalse(gate.g1(self.root, 60)[0])
        self.put("agent/timing.json", [{"cmd": "work"}])
        self.put("agent/usage.json", {"hit_lm_call_cap": True})
        self.assertFalse(gate.g1(self.root, 60)[0])

    def test_missing_g1_evidence_records_failed(self):
        (self.root / "verifier/details.json").unlink()
        self.assertEqual(self.command("g1", self.root, self.root, 60).returncode, 1)
        row = json.loads((self.root / "status.json").read_text())["gates"]["G1"]
        self.assertEqual(row["status"], "failed")
        self.assertIn("error", row)

    def test_g2_requires_quality_and_history_beyond_server(self):
        self.assertTrue(gate.demo(self.demo(), 0, "G2")[0])
        self.assertFalse(gate.demo(self.demo(history=262144), 0, "G2")[0])
        self.assertFalse(gate.demo(self.demo(passed=3), 1, "G2")[0])

    def test_g4_quality_observational_but_full_100k_required(self):
        for passed in range(5):
            with self.subTest(passed=passed):
                rc = 0 if passed == 4 else 1
                self.assertTrue(gate.demo(self.demo(passed=passed, history=100000), rc, "G4")[0])
        self.assertFalse(gate.demo(self.demo(history=99999), 0, "G4")[0])

    def test_demo_rejects_timeout_and_score_rc_mismatch(self):
        for name in ("G2", "G4"):
            for rc in (1, 124, 130, 137):
                with self.subTest(gate=name, rc=rc):
                    self.assertFalse(gate.demo(self.demo(), rc, name)[0])
        self.assertFalse(gate.demo(self.demo(passed=3), 0, "G4")[0])

    def test_demo_rejects_truncation_duplicate_summary_and_inconsistent_counts(self):
        log = Path(self.demo())
        full = log.read_text()
        for text in ("Traceback: request failed", full + full):
            log.write_text(text)
            with self.assertRaises(ValueError):
                gate.demo(str(log), 0, "G4")
        log.write_text(full.replace("[PASS] check\n", "", 1))
        self.assertFalse(gate.demo(str(log), 0, "G4")[0])
        log.write_text(full.replace("4/4 checks", "3/4 checks"))
        self.assertFalse(gate.demo(str(log), 1, "G4")[0])

    def test_empty_missing_nonfinite_and_busy_metrics_fail(self):
        samples = ["", "vllm:num_requests_running 0\n", "vllm:num_requests_waiting 0\n"]
        samples += [f"vllm:num_requests_running {v}\nvllm:num_requests_waiting 0\n"
                    for v in ("NaN", "+Inf", "-Inf", "1", "-1", "garbage")]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertNotEqual(self.command("idle", stdin=sample).returncode, 0)
        self.assertEqual(self.command("idle", stdin='vllm:num_requests_running{model="x"} 0\nvllm:num_requests_waiting 0\n').returncode, 0)

    def test_shell_failure_annotation_preserves_check_evidence(self):
        gate.record(self.root, "G1", "failed", {"clean": 37, "readme_recite_when_required": True})
        gate.record(self.root, "G1", "failed", {"message": "command failed at line 200"})
        row = json.loads((self.root / "status.json").read_text())["gates"]["G1"]
        self.assertEqual(row["clean"], 37)
        self.assertTrue(row["readme_recite_when_required"])
        self.assertIn("message", row)

    def test_finish_requires_all_gates_and_cleanup(self):
        self.assertEqual(self.command("finish", self.root, 0, 0).returncode, 1)
        for name in ("G1", "G2", "G3", "G4"):
            gate.record(self.root, name, "passed", {})
        self.assertEqual(self.command("finish", self.root, 0, 1).returncode, 1)
        self.assertEqual(self.command("finish", self.root, 130, 0).returncode, 1)
        self.assertEqual(self.command("finish", self.root, 0, 0).returncode, 0)

    def test_archive_binding_without_extraction(self):
        source = self.root / "source"
        (source / "examples").mkdir(parents=True)
        names = ("ctxkeeper.py", "notesdelta.py", "examples/long_chat.py")
        archive = self.root / "release.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for name in names:
                data = ("# " + name).encode()
                (source / name).write_bytes(data)
                member = tarfile.TarInfo("ctxkeeper-1.2.0/" + name)
                member.size = len(data)
                tar.addfile(member, io.BytesIO(data))
            # Irrelevant unsafe member is never extracted or executed.
            member = tarfile.TarInfo("../../not-extracted")
            member.size = 1
            tar.addfile(member, io.BytesIO(b"x"))
        self.assertEqual(self.command("init", self.root, "1.2.0", "venv", "image", archive, source).returncode, 0)
        self.assertFalse((self.root / "not-extracted").exists())
        (source / "ctxkeeper.py").write_text("# altered")
        self.assertNotEqual(self.command("init", self.root, "1.2.0", "venv", "image", archive, source).returncode, 0)

    def shell_functions(self, body):
        # Load definitions only. All operational functions used below are replaced
        # with stubs before invocation; nothing starts Docker, systemd or a GPU.
        definitions = RUNNER.read_text().split('[[ $RUN =~', 1)[0]
        env = {**os.environ, "VENV": "unused", "IMG": "unused", "SOURCE_ARCHIVE": "unused",
               "RELEASE_SOURCE": "unused", "SUDO_ASKPASS": "unused", "OUT": str(self.root)}
        return subprocess.run(["bash", "-c", definitions + "\n" + body], env=env,
                              capture_output=True, text=True, timeout=10)

    def test_busy_gpu_is_never_sent_stop(self):
        result = self.shell_functions('''
SERVER_OWNED=1; CURRENT=G1
unit_alive() { return 0; }
idle_fp8() { return 1; }
touch() { echo UNEXPECTED_STOP; return 0; }
if stop_server; then exit 99; fi
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("UNEXPECTED_STOP", result.stdout)

    def test_failed_cpu_cleanup_still_drains_gpu(self):
        result = self.shell_functions('''
DOCKER_OWNED=1; PROXY_OWNED=1; TASK_OWNED=1; SERVER_OWNED=1
stop_cpu_container() { echo CPU; return 1; }
stop_proxy() { echo PROXY; return 0; }
stop_server() { echo GPU_DRAIN; return 0; }
fault_check() { return 0; }
if cleanup; then exit 99; fi
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["CPU", "PROXY", "CPU", "GPU_DRAIN"])


if __name__ == "__main__":
    unittest.main()
