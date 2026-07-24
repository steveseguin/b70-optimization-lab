#!/usr/bin/env python3
"""Fail-closed, read-only operational preflight for sharded Laguna M8 gather.

This program deliberately has no candidate, vLLM, Torch, or native-extension
dependency.  It invokes only the fixed installed ``/usr/bin/xpu-smi ps -j``
observer.  A basename in the observer output is never used as executable
identity: the retained child PID is bound independently to the installed
binary through a retained proc-directory descriptor and ``/proc/<pid>/exe``.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, NoReturn


DEFAULT_XPU_SMI = Path("/usr/bin/xpu-smi")
EXPECTED_XPU_SMI_SHA256 = (
    "2b5b128edf28b38da8637413fe8bfe3a4a40e8113210ba9ddaed945bd56d826e"
)
PS_ARGUMENTS = ("ps", "-j")
EXPECTED_DEVICE_IDS = (0, 1, 2, 3)
EXPECTED_ROW_KEYS = frozenset(
    {"device_id", "mem_size", "process_id", "process_name", "shared_mem_size"}
)
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_OUTPUT_ROOT = Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs"
)
EXPECTED_OUTPUT_SOURCE = "/dev/nvme0n1p2"
EXPECTED_OUTPUT_FSTYPE = "ext4"
EXPECTED_OUTPUT_MAJOR_MINOR = "259:2"
OBSERVER_ENVIRONMENT = {
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
}
FORMAT = "laguna-m8-gather-sharded-operational-preflight-v2"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encode_capture(stdout: bytes, stderr: bytes) -> dict[str, Any]:
    return {
        "stdout_bytes": len(stdout),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stdout_base64": base64.b64encode(stdout).decode("ascii"),
        "stderr_bytes": len(stderr),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "stderr_base64": base64.b64encode(stderr).decode("ascii"),
    }


class OperationalPreflightError(RuntimeError):
    """Expected fail-closed preflight error with retained raw observer bytes."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        stdout: bytes = b"",
        stderr: bytes = b"",
        context: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.stdout = stdout
        self.stderr = stderr
        self.context = dict(context or {})


def fail(
    message: str,
    *,
    stage: str,
    stdout: bytes = b"",
    stderr: bytes = b"",
    context: Mapping[str, Any] | None = None,
) -> NoReturn:
    raise OperationalPreflightError(
        message,
        stage=stage,
        stdout=stdout,
        stderr=stderr,
        context=context,
    )


@dataclass(frozen=True)
class ChildIdentity:
    process_id: int
    proc_dir_fd_acquired: bool
    pidfd_acquired: bool
    proc_exe_resolved: str
    executable_device: int
    executable_inode: int


def resolve_executable(
    configured_path: Path,
    *,
    expected_sha256: str,
) -> tuple[Path, os.stat_result, str]:
    """Resolve and cryptographically bind the exact program to be launched."""
    require(configured_path.is_absolute(), "xpu-smi path must be absolute")
    try:
        resolved = configured_path.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as error:
        raise RuntimeError("xpu-smi executable is unavailable") from error
    require(stat.S_ISREG(metadata.st_mode), "xpu-smi path is not a regular file")
    require(os.access(resolved, os.X_OK), "xpu-smi path is not executable")
    actual_sha256 = sha256_file(resolved)
    require(actual_sha256 == expected_sha256, "xpu-smi binary SHA-256 mismatch")
    return resolved, metadata, actual_sha256


