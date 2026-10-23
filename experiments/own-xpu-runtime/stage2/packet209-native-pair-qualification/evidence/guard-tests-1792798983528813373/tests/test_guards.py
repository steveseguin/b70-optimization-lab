"""Actual runner validators/lifetimes with fake children and real temporary flocks."""
import contextlib
import copy
import fcntl
import gzip
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import signal
import sys
import tempfile
import types
import unittest
from unittest import mock

P = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("p209_tested_runner", P / "runner.py")
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)
sys.path.insert(0, str(R.P181))
import lane_admission as L
import drain_gate as D
assert Path(L.__file__).resolve() == R.P181 / "lane_admission.py"
assert Path(D.__file__).resolve() == R.P181 / "drain_gate.py"


def topology_fixture():
    return {f"/dev/dri/{name}": dict(bdf=bdf, dev=f"226:{minor}", sys_device="/sys/devices/" + bdf, driver="xe")
            for i, bdf in enumerate(("0000:23:00.0", R.BDF, "0000:43:00.0", "0000:47:00.0"))
            for name, minor in ((f"card{i}", i), (f"renderD{128+i}", 128+i))}


def manifest():
    return dict(schema=R.SCHEMA, authorized=True, unit=R.UNIT, bdf=R.BDF,
                lane="A", window="screen", timing_claim=False,
                output=str(R.OUTPUT), binary=str(R.BINARY), binary_sha256="a" * 64,
                boot_id="11111111-1111-1111-1111-111111111111", expires_unix=2000,
                environment=R.environment(), source_sha256={"fixture-only": "b" * 64},
                fault_review="fixture-review.json", fault_review_sha256="c" * 64,
                pause_sha256={"A": "d" * 64, "B": "e" * 64},
                queue_sha256={"A": "f" * 64, "B": "f" * 64},
                protected_units={"app0.service": {"pid": 101, "start_ticks": 1001},
                                 "app2.service": {"pid": 102, "start_ticks": 1002},
                                 "app3.service": {"pid": 103, "start_ticks": 1003}},
                allowed_holders=[{"pid": pid, "start_ticks": 900 + pid,
                                  "nodes": [f"/dev/dri/card{card}", f"/dev/dri/renderD{128 + card}"]}
                                 for pid, card in ((101, 0), (102, 2), (103, 3))],
                target_nodes=["/dev/dri/card1", "/dev/dri/renderD129"], topology=topology_fixture(),
                competitor_units=["fixture-other-experiment.service"],
                root_floor_bytes=R.FLOOR, write_bytes=R.WRITE_BYTES,
                host_available_bytes=R.HOST_BYTES,
                parent_device_image_sha256="e90834e35401eceaa48d1cb9691b6b0bfa56d456e9d57464636140d0c2e3f4a5")


def snapshot(m):
    return dict(boot_id=m["boot_id"], now_unix=1000, pause_sha256=copy.deepcopy(m["pause_sha256"]),
                queue_sha256=copy.deepcopy(m["queue_sha256"]), queues_empty=True,
                stop_present=False, competitors_inactive=True,
                protected_units=copy.deepcopy(m["protected_units"]), target_bdf=R.BDF,
                target_nodes=list(m["target_nodes"]), topology=copy.deepcopy(m["topology"]), faults_clear=True,
                free_bytes=R.FLOOR + R.WRITE_BYTES, mem_available_bytes=R.HOST_BYTES,
                unit_properties=dict(R.SAFE_UNIT))


def inventory():
    return dict(passed=False, metadata_only=True, device_opens=0, errors=[],
                holders=[dict(pid=pid, fd="7", node=f"renderD{128 + card}")
                         for pid, card in ((101, 0), (102, 2), (103, 3))],
                nodes={**{f"226:{i}": f"card{i}" for i in range(4)},
                       **{f"226:{128+i}": f"renderD{128+i}" for i in range(4)}},
                intel_devices=["/sys/devices/" + bdf for bdf in
                               ("0000:23:00.0", "0000:27:00.0", "0000:43:00.0", "0000:47:00.0")])


