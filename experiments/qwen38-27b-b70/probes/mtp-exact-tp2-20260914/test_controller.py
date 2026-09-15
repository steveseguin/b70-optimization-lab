import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import json
import copy
from unittest import mock

spec = importlib.util.spec_from_file_location("controller", Path(__file__).with_name("run-native.py"))
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


class Helper:
    def __init__(self, infos):
        self.infos = iter(infos)
        self.commands = []
    def now(self):
        return "test-time"
    def inspect_container(self, identity):
        return next(self.infos)
    def run(self, args, **kwargs):
        self.commands.append(args)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")


class ControllerTests(unittest.TestCase):
    def test_quarantine_blocks_cli_before_inputs_docker_or_device_helpers(self):
        with mock.patch("sys.argv", ["run-native.py", "--out", "/tmp/new-campaign/communication-native-04"]), \
             mock.patch.object(controller, "inputs") as inputs, \
             mock.patch.object(controller, "freeze") as freeze, \
             mock.patch.object(controller.subprocess, "Popen") as popen, \
             mock.patch.object(controller.importlib.util, "spec_from_file_location") as helper_import:
            with self.assertRaisesRegex(RuntimeError, "GPU-fault quarantine"):
                controller.main()
            for operation in (inputs, freeze, popen, helper_import):
                operation.assert_not_called()

    def test_quarantine_allows_cpu_admission_only(self):
        controller.require_native_execution_admission(True)
        with self.assertRaisesRegex(RuntimeError, "No override"):
            controller.require_native_execution_admission(False)

    def test_actual_qualified_transport_contract(self):
        reference = json.loads(controller.RUNTIME_REFERENCE.read_text())
        contract = controller.runtime_contract(reference)
        self.assertEqual(contract["env"]["ONEAPI_DEVICE_SELECTOR"], "level_zero:0,1")
        self.assertEqual(contract["env"]["CCL_ZE_IPC_EXCHANGE"], "pidfd")
        self.assertEqual(contract["env"]["CCL_ATL_TRANSPORT"], "ofi")
        argv = controller.hardware_argv()
        for key, value in [("--network", "bridge"), ("--ipc", "host"), ("--cap-add", "SYS_PTRACE"),
                           ("--device", "/dev/dri"), ("--security-opt", "label=disable")]:
            self.assertEqual(argv[argv.index(key) + 1], value)

    def test_missing_selector_or_transport_capability_refused(self):
        reference = json.loads(controller.RUNTIME_REFERENCE.read_text())
        reference = reference[0] if isinstance(reference, list) else reference
        missing = copy.deepcopy(reference)
        missing["Config"]["Env"] = [v for v in missing["Config"]["Env"] if not v.startswith("ONEAPI_DEVICE_SELECTOR=")]
        with self.assertRaisesRegex(ValueError, "environment"):
            controller.runtime_contract(missing)
        for key, value in [("NetworkMode", "none"), ("IpcMode", "private"), ("CapAdd", [])]:
            changed = copy.deepcopy(reference)
            changed["HostConfig"][key] = value
            with self.assertRaisesRegex(ValueError, "hardware/transport"):
                controller.runtime_contract(changed)

    def test_static_loopback_rendezvous_without_restarts(self):
        argv = controller.operator_argv()
        self.assertEqual(argv[:7], [controller.IMAGE, "--nnodes=1", "--node-rank=0",
                                   "--nproc-per-node=2", "--master-addr=127.0.0.1",
                                   "--master-port=29500", "--max-restarts=0"])
        self.assertNotIn("--standalone", argv)
        self.assertNotIn("--rdzv-backend=c10d", argv)

    def info(self, running=True, id_="abc"):
        return {"Id": id_, "Name": "/ours", "Image": controller.IMAGE,
                "State": {"Running": running, "ExitCode": 0, "OOMKilled": False}}
    def test_running_owned_container_stopped_once(self):
        helper = Helper([self.info(), self.info(False)])
        with tempfile.TemporaryDirectory() as d:
            receipt = controller.finish_owned(helper, None, Path(d), {"name": "ours", "container_id": "abc"})
        self.assertTrue(receipt["confirmed"])
        self.assertEqual(helper.commands, [["docker", "stop", "--time", "30", "abc"]])

    def test_foreign_same_named_container_never_stopped(self):
        helper = Helper([self.info(id_="foreign")])
        with tempfile.TemporaryDirectory() as d:
            receipt = controller.finish_owned(helper, None, Path(d), {"name": "ours", "container_id": "abc"})
            self.assertTrue((Path(d) / "STOP_UNCONFIRMED").exists())
        self.assertFalse(receipt["confirmed"])
        self.assertEqual(helper.commands, [])

    def test_natural_exit_has_no_stop(self):
        helper = Helper([self.info(False), self.info(False)])
        with tempfile.TemporaryDirectory() as d:
            receipt = controller.finish_owned(helper, None, Path(d), {"name": "ours", "container_id": "abc"})
        self.assertTrue(receipt["confirmed"])
        self.assertEqual(helper.commands, [])

    def test_snapshot_keeps_exact_bytes_and_readonly_mode(self):
        with tempfile.TemporaryDirectory() as d:
            snapshot = controller.freeze(Path(d), {"a.py": b"value = 1\n", "a.so": b"binary"})
            self.assertEqual((snapshot / "a.py").read_bytes(), b"value = 1\n")
            self.assertEqual((snapshot / "a.so").stat().st_mode & 0o777, 0o444)
            self.assertEqual(snapshot.stat().st_mode & 0o777, 0o555)
            # Restore our fixture directory's mode for stdlib temporary cleanup.
            snapshot.chmod(0o755)