def attest_live_child(
    *,
    child_pid: int,
    launched_executable: Path,
    launched_metadata: os.stat_result,
) -> tuple[ChildIdentity, tuple[int, ...]]:
    """Bind the retained PID to the launched binary while that child is live.

    The ``Popen`` child is not reaped until after this check, so its PID cannot
    be recycled.  A retained descriptor for that child's procfs directory
    anchors the subsequent ``exe`` lookup.  A pidfd is retained too when this
    Python build exposes ``os.pidfd_open``.
    """
    require(type(child_pid) is int and child_pid > 0, "invalid retained child PID")
    proc_flags = (
        getattr(os, "O_PATH", os.O_RDONLY) | os.O_DIRECTORY | os.O_CLOEXEC
    )
    try:
        proc_dir_fd = os.open(f"/proc/{child_pid}", proc_flags)
    except OSError as error:
        raise RuntimeError("could not acquire observer proc directory") from error

    pidfd_open = getattr(os, "pidfd_open", None)
    pidfd: int | None = None
    try:
        if callable(pidfd_open):
            pidfd = pidfd_open(child_pid, 0)

        proc_target = os.readlink("exe", dir_fd=proc_dir_fd)
        require(not proc_target.endswith(" (deleted)"), "observer executable is deleted")
        proc_resolved = Path(proc_target).resolve(strict=True)
        proc_metadata = os.stat("exe", dir_fd=proc_dir_fd)
        require(
            proc_resolved == launched_executable,
            "observer /proc executable path mismatch",
        )
        require(
            (proc_metadata.st_dev, proc_metadata.st_ino)
            == (launched_metadata.st_dev, launched_metadata.st_ino),
            "observer /proc executable identity mismatch",
        )
    except BaseException:
        if pidfd is not None:
            os.close(pidfd)
        os.close(proc_dir_fd)
        raise

    return (
        ChildIdentity(
            process_id=child_pid,
            proc_dir_fd_acquired=True,
            pidfd_acquired=pidfd is not None,
            proc_exe_resolved=str(proc_resolved),
            executable_device=proc_metadata.st_dev,
            executable_inode=proc_metadata.st_ino,
        ),
        (proc_dir_fd,) if pidfd is None else (proc_dir_fd, pidfd),
    )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_loads(text: str) -> Any:
    def reject_constant(value: str) -> NoReturn:
        raise ValueError(f"non-finite JSON constant: {value}")

    return json.loads(
        text,
        object_pairs_hook=_strict_object,
        parse_constant=reject_constant,
    )


def _reported_name_mode(value: object, launched_executable: Path) -> str:
    require(isinstance(value, str) and value != "", "self row process_name missing")
    reported = Path(value)
    if reported.is_absolute():
        try:
            resolved = reported.resolve(strict=True)
        except OSError as error:
            raise RuntimeError("absolute self row process_name does not resolve") from error
        require(resolved == launched_executable, "foreign XPU executable observed")
        return "absolute_normalized"
    require(reported.name == value, "relative process_name path is forbidden")
    require(value == launched_executable.name, "foreign XPU process name observed")
    return "basename_non_authoritative"


