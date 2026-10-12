#!/usr/bin/env python3
"""Serial standard-library tests; no child, loader, journal or device is launched."""
import io
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import tempfile
import window


class Clock:
    def __init__(self): self.value = 0
    def now(self): return self.value
    def sleep(self, delta): self.value += delta


class Child:
    def __init__(self, clock, finish=None):
        self.clock, self.finish, self.signals, self.returncode = clock, finish, [], None
        self.pid = 42
    def poll(self):
        if self.finish is not None and self.clock.value >= self.finish:
            self.returncode = 0
        return self.returncode
    def send_signal(self, signum): self.signals.append(signum)


class WindowTests(unittest.TestCase):
    def sealed_fixture(self, root):
        build = {"passed": True, "device_executed": False, "binaries": {}, "gate_receipts": {}}
        native = {"device/replay-bench": "native-r1", "device/jit-smoke": "native-k0"}
        build["binaries"].update(native)
        rows = []
        for mode in window.HOST_MODES:
            name = mode + "/replay-bench"
            path = root / "build" / name; path.parent.mkdir(parents=True); path.write_text(mode)
            digest = window.sha(path); build["binaries"][name] = digest
            for fresh in range(2):
                rows.append({"compiler": mode, "fresh_process": fresh, "passed": True,
                             "device_executed": False, "safe_to_exit": True, "binary_sha256": digest})
        gates = {name: {"passed": True, "device_executed": False} for name in window.GATE_RECEIPTS}
        gates["cpu-tests.json"]["rows"] = rows
        gates["capture-gates.json"].update(binary_sha256=native, k0_r1_device_images_identical=True,
                                             negative_1025_rejected=True, maximum_capture_bytes=512)
        gates["raw-abi-gate.json"].update(raw_available=False, qualified=False)
        for name, row in gates.items():
            (root / name).write_text(json.dumps(row)); build["gate_receipts"][name] = window.sha(root / name)
        source = root / "source.cpp"; source.write_text("sealed current source")
        upstream = root / "upstream.hpp"; upstream.write_text("sealed upstream source")
        build["source_files"] = {"source.cpp": window.sha(source)}
        (root / "source-proof.json").write_text(json.dumps({"unchanged_packet29_inputs": {"upstream.hpp": window.sha(upstream)}}))
        build["upstream_source_proof_sha256"] = window.sha(root / "source-proof.json")
        return build, native, gates

    def test_sealed_build_complete(self):
        with tempfile.TemporaryDirectory(prefix="window-seal-", dir=window.HERE / "build") as temporary:
            root = Path(temporary); build, native, gates = self.sealed_fixture(root)
            row = window.sealed_build_gate(build, native, root, root)
            self.assertTrue(row["sealed_gates_verified"]); self.assertTrue(row["source_closure_verified"])
            self.assertEqual(set(row["host_binaries_verified"]), window.HOST_MODES)

    def test_sealed_build_incomplete_rejected(self):
        with tempfile.TemporaryDirectory(prefix="window-seal-", dir=window.HERE / "build") as temporary:
            root = Path(temporary); build, native, gates = self.sealed_fixture(root)
            mutations = [lambda b: b.pop("passed"), lambda b: b.update(passed=False),
                         lambda b: b["gate_receipts"].pop("cpu-tests.json"),
                         lambda b: b["gate_receipts"].update({"../outside.json": "foreign"}),
                         lambda b: b["binaries"].update({"device/replay-bench": "wrong"}),
                         lambda b: b["source_files"].update({"../outside.cpp": "foreign"}),
                         lambda b: b.update(upstream_source_proof_sha256="wrong")]
            for mutate in mutations:
                candidate = copy.deepcopy(build); mutate(candidate)
                with self.assertRaises(ValueError): window.sealed_build_gate(candidate, native, root, root)

    def test_sealed_build_stale_gate_rejected(self):
        with tempfile.TemporaryDirectory(prefix="window-seal-", dir=window.HERE / "build") as temporary:
            root = Path(temporary); build, native, gates = self.sealed_fixture(root)
            (root / "window-tests.json").write_text('{"passed": true}')
            with self.assertRaises(ValueError): window.sealed_build_gate(build, native, root, root)

    def test_sealed_build_false_or_wrong_binary_gate_rejected(self):
        with tempfile.TemporaryDirectory(prefix="window-seal-", dir=window.HERE / "build") as temporary:
            root = Path(temporary); build, native, gates = self.sealed_fixture(root)
            cases = [("lifetime-tests.json", lambda g: g.update(passed=False)),
                     ("capture-gates.json", lambda g: g.update(binary_sha256={"wrong": "binary"})),
                     ("capture-gates.json", lambda g: g.update(maximum_capture_bytes=1025)),
                     ("cpu-tests.json", lambda g: g["rows"].pop()),
                     ("cpu-tests.json", lambda g: g["rows"][0].update(binary_sha256="stale")),
                     ("raw-abi-gate.json", lambda g: g.update(raw_available=True))]
            for name, mutate in cases:
                original = (root / name).read_bytes(); candidate = copy.deepcopy(build)
                gate = copy.deepcopy(gates[name]); mutate(gate)
                (root / name).write_text(json.dumps(gate)); candidate["gate_receipts"][name] = window.sha(root / name)
                with self.assertRaises(ValueError): window.sealed_build_gate(candidate, native, root, root)
                (root / name).write_bytes(original)

    def test_sealed_build_changed_binary_or_source_rejected(self):
        with tempfile.TemporaryDirectory(prefix="window-seal-", dir=window.HERE / "build") as temporary:
            root = Path(temporary); build, native, gates = self.sealed_fixture(root)
            for relative in ("build/host/replay-bench", "source.cpp", "upstream.hpp"):
                path = root / relative; original = path.read_bytes(); path.write_text("changed after seal")
                with self.assertRaises(ValueError): window.sealed_build_gate(build, native, root, root)
                path.write_bytes(original)

    def test_environment(self):
        self.assertEqual(set(window.environment_gate({"LD_LIBRARY_PATH": "/x"})), window.NATIVE_KEYS)
        admitted = window.environment_gate({"LD_LIBRARY_PATH": "/x", "LC_CTYPE": "C.UTF-8"})
        self.assertEqual(admitted["OMP_NUM_THREADS"], "2")
        self.assertEqual(admitted["PATH"], "/usr/bin:/bin")
        self.assertNotIn("LC_CTYPE", admitted)
        for key in ("OMP_NUM_THREADS", "PATH", "LD_PRELOAD", "SYCL_DEVICE_FILTER", "ZE_AFFINITY_MASK", "FOO"):
            with self.assertRaises(ValueError): window.environment_gate({"LD_LIBRARY_PATH": "/x", key: ""})
        with self.assertRaises(ValueError): window.environment_gate({})
        for locale in ("", "C", "en_US.UTF-8", "C.utf8"):
            with self.assertRaises(ValueError):
                window.environment_gate({"LD_LIBRARY_PATH": "/x", "LC_CTYPE": locale})

    def test_deadlines(self):
        self.assertEqual(window.watchdog(None), 1200)
        self.assertEqual(window.watchdog(1200), 1200)
        for value in (0, 300, 600, 1199, float("nan"), float("inf")):
            with self.assertRaises(ValueError): window.watchdog(value)

    def test_ldd(self):
        calls = []
        def runner(argv, **kw):
            calls.append((argv, kw)); return SimpleNamespace(returncode=0, stdout="libsycl.so => /x/libsycl.so", stderr="")
        row = window.ldd_preflight("binary", {"LD_LIBRARY_PATH": "/x"}, runner)
        self.assertEqual(row["returncode"], 0)
        self.assertEqual(calls[0][1]["env"], {"LD_LIBRARY_PATH": "/x"})
        self.assertIn("ldd", calls[0][0][-2])
        bad = lambda *a, **k: SimpleNamespace(returncode=0, stdout="libsycl.so => not found", stderr="")
        with self.assertRaises(ValueError): window.ldd_preflight("binary", {}, bad)

    def drive(self, finish=None, fault=False, unavailable=False, requested=False, memory=None):
        clock = Clock(); child = Child(clock, finish); reasons = ["watcher signal 2"] if requested else []
        events = []
        def read(cursor):
            if unavailable: raise OSError("journal denied")
            return ("Fault response" if fault else "", cursor)
        row = window.supervise(child, 2, "cursor", io.StringIO(), reasons,
            lambda reason: events.append("latch"), lambda: events.append("persist"),
            read_journal=read, now=clock.now, sleep=clock.sleep, drain_seconds=1, postflight_seconds=.5,
            memory_sensor=memory or (lambda pid: {"root_seen": True, "anonymous_bytes": 1024, "processes": []}))
        return row, child, reasons, events

    def test_normal_exit(self):
        row, child, reasons, events = self.drive(finish=.5)
        self.assertFalse(row["child_still_running"]); self.assertEqual(child.signals, []); self.assertEqual(reasons, [])

    def test_watchdog_retains(self):
        row, child, reasons, events = self.drive()
        self.assertTrue(row["child_still_running"]); self.assertEqual(len(child.signals), 1)
        self.assertEqual(events[:2], ["latch", "persist"])
        self.assertIn("watchdog", reasons[0])

    def test_fault_retains(self):
        row, child, reasons, events = self.drive(fault=True)
        self.assertTrue(row["child_still_running"]); self.assertEqual(len(child.signals), 1)
        self.assertIn("GPU fault", reasons[0])

    def test_journal_failure_retains(self):
        row, child, reasons, events = self.drive(unavailable=True)
        self.assertTrue(row["child_still_running"]); self.assertEqual(len(child.signals), 1)

    def test_interrupt_retains(self):
        row, child, reasons, events = self.drive(requested=True)
        self.assertTrue(row["child_still_running"]); self.assertEqual(len(child.signals), 1)

    def test_cooperative_exit_failed(self):
        row, child, reasons, events = self.drive(finish=.5, fault=True)
        self.assertFalse(row["child_still_running"]); self.assertEqual(len(child.signals), 1); self.assertTrue(reasons)

    def test_k0_retains_without_signalling(self):
        clock = Clock(); child = Child(clock); reasons = ["watcher signal 2"]
        row = window.supervise(child, 2, "cursor", io.StringIO(), reasons,
            lambda reason: None, lambda: None, read_journal=lambda cursor: ("", cursor),
            now=clock.now, sleep=clock.sleep, drain_seconds=1, postflight_seconds=0,
            cooperative_stop=False,
            memory_sensor=lambda pid: {"root_seen": True, "anonymous_bytes": 1024, "processes": []})
        self.assertTrue(row["child_still_running"])
        self.assertFalse(row["sigterm_sent"])
        self.assertEqual(child.signals, [])

    def test_anonymous_memory_stop(self):
        sensor = lambda pid: {"root_seen": True, "anonymous_bytes": window.ANONYMOUS_STOP_BYTES, "processes": [{"pid": pid}]}
        row, child, reasons, events = self.drive(memory=sensor)
        self.assertTrue(row["child_still_running"])
        self.assertEqual(len(child.signals), 1)
        self.assertIn("anonymous memory", reasons[0])
        self.assertEqual(row["anonymous_peak_bytes"], window.ANONYMOUS_STOP_BYTES)
        self.assertLess(row["anonymous_stop_bytes"], 8 * 1024**3)

    def test_memory_sensor_failure(self):
        def denied(pid): raise PermissionError("proc denied")
        row, child, reasons, events = self.drive(memory=denied)
        self.assertTrue(row["child_still_running"])
        self.assertIn("sensor unavailable", reasons[0])
        self.assertEqual(len(child.signals), 1)

    def test_live_root_missing(self):
        sensor = lambda pid: {"root_seen": False, "anonymous_bytes": 0, "processes": []}
        row, child, reasons, events = self.drive(memory=sensor)
        self.assertTrue(row["child_still_running"])
        self.assertIn("missing", reasons[0])

    def test_memory_process_tree(self):
        build = window.HERE / "build"; build.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="window-test-", dir=build) as temporary:
            proc = Path(temporary)
            def process(pid, amount, threads):
                base = proc / str(pid); base.mkdir()
                (base / "status").write_text("Name: fake\nRssAnon:\t" + str(amount) + " kB\n")
                for tid, children in threads.items():
                    task = base / "task" / str(tid); task.mkdir(parents=True)
                    (task / "children").write_text(children)
            process(1, 100, {1: "2", 11: "3 2"})
            process(2, 200, {2: "4"})
            process(3, 300, {3: "999"})  # An exited child is safely skipped.
            process(4, 400, {4: ""})
            row = window.process_tree_anon(1, proc)
            self.assertTrue(row["root_seen"])
            self.assertEqual(row["anonymous_bytes"], 1000 * 1024)
            self.assertEqual([r["pid"] for r in row["processes"]], [1, 2, 3, 4])
            (proc / "4/status").write_text("RssAnon: malformed\n")
            with self.assertRaises(ValueError): window.process_tree_anon(1, proc)

    def test_summary_required_and_hash_bound(self):
        build = window.HERE / "build"; build.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="window-test-", dir=build) as temporary:
            run = Path(temporary)
            def summary(path):
                self.assertEqual(path, run)
                row = {"passed": True, "device_executed": True, "replay_pays": {"graph-whole": False}}
                (path / "summary.json").write_text(json.dumps(row))
                return row
            result = window.finalize_r1(run, summary)
            self.assertEqual(result["summary_sha256"], window.sha(run / "summary.json"))
            self.assertFalse(result["replay_pays"]["graph-whole"])
            with self.assertRaises(ValueError): window.finalize_r1(run, lambda path: {"passed": False})
            with self.assertRaises(ValueError): window.finalize_r1(run, lambda path: {"passed": True, "device_executed": False})

    def test_specific_fault_signatures(self):
        for line in ("Fault response", "CAT error", "engine reset", "GPU coredump", "xe device coredump", "job 12 timed out"):
            self.assertIsNotNone(window.FAULT.search(line), line)
        for line in ("hang artwork", "no changes", "reset password", "normal engine activity"):
            self.assertIsNone(window.FAULT.search(line), line)

    def test_native_receipt(self):
        window.native_gate({"passed": True, "safe_to_exit": True})
        window.native_gate({"passed": True, "teardown": {"safe_to_exit": True}})
        for row in ({}, {"passed": True}, {"passed": False, "safe_to_exit": True}):
            with self.assertRaises(ValueError): window.native_gate(row)

    def test_output_boundary(self):
        self.assertEqual(window.under_packet(window.HERE / "build/run"), window.HERE / "build/run")
        with self.assertRaises(ValueError): window.under_packet(window.HERE / "../escape")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WindowTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    receipt = dict(schema="own-runtime.packet34.window-tests.v1", passed=result.wasSuccessful(),
                   tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                   device_executed=False, actual_children_launched=0)
    (window.HERE / "window-tests.json").write_text(json.dumps(receipt, indent=2) + "\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
