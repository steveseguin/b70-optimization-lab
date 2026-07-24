#!/usr/bin/env python3
"""CPU-only tests for the Laguna M8 gather-sharded operational preflight."""

from __future__ import annotations

import ast
import hashlib
import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import preflight_laguna_m8_gather_sharded_operational as preflight


class FakeProcess:
    def __init__(
        self,
        pid: int,
        stdout: bytes,
        stderr: bytes = b"",
        returncode: int = 0,
    ) -> None:
        self.pid = pid
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self.timeout: float | None = None
        self.killed = False

    def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
        self.timeout = timeout
        return self._stdout, self._stderr

    def poll(self) -> int | None:
        return self.returncode if self.returncode != 0 or self.killed else None

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        self.timeout = timeout
        return self.returncode


class TimeoutProcess(FakeProcess):
    def __init__(self, pid: int) -> None:
        super().__init__(pid, b'{"partial":')
        self.calls = 0

    def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
        self.calls += 1
        if self.calls == 1:
            raise preflight.subprocess.TimeoutExpired("xpu-smi", timeout)
        return super().communicate(timeout)


class CommunicateErrorProcess(FakeProcess):
    def __init__(self, pid: int) -> None:
        super().__init__(pid, b"captured after cleanup")
        self.calls = 0

    def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
        self.calls += 1
        if self.calls == 1:
            raise OSError("injected communication failure")
        return super().communicate(timeout)


class OperationalPreflightCpuTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.executable = self.root / "xpu-smi"
        self.executable.write_text("#!/bin/sh\nexit 0\n")
        self.executable.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        self.resolved = self.executable.resolve(strict=True)
        self.metadata = self.resolved.stat()
        self.executable_sha256 = preflight.sha256_file(self.resolved)
        self.child_pid = 4242
        self.identity = preflight.ChildIdentity(
            process_id=self.child_pid,
            proc_dir_fd_acquired=True,
            pidfd_acquired=True,
            proc_exe_resolved=str(self.resolved),
            executable_device=self.metadata.st_dev,
            executable_inode=self.metadata.st_ino,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def payload(self, rows: list[dict[str, object]]) -> dict[str, object]:
        return {"device_util_by_proc_list": rows}

    def self_row(
        self,
        device_id: int,
        *,
        pid: int | None = None,
        name: str | None = None,
    ) -> dict[str, object]:
        return {
            "device_id": device_id,
            "mem_size": 2780,
            "process_id": self.child_pid if pid is None else pid,
            "process_name": self.resolved.name if name is None else name,
            "shared_mem_size": 0,
        }

    def all_self_rows(self) -> list[dict[str, object]]:
        return [self.self_row(device_id) for device_id in range(4)]

    def validate(self, payload: object) -> dict[str, object]:
        return preflight.validate_idle_payload(
            payload,
            child_identity=self.identity,
            launched_executable=self.resolved,
        )

    def capture_with_process(self, process: FakeProcess) -> dict[str, object]:
        with (
            mock.patch.object(preflight.subprocess, "Popen", return_value=process),
            mock.patch.object(
                preflight,
                "attest_live_child",
                return_value=(self.identity, (91,)),
            ),
            mock.patch.object(preflight.os, "close"),
        ):
            return preflight.capture_idle_snapshot(
                self.executable,
                expected_sha256=self.executable_sha256,
                timeout_seconds=3,
            )

    def test_retained_installed_schema_fixture_passes(self) -> None:
        fixture_path = (
            Path(__file__).resolve().parents[3]
            / "data"
            / "laguna-s-2.1-xpu-smi-ps-installed-schema-sanitized-20260724.json"
        )
        raw = fixture_path.read_bytes()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "f1ed4c4f41999a2f79ce77f8b7fb251d15d5f2d87ac6a62b83a1ddfddfaa40ef",
        )
        fixture = preflight.strict_json_loads(raw.decode("utf-8"))
        self.assertEqual(
            set(fixture),
            {"schema_version", "capture", "payload"},
        )
        self.assertEqual(fixture["schema_version"], 1)
        self.assertEqual(
            fixture["capture"],
            {
                "date": "2026-07-24",
                "host_gpu_count": 4,
                "observer": "/usr/bin/xpu-smi",
                "observer_sha256": preflight.EXPECTED_XPU_SMI_SHA256,
                "argv": ["/usr/bin/xpu-smi", "ps", "-j"],
                "classification": "read_only_pre_packet_installed_schema_probe",
                "process_id_sanitized": True,
            },
        )
        payload = fixture["payload"]
        result = preflight.validate_idle_payload(
            payload,
            child_identity=preflight.ChildIdentity(
                process_id=4242,
                proc_dir_fd_acquired=True,
                pidfd_acquired=True,
                proc_exe_resolved="/usr/bin/xpu-smi",
                executable_device=0,
                executable_inode=0,
            ),
            launched_executable=Path("/usr/bin/xpu-smi"),
        )
        self.assertEqual(result["accepted_mode"], "self_observer_rows")
        self.assertEqual(result["device_ids"], [0, 1, 2, 3])
        self.assertEqual(result["row_count"], 4)
        self.assertTrue(
            all(
                row["process_name_mode"] == "basename_non_authoritative"
                for row in result["sanitized_payload"]["device_util_by_proc_list"]
            )
        )

    def test_empty_installed_schema_passes(self) -> None:
        result = self.validate(self.payload([]))
        self.assertEqual(
            result,
            {
                "accepted_mode": "empty",
                "row_count": 0,
                "device_ids": [],
                "sanitized_payload": {"device_util_by_proc_list": []},
            },
        )

    def test_exact_self_rows_and_absolute_normalization_pass(self) -> None:
        rows = self.all_self_rows()
        rows[0]["process_name"] = str(self.resolved)
        result = self.validate(self.payload(rows))
        sanitized = result["sanitized_payload"]["device_util_by_proc_list"]
        self.assertEqual(sanitized[0]["process_name_mode"], "absolute_normalized")
        self.assertEqual(
            [row["process_id"] for row in sanitized],
            ["<observer-child-pid>"] * 4,
        )

    def test_row_schema_pid_name_type_and_device_mutations_fail(self) -> None:
        mutations: list[list[dict[str, object]]] = []

        missing = self.all_self_rows()
        del missing[0]["mem_size"]
        mutations.append(missing)
        extra = self.all_self_rows()
        extra[0]["extra"] = 1
        mutations.append(extra)
        foreign_pid = self.all_self_rows()
        foreign_pid[1]["process_id"] = self.child_pid + 1
        mutations.append(foreign_pid)
        bool_pid = self.all_self_rows()
        bool_pid[1]["process_id"] = True
        mutations.append(bool_pid)
        foreign_name = self.all_self_rows()
        foreign_name[2]["process_name"] = "foreign"
        mutations.append(foreign_name)
        relative_name = self.all_self_rows()
        relative_name[2]["process_name"] = "bin/xpu-smi"
        mutations.append(relative_name)
        duplicate_device = self.all_self_rows()
        duplicate_device[3]["device_id"] = 2
        mutations.append(duplicate_device)
        bool_device = self.all_self_rows()
        bool_device[0]["device_id"] = True
        mutations.append(bool_device)
        bad_memory = self.all_self_rows()
        bad_memory[0]["mem_size"] = -1
        mutations.append(bad_memory)
        bool_memory = self.all_self_rows()
        bool_memory[0]["shared_mem_size"] = False
        mutations.append(bool_memory)
        mutations.append(self.all_self_rows()[:3])
        mutations.append([*self.all_self_rows(), self.self_row(0)])

        for rows in mutations:
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                self.validate(self.payload(rows))

    def test_payload_and_attestation_schema_mutations_fail(self) -> None:
        values: tuple[object, ...] = (
            {"process_list": []},
            {"device_util_by_proc_list": [], "extra": []},
            {"device_util_by_proc_list": {}},
            [],
        )
        for value in values:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.validate(value)

        unattested = preflight.ChildIdentity(
            process_id=self.child_pid,
            proc_dir_fd_acquired=False,
            pidfd_acquired=True,
            proc_exe_resolved=str(self.resolved),
            executable_device=self.metadata.st_dev,
            executable_inode=self.metadata.st_ino,
        )
        with self.assertRaises(RuntimeError):
            preflight.validate_idle_payload(
                self.payload([]),
                child_identity=unattested,
                launched_executable=self.resolved,
            )

    def test_strict_json_rejects_duplicates_nonfinite_and_invalid_json(self) -> None:
        invalid = (
            '{"device_util_by_proc_list":[],"device_util_by_proc_list":[]}',
            '{"device_util_by_proc_list":NaN}',
            '{"device_util_by_proc_list":',
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                preflight.strict_json_loads(value)

    def test_executable_hash_is_bound(self) -> None:
        resolved, metadata, digest = preflight.resolve_executable(
            self.executable,
            expected_sha256=self.executable_sha256,
        )
        self.assertEqual(resolved, self.resolved)
        self.assertEqual(metadata.st_ino, self.metadata.st_ino)
        self.assertEqual(digest, self.executable_sha256)
        with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
            preflight.resolve_executable(
                self.executable,
                expected_sha256="0" * 64,
            )

    def test_live_proc_identity_attestation_success_and_failures(self) -> None:
        with (
            mock.patch.object(preflight.os, "open", return_value=91),
            mock.patch.object(
                preflight.os,
                "pidfd_open",
                return_value=92,
                create=True,
            ),
            mock.patch.object(
                preflight.os,
                "readlink",
                return_value=str(self.resolved),
            ),
            mock.patch.object(preflight.os, "stat", return_value=self.metadata),
            mock.patch.object(preflight.os, "close") as close,
        ):
            identity, identity_fds = preflight.attest_live_child(
                child_pid=self.child_pid,
                launched_executable=self.resolved,
                launched_metadata=self.metadata,
            )
        self.assertEqual(identity, self.identity)
        self.assertEqual(identity_fds, (91, 92))
        close.assert_not_called()

        foreign = self.root / "foreign"
        foreign.write_text("#!/bin/sh\nexit 0\n")
        foreign.chmod(stat.S_IRUSR | stat.S_IXUSR)
        with (
            mock.patch.object(preflight.os, "open", return_value=91),
            mock.patch.object(
                preflight.os,
                "pidfd_open",
                return_value=92,
                create=True,
            ),
            mock.patch.object(preflight.os, "readlink", return_value=str(foreign)),
            mock.patch.object(preflight.os, "stat", return_value=self.metadata),
            mock.patch.object(preflight.os, "close") as close,
            self.assertRaisesRegex(RuntimeError, "path mismatch"),
        ):
            preflight.attest_live_child(
                child_pid=self.child_pid,
                launched_executable=self.resolved,
                launched_metadata=self.metadata,
            )
        self.assertEqual(close.call_args_list, [mock.call(92), mock.call(91)])

        with (
            mock.patch.object(preflight.os, "open", return_value=91),
            mock.patch.object(
                preflight.os,
                "pidfd_open",
                side_effect=KeyboardInterrupt,
                create=True,
            ),
            mock.patch.object(preflight.os, "close") as close,
            self.assertRaises(KeyboardInterrupt),
        ):
            preflight.attest_live_child(
                child_pid=self.child_pid,
                launched_executable=self.resolved,
                launched_metadata=self.metadata,
            )
        close.assert_called_once_with(91)

        with (
            mock.patch.object(preflight.os, "open", return_value=91),
            mock.patch.object(
                preflight.os,
                "pidfd_open",
                return_value=92,
                create=True,
            ),
            mock.patch.object(preflight.os, "readlink", side_effect=KeyboardInterrupt),
            mock.patch.object(preflight.os, "close") as close,
            self.assertRaises(KeyboardInterrupt),
        ):
            preflight.attest_live_child(
                child_pid=self.child_pid,
                launched_executable=self.resolved,
                launched_metadata=self.metadata,
            )
        self.assertEqual(close.call_args_list, [mock.call(92), mock.call(91)])

        with (
            mock.patch.object(preflight.os, "open", return_value=91),
            mock.patch.object(
                preflight.os,
                "pidfd_open",
                return_value=92,
                create=True,
            ),
            mock.patch.object(preflight.os, "readlink", side_effect=FileNotFoundError),
            mock.patch.object(preflight.os, "close") as close,
            self.assertRaises(FileNotFoundError),
        ):
            preflight.attest_live_child(
                child_pid=self.child_pid,
                launched_executable=self.resolved,
                launched_metadata=self.metadata,
            )
        self.assertEqual(close.call_args_list, [mock.call(92), mock.call(91)])

    def test_capture_retains_pid_exact_argv_env_and_raw_bytes(self) -> None:
        stdout = json.dumps(self.payload(self.all_self_rows())).encode()
        process = FakeProcess(self.child_pid, stdout, b"observer warning")
        with (
            mock.patch.object(preflight.subprocess, "Popen", return_value=process) as popen,
            mock.patch.object(
                preflight,
                "attest_live_child",
                return_value=(self.identity, (91, 92)),
            ) as attest,
            mock.patch.object(preflight.os, "close") as close,
        ):
            result = preflight.capture_idle_snapshot(
                self.executable,
                expected_sha256=self.executable_sha256,
                timeout_seconds=3,
            )
        popen.assert_called_once_with(
            [str(self.resolved), "ps", "-j"],
            stdin=preflight.subprocess.DEVNULL,
            stdout=preflight.subprocess.PIPE,
            stderr=preflight.subprocess.PIPE,
            env=dict(preflight.OBSERVER_ENVIRONMENT),
            close_fds=True,
            cwd="/",
        )
        attest.assert_called_once()
        self.assertEqual(close.call_args_list, [mock.call(92), mock.call(91)])
        self.assertEqual(process.timeout, 3.0)
        self.assertEqual(result["child_identity"], preflight.asdict(self.identity))
        self.assertEqual(
            result["raw_capture"]["stdout_sha256"],
            hashlib.sha256(stdout).hexdigest(),
        )
        self.assertEqual(result["status"], "passed")

    def test_capture_launch_timeout_nonzero_and_decode_parse_fail_closed(self) -> None:
        with mock.patch.object(preflight.subprocess, "Popen", side_effect=OSError):
            with self.assertRaisesRegex(
                preflight.OperationalPreflightError,
                "launch failed",
            ) as caught:
                preflight.capture_idle_snapshot(
                    self.executable,
                    expected_sha256=self.executable_sha256,
                )
        self.assertEqual(caught.exception.stage, "launch")

        cases = (
            (TimeoutProcess(self.child_pid), "communicate"),
            (FakeProcess(self.child_pid, b"{}", returncode=7), "exit"),
            (FakeProcess(self.child_pid, b"\xff"), "decode"),
            (FakeProcess(self.child_pid, b"{"), "parse"),
            (
                FakeProcess(
                    self.child_pid,
                    b'{"device_util_by_proc_list":[],"device_util_by_proc_list":[]}',
                ),
                "parse",
            ),
        )
        for process, expected_stage in cases:
            with self.subTest(stage=expected_stage), self.assertRaises(
                preflight.OperationalPreflightError
            ) as caught:
                self.capture_with_process(process)
            self.assertEqual(caught.exception.stage, expected_stage)
        self.assertTrue(cases[0][0].killed)

    def test_communication_exception_kills_reaps_and_retains_capture(self) -> None:
        process = CommunicateErrorProcess(self.child_pid)
        with self.assertRaises(
            preflight.OperationalPreflightError
        ) as caught:
            self.capture_with_process(process)
        self.assertEqual(caught.exception.stage, "communicate_exception")
        self.assertEqual(caught.exception.stdout, b"captured after cleanup")
        self.assertTrue(process.killed)
        self.assertEqual(process.calls, 2)

    def test_child_attestation_failure_kills_and_reaps(self) -> None:
        process = FakeProcess(self.child_pid, b"partial")
        with (
            mock.patch.object(preflight.subprocess, "Popen", return_value=process),
            mock.patch.object(
                preflight,
                "attest_live_child",
                side_effect=RuntimeError("mismatch"),
            ),
            self.assertRaises(preflight.OperationalPreflightError) as caught,
        ):
            preflight.capture_idle_snapshot(
                self.executable,
                expected_sha256=self.executable_sha256,
            )
        self.assertEqual(caught.exception.stage, "child_identity")
        self.assertTrue(process.killed)

        interrupted = FakeProcess(self.child_pid, b"partial after interrupt")
        with (
            mock.patch.object(
                preflight.subprocess,
                "Popen",
                return_value=interrupted,
            ),
            mock.patch.object(
                preflight,
                "attest_live_child",
                side_effect=KeyboardInterrupt,
            ),
            self.assertRaises(preflight.OperationalPreflightError) as caught,
        ):
            preflight.capture_idle_snapshot(
                self.executable,
                expected_sha256=self.executable_sha256,
            )
        self.assertEqual(caught.exception.stage, "child_identity")
        self.assertTrue(interrupted.killed)
        self.assertEqual(caught.exception.stdout, b"partial after interrupt")

    def test_failure_report_and_exclusive_durable_writer(self) -> None:
        error = preflight.OperationalPreflightError(
            "bad observer",
            stage="validate",
            stdout=b"raw",
            context={"bound": True},
        )
        with mock.patch.object(preflight, "capture_idle_snapshot", side_effect=error):
            report, status = preflight.execute_preflight()
        self.assertEqual(status, 1)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["failure"]["stage"], "validate")
        self.assertEqual(
            report["raw_capture"]["stdout_sha256"],
            hashlib.sha256(b"raw").hexdigest(),
        )

        output = self.root / "report.json"
        preflight.write_report_exclusive(output, report)
        self.assertEqual(json.loads(output.read_text()), report)
        with self.assertRaises(FileExistsError):
            preflight.write_report_exclusive(output, report)

    def test_output_reservation_requires_fresh_internal_run_directory(self) -> None:
        output_root = self.root / "runs"
        output_root.mkdir()
        good = output_root / "fresh-run" / "report.json"
        storage = {
            "mount_point": "/",
            "filesystem": "ext4",
            "source": "/dev/nvme0n1p2",
            "major_minor": "259:2",
            "sysfs_device": "/sys/devices/nvme/nvme0n1/nvme0n1p2",
        }
        with (
            mock.patch.object(preflight, "DEFAULT_OUTPUT_ROOT", output_root),
            mock.patch.object(
                preflight,
                "attest_internal_nvme",
                return_value=storage,
            ),
        ):
            reserved, observed_storage = preflight.reserve_output_directory(good)
            self.assertEqual(reserved, good)
            self.assertEqual(observed_storage, storage)
            with self.assertRaises(FileExistsError):
                preflight.reserve_output_directory(
                    output_root / "fresh-run" / "other.json"
                )
            with self.assertRaises(RuntimeError):
                preflight.reserve_output_directory(
                    output_root / "nested" / "too-deep" / "report.json"
                )
            with self.assertRaises(RuntimeError):
                preflight.reserve_output_directory(self.root / "external.json")

    def test_internal_nvme_mount_attestation_and_mutations(self) -> None:
        actual = preflight.attest_internal_nvme(preflight.DEFAULT_OUTPUT_ROOT)
        self.assertEqual(actual["filesystem"], "ext4")
        self.assertEqual(actual["source"], "/dev/nvme0n1p2")
        self.assertEqual(actual["major_minor"], "259:2")
        self.assertIn("nvme", actual["sysfs_device"])

        mountinfo = self.root / "mountinfo"
        sysfs = self.root / "sys-dev-block"
        sysfs.mkdir()
        device = self.root / "devices" / "nvme" / "nvme0" / "nvme0n1p2"
        device.mkdir(parents=True)
        (sysfs / "259:2").symlink_to(device)
        line = "1 0 259:2 / / rw - ext4 /dev/nvme0n1p2 rw\n"
        mountinfo.write_text(line)
        result = preflight.attest_internal_nvme(
            self.root,
            mountinfo_path=mountinfo,
            sysfs_root=sysfs,
        )
        self.assertEqual(result["source"], "/dev/nvme0n1p2")

        mutations = (
            "1 0 259:2 / / rw - xfs /dev/nvme0n1p2 rw\n",
            "1 0 259:2 / / rw - ext4 /dev/sda2 rw\n",
            "1 0 8:2 / / rw - ext4 /dev/nvme0n1p2 rw\n",
        )
        for value in mutations:
            mountinfo.write_text(value)
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                preflight.attest_internal_nvme(
                    self.root,
                    mountinfo_path=mountinfo,
                    sysfs_root=sysfs,
                )

    def test_invalid_timeout_rejected_before_launch(self) -> None:
        with mock.patch.object(preflight.subprocess, "Popen") as popen:
            for value in (0, -1, float("inf"), True):
                with self.subTest(value=value), self.assertRaises(RuntimeError):
                    preflight.capture_idle_snapshot(
                        self.executable,
                        expected_sha256=self.executable_sha256,
                        timeout_seconds=value,
                    )
        self.assertFalse(popen.called)

    def test_source_has_no_runtime_candidate_or_observer_override(self) -> None:
        source = Path(preflight.__file__).read_text()
        tree = ast.parse(source)
        imports: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        forbidden_prefixes = ("torch", "vllm", "vllm_xpu_kernels")
        self.assertFalse(
            any(
                item == prefix or item.startswith(prefix + ".")
                for item in imports
                for prefix in forbidden_prefixes
            )
        )
        self.assertNotIn('"--xpu-smi"', source)
        self.assertNotIn("import torch", source)
        self.assertNotIn("import vllm", source)


if __name__ == "__main__":
    unittest.main()