def native_result():
    return dict(schema="packet208.future-native-proof.v1", passed=True, safe_to_exit=True,
                teardown=dict(safe_to_exit=True, exit_code=0, in_flight=0, live_bytes=0, idle_marker_complete=True),
                cases=[dict(rows=rows, columns=2560, stride=3380, variant=6, passed=True,
                            pair_commands=1, serial_commands=2, output_sha256=["a"*64, "b"*64],
                            native_serial_cpu_exact=True, live_input_weight_controls=True)
                       for rows in (10240, 6144)])


class Child:
    pid = 9000
    returncode = None

    def __init__(self):
        self.signals = []
        self.poll_error = None
        self.signal_error = None

    def poll(self):
        if self.poll_error is not None:
            error, self.poll_error = self.poll_error, None
            raise error
        return self.returncode

    def send_signal(self, value):
        self.signals.append(value)
        if self.signal_error is not None:
            raise self.signal_error


class Ops:
    def __init__(self, test, root, m):
        self.test, self.root, self.m = test, Path(root), m
        self.snap, self.raw = snapshot(m), inventory()
        self.child = Child()
        self.events, self.records = [], []
        self.launches = self.checks = self.observes = self.diagnoses = 0
        self.failure = self.launch_error = self.receipt_error = self.sleep_error = None
        self.secondary_error = None
        self.fail_receipt_phase = None
        self.delay_drain = 0
        self.diagnose_error = None
        self.lease = self.permit = None

    def locked(self):
        for path in (self.root / "coord/lane-A.lock", self.root / "drain/teardown.lock"):
            with path.open("r+") as file:
                with self.test.assertRaises(BlockingIOError):
                    fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def released(self):
        for path in (self.root / "coord/lane-A.lock", self.root / "drain/teardown.lock"):
            if path.exists():
                with path.open("r+") as file:
                    fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def preflight(self, m):
        R.validate_snapshot(m, self.snap)
        R.classify_inventory(self.raw, m["target_nodes"], m["allowed_holders"],
                             {h["pid"]: h["start_ticks"] for h in m["allowed_holders"]})

    @contextlib.contextmanager
    def reservation(self, m):
        lease = L.Reservation("A", root=self.root / "coord", wait_seconds=2)
        self.lease = lease
        complete = lease.complete
        def finish(**kwargs):
            self.events.append("reservation.complete")
            return complete(**kwargs)
        lease.complete = finish
        with lease:
            yield lease

    @contextlib.contextmanager
    def drain(self, m, reservation):
        root = self.root / "drain"
        root.mkdir(mode=0o700)
        permit = D.DrainPermit(self.root / "output", root=root, wait_seconds=2,
                               reservation=reservation.record)
        self.permit = permit
        complete = permit.complete
        def finish():
            self.events.append("drain.complete")
            return complete()
        permit.complete = finish
        with permit:
            yield permit

    def check(self, m):
        self.checks += 1
        self.locked()
        if self.launches and self.failure is not None:
            raise self.failure
        R.validate_snapshot(m, self.snap)

    def launch(self, m):
        self.locked()
        self.launches += 1
        self.events.append("launch")
        if self.launch_error is not None:
            raise self.launch_error
        return self.child

    def observe(self, m, child):
        self.locked()
        self.observes += 1
        if self.observes >= 2:
            child.returncode = 0
        return dict(child_observed=self.observes == 1, target_empty=self.observes >= 2)

    def ack(self, m, child):
        self.events.append("ack")

    def result(self, m):
        return native_result()

    def receipt(self, row):
        phase = row.get("phase", "failure")
        if self.receipt_error is not None and phase == self.fail_receipt_phase:
            raise self.receipt_error
        self.records.append(copy.deepcopy(row))
        self.events.append("receipt:" + phase)

    def stop(self, m):
        self.events.append("stop")

    def secondary(self, error):
        if self.secondary_error is not None:
            raise self.secondary_error

    def diagnose(self, m, child):
        self.locked()
        self.diagnoses += 1
        if self.diagnose_error is not None:
            error, self.diagnose_error = self.diagnose_error, None
            raise error
        safe = self.diagnoses > self.delay_drain
        if safe:
            self.child.returncode = 0
        return dict(child_exited=safe, owner_safe=safe, target_empty=safe)

    def sleep(self, seconds):
        if self.sleep_error is not None:
            error, self.sleep_error = self.sleep_error, None
            raise error


