#!/usr/bin/env python3
"""CPU-only tests for the blocked reference-host Q64K32 clock campaign."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
CAMPAIGN_PATH = HERE / "qwen38_mtp5_m6_fa_q64k32_remote_clock_campaign.py"
DRIVER_PATH = HERE / "run-20260821-qwen38-mtp5-m6-fa-q64k32-remote-clock-abba.sh"
HELPER_PATH = HERE / "prepare-qwen38-m6-head256-q64k32-remote-stage-20260821.sh"
SPEC = importlib.util.spec_from_file_location("remote_clock_campaign", CAMPAIGN_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load campaign module")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


def bash_function(source: str, name: str) -> str:
    match = re.search(rf"(?ms)^{re.escape(name)}\(\) \{{\n.*?^\}}\n", source)
    if match is None:
        raise AssertionError(f"missing Bash function: {name}")
    return match.group(0)


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

    def test_passive_inventory_dependency_recipe_and_opaque_runtime_boundary(
        self,
    ) -> None:
        inventory_path = (
            HERE.parent / "data/2026-08-21-qwen38-q64k32-remote-passive-inventory.json"
        )
        inventory = C.load_json(inventory_path)
        projected = [
            {key: row[key] for key in ("soname", "path", "resolved_path", "sha256")}
            for row in inventory["xpu_smi"]["dependencies"]
        ]
        encoded = C.json.dumps(
            projected, sort_keys=True, separators=(",", ":")
        ).encode()
        self.assertEqual(
            C.hashlib.sha256(encoded).hexdigest(),
            inventory["xpu_smi"]["dependency_inventory_sha256"],
        )
        self.assertIn(
            "not rederivable",
            inventory["python_and_xpu_runtime"][
                "passive_runtime_candidate_inventory_sha256_classification"
            ],
        )

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
        self.assertIs(C.DRIVER_SIGNAL_OWNERSHIP_AUTHORIZED, True)
        self.assertIs(C.CLOCK_WRITER_EXCLUSION_AUTHORIZED, False)
        self.assertIs(C.DRIVER_ENVIRONMENT_AUTHORIZED, True)
        self.assertIsNone(C.AUTHORIZED_REMOTE_REPO_HEAD)
        self.assertEqual(
            C.AUTHORIZED_DEVICE_IDENTITIES,
            {
                0: {
                    "uuid": "00000000-0000-0003-0000-0000e2238086",
                    "bdf": "0000:03:00.0",
                },
                1: {
                    "uuid": "00000000-0000-00e3-0000-0000e2238086",
                    "bdf": "0000:e3:00.0",
                },
            },
        )
        self.assertEqual(
            C.AUTHORIZED_XPU_SMI_QUERY_SCHEMA_SHA256,
            "afb4b7fe6d1ea9847559734fae1b73241f18587f036ae3d18376c146fa6eafba",
        )
        self.assertEqual(
            C.AUTHORIZED_XPU_SMI_FIELD_PATHS["min_mhz"],
            ("config", "tile_config_data", 0, "min_frequency"),
        )
        self.assertEqual(C.AUTHORIZED_XPU_SMI_PATH, "/usr/bin/xpu-smi")
        self.assertEqual(
            C.AUTHORIZED_XPU_SMI_SHA256,
            "01c7b83881e99754642b827ba05418d263aed615933e3df35821af7733eb8d83",
        )
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
            terminal, packet = self._terminal_fixture(Path(directory))
            C.write_json_atomic(Path(f"{terminal}.signals-late.json"), {"signal": 15})
            with self.assertRaisesRegex(C.ContractError, "publication fence"):
                C.validate_terminal(terminal)
            self.assertEqual(
                C.validate_terminal(terminal, allow_late_signal_for_cleanup=True),
                packet,
            )

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

    def _live_group(self, child_exits: bool = False) -> subprocess.Popen[bytes]:
        code = (
            "import subprocess,sys,time; "
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
            + ("sys.exit(0)" if child_exits else "time.sleep(60)")
        )
        process = subprocess.Popen(
            [sys.executable, "-c", code],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        for _ in range(100):
            try:
                C._proc_start_ticks(process.pid)
                return process
            except (OSError, C.ContractError):
                time.sleep(0.01)
        process.kill()
        process.wait(timeout=5)
        self.fail("live test process identity did not appear")

    def test_live_watchdog_timeout_kills_leader_and_descendant(self) -> None:
        process = self._live_group()
        try:
            start_ticks = C._proc_start_ticks(process.pid)
            returncode, cleanup, status = C._watch_owned_process(
                process, start_ticks, 0.05, 1.0, lambda: False
            )
            self.assertEqual(status, "timeout")
            self.assertIsNotNone(returncode)
            self.assertTrue(cleanup["identity_safe"])
            self.assertTrue(cleanup["term_sent"] or cleanup["kill_sent"])
            self.assertTrue(cleanup["group_absent"])
            self.assertTrue(C._group_absent(process.pid))
        finally:
            if not C._group_absent(process.pid):
                os.killpg(process.pid, signal.SIGKILL)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()

    def test_live_watchdog_interrupt_path_kills_owned_group(self) -> None:
        process = self._live_group()
        try:
            start_ticks = C._proc_start_ticks(process.pid)
            returncode, cleanup, status = C._watch_owned_process(
                process, start_ticks, 2.0, 1.0, lambda: True
            )
            self.assertEqual(status, "interrupted")
            self.assertIsNotNone(returncode)
            self.assertTrue(cleanup["identity_safe"])
            self.assertTrue(cleanup["term_sent"] or cleanup["kill_sent"])
            self.assertTrue(cleanup["group_absent"])
        finally:
            if not C._group_absent(process.pid):
                os.killpg(process.pid, signal.SIGKILL)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()

    def test_live_watchdog_cleans_descendant_after_normal_leader_exit(self) -> None:
        process = self._live_group(child_exits=True)
        try:
            start_ticks = C._proc_start_ticks(process.pid)
            returncode, cleanup, status = C._watch_owned_process(
                process, start_ticks, 2.0, 1.0, lambda: False
            )
            self.assertIsNone(status)
            self.assertEqual(returncode, 0)
            self.assertTrue(cleanup["identity_safe"])
            self.assertTrue(cleanup["group_absent"])
        finally:
            if not C._group_absent(process.pid):
                os.killpg(process.pid, signal.SIGKILL)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()

    def test_live_signal_after_terminal_publication_creates_late_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "signal_fence.py"
            terminal = Path(directory) / "terminal.json"
            late = Path(f"{terminal}.signals-late.json")
            script.write_text(
                "import importlib.util,os,pathlib,signal,time\n"
                f"source=pathlib.Path({str(CAMPAIGN_PATH)!r})\n"
                "spec=importlib.util.spec_from_file_location('campaign_live',source)\n"
                "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)\n"
                f"terminal=pathlib.Path({str(terminal)!r})\n"
                f"late=pathlib.Path({str(late)!r})\n"
                "payload={'schema':'fixture','status':'success','valid':True}\n"
                "module._publish_terminal_with_signal_fence(terminal,late,payload,"
                "(signal.SIGINT,signal.SIGTERM,signal.SIGHUP))\n"
                "os.kill(os.getpid(),signal.SIGTERM); time.sleep(0.05)\n"
                "assert late.is_file(); assert module.load_json(late)['signals']==[15]\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, "-B", str(script)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            self.assertTrue(late.is_file())

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
        driver = DRIVER_PATH.read_text(encoding="utf-8")
        run_block = driver.index("if [[ $action == run ]]")
        mkdir = driver.index('"$mkdir_bin" -- "$result"')
        sudo = driver.index('"$sudo_bin" -n "$true_bin"')
        self.assertLess(run_block, mkdir)
        self.assertLess(run_block, sudo)
        self.assertIn("launch_authorized=false", driver)
        self.assertIn(
            "trap 'exit_rc=$?; active_forward_signal=TERM; "
            'restore_pre_run_ranges "$exit_rc"\' EXIT',
            driver,
        )
        self.assertIn(
            "trap 'handle_driver_signal INT 130' INT",
            driver,
        )
        self.assertIn(
            "trap 'handle_driver_signal TERM 143' TERM",
            driver,
        )
        self.assertIn(
            "trap 'handle_driver_signal HUP 129' HUP",
            driver,
        )
        self.assertIn("trap '' EXIT INT TERM HUP", driver)
        self.assertIn("quiesce_active_supervisor", driver)
        self.assertIn("clock restoration is forbidden", driver)
        self.assertIn("supervisor_spawn_state=spawning", driver)
        self.assertIn('claim_active_supervisor "$!"', driver)
        self.assertIn("if [[ $supervisor_spawn_state == spawning ]]", driver)
        self.assertIn('wait "$active_supervisor_pid"', driver)
        self.assertLess(
            driver.index("if ! quiesce_active_supervisor"),
            driver.index("cleanup_state=restoring"),
        )
        self.assertIn("set_clock 0 400,2800 initial-default", driver)
        self.assertIn("set_clock 1 400,2800 initial-default", driver)
        self.assertIn('set_clock "$device" 2800,2800 "$state"', driver)
        self.assertIn("original_ranges[0]=$(parse_range 0", driver)
        self.assertIn("original_ranges[1]=$(parse_range 1", driver)
        self.assertIn('--frequencyrange "${original_ranges[$device]}"', driver)
        capture = driver.index("original_ranges[1]=$(parse_range 1")
        trap = driver.index("trap 'exit_rc=$?")
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
        self.assertIn("driver_signal_ownership_authorized=true", driver)
        self.assertIn("driver_environment_authorized=true", driver)
        self.assertIn('exec "$env_bin" -i', driver)
        self.assertIn("QWEN38_REMOTE_DRIVER_CLEAN", driver)
        self.assertIn("management_python()", driver)
        self.assertIn("mapfile -t exported_environment_names < <(compgen -e)", driver)
        self.assertIn("unexpected exported management environment", driver)
        self.assertIn("[[ -z $(declare -Fx) ]]", driver)
        self.assertIn('"$sudo_bin" -n "$env_bin" -i', driver)
        self.assertIn("clean_path=/usr/bin:/bin", driver)
        self.assertNotIn('sudo -n "$xpu_smi"', driver)
        self.assertIn("seal-clock-receipt", driver)
        self.assertIn("REMOTE_SYSTEM_RUNTIME_INVENTORY_SHA256_TO_FREEZE", driver)

    def test_driver_run_gate_precedes_clean_reexec_and_any_host_operation(self) -> None:
        driver_path = (
            HERE / "run-20260821-qwen38-mtp5-m6-fa-q64k32-remote-clock-abba.sh"
        )
        completed = subprocess.run(
            ["/usr/bin/bash", str(driver_path), "run"],
            env={
                "PATH": "/tmp/hostile",
                "PYTHONPATH": "/tmp/hostile",
                "LD_LIBRARY_PATH": "/tmp/hostile",
            },
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn(b"launch blocked", completed.stderr)
        self.assertNotIn(b"requires steve-TURIND8-2L2T", completed.stderr)

    def test_driver_audit_reexec_removes_management_contamination(self) -> None:
        completed = subprocess.run(
            ["/usr/bin/bash", str(DRIVER_PATH), "audit"],
            env={
                "PATH": "/tmp/hostile",
                "PYTHONPATH": "/tmp/hostile",
                "ZE_AFFINITY_MASK": "99",
                "GIT_CONFIG_GLOBAL": "/tmp/hostile.gitconfig",
            },
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn(b"requires steve-TURIND8-2L2T", completed.stderr)
        self.assertNotIn(b"forbidden management environment", completed.stderr)

    def test_driver_rejects_forged_clean_marker_and_exported_function(self) -> None:
        clean = {
            "HOME": "/home/steve",
            "USER": "steve",
            "LOGNAME": "steve",
            "SHELL": "/usr/bin/bash",
            "LANG": "C.UTF-8",
            "PATH": "/usr/bin:/bin",
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "QWEN38_REMOTE_DRIVER_CLEAN": "remote-q64k32-management-v1",
        }
        cases = (
            (
                {**clean, "GLIBC_TUNABLES": "glibc.malloc.trim_threshold=1"},
                b"unexpected exported management environment",
            ),
            ({**clean, "BASH_FUNC_evil%%": "() { :; }"}, b"exported Bash function"),
        )
        for environment, expected in cases:
            with self.subTest(expected=expected):
                completed = subprocess.run(
                    ["/usr/bin/bash", str(DRIVER_PATH), "audit"],
                    env=environment,
                    cwd="/home/steve",
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(completed.returncode, 2)
                self.assertIn(expected, completed.stderr)
                self.assertNotIn(b"requires steve-TURIND8-2L2T", completed.stderr)

    def test_live_shell_signal_is_deferred_until_supervisor_pid_publication(
        self,
    ) -> None:
        source = DRIVER_PATH.read_text(encoding="utf-8")
        functions = "\n".join(
            bash_function(source, name)
            for name in ("handle_driver_signal", "claim_active_supervisor")
        )
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "events.log"
            script = f"""#!/usr/bin/bash