def validate_idle_payload(
    payload: object,
    *,
    child_identity: ChildIdentity,
    launched_executable: Path,
) -> dict[str, Any]:
    """Fail closed unless every installed-schema row is the exact observer child."""
    require(
        child_identity.proc_dir_fd_acquired,
        "observer child is not proc-directory-attested",
    )
    require(
        child_identity.proc_exe_resolved == str(launched_executable),
        "observer executable attestation mismatch",
    )
    require(
        isinstance(payload, dict) and set(payload) == {"device_util_by_proc_list"},
        "xpu-smi ps JSON schema drift",
    )
    rows = payload["device_util_by_proc_list"]
    require(isinstance(rows, list), "xpu-smi process list is not a list")

    if not rows:
        return {
            "accepted_mode": "empty",
            "row_count": 0,
            "device_ids": [],
            "sanitized_payload": {"device_util_by_proc_list": []},
        }

    require(
        len(rows) == len(EXPECTED_DEVICE_IDS),
        "self-observer row cardinality drift",
    )
    accepted_rows: list[dict[str, Any]] = []
    observed_device_ids: list[int] = []
    for row in rows:
        require(isinstance(row, dict), "xpu-smi process row is malformed")
        require(set(row) == EXPECTED_ROW_KEYS, "xpu-smi process row schema drift")

        device_id = row["device_id"]
        process_id = row["process_id"]
        mem_size = row["mem_size"]
        shared_mem_size = row["shared_mem_size"]
        require(
            type(device_id) is int and device_id in EXPECTED_DEVICE_IDS,
            "process row device ID malformed",
        )
        require(
            type(process_id) is int and process_id > 0,
            "process row PID malformed",
        )
        require(
            process_id == child_identity.process_id,
            "foreign XPU process observed",
        )
        require(
            type(mem_size) is int and mem_size >= 0,
            "process row memory size malformed",
        )
        require(
            type(shared_mem_size) is int and shared_mem_size >= 0,
            "process row shared-memory size malformed",
        )
        name_mode = _reported_name_mode(row["process_name"], launched_executable)
        observed_device_ids.append(device_id)
        accepted_rows.append(
            {
                "device_id": device_id,
                "mem_size": mem_size,
                "process_id": "<observer-child-pid>",
                "process_name": row["process_name"],
                "process_name_mode": name_mode,
                "shared_mem_size": shared_mem_size,
            }
        )

    require(
        tuple(sorted(observed_device_ids)) == EXPECTED_DEVICE_IDS,
        "self-observer device coverage drift",
    )
    accepted_rows.sort(key=lambda row: int(row["device_id"]))
    return {
        "accepted_mode": "self_observer_rows",
        "row_count": len(rows),
        "device_ids": list(EXPECTED_DEVICE_IDS),
        "sanitized_payload": {"device_util_by_proc_list": accepted_rows},
    }


def _kill_and_reap(process: subprocess.Popen[bytes]) -> tuple[bytes, bytes]:
    try:
        if process.poll() is None:
            process.kill()
    except ProcessLookupError:
        pass
    try:
        return process.communicate(timeout=5.0)
    except BaseException as capture_error:
        try:
            process.wait(timeout=5.0)
        except BaseException as wait_error:
            raise RuntimeError("observer cleanup could not reap child") from wait_error
        raise RuntimeError("observer was reaped but raw capture was unavailable") from capture_error


