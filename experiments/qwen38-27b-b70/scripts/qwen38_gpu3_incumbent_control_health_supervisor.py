#!/usr/bin/env python3
"""External watchdog for the bounded GPU3 incumbent-control health probe.

This process never imports torch.  It creates the immutable contract and phase
chain, launches the XPU worker in a fresh session, and owns the wall deadline
and termination receipts.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from typing import Any


REPO = Path("/home/steve/llm-optimizations")
WORKER = REPO / (
    "experiments/qwen38-27b-b70/scripts/qwen38_gpu3_incumbent_control_health_worker.py"
)
WORKER_SHA256 = "bd8225e30e1335a3fe33e78421b1feb3cfb036ca04d0ca6738cb1eea8639b11f"
XPU_PYTHON = Path("/home/steve/.venvs/vllm-xpu/bin/python")
VENV_LIB = Path("/home/steve/.venvs/vllm-xpu/lib")
TORCH_LIB = VENV_LIB / "python3.12/site-packages/torch/lib"
DEADLINE_SECONDS = 60.0
TERM_GRACE_SECONDS = 5.0
KILL_GRACE_SECONDS = 5.0
SCHEMA_TERMINAL = "qwen38-gpu3-incumbent-control-health-terminal-v1"
SCHEMA_CLEANUP = "qwen38-gpu3-incumbent-control-health-cleanup-v1"
LAUNCH_PHASES = (
    "child-launched",
    "child-launched-after-supervisor-error",
    "child-identity-unavailable",
)


class SupervisorError(RuntimeError):
    """A fail-closed supervisor-contract violation."""


class ExternalInterrupt(BaseException):
    """Controlled wakeup raised when SIGINT or SIGTERM reaches the supervisor."""

    def __init__(self, signum: int) -> None:
        super().__init__(f"external signal {signal.Signals(signum).name}")
        self.signum = signum


class ChildIdentityAcquisitionError(SupervisorError):
    """All ordinary and supervisor-local child identity reads failed."""

    def __init__(self, pid: int, errors: list[dict[str, str]]) -> None:
        super().__init__(f"all child identity reads failed for PID {pid}")
        self.pid = pid
        self.errors = errors


class UnidentifiedChildEmergency(SupervisorError):
    """An unidentified Popen child received bounded emergency cleanup."""


def load_worker_module() -> Any:
    if not WORKER.is_file():
        raise SupervisorError(f"missing worker: {WORKER}")
    digest = hashlib.sha256()
    with WORKER.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != WORKER_SHA256:
        raise SupervisorError("worker SHA mismatch before import")
    spec = importlib.util.spec_from_file_location("qwen38_gpu3_health_worker", WORKER)
    if spec is None or spec.loader is None:
        raise SupervisorError("cannot construct worker import")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def clean_repo_identity(worker: Any) -> dict[str, Any]:
    if git_output("branch", "--show-current") != "main":
        raise SupervisorError("health diagnostic requires main")
    status = git_output("status", "--porcelain", "--untracked-files=normal")
    if status:
        raise SupervisorError("health diagnostic requires a clean lab repository")
    head = git_output("rev-parse", "HEAD")
    origin = git_output("rev-parse", "origin/main")
    if head != origin:
        raise SupervisorError("health diagnostic requires local main == origin/main")
    return {
        "path": str(REPO),
        "branch": "main",
        "head": head,
        "origin_main": origin,
        "status_porcelain_sha256": worker.sha256_bytes(b""),
    }


def stage_identity(worker: Any) -> dict[str, Any]:
    base = worker.load_base_qualifier()
    identity = base.stage_identity(
        argparse.Namespace(
            role="control", stage=str(worker.CONTROL_STAGE), stage_manifest=None
        )
    )
    if identity.get("role") != "control" or identity.get("stage") != str(
        worker.CONTROL_STAGE
    ):
        raise SupervisorError("frozen base returned a non-stock stage")
    return identity


def sealed_environment(worker: Any) -> dict[str, str]:
    return {
        "HOME": "/home/steve",
        "USER": "steve",
        "LOGNAME": "steve",
        "SHELL": "/bin/bash",
        "LANG": "C.UTF-8",
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(worker.CONTROL_STAGE),
        "LD_LIBRARY_PATH": (
            f"{worker.CONTROL_STAGE}/vllm_xpu_kernels:{VENV_LIB}:{TORCH_LIB}"
        ),
        "ZE_AFFINITY_MASK": str(worker.PHYSICAL_GPU),
        "VLLM_XPU_FA2_FORCE_CHUNK_DECODE": "1",
        worker.Q64_POLICY_ENV: "0",
        worker.Q8_POLICY_ENV: "0",
    }


def build_contract(worker: Any, output_root: Path) -> dict[str, Any]:
    if worker.sha256_file(WORKER) != WORKER_SHA256:
        raise SupervisorError("worker SHA differs from frozen supervisor binding")
    supervisor = Path(__file__).resolve(strict=True)
    return {
        "schema": worker.SCHEMA_CONTRACT,
        "created_time_ns": time.time_ns(),
        "output_root": str(output_root),
        "deadline": {
            "wall_seconds": DEADLINE_SECONDS,
            "term_grace_seconds": TERM_GRACE_SECONDS,
            "kill_grace_seconds": KILL_GRACE_SECONDS,
        },
        "repo": clean_repo_identity(worker),
        "files": {
            "supervisor": {
                "path": str(supervisor),
                "sha256": worker.sha256_file(supervisor),
            },
            "worker": {"path": str(WORKER), "sha256": WORKER_SHA256},
            "base_qualifier": {
                "path": str(worker.BASE_QUALIFIER),
                "sha256": worker.BASE_QUALIFIER_SHA256,
            },
        },
        "stage_identity": stage_identity(worker),
        "stock_graph_identity": worker.stock_graph_identity(
            worker.load_base_qualifier()
        ),
        "environment": sealed_environment(worker),
        "device": {
            "physical_gpu": worker.PHYSICAL_GPU,
            "logical_device": worker.LOGICAL_DEVICE,
            "expected_name": worker.EXPECTED_DEVICE_NAME,
            "expected_uuid": worker.EXPECTED_DEVICE_UUID,
            "pci_bdf_context": worker.EXPECTED_PCI_BDF_CONTEXT,
            "expected_hostname": worker.EXPECTED_HOSTNAME,
        },
        "workload": {
            "kv_length": worker.EXPECTED_KV_LENGTH,
            "returned_fa_launches": worker.EXPECTED_RETURNED_LAUNCHES,
            "is_mix_batch": True,
            "force_chunk_decode": True,
            "stop_after_first_explicit_synchronize": True,
        },
    }


def process_group_members(worker: Any, group: dict[str, Any]) -> list[dict[str, Any]]:
    pgid = worker.require_int(group["pgid"], "process group pgid")
    sid = worker.require_int(group["sid"], "process group sid")
    if pgid != sid or pgid <= 1:
        raise SupervisorError(f"unsafe process group identity: pgid={pgid} sid={sid}")
    members: list[dict[str, Any]] = []
    for stat_path in Path("/proc").glob("[0-9]*/stat"):
        try:
            parsed = worker.parse_proc_stat(
                stat_path.read_text(encoding="utf-8"), str(stat_path)
            )
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if parsed["pgid"] == pgid and parsed["sid"] == sid:
            try:
                identity = worker.process_identity(parsed["pid"])
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            if identity["pgid"] == pgid and identity["sid"] == sid:
                members.append(identity)
    return sorted(members, key=lambda item: (item["pid"], item["start_ticks"]))


def supervisor_local_process_group_members(
    worker: Any, group: dict[str, Any]
) -> list[dict[str, Any]]:
    """Scan a marked fallback group without calling worker.process_identity."""

    pgid = worker.require_int(group["pgid"], "fallback process group pgid")
    sid = worker.require_int(group["sid"], "fallback process group sid")
    if pgid != sid or pgid <= 1:
        raise SupervisorError(f"unsafe fallback group: pgid={pgid} sid={sid}")
    members: list[dict[str, Any]] = []
    for stat_path in Path("/proc").glob("[0-9]*/stat"):
        try:
            parsed = worker.parse_proc_stat(
                stat_path.read_text(encoding="utf-8"), str(stat_path)
            )
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if parsed["pgid"] == pgid and parsed["sid"] == sid:
            identity = supervisor_local_process_identity(worker, parsed["pid"])
            if identity["pgid"] == pgid and identity["sid"] == sid:
                members.append(identity)
    return sorted(members, key=lambda item: (item["pid"], item["start_ticks"]))


def verified_process_group_members(
    worker: Any,
    proc: subprocess.Popen[bytes],
    child_process: dict[str, Any],
    group_fn: Any = process_group_members,
    identity_fn: Any | None = None,
) -> list[dict[str, Any]]:
    members = group_fn(worker, child_process)
    if members or proc.poll() is not None:
        return members
    current = (
        worker.process_identity(proc.pid)
        if identity_fn is None
        else identity_fn(proc.pid)
    )
    if current != child_process:
        raise SupervisorError("live process-group leader identity changed")
    return [current]


def wait_until(
    proc: subprocess.Popen[bytes],
    deadline: float,
    pending_signals: list[int] | None = None,
    *,
    worker: Any | None = None,
    process_group: dict[str, Any] | None = None,
    group_fn: Any = process_group_members,
) -> int | None:
    while True:
        if pending_signals:
            raise ExternalInterrupt(pending_signals[0])
        returncode = proc.poll()
        members = (
            group_fn(worker, process_group)
            if worker is not None and process_group is not None
            else ([] if returncode is not None else [process_group])
        )
        if returncode is not None and not members:
            return returncode
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        time.sleep(min(0.05, remaining))


def receipt_snapshot(worker: Any, directory: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not directory.is_dir():
        return result
    for path in sorted(directory.glob("*.json")):
        result.append(
            {
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": worker.sha256_file(path),
            }
        )
    return result


def finalize_log(worker: Any, temporary: Path, final: Path) -> dict[str, Any]:
    if not temporary.is_file() or final.exists():
        raise SupervisorError(f"log finalization collision/missing temporary: {final}")
    with temporary.open("rb") as stream:
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o444)
    os.replace(temporary, final)
    directory_descriptor = os.open(final.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)
    return {
        "path": str(final),
        "sha256": worker.sha256_file(final),
        "size_bytes": final.stat().st_size,
        "mode": "0444",
        "immutable": True,
    }


def temporary_log_observation(worker: Any, path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256_at_terminal": worker.sha256_file(path),
        "size_bytes_at_terminal": path.stat().st_size,
        "mode_at_terminal": f"{path.stat().st_mode & 0o777:04o}",
        "immutable": False,
    }


def validate_process_identity(
    worker: Any, value: Any, where: str, *, group_leader: bool = False
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SupervisorError(f"{where} is not an object")
    worker.require_exact_keys(
        value, ("boot_id", "pid", "pgid", "sid", "start_ticks"), where
    )
    if not isinstance(value["boot_id"], str) or not value["boot_id"]:
        raise SupervisorError(f"{where}.boot_id is missing")
    for name in ("pid", "pgid", "sid", "start_ticks"):
        if worker.require_int(value[name], f"{where}.{name}") <= 0:
            raise SupervisorError(f"{where}.{name} must be positive")
    if group_leader and not (value["pid"] == value["pgid"] == value["sid"]):
        raise SupervisorError(f"{where} is not a process-group/session leader")
    return value


def validate_process_group_snapshot(
    worker: Any, value: Any, child: dict[str, Any], where: str
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise SupervisorError(f"{where} is not an array")
    result: list[dict[str, Any]] = []
    previous: tuple[int, int] | None = None
    for index, item in enumerate(value):
        identity = validate_process_identity(worker, item, f"{where}[{index}]")
        if (
            identity["boot_id"] != child["boot_id"]
            or identity["pgid"] != child["pgid"]
            or identity["sid"] != child["sid"]
        ):
            raise SupervisorError(f"{where}[{index}] escaped the sealed process group")
        order = (identity["pid"], identity["start_ticks"])
        if previous is not None and order <= previous:
            raise SupervisorError(f"{where} is not strictly sorted and unique")
        previous = order
        result.append(identity)
    return result


def validate_snapshot_entries(
    worker: Any,
    entries: Any,
    output_root: Path,
    where: str,
    *,
    require_current: bool,
) -> None:
    if not isinstance(entries, list):
        raise SupervisorError(f"{where} is not an array")
    seen: set[Path] = set()
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise SupervisorError(f"{where}[{index}] is not an object")
        expected_keys = {"path", "size_bytes", "sha256"}
        if "writable" in item:
            expected_keys.add("writable")
        worker.require_exact_keys(item, expected_keys, f"{where}[{index}]")
        path = Path(item["path"])
        if not path.is_absolute():
            path = output_root / path
        try:
            path.relative_to(output_root)
        except ValueError as error:
            raise SupervisorError(
                f"{where}[{index}] path escapes output root"
            ) from error
        if not path.is_file() or path.resolve(strict=True) != path:
            raise SupervisorError(f"{where}[{index}] path is missing or non-canonical")
        if path in seen:
            raise SupervisorError(f"{where} contains a duplicate path")
        seen.add(path)
        size = worker.require_int(item["size_bytes"], f"{where}[{index}].size_bytes")
        digest = item["sha256"]
        if (
            size < 0
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            raise SupervisorError(f"{where}[{index}] has malformed metadata")
        immutable = item.get("writable") is not True
        if require_current or immutable:
            if path.stat().st_size != size or worker.sha256_file(path) != digest:
                raise SupervisorError(f"{where}[{index}] current bytes changed")
            if immutable and path.stat().st_mode & 0o222:
                raise SupervisorError(f"{where}[{index}] became writable")


def validate_mapping_payload(
    worker: Any, mapping: Any, stage_identity: dict[str, Any], where: str
) -> dict[str, Any]:
    if not isinstance(mapping, dict):
        raise SupervisorError(f"{where} is not an object")
    worker.require_exact_keys(
        mapping,
        (
            "proc_self_maps_sha256",
            "required",
            "selected_lines",
            "same_basename_paths",
            "passed",
        ),
        where,
    )
    digest = mapping["proc_self_maps_sha256"]
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise SupervisorError(f"{where} maps SHA is malformed")
    names = ("extension", "device_library", "stock_library")
    expected_required = {
        name: {
            "path": stage_identity["files"][name]["path"],
            "sha256": stage_identity["files"][name]["sha256"],
        }
        for name in names
    }
    if mapping["required"] != expected_required or mapping["passed"] is not True:
        raise SupervisorError(f"{where} required mappings differ")
    expected_paths = {name: [expected_required[name]["path"]] for name in names}
    if mapping["same_basename_paths"] != expected_paths:
        raise SupervisorError(f"{where} same-basename inventory differs")
    selected = mapping["selected_lines"]
    if not isinstance(selected, dict) or set(selected) != set(names):
        raise SupervisorError(f"{where} selected-line keys differ")
    for name in names:
        lines = selected[name]
        if not isinstance(lines, list) or not lines:
            raise SupervisorError(f"{where}.{name} has no mapped lines")
        for line in lines:
            if not isinstance(line, str):
                raise SupervisorError(f"{where}.{name} line is not text")
            fields = line.split(maxsplit=5)
            if len(fields) != 6 or fields[5] != expected_required[name]["path"]:
                raise SupervisorError(f"{where}.{name} mapped line path differs")
        path = Path(expected_required[name]["path"])
        if worker.sha256_file(path) != expected_required[name]["sha256"]:
            raise SupervisorError(f"{where}.{name} current file SHA differs")
    return mapping


def emit_launch_boundary_nonthrowing(
    chain: Any,
    command: list[str],
    child_process: dict[str, Any],
    *,
    fallback_only=False,
) -> tuple[str | None, list[dict[str, str]], BaseException | None]:
    errors: list[dict[str, str]] = []
    first_error: BaseException | None = None
    phases = (
        ("child-launched-after-supervisor-error",)
        if fallback_only
        else ("child-launched", "child-launched-after-supervisor-error")
    )
    for phase in phases:
        try:
            chain.emit(phase, {"argv": command, "child_process": child_process})
        except BaseException as error:
            if first_error is None:
                first_error = error
            errors.append(
                {
                    "operation": f"emit:{phase}",
                    "exception_type": type(error).__name__,
                    "message": str(error),
                }
            )
            continue
        return phase, errors, first_error
    return None, errors, first_error


def exception_record(operation: str, error: BaseException) -> dict[str, str]:
    return {
        "operation": operation,
        "exception_type": type(error).__name__,
        "message": str(error),
    }


def supervisor_local_process_identity(worker: Any, pid: int) -> dict[str, Any]:
    """Read exact proc identity without calling the worker identity helper."""

    stat_path = Path(f"/proc/{pid}/stat")
    parsed = worker.parse_proc_stat(
        stat_path.read_text(encoding="utf-8"), str(stat_path)
    )
    if parsed["pid"] != pid:
        raise SupervisorError("supervisor-local process stat PID differs")
    identity = {
        "boot_id": Path("/proc/sys/kernel/random/boot_id")
        .read_text(encoding="utf-8")
        .strip(),
        **parsed,
    }
    validate_process_identity(
        worker, identity, "supervisor-local child", group_leader=True
    )
    return identity


def acquire_child_identity(
    worker: Any, pid: int
) -> tuple[dict[str, Any], bool, list[dict[str, str]]]:
    """Try the canonical reader twice, then a marked supervisor-local fallback."""

    errors: list[dict[str, str]] = []
    for attempt in (1, 2):
        try:
            identity = worker.process_identity(pid)
            validate_process_identity(
                worker,
                identity,
                f"worker child identity attempt {attempt}",
                group_leader=True,
            )
        except BaseException as error:
            errors.append(
                exception_record(f"worker-process-identity-attempt-{attempt}", error)
            )
            continue
        return identity, True, errors
    try:
        identity = supervisor_local_process_identity(worker, pid)
    except BaseException as error:
        errors.append(exception_record("supervisor-local-process-identity", error))
        raise ChildIdentityAcquisitionError(pid, errors) from error
    return identity, False, errors


def emit_unverified_identity_boundary_nonthrowing(
    chain: Any,
    command: list[str],
    child_process: dict[str, Any],
    identity_errors: list[dict[str, str]],
) -> tuple[str | None, list[dict[str, str]], BaseException | None]:
    phase = "child-identity-unavailable"
    try:
        chain.emit(
            phase,
            {
                "argv": command,
                "child_process": child_process,
                "identity_errors": identity_errors,
            },
        )
    except BaseException as error:
        return None, [exception_record(f"emit:{phase}", error)], error
    return phase, [], None


def emergency_cleanup_unidentified_child(
    worker: Any,
    proc: subprocess.Popen[bytes],
    chain: Any,
    output_root: Path,
    started_monotonic: float,
    identity_errors: list[dict[str, str]],
    *,
    killpg_fn: Any = os.killpg,
    kill_pid_fn: Any = os.kill,
    monotonic_fn: Any = time.monotonic,
    sleep_fn: Any = time.sleep,
) -> dict[str, Any]:
    """Best-effort bounded cleanup using only Popen's fresh-session guarantee."""

    pgid = proc.pid
    errors = list(identity_errors)
    receipts_persisted: list[str] = []

    def record_error(operation: str, error: BaseException | str) -> None:
        if isinstance(error, BaseException):
            errors.append(exception_record(operation, error))
        else:
            errors.append(
                {
                    "operation": operation,
                    "exception_type": "EmergencyCleanupError",
                    "message": error,
                }
            )

    def emit(phase: str, data: dict[str, Any]) -> None:
        try:
            chain.emit(phase, data)
        except BaseException as error:
            record_error(f"emit:{phase}", error)
        else:
            receipts_persisted.append(phase)

    def poll(operation: str) -> int | None:
        try:
            return proc.poll()
        except BaseException as error:
            record_error(operation, error)
            return None

    def now(operation: str) -> float:
        try:
            return monotonic_fn()
        except BaseException as error:
            record_error(operation, error)
            return started_monotonic + TERM_GRACE_SECONDS + KILL_GRACE_SECONDS + 1.0

    def pause(seconds: float, operation: str) -> None:
        try:
            sleep_fn(seconds)
        except BaseException as error:
            record_error(operation, error)

    def probe_group(operation: str) -> bool | None:
        try:
            killpg_fn(pgid, 0)
        except OSError as error:
            if error.errno == errno.ESRCH:
                return False
            record_error(operation, error)
            return None
        except BaseException as error:
            record_error(operation, error)
            return None
        return True

    def signal_group(sent_signal: signal.Signals, operation: str) -> bool:
        try:
            killpg_fn(pgid, sent_signal)
        except OSError as error:
            if error.errno != errno.ESRCH:
                record_error(operation, error)
                return False
            record_error(f"{operation}:group-esrch", error)
            if poll(f"{operation}:pid-fallback-poll") is not None:
                return False
            try:
                kill_pid_fn(proc.pid, sent_signal)
            except OSError as pid_error:
                if pid_error.errno != errno.ESRCH:
                    record_error(f"{operation}:pid-fallback", pid_error)
                return False
            except BaseException as pid_error:
                record_error(f"{operation}:pid-fallback", pid_error)
                return False
            return True
        except BaseException as error:
            record_error(operation, error)
            return False
        return True

    def wait_for_empty(
        deadline: float, operation: str
    ) -> tuple[int | None, bool | None]:
        returncode: int | None = None
        exists: bool | None = None
        while True:
            returncode = poll(f"{operation}:poll")
            exists = probe_group(f"{operation}:probe")
            if exists is False and returncode is not None:
                return returncode, exists
            current = now(f"{operation}:clock")
            if current >= deadline:
                return returncode, exists
            pause(min(0.05, max(0.0, deadline - current)), f"{operation}:sleep")

    provisional = {
        "popen_pid": pgid,
        "expected_pgid": pgid,
        "start_new_session": True,
    }
    group_before_term = probe_group("pre-term-group-probe")
    emit(
        "child-identity-unavailable-emergency-before-term",
        {
            "provisional_child": provisional,
            "identity_errors": identity_errors,
            "group_exists_before_term": group_before_term,
            "elapsed_seconds": now("emergency-entry-clock") - started_monotonic,
        },
    )
    sigterm_attempted = group_before_term is not False or poll("pre-term-poll") is None
    sigterm_sent = (
        signal_group(signal.SIGTERM, "send-emergency-sigterm")
        if sigterm_attempted
        else False
    )
    returncode, group_after_term = wait_for_empty(
        now("emergency-term-deadline-clock") + TERM_GRACE_SECONDS,
        "emergency-term-grace",
    )
    sigkill_attempted = group_after_term is not False or returncode is None
    sigkill_sent = False
    if sigkill_attempted:
        emit(
            "child-identity-unavailable-emergency-before-kill",
            {
                "provisional_child": provisional,
                "group_exists_before_kill": group_after_term,
                "term_grace_seconds": TERM_GRACE_SECONDS,
            },
        )
        sigkill_sent = signal_group(signal.SIGKILL, "send-emergency-sigkill")
    returncode, final_group_exists = wait_for_empty(
        now("emergency-kill-deadline-clock") + KILL_GRACE_SECONDS,
        "emergency-kill-grace",
    )
    unkillable = final_group_exists is not False or returncode is None
    logs: dict[str, Any] = {}
    for name in ("stdout", "stderr"):
        path = output_root / f"worker.{name}.log.tmp"
        try:
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
            logs[name] = {
                "path": str(path),
                "sha256_at_emergency": worker.sha256_file(path),
                "size_bytes_at_emergency": path.stat().st_size,
                "possibly_mutable": unkillable,
            }
        except BaseException as error:
            record_error(f"snapshot-emergency-{name}", error)
            logs[name] = None
    state = {
        "schema": "qwen38-gpu3-unidentified-child-emergency-v1",
        "contract_path": str(chain.contract_path),
        "contract_sha256": chain.contract_sha256,
        "provisional_child": provisional,
        "identity_errors": identity_errors,
        "receipts_persisted": receipts_persisted,
        "sigterm_attempted": sigterm_attempted,
        "sigterm_sent": sigterm_sent,
        "sigkill_attempted": sigkill_attempted,
        "sigkill_sent": sigkill_sent,
        "child_returncode": None if unkillable else returncode,
        "final_group_exists": final_group_exists,
        "unkillable": unkillable,
        "errors": errors,
        "logs": logs,
    }
    emit("child-identity-unavailable-emergency-complete", state)
    state["receipts_persisted"] = list(receipts_persisted)
    packet_path = output_root / "unidentified-child-emergency.json"
    try:
        worker.atomic_json(packet_path, state)
    except BaseException as error:
        record_error("persist-unidentified-child-emergency", error)
    return state


