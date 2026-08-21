#!/usr/bin/env python3
"""CPU-only contract tests for the no-clock remote runtime-map diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "qwen38_q64k32_remote_runtime_map_diagnostic.py"
DRIVER = HERE / "run-20260821-qwen38-q64k32-remote-runtime-map-diagnostic.sh"
SPEC = importlib.util.spec_from_file_location("remote_runtime_map_diagnostic", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load diagnostic module")
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)


class DiagnosticContractTests(unittest.TestCase):
    @staticmethod
    def _shell_function(source: str, name: str) -> str:
        start = source.index(f"{name}() {{")
        lines = source[start:].splitlines()
        selected: list[str] = []
        for line in lines:
            selected.append(line)
            if line == "}":
                break
        return "\n".join(selected)

    @staticmethod
    def _valid_live_scan() -> dict[str, object]:
        empty = hashlib.sha256(b"").hexdigest()
        return {
            "schema": "qwen38-q64k32-remote-live-scan-v1",
            "captured_time_ns": 100,
            "boot_id": D.EXPECTED_BOOT_ID,
            "devices": [
                {
                    "device": device,
                    "uuid": D.EXPECTED_DEVICES[device]["uuid"],
                    "bdf": D.EXPECTED_DEVICES[device]["bdf"],
                    "device_state": "normal",
                }
                for device in (0, 1)
            ],
            "discovery_stdout_sha256": empty,
            "configurations": [
                {
                    "device": device,
                    "minimum_mhz": 400,
                    "maximum_mhz": 2800,
                    "stdout_sha256": empty,
                    "stderr_sha256": empty,
                }
                for device in (0, 1)
            ],
            "clock_units": {
                unit: {
                    "LoadState": "not-found",
                    "ActiveState": "inactive",
                    "SubState": "dead",
                    "FragmentPath": "",
                    "MainPID": "0",
                }
                for unit in ("xe-b70-minfreq.service", "xe-b70-minfreq.timer")
            },
            "scheduled_source_inventory_sha256": empty,
            "user_crontab": {
                "returncode": 1,
                "stdout_sha256": empty,
                "stderr_sha256": hashlib.sha256(b"no crontab for steve\n").hexdigest(),
            },
            "read_only_commands": D.expected_passive_commands(),
            "scheduled_writer_matches": [],
            "process_writer_matches": [],
            "passed": True,
        }

    @classmethod
    def _valid_authorization(cls) -> dict[str, object]:
        return {
            "boot_id": D.EXPECTED_BOOT_ID,
            "repo_head": "a" * 40,
            "stage_inventory_sha256": D.EXPECTED_STAGE_INVENTORY_SHA256,
            "campaign_sha256": D.CAMPAIGN_SHA256,
            "passive_evidence_sha256": D.PASSIVE_EVIDENCE_SHA256,
            "live_scan": cls._valid_live_scan(),
        }

    @staticmethod
    def _full_runtime_rows() -> list[dict[str, object]]:
        return [
            dict(
                row,
                mapped_device="103:04",
                mapped_inode=1000 + index,
                canonical_device="103:04",
                canonical_inode=1000 + index,
            )
            for index, row in enumerate(D.OBSERVED_RUNTIME_LIBRARIES)
        ]

    def test_import_is_cpu_safe_and_plan_is_exact(self) -> None:
        self.assertNotIn("torch", D.sys.modules)
        self.assertTrue(D.DIAGNOSTIC_AUTHORIZED)
        self.assertEqual(
            D.PLAN,
            (
                {"ordinal": 1, "device": 0, "role": "control"},
                {"ordinal": 2, "device": 0, "role": "candidate"},
                {"ordinal": 3, "device": 1, "role": "candidate"},
                {"ordinal": 4, "device": 1, "role": "control"},
            ),
        )
        self.assertEqual(D.KV_LENGTH, 128)
        self.assertEqual(D.TIMEOUT_SECONDS, 300.0)
        self.assertEqual(D.GRACE_SECONDS, 10.0)
        self.assertEqual(
            D.RESULT_ROOT,
            Path("/home/steve/qwen38-q64k32-remote-runtime-map-diagnostic-20260821-r3"),
        )

    def test_static_runtime_candidate_map_is_exact(self) -> None:
        self.assertEqual(
            set(D.STATIC_RUNTIME_CANDIDATES),
            {
                "libsycl.so.8.0.0",
                "libur_loader.so.0.12.0",
                "libur_adapter_level_zero.so.0.12.0",
                "libze_loader.so.1.28.6",
                "libze_intel_gpu.so.1.15.38646",
            },
        )
        for digest in D.STATIC_RUNTIME_CANDIDATES.values():
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertRegex(D.EXPECTED_FIXTURE_SHA256, r"^[0-9a-f]{64}$")
        self.assertRegex(D.R2_OBSERVED_ORACLE_SHA256, r"^[0-9a-f]{64}$")
        self.assertRegex(D.R2_OBSERVED_OUTPUT_SHA256, r"^[0-9a-f]{64}$")
        self.assertEqual(len(D.OBSERVED_RUNTIME_LIBRARIES), 8)
        self.assertEqual(
            [row["basename"] for row in D.OBSERVED_RUNTIME_LIBRARIES],
            sorted(row["basename"] for row in D.OBSERVED_RUNTIME_LIBRARIES),
        )
        self.assertEqual(
            D.R2_OBSERVED_ORACLE_SHA256,
            "eb71753ec76de2390e25f5bebacecf54cb63f7966311cdd6548a5ed03638364a",
        )
        self.assertEqual(
            D.R2_OBSERVED_OUTPUT_SHA256,
            "c3e022a5e724574d06e2388e33e2e29c4b1f8630f2b7eb236ffc5e349fe9c403",
        )

    def test_strict_json_rejects_duplicate_and_nonfinite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"a":1,"a":2}\n', encoding="utf-8")
            nonfinite = root / "nonfinite.json"
            nonfinite.write_text('{"a":NaN}\n', encoding="utf-8")
            with self.assertRaisesRegex(D.ContractError, "duplicate"):
                D.load_json(duplicate)
            with self.assertRaisesRegex(D.ContractError, "nonfinite"):
                D.load_json(nonfinite)

    def test_per_arm_correctness_uses_numeric_gate_not_cross_host_oracle_pin(
        self,
    ) -> None:
        qualifier = mock.Mock()
        qualifier.BASE.ATOL = 0.02
        qualifier.BASE.RTOL = 0.01
        summary = {
            "kv_length": 128,
            "fixture_seed": 380128,
            "fixture_sha256": D.EXPECTED_FIXTURE_SHA256,
            "output_sha256": D.R2_OBSERVED_OUTPUT_SHA256,
            "oracle_sha256": D.R2_OBSERVED_ORACLE_SHA256,
            "max_abs_diff": 0.00048828125,
            "atol": 0.02,
            "rtol": 0.01,
            "passed": True,
        }
        self.assertEqual(
            D.validate_correctness_summary(summary, qualifier, "fixture"), summary
        )
        alternate_oracle = dict(summary, oracle_sha256="a" * 64)
        self.assertEqual(
            D.validate_correctness_summary(
                alternate_oracle, qualifier, "alternate-host"
            ),
            alternate_oracle,
        )
        with self.assertRaisesRegex(D.ContractError, "correctness summary"):
            D.validate_correctness_summary(
                dict(summary, max_abs_diff=0.0200001), qualifier, "too-far"
            )
        with self.assertRaisesRegex(D.ContractError, "fixture"):
            D.validate_correctness_summary(
                dict(summary, fixture_sha256="0" * 64), qualifier, "wrong-fixture"
            )

    def test_runtime_snapshot_binds_exact_basename_path_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory) / "libsycl.so.8.0.0"
            library.write_bytes(b"fixture runtime\n")
            soname = library.with_name("libsycl.so.8")
            soname.symlink_to(library.name)
            stat = library.stat()
            device = f"{os.major(stat.st_dev):02x}:{os.minor(stat.st_dev):02x}"
            maps = (
                "0800-0900 rw-s 00000000 00:06 123 /dev/dri/renderD129\n"
                f"1000-2000 r-xp 00000000 {device} {stat.st_ino} {soname}\n"
            )
            portable = {
                "basename": library.name,
                "path": str(library),
                "mapped_basename": soname.name,
                "mapped_path": str(soname),
                "sha256": D.sha256_file(library),
            }
            with mock.patch.object(Path, "read_text", return_value=maps):
                packet = D._runtime_snapshot()
                # The snapshot differs from the frozen r2-observed rows, and
                # arm-level validation must still accept it: portable-row
                # drift is a comparison-level valid negative, not an arm gate.
                self.assertNotEqual(
                    D._portable_runtime_rows(packet["libraries"]),
                    list(D.OBSERVED_RUNTIME_LIBRARIES),
                )
                D.validate_runtime_snapshot(packet, "fixture")
            self.assertEqual(len(packet["libraries"]), 1)
            self.assertEqual(packet["libraries"][0]["basename"], library.name)
            self.assertEqual(packet["libraries"][0]["path"], str(library))
            self.assertEqual(packet["libraries"][0]["mapped_path"], str(soname))
            self.assertEqual(packet["libraries"][0]["mapped_inode"], stat.st_ino)
            self.assertEqual(packet["libraries"][0]["sha256"], D.sha256_file(library))
            self.assertEqual([portable], D._portable_runtime_rows(packet["libraries"]))
            packet["libraries"][0]["mapped_inode"] += 1
            with self.assertRaisesRegex(D.ContractError, "mapped library"):
                D.validate_runtime_snapshot(packet, "forged")
            deleted = maps.rstrip() + " (deleted)\n"
            with mock.patch.object(Path, "read_text", return_value=deleted):
                with self.assertRaisesRegex(D.ContractError, "deleted"):
                    D._runtime_snapshot()
            missing = (
                "1000-2000 r-xp 00000000 00:00 123 "
                f"{Path(directory) / 'libsycl-missing.so.8'}\n"
            )
            with mock.patch.object(Path, "read_text", return_value=missing):
                with self.assertRaisesRegex(D.ContractError, "noncanonical"):
                    D._runtime_snapshot()

    def test_passive_command_allowlist_rejects_clock_mutation(self) -> None:
        with self.assertRaisesRegex(D.ContractError, "outside passive allowlist"):
            D._run_passive(
                [
                    str(D.XPU_SMI),
                    "config",
                    "-d",
                    "0",
                    "-t",
                    "0",
                    "--frequencyrange",
                    "2800,2800",
                    "-j",
                ]
            )

    def test_live_scan_parses_normal_devices_ranges_and_no_writers(self) -> None:
        empty = hashlib.sha256(b"").hexdigest()
        discovery = {
            "device_list": [
                {
                    "device_id": device,
                    "uuid": D.EXPECTED_DEVICES[device]["uuid"],
                    "pci_bdf_address": D.EXPECTED_DEVICES[device]["bdf"],
                    "device_state": "normal",
                    "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
                }
                for device in (0, 1)
            ]
        }
        config = {"tile_config_data": [{"min_frequency": 400, "max_frequency": 2800}]}
        unit_with_pid = (
            b"LoadState=not-found\nActiveState=inactive\nSubState=dead\n"
            b"FragmentPath=\nMainPID=0\n"
        )
        unit_without_pid = (
            b"LoadState=not-found\nActiveState=inactive\nSubState=dead\nFragmentPath=\n"
        )

        def capture(
            arguments: list[str], ok: tuple[int, ...] = (0,)
        ) -> dict[str, object]:
            del ok
            returncode = 0
            stderr = b""
            if arguments[1:3] == ["discovery", "-j"]:
                stdout = json.dumps(discovery).encode()
            elif arguments[1:2] == ["config"]:
                stdout = json.dumps(config).encode()
            elif arguments[0] == "/usr/bin/systemctl":
                stdout = (
                    unit_without_pid
                    if arguments[2] == "xe-b70-minfreq.timer"
                    else unit_with_pid
                )
            elif arguments == ["/usr/bin/crontab", "-l"]:
                returncode = 1
                stdout = b""
                stderr = b"no crontab for steve\n"
            else:
                raise AssertionError(arguments)
            return {
                "argv": arguments,
                "returncode": returncode,
                "stdout": stdout,
                "stderr": stderr,
                "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            }

        real_sha = D.sha256_file
        real_read = Path.read_text

        def file_sha(path: Path) -> str:
            return D.XPU_SMI_SHA256 if path == D.XPU_SMI else real_sha(path)

        def read_text(path: Path, *args: object, **kwargs: object) -> str:
            if str(path) == "/proc/sys/kernel/random/boot_id":
                return D.EXPECTED_BOOT_ID + "\n"
            return real_read(path, *args, **kwargs)

        with (
            mock.patch.object(D, "sha256_file", side_effect=file_sha),
            mock.patch.object(D.Path, "read_text", read_text),
            mock.patch.object(D, "_run_passive", side_effect=capture),
            mock.patch.object(
                D,
                "_scheduled_writer_scan",
                return_value={"inventory_sha256": empty, "matches": []},
            ),
            mock.patch.object(D, "_live_writer_process_scan", return_value=[]),
        ):
            scan = D.passive_live_scan()
        D.validate_live_scan(scan)
        self.assertEqual(scan["clock_units"]["xe-b70-minfreq.timer"]["MainPID"], "0")

    def test_live_scan_rejects_range_and_writer_tampering(self) -> None:
        scan = self._valid_live_scan()
        D.validate_live_scan(scan)
        configurations = scan["configurations"]
        assert isinstance(configurations, list)
        assert isinstance(configurations[0], dict)
        configurations[0]["maximum_mhz"] = 2799
        with self.assertRaisesRegex(D.ContractError, "range"):
            D.validate_live_scan(scan)
        scan = self._valid_live_scan()
        scan["process_writer_matches"] = [7]
        with self.assertRaisesRegex(D.ContractError, "result"):
            D.validate_live_scan(scan)

    def test_scan_packet_is_exact_immutable_and_authorization_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "preflight-live-scan.json"
            with (
                mock.patch.object(D, "RESULT_ROOT", root),
                mock.patch.object(
                    D,
                    "diagnostic_preflight",
                    return_value=self._valid_authorization(),
                ),
            ):
                packet = D.scan_command(argparse.Namespace(output=str(output)))
                self.assertFalse(output.stat().st_mode & 0o222)
                self.assertEqual(D.validate_preflight_scan(output), packet)
                output.chmod(0o644)
                with self.assertRaisesRegex(D.ContractError, "writable"):
                    D.validate_preflight_scan(output)

    def test_preflight_is_clean_main_stage_and_boot_bound(self) -> None:
        campaign = mock.Mock()
        campaign.derive_stage_inventory.return_value = {
            "sha256": D.EXPECTED_STAGE_INVENTORY_SHA256
        }
        outputs = {
            ("rev-parse", "HEAD"): "a" * 40,
            ("branch", "--show-current"): "main",
            ("status", "--porcelain", "--untracked-files=normal"): "",
            ("rev-parse", "origin/main"): "a" * 40,
        }
        real_read = Path.read_text

        def read_text(path: Path, *args: object, **kwargs: object) -> str:
            if str(path) == "/proc/sys/kernel/random/boot_id":
                return D.EXPECTED_BOOT_ID + "\n"
            return real_read(path, *args, **kwargs)

        with (
            mock.patch.object(
                D.socket, "gethostname", return_value="steve-TURIND8-2L2T"
            ),
            mock.patch.object(D.Path, "read_text", read_text),
            mock.patch.object(
                D, "_git_output", side_effect=lambda *args: outputs[args]
            ),
            mock.patch.object(D, "_load_campaign", return_value=campaign),
            mock.patch.object(
                D, "passive_live_scan", return_value=self._valid_live_scan()
            ),
        ):
            result = D.diagnostic_preflight()
        self.assertEqual(result["repo_head"], "a" * 40)
        self.assertEqual(
            result["stage_inventory_sha256"], D.EXPECTED_STAGE_INVENTORY_SHA256
        )

    def test_worker_rejects_wrong_plan_before_torch_import(self) -> None:
        args = argparse.Namespace(
            ordinal=1,
            device=1,
            role="control",
            output=str(D.RESULT_ROOT / "arm-01.json"),
        )
        with mock.patch.object(D, "diagnostic_preflight", return_value={}):
            with self.assertRaisesRegex(D.ContractError, "arguments"):
                D.worker_command(args)
        self.assertNotIn("torch", sys.modules)

    def test_supervisor_rejects_nonfrozen_command_before_spawn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = argparse.Namespace(
                ordinal=1,
                terminal=str(root / "arm-01.terminal.json"),
                command=["/bin/false"],
            )
            with (
                mock.patch.object(D, "RESULT_ROOT", root),
                mock.patch.object(D, "diagnostic_preflight", return_value={}),
                mock.patch.object(D.signal, "signal"),
                mock.patch.object(D.signal, "pthread_sigmask", return_value=set()),
                mock.patch.object(D.subprocess, "Popen") as popen,
            ):
                with self.assertRaisesRegex(D.ContractError, "command differs"):
                    D.supervise_command(args)
            popen.assert_not_called()

    def test_supervisor_publishes_identity_before_passive_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            terminal = root / "arm-01.terminal.json"
            command = [
                str(D.REMOTE_PYTHON),
                "-B",
                str(SCRIPT),
                "worker",
                "--ordinal",
                "1",
                "--device",
                "0",
                "--role",
                "control",
                "--output",
                str(root / "arm-01.json"),
            ]
            args = argparse.Namespace(
                ordinal=1, terminal=str(terminal), command=command
            )
            with (
                mock.patch.object(D, "RESULT_ROOT", root),
                mock.patch.object(
                    D,
                    "diagnostic_preflight",
                    side_effect=D.ContractError("fixture preflight failure"),
                ),
                mock.patch.object(D.signal, "signal"),
                mock.patch.object(D.signal, "pthread_sigmask", return_value=set()),
                mock.patch.object(D.subprocess, "Popen") as popen,
            ):
                packet = D.supervise_command(args)
                self.assertEqual(packet["status"], "invalid")
                self.assertFalse(packet["valid"])
                self.assertIsNone(packet["authorization"])
                D.validate_cleanup_terminal(terminal, 1, os.getpid())
            popen.assert_not_called()
            receipt = D.load_json(Path(f"{terminal}.phase-supervisor-started.json"))
            self.assertEqual(receipt["phase"], "supervisor-started")
            self.assertEqual(receipt["plan"], D.PLAN[0])
            self.assertEqual(receipt["supervisor_pid"], os.getpid())

    def test_cleanup_success_is_bound_to_owned_supervisor_pid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            terminal = root / "arm-01.terminal.json"
            packet = {
                "schema": "qwen38-q64k32-remote-runtime-map-terminal-v1",
                "status": "success",
                "valid": True,
                "plan": dict(D.PLAN[0]),
                "authorization": {},
                "process": {"supervisor_pid": 321},
                "watchdog": {},
                "signals": [],
                "artifacts": {},
                "error": None,
            }
            D.write_json_atomic(terminal, packet)
            with (
                mock.patch.object(D, "RESULT_ROOT", root),
                mock.patch.object(D, "validate_terminal", return_value=packet),
            ):
                self.assertEqual(D.validate_cleanup_terminal(terminal, 1, 321), packet)
                with self.assertRaisesRegex(D.ContractError, "ownership"):
                    D.validate_cleanup_terminal(terminal, 1, 322)

    def test_cleanup_negative_rederives_receipts_and_group_absence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            terminal = root / "arm-01.terminal.json"
            supervisor_pid = 321
            plan = dict(D.PLAN[0])
            command = [
                str(D.REMOTE_PYTHON),
                "-B",
                str(SCRIPT),
                "worker",
                "--ordinal",
                "1",
                "--device",
                "0",
                "--role",
                "control",
                "--output",
                str(root / "arm-01.json"),
            ]
            command_sha = hashlib.sha256(
                ("\0".join(command) + "\0").encode()
            ).hexdigest()
            started = Path(f"{terminal}.phase-supervisor-started.json")
            preflight = Path(f"{terminal}.phase-preflight.json")
            before = Path(f"{terminal}.phase-before-spawn.json")
            D.write_json_atomic(
                started,
                {
                    "schema": "qwen38-q64k32-remote-runtime-map-phase-v1",
                    "phase": "supervisor-started",
                    "time_ns": 10,
                    "supervisor_pid": supervisor_pid,
                    "plan": plan,
                    "command_sha256": command_sha,
                },
            )
            authorization = self._valid_authorization()
            D.write_json_atomic(
                preflight,
                {
                    "schema": "qwen38-q64k32-remote-runtime-map-phase-v1",
                    "phase": "preflight-complete",
                    "time_ns": 20,
                    "supervisor_pid": supervisor_pid,
                    "plan": plan,
                    "authorization": authorization,
                },
            )
            D.write_json_atomic(
                before,
                {
                    "schema": "qwen38-q64k32-remote-runtime-map-phase-v1",
                    "phase": "before-spawn",
                    "time_ns": 30,
                    "supervisor_pid": supervisor_pid,
                    "plan": plan,
                    "command_sha256": command_sha,
                },
            )
            packet = {
                "schema": "qwen38-q64k32-remote-runtime-map-terminal-v1",
                "status": "interrupted",
                "valid": False,
                "plan": plan,
                "authorization": authorization,
                "process": {
                    "supervisor_pid": supervisor_pid,
                    "worker_pid": None,
                    "worker_pgid": None,
                    "worker_start_ticks": None,
                    "returncode": None,
                    "started_time_ns": 30,
                    "finished_time_ns": 40,
                    "command_sha256": command_sha,
                },
                "watchdog": {
                    "timeout_seconds": D.TIMEOUT_SECONDS,
                    "grace_seconds": D.GRACE_SECONDS,
                    "cleanup": {
                        "identity_safe": True,
                        "term_sent": False,
                        "kill_sent": False,
                        "group_absent": True,
                    },
                },
                "signals": [15],
                "artifacts": {
                    "output": None,
                    "log": None,
                    "supervisor_started": D._artifact(started),
                    "preflight": D._artifact(preflight),
                    "before": D._artifact(before),
                    "spawned": None,
                },
                "error": "ContractError: interrupted before spawn",
            }
            D.write_json_atomic(terminal, packet)
            with mock.patch.object(D, "RESULT_ROOT", root):
                self.assertEqual(
                    D.validate_cleanup_terminal(terminal, 1, supervisor_pid), packet
                )
                packet["watchdog"]["cleanup"]["group_absent"] = False
                D.write_json_atomic(terminal, packet)
                with self.assertRaisesRegex(D.ContractError, "group absence"):
                    D.validate_cleanup_terminal(terminal, 1, supervisor_pid)

    def test_terminal_late_signal_sidecar_is_always_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            terminal = Path(directory) / "arm-01.terminal.json"
            Path(f"{terminal}.signals-late.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(D.ContractError, "late-signal"):
                D.validate_terminal(terminal)

    def test_driver_has_no_clock_or_model_command_and_is_fresh_root_only(self) -> None:
        source = DRIVER.read_text(encoding="utf-8")
        self.assertNotIn("--frequencyrange", source)
        self.assertNotIn("xpu-smi", source)
        self.assertNotIn("vllm serve", source)
        self.assertIn("[[ ! -e $result && ! -L $result ]]", source)
        self.assertIn("for ordinal in 1 2 3 4", source)
        self.assertIn("preflight-live-scan.json", source)
        self.assertIn("validate-terminal", source)
        self.assertIn("validate-cleanup-terminal", source)
        self.assertIn("abort_if_driver_signaled", source)
        self.assertGreaterEqual(source.count("abort_if_driver_signaled"), 7)
        self.assertIn(
            "set -e\n  abort_if_driver_signaled\n  [[ $supervisor_rc -eq 0 ]]",
            source,
        )
        self.assertIn("supervisor_spawn_state=spawning", source)
        self.assertIn("counter -lt 600", source)
        self.assertNotIn("trap - EXIT INT TERM HUP", source)
        self.assertLess(
            source.index("trap cleanup_active_supervisor EXIT"),
            source.index("[[ ! -e $result && ! -L $result ]]"),
        )
        completed = subprocess.run(
            ["/usr/bin/bash", "-n", str(DRIVER)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())

    def test_driver_source_pins_rederive_exactly(self) -> None:
        source = DRIVER.read_text(encoding="utf-8")
        pins = dict(
            line.split("=", 1)
            for line in source.splitlines()
            if line.startswith(("diagnostic_sha=", "campaign_sha="))
        )
        self.assertEqual(pins["diagnostic_sha"], D.sha256_file(SCRIPT))
        self.assertEqual(pins["campaign_sha"], D.sha256_file(D.CAMPAIGN_PATH))

    def test_forged_clean_marker_still_requires_exact_management_values(self) -> None:
        base = {
            "HOME": "/home/steve",
            "USER": "steve",
            "LOGNAME": "steve",
            "SHELL": "/usr/bin/bash",
            "LANG": "C.UTF-8",
            "PATH": "/usr/bin:/bin",
            "PWD": "/home/steve",
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "QWEN38_RUNTIME_MAP_DRIVER_CLEAN": (
                "qwen38-q64k32-runtime-map-management-v1"
            ),
        }
        for name, value, cwd in (
            ("HOME", "/tmp", "/home/steve"),
            ("PATH", "/bin", "/home/steve"),
            ("PWD", "/tmp", "/tmp"),
        ):
            with self.subTest(name=name):
                environment = dict(base)
                environment[name] = value
                completed = subprocess.run(
                    ["/usr/bin/bash", str(DRIVER), "preflight"],
                    cwd=cwd,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=5,
                )
                self.assertEqual(completed.returncode, 2)
                self.assertIn(b"management environment values differ", completed.stderr)
        clean = subprocess.run(
            ["/usr/bin/bash", str(DRIVER), "preflight"],
            cwd="/home/steve",
            env=base,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=5,
        )
        self.assertEqual(clean.returncode, 2)
        self.assertIn(b"wrong host", clean.stderr)
        self.assertNotIn(b"management environment", clean.stderr)
        unexpected = dict(base, UNEXPECTED_MANAGEMENT_INPUT="1")
        rejected = subprocess.run(
            ["/usr/bin/bash", str(DRIVER), "preflight"],
            cwd="/home/steve",
            env=unexpected,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=5,
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertIn(b"unexpected management environment", rejected.stderr)

    def test_live_shell_signal_cannot_cross_an_idle_boundary(self) -> None:
        source = DRIVER.read_text(encoding="utf-8")
        handle = self._shell_function(source, "handle_driver_signal")
        abort = self._shell_function(source, "abort_if_driver_signaled")
        script = f"""#!/usr/bin/env bash