class Guards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p209-guards-")
        self.addCleanup(self.temp.cleanup)
        self.m = manifest()
        self.ops = Ops(self, self.temp.name, self.m)

    def run_failure(self, expected):
        with self.assertRaises(type(expected)) as caught:
            # The fallback sleep is patched only to make passive retained-loop
            # exceptions fast; real temporary lock acquisition is unchanged.
            with mock.patch.object(R.time, "sleep", lambda seconds: None):
                R.run_once(self.m, self.ops)
        self.assertIs(caught.exception, expected)
        self.ops.released()
        self.assertNotIn("reservation.complete", self.ops.events)
        self.assertNotIn("drain.complete", self.ops.events)
        self.assertTrue((Path(self.temp.name) / "coord/active-lane-A.json").exists())
        drain = json.loads((Path(self.temp.name) / "drain/teardown-state.json").read_text())
        self.assertFalse(drain["drained"])
        self.assertLessEqual(len(self.ops.child.signals), 1)

    def test_manifest_mutations_never_launch(self):
        for key, value in [("authorized", False), ("boot_id", "bad"), ("bdf", "0000:23:00.0"),
                           ("lane", "B"), ("timing_claim", True), ("binary_sha256", "g" * 64),
                           ("parent_device_image_sha256", "0" * 64), ("write_bytes", 0),
                           ("output", "/tmp/unadmitted")]:
            m = copy.deepcopy(self.m)
            m[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                R.run_once(m, self.ops)
        for key, value in [("HOME", "/tmp/private-home"), ("LD_PRELOAD", "/tmp/foreign.so"),
                           ("FilterBdfPath", "0000:2")]:
            m = copy.deepcopy(self.m)
            m["environment"][key] = value
            with self.subTest(env=key), self.assertRaises(RuntimeError):
                R.run_once(m, self.ops)
        self.assertEqual(self.ops.launches, 0)

    def test_live_snapshot_mutations_never_launch(self):
        changes = [("boot_id", "22222222-2222-2222-2222-222222222222"), ("now_unix", 2001),
                   ("stop_present", True), ("queues_empty", False), ("competitors_inactive", False),
                   ("faults_clear", False), ("free_bytes", R.FLOOR + R.WRITE_BYTES - 1),
                   ("mem_available_bytes", R.HOST_BYTES - 1), ("target_bdf", "0000:23:00.0"),
                   ("pause_sha256", {"A": "changed", "B": "changed"}),
                   ("queue_sha256", {"A": "changed", "B": "changed"}),
                   ("protected_units", {}), ("unit_properties", {**R.SAFE_UNIT, "Restart": "always"})]
        for key, value in changes:
            self.ops.snap = snapshot(self.m)
            self.ops.snap[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                R.run_once(self.m, self.ops)
        self.assertEqual(self.ops.launches, 0)

    def test_other_app_holders_and_duplicate_fd_rows_are_allowed(self):
        raw = inventory()
        raw["holders"].append(dict(raw["holders"][0], fd="8"))
        ids = {h["pid"]: h["start_ticks"] for h in self.m["allowed_holders"]}
        self.assertEqual(R.classify_inventory(raw, self.m["target_nodes"], self.m["allowed_holders"], ids),
                         {"child_observed": False, "target_empty": True})
        raw["holders"].append(dict(pid=9000, fd="9", node="renderD129"))
        ids[9000] = 90000
        self.assertEqual(R.classify_inventory(raw, self.m["target_nodes"], self.m["allowed_holders"], ids,
                                              child={"pid": 9000, "start_ticks": 90000}),
                         {"child_observed": True, "target_empty": False})

    def test_incomplete_or_malformed_inventory_refuses(self):
        ids = {h["pid"]: h["start_ticks"] for h in self.m["allowed_holders"]}
        for key in inventory():
            raw = inventory()
            del raw[key]
            with self.subTest(missing=key), self.assertRaises((RuntimeError, ValueError, KeyError)):
                R.classify_inventory(raw, self.m["target_nodes"], self.m["allowed_holders"], ids)
        for key, value in [("errors", ["permission denied"]), ("device_opens", 1),
                           ("passed", True), ("metadata_only", False), ("holders", None),
                           ("nodes", {}), ("intel_devices", [])]:
            raw = inventory()
            raw[key] = value
            with self.subTest(key=key), self.assertRaises((RuntimeError, ValueError, KeyError, TypeError)):
                R.classify_inventory(raw, self.m["target_nodes"], self.m["allowed_holders"], ids)

    def test_unknown_target_holder_pid_reuse_or_wrong_card_refuses(self):
        ids = {h["pid"]: h["start_ticks"] for h in self.m["allowed_holders"]}
        for holder in [dict(pid=101, fd="8", node="renderD129"),
                       dict(pid=999, fd="8", node="renderD128"),
                       dict(pid=101, fd="8", node="renderD131"),
                       dict(pid=101, fd="8", node="renderD999")]:
            raw = inventory()
            raw["holders"].append(holder)
            with self.subTest(holder=holder), self.assertRaises(RuntimeError):
                R.classify_inventory(raw, self.m["target_nodes"], self.m["allowed_holders"], ids)
        for changed in (dict(ids, **{}), {**ids, 101: 9999}):
            if changed == ids:
                del changed[101]
            with self.assertRaises(RuntimeError):
                R.classify_inventory(inventory(), self.m["target_nodes"], self.m["allowed_holders"], changed)

    def test_success_has_durable_precompletion_before_lock_completion(self):
        self.assertEqual(R.run_once(self.m, self.ops), 0)
        self.assertEqual(self.ops.launches, 1)
        self.assertEqual(self.ops.child.signals, [])
        events = self.ops.events
        self.assertLess(events.index("receipt:pre-completion"), events.index("drain.complete"))
        self.assertLess(events.index("drain.complete"), events.index("reservation.complete"))
        self.assertLess(events.index("reservation.complete"), events.index("receipt:completed"))
        self.ops.released()
        self.assertFalse((Path(self.temp.name) / "coord/active-lane-A.json").exists())

    def test_fault_halts_intake_single_signal_retains_locks_until_drain(self):
        error = RuntimeError("first kernel fault")
        self.ops.failure = error
        self.ops.delay_drain = 2
        self.run_failure(error)
        self.assertEqual(self.ops.launches, 1)
        self.assertEqual(self.ops.observes, 0)
        self.assertEqual(self.ops.child.signals, [signal.SIGTERM])
        self.assertEqual(self.ops.diagnoses, 3)

    def test_failure_receipt_and_secondary_error_do_not_release_early(self):
        error = RuntimeError("primary fault")
        self.ops.failure = error
        self.ops.receipt_error = OSError("evidence disk error")
        self.ops.fail_receipt_phase = "failure"
        self.ops.secondary_error = RuntimeError("logger failed")
        self.ops.delay_drain = 1
        self.run_failure(error)
        self.assertEqual(self.ops.child.signals, [signal.SIGTERM])

    def test_poll_signal_passive_diagnostic_and_sleep_failures_preserve_primary(self):
        error = RuntimeError("primary guard failure")
        self.ops.failure = error
        self.ops.child.poll_error = OSError("owner status unknown")
        self.ops.diagnose_error = OSError("passive inventory temporarily unreadable")
        self.ops.sleep_error = RuntimeError("sleep interrupted")
        self.run_failure(error)
        self.assertEqual(self.ops.diagnoses, 2)

    def test_signal_failure_never_causes_a_second_signal(self):
        error = RuntimeError("primary guard failure")
        self.ops.failure = error
        self.ops.child.signal_error = OSError("signal interrupted")
        self.ops.delay_drain = 1
        self.run_failure(error)
        self.assertEqual(self.ops.child.signals, [signal.SIGTERM])

    def test_uncertain_spawn_keeps_locks_until_passive_resolution(self):
        error = RuntimeError("Popen interrupted after child creation")
        self.ops.launch_error = error
        self.ops.delay_drain = 2
        self.run_failure(error)
        self.assertEqual(self.ops.launches, 1)
        self.assertEqual(self.ops.child.signals, [])
        self.assertEqual(self.ops.diagnoses, 3)

    def test_precompletion_write_failure_does_not_complete_markers(self):
        error = OSError("precompletion write failed")
        self.ops.receipt_error = error
        self.ops.fail_receipt_phase = "pre-completion"
        self.run_failure(error)
        self.assertEqual(self.ops.child.signals, [])

    def test_terminal_proof_refuses_short_or_inexact_owner(self):
        for code, observed, drained in [(1, True, True), (0, False, True), (0, True, False)]:
            with self.assertRaises(RuntimeError):
                R.finish_proof(native_result(), code, observed, drained)
        for key, value in [("safe_to_exit", False), ("passed", False), ("cases", [])]:
            result = native_result()
            result[key] = value
            with self.assertRaises(RuntimeError):
                R.finish_proof(result, 0, True, True)

    def test_duplicate_json_admission_refuses(self):
        path = Path(self.temp.name) / "bad.json"
        path.write_text('{"authorized":true,"authorized":false}')
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            R.read_json(path)


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("p209_tested_live_ops", P / "live_ops.py")
        cls.V = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"runner": R}):
            spec.loader.exec_module(cls.V)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.m = manifest()
        self.ops = self.V.LiveOps(self.m, "a" * 64)
        self.ops.control = Path(self.temp.name) / "control"
        self.ops.control.mkdir(mode=0o700)
        self.addCleanup(self.close_log)

    def close_log(self):
        if self.ops.log is not None:
            self.ops.log.close()

    def test_ambient_cached_helper_origin_refused(self):
        impostor = types.ModuleType("lane_admission")
        impostor.__file__ = "/tmp/ambient/lane_admission.py"
        impostor.Reservation = L.Reservation
        with mock.patch.dict(sys.modules, {"lane_admission": impostor}), self.assertRaisesRegex(RuntimeError, "origin"):
            self.V.LiveOps(self.m, "a" * 64)

    def test_missing_required_source_pin_fails_before_live_reads(self):
        # Exercise actual preflight comparison; fixtures replace only its immutable
        # source/boot inputs, and forbid every following live operation.
        with mock.patch.object(Path, "read_text", return_value=self.m["boot_id"]), \
             mock.patch.object(R, "sha", return_value="a" * 64), \
             mock.patch.object(R, "source_closure", return_value={"required.py": "b" * 64}), \
             mock.patch.object(self.ops, "snapshot", side_effect=AssertionError("live snapshot reached")), \
             mock.patch.object(self.V, "inventory", side_effect=AssertionError("inventory reached")), \
             self.assertRaisesRegex(RuntimeError, "exact reviewed source closure"):
            self.ops.preflight(self.m)

    def test_actual_launch_boundary_exact_argv_env_no_tick_lookup(self):
        child = Child()
        with mock.patch.object(self.V.subprocess, "Popen", return_value=child) as launch, \
             mock.patch.object(self.V, "process_identity", side_effect=AssertionError("premature identity lookup")):
            self.assertIs(self.ops.launch(self.m), child)
        self.assertIs(self.ops.child, child)
        args, kw = launch.call_args
        self.assertEqual(args[0], [str(R.BINARY), "--authorized-device-window", "--manifest", str(R.MANIFEST), "--manifest-sha256", "a" * 64])
        self.assertEqual(kw["env"], R.environment())
        self.assertEqual(kw["env"]["HOME"], "/home/steve")
        self.assertEqual(kw["stdin"], self.V.subprocess.DEVNULL)
        self.assertEqual(kw["stderr"], self.V.subprocess.STDOUT)
        self.assertFalse(self.ops.spawn_uncertain)

    def test_actual_observe_tick_failure_retains_known_child(self):
        child = self.ops.child = Child()
        error = OSError("proc identity unavailable")
        with mock.patch.object(self.V, "process_identity", side_effect=error), self.assertRaises(OSError) as caught:
            self.ops.observe(self.m, child)
        self.assertIs(caught.exception, error)
        self.assertIs(self.ops.child, child)
        self.assertIsNone(self.ops.child_identity)

    def test_tick_lookup_failure_reaches_single_signal_and_held_drain(self):
        ops = Ops(self, Path(self.temp.name) / "lifetimes", self.m)
        error = OSError("known child proc lookup failed")
        ops.observe = lambda m, child: self.ops.observe(m, child)
        ops.delay_drain = 1
        with mock.patch.object(self.V, "process_identity", side_effect=error), \
             self.assertRaises(OSError) as caught:
            R.run_once(self.m, ops)
        self.assertIs(caught.exception, error)
        self.assertEqual(ops.child.signals, [signal.SIGTERM])
        self.assertEqual(ops.diagnoses, 2)
        self.assertNotIn("reservation.complete", ops.events)
        self.assertNotIn("drain.complete", ops.events)
        ops.released()

    def test_missing_output_does_not_prove_no_owner(self):
        child = Child()
        child.returncode = 1
        self.ops.child = child
        with mock.patch.object(R, "OUTPUT", Path(self.temp.name) / "absent-output"), \
             mock.patch.object(self.V, "inventory", return_value=({"target_empty": True}, {})):
            result = self.ops.diagnose(self.m, child)
        self.assertTrue(result["child_exited"])
        self.assertFalse(result["owner_safe"])

    def test_actual_inventory_refusal_retains_raw_metadata_without_secret_read(self):
        raw = inventory()
        raw["holders"].append(dict(pid=9999, fd="90", node="renderD129"))
        completed = types.SimpleNamespace(returncode=1, stdout=json.dumps(raw), stderr="")
        with mock.patch.object(self.V, "topology", return_value=topology_fixture()), \
             mock.patch.object(Path, "open", return_value=io.BytesIO(b"fixture-only-secret\n")) as opening, \
             mock.patch.object(self.V.subprocess, "run", return_value=completed) as subprocess_run, \
             mock.patch.object(self.V, "process_identity", side_effect=lambda pid:900+pid), \
             self.assertRaises(RuntimeError) as caught:
            self.V.inventory(self.m)
        self.assertEqual(caught.exception.passive_evidence["raw"], raw)
        self.assertEqual(caught.exception.passive_evidence["topology"], topology_fixture())
        self.assertEqual(subprocess_run.call_count, 1)
        self.assertEqual(subprocess_run.call_args.kwargs["timeout"], 30)
        self.assertNotIn("fixture-only-secret", repr(caught.exception.passive_evidence))
        self.ops.secondary(caught.exception)
        evidence = json.loads((self.ops.control / "incident-passive.json").read_text())
        self.assertEqual(evidence["raw"], raw)

    def test_actual_fault_classifier_retains_bounded_new_fault_records(self):
        boot = self.m["boot_id"].replace("-", "")
        old = [dict(_BOOT_ID=boot, MESSAGE="GPU HANG fixture old " + str(i)) for i in range(2)]
        current = old + [dict(_BOOT_ID=boot, MESSAGE="GPU HANG fixture new " + str(i)) for i in range(33)]
        old_bytes = ("\n".join(map(json.dumps, old))+"\n").encode()
        capture = Path(self.temp.name) / "review.gz"
        capture.write_bytes(gzip.compress(old_bytes))
        review = dict(driver_sha256=R.sha(R.P181 / "lineage/window_driver.py"),
                      kernel_capture=str(capture), journal_sha256=hashlib.sha256(old_bytes).hexdigest(),
                      faults=old, boot_id=self.m["boot_id"])
        path = Path(self.temp.name) / "review.json"
        path.write_text(json.dumps(review))
        self.m.update(fault_review=str(path), fault_review_sha256=R.sha(path))
        journal = "\n".join(map(json.dumps, current))+"\n"
        with mock.patch.object(self.V, "run", return_value=journal) as passive, \
             self.assertRaisesRegex(RuntimeError, "kernel fault") as caught:
            self.V.faults_clear(self.m)
        evidence = caught.exception.passive_evidence
        self.assertEqual(evidence["journal_sha256"], hashlib.sha256(journal.encode()).hexdigest())
        self.assertEqual(evidence["fault_count"], 35)
        self.assertEqual(evidence["faults"], current[:32])
        self.assertTrue(evidence["truncated"])
        self.assertEqual(passive.call_count, 1)

    def test_positive_no_owner_refusal_requires_exact_child_and_admission(self):
        child = Child()
        child.returncode = 1
        self.ops.child = child
        self.ops.child_identity = {"pid": child.pid, "start_ticks": 90000}
        valid = dict(pid=child.pid, start_ticks=90000, manifest_sha256=self.ops.digest,
                     fixture_entered=False, safe_no_owner=True, device_enumerated=True)
        path = self.ops.control / "entry-refusal.json"
        with mock.patch.object(R, "OUTPUT", Path(self.temp.name) / "absent-output"), \
             mock.patch.object(self.V, "inventory", return_value=({"target_empty": True}, {})):
            path.write_text(json.dumps(valid))
            self.assertTrue(self.ops.diagnose(self.m, child)["owner_safe"])
            for key, value in [("pid", 999), ("start_ticks", 90001), ("manifest_sha256", "b"*64),
                               ("fixture_entered", True), ("safe_no_owner", False)]:
                path.write_text(json.dumps({**valid, key:value}))
                with self.subTest(key=key):
                    self.assertFalse(self.ops.diagnose(self.m, child)["owner_safe"])

    def test_operational_cli_stays_disabled_without_constructing_adapter(self):
        with mock.patch.object(sys, "argv", ["runner.py", "--run"]), \
             mock.patch.object(self.V, "LiveOps", side_effect=AssertionError("constructed live adapter")), \
             self.assertRaisesRegex(RuntimeError, "not finalized"):
            R.main()

    def test_observed_vision_pid_on_target_refused_despite_other_allowed_card(self):
        # Actual observed node numbering: BDF27 card4/renderD131, BDF43 renderD128.
        raw = inventory()
        raw["nodes"] = {"226:0":"card0", "226:2":"card2", "226:3":"card3", "226:4":"card4",
                        **{f"226:{i}":f"renderD{i}" for i in range(128,132)}}
        raw["holders"] = [dict(pid=3487303, fd="7", node="renderD128"),
                          dict(pid=3487303, fd="8", node="renderD131")]
        allowed = [dict(pid=3487303, start_ticks=63453537, nodes=["/dev/dri/renderD128"])]
        with self.assertRaises(RuntimeError):
            R.classify_inventory(raw, ["/dev/dri/card4", "/dev/dri/renderD131"], allowed, {3487303:63453537})
        allowed[0]["nodes"].append("/dev/dri/renderD131")
        with self.assertRaisesRegex(RuntimeError, "target occupied"):
            R.classify_inventory(raw, ["/dev/dri/card4", "/dev/dri/renderD131"], allowed, {3487303:63453537})


if __name__ == "__main__":
    unittest.main()