def cleanup_process_group(
    worker: Any,
    proc: subprocess.Popen[bytes],
    child_process: dict[str, Any],
    chain: Any,
    output_root: Path,
    started_monotonic: float,
    reason: str,
    abort: dict[str, Any] | None,
    *,
    launch_receipt_phase: str | None = "child-launched",
    initial_errors: list[dict[str, str]] | None = None,
    group_fn: Any = process_group_members,
    identity_fn: Any | None = None,
    killpg_fn: Any = os.killpg,
    monotonic_fn: Any = time.monotonic,
    sleep_fn: Any = time.sleep,
) -> dict[str, Any]:
    """Non-reentrant, non-throwing process-group cleanup state machine."""

    if reason not in ("timeout", "external-interrupt", "supervisor-baseexception"):
        raise SupervisorError(f"unknown cleanup reason: {reason}")
    errors: list[dict[str, str]] = list(initial_errors or [])
    receipts_persisted: list[str] = []
    sigterm_attempted = False
    sigterm_sent = False
    sigkill_attempted = False
    sigkill_sent = False
    term_disappeared = False
    kill_disappeared = False

    def record_error(operation: str, error: BaseException | str) -> None:
        if isinstance(error, str):
            error_type = "CleanupStateError"
            message = error
        else:
            error_type = type(error).__name__
            message = str(error)
        errors.append(
            {"operation": operation, "exception_type": error_type, "message": message}
        )

    def emit(phase: str, data: dict[str, Any]) -> bool:
        try:
            chain.emit(phase, data)
        except BaseException as error:
            record_error(f"emit:{phase}", error)
            return False
        receipts_persisted.append(phase)
        return True

    def poll(operation: str) -> int | None:
        try:
            return proc.poll()
        except BaseException as error:
            record_error(operation, error)
            return None

    def scan(operation: str) -> tuple[bool, list[dict[str, Any]]]:
        try:
            members = verified_process_group_members(
                worker, proc, child_process, group_fn, identity_fn
            )
            return True, members
        except BaseException as error:
            record_error(operation, error)
            return False, []

    def send_group_signal(
        sent_signal: signal.Signals, operation: str
    ) -> tuple[bool, bool]:
        try:
            killpg_fn(child_process["pgid"], sent_signal)
            return True, False
        except OSError as error:
            if error.errno != errno.ESRCH:
                record_error(operation, error)
                return False, False
            verified, members = scan(f"{operation}:esrch-rescan")
            if verified and not members:
                return False, True
            record_error(operation, error)
            return False, False
        except BaseException as error:
            record_error(operation, error)
            return False, False

    def wait_for_empty(
        deadline: float, operation: str
    ) -> tuple[int | None, bool, list]:
        last_verified = False
        last_members: list[dict[str, Any]] = []
        while True:
            returncode = poll(f"{operation}:poll")
            verified, members = scan(f"{operation}:scan")
            if verified:
                last_verified = True
                last_members = members
                if returncode is not None and not members:
                    return returncode, True, []
            if monotonic_fn() >= deadline:
                return returncode, last_verified, last_members
            sleep_fn(min(0.05, max(0.0, deadline - monotonic_fn())))

    entry_phase = {
        "timeout": "timeout-before-term",
        "external-interrupt": "external-interrupt-before-term",
        "supervisor-baseexception": "supervisor-abort-before-term",
    }[reason]
    verified_before_term, group_before_term = scan("pre-term-group-scan")
    try:
        worker_phase_snapshot = receipt_snapshot(worker, output_root / "worker-phases")
    except BaseException as error:
        record_error("worker-phase-snapshot-before-term", error)
        worker_phase_snapshot = []
    entry_data = {
        "elapsed_seconds": monotonic_fn() - started_monotonic,
        "child_process": child_process,
        "worker_phase_snapshot": worker_phase_snapshot,
        "cleanup_reason": reason,
        "abort": abort,
        "group_scan_verified": verified_before_term,
        "process_group_before_term": group_before_term,
        "cleanup_errors_before_term": list(errors),
    }
    entry_receipt_persisted = emit(entry_phase, entry_data)

    if verified_before_term and group_before_term:
        sigterm_attempted = True
        sigterm_sent, term_disappeared = send_group_signal(
            signal.SIGTERM, "send-sigterm"
        )

    term_deadline = monotonic_fn() + TERM_GRACE_SECONDS
    child_returncode, term_scan_verified, group_after_term = wait_for_empty(
        term_deadline, "term-grace"
    )
    term_grace_receipt_persisted = False
    if term_scan_verified and group_after_term:
        term_grace_receipt_persisted = emit(
            "term-grace-expired-before-kill",
            {
                "child_process": child_process,
                "term_grace_seconds": TERM_GRACE_SECONDS,
                "process_group_before_kill": group_after_term,
            },
        )
        sigkill_attempted = True
        sigkill_sent, kill_disappeared = send_group_signal(
            signal.SIGKILL, "send-sigkill"
        )

    kill_deadline = monotonic_fn() + KILL_GRACE_SECONDS
    child_returncode, final_scan_verified, final_members = wait_for_empty(
        kill_deadline, "kill-grace"
    )
    if final_scan_verified and final_members:
        emit(
            "final-kill-retry-before-signal",
            {
                "child_process": child_process,
                "process_group_before_final_kill": final_members,
            },
        )
        sigkill_attempted = True
        retry_sent, retry_disappeared = send_group_signal(
            signal.SIGKILL, "send-final-sigkill"
        )
        sigkill_sent = sigkill_sent or retry_sent
        kill_disappeared = kill_disappeared or retry_disappeared
        final_scan_verified, final_members = scan("final-kill-verification")
        child_returncode = poll("final-kill-verification:poll")
    unkillable = not final_scan_verified or bool(final_members)
    leader_returncode_observed = child_returncode
    state = {
        "reason": reason,
        "launch_receipt_phase": launch_receipt_phase,
        "entry_phase": entry_phase,
        "entry_receipt_persisted": entry_receipt_persisted,
        "term_grace_receipt_persisted": term_grace_receipt_persisted,
        "receipts_persisted": receipts_persisted,
        "sigterm_attempted": sigterm_attempted,
        "sigterm_sent": sigterm_sent,
        "sigterm_esrch_group_disappeared": term_disappeared,
        "sigkill_attempted": sigkill_attempted,
        "sigkill_sent": sigkill_sent,
        "sigkill_esrch_group_disappeared": kill_disappeared,
        "leader_returncode_observed": leader_returncode_observed,
        "child_returncode": None if unkillable else child_returncode,
        "final_group_scan_verified": final_scan_verified,
        "final_process_group_snapshot": final_members,
        "unkillable": unkillable,
        "errors": errors,
    }
    emit("cleanup-complete", state)
    state["receipts_persisted"] = list(receipts_persisted)
    cleanup_packet_path = output_root / "cleanup-state.json"
    cleanup_packet = {
        "schema": SCHEMA_CLEANUP,
        "contract_path": str(chain.contract_path),
        "contract_sha256": chain.contract_sha256,
        "child_process": child_process,
        "cleanup": state,
    }
    try:
        worker.atomic_json(cleanup_packet_path, cleanup_packet)
        durable_packet = {
            "path": str(cleanup_packet_path),
            "sha256": worker.sha256_file(cleanup_packet_path),
        }
    except BaseException as error:
        record_error("persist-cleanup-state", error)
        durable_packet = None
    state["durable_packet"] = durable_packet
    return state