def capture_idle_snapshot(
    configured_path: Path = DEFAULT_XPU_SMI,
    *,
    expected_sha256: str = EXPECTED_XPU_SMI_SHA256,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    environment: Mapping[str, str] = OBSERVER_ENVIRONMENT,
) -> dict[str, Any]:
    """Launch one bounded observer and return a self-contained capture."""
    require(
        isinstance(timeout_seconds, (int, float))
        and not isinstance(timeout_seconds, bool)
        and math.isfinite(float(timeout_seconds))
        and timeout_seconds > 0,
        "timeout must be a positive finite number",
    )
    executable, executable_metadata, actual_sha256 = resolve_executable(
        configured_path,
        expected_sha256=expected_sha256,
    )
    argv = [str(executable), *PS_ARGUMENTS]
    identity_context = {
        "configured_path": str(configured_path),
        "resolved_path": str(executable),
        "sha256": actual_sha256,
        "device": executable_metadata.st_dev,
        "inode": executable_metadata.st_ino,
    }
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(environment),
            close_fds=True,
            cwd="/",
        )
    except OSError:
        fail(
            "xpu-smi launch failed",
            stage="launch",
            context=identity_context,
        )

    identity_fds: tuple[int, ...] = ()
    try:
        try:
            child_identity, identity_fds = attest_live_child(
                child_pid=process.pid,
                launched_executable=executable,
                launched_metadata=executable_metadata,
            )
        except BaseException as error:
            stdout, stderr = _kill_and_reap(process)
            fail(
                f"observer child identity attestation failed: {error}",
                stage="child_identity",
                stdout=stdout,
                stderr=stderr,
                context=identity_context,
            )

        try:
            stdout, stderr = process.communicate(timeout=float(timeout_seconds))
        except subprocess.TimeoutExpired as error:
            try:
                stdout, stderr = _kill_and_reap(process)
            except RuntimeError as cleanup_error:
                fail(
                    f"xpu-smi timeout cleanup failed: {cleanup_error}",
                    stage="cleanup",
                    context={
                        **identity_context,
                        "child_identity": asdict(child_identity),
                        "original_exception": type(error).__name__,
                    },
                )
            fail(
                "xpu-smi ps timed out",
                stage="communicate",
                stdout=stdout,
                stderr=stderr,
                context={
                    **identity_context,
                    "child_identity": asdict(child_identity),
                },
            )
        except BaseException as error:
            try:
                stdout, stderr = _kill_and_reap(process)
            except RuntimeError as cleanup_error:
                fail(
                    f"xpu-smi communication cleanup failed: {cleanup_error}",
                    stage="cleanup",
                    context={
                        **identity_context,
                        "child_identity": asdict(child_identity),
                        "original_exception": type(error).__name__,
                    },
                )
            fail(
                f"xpu-smi communication failed: {type(error).__name__}",
                stage="communicate_exception",
                stdout=stdout,
                stderr=stderr,
                context={
                    **identity_context,
                    "child_identity": asdict(child_identity),
                    "original_exception": type(error).__name__,
                },
            )
    finally:
        for descriptor in reversed(identity_fds):
            os.close(descriptor)

    capture = encode_capture(stdout, stderr)
    full_context = {
        **identity_context,
        "child_identity": asdict(child_identity),
    }
    if process.returncode != 0:
        fail(
            f"xpu-smi ps exit {process.returncode}",
            stage="exit",
            stdout=stdout,
            stderr=stderr,
            context=full_context,
        )
    try:
        text = stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        fail(
            "xpu-smi ps output is not UTF-8",
            stage="decode",
            stdout=stdout,
            stderr=stderr,
            context=full_context,
        )
    try:
        payload = strict_json_loads(text)
    except (json.JSONDecodeError, ValueError) as error:
        fail(
            f"xpu-smi ps output is not strict JSON: {error}",
            stage="parse",
            stdout=stdout,
            stderr=stderr,
            context=full_context,
        )
    try:
        idle = validate_idle_payload(
            payload,
            child_identity=child_identity,
            launched_executable=executable,
        )
    except RuntimeError as error:
        fail(
            f"xpu-smi ps idle validation failed: {error}",
            stage="validate",
            stdout=stdout,
            stderr=stderr,
            context=full_context,
        )

    return {
        "format": FORMAT,
        "status": "passed",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "argv": argv,
        "environment": dict(environment),
        "timeout_seconds": float(timeout_seconds),
        "xpu_smi": identity_context,
        "child_identity": asdict(child_identity),
        "raw_capture": capture,
        "idle": idle,
    }


def execute_preflight() -> tuple[dict[str, Any], int]:
    try:
        report = capture_idle_snapshot()
    except OperationalPreflightError as error:
        return (
            {
                "format": FORMAT,
                "status": "failed",
                "observed_utc": datetime.now(timezone.utc).isoformat(),
                "failure": {
                    "type": type(error).__name__,
                    "stage": error.stage,
                    "message": str(error),
                },
                "context": error.context,
                "raw_capture": encode_capture(error.stdout, error.stderr),
            },
            1,
        )
    except BaseException as error:
        return (
            {
                "format": FORMAT,
                "status": "failed",
                "observed_utc": datetime.now(timezone.utc).isoformat(),
                "failure": {
                    "type": type(error).__name__,
                    "stage": "prelaunch_validation",
                    "message": str(error),
                },
                "raw_capture": encode_capture(b"", b""),
            },
            1,
        )
    return report, 0


def _unescape_mount_field(value: str) -> str:
    return re.sub(
        r"\\([0-7]{3})",
        lambda match: chr(int(match.group(1), 8)),
        value,
    )