LIB = b"\x7fELF test library"


class Popen:
    """Fake child: poll values in order (last repeats); wait must never be needed."""
    def __init__(self, polls=(None,)):
        self.polls, self.killed, self.pid = list(polls), False, 4242
        self.stdin = mock.Mock()
    def poll(self):
        return self.polls.pop(0) if len(self.polls) > 1 else self.polls[0]
    def kill(self):
        self.killed = True
    def wait(self, timeout=None):
        raise AssertionError("monitor must not wait on a possibly stuck child")


class NewStageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "optimization-validation-20260915"
        (self.root / "health-post-reboot").mkdir(parents=True)
        (self.root / controller.HEALTH_RECEIPT).write_text(json.dumps({"passed": True}))
        contract = controller.qualified_contract(json.loads(controller.RUNTIME_REFERENCE.read_text()))
        patcher = mock.patch.object(controller, "stage_inputs", return_value=({"libexact_tp2.so": LIB}, contract))
        self.stage_inputs = patcher.start()
        self.addCleanup(patcher.stop)

    def admit(self, stage, add_mode=None, check_only=False):
        return controller.stage_admission(self.root / stage, add_mode, check_only, Path("lib.so"), root=self.root)

    def nan_receipt(self, selected="m2", status="selected", library=LIB, tamper=False, state="completed"):
        stage = self.root / controller.NAN_STAGE
        stage.mkdir()
        verdict = json.dumps({"status": status, "selected_mode": selected, "matching_modes": [selected] if selected else []}).encode()
        (stage / "nan-semantics-verdict.json").write_bytes(verdict)
        (stage / "state.json").write_text(json.dumps({"status": state, "stop_confirmed": True}))
        (stage / "DONE.json").write_text(json.dumps({
            "passed": True, "stage": controller.NAN_STAGE, "image": controller.IMAGE,
            "verdict_sha256": controller.sha(verdict + (b" " if tamper else b"")),
            "library_sha256": controller.sha(library)}))

    def test_old_stages_stay_quarantined_even_under_new_root(self):
        for n in range(1, 5):
            out = controller.CAMPAIGN_ROOT / f"communication-native-0{n}"
            with mock.patch("sys.argv", ["run-native.py", "--out", str(out)]), \
                 mock.patch.object(controller, "inputs") as inputs, \
                 mock.patch.object(controller, "stage_admission") as admission, \
                 mock.patch.object(controller.subprocess, "Popen") as popen:
                with self.assertRaisesRegex(RuntimeError, "GPU-fault quarantine"):
                    controller.main()
                for operation in (inputs, admission, popen):
                    operation.assert_not_called()

    def test_new_stage_names_admitted_only_directly_under_new_root(self):
        for bad in (controller.OLD_CAMPAIGN_ROOT / controller.NAN_STAGE, self.root / "x" / controller.NAN_STAGE,
                    self.root / "communication-native-04"):
            with self.assertRaisesRegex(RuntimeError, "admitted"):
                controller.stage_admission(bad, None, True, Path("lib.so"), root=self.root)
        self.assertEqual(self.admit(controller.NAN_STAGE)["stage"], controller.NAN_STAGE)

    def test_fault_latch_missing_health_and_existing_output_refused(self):
        (self.root / controller.NAN_STAGE).mkdir()
        with self.assertRaisesRegex(RuntimeError, "no retry"):
            self.admit(controller.NAN_STAGE)
        self.admit(controller.NAN_STAGE, check_only=True)
        (self.root / controller.HEALTH_RECEIPT).write_text(json.dumps({"passed": False}))
        with self.assertRaisesRegex(RuntimeError, "health"):
            self.admit(controller.NAN_STAGE, check_only=True)
        (self.root / "FAULT.json").write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "latch"):
            self.admit(controller.NAN_STAGE, check_only=True)

    def test_mode_arguments_per_stage(self):
        with self.assertRaisesRegex(ValueError, "refused"):
            self.admit(controller.NAN_STAGE, "m0")
        with self.assertRaisesRegex(ValueError, "requires --add-mode"):
            self.admit(controller.GATE_STAGE, None)

    def test_stage05_refused_without_receipt_but_check_only_reports_it(self):
        with self.assertRaisesRegex(RuntimeError, "stage 05 refused"):
            self.admit(controller.GATE_STAGE, "m2")
        report = self.admit(controller.GATE_STAGE, "m2", check_only=True)["nan_semantics_receipt"]
        self.assertFalse(report["satisfied"])

    def test_stage05_refused_for_wrong_mode_no_selection_hash_or_library(self):
        cases = [dict(selected="m1"), dict(selected=None, status="no-single-formulation-matches"),
                 dict(tamper=True), dict(library=b"other"), dict(state="client_failed")]
        for kwargs in cases:
            with self.subTest(**{k: str(v) for k, v in kwargs.items()}):
                self.nan_receipt(**kwargs)
                with self.assertRaisesRegex(RuntimeError, "stage 05 refused"):
                    self.admit(controller.GATE_STAGE, "m2")
                for path in (self.root / controller.NAN_STAGE).iterdir():
                    path.unlink()
                (self.root / controller.NAN_STAGE).rmdir()

    def test_stage05_admitted_with_matching_receipt_and_verdict_frozen(self):
        self.nan_receipt(selected="m2")
        admission = self.admit(controller.GATE_STAGE, "m2")
        self.assertTrue(admission["nan_semantics_receipt"]["satisfied"])
        self.assertIn("nan-semantics-verdict.json", admission["blobs"])
        self.assertIn("--add-mode", controller.stage_argv(controller.GATE_STAGE, "m2"))

    def test_env_carries_exact_qualified_service_variables(self):
        env = self.admit(controller.NAN_STAGE)["env"]
        for key, value in controller.QUALIFIED_ENV.items():
            self.assertEqual(env[key], value)
        self.assertEqual(controller.QUALIFIED_ENV, {"PYTORCH_ALLOC_CONF": "expandable_segments:True", "FI_PROVIDER": "tcp",
                         "FI_TCP_IFACE": "lo", "PYTHONHASHSEED": "0", "TORCHINDUCTOR_DETERMINISTIC": "1"})
        self.assertEqual(env["CCL_ZE_IPC_EXCHANGE"], "pidfd")
        reference = json.loads(controller.RUNTIME_REFERENCE.read_text())
        reference = copy.deepcopy(reference[0] if isinstance(reference, list) else reference)
        reference["Config"]["Env"] = [v for v in reference["Config"]["Env"] if not v.startswith("PYTORCH_ALLOC_CONF=")]
        with self.assertRaisesRegex(ValueError, "allocator"):
            controller.qualified_contract(reference)
        with self.assertRaisesRegex(ValueError, "injection"):
            controller.stage_env({"env": {"LD_PRELOAD": "x"}})

    def test_stage_argv_static_rendezvous_and_image(self):
        for stage, mode in ((controller.NAN_STAGE, None), (controller.GATE_STAGE, "m3")):
            argv = controller.stage_argv(stage, mode)
            self.assertEqual(argv[0], controller.IMAGE)
            self.assertIn("--max-restarts=0", argv)
            self.assertNotIn("--standalone", argv)
        self.assertNotIn("--add-mode", controller.stage_argv(controller.NAN_STAGE))
        self.assertIn("/probe/nan_semantics.py", controller.stage_argv(controller.NAN_STAGE))
        with self.assertRaises(ValueError):
            controller.stage_argv(controller.GATE_STAGE, None)

    def test_check_only_new_stage_makes_no_docker_guard_or_device_calls(self):
        out = controller.CAMPAIGN_ROOT / controller.NAN_STAGE
        fake = {"out": out, "root": controller.CAMPAIGN_ROOT, "stage": controller.NAN_STAGE, "blobs": {"a": b"b"},
                "contract": {}, "env": {"X": "1"}, "nan_semantics_receipt": None}
        with mock.patch("sys.argv", ["run-native.py", "--out", str(out), "--check-only"]), \
             mock.patch.object(controller, "stage_admission", return_value=fake), \
             mock.patch.object(controller.subprocess, "Popen") as popen, \
             mock.patch.object(controller, "load_module") as loader, \
             mock.patch.object(controller, "start_guard") as guard, \
             mock.patch("builtins.print"):
            controller.main()
        for operation in (popen, loader, guard):
            operation.assert_not_called()