def validate_worker_receipt_payloads(
    worker: Any,
    receipts: list[dict[str, Any]],
    contract: dict[str, Any],
    child_process: dict[str, Any],
    mapping: dict[str, Any] | None,
) -> dict[str, Any] | None:
    payloads = [worker.load_json(Path(item["path"])) for item in receipts]
    expected_phases = (
        ["worker-start", "base-and-stage-verified", "device-bound", "stock-maps-bound"]
        + ["fa-launch-returned"] * worker.EXPECTED_RETURNED_LAUNCHES
        + ["sync-enter", "sync-return", "worker-complete"]
    )
    if [payload["phase"] for payload in payloads] != expected_phases[: len(payloads)]:
        raise SupervisorError("worker receipt phases are not an exact success prefix")
    if any(payload["process"] != child_process for payload in payloads):
        raise SupervisorError("worker receipt child identity mismatch")
    expected_start = {
        "hostname": worker.EXPECTED_HOSTNAME,
        "worker_sha256": contract["files"]["worker"]["sha256"],
        "base_qualifier_sha256": worker.BASE_QUALIFIER_SHA256,
    }
    if payloads and payloads[0]["data"] != expected_start:
        raise SupervisorError("worker-start payload mismatch")
    expected_stage = {
        "base_qualifier_sha256": worker.BASE_QUALIFIER_SHA256,
        "stage": str(worker.CONTROL_STAGE),
        "stage_hashes": contract["stage_identity"]["hashes"],
        "stock_graph_manifest_path": contract["stock_graph_identity"]["manifest_path"],
        "stock_graph_manifest_sha256": contract["stock_graph_identity"][
            "manifest_sha256"
        ],
        "stock_graph_file_count": contract["stock_graph_identity"]["file_count"],
    }
    if len(payloads) >= 2 and payloads[1]["data"] != expected_stage:
        raise SupervisorError("base-and-stage receipt payload mismatch")
    expected_device = {
        "device_count": 1,
        "logical_device": worker.LOGICAL_DEVICE,
        "physical_gpu": worker.PHYSICAL_GPU,
        "ze_affinity_mask": str(worker.PHYSICAL_GPU),
        "device_name": worker.EXPECTED_DEVICE_NAME,
        "device_uuid": worker.EXPECTED_DEVICE_UUID,
        "pci_bdf_context": worker.EXPECTED_PCI_BDF_CONTEXT,
    }
    if len(payloads) >= 3 and payloads[2]["data"] != expected_device:
        raise SupervisorError("device-bound receipt payload mismatch")
    receipt_mapping: dict[str, Any] | None = None
    if len(payloads) >= 4:
        receipt_mapping = validate_mapping_payload(
            worker,
            payloads[3]["data"],
            contract["stage_identity"],
            "stock-maps receipt",
        )
        if mapping is not None and receipt_mapping != mapping:
            raise SupervisorError("stock-maps receipt payload mismatch")
    for launch_index, payload in enumerate(payloads[4:14], 1):
        data = payload["data"]
        if data != {
            "launch_index": launch_index,
            "expected_launches": worker.EXPECTED_RETURNED_LAUNCHES,
            "return_type": "Tensor",
        }:
            raise SupervisorError("FA launch receipt payload mismatch")
    if len(payloads) >= 15 and payloads[14]["data"] != {
        "returned_launches": worker.EXPECTED_RETURNED_LAUNCHES,
        "maps_sha256": receipt_mapping["proc_self_maps_sha256"],
    }:
        raise SupervisorError("sync-enter receipt payload mismatch")
    if len(payloads) >= 16 and payloads[15]["data"] != {
        "returned_launches": worker.EXPECTED_RETURNED_LAUNCHES,
        "synchronize_returns": 1,
    }:
        raise SupervisorError("sync-return receipt payload mismatch")
    if len(payloads) >= 17 and payloads[16]["data"] != {
        "returned_fa_launches": worker.EXPECTED_RETURNED_LAUNCHES,
        "synchronize_entries": 1,
        "synchronize_returns": 1,
    }:
        raise SupervisorError("worker-complete receipt payload mismatch")
    return receipt_mapping