set -euo pipefail
active_supervisor_pid=
active_forward_signal=TERM
supervisor_spawn_state=idle
deferred_signal=
deferred_exit_code=
die() {{ printf 'die:%s\\n' "$*" >>{log!s}; exit 2; }}
restore_pre_run_ranges() {{
  printf 'restore:%s:%s:%s\\n' "$1" "$active_forward_signal" "$active_supervisor_pid" >>{log!s}
  [[ -n $active_supervisor_pid ]]
  /usr/bin/kill -TERM "$active_supervisor_pid" 2>/dev/null || true
  wait "$active_supervisor_pid" 2>/dev/null || true
}}
{functions}
trap 'handle_driver_signal TERM 143' TERM
supervisor_spawn_state=spawning
/usr/bin/sleep 60 &
spawned=$!
/usr/bin/kill -TERM $$
[[ -z $active_supervisor_pid && $deferred_signal == TERM && $deferred_exit_code == 143 ]]
claim_active_supervisor "$spawned"
[[ $active_supervisor_pid == "$spawned" && $supervisor_spawn_state == owned ]]
"""
            completed = subprocess.run(
                ["/usr/bin/bash"],
                input=script.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            events = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(events), 1)
            self.assertRegex(events[0], r"^restore:143:TERM:[1-9][0-9]*$")

    def test_restoration_accumulates_first_device_failure_and_seals_terminal(
        self,
    ) -> None:
        source = DRIVER_PATH.read_text(encoding="utf-8")
        restore_functions = "\n".join(
            bash_function(source, name)
            for name in ("restore_one_device", "restore_all_devices")
        )
        restore_driver = bash_function(source, "restore_pre_run_ranges")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.log"
            exercise_devices = f"""#!/usr/bin/bash