set -euo pipefail
kill_bin=/usr/bin/kill
active_supervisor_pid=
supervisor_spawn_state=idle
deferred_signal=
driver_signal_exit_code=
{handle}
{abort}
trap 'handle_driver_signal TERM 143' TERM
(/usr/bin/sleep 0.05; /usr/bin/kill -s TERM $$) &
/usr/bin/sleep 0.2
abort_if_driver_signaled
printf 'UNREACHABLE\\n'
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signal-boundary.sh"
            path.write_text(script, encoding="utf-8")
            completed = subprocess.run(
                ["/usr/bin/bash", str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=5,
            )
        self.assertEqual(completed.returncode, 143, completed.stderr.decode())
        self.assertNotIn(b"UNREACHABLE", completed.stdout)

    def test_compare_paths_and_terminal_count_are_exact(self) -> None:
        with mock.patch.object(D, "diagnostic_preflight", return_value={}):
            with self.assertRaisesRegex(D.ContractError, "paths"):
                D.compare_command(
                    argparse.Namespace(
                        output=str(D.RESULT_ROOT / "wrong.json"), terminals=[]
                    )
                )

    def test_compare_binds_fresh_processes_and_overall_scan_chronology(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            terminals = [
                root / f"arm-{ordinal:02d}.terminal.json" for ordinal in range(1, 5)
            ]
            terminal_packets = []
            arm_packets = []
            for ordinal in range(1, 5):
                authorization = self._valid_authorization()
                authorization["live_scan"]["captured_time_ns"] = ordinal * 100
                terminal_packets.append(
                    {
                        "authorization": authorization,
                        "process": {
                            "started_time_ns": ordinal * 100 + 10,
                            "finished_time_ns": ordinal * 100 + 20,
                        },
                    }
                )
                arm_packets.append(
                    {
                        "authorization": authorization,
                        "process": {"pid": 1000 + ordinal},
                        "runtime_maps_before_first_operator": {
                            "libraries": self._full_runtime_rows()
                        },
                        "runtime_maps_after_first_return_before_correctness": {
                            "libraries": self._full_runtime_rows()
                        },
                        "correctness": {
                            "oracle_sha256": D.R2_OBSERVED_ORACLE_SHA256,
                            "output_sha256": D.R2_OBSERVED_OUTPUT_SHA256,
                        },
                    }
                )
            preflight = {"authorization": self._valid_authorization()}
            preflight["authorization"]["live_scan"]["captured_time_ns"] = 1
            post = self._valid_authorization()
            post["live_scan"]["captured_time_ns"] = 1000
            with (
                mock.patch.object(D, "RESULT_ROOT", root),
                mock.patch.object(D, "diagnostic_preflight", return_value=post),
                mock.patch.object(D, "validate_preflight_scan", return_value=preflight),
                mock.patch.object(D, "validate_terminal", side_effect=terminal_packets),
                mock.patch.object(D, "validate_arm", side_effect=arm_packets),
                mock.patch.object(D, "sha256_file", return_value="f" * 64),
            ):
                result = D.compare_command(
                    argparse.Namespace(
                        output=str(root / "comparison.json"),
                        terminals=[str(path) for path in terminals],
                    )
                )
            self.assertTrue(result["passed"])
            self.assertEqual(
                result["runtime_libraries"]["expected_r2_observed_portable_rows"],
                list(D.OBSERVED_RUNTIME_LIBRARIES),
            )
            self.assertTrue(
                result["correctness_consistency"]["oracle_sha256_consistent"]
            )
            self.assertTrue(
                result["correctness_consistency"]["output_sha256_consistent"]
            )

    def test_compare_classifies_one_live_inode_mismatch_as_valid_negative(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            terminals = [
                root / f"arm-{ordinal:02d}.terminal.json" for ordinal in range(1, 5)
            ]
            terminal_packets = []
            arm_packets = []
            for ordinal in range(1, 5):
                authorization = self._valid_authorization()
                authorization["live_scan"]["captured_time_ns"] = ordinal * 100
                terminal_packets.append(
                    {
                        "authorization": authorization,
                        "process": {
                            "started_time_ns": ordinal * 100 + 10,
                            "finished_time_ns": ordinal * 100 + 20,
                        },
                    }
                )
                libraries = self._full_runtime_rows()
                if ordinal == 4:
                    libraries[0] = dict(libraries[0], mapped_inode=9999)
                arm_packets.append(
                    {
                        "authorization": authorization,
                        "process": {"pid": 2000 + ordinal},
                        "runtime_maps_before_first_operator": {
                            "libraries": self._full_runtime_rows()
                        },
                        "runtime_maps_after_first_return_before_correctness": {
                            "libraries": libraries
                        },
                        "correctness": {
                            "oracle_sha256": D.R2_OBSERVED_ORACLE_SHA256,
                            "output_sha256": D.R2_OBSERVED_OUTPUT_SHA256,
                        },
                    }
                )
            preflight = {"authorization": self._valid_authorization()}
            preflight["authorization"]["live_scan"]["captured_time_ns"] = 1
            post = self._valid_authorization()
            post["live_scan"]["captured_time_ns"] = 1000
            with (
                mock.patch.object(D, "RESULT_ROOT", root),
                mock.patch.object(D, "diagnostic_preflight", return_value=post),
                mock.patch.object(D, "validate_preflight_scan", return_value=preflight),
                mock.patch.object(D, "validate_terminal", side_effect=terminal_packets),
                mock.patch.object(D, "validate_arm", side_effect=arm_packets),
                mock.patch.object(D, "sha256_file", return_value="f" * 64),
            ):
                result = D.compare_command(
                    argparse.Namespace(
                        output=str(root / "comparison.json"),
                        terminals=[str(path) for path in terminals],
                    )
                )
            self.assertFalse(result["passed"])
            self.assertEqual(
                result["classification"], "valid-no-clock-runtime-map-instability"
            )

    def test_compare_classifies_portable_drift_from_r2_rows_as_valid_negative(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            terminals = [
                root / f"arm-{ordinal:02d}.terminal.json" for ordinal in range(1, 5)
            ]
            terminal_packets = []
            arm_packets = []

            def _drifted_rows() -> list[dict[str, object]]:
                rows = self._full_runtime_rows()
                rows[0] = dict(rows[0], sha256="d" * 64)
                return rows

            for ordinal in range(1, 5):
                authorization = self._valid_authorization()
                authorization["live_scan"]["captured_time_ns"] = ordinal * 100
                terminal_packets.append(
                    {
                        "authorization": authorization,
                        "process": {
                            "started_time_ns": ordinal * 100 + 10,
                            "finished_time_ns": ordinal * 100 + 20,
                        },
                    }
                )
                arm_packets.append(
                    {
                        "authorization": authorization,
                        "process": {"pid": 4000 + ordinal},
                        "runtime_maps_before_first_operator": {
                            "libraries": _drifted_rows()
                        },
                        "runtime_maps_after_first_return_before_correctness": {
                            "libraries": _drifted_rows()
                        },
                        "correctness": {
                            "oracle_sha256": D.R2_OBSERVED_ORACLE_SHA256,
                            "output_sha256": D.R2_OBSERVED_OUTPUT_SHA256,
                        },
                    }
                )
            preflight = {"authorization": self._valid_authorization()}
            preflight["authorization"]["live_scan"]["captured_time_ns"] = 1
            post = self._valid_authorization()
            post["live_scan"]["captured_time_ns"] = 1000
            with (
                mock.patch.object(D, "RESULT_ROOT", root),
                mock.patch.object(D, "diagnostic_preflight", return_value=post),
                mock.patch.object(D, "validate_preflight_scan", return_value=preflight),
                mock.patch.object(D, "validate_terminal", side_effect=terminal_packets),
                mock.patch.object(D, "validate_arm", side_effect=arm_packets),
                mock.patch.object(D, "sha256_file", return_value="f" * 64),
            ):
                result = D.compare_command(
                    argparse.Namespace(
                        output=str(root / "comparison.json"),
                        terminals=[str(path) for path in terminals],
                    )
                )
            self.assertFalse(result["passed"])
            self.assertEqual(
                result["classification"], "valid-no-clock-runtime-map-instability"
            )
            self.assertFalse(result["runtime_libraries"]["portable_rows_match"])
            self.assertTrue(
                result["runtime_libraries"][
                    "full_rows_same_before_after_and_across_processes"
                ]
            )
            self.assertTrue(
                result["correctness_consistency"]["oracle_sha256_consistent"]
            )
            self.assertTrue(
                result["correctness_consistency"]["output_sha256_consistent"]
            )

    def test_compare_rejects_cross_process_oracle_or_output_instability(self) -> None:
        for field in ("oracle_sha256", "output_sha256"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                terminals = [
                    root / f"arm-{ordinal:02d}.terminal.json" for ordinal in range(1, 5)
                ]
                terminal_packets = []
                arm_packets = []
                for ordinal in range(1, 5):
                    authorization = self._valid_authorization()
                    authorization["live_scan"]["captured_time_ns"] = ordinal * 100
                    terminal_packets.append(
                        {
                            "authorization": authorization,
                            "process": {
                                "started_time_ns": ordinal * 100 + 10,
                                "finished_time_ns": ordinal * 100 + 20,
                            },
                        }
                    )
                    correctness = {
                        "oracle_sha256": D.R2_OBSERVED_ORACLE_SHA256,
                        "output_sha256": D.R2_OBSERVED_OUTPUT_SHA256,
                    }
                    if ordinal == 4:
                        correctness[field] = "0" * 64
                    rows = self._full_runtime_rows()
                    arm_packets.append(
                        {
                            "authorization": authorization,
                            "process": {"pid": 3000 + ordinal},
                            "runtime_maps_before_first_operator": {"libraries": rows},
                            "runtime_maps_after_first_return_before_correctness": {
                                "libraries": [dict(row) for row in rows]
                            },
                            "correctness": correctness,
                        }
                    )
                preflight = {"authorization": self._valid_authorization()}
                preflight["authorization"]["live_scan"]["captured_time_ns"] = 1
                post = self._valid_authorization()
                post["live_scan"]["captured_time_ns"] = 1000
                with (
                    mock.patch.object(D, "RESULT_ROOT", root),
                    mock.patch.object(D, "diagnostic_preflight", return_value=post),
                    mock.patch.object(
                        D, "validate_preflight_scan", return_value=preflight
                    ),
                    mock.patch.object(
                        D, "validate_terminal", side_effect=terminal_packets
                    ),
                    mock.patch.object(D, "validate_arm", side_effect=arm_packets),
                    mock.patch.object(D, "sha256_file", return_value="f" * 64),
                ):
                    result = D.compare_command(
                        argparse.Namespace(
                            output=str(root / "comparison.json"),
                            terminals=[str(path) for path in terminals],
                        )
                    )
                self.assertFalse(result["passed"])
                self.assertEqual(
                    result["classification"],
                    "valid-no-clock-correctness-instability",
                )
                self.assertFalse(
                    result["correctness_consistency"][f"{field}_consistent"]
                )


if __name__ == "__main__":
    unittest.main()