def validate_worker_success(
    worker: Any,
    output_root: Path,
    contract_path: Path,
    contract_sha: str,
    child_process: dict[str, Any],
) -> dict[str, Any]:
    path = output_root / "worker-result.json"
    if not path.is_file() or path.stat().st_mode & 0o222:
        raise SupervisorError("worker success packet missing or writable")
    packet = worker.load_json(path)
    if not isinstance(packet, dict):
        raise SupervisorError("worker success packet is not an object")
    worker.require_exact_keys(
        packet,
        (
            "schema",
            "passed",
            "classification",
            "contract_path",
            "contract_sha256",
            "process",
            "device",
            "stage_identity",
            "stock_graph_identity",
            "mapping_evidence",
            "workload",
            "phase_receipts",
        ),
        str(path),
    )
    contract = worker.load_json(contract_path)
    mapping = validate_mapping_payload(
        worker, packet["mapping_evidence"], contract["stage_identity"], "worker mapping"
    )
    if (
        packet["schema"] != worker.SCHEMA_RESULT
        or packet["passed"] is not True
        or packet["classification"] != "gpu3-incumbent-control-health-pass"
        or packet["contract_path"] != str(contract_path)
        or packet["contract_sha256"] != contract_sha
        or packet["process"] != child_process
        or packet["stage_identity"] != contract["stage_identity"]
        or packet["stock_graph_identity"] != contract["stock_graph_identity"]
        or packet["device"]
        != {
            "physical_gpu": worker.PHYSICAL_GPU,
            "logical_device": worker.LOGICAL_DEVICE,
            "name": worker.EXPECTED_DEVICE_NAME,
            "uuid": worker.EXPECTED_DEVICE_UUID,
            "pci_bdf_context": worker.EXPECTED_PCI_BDF_CONTEXT,
        }
        or packet["workload"]
        != {
            "returned_fa_launches": worker.EXPECTED_RETURNED_LAUNCHES,
            "synchronize_entries": 1,
            "synchronize_returns": 1,
        }
        or packet["mapping_evidence"] != mapping
    ):
        raise SupervisorError("worker success packet contract mismatch")
    receipts = worker.validate_receipt_chain(
        output_root / "worker-phases", "worker", contract_path, contract_sha
    )
    expected_phases = (
        ["worker-start", "base-and-stage-verified", "device-bound", "stock-maps-bound"]
        + ["fa-launch-returned"] * worker.EXPECTED_RETURNED_LAUNCHES
        + ["sync-enter", "sync-return", "worker-complete"]
    )
    if [item["phase"] for item in receipts] != expected_phases:
        raise SupervisorError("worker receipt phase sequence mismatch")
    if packet["phase_receipts"] != receipts:
        raise SupervisorError("worker result receipt inventory mismatch")
    validate_worker_receipt_payloads(worker, receipts, contract, child_process, mapping)
    return {
        "path": str(path),
        "sha256": worker.sha256_file(path),
        "phase_count": len(receipts),
    }


def validate_worker_failure(
    worker: Any,
    output_root: Path,
    contract_path: Path,
    contract_sha: str,
    child_process: dict[str, Any],
) -> dict[str, Any] | None:
    path = output_root / "worker-failure.json"
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_mode & 0o222:
        raise SupervisorError("worker failure packet is not immutable")
    packet = worker.load_json(path)
    if not isinstance(packet, dict):
        raise SupervisorError("worker failure packet is not an object")
    worker.require_exact_keys(
        packet,
        (
            "schema",
            "passed",
            "classification",
            "contract_path",
            "contract_sha256",
            "process",
            "exception_type",
            "message",
            "phase_receipt_snapshot",
            "receipt_chain_validation_error",
        ),
        str(path),
    )
    if (
        packet["schema"] != worker.SCHEMA_FAILURE
        or packet["passed"] is not False
        or packet["classification"] != "gpu3-incumbent-control-health-worker-failure"
        or packet["contract_path"] != str(contract_path)
        or packet["contract_sha256"] != contract_sha
        or packet["process"] != child_process
        or not isinstance(packet["exception_type"], str)
        or not packet["exception_type"]
        or not isinstance(packet["message"], str)
    ):
        raise SupervisorError("worker failure packet contract mismatch")
    validate_process_identity(worker, packet["process"], "worker_failure.process")
    validate_snapshot_entries(
        worker,
        packet["phase_receipt_snapshot"],
        output_root,
        "worker_failure.phase_receipt_snapshot",
        require_current=True,
    )
    chain_error = packet["receipt_chain_validation_error"]
    if chain_error is not None and (
        not isinstance(chain_error, str) or not chain_error
    ):
        raise SupervisorError("worker failure chain error is malformed")
    receipts: list[dict[str, Any]] = []
    current_chain_error: str | None = None
    if packet["phase_receipt_snapshot"]:
        try:
            receipts = worker.validate_receipt_chain(
                output_root / "worker-phases", "worker", contract_path, contract_sha
            )
        except Exception as error:
            current_chain_error = f"{type(error).__name__}: {error}"
    if chain_error != current_chain_error:
        raise SupervisorError("worker failure chain error does not rederive")
    if chain_error is None and packet["phase_receipt_snapshot"]:
        canonical_snapshot = [
            {
                "path": item["path"],
                "size_bytes": Path(item["path"]).stat().st_size,
                "sha256": item["sha256"],
            }
            for item in receipts
        ]
        if packet["phase_receipt_snapshot"] != canonical_snapshot:
            raise SupervisorError("worker failure receipt snapshot differs from chain")
        for receipt in receipts:
            payload = worker.load_json(Path(receipt["path"]))
            if payload["process"] != child_process:
                raise SupervisorError("worker failure receipt process mismatch")
    return {"path": str(path), "sha256": worker.sha256_file(path)}


def validate_worker_partial_chain(
    worker: Any,
    output_root: Path,
    contract_path: Path,
    contract_sha: str,
    child_process: dict[str, Any],
) -> list[dict[str, Any]]:
    phase_directory = output_root / "worker-phases"
    snapshot = receipt_snapshot(worker, phase_directory)
    if not snapshot:
        if phase_directory.exists() and any(phase_directory.iterdir()):
            raise SupervisorError(
                "worker phase directory has no complete JSON receipts"
            )
        return []
    receipts = worker.validate_receipt_chain(
        phase_directory, "worker", contract_path, contract_sha
    )
    canonical_snapshot = [
        {
            "path": item["path"],
            "size_bytes": Path(item["path"]).stat().st_size,
            "sha256": item["sha256"],
        }
        for item in receipts
    ]
    if snapshot != canonical_snapshot:
        raise SupervisorError("worker receipt snapshot differs from validated chain")
    validate_worker_receipt_payloads(
        worker,
        receipts,
        worker.load_json(contract_path),
        child_process,
        None,
    )
    return snapshot


def validate_worker_receipt_snapshot(
    worker: Any,
    snapshot: list[dict[str, Any]],
    contract_path: Path,
    contract_sha: str,
    child_process: dict[str, Any],
) -> None:
    previous_sha: str | None = None
    receipts: list[dict[str, Any]] = []
    for index, item in enumerate(snapshot):
        path = Path(item["path"])
        payload = worker.load_json(path)
        if not isinstance(payload, dict):
            raise SupervisorError("snapshotted worker receipt is not an object")
        worker.require_exact_keys(
            payload,
            (
                "schema",
                "writer",
                "index",
                "phase",
                "time_ns",
                "monotonic_ns",
                "contract_path",
                "contract_sha256",
                "previous_receipt_sha256",
                "process",
                "data",
            ),
            str(path),
        )
        phase = payload["phase"]
        if (
            payload["schema"] != worker.SCHEMA_RECEIPT
            or payload["writer"] != "worker"
            or worker.require_int(payload["index"], f"{path}.index") != index
            or not isinstance(phase, str)
            or path.name != f"{index:04d}-{phase}.json"
            or payload["contract_path"] != str(contract_path)
            or payload["contract_sha256"] != contract_sha
            or payload["previous_receipt_sha256"] != previous_sha
            or payload["process"] != child_process
            or not isinstance(payload["data"], dict)
        ):
            raise SupervisorError("snapshotted worker receipt chain mismatch")
        worker.require_int(payload["time_ns"], f"{path}.time_ns")
        worker.require_int(payload["monotonic_ns"], f"{path}.monotonic_ns")
        previous_sha = item["sha256"]
        receipts.append({"path": str(path), "sha256": previous_sha, "phase": phase})
    validate_worker_receipt_payloads(
        worker,
        receipts,
        worker.load_json(contract_path),
        child_process,
        None,
    )