set -u
result={root!s}
declare -a original_ranges=([0]=400,2700 [1]=500,2800)
timeout_bin=fake_timeout; sudo_bin=fake_sudo; env_bin=fake_env; xpu_smi=fake_xpu
chmod_bin=fake_chmod; mv_bin=fake_mv; rm_bin=fake_rm; clean_path=/usr/bin:/bin
fake_timeout() {{
  local previous= argument device=unknown
  for argument in "$@"; do [[ $previous == -d ]] && device=$argument; previous=$argument; done
  printf 'set:%s\\n' "$device" >>{events!s}; printf '{{}}\\n'
}}
fake_sudo() {{ :; }}; fake_env() {{ :; }}; fake_xpu() {{ :; }}
fake_chmod() {{ [[ $2 == *clock-0-* ]] && return 1; /usr/bin/chmod "$@"; }}
fake_mv() {{ /usr/bin/mv "$@"; }}
fake_rm() {{ /usr/bin/rm "$@"; }}
clock_receipt() {{ printf 'receipt:%s\\n' "$1" >>{events!s}; printf '{{}}\\n' >"$result/clock-$1-restore-effective.json"; }}
parse_range() {{ printf '%s\\n' "${{original_ranges[$1]}}"; }}
{restore_functions}
set +e
restore_all_devices
rc=$?
set -e
[[ $rc -eq 1 ]]
"""
            completed = subprocess.run(
                ["/usr/bin/bash"],
                input=exercise_devices.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            self.assertEqual(
                events.read_text(encoding="utf-8").splitlines(),
                ["set:0", "set:1", "receipt:1"],
            )
            seal_log = root / "seal.log"
            exercise_terminal = f"""#!/usr/bin/bash