def _mount_record_for_path(
    target: Path,
    *,
    mountinfo_path: Path = Path("/proc/self/mountinfo"),
) -> dict[str, str]:
    resolved_target = target.resolve(strict=True)
    try:
        raw = mountinfo_path.read_text(encoding="utf-8")
    except OSError as error:
        raise RuntimeError("could not read mountinfo") from error
    candidates: list[dict[str, str]] = []
    for line in raw.splitlines():
        fields = line.split()
        try:
            separator = fields.index("-")
            major_minor = fields[2]
            mount_point = _unescape_mount_field(fields[4])
            filesystem = fields[separator + 1]
            source = _unescape_mount_field(fields[separator + 2])
        except (IndexError, ValueError):
            raise RuntimeError("malformed mountinfo row") from None
        mounted = Path(mount_point)
        if resolved_target == mounted or resolved_target.is_relative_to(mounted):
            candidates.append(
                {
                    "mount_point": mount_point,
                    "filesystem": filesystem,
                    "source": source,
                    "major_minor": major_minor,
                }
            )
    require(candidates, "no backing mount found for output root")
    return max(candidates, key=lambda item: len(Path(item["mount_point"]).parts))


def attest_internal_nvme(
    target: Path,
    *,
    mountinfo_path: Path = Path("/proc/self/mountinfo"),
    sysfs_root: Path = Path("/sys/dev/block"),
) -> dict[str, str]:
    record = _mount_record_for_path(target, mountinfo_path=mountinfo_path)
    require(
        record["filesystem"] == EXPECTED_OUTPUT_FSTYPE,
        "output filesystem is not frozen ext4",
    )
    require(
        record["source"] == EXPECTED_OUTPUT_SOURCE,
        "output source is not the frozen internal NVMe partition",
    )
    require(
        record["major_minor"] == EXPECTED_OUTPUT_MAJOR_MINOR,
        "output block-device identity drift",
    )
    try:
        sysfs_device = (sysfs_root / record["major_minor"]).resolve(strict=True)
    except OSError as error:
        raise RuntimeError("output block-device sysfs identity unavailable") from error
    require(
        any(part.startswith("nvme") for part in sysfs_device.parts),
        "output block device is not NVMe",
    )
    return {**record, "sysfs_device": str(sysfs_device)}


def reserve_output_directory(output: Path) -> tuple[Path, dict[str, str]]:
    require(output.is_absolute(), "output path must be absolute")
    require(output.suffix == ".json", "output path must end in .json")
    root = DEFAULT_OUTPUT_ROOT.resolve(strict=True)
    storage = attest_internal_nvme(root)
    candidate = output.resolve(strict=False)
    require(candidate.is_relative_to(root), "output must be on the internal NVMe")
    require(candidate.parent.parent == root, "output must use one fresh run directory")
    candidate.parent.mkdir(mode=0o700, parents=False, exist_ok=False)
    return candidate, storage


def write_report_exclusive(output: Path, report: Mapping[str, Any]) -> None:
    payload = (canonical_json(report) + "\n").encode("utf-8")
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o600,
        )
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            require(written > 0, "short report write")
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.link(temporary, output)
        os.unlink(temporary)
        directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()
    try:
        output, storage = reserve_output_directory(args.output)
    except Exception as error:
        sys.stderr.write(f"operational preflight did not run: {error}\n")
        return 2

    if args.timeout_seconds != DEFAULT_TIMEOUT_SECONDS:
        report = {
            "format": FORMAT,
            "status": "failed",
            "observed_utc": datetime.now(timezone.utc).isoformat(),
            "failure": {
                "type": "RuntimeError",
                "stage": "prelaunch_validation",
                "message": "operational CLI timeout is frozen at 20 seconds",
            },
            "raw_capture": encode_capture(b"", b""),
        }
        status = 1
    else:
        report, status = execute_preflight()
    report["output"] = {
        "path": str(output),
        "storage": storage,
    }
    write_report_exclusive(output, report)
    sys.stdout.write(canonical_json(report) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
