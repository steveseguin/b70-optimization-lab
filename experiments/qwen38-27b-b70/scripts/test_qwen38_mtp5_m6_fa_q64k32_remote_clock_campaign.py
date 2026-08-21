#!/usr/bin/env python3
"""CPU-only tests for the blocked reference-host Q64K32 clock campaign."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
CAMPAIGN_PATH = HERE / "qwen38_mtp5_m6_fa_q64k32_remote_clock_campaign.py"
SPEC = importlib.util.spec_from_file_location("remote_clock_campaign", CAMPAIGN_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load campaign module")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


class ContractTests(unittest.TestCase):
    def test_import_does_not_import_torch(self) -> None:
        self.assertNotIn("torch", C.sys.modules)

    def test_plan_is_exact_counterbalanced_sixteen_arm_abba(self) -> None:
        self.assertEqual(len(C.PLAN), 16)
        self.assertEqual([row["ordinal"] for row in C.PLAN], list(range(1, 17)))
        self.assertEqual(
            [(row["device"], row["clock"]) for row in C.PLAN[::4]],
            [(0, "default"), (1, "fixed"), (0, "fixed"), (1, "default")],
        )
        for device, clocks in ((0, ("default", "fixed")), (1, ("fixed", "default"))):
            rows = [row for row in C.PLAN if row["device"] == device]
            self.assertEqual(
                [row["clock"] for row in rows], [clocks[0]] * 4 + [clocks[1]] * 4
            )
            self.assertEqual(
                [row["role"] for row in rows],
                ["control", "candidate", "candidate", "control"] * 2,
            )
            self.assertEqual([row["slot"] for row in rows], [1, 2, 3, 4] * 2)
            self.assertEqual(
                [row["inner_arm_id"] for row in rows],
                [
                    f"gpu{device}-a1",
                    f"gpu{device}-b1",
                    f"gpu{device}-b2",
                    f"gpu{device}-a2",
                ]
                * 2,
            )
            self.assertTrue(
                all(row["outer_arm_id"] != row["inner_arm_id"] for row in rows)
            )

    def test_fixture_contract_matches_preserved_exact_values(self) -> None:
        self.assertEqual(set(C.FIXTURES), {128, 1024, 1300, 2048})
        self.assertEqual(C.FIXTURES[128]["fixture_seed"], 380128)
        self.assertEqual(
            C.FIXTURES[1300]["fixture_sha256"],
            "d5044ce346d2b4f97745c42341c85572e205e95d3bee0bc1baa5c84403771c3a",
        )
        for evidence in C.FIXTURES.values():
            self.assertRegex(evidence["fixture_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(evidence["oracle_sha256"], r"^[0-9a-f]{64}$")

    def test_runtime_hash_contract(self) -> None:
        self.assertEqual(len(C.RUNTIME_FILES), 3)
        self.assertNotEqual(C.CONTROL_DEVICE_SHA256, C.CANDIDATE_DEVICE_SHA256)
        self.assertEqual(
            C.CANDIDATE_GRAPH_SHA256,
            "d662dba3927fac706ff221902f536b67178b6875f66604597a1f2fe98a4defc4",
        )

    def test_strict_json_rejects_duplicate_and_nonfinite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"a":1,"a":2}\n', encoding="utf-8")
            with self.assertRaises(C.ContractError):
                C.load_json(path)
            path.write_text('{"a":NaN}\n', encoding="utf-8")
            with self.assertRaises(C.ContractError):
                C.load_json(path)

    def test_atomic_json_is_canonical_read_only_and_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packet.json"
            C.write_json_atomic(path, {"z": 1, "a": 2})
            self.assertEqual(path.read_bytes(), b'{"a":2,"z":1}\n')
            self.assertEqual(path.stat().st_mode & 0o777, 0o444)
            with self.assertRaises(C.ContractError):
                C.write_json_atomic(path, {})

    def test_source_authorization_is_deliberately_incomplete(self) -> None:
        self.assertIs(C.CAMPAIGN_LAUNCH_AUTHORIZED, False)
        self.assertIs(C.DRIVER_SIGNAL_OWNERSHIP_AUTHORIZED, False)
        self.assertIs(C.CLOCK_WRITER_EXCLUSION_AUTHORIZED, False)
        self.assertIs(C.DRIVER_ENVIRONMENT_AUTHORIZED, False)
        self.assertIsNone(C.AUTHORIZED_REMOTE_REPO_HEAD)
        self.assertIsNone(C.AUTHORIZED_DEVICE_IDENTITIES)
        self.assertIsNone(C.AUTHORIZED_XPU_SMI_QUERY_SCHEMA_SHA256)
        self.assertIsNone(C.AUTHORIZED_XPU_SMI_FIELD_PATHS)
        self.assertIsNone(C.AUTHORIZED_STAGE_INVENTORY_SHA256)
        self.assertIsNone(C.AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES)
        with self.assertRaisesRegex(C.ContractError, "launch blocked"):
            C.require_launch_authorized()

    def test_supervise_blocks_before_subprocess_or_output(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch.object(C.subprocess, "Popen") as popen,
        ):
            root = Path(directory)
            args = argparse.Namespace(
                ordinal=1,
                terminal=str(root / "terminal.json"),
                stderr=str(root / "stderr.log"),
                success=str(root / "success.json"),
                timeout_seconds=1.0,
                grace_seconds=0.1,
                command=["/bin/true"],
            )
            with self.assertRaisesRegex(C.ContractError, "launch blocked"):
                C.supervise_command(args)
            popen.assert_not_called()
            self.assertEqual(list(root.iterdir()), [])

    def test_worker_blocks_before_repo_or_qualifier_access(self) -> None:
        args = argparse.Namespace(
            ordinal=1,
            repo="/definitely/absent",
            physical_gpu=0,
            role="control",
            outer_arm_id="gpu0-default-a1",
            inner_arm_id="gpu0-a1",
            campaign_slot=1,
            output="/tmp/forbidden.json",
        )
        with mock.patch.object(C, "source_audit") as audit:
            with self.assertRaisesRegex(C.ContractError, "launch blocked"):
                C.worker_command(args)
            audit.assert_not_called()

    def test_campaign_compare_blocks_before_artifact_access(self) -> None:
        args = argparse.Namespace(
            restoration_terminal="/definitely/absent.json",
            terminals=[],
            output="/tmp/forbidden.json",
        )
        with mock.patch.object(C, "load_json") as loader:
            with self.assertRaisesRegex(C.ContractError, "launch blocked"):
                C.compare_command(args)
            loader.assert_not_called()

    def test_clock_parser_blocks_before_receipt_access(self) -> None:
        args = argparse.Namespace(device=0, receipt="/definitely/absent.json")
        with mock.patch.object(C, "load_json") as loader:
            with self.assertRaisesRegex(C.ContractError, "launch blocked"):
                C.parse_clock_command(args)
            loader.assert_not_called()

    def test_clock_parser_binds_exact_two_b70_inventory(self) -> None:
        payload = {
            "schema": "qwen38-xpu-smi-config-discovery-raw-v1",
            "device": 0,
            "captured_time_ns": 1,
            "xpu_smi": {
                "path": "/usr/bin/xpu-smi",
                "sha256": "4" * 64,
                "version": "fixture-version",
            },
            "config": {"frequency": {"minimum": 400, "maximum": 2800}},
            "discovery": {
                "device_list": [
                    {
                        "device_id": 0,
                        "uuid": "uuid-0",
                        "pci_bdf_address": "0000:01:00.0",
                        "device_name": C.EXPECTED_DEVICE_NAME,
                    },
                    {
                        "device_id": 1,
                        "uuid": "uuid-1",
                        "pci_bdf_address": "0000:02:00.0",
                        "device_name": C.EXPECTED_DEVICE_NAME,
                    },
                ]
            },
        }
        paths = {
            "devices": ("discovery", "device_list"),
            "entry_device_id": ("device_id",),
            "entry_uuid": ("uuid",),
            "entry_bdf": ("pci_bdf_address",),
            "entry_name": ("device_name",),
            "min_mhz": ("config", "frequency", "minimum"),
            "max_mhz": ("config", "frequency", "maximum"),
        }
        shape = C.json.dumps(
            C._json_shape(payload), sort_keys=True, separators=(",", ":")
        )
        schema_sha = C.hashlib.sha256(shape.encode()).hexdigest()
        identities = {
            0: {"uuid": "uuid-0", "bdf": "0000:01:00.0"},
            1: {"uuid": "uuid-1", "bdf": "0000:02:00.0"},
        }
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "clock.json"
            C.write_json_atomic(receipt, payload)
            with mock.patch.multiple(
                C,
                CAMPAIGN_LAUNCH_AUTHORIZED=True,
                AUTHORIZED_REMOTE_REPO_HEAD="0" * 40,
                AUTHORIZED_DEVICE_IDENTITIES=identities,
                AUTHORIZED_XPU_SMI_QUERY_SCHEMA_SHA256=schema_sha,
                AUTHORIZED_XPU_SMI_FIELD_PATHS=paths,
                AUTHORIZED_XPU_SMI_PATH="/usr/bin/xpu-smi",
                AUTHORIZED_XPU_SMI_SHA256="4" * 64,
                AUTHORIZED_XPU_SMI_VERSION="fixture-version",
                AUTHORIZED_STAGE_INVENTORY_SHA256="1" * 64,
                AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES={"libfixture.so": "2" * 64},
                DRIVER_SIGNAL_OWNERSHIP_AUTHORIZED=True,
                CLOCK_WRITER_EXCLUSION_AUTHORIZED=True,
                DRIVER_ENVIRONMENT_AUTHORIZED=True,
            ):
                parsed = C.parse_clock_command(
                    argparse.Namespace(device=0, receipt=str(receipt))
                )
                self.assertEqual(parsed["uuid"], "uuid-0")
                self.assertEqual((parsed["min_mhz"], parsed["max_mhz"]), (400, 2800))
                bad = copy.deepcopy(payload)
                bad["discovery"]["device_list"].pop()
                bad_path = Path(directory) / "bad.json"
                C.write_json_atomic(bad_path, bad)
                with self.assertRaises(C.ContractError):
                    C.parse_clock_command(
                        argparse.Namespace(device=0, receipt=str(bad_path))
                    )

    def _terminal_fixture(self, root: Path, ordinal: int = 1) -> tuple[Path, dict]:
        root.mkdir(parents=True, exist_ok=True)
        success = root / "success.json"
        stderr = root / "stderr.log"
        clock = root / "clock.json"
        runtime = root / "success.json.remote-runtime.json"
        success.write_bytes(b"{}\n")
        stderr.write_bytes(b"log\n")
        clock.write_bytes(b"{}\n")
        success.chmod(0o444)
        stderr.chmod(0o444)
        clock.chmod(0o444)
        campaign = CAMPAIGN_PATH.resolve(strict=True)
        campaign_sha = C.sha256_file(campaign)
        C.write_json_atomic(
            runtime,
            {
                "schema": "qwen38-q64k32-remote-runtime-map-v1",
                "host": C.REMOTE_HOSTNAME,
                "process_id": 20 + ordinal,
                "physical_device": C.PLAN[ordinal - 1]["device"],
                "authorized_libraries": {campaign.name: campaign_sha},
                "libraries": [
                    {
                        "basename": campaign.name,
                        "path": str(campaign),
                        "sha256": campaign_sha,
                    }
                ],
                "campaign_script": str(campaign),
                "campaign_script_sha256": campaign_sha,
            },
        )
        command_sha = hashlib.sha256(b"command").hexdigest()
        before = root / "terminal.json.phase-before-spawn.json"
        spawned = root / "terminal.json.phase-spawned.json"
        row = dict(C.PLAN[ordinal - 1])
        C.write_json_atomic(
            before,
            {
                "schema": "qwen38-q64k32-remote-clock-supervisor-phase-v1",
                "phase": "before-spawn",
                "time_ns": ordinal * 10,
                "supervisor_pid": 10,
                "plan": row,
                "command_sha256": command_sha,
            },
        )
        C.write_json_atomic(
            spawned,
            {
                "schema": "qwen38-q64k32-remote-clock-supervisor-phase-v1",
                "phase": "spawned",
                "time_ns": ordinal * 10 + 1,
                "supervisor_pid": 10,
                "worker_pid": 20 + ordinal,
                "worker_pgid": 20 + ordinal,
                "worker_start_ticks": 30 + ordinal,
                "plan": row,
                "command_sha256": command_sha,
            },
        )
        packet = {
            "schema": C.SCHEMA_TERMINAL,
            "status": "success",
            "valid": True,
            "plan": row,
            "host": C.REMOTE_HOSTNAME,
            "authorization": {
                "repo_head": "0" * 40,
                "stage_inventory_sha256": "1" * 64,
            },
            "clock_identity": {
                "device": row["device"],
                "uuid": "fixture-uuid",
                "bdf": "0000:00:00.0",
                "min_mhz": 400 if row["clock"] == "default" else 2800,
                "max_mhz": 2800,
                "captured_time_ns": ordinal * 10 - 1,
                "device_inventory_sha256": "3" * 64,
                "schema_sha256": "2" * 64,
                "receipt_sha256": C.sha256_file(clock),
            },
            "process": {
                "supervisor_pid": 10,
                "pid": 20 + ordinal,
                "pgid": 20 + ordinal,
                "start_ticks": 30 + ordinal,
                "returncode": 0,
                "started_time_ns": ordinal * 10,
                "finished_time_ns": ordinal * 10 + 3,
                "command_sha256": command_sha,
            },
            "watchdog": {
                "timeout_seconds": 900.0,
                "grace_seconds": 10.0,
                "cleanup": {
                    "identity_safe": True,
                    "term_sent": False,
                    "kill_sent": False,
                    "group_absent": True,
                },
            },
            "artifacts": {
                "success": C._artifact(success),
                "failure": None,
                "stderr": C._artifact(stderr),
                "clock": C._artifact(clock),
                "runtime": C._artifact(runtime),
            },
            "receipts": [C._artifact(before), C._artifact(spawned)],
            "error": None,
            "signals": [],
        }
        terminal = root / "terminal.json"
        C.write_json_atomic(terminal, packet)
        return terminal, packet

    def test_terminal_rederives_receipts_artifacts_and_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            terminal, packet = self._terminal_fixture(Path(directory))
            self.assertEqual(C.validate_terminal(terminal), packet)

    def test_terminal_rejects_receipt_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            terminal, packet = self._terminal_fixture(Path(directory))
            receipt = Path(packet["receipts"][0]["path"])
            receipt.chmod(0o644)
            receipt.write_text("{}\n", encoding="utf-8")
            receipt.chmod(0o444)
            with self.assertRaises(C.ContractError):
                C.validate_terminal(terminal)

    def test_terminal_rejects_false_success_and_writable_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            terminal, packet = self._terminal_fixture(root)
            success = Path(packet["artifacts"]["success"]["path"])
            success.chmod(0o644)
            with self.assertRaises(C.ContractError):
                C.validate_terminal(terminal)

    def test_terminal_rejects_plan_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, packet = self._terminal_fixture(root)
            packet = copy.deepcopy(packet)
            packet["plan"]["clock"] = "fixed"
            tampered = root / "tampered.json"
            C.write_json_atomic(tampered, packet)
            with self.assertRaises(C.ContractError):
                C.validate_terminal(tampered)

    def test_terminal_rejects_late_signal_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            terminal, _ = self._terminal_fixture(Path(directory))
            C.write_json_atomic(Path(f"{terminal}.signals-late.json"), {"signal": 15})
            with self.assertRaisesRegex(C.ContractError, "publication fence"):
                C.validate_terminal(terminal)

    def test_proc_stat_parser_handles_spaces_and_closing_parenthesis(self) -> None:
        tail = ["S", "1", "77", "77", "0"] + ["0"] * 14 + ["12345"]
        self.assertEqual(
            C._parse_proc_stat(f"99 (worker ) name) {' '.join(tail)}"), (77, 12345)
        )
        with self.assertRaises(C.ContractError):
            C._parse_proc_stat("99 (truncated) S 1")

    def test_group_absence_uses_kernel_group_probe_fail_closed(self) -> None:
        with mock.patch.object(C.os, "killpg", side_effect=ProcessLookupError):
            self.assertTrue(C._group_absent(123))
        with mock.patch.object(C.os, "killpg", side_effect=PermissionError):
            self.assertFalse(C._group_absent(123))
        with mock.patch.object(C.os, "killpg", return_value=None):
            self.assertFalse(C._group_absent(123))

    def test_unreaped_cleanup_preserves_evidence_after_repeated_wait_timeout(
        self,
    ) -> None:
        process = mock.Mock(pid=123)
        process.wait.side_effect = C.subprocess.TimeoutExpired("worker", 10)
        with (
            mock.patch.object(C, "_group_absent", return_value=False),
            mock.patch.object(C.os, "killpg"),
            mock.patch.object(C.time, "monotonic", side_effect=[0.0, 11.0]),
        ):
            result = C._terminate_unreaped_fresh_group(process, 10.0)
        self.assertTrue(result["identity_safe"])
        self.assertTrue(result["kill_sent"])
        self.assertFalse(result["group_absent"])

    def test_terminal_rejects_watchdog_and_supervisor_pid_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, packet = self._terminal_fixture(root)
            tampered = copy.deepcopy(packet)
            tampered["watchdog"]["timeout_seconds"] = 899.0
            watchdog_path = root / "watchdog-tampered.json"
            C.write_json_atomic(watchdog_path, tampered)
            with self.assertRaisesRegex(C.ContractError, "watchdog interval"):
                C.validate_terminal(watchdog_path)
            tampered = copy.deepcopy(packet)
            tampered["process"]["supervisor_pid"] = 11
            pid_path = root / "pid-tampered.json"
            C.write_json_atomic(pid_path, tampered)
            with self.assertRaisesRegex(
                C.ContractError, "supervisor receipt chronology"
            ):
                C.validate_terminal(pid_path)

    def test_worker_failure_is_a_valid_stopping_terminal_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, packet = self._terminal_fixture(root)
            failure = root / "success.json.failure.json"
            C.write_json_atomic(failure, {"fixture": "deep validation is source-gated"})
            packet = copy.deepcopy(packet)
            packet["status"] = "worker-failure"
            packet["valid"] = True
            packet["process"]["returncode"] = 1
            packet["artifacts"]["success"] = None
            packet["artifacts"]["failure"] = C._artifact(failure)
            packet["artifacts"]["runtime"] = None
            terminal = root / "worker-failure-terminal.json"
            C.write_json_atomic(terminal, packet)
            self.assertEqual(C.validate_terminal(terminal), packet)

    def test_restoration_terminal_rederives_immutable_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            devices = []
            for device in (0, 1):
                paths = []
                identities = []
                for phase in ("pre", "restored"):
                    receipt = root / f"gpu{device}-{phase}.json"
                    C.write_json_atomic(receipt, {"device": device, "phase": phase})
                    identity = {
                        "device": device,
                        "uuid": f"uuid-{device}",
                        "bdf": f"0000:0{device + 1}:00.0",
                        "min_mhz": 400,
                        "max_mhz": 2800,
                        "captured_time_ns": 1,
                        "device_inventory_sha256": "3" * 64,
                        "schema_sha256": "2" * 64,
                        "receipt_sha256": C.sha256_file(receipt),
                    }
                    paths.append(receipt)
                    identities.append(identity)
                devices.append(
                    {
                        "device": device,
                        "pre_run": identities[0],
                        "restored": identities[1],
                        "pre_run_artifact": C._artifact(paths[0]),
                        "restored_artifact": C._artifact(paths[1]),
                    }
                )
            arm_terminals = [
                C._artifact(self._terminal_fixture(root / f"arm-{ordinal}", ordinal)[0])
                for ordinal in range(1, 17)
            ]
            packet = {
                "schema": C.SCHEMA_RESTORATION,
                "status": "restored",
                "valid": True,
                "host": C.REMOTE_HOSTNAME,
                "authorization": {
                    "repo_head": "0" * 40,
                    "stage_inventory_sha256": "1" * 64,
                },
                "original_exit_code": 0,
                "shell_restore_status": 0,
                "devices": devices,
                "arm_terminals": arm_terminals,
                "terminal_prefix_count": 16,
                "terminal_prefix_statuses": ["success"] * 16,
                "campaign_complete": True,
                "clock_errors": [],
                "campaign_errors": [],
                "finished_time_ns": 1000,
            }
            terminal = root / "restoration.json"
            C.write_json_atomic(terminal, packet)
            self.assertEqual(C.validate_restoration(terminal), packet)
            self.assertEqual(
                C.validate_restoration(terminal, require_complete=True), packet
            )
            prefix_packet = copy.deepcopy(packet)
            prefix_packet["original_exit_code"] = 1
            prefix_packet["arm_terminals"] = arm_terminals[:1] + [None] * 15
            prefix_packet["terminal_prefix_count"] = 1
            prefix_packet["terminal_prefix_statuses"] = ["success"]
            prefix_packet["campaign_complete"] = False
            prefix_path = root / "prefix-restoration.json"
            C.write_json_atomic(prefix_path, prefix_packet)
            self.assertEqual(C.validate_restoration(prefix_path), prefix_packet)
            with self.assertRaisesRegex(C.ContractError, "campaign is incomplete"):
                C.validate_restoration(prefix_path, require_complete=True)
            Path(devices[0]["restored_artifact"]["path"]).chmod(0o644)
            with self.assertRaises(C.ContractError):
                C.validate_restoration(terminal)

    def test_driver_has_first_run_gate_restore_trap_and_exact_order(self) -> None:
        driver = (
            HERE / "run-20260821-qwen38-mtp5-m6-fa-q64k32-remote-clock-abba.sh"
        ).read_text(encoding="utf-8")
        run_block = driver.index("if [[ $action == run ]]")
        mkdir = driver.index('mkdir -- "$result"')
        sudo = driver.index("sudo -n true")
        self.assertLess(run_block, mkdir)
        self.assertLess(run_block, sudo)
        self.assertIn("launch_authorized=false", driver)
        self.assertIn("trap 'restore_pre_run_ranges $?' EXIT", driver)
        self.assertIn("trap 'restore_pre_run_ranges 130' INT", driver)
        self.assertIn("trap 'restore_pre_run_ranges 143' TERM", driver)
        self.assertIn("trap 'restore_pre_run_ranges 129' HUP", driver)
        self.assertIn("trap '' EXIT INT TERM HUP", driver)
        self.assertIn("set_clock 0 400,2800 initial-default", driver)
        self.assertIn("set_clock 1 400,2800 initial-default", driver)
        self.assertIn('set_clock "$device" 2800,2800 "$state"', driver)
        self.assertIn("original_ranges[0]=$(parse_range 0", driver)
        self.assertIn("original_ranges[1]=$(parse_range 1", driver)
        self.assertIn('--frequencyrange "${original_ranges[$device]}"', driver)
        capture = driver.index("original_ranges[1]=$(parse_range 1")
        trap = driver.index("trap 'restore_pre_run_ranges $?' EXIT")
        precondition = driver.index("set_clock 0 400,2800 initial-default")
        self.assertLess(capture, trap)
        self.assertLess(trap, precondition)
        self.assertIn(
            "for block in '0 default' '1 fixed' '0 fixed' '1 default'", driver
        )
        self.assertIn(
            "'1 control a1' '2 candidate b1' '3 candidate b2' '4 control a2'",
            driver,
        )
        fixed_start = driver.index("fixed_packets=(")
        fixed_end = driver.index(")", fixed_start)
        fixed = driver[fixed_start:fixed_end]
        self.assertLess(fixed.index("arm-09.json"), fixed.index("arm-05.json"))
        self.assertIn('"$xpu_smi" discovery -j', driver)
        self.assertIn("xpu_smi=/usr/bin/xpu-smi", driver)
        self.assertIn('verify "$xpu_smi" "$authorized_xpu_smi_sha"', driver)
        self.assertIn("driver_signal_ownership_authorized=false", driver)
        self.assertIn("seal-clock-receipt", driver)
        self.assertIn("REMOTE_SYSTEM_RUNTIME_INVENTORY_SHA256_TO_FREEZE", driver)

    def test_preparer_constructs_both_exact_stages_without_build(self) -> None:
        helper = (
            HERE / "prepare-qwen38-m6-head256-q64k32-remote-stage-20260821.sh"
        ).read_text(encoding="utf-8")
        self.assertNotIn("rsync ", helper)
        self.assertNotIn("cmake ", helper)
        self.assertNotIn("ninja ", helper)
        self.assertIn(C.CANDIDATE_DEVICE_SHA256, helper)
        self.assertIn(C.CONTROL_DEVICE_SHA256, helper)
        self.assertIn(C.CANDIDATE_GRAPH_SHA256, helper)
        self.assertIn(C.CONTROL_GRAPH_SHA256, helper)
        self.assertIn("cp -R --reflink=auto --preserve=mode,timestamps --", helper)
        self.assertNotIn('cp -al -- "$incoming_runtime"', helper)
        self.assertIn('cp -al -- "$candidate_tmp_stage/." "$control_tmp/"', helper)
        self.assertIn('find "$selected_stage" -type f | wc -l', helper)
        self.assertIn('find "$selected_stage" -perm /222', helper)
        self.assertIn("incoming transfer packet inventory differs", helper)
        self.assertIn("candidate file aliases mutable incoming packet", helper)
        self.assertIn("trap '' EXIT INT TERM HUP", helper)
        self.assertIn("candidate_identity=$(stat -c", helper)
        self.assertIn("control_identity=$(stat -c", helper)
        self.assertIn("exactly 20 regular package files", helper)

    def test_supervisor_and_compare_bind_runtime_and_restoration(self) -> None:
        source = CAMPAIGN_PATH.read_text(encoding="utf-8")
        self.assertIn('Path(f"{success}.remote-runtime.json")', source)
        self.assertIn('"runtime": _artifact(runtime_sidecar)', source)
        self.assertIn("validate_runtime_sidecar", source)
        self.assertIn(
            "validate_restoration(restoration_path, require_complete=True)", source
        )
        self.assertIn('"clock_by_policy_interactions"', source)
        self.assertIn("selected_arms", source)
        self.assertIn("_terminate_unreaped_fresh_group", source)
        self.assertIn("if returncode is not None and cleanup", source)
        self.assertIn("signal.sigpending()", source)
        self.assertIn("signals-late.json", source)
        self.assertIn("strict_stage_graphs", source)
        self.assertIn("stage contains a writable node", source)

    def test_remote_operator_adapter_preserves_original_then_virtualizes(self) -> None:
        source = CAMPAIGN_PATH.read_text(encoding="utf-8")
        validate = source.index("qualifier._validate_run_packet")
        deep_copy = source.index("virtual_packets = copy.deepcopy(packets)")
        inherited = source.index("inherited = qualifier.compare_packets")
        self.assertLess(validate, deep_copy)
        self.assertLess(deep_copy, inherited)
        self.assertIn(
            '"schema": "qwen38-q64k32-remote-clock-operator-compare-v1"', source
        )
        self.assertIn('"virtual_validation_device_map"', source)

    def test_campaign_forbids_local_absolute_timing_pooling(self) -> None:
        source = CAMPAIGN_PATH.read_text(encoding="utf-8")
        self.assertIn('"absolute_timing_pooling_with_local_forbidden": True', source)
        self.assertNotIn("151.46586", source)


if __name__ == "__main__":
    unittest.main()