def output_inventory(worker: Any, output_root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(output_root.rglob("*")):
        if not path.is_file() or path.name == "terminal.json":
            continue
        entries.append(
            {
                "path": str(path.relative_to(output_root)),
                "size_bytes": path.stat().st_size,
                "sha256": worker.sha256_file(path),
                "writable": bool(path.stat().st_mode & 0o222),
            }
        )
    return entries


def validate_cleanup_state(
    worker: Any,
    cleanup: Any,
    child_process: dict[str, Any],
    where: str,
    *,
    contract_path: Path | None = None,
    contract_sha: str | None = None,
) -> dict[str, Any]:
    if not isinstance(cleanup, dict):
        raise SupervisorError(f"{where} is not an object")
    worker.require_exact_keys(
        cleanup,
        (
            "reason",
            "launch_receipt_phase",
            "entry_phase",
            "entry_receipt_persisted",
            "term_grace_receipt_persisted",
            "receipts_persisted",
            "sigterm_attempted",
            "sigterm_sent",
            "sigterm_esrch_group_disappeared",
            "sigkill_attempted",
            "sigkill_sent",
            "sigkill_esrch_group_disappeared",
            "leader_returncode_observed",
            "child_returncode",
            "final_group_scan_verified",
            "final_process_group_snapshot",
            "unkillable",
            "errors",
            "durable_packet",
        ),
        where,
    )
    expected_entry = {
        "timeout": "timeout-before-term",
        "external-interrupt": "external-interrupt-before-term",
        "supervisor-baseexception": "supervisor-abort-before-term",
    }
    if (
        cleanup["reason"] not in expected_entry
        or cleanup["entry_phase"] != expected_entry[cleanup["reason"]]
    ):
        raise SupervisorError(f"{where} reason/entry phase differs")
    launch_phase = cleanup["launch_receipt_phase"]
    if launch_phase not in (
        None,
        "child-launched",
        "child-launched-after-supervisor-error",
        "child-identity-unavailable",
    ):
        raise SupervisorError(f"{where}.launch_receipt_phase differs")
    for name in (
        "entry_receipt_persisted",
        "term_grace_receipt_persisted",
        "sigterm_attempted",
        "sigterm_sent",
        "sigterm_esrch_group_disappeared",
        "sigkill_attempted",
        "sigkill_sent",
        "sigkill_esrch_group_disappeared",
        "final_group_scan_verified",
        "unkillable",
    ):
        if not isinstance(cleanup[name], bool):
            raise SupervisorError(f"{where}.{name} is not boolean")
    if cleanup["child_returncode"] is not None:
        worker.require_int(cleanup["child_returncode"], f"{where}.child_returncode")
    if cleanup["leader_returncode_observed"] is not None:
        worker.require_int(
            cleanup["leader_returncode_observed"],
            f"{where}.leader_returncode_observed",
        )
    receipts = cleanup["receipts_persisted"]
    if not isinstance(receipts, list) or any(
        not isinstance(item, str) for item in receipts
    ):
        raise SupervisorError(f"{where}.receipts_persisted is malformed")
    if len(receipts) != len(set(receipts)):
        raise SupervisorError(f"{where}.receipts_persisted has duplicates")
    if cleanup["entry_receipt_persisted"] is not (
        cleanup["entry_phase"] in receipts
    ) or cleanup["term_grace_receipt_persisted"] is not (
        "term-grace-expired-before-kill" in receipts
    ):
        raise SupervisorError(f"{where} receipt booleans differ from inventory")
    allowed_receipts = {
        cleanup["entry_phase"],
        "term-grace-expired-before-kill",
        "final-kill-retry-before-signal",
        "cleanup-complete",
    }
    if not set(receipts) <= allowed_receipts:
        raise SupervisorError(f"{where} receipt inventory has an unknown phase")
    expected_receipt_order = [
        phase
        for phase in (
            cleanup["entry_phase"],
            "term-grace-expired-before-kill",
            "final-kill-retry-before-signal",
            "cleanup-complete",
        )
        if phase in receipts
    ]
    if receipts != expected_receipt_order:
        raise SupervisorError(f"{where} receipt inventory order differs")
    errors = cleanup["errors"]
    if not isinstance(errors, list):
        raise SupervisorError(f"{where}.errors is not an array")
    for index, item in enumerate(errors):
        if not isinstance(item, dict):
            raise SupervisorError(f"{where}.errors[{index}] is not an object")
        worker.require_exact_keys(
            item,
            ("operation", "exception_type", "message"),
            f"{where}.errors[{index}]",
        )
        if any(not isinstance(item[name], str) for name in item):
            raise SupervisorError(f"{where}.errors[{index}] has a non-string value")
    error_operations = {item["operation"] for item in errors}
    primary_launch_error = "emit:child-launched" in error_operations
    fallback_launch_error = (
        "emit:child-launched-after-supervisor-error" in error_operations
    )
    identity_errors = {
        "worker-process-identity-attempt-1",
        "worker-process-identity-attempt-2",
    }
    identity_boundary_error = "emit:child-identity-unavailable" in error_operations
    if launch_phase == "child-launched" and (
        primary_launch_error or fallback_launch_error
    ):
        raise SupervisorError(f"{where} primary launch receipt/error is contradictory")
    if launch_phase == "child-launched-after-supervisor-error" and (
        not primary_launch_error or fallback_launch_error
    ):
        raise SupervisorError(f"{where} fallback launch receipt/error is contradictory")
    if launch_phase == "child-identity-unavailable" and (
        not identity_errors <= error_operations or identity_boundary_error
    ):
        raise SupervisorError(f"{where} unavailable identity evidence differs")
    if launch_phase is None and not (
        (primary_launch_error and fallback_launch_error)
        or (identity_errors <= error_operations and identity_boundary_error)
    ):
        raise SupervisorError(f"{where} missing both launch-receipt errors")
    if not cleanup["entry_receipt_persisted"] and (
        f"emit:{cleanup['entry_phase']}" not in error_operations
    ):
        raise SupervisorError(f"{where} missing entry-receipt error evidence")
    if "cleanup-complete" not in receipts and (
        "emit:cleanup-complete" not in error_operations
    ):
        raise SupervisorError(f"{where} missing cleanup-complete error evidence")
    final_members = validate_process_group_snapshot(
        worker,
        cleanup["final_process_group_snapshot"],
        child_process,
        f"{where}.final_process_group_snapshot",
    )
    if cleanup["unkillable"] is not (
        not cleanup["final_group_scan_verified"] or bool(final_members)
    ):
        raise SupervisorError(f"{where}.unkillable does not rederive")
    if cleanup["unkillable"] and cleanup["child_returncode"] is not None:
        raise SupervisorError(f"{where} unkillable cleanup exposes a final returncode")
    if (
        not cleanup["unkillable"]
        and cleanup["child_returncode"] != cleanup["leader_returncode_observed"]
    ):
        raise SupervisorError(f"{where} final and leader returncodes differ")
    if not cleanup["final_group_scan_verified"] and not errors:
        raise SupervisorError(f"{where} unverified final scan lacks an error")
    if cleanup["sigterm_sent"] and not cleanup["sigterm_attempted"]:
        raise SupervisorError(f"{where} sent SIGTERM without attempting it")
    if cleanup["sigkill_sent"] and not cleanup["sigkill_attempted"]:
        raise SupervisorError(f"{where} sent SIGKILL without attempting it")
    if cleanup["sigterm_esrch_group_disappeared"] and (
        not cleanup["sigterm_attempted"] or cleanup["sigterm_sent"]
    ):
        raise SupervisorError(f"{where} SIGTERM ESRCH state is contradictory")
    if cleanup["sigkill_esrch_group_disappeared"] and not cleanup["sigkill_attempted"]:
        raise SupervisorError(f"{where} SIGKILL ESRCH state is contradictory")
    durable_packet = cleanup["durable_packet"]
    if durable_packet is None:
        if "persist-cleanup-state" not in error_operations:
            raise SupervisorError(f"{where} lacks durable cleanup-state evidence")
    else:
        if not isinstance(durable_packet, dict):
            raise SupervisorError(f"{where}.durable_packet is not an object")
        worker.require_exact_keys(
            durable_packet, ("path", "sha256"), f"{where}.durable_packet"
        )
        packet_path = Path(durable_packet["path"])
        if (
            packet_path.name != "cleanup-state.json"
            or (
                contract_path is not None
                and packet_path != contract_path.parent / "cleanup-state.json"
            )
            or not packet_path.is_file()
            or packet_path.resolve(strict=True) != packet_path
            or packet_path.stat().st_mode & 0o222
            or worker.sha256_file(packet_path) != durable_packet["sha256"]
        ):
            raise SupervisorError(f"{where} durable packet changed")
        packet = worker.load_json(packet_path)
        if not isinstance(packet, dict):
            raise SupervisorError(f"{where} durable packet is not an object")
        worker.require_exact_keys(
            packet,
            (
                "schema",
                "contract_path",
                "contract_sha256",
                "child_process",
                "cleanup",
            ),
            f"{where}.durable_packet.payload",
        )
        expected_packet_cleanup = dict(cleanup)
        expected_packet_cleanup.pop("durable_packet")
        if (
            packet["schema"] != SCHEMA_CLEANUP
            or packet["child_process"] != child_process
            or packet["cleanup"] != expected_packet_cleanup
            or (
                contract_path is not None
                and packet["contract_path"] != str(contract_path)
            )
            or (contract_sha is not None and packet["contract_sha256"] != contract_sha)
        ):
            raise SupervisorError(f"{where} durable packet binding differs")
    return cleanup


def validate_supervisor_receipt_payloads(
    worker: Any,
    receipts: list[dict[str, Any]],
    terminal: dict[str, Any],
    contract: dict[str, Any],
    output_root: Path,
) -> None:
    payloads = [worker.load_json(Path(item["path"])) for item in receipts]
    if any(
        payload["process"] != terminal["supervisor_process"] for payload in payloads
    ):
        raise SupervisorError("supervisor receipt process identity mismatch")
    if payloads[0]["data"] != {
        "deadline_seconds": DEADLINE_SECONDS,
        "term_grace_seconds": TERM_GRACE_SECONDS,
        "kill_grace_seconds": KILL_GRACE_SECONDS,
    }:
        raise SupervisorError("supervisor-start payload mismatch")
    command = [
        str(XPU_PYTHON),
        contract["files"]["worker"]["path"],
        "--contract",
        terminal["contract_path"],
    ]
    by_phase = {payload["phase"]: payload for payload in payloads}
    cleanup = terminal["cleanup"]
    launch_phase = (
        cleanup["launch_receipt_phase"] if cleanup is not None else "child-launched"
    )
    launch_payloads = [
        payload for payload in payloads if payload["phase"] in LAUNCH_PHASES
    ]
    if launch_phase is None:
        if launch_payloads:
            raise SupervisorError("unexpected persisted child-launch receipt")
    else:
        expected_launch_data = {
            "argv": command,
            "child_process": terminal["child_process"],
        }
        if launch_phase == "child-identity-unavailable":
            expected_launch_data["identity_errors"] = terminal["child_identity_errors"]
        if (
            len(launch_payloads) != 1
            or launch_payloads[0]["phase"] != launch_phase
            or launch_payloads[0]["data"] != expected_launch_data
        ):
            raise SupervisorError("child-launch payload mismatch")
    if cleanup is not None and cleanup["entry_receipt_persisted"]:
        boundary_phase = cleanup["entry_phase"]
        data = by_phase[boundary_phase]["data"]
        worker.require_exact_keys(
            data,
            (
                "elapsed_seconds",
                "child_process",
                "worker_phase_snapshot",
                "cleanup_reason",
                "abort",
                "group_scan_verified",
                "process_group_before_term",
                "cleanup_errors_before_term",
            ),
            f"receipt.{boundary_phase}.data",
        )
        if (
            worker.require_finite(data["elapsed_seconds"], "abort elapsed") < 0
            or data["child_process"] != terminal["child_process"]
            or data["cleanup_reason"] != cleanup["reason"]
            or data["abort"] != terminal["abort"]
            or not isinstance(data["group_scan_verified"], bool)
            or cleanup["errors"][: len(data["cleanup_errors_before_term"])]
            != data["cleanup_errors_before_term"]
        ):
            raise SupervisorError("termination-boundary receipt payload mismatch")
        before_term = validate_process_group_snapshot(
            worker,
            data["process_group_before_term"],
            terminal["child_process"],
            f"receipt.{boundary_phase}.process_group_before_term",
        )
        if cleanup["sigterm_attempted"] is not (
            data["group_scan_verified"] and bool(before_term)
        ):
            raise SupervisorError("SIGTERM attempt differs from pre-TERM snapshot")
        validate_snapshot_entries(
            worker,
            data["worker_phase_snapshot"],
            output_root,
            f"receipt.{boundary_phase}.worker_phase_snapshot",
            require_current=not terminal["unkillable"],
        )
    if cleanup is not None and cleanup["term_grace_receipt_persisted"]:
        data = by_phase["term-grace-expired-before-kill"]["data"]
        worker.require_exact_keys(
            data,
            ("child_process", "term_grace_seconds", "process_group_before_kill"),
            "term-grace receipt data",
        )
        if (
            data["child_process"] != terminal["child_process"]
            or data["term_grace_seconds"] != TERM_GRACE_SECONDS
        ):
            raise SupervisorError("term-grace receipt payload mismatch")
        before_kill = validate_process_group_snapshot(
            worker,
            data["process_group_before_kill"],
            terminal["child_process"],
            "term-grace process group",
        )
        if not before_kill:
            raise SupervisorError("SIGKILL receipt lacks a live process-group member")
    if (
        cleanup is not None
        and "final-kill-retry-before-signal" in cleanup["receipts_persisted"]
    ):
        data = by_phase["final-kill-retry-before-signal"]["data"]
        worker.require_exact_keys(
            data,
            ("child_process", "process_group_before_final_kill"),
            "final-kill retry receipt data",
        )
        if data["child_process"] != terminal["child_process"]:
            raise SupervisorError("final-kill retry child differs")
        if not validate_process_group_snapshot(
            worker,
            data["process_group_before_final_kill"],
            terminal["child_process"],
            "final-kill retry process group",
        ):
            raise SupervisorError("final-kill retry lacks a verified group")
    if cleanup is not None and "cleanup-complete" in cleanup["receipts_persisted"]:
        recorded_cleanup = by_phase["cleanup-complete"]["data"]
        expected_recorded_cleanup = dict(cleanup)
        expected_recorded_cleanup.pop("durable_packet")
        expected_recorded_cleanup["receipts_persisted"] = [
            phase
            for phase in cleanup["receipts_persisted"]
            if phase != "cleanup-complete"
        ]
        recorded_errors = recorded_cleanup.get("errors")
        if (
            not isinstance(recorded_errors, list)
            or cleanup["errors"][: len(recorded_errors)] != recorded_errors
        ):
            raise SupervisorError("cleanup-complete receipt error prefix mismatch")
        expected_recorded_cleanup["errors"] = recorded_errors
        if recorded_cleanup != expected_recorded_cleanup:
            raise SupervisorError("cleanup-complete receipt payload mismatch")
    outcome = by_phase["child-outcome"]["data"]
    if outcome != {
        "child_process": terminal["child_process"],
        "child_identity_verified": terminal["child_identity_verified"],
        "child_identity_errors": terminal["child_identity_errors"],
        "returncode": terminal["child_returncode"],
        "timed_out": terminal["timed_out"],
        "sigterm_sent": terminal["sigterm_sent"],
        "sigkill_sent": terminal["sigkill_sent"],
        "unkillable": terminal["unkillable"],
        "abort": terminal["abort"],
        "cleanup": terminal["cleanup"],
        "late_signals": terminal["late_signals"],
        "final_process_group_snapshot": terminal["final_process_group_snapshot"],
    }:
        raise SupervisorError("child-outcome receipt payload mismatch")
    ready = by_phase["supervisor-terminal-ready"]["data"]
    if ready != {
        "passed": terminal["passed"],
        "classification": terminal["classification"],
        "child_identity_verified": terminal["child_identity_verified"],
        "child_identity_errors": terminal["child_identity_errors"],
        "success_validation_error": terminal["worker_success_validation_error"],
        "failure_validation_error": terminal["worker_failure_validation_error"],
        "worker_phase_validation_error": terminal["worker_phase_validation_error"],
        "abort": terminal["abort"],
        "cleanup": terminal["cleanup"],
        "late_signals": terminal["late_signals"],
    }:
        raise SupervisorError("terminal-ready receipt payload mismatch")


def validate_new_output_root(output_root: Path) -> Path:
    if not output_root.is_absolute():
        raise SupervisorError("output root must be absolute")
    try:
        canonical_parent = output_root.parent.resolve(strict=True)
    except OSError as error:
        raise SupervisorError(
            f"output parent does not resolve: {output_root.parent}"
        ) from error
    if canonical_parent != output_root.parent or output_root != output_root.resolve(
        strict=False
    ):
        raise SupervisorError(
            "output root and parent must be canonical and symlink-free"
        )
    if output_root.exists() or Path(f"{output_root}.tmp").exists():
        raise SupervisorError(f"refusing existing output root: {output_root}")
    if REPO == output_root or REPO in output_root.parents:
        raise SupervisorError("output root must be outside the lab repository")
    if not canonical_parent.is_dir():
        raise SupervisorError(f"output parent does not exist: {output_root.parent}")
    return canonical_parent


def create_output_root(output_root: Path, canonical_parent: Path) -> None:
    parent_descriptor = os.open(
        canonical_parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    )
    try:
        os.mkdir(output_root.name, mode=0o700, dir_fd=parent_descriptor)
        root_descriptor = os.open(
            output_root.name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_descriptor,
        )
        try:
            descriptor_stat = os.fstat(root_descriptor)
            path_stat = output_root.stat(follow_symlinks=False)
            if (descriptor_stat.st_dev, descriptor_stat.st_ino) != (
                path_stat.st_dev,
                path_stat.st_ino,
            ):
                raise SupervisorError("created output root inode changed")
            os.fsync(root_descriptor)
        finally:
            os.close(root_descriptor)
        os.fsync(parent_descriptor)
    finally:
        os.close(parent_descriptor)
    if output_root.resolve(strict=True) != output_root or output_root.is_symlink():
        raise SupervisorError("created output root is not the canonical directory")


def classify_pending_signals(
    cleanup_exists: bool, pending_signals: list[int], handled_count: int
) -> tuple[int | None, list[int], int]:
    newly_observed = pending_signals[handled_count:]
    if not newly_observed:
        return None, [], handled_count
    if cleanup_exists:
        return None, list(newly_observed), len(pending_signals)
    return newly_observed[0], list(newly_observed[1:]), len(pending_signals)


def consume_blocked_kernel_signals(signal_set: set[signal.Signals]) -> list[int]:
    """Consume, rather than merely observe, signals while they remain blocked."""

    consumed: list[int] = []
    while signal.sigpending() & signal_set:
        info = signal.sigtimedwait(signal_set, 0)
        if info is None:
            break
        consumed.append(int(info.si_signo))
    return consumed


def record_post_cleanup_signals(
    signal_set: set[signal.Signals],
    pending_signals: list[int],
    handled_signal_count: int,
    late_signals: list[int],
) -> int:
    """Drain and record signals observed after cleanup began, without reentry."""

    pending_signals.extend(consume_blocked_kernel_signals(signal_set))
    late_signals.extend(pending_signals[handled_signal_count:])
    return len(pending_signals)


def run_supervised(output_root: Path) -> dict[str, Any]:
    canonical_parent = validate_new_output_root(output_root)
    worker = load_worker_module()
    contract = build_contract(worker, output_root)
    create_output_root(output_root, canonical_parent)
    contract_path = output_root / "contract.json"
    worker.atomic_json(contract_path, contract)
    contract_sha = worker.sha256_file(contract_path)
    supervisor_identity = worker.process_identity()
    chain = worker.ReceiptChain(
        output_root / "supervisor-phases",
        "supervisor",
        contract_path,
        contract_sha,
        supervisor_identity,
    )
    chain.emit(
        "supervisor-start",
        {
            "deadline_seconds": DEADLINE_SECONDS,
            "term_grace_seconds": TERM_GRACE_SECONDS,
            "kill_grace_seconds": KILL_GRACE_SECONDS,
        },
    )
    environment = dict(contract["environment"])
    environment["QWEN38_GPU3_HEALTH_CONTRACT"] = str(contract_path)
    environment["QWEN38_GPU3_HEALTH_CONTRACT_SHA256"] = contract_sha
    command = [str(XPU_PYTHON), str(WORKER), "--contract", str(contract_path)]
    stdout_tmp = output_root / "worker.stdout.log.tmp"
    stderr_tmp = output_root / "worker.stderr.log.tmp"
    started_monotonic = time.monotonic()
    child_returncode: int | None = None
    abort: dict[str, Any] | None = None
    cleanup: dict[str, Any] | None = None
    child_identity_verified = True
    child_identity_errors: list[dict[str, str]] = []
    pending_signals: list[int] = []
    handled_signal_count = 0
    original_signal_handlers: dict[int, Any] = {}

    def signal_wakeup(signum: int, _frame: Any) -> None:
        pending_signals.append(signum)

    def signal_abort(signum: int) -> dict[str, Any]:
        return {
            "kind": "external-interrupt",
            "signal_number": signum,
            "signal_name": signal.Signals(signum).name,
            "exception_type": "ExternalInterrupt",
            "message": f"external signal {signal.Signals(signum).name}",
        }

    def exception_abort(error: BaseException) -> dict[str, Any]:
        return {
            "kind": "supervisor-baseexception",
            "signal_number": None,
            "signal_name": None,
            "exception_type": type(error).__name__,
            "message": str(error),
        }

    def fail_after_unidentified_cleanup(
        proc: subprocess.Popen[bytes], error: ChildIdentityAcquisitionError
    ) -> None:
        state = emergency_cleanup_unidentified_child(
            worker,
            proc,
            chain,
            output_root,
            started_monotonic,
            error.errors,
        )
        for signum, original_handler in original_signal_handlers.items():
            signal.signal(signum, original_handler)
        suffix = "unkillable" if state["unkillable"] else "group-empty"
        raise UnidentifiedChildEmergency(
            f"child identity unavailable; emergency cleanup {suffix}; "
            f"packet={output_root / 'unidentified-child-emergency.json'}"
        ) from error

    for signum in (signal.SIGINT, signal.SIGTERM):
        original_signal_handlers[signum] = signal.signal(signum, signal_wakeup)
    with stdout_tmp.open("xb") as stdout_stream, stderr_tmp.open("xb") as stderr_stream:
        proc: subprocess.Popen[bytes] | None = None
        child_process: dict[str, Any] | None = None
        launch_receipt_phase: str | None = None
        launch_receipt_errors: list[dict[str, str]] = []
        cleanup_reason: str | None = None
        try:
            proc = subprocess.Popen(
                command,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout_stream,
                stderr=stderr_stream,
                start_new_session=True,
            )
            try:
                (
                    child_process,
                    child_identity_verified,
                    child_identity_errors,
                ) = acquire_child_identity(worker, proc.pid)
            except ChildIdentityAcquisitionError as error:
                fail_after_unidentified_cleanup(proc, error)
            if not child_identity_verified:
                (
                    launch_receipt_phase,
                    launch_receipt_errors,
                    _identity_boundary_error,
                ) = emit_unverified_identity_boundary_nonthrowing(
                    chain,
                    command,
                    child_process,
                    child_identity_errors,
                )
                cleanup_reason = "supervisor-baseexception"
                abort = exception_abort(
                    SupervisorError(
                        "canonical child identity failed twice; "
                        "using marked supervisor-local identity only for cleanup"
                    )
                )
                launch_receipt_errors = child_identity_errors + launch_receipt_errors
            else:
                (
                    launch_receipt_phase,
                    launch_receipt_errors,
                    launch_receipt_error,
                ) = emit_launch_boundary_nonthrowing(
                    chain,
                    command,
                    child_process,
                )
                if launch_receipt_error is not None:
                    cleanup_reason = "supervisor-baseexception"
                    abort = exception_abort(launch_receipt_error)
                else:
                    child_returncode = wait_until(
                        proc,
                        started_monotonic + DEADLINE_SECONDS,
                        pending_signals,
                        worker=worker,
                        process_group=child_process,
                    )
                    if child_returncode is None:
                        cleanup_reason = "timeout"
                    elif pending_signals:
                        cleanup_reason = "external-interrupt"
                        abort = signal_abort(pending_signals[0])
                        handled_signal_count = 1
        except UnidentifiedChildEmergency:
            raise
        except BaseException as error:
            if proc is None:
                raise
            if child_process is None:
                try:
                    (
                        child_process,
                        child_identity_verified,
                        child_identity_errors,
                    ) = acquire_child_identity(worker, proc.pid)
                except ChildIdentityAcquisitionError as identity_error:
                    fail_after_unidentified_cleanup(proc, identity_error)
            if launch_receipt_phase is None and not launch_receipt_errors:
                if child_identity_verified:
                    (
                        launch_receipt_phase,
                        launch_receipt_errors,
                        _launch_receipt_error,
                    ) = emit_launch_boundary_nonthrowing(
                        chain,
                        command,
                        child_process,
                    )
                else:
                    (
                        launch_receipt_phase,
                        launch_receipt_errors,
                        _identity_boundary_error,
                    ) = emit_unverified_identity_boundary_nonthrowing(
                        chain,
                        command,
                        child_process,
                        child_identity_errors,
                    )
                    launch_receipt_errors = (
                        child_identity_errors + launch_receipt_errors
                    )
            if isinstance(error, ExternalInterrupt):
                cleanup_reason = "external-interrupt"
                abort = signal_abort(error.signum)
                handled_signal_count = 1 if pending_signals else 0
            else:
                cleanup_reason = "supervisor-baseexception"
                abort = exception_abort(error)
        if proc is None or child_process is None:
            raise SupervisorError("worker process was not durably identified")
        if cleanup_reason is not None:
            cleanup = cleanup_process_group(
                worker,
                proc,
                child_process,
                chain,
                output_root,
                started_monotonic,
                cleanup_reason,
                abort,
                launch_receipt_phase=launch_receipt_phase,
                initial_errors=launch_receipt_errors,
                group_fn=(
                    process_group_members
                    if child_identity_verified
                    else supervisor_local_process_group_members
                ),
                identity_fn=(
                    None
                    if child_identity_verified
                    else lambda pid: supervisor_local_process_identity(worker, pid)
                ),
            )
            child_returncode = cleanup["child_returncode"]
            if not child_identity_verified and cleanup["unkillable"]:
                emergency_state = emergency_cleanup_unidentified_child(
                    worker,
                    proc,
                    chain,
                    output_root,
                    started_monotonic,
                    child_identity_errors + cleanup["errors"],
                )
                for signum, original_handler in original_signal_handlers.items():
                    signal.signal(signum, original_handler)
                suffix = (
                    "unkillable" if emergency_state["unkillable"] else "group-empty"
                )
                raise UnidentifiedChildEmergency(
                    "supervisor-local identity cleanup lost verification; "
                    f"emergency cleanup {suffix}; "
                    f"packet={output_root / 'unidentified-child-emergency.json'}"
                )
        stdout_stream.flush()
        stderr_stream.flush()
        os.fsync(stdout_stream.fileno())
        os.fsync(stderr_stream.fileno())

    late_signals: list[int] = []

    def consume_pending_signal() -> None:
        nonlocal abort, child_returncode, cleanup, handled_signal_count
        action, late, new_handled_count = classify_pending_signals(
            cleanup is not None, pending_signals, handled_signal_count
        )
        if action is None and not late:
            return
        if action is not None:
            abort = signal_abort(action)
            cleanup = cleanup_process_group(
                worker,
                proc,
                child_process,
                chain,
                output_root,
                started_monotonic,
                "external-interrupt",
                abort,
                launch_receipt_phase=launch_receipt_phase,
            )
            child_returncode = cleanup["child_returncode"]
        late_signals.extend(late)
        handled_signal_count = new_handled_count

    consume_pending_signal()
    if child_returncode is not None:
        stdout_record = finalize_log(
            worker, stdout_tmp, output_root / "worker.stdout.log"
        )
        stderr_record = finalize_log(
            worker, stderr_tmp, output_root / "worker.stderr.log"
        )
    else:
        stdout_record = temporary_log_observation(worker, stdout_tmp)
        stderr_record = temporary_log_observation(worker, stderr_tmp)
    consume_pending_signal()

    worker_success: dict[str, Any] | None = None
    success_error: str | None = None
    if child_returncode == 0 and cleanup is None:
        try:
            worker_success = validate_worker_success(
                worker, output_root, contract_path, contract_sha, child_process
            )
        except Exception as error:
            success_error = f"{type(error).__name__}: {error}"
    worker_failure: dict[str, Any] | None = None
    worker_failure_error: str | None = None
    try:
        worker_failure = validate_worker_failure(
            worker, output_root, contract_path, contract_sha, child_process
        )
    except Exception as error:
        worker_failure_error = f"{type(error).__name__}: {error}"
    worker_phase_error: str | None = None
    unkillable = cleanup is not None and cleanup["unkillable"] is True
    try:
        if unkillable:
            worker_receipts = receipt_snapshot(worker, output_root / "worker-phases")
            validate_snapshot_entries(
                worker,
                worker_receipts,
                output_root,
                "worker_phase_snapshot",
                require_current=False,
            )
            validate_worker_receipt_snapshot(
                worker,
                worker_receipts,
                contract_path,
                contract_sha,
                child_process,
            )
        else:
            worker_receipts = validate_worker_partial_chain(
                worker, output_root, contract_path, contract_sha, child_process
            )
    except Exception as error:
        worker_phase_error = f"{type(error).__name__}: {error}"
        worker_receipts = receipt_snapshot(worker, output_root / "worker-phases")
    consume_pending_signal()
    if cleanup is not None:
        worker_success = None
        success_error = None

    signal_set = {signal.SIGINT, signal.SIGTERM}
    while True:
        previous_signal_mask = signal.pthread_sigmask(signal.SIG_BLOCK, signal_set)
        pending_signals.extend(consume_blocked_kernel_signals(signal_set))
        if pending_signals[handled_signal_count:] and cleanup is None:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_signal_mask)
            consume_pending_signal()
            worker_success = None
            success_error = None
            continue
        newly_observed = pending_signals[handled_signal_count:]
        if newly_observed:
            late_signals.extend(newly_observed)
            handled_signal_count = len(pending_signals)
        break

    if cleanup is None:
        try:
            final_process_group_snapshot = process_group_members(worker, child_process)
        except BaseException as error:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_signal_mask)
            abort = exception_abort(error)
            cleanup = cleanup_process_group(
                worker,
                proc,
                child_process,
                chain,
                output_root,
                started_monotonic,
                "supervisor-baseexception",
                abort,
                launch_receipt_phase=launch_receipt_phase,
            )
            child_returncode = cleanup["child_returncode"]
            previous_signal_mask = signal.pthread_sigmask(signal.SIG_BLOCK, signal_set)
        else:
            if final_process_group_snapshot:
                signal.pthread_sigmask(signal.SIG_SETMASK, previous_signal_mask)
                error = SupervisorError(
                    "process group remained after ordinary worker completion"
                )
                abort = exception_abort(error)
                cleanup = cleanup_process_group(
                    worker,
                    proc,
                    child_process,
                    chain,
                    output_root,
                    started_monotonic,
                    "supervisor-baseexception",
                    abort,
                    launch_receipt_phase=launch_receipt_phase,
                )
                child_returncode = cleanup["child_returncode"]
                previous_signal_mask = signal.pthread_sigmask(
                    signal.SIG_BLOCK, signal_set
                )

    pending_signals.extend(consume_blocked_kernel_signals(signal_set))
    if pending_signals[handled_signal_count:] and cleanup is None:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_signal_mask)
        consume_pending_signal()
        worker_success = None
        success_error = None
        previous_signal_mask = signal.pthread_sigmask(signal.SIG_BLOCK, signal_set)
    elif pending_signals[handled_signal_count:]:
        late_signals.extend(pending_signals[handled_signal_count:])
        handled_signal_count = len(pending_signals)

    # A signal that triggers cleanup above is consumed before cleanup begins, but
    # the mask is deliberately open while cleanup runs.  Reblock, drain any signal
    # that raced with that cleanup, and classify every such signal as late evidence
    # without re-entering the cleanup state machine.
    if cleanup is not None:
        handled_signal_count = record_post_cleanup_signals(
            signal_set,
            pending_signals,
            handled_signal_count,
            late_signals,
        )

    timed_out = cleanup is not None and cleanup["reason"] == "timeout"
    sigterm_sent = cleanup is not None and cleanup["sigterm_sent"] is True
    sigkill_sent = cleanup is not None and cleanup["sigkill_sent"] is True
    unkillable = cleanup is not None and cleanup["unkillable"] is True
    final_process_group_snapshot = (
        cleanup["final_process_group_snapshot"] if cleanup is not None else []
    )
    passed = (
        child_returncode == 0
        and child_identity_verified
        and cleanup is None
        and worker_success is not None
        and worker_failure is None
        and worker_failure_error is None
        and worker_phase_error is None
    )
    if passed:
        classification = "gpu3-incumbent-control-health-pass"
    elif not child_identity_verified:
        classification = (
            "gpu3-incumbent-control-child-identity-unavailable-unkillable"
            if unkillable
            else "gpu3-incumbent-control-child-identity-unavailable-terminated"
        )
    elif abort is not None and abort["kind"] == "external-interrupt":
        classification = (
            "gpu3-incumbent-control-supervisor-interrupt-unkillable"
            if unkillable
            else "gpu3-incumbent-control-supervisor-interrupt-terminated"
        )
    elif abort is not None:
        classification = (
            "gpu3-incumbent-control-supervisor-abort-unkillable"
            if unkillable
            else "gpu3-incumbent-control-supervisor-abort-terminated"
        )
    elif unkillable:
        classification = "gpu3-incumbent-control-timeout-unkillable"
    elif timed_out:
        classification = "gpu3-incumbent-control-timeout-terminated"
    elif child_returncode == 0:
        classification = "gpu3-incumbent-control-invalid-success-packet"
    else:
        classification = "gpu3-incumbent-control-worker-failure"
    chain.emit(
        "child-outcome",
        {
            "child_process": child_process,
            "child_identity_verified": child_identity_verified,
            "child_identity_errors": child_identity_errors,
            "returncode": child_returncode,
            "timed_out": timed_out,
            "sigterm_sent": sigterm_sent,
            "sigkill_sent": sigkill_sent,
            "unkillable": unkillable,
            "abort": abort,
            "cleanup": cleanup,
            "late_signals": late_signals,
            "final_process_group_snapshot": final_process_group_snapshot,
        },
    )
    chain.emit(
        "supervisor-terminal-ready",
        {
            "passed": passed,
            "classification": classification,
            "child_identity_verified": child_identity_verified,
            "child_identity_errors": child_identity_errors,
            "success_validation_error": success_error,
            "failure_validation_error": worker_failure_error,
            "worker_phase_validation_error": worker_phase_error,
            "abort": abort,
            "cleanup": cleanup,
            "late_signals": late_signals,
        },
    )
    supervisor_receipts = worker.validate_receipt_chain(
        chain.directory, "supervisor", contract_path, contract_sha
    )
    terminal = {
        "schema": SCHEMA_TERMINAL,
        "passed": passed,
        "classification": classification,
        "contract_path": str(contract_path),
        "contract_sha256": contract_sha,
        "supervisor_process": supervisor_identity,
        "child_process": child_process,
        "child_identity_verified": child_identity_verified,
        "child_identity_errors": child_identity_errors,
        "child_returncode": child_returncode,
        "final_process_group_snapshot": final_process_group_snapshot,
        "deadline": contract["deadline"],
        "timed_out": timed_out,
        "sigterm_sent": sigterm_sent,
        "sigkill_sent": sigkill_sent,
        "unkillable": unkillable,
        "abort": abort,
        "cleanup": cleanup,
        "late_signals": late_signals,
        "stdout": stdout_record,
        "stderr": stderr_record,
        "worker_success": worker_success,
        "worker_success_validation_error": success_error,
        "worker_failure": worker_failure,
        "worker_failure_validation_error": worker_failure_error,
        "worker_phase_validation_error": worker_phase_error,
        "supervisor_phase_receipts": supervisor_receipts,
        "worker_phase_snapshot": worker_receipts,
        "output_inventory_before_terminal": output_inventory(worker, output_root),
        "decision": {
            "original_q64_r2_root_append_authorized": False,
            "carry_gpu2_evidence_forward": False,
            "candidate_or_model_run_authorized": False,
            "fresh_full_operator_campaign_may_be_preregistered": passed,
        },
    }
    try:
        worker.atomic_json(output_root / "terminal.json", terminal)
    finally:
        for signum, original_handler in original_signal_handlers.items():
            signal.signal(signum, original_handler)
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_signal_mask)
    return terminal