set -u
cleanup_state=idle; active_supervisor_pid=; active_forward_signal=TERM
restore_rc=0; result={root!s}; declare -a arm_terminals=()
quiesce_active_supervisor() {{ return 0; }}
restore_all_devices() {{ printf 'restore-all\\n' >>{seal_log!s}; return 1; }}
management_python() {{ printf '%s\\n' "$*" >>{seal_log!s}; return 1; }}
{restore_driver}
restore_pre_run_ranges 42
"""
            completed = subprocess.run(
                ["/usr/bin/bash"],
                input=exercise_terminal.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
            )
            self.assertEqual(completed.returncode, 97)
            seal_events = seal_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(seal_events[0], "restore-all")
            self.assertIn("seal-restoration", seal_events[1])

    def test_preparer_constructs_both_exact_stages_without_build(self) -> None:
        helper = HELPER_PATH.read_text(encoding="utf-8")
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
        self.assertIn("[[ ! -e $1 && ! -L $1 ]]", helper)
        self.assertIn("mv_bin=/usr/bin/mv", helper)
        self.assertIn('"$mv_bin" -T --no-clobber', helper)
        self.assertIn("publish collision left source present", helper)
        self.assertIn("destination identity differs after publish", helper)
        self.assertIn("remove_owned_tree", helper)
        self.assertIn("stage seal requires HEAD == origin/main", helper)

    def test_preparer_rejects_dangling_and_all_publish_collision_types(self) -> None:
        source = HELPER_PATH.read_text(encoding="utf-8")
        functions = "\n".join(
            bash_function(source, name)
            for name in ("absent_path", "path_identity", "publish_owned_tree")
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dangling = root / "dangling"
            dangling.symlink_to(root / "missing")
            check = subprocess.run(
                [
                    "/usr/bin/bash",
                    "-c",
                    f'{functions}\nabsent_path "$1"',
                    "bash",
                    str(dangling),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(check.returncode, 0)
        for collision_kind in ("regular", "directory", "dangling", "directory-symlink"):
            with (
                self.subTest(collision_kind=collision_kind),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                source_path = root / "source"
                destination = root / "destination"
                source_path.mkdir()
                identity = f"{source_path.stat().st_dev}:{source_path.stat().st_ino}"
                if collision_kind == "regular":
                    destination.write_text("collision\n", encoding="utf-8")
                elif collision_kind == "directory":
                    destination.mkdir()
                elif collision_kind == "dangling":
                    destination.symlink_to(root / "missing")
                else:
                    target = root / "target"
                    target.mkdir()
                    destination.symlink_to(target, target_is_directory=True)
                before = destination.lstat()
                completed = subprocess.run(
                    [
                        "/usr/bin/bash",
                        "-c",
                        f"mv_bin=/usr/bin/mv\n{functions}\n"
                        'publish_owned_tree "$1" "$2" "$3" fixture',
                        "bash",
                        str(source_path),
                        str(destination),
                        identity,
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertNotEqual(completed.returncode, 0)
                self.assertTrue(source_path.is_dir())
                after = destination.lstat()
                self.assertEqual(
                    (before.st_dev, before.st_ino), (after.st_dev, after.st_ino)
                )
                self.assertRegex(
                    completed.stderr,
                    rb"publish (failed|collision left source present)",
                )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source"
            destination = root / "destination"
            source_path.mkdir()
            identity = f"{source_path.stat().st_dev}:{source_path.stat().st_ino}"
            completed = subprocess.run(
                [
                    "/usr/bin/bash",
                    "-c",
                    f"fake_mv() {{ return 0; }}\nmv_bin=fake_mv\n{functions}\n"
                    'publish_owned_tree "$1" "$2" "$3" skipped',
                    "bash",
                    str(source_path),
                    str(destination),
                    identity,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertTrue(source_path.is_dir())
            self.assertFalse(destination.exists())
            self.assertIn(b"publish collision left source present", completed.stderr)

    def test_preparer_publication_and_cleanup_are_inode_owned(self) -> None:
        source = HELPER_PATH.read_text(encoding="utf-8")
        names = (
            "absent_path",
            "path_identity",
            "remove_owned_tree",
            "publish_owned_tree",
            "cleanup",
        )
        functions = "\n".join(bash_function(source, name) for name in names)
        with tempfile.TemporaryDirectory() as directory:
            root_path = Path(directory)
            candidate_tmp = root_path / "candidate.tmp"
            control_tmp = root_path / "control.tmp"
            candidate_root = root_path / "candidate"
            control_root = root_path / "control"
            candidate_tmp.mkdir()
            control_tmp.mkdir()
            candidate_identity = (
                f"{candidate_tmp.stat().st_dev}:{candidate_tmp.stat().st_ino}"
            )
            control_identity = (
                f"{control_tmp.stat().st_dev}:{control_tmp.stat().st_ino}"
            )
            script = f"""#!/usr/bin/bash
