"""CPU-only integration contracts; AST loads avoid all runtime/device imports."""
import ast
import datetime
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def require(value, message):
    if not value:
        raise RuntimeError(message)


def functions(relative, names, namespace):
    tree = ast.parse((HERE / "copies" / relative).read_text())
    selected = [node for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    for node in selected:
        node.decorator_list = []
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *selected], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(relative), "exec"), namespace)
    return namespace


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="moe-window-test-")
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name)
        self.ns = dict(os=os, json=json, time=time, Path=Path, require=require,
                       datetime=datetime, HERE=BASE, REPO=self.run,
                       PLAN=json.loads((BASE / "image-plan.json").read_text()),
                       MODEL=Path("/model-placeholder"),
                       calibration=SimpleNamespace(LOADING_GUARD_ENV="B70_SCREEN1B_LOADING_MAX_RAM_BYTES"))
        functions("screen.py", {"launch", "boundary_window_enabled", "boundary_watcher_clear",
                                "boundary_window_admission", "boundary_atomic_json", "parse_utc"}, self.ns)
        self.env = patch.dict(os.environ, {"SCREEN1B_MOE_BOUNDARY": "1"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def args(self, **kw):
        args = dict(mode="calibrate-load", port=19988, loading_ram_guard_gb=96,
                    health_receipt=Path("health.json"), previous_stop_utc="2026-01-01 00:00:00 UTC")
        args.update(kw)
        return SimpleNamespace(**args)

    def test_launch_keeps_topology_and_profile_shape(self):
        cmd = self.ns["launch"](self.args(), self.run)
        for flag, value in [("--tensor-parallel-size", "4"), ("--max-num-batched-tokens", "64"),
                            ("--kv-cache-dtype", "auto"), ("--kv-cache-memory-bytes", "376569856")]:
            self.assertEqual(cmd[cmd.index(flag)+1], value)
        self.assertIn("--enable-expert-parallel", cmd)
        self.assertIn("--enforce-eager", cmd)
        config = json.loads(cmd[cmd.index("--compilation-config")+1])
        self.assertEqual(config["cudagraph_mode"], "NONE")
        self.assertEqual(config["cudagraph_num_of_warmups"], 0)
        self.assertIn("SCREEN1B_MOE_BOUNDARY_WATCHER=/screen/watcher.json", cmd)
        self.assertIn("SCREEN1B_MOE_BOUNDARY_DIR=/screen/moe-boundary", cmd)
        self.assertIn("OMP_NUM_THREADS=2", cmd)

    def test_launch_refuses_disabled(self):
        with patch.dict(os.environ, {"SCREEN1B_MOE_BOUNDARY": "0"}):
            with self.assertRaisesRegex(RuntimeError, "requires"):
                self.ns["launch"](self.args(), self.run)

    def test_launch_refuses_generation_mode(self):
        with self.assertRaisesRegex(RuntimeError, "calibrate-load"):
            self.ns["launch"](self.args(mode="mtp1"), self.run)

    def receipt(self, **kw):
        receipt = dict(passed=True, new_fault_lines=[], updated_unix=time.time(),
                       read_started_unix=time.time(),
                       boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip())
        receipt.update(kw)
        (self.run / "watcher.json").write_text(json.dumps(receipt))

    def test_clear_watcher_passes(self):
        self.receipt()
        self.ns["boundary_watcher_clear"](self.run)

    def test_fault_and_stop_latches_refused(self):
        self.receipt()
        for name in ("STOP", "FAULT"):
            with self.subTest(name=name):
                (self.run / name).touch()
                with self.assertRaisesRegex(RuntimeError, "latched"):
                    self.ns["boundary_watcher_clear"](self.run)
                (self.run / name).unlink()

    def test_watcher_requires_fresh_journal_start(self):
        self.receipt(read_started_unix=time.time()-4)
        with self.assertRaisesRegex(RuntimeError, "read_started"):
            self.ns["boundary_watcher_clear"](self.run)

    def test_watcher_boot_mismatch(self):
        self.receipt(boot_id="different")
        with self.assertRaisesRegex(RuntimeError, "boot mismatch"):
            self.ns["boundary_watcher_clear"](self.run)

    def test_watcher_negative_receipt(self):
        self.receipt(passed=False)
        with self.assertRaisesRegex(RuntimeError, "not clear"):
            self.ns["boundary_watcher_clear"](self.run)

    def test_gap_admission(self):
        (self.run / ".git").mkdir()
        self.ns["boundary_window_admission"](self.args())
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        with self.assertRaisesRegex(RuntimeError, "305-second"):
            self.ns["boundary_window_admission"](self.args(previous_stop_utc=now))

    def test_health_is_required(self):
        with self.assertRaisesRegex(RuntimeError, "health receipt"):
            self.ns["boundary_window_admission"](self.args(health_receipt=None))

    def test_watcher_exit_marker_contract(self):
        ns = functions("probe/watch_kernel.py", {"terminal_time"},
                       dict(json=json, time=time, screen=SimpleNamespace(require=require)))
        marker = self.run / "controller-exit.json"
        self.assertIsNone(ns["terminal_time"](marker, "boot"))
        marker.write_text(json.dumps(dict(schema="screen1b.moe-boundary-controller-exit.v1",
                                         boot_id="boot", server_exited=True, exit_unix=time.time()-306)))
        self.assertLess(ns["terminal_time"](marker, "boot"), time.time()-305)
        with self.assertRaisesRegex(RuntimeError, "marker"):
            ns["terminal_time"](marker, "other")

    def watcher_namespace(self, faults):
        return functions("probe/watch_kernel.py", {"watch", "terminal_time", "atomic_json", "latch"},
                         dict(json=json, time=time, os=os, Path=Path,
                              screen=SimpleNamespace(require=require, journal=lambda: "fixture journal",
                                                     new_fault_lines=lambda text, cutoff: faults)))

    def test_watcher_observes_completed_gap(self):
        (self.run / "journal-admission.json").write_text(json.dumps(dict(passed=True, monitoring_cutoff_unix=1.0)))
        (self.run / "controller-exit.json").write_text(json.dumps(dict(
            schema="screen1b.moe-boundary-controller-exit.v1", server_exited=True,
            boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(), exit_unix=time.time()-306)))
        self.watcher_namespace([])["watch"](self.run, 1.0)
        row = json.loads((self.run / "watcher.json").read_text())
        self.assertTrue(row["passed"])
        self.assertEqual(row["post_exit_gap_seconds"], 305)
        self.assertEqual(row["status"], "post-exit gap complete")

    def test_watcher_latches_first_fault_and_preserves_stop(self):
        (self.run / "journal-admission.json").write_text(json.dumps(dict(passed=True, monitoring_cutoff_unix=1.0)))
        (self.run / "STOP").write_text("prior stop intent")
        (self.run / "controller-exit.json").write_text(json.dumps(dict(
            schema="screen1b.moe-boundary-controller-exit.v1", server_exited=True,
            boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(), exit_unix=time.time()-306)))
        self.assertEqual(self.watcher_namespace(["Fault response fixture"])["watch"](self.run, 1.0), 2)
        self.assertEqual((self.run / "STOP").read_text(), "prior stop intent")
        self.assertTrue((self.run / "FAULT").exists())
        self.assertFalse(json.loads((self.run / "watcher.json").read_text())["passed"])

    def test_controller_terminal_marker_is_atomic(self):
        marker = self.run / "controller-exit.json"
        marker.write_text('{"prior": true}')
        original_replace = Path.replace
        observations = []
        def replace(source, destination):
            observations.append((json.loads(marker.read_text()), json.loads(source.read_text())))
            return original_replace(source, destination)
        with patch.object(Path, "replace", replace):
            self.ns["boundary_atomic_json"](marker, {"server_exited": True})
        self.assertEqual(observations, [({"prior": True}, {"server_exited": True})])
        self.assertEqual(json.loads(marker.read_text()), {"server_exited": True})
        self.assertFalse(marker.with_suffix(".tmp").exists())

    def bounded_watcher_fixture(self):
        (self.run / "journal-admission.json").write_text(json.dumps(dict(passed=True, monitoring_cutoff_unix=1.0)))
        (self.run / "controller-exit.json").write_text(json.dumps(dict(
            schema="screen1b.moe-boundary-controller-exit.v1", server_exited=True,
            boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(), exit_unix=696.0)))
        now = [1000.0]
        sleeps = []
        def sleep(seconds):
            sleeps.append(seconds)
            now[0] += seconds
        clock = SimpleNamespace(time=lambda: now[0], monotonic=lambda: now[0], sleep=sleep)
        ns = self.watcher_namespace([])
        ns["time"] = clock
        return ns, sleeps

    def test_fault_latch_persists_through_post_exit_gap(self):
        ns, sleeps = self.bounded_watcher_fixture()
        reads = []
        def faults(text, cutoff):
            reads.append(text)
            return ["Fault response fixture"] if len(reads) == 1 else []
        ns["screen"].new_fault_lines = faults
        self.assertEqual(ns["watch"](self.run, 1.0), 2)
        self.assertEqual(sleeps, [.5, .5])
        self.assertEqual(len(reads), 3)
        row = json.loads((self.run / "watcher.json").read_text())
        self.assertFalse(row["passed"])
        self.assertEqual(row["new_fault_lines"], ["Fault response fixture"])
        self.assertEqual(row["status"], "post-exit gap complete")
        self.assertTrue((self.run / "STOP").exists())
        self.assertTrue((self.run / "FAULT").exists())

    def test_lost_journal_latches_without_losing_gap_monitoring(self):
        ns, sleeps = self.bounded_watcher_fixture()
        reads = []
        def journal():
            reads.append(True)
            if len(reads) == 1:
                raise RuntimeError("journal access lost")
            return "fixture journal"
        ns["screen"].journal = journal
        self.assertEqual(ns["watch"](self.run, 1.0), 2)
        self.assertEqual(sleeps, [.5, .5])
        row = json.loads((self.run / "watcher.json").read_text())
        self.assertFalse(row["passed"])
        self.assertTrue(row["journal_readable"])
        self.assertIn("journal access lost", row["exception"])
        self.assertEqual(row["status"], "post-exit gap complete")
        self.assertTrue((self.run / "STOP").exists())
        self.assertTrue((self.run / "FAULT").exists())

    def test_watcher_timeout_latches_and_fails(self):
        ns, _ = self.bounded_watcher_fixture()
        clock_reads = iter([0.0, 2701.0])
        ns["time"].monotonic = lambda: next(clock_reads)
        with self.assertRaisesRegex(RuntimeError, "2700-second watcher bound"):
            ns["watch"](self.run, 1.0)
        row = json.loads((self.run / "watcher.json").read_text())
        self.assertFalse(row["passed"])
        self.assertIn("2700-second watcher bound", row["terminal_exception"])
        self.assertTrue((self.run / "STOP").exists())
        self.assertTrue((self.run / "FAULT").exists())

    def test_runtime_warmup_bypassed_only_when_enabled(self):
        import sys
        boundary = SimpleNamespace(clear=lambda: None, emit=lambda *a, **kw: None)
        module = SimpleNamespace(enabled=lambda: True, get=lambda device: boundary)
        modules = {"vllm.screen1b_moe_boundary": module}
        ns = functions("overlay/vllm/v1/worker/gpu_worker.py", {"compile_or_warm_up_model"},
                       dict(CompilationTimes=lambda **kw: kw))
        worker = SimpleNamespace(device="cpu", model_runner=SimpleNamespace(_screen1b_profile_complete=True))
        with patch.dict(sys.modules, modules):
            self.assertEqual(ns["compile_or_warm_up_model"](worker), {"language_model": 0.0, "encoder": 0.0})
            worker.model_runner._screen1b_profile_complete=False
            with self.assertRaisesRegex(RuntimeError, "completed startup profile"):
                ns["compile_or_warm_up_model"](worker)

    def test_execute_model_forbids_later_forward(self):
        import sys
        module = SimpleNamespace(enabled=lambda: True, get=lambda device: SimpleNamespace(clear=lambda: None))
        ns = functions("overlay/vllm/v1/worker/gpu/model_runner.py", {"execute_model"}, {})
        runner = SimpleNamespace(device="cpu", _screen1b_profile_complete=True)
        with patch.dict(sys.modules, {"vllm.screen1b_moe_boundary": module}):
            with self.assertRaisesRegex(RuntimeError, "only the startup profile"):
                ns["execute_model"](runner, None, dummy_run=True, is_profile=True)
            with self.assertRaisesRegex(RuntimeError, "only the startup profile"):
                ns["execute_model"](runner, None)


if __name__ == "__main__":
    unittest.main()
