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


if __name__ == "__main__":
    unittest.main()