def validate_terminal(output_root: Path) -> dict[str, Any]:
    worker = load_worker_module()
    terminal_path = output_root / "terminal.json"
    contract_path = output_root / "contract.json"
    if not terminal_path.is_file() or terminal_path.stat().st_mode & 0o222:
        raise SupervisorError("terminal packet missing or writable")
    terminal = worker.load_json(terminal_path)
    contract = worker.load_json(contract_path)
    if not isinstance(terminal, dict) or not isinstance(contract, dict):
        raise SupervisorError("terminal/contract must be objects")
    contract_sha = worker.sha256_file(contract_path)
    worker.require_exact_keys(
        terminal,
        (
            "schema",
            "passed",
            "classification",
            "contract_path",
            "contract_sha256",
            "supervisor_process",
            "child_process",
            "child_identity_verified",
            "child_identity_errors",
            "child_returncode",
            "final_process_group_snapshot",
            "deadline",
            "timed_out",
            "sigterm_sent",
            "sigkill_sent",
            "unkillable",
            "abort",
            "cleanup",
            "late_signals",
            "stdout",
            "stderr",
            "worker_success",
            "worker_success_validation_error",
            "worker_failure",
            "worker_failure_validation_error",
            "worker_phase_validation_error",
            "supervisor_phase_receipts",
            "worker_phase_snapshot",
            "output_inventory_before_terminal",
            "decision",
        ),
        str(terminal_path),
    )
    if (
        terminal.get("schema") != SCHEMA_TERMINAL
        or terminal.get("contract_path") != str(contract_path)
        or terminal.get("contract_sha256") != contract_sha
        or contract.get("output_root") != str(output_root)
    ):
        raise SupervisorError("terminal/contract binding mismatch")
    if contract_path.stat().st_mode & 0o222:
        raise SupervisorError("contract is writable")
    worker.validate_contract(
        contract, contract_path, contract_sha, check_environment=False
    )
    supervisor_receipts = worker.validate_receipt_chain(
        output_root / "supervisor-phases",
        "supervisor",
        contract_path,
        contract_sha,
    )
    if terminal["supervisor_phase_receipts"] != supervisor_receipts:
        raise SupervisorError("terminal supervisor receipt inventory mismatch")
    validate_process_identity(
        worker, terminal["supervisor_process"], "terminal.supervisor_process"
    )
    validate_process_identity(
        worker, terminal["child_process"], "terminal.child_process", group_leader=True
    )
    if (
        terminal["child_process"]["boot_id"]
        != terminal["supervisor_process"]["boot_id"]
    ):
        raise SupervisorError("supervisor and child boot IDs differ")
    identity_verified = terminal["child_identity_verified"]
    identity_errors = terminal["child_identity_errors"]
    if not isinstance(identity_verified, bool) or not isinstance(identity_errors, list):
        raise SupervisorError("terminal child identity provenance is malformed")
    for index, item in enumerate(identity_errors):
        if not isinstance(item, dict):
            raise SupervisorError("terminal child identity error is not an object")
        worker.require_exact_keys(
            item,
            ("operation", "exception_type", "message"),
            f"terminal.child_identity_errors[{index}]",
        )
        if (
            item["operation"] != f"worker-process-identity-attempt-{index + 1}"
            or not isinstance(item["exception_type"], str)
            or not isinstance(item["message"], str)
        ):
            raise SupervisorError("terminal child identity error differs")
    if identity_verified:
        if len(identity_errors) > 1:
            raise SupervisorError("verified child carries two failed identity attempts")
    elif len(identity_errors) != 2:
        raise SupervisorError("unverified child lacks two identity-read failures")
    final_group = validate_process_group_snapshot(
        worker,
        terminal["final_process_group_snapshot"],
        terminal["child_process"],
        "terminal.final_process_group_snapshot",
    )
    first_supervisor_receipt = worker.load_json(Path(supervisor_receipts[0]["path"]))
    launch_receipts = [
        worker.load_json(Path(item["path"]))
        for item in supervisor_receipts
        if item["phase"] in LAUNCH_PHASES
    ]
    if terminal["supervisor_process"] != first_supervisor_receipt["process"]:
        raise SupervisorError("terminal process identities do not bind receipts")
    validate_snapshot_entries(
        worker,
        terminal["worker_phase_snapshot"],
        output_root,
        "terminal.worker_phase_snapshot",
        require_current=not terminal["unkillable"],
    )
    validate_snapshot_entries(
        worker,
        terminal["output_inventory_before_terminal"],
        output_root,
        "terminal.output_inventory_before_terminal",
        require_current=not terminal["unkillable"],
    )
    if not terminal["unkillable"]:
        if terminal["worker_phase_snapshot"] != receipt_snapshot(
            worker, output_root / "worker-phases"
        ):
            raise SupervisorError("terminal worker phase snapshot changed")
        if terminal["output_inventory_before_terminal"] != output_inventory(
            worker, output_root
        ):
            raise SupervisorError("terminal output inventory changed")
    worker_phase_error = terminal["worker_phase_validation_error"]
    if worker_phase_error is not None and (
        not isinstance(worker_phase_error, str) or not worker_phase_error
    ):
        raise SupervisorError("worker phase validation error is malformed")
    try:
        if terminal["unkillable"]:
            validate_worker_receipt_snapshot(
                worker,
                terminal["worker_phase_snapshot"],
                contract_path,
                contract_sha,
                terminal["child_process"],
            )
        else:
            current_worker_snapshot = validate_worker_partial_chain(
                worker,
                output_root,
                contract_path,
                contract_sha,
                terminal["child_process"],
            )
            if current_worker_snapshot != terminal["worker_phase_snapshot"]:
                raise SupervisorError("worker phase snapshot differs")
    except Exception as error:
        current_worker_phase_error = f"{type(error).__name__}: {error}"
    else:
        current_worker_phase_error = None
    if current_worker_phase_error != worker_phase_error:
        raise SupervisorError("worker phase validation error does not rederive")
    expected_decision = {
        "original_q64_r2_root_append_authorized": False,
        "carry_gpu2_evidence_forward": False,
        "candidate_or_model_run_authorized": False,
        "fresh_full_operator_campaign_may_be_preregistered": terminal["passed"],
    }
    if terminal["decision"] != expected_decision:
        raise SupervisorError("terminal decision contract mismatch")
    timed_out = terminal["timed_out"]
    unkillable = terminal["unkillable"]
    returncode = terminal["child_returncode"]
    abort = terminal["abort"]
    cleanup = terminal["cleanup"]
    late_signals = terminal["late_signals"]
    if not all(
        isinstance(terminal[name], bool)
        for name in (
            "passed",
            "timed_out",
            "sigterm_sent",
            "sigkill_sent",
            "unkillable",
        )
    ):
        raise SupervisorError("terminal status fields must be booleans")
    if returncode is not None:
        worker.require_int(returncode, "terminal child returncode")
    if terminal["deadline"] != contract["deadline"]:
        raise SupervisorError("terminal deadline differs from contract")
    if not isinstance(late_signals, list):
        raise SupervisorError("terminal late_signals is not an array")
    for index, signum in enumerate(late_signals):
        value = worker.require_int(signum, f"terminal.late_signals[{index}]")
        if value not in (signal.SIGINT, signal.SIGTERM):
            raise SupervisorError("terminal late signal is unsupported")
    if abort is not None:
        if not isinstance(abort, dict):
            raise SupervisorError("terminal abort is not an object")
        worker.require_exact_keys(
            abort,
            ("kind", "signal_number", "signal_name", "exception_type", "message"),
            "terminal.abort",
        )
        if abort["kind"] == "external-interrupt":
            signum = worker.require_int(abort["signal_number"], "abort.signal_number")
            if (
                signum not in (signal.SIGINT, signal.SIGTERM)
                or abort["signal_name"] != signal.Signals(signum).name
            ):
                raise SupervisorError("terminal external interrupt signal differs")
        elif abort["kind"] == "supervisor-baseexception":
            if abort["signal_number"] is not None or abort["signal_name"] is not None:
                raise SupervisorError("supervisor BaseException carries a signal")
        else:
            raise SupervisorError("terminal abort kind is unknown")
        if not isinstance(abort["exception_type"], str) or not isinstance(
            abort["message"], str
        ):
            raise SupervisorError("terminal abort exception metadata is malformed")
        if timed_out:
            raise SupervisorError(
                "terminal cannot be both timeout and supervisor abort"
            )
    if cleanup is None:
        if (
            timed_out
            or abort is not None
            or late_signals
            or final_group
            or any(
                terminal[name]
                for name in ("sigterm_sent", "sigkill_sent", "unkillable")
            )
        ):
            raise SupervisorError("ordinary terminal carries cleanup state")
    else:
        validate_cleanup_state(
            worker,
            cleanup,
            terminal["child_process"],
            "terminal.cleanup",
            contract_path=contract_path,
            contract_sha=contract_sha,
        )
        if (
            cleanup["child_returncode"] != returncode
            or cleanup["final_process_group_snapshot"] != final_group
            or cleanup["unkillable"] is not unkillable
            or cleanup["sigterm_sent"] is not terminal["sigterm_sent"]
            or cleanup["sigkill_sent"] is not terminal["sigkill_sent"]
            or timed_out is not (cleanup["reason"] == "timeout")
        ):
            raise SupervisorError("terminal cleanup summary differs")
        if cleanup["reason"] == "timeout":
            if abort is not None:
                raise SupervisorError("timeout cleanup carries an abort")
        elif (
            abort is None
            or (
                cleanup["reason"] == "external-interrupt"
                and abort["kind"] != "external-interrupt"
            )
            or (
                cleanup["reason"] == "supervisor-baseexception"
                and abort["kind"] != "supervisor-baseexception"
            )
        ):
            raise SupervisorError("cleanup reason and abort differ")
    if terminal["passed"]:
        expected_classification = "gpu3-incumbent-control-health-pass"
    elif not identity_verified:
        expected_classification = (
            "gpu3-incumbent-control-child-identity-unavailable-unkillable"
            if unkillable
            else "gpu3-incumbent-control-child-identity-unavailable-terminated"
        )
    elif abort is not None and abort["kind"] == "external-interrupt":
        expected_classification = (
            "gpu3-incumbent-control-supervisor-interrupt-unkillable"
            if unkillable
            else "gpu3-incumbent-control-supervisor-interrupt-terminated"
        )
    elif abort is not None:
        expected_classification = (
            "gpu3-incumbent-control-supervisor-abort-unkillable"
            if unkillable
            else "gpu3-incumbent-control-supervisor-abort-terminated"
        )
    elif unkillable:
        expected_classification = "gpu3-incumbent-control-timeout-unkillable"
    elif timed_out:
        expected_classification = "gpu3-incumbent-control-timeout-terminated"
    elif returncode == 0:
        expected_classification = "gpu3-incumbent-control-invalid-success-packet"
    else:
        expected_classification = "gpu3-incumbent-control-worker-failure"
    if terminal["classification"] != expected_classification:
        raise SupervisorError("terminal classification does not rederive")
    if not identity_verified and (
        cleanup is None
        or cleanup["reason"] != "supervisor-baseexception"
        or cleanup["launch_receipt_phase"] not in (None, "child-identity-unavailable")
        or cleanup["errors"][:2] != identity_errors
    ):
        raise SupervisorError("unverified child is not bound to identity cleanup")
    phases = [item["phase"] for item in supervisor_receipts]
    expected_phases = ["supervisor-start"]
    launch_phase = (
        cleanup["launch_receipt_phase"] if cleanup is not None else "child-launched"
    )
    if launch_phase is not None:
        expected_phases.append(launch_phase)
        if (
            len(launch_receipts) != 1
            or launch_receipts[0]["phase"] != launch_phase
            or terminal["child_process"]
            != launch_receipts[0]["data"].get("child_process")
        ):
            raise SupervisorError("supervisor launch receipt phase differs")
    elif launch_receipts:
        raise SupervisorError("supervisor has an unexpected launch receipt")
    if cleanup is not None:
        expected_phases.extend(cleanup["receipts_persisted"])
    expected_phases.extend(["child-outcome", "supervisor-terminal-ready"])
    if phases != expected_phases:
        raise SupervisorError("supervisor phase sequence mismatch")
    validate_supervisor_receipt_payloads(
        worker, supervisor_receipts, terminal, contract, output_root
    )
    for name in ("stdout", "stderr"):
        record = terminal[name]
        if not isinstance(record, dict):
            raise SupervisorError(f"terminal {name} record is not an object")
        if record.get("immutable") is True:
            worker.require_exact_keys(
                record,
                ("path", "sha256", "size_bytes", "mode", "immutable"),
                f"terminal.{name}",
            )
            log_path = Path(record["path"])
            if (
                log_path != output_root / f"worker.{name}.log"
                or not log_path.is_file()
                or log_path.resolve(strict=True) != log_path
                or log_path.stat().st_mode & 0o222
                or log_path.stat().st_mode & 0o777 != 0o444
                or worker.sha256_file(log_path) != record["sha256"]
                or log_path.stat().st_size != record["size_bytes"]
                or record["mode"] != "0444"
            ):
                raise SupervisorError(f"terminal {name} immutable log changed")
        elif record.get("immutable") is not False or not unkillable:
            raise SupervisorError(f"terminal {name} mutable log is not unkillable")
        else:
            worker.require_exact_keys(
                record,
                (
                    "path",
                    "sha256_at_terminal",
                    "size_bytes_at_terminal",
                    "mode_at_terminal",
                    "immutable",
                ),
                f"terminal.{name}",
            )
            log_path = Path(record["path"])
            if (
                log_path != output_root / f"worker.{name}.log.tmp"
                or not log_path.is_file()
                or log_path.resolve(strict=True) != log_path
                or not isinstance(record["sha256_at_terminal"], str)
                or re.fullmatch(r"[0-9a-f]{64}", record["sha256_at_terminal"]) is None
                or worker.require_int(
                    record["size_bytes_at_terminal"], f"terminal.{name}.size"
                )
                < 0
                or record["mode_at_terminal"] != "0644"
            ):
                raise SupervisorError(f"terminal {name} mutable log metadata differs")
    failure_record = terminal["worker_failure"]
    if failure_record is not None:
        if not isinstance(failure_record, dict):
            raise SupervisorError("terminal worker failure record is not an object")
        worker.require_exact_keys(
            failure_record, ("path", "sha256"), "terminal.worker_failure"
        )
        current_failure = validate_worker_failure(
            worker, output_root, contract_path, contract_sha, terminal["child_process"]
        )
        if current_failure != failure_record:
            raise SupervisorError("terminal worker failure packet changed")
    elif (
        terminal["worker_failure_validation_error"] is None
        and (output_root / "worker-failure.json").exists()
    ):
        raise SupervisorError("terminal omitted an extant worker failure packet")
    if terminal["worker_failure_validation_error"] is not None and (
        not isinstance(terminal["worker_failure_validation_error"], str)
        or not terminal["worker_failure_validation_error"]
    ):
        raise SupervisorError("worker failure validation error is malformed")
    if terminal["worker_failure_validation_error"] is not None:
        try:
            validate_worker_failure(
                worker,
                output_root,
                contract_path,
                contract_sha,
                terminal["child_process"],
            )
        except Exception as error:
            current_failure_error = f"{type(error).__name__}: {error}"
        else:
            current_failure_error = None
        if current_failure_error != terminal["worker_failure_validation_error"]:
            raise SupervisorError("worker failure validation error does not rederive")
    success_validation_error = terminal["worker_success_validation_error"]
    if success_validation_error is not None and (
        not isinstance(success_validation_error, str) or not success_validation_error
    ):
        raise SupervisorError("worker success validation error is malformed")
    if returncode != 0 or timed_out or abort is not None:
        if success_validation_error is not None:
            raise SupervisorError("ineligible run carries success validation error")
    elif terminal["worker_success"] is None:
        try:
            validate_worker_success(
                worker,
                output_root,
                contract_path,
                contract_sha,
                terminal["child_process"],
            )
        except Exception as error:
            current_success_error = f"{type(error).__name__}: {error}"
        else:
            current_success_error = None
        if current_success_error != success_validation_error:
            raise SupervisorError("worker success validation error does not rederive")
    if terminal.get("passed") is True:
        success_record = validate_worker_success(
            worker,
            output_root,
            contract_path,
            contract_sha,
            terminal["child_process"],
        )
        if terminal["worker_success"] != success_record:
            raise SupervisorError("terminal worker success summary mismatch")
        if (
            terminal.get("timed_out") is not False
            or identity_verified is not True
            or terminal.get("unkillable") is not False
            or terminal.get("abort") is not None
            or terminal.get("cleanup") is not None
            or terminal.get("late_signals") != []
            or terminal.get("child_returncode") != 0
            or terminal.get("worker_success_validation_error") is not None
            or terminal.get("worker_failure") is not None
            or terminal.get("worker_failure_validation_error") is not None
            or terminal.get("classification") != "gpu3-incumbent-control-health-pass"
        ):
            raise SupervisorError("passing terminal has contradictory status")
    elif terminal["worker_success"] is not None:
        raise SupervisorError("failed terminal carries a validated worker success")
    return terminal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("output_root")
    validate = subparsers.add_parser("validate")
    validate.add_argument("output_root")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        output_root = Path(args.output_root)
        if args.command == "run":
            terminal = run_supervised(output_root)
        else:
            terminal = validate_terminal(output_root)
        print(
            json.dumps(
                {
                    "passed": terminal["passed"],
                    "classification": terminal["classification"],
                    "terminal": str(output_root / "terminal.json"),
                },
                sort_keys=True,
            )
        )
        return 0 if terminal["passed"] else 14
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as error:
        print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