set -euo pipefail
mv_bin=/usr/bin/mv; chmod_bin=/usr/bin/chmod; rm_bin=/usr/bin/rm
candidate_tmp={candidate_tmp!s}; control_tmp={control_tmp!s}
root={candidate_root!s}; control={control_root!s}
candidate_identity={candidate_identity}; control_identity={control_identity}; complete=false
{functions}
publish_owned_tree "$candidate_tmp" "$root" "$candidate_identity" candidate
publish_owned_tree "$control_tmp" "$control" "$control_identity" control
complete=true
"""
            completed = subprocess.run(
                ["/usr/bin/bash"],
                input=script.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            self.assertFalse(candidate_tmp.exists())
            self.assertFalse(control_tmp.exists())
            self.assertEqual(
                f"{candidate_root.stat().st_dev}:{candidate_root.stat().st_ino}",
                candidate_identity,
            )
            self.assertEqual(
                f"{control_root.stat().st_dev}:{control_root.stat().st_ino}",
                control_identity,
            )
            owned = root_path / "private-owned"
            displaced = root_path / "private-displaced"
            owned.mkdir()
            owned_identity = f"{owned.stat().st_dev}:{owned.stat().st_ino}"
            owned.rename(displaced)
            owned.mkdir()
            removal = subprocess.run(
                [
                    "/usr/bin/bash",
                    "-c",
                    f"chmod_bin=/usr/bin/chmod; rm_bin=/usr/bin/rm\n{functions}\n"
                    'remove_owned_tree "$1" "$2"',
                    "bash",
                    str(owned),
                    owned_identity,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(removal.returncode, 0)
            self.assertTrue(owned.is_dir())
            self.assertTrue(displaced.is_dir())

    def test_preparer_cleanup_preserves_collision_and_handles_publish_signals(
        self,
    ) -> None:
        source = HELPER_PATH.read_text(encoding="utf-8")
        names = (
            "absent_path",
            "path_identity",
            "remove_owned_tree",
            "publish_owned_tree",
            "cleanup",
        )
        functions = "\n".join(bash_function(source, name) for name in names)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            candidate_tmp = base / "candidate.tmp"
            control_tmp = base / "control.tmp"
            candidate_root = base / "candidate"
            control_root = base / "control"
            candidate_tmp.mkdir()
            control_tmp.mkdir()
            control_root.write_text("collision\n", encoding="utf-8")
            candidate_identity = (
                f"{candidate_tmp.stat().st_dev}:{candidate_tmp.stat().st_ino}"
            )
            control_identity = (
                f"{control_tmp.stat().st_dev}:{control_tmp.stat().st_ino}"
            )
            collision_inode = control_root.stat().st_ino
            script = f"""#!/usr/bin/bash