class StageInputTests(unittest.TestCase):
    def probe(self, d, mutate=None, build=None):
        d = Path(d)
        for name in controller.NEW_FILES[:-1]:
            (d / name).write_bytes((controller.HERE / name).read_bytes())
        guard = d / "host_memory_guard.py"
        guard.write_bytes(controller.GUARD.read_bytes())
        library = d / "lib.so"; library.write_bytes(LIB)
        sources = [{"path": n, "sha256": controller.sha((d / n).read_bytes())} for n in controller.CHECKED_SOURCES]
        record = {"library_sha256": controller.sha(LIB), "source_sha256": controller.sha((d / "exact_tp2.cpp").read_bytes()),
                  "sycl_needed": "libsycl.so.9", "container_runtime": controller.CONTAINER_SYCL_RUNTIME,
                  "abi_symbol_check": {"passed": True}}
        record.update(build or {})
        (d / controller.NEW_RECEIPT).write_text(json.dumps({"schema": "neural.download.exact-tp2-cpu-validation.v2",
            "gpu_initialized": False, "tests": {"returncode": 0}, "sources": sources, "builds": [record]}))
        if mutate:
            with (d / mutate).open("a") as f:
                f.write("\n# drift\n")
        return d, library, guard

    def test_snapshot_contains_retirement_worker_analysis_guard_and_contract(self):
        with tempfile.TemporaryDirectory() as d:
            here, library, guard = self.probe(d)
            blobs, contract = controller.stage_inputs(library, here=here, guard=guard, majors=lambda _: {"9"})
        for name in ("quality_retirement.py", "nan_semantics.py", "nan_analysis.py", "host_memory_guard.py", "gate.py",
                     "libexact_tp2.so", "qualified-runtime-contract.json", controller.NEW_RECEIPT):
            self.assertIn(name, blobs)
        self.assertEqual(json.loads(blobs["qualified-runtime-contract.json"])["qualified_env"], controller.QUALIFIED_ENV)
        self.assertEqual(contract["image"], controller.IMAGE); self.assertEqual(contract["reference_image"], controller.QUALIFIED_IMAGE)

    def test_source_drift_abi_and_unchecked_build_refused(self):
        cases = [(dict(mutate="quality_retirement.py"), {"9"}, "drift"), (dict(mutate="host_memory_guard.py"), {"9"}, "drift"),
                 (dict(), {"8"}, "libsycl"), (dict(build={"abi_symbol_check": {"passed": False}}), {"9"}, "ABI-checked")]
        for kwargs, majors, message in cases:
            with self.subTest(message=message, **{k: str(v) for k, v in kwargs.items()}), tempfile.TemporaryDirectory() as d:
                if kwargs.get("mutate") == "host_memory_guard.py":
                    here, library, guard = self.probe(d)
                    with guard.open("a") as f:
                        f.write("\n# drift\n")
                else:
                    here, library, guard = self.probe(d, **kwargs)
                with self.assertRaisesRegex(RuntimeError, message):
                    controller.stage_inputs(library, here=here, guard=guard, majors=lambda _: majors)