set -u
mv_bin=/usr/bin/mv; chmod_bin=/usr/bin/chmod; rm_bin=/usr/bin/rm
candidate_tmp={candidate_tmp!s}; control_tmp={control_tmp!s}
root={candidate_root!s}; control={control_root!s}
candidate_identity={candidate_identity}; control_identity={control_identity}; complete=false
{functions}
trap cleanup EXIT
publish_owned_tree "$candidate_tmp" "$root" "$candidate_identity" candidate || exit 1
publish_owned_tree "$control_tmp" "$control" "$control_identity" control || exit 1
"""
            completed = subprocess.run(
                ["/usr/bin/bash"],
                input=script.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertFalse(candidate_root.exists())
            self.assertFalse(candidate_tmp.exists())
            self.assertFalse(control_tmp.exists())
            self.assertEqual(control_root.stat().st_ino, collision_inode)
        for signal_point in ("candidate", "control"):
            with (
                self.subTest(signal_point=signal_point),
                tempfile.TemporaryDirectory() as directory,
            ):
                base = Path(directory)
                candidate_tmp = base / "candidate.tmp"
                control_tmp = base / "control.tmp"
                candidate_root = base / "candidate"
                control_root = base / "control"
                candidate_tmp.mkdir()
                control_tmp.mkdir()
                candidate_identity = (
                    f"{candidate_tmp.stat().st_dev}:{candidate_tmp.stat().st_ino}"
                )
                control_identity = (
                    f"{control_tmp.stat().st_dev}:{control_tmp.stat().st_ino}"
                )
                second_publish = (
                    'publish_owned_tree "$control_tmp" "$control" "$control_identity" control\n'
                    if signal_point == "control"
                    else ""
                )
                script = f"""#!/usr/bin/bash
set -u
mv_bin=/usr/bin/mv; chmod_bin=/usr/bin/chmod; rm_bin=/usr/bin/rm
candidate_tmp={candidate_tmp!s}; control_tmp={control_tmp!s}
root={candidate_root!s}; control={control_root!s}
candidate_identity={candidate_identity}; control_identity={control_identity}; complete=false
{functions}
trap cleanup EXIT
trap 'exit 130' INT
publish_owned_tree "$candidate_tmp" "$root" "$candidate_identity" candidate
{second_publish}/usr/bin/kill -INT $$
exit 3
"""
                completed = subprocess.run(
                    ["/usr/bin/bash"],
                    input=script.encode(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(completed.returncode, 130)
                self.assertFalse(candidate_tmp.exists())
                self.assertFalse(control_tmp.exists())
                self.assertFalse(candidate_root.exists())
                self.assertFalse(control_root.exists())

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
        self.assertIn("_watch_owned_process", source)
        self.assertIn("_publish_terminal_with_signal_fence", source)
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

    def test_numeric_clock_effect_and_interaction_fixture(self) -> None:
        cells: dict[tuple[int, str, int, str], list[list[float]]] = {}
        for device in (0, 1):
            for role in ("control", "candidate"):
                saving = 10.0 if role == "control" else 20.0
                for kv_length in C.FIXTURES:
                    base = 100.0 + device * 10.0 + kv_length / 1000.0
                    cells[(device, role, kv_length, "default")] = [
                        [base] * 40,
                        [base] * 40,
                    ]
                    fixed = base * (1.0 - saving / 100.0)
                    cells[(device, role, kv_length, "fixed")] = [
                        [fixed] * 40,
                        [fixed] * 40,
                    ]
        rows, interactions, passed = C.compute_clock_effects(cells)
        self.assertTrue(passed)
        self.assertEqual(len(rows), 16)
        self.assertEqual(len(interactions), 8)
        for row in rows:
            expected = 10.0 if row["role"] == "control" else 20.0
            self.assertAlmostEqual(row["fixed_saving_percent"], expected)
            self.assertAlmostEqual(row["bootstrap_95_percent_ci"][0], expected)
            self.assertAlmostEqual(row["bootstrap_95_percent_ci"][1], expected)
        for row in interactions:
            self.assertAlmostEqual(row["fixed_clock_policy_interaction_percent"], 10.0)
            self.assertAlmostEqual(row["bootstrap_95_percent_ci"][0], 10.0)
            self.assertAlmostEqual(row["bootstrap_95_percent_ci"][1], 10.0)

    def test_numeric_clock_effect_rejects_nonfinite_missing_and_extra_cells(
        self,
    ) -> None:
        cells = {
            (device, role, kv_length, state): [[100.0] * 40, [101.0] * 40]
            for device in (0, 1)
            for role in ("control", "candidate")
            for kv_length in C.FIXTURES
            for state in ("default", "fixed")
        }
        missing = copy.deepcopy(cells)
        missing.pop((0, "control", 128, "default"))
        with self.assertRaises(C.ContractError):
            C.compute_clock_effects(missing)
        nonfinite = copy.deepcopy(cells)
        nonfinite[(0, "control", 128, "default")][0][0] = float("nan")
        with self.assertRaises(C.ContractError):
            C.compute_clock_effects(nonfinite)
        extra = copy.deepcopy(cells)
        extra[(2, "control", 128, "default")] = [[100.0] * 40, [100.0] * 40]
        with self.assertRaises(C.ContractError):
            C.compute_clock_effects(extra)

    def test_numeric_clock_gate_rejects_zero_and_negative_nonconstant_kv1300(
        self,
    ) -> None:
        cells: dict[tuple[int, str, int, str], list[list[float]]] = {}
        for device in (0, 1):
            for role in ("control", "candidate"):
                for kv_length in C.FIXTURES:
                    base = 100.0 + device * 20.0 + (5.0 if role == "candidate" else 0.0)
                    default = [
                        [
                            base + arm * 7.0 + ((index % 9) - 4) * 0.2
                            for index in range(40)
                        ]
                        for arm in range(2)
                    ]
                    fixed = [
                        [value * 0.9 for value in arm_values] for arm_values in default
                    ]
                    if kv_length == 1300 and device == 0 and role == "control":
                        fixed = copy.deepcopy(default)
                    if kv_length == 1300 and device == 1 and role == "candidate":
                        fixed = [[value + 5.0 for value in arm] for arm in default]
                    cells[(device, role, kv_length, "default")] = default
                    cells[(device, role, kv_length, "fixed")] = fixed
        rows, interactions, passed = C.compute_clock_effects(cells)
        self.assertFalse(passed)
        zero = next(
            row
            for row in rows
            if (row["device"], row["role"], row["kv_length"]) == (0, "control", 1300)
        )
        negative = next(
            row
            for row in rows
            if (row["device"], row["role"], row["kv_length"]) == (1, "candidate", 1300)
        )
        nonconstant = next(
            row
            for row in rows
            if (row["device"], row["role"], row["kv_length"]) == (0, "candidate", 128)
        )
        self.assertAlmostEqual(zero["fixed_saving_percent"], 0.0)
        self.assertLessEqual(zero["bootstrap_95_percent_ci"][0], 0.0)
        self.assertLess(negative["fixed_saving_percent"], 0.0)
        self.assertLess(negative["bootstrap_95_percent_ci"][0], 0.0)
        self.assertLess(
            nonconstant["bootstrap_95_percent_ci"][0],
            nonconstant["fixed_saving_percent"],
        )
        self.assertGreater(
            nonconstant["bootstrap_95_percent_ci"][1],
            nonconstant["fixed_saving_percent"],
        )
        self.assertEqual(len(interactions), 8)

    def test_campaign_forbids_local_absolute_timing_pooling(self) -> None:
        source = CAMPAIGN_PATH.read_text(encoding="utf-8")
        self.assertIn('"absolute_timing_pooling_with_local_forbidden": True', source)
        self.assertNotIn("151.46586", source)


if __name__ == "__main__":
    unittest.main()