class MonitorTests(unittest.TestCase):
    def test_bounded_run_deadline_kills_and_never_waits(self):
        child = Popen()
        clock = iter([0, 0.5, 1.1, 2])
        with self.assertRaises(TimeoutError):
            controller.bounded_run(["journalctl"], 1, popen=lambda *a, **k: child, clock=lambda: next(clock), sleep=lambda _: None)
        self.assertTrue(child.killed)

    def test_bounded_run_real_commands(self):
        started = controller.time.monotonic()
        with self.assertRaises(TimeoutError):
            controller.bounded_run(["sleep", "5"], 0.2)
        self.assertLess(controller.time.monotonic() - started, 2)
        result = controller.bounded_run(["sh", "-c", "echo out; echo err >&2; exit 3"], 5)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (3, "out\n", "err\n"))

    def test_bounded_helper_uses_runner_for_journal_and_inspect(self):
        calls = []
        def runner(args, timeout, env=None):
            calls.append((args[0], timeout))
            if args[0] == "docker":
                return SimpleNamespace(returncode=1, stdout="", stderr="Error: No such container")
            return SimpleNamespace(returncode=0, stdout="kernel", stderr="")
        helper = controller.BoundedHelper(SimpleNamespace(FAULT=None, now=lambda: "t", clean_env=lambda: {}), runner)
        self.assertIsNone(helper.inspect_container("abc"))
        self.assertEqual(helper.journal("t"), "kernel")
        self.assertTrue(all(timeout <= 30 for _, timeout in calls))

    def test_guard_exit_codes(self):
        self.assertEqual([controller.guard_outcome(c) for c in (None, 0, 3, 1)], ["running", "clean", "fired", "failed"])
        with self.assertRaises(controller.StageFailure) as fired:
            controller.check_guard(Popen([3]), None)
        self.assertEqual(fired.exception.kind, "memory_guard_fired")
        self.assertEqual(controller.classify_failure(fired.exception, False, 3), ("memory_guard_fired", "MEMORY-GUARD-FIRED.json"))
        self.assertEqual(controller.classify_failure(RuntimeError(), True, 3), ("gpu_fault", "GPU-FAULT.json"))
        self.assertEqual(controller.classify_failure(RuntimeError(), False, 0), ("client_failed", "CLIENT-FAILED.json"))
        with self.assertRaisesRegex(controller.StageFailure, "exit 1"):
            controller.check_guard(Popen([1]), None)
        self.assertIsNone(controller.check_guard(Popen([None]), None))
        self.assertEqual(controller.check_guard(Popen([0]), None, clock=lambda: 10, child_running=False), None)
        with self.assertRaisesRegex(controller.StageFailure, "attach still runs"):
            controller.check_guard(Popen([0]), 1, clock=lambda: 30)

    def test_guard_started_through_sudo_with_password_only_on_stdin(self):
        with tempfile.TemporaryDirectory() as d:
            secret = Path(d) / "pw"; secret.write_bytes(b"hunter2")
            argv = controller.guard_argv(Path("/snap/host_memory_guard.py"), "a" * 64, Path(d) / "g", 123)
            seen = {}
            def popen(args, **kwargs):
                seen.update(args=args, kwargs=kwargs)
                return Popen()
            child = controller.start_guard(argv, None, password=secret, popen=popen)
        self.assertEqual(argv[:5], ["sudo", "-S", "-p", "", "--"])
        self.assertNotIn("hunter2", " ".join(seen["args"]))
        self.assertIn("--baseline-unaccounted", argv)
        self.assertEqual(argv[argv.index("--baseline-unaccounted") + 1], "123")
        child.stdin.write.assert_called_once_with(b"hunter2\n")
        child.stdin.close.assert_called_once()
        with self.assertRaises(ValueError):
            controller.guard_argv(Path("g.py"), "short", Path("g"), 1)

    def test_guard_readiness(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError, "exited 1"):
                controller.wait_guard_ready(Popen([1]), d)
            (Path(d) / "memory-guard.jsonl").write_text("{}\n")
            controller.wait_guard_ready(Popen([None]), d)
            (Path(d) / "memory-guard.jsonl").unlink()
            clock = iter([0, 30])
            with self.assertRaises(TimeoutError):
                controller.wait_guard_ready(Popen([None]), d, clock=lambda: next(clock), sleep=lambda _: None)

    def test_latch_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            controller.latch(d, {"first": True})
            controller.latch(d, {"first": False})
            self.assertTrue(json.loads((Path(d) / "FAULT.json").read_text())["first"])


if __name__ == "__main__":
    unittest.main()
