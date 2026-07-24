#!/usr/bin/env python3
"""One-shot, sequential four-card coordinator for Phase A.

The coordinator owns the only capability issuer.  A child cannot start from a
packet path alone: it must consume the rank-specific pipe descriptor inherited
from this process.  No retry, second capability, or replacement card root is
available after any terminal state.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import fcntl
import hashlib
import json
import os
import secrets
import signal
import socket
import stat
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any

TIMEOUT_SECONDS = 1800
LIVE_IDLE_SECONDS = 65
TERMINAL_FORMAT = "laguna-m8-gather-sharded-phase-a-campaign-terminal-v3"
F_ADD_SEALS = getattr(fcntl, "F_ADD_SEALS", 1033)
F_GET_SEALS = getattr(fcntl, "F_GET_SEALS", 1034)
REQUIRED_SEALS = (getattr(fcntl, "F_SEAL_SEAL", 1) | getattr(fcntl, "F_SEAL_SHRINK", 2) |
                  getattr(fcntl, "F_SEAL_GROW", 4) | getattr(fcntl, "F_SEAL_WRITE", 8))
phase_a: Any = None
analyzer: Any = None
operational: Any = None
_SEALED_SELF_FD: int | None = None


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _read_source(path: Path, expected_sha256: str) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        require(before.st_size <= 8 * 1024 * 1024, "tool source too large")
        raw = os.pread(descriptor, before.st_size, 0)
        after = os.fstat(descriptor)
        require(len(raw) == before.st_size and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "tool source changed")
        require(hashlib.sha256(raw).hexdigest() == expected_sha256, "tool source SHA-256 drift")
        return raw
    finally:
        os.close(descriptor)


def _sealed_source(raw: bytes, name: str) -> int:
    create = getattr(os, "memfd_create", None)
    if callable(create):
        descriptor = create(name, getattr(os, "MFD_CLOEXEC", 1) | getattr(os, "MFD_ALLOW_SEALING", 2))
    else:
        libc = ctypes.CDLL(None, use_errno=True)
        descriptor = int(libc.memfd_create(name.encode(), 1 | 2))
        if descriptor < 0:
            raise OSError(ctypes.get_errno(), "memfd_create failed")
    offset = 0
    while offset < len(raw):
        offset += os.write(descriptor, raw[offset:])
    os.lseek(descriptor, 0, os.SEEK_SET)
    fcntl.fcntl(descriptor, F_ADD_SEALS, REQUIRED_SEALS)
    require(fcntl.fcntl(descriptor, F_GET_SEALS) & REQUIRED_SEALS == REQUIRED_SEALS, "source memfd sealing failed")
    return descriptor


def _load_module(name: str, identity: dict[str, str]) -> Any:
    raw = _read_source(Path(identity["path"]), identity["sha256"])
    descriptor = _sealed_source(raw, f"laguna-phase-a-{name}")
    try:
        module = types.ModuleType(name)
        module.__file__ = f"/proc/self/fd/{descriptor}"
        sys.modules[name] = module
        exec(compile(raw, identity["path"], "exec"), module.__dict__)
        return module
    finally:
        os.close(descriptor)


def _bootstrap_packet(path: Path, expected_sha256: str) -> dict[str, Any]:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(descriptor)
        raw = os.pread(descriptor, metadata.st_size, 0)
    finally:
        os.close(descriptor)
    value = json.loads(raw)
    require(isinstance(value, dict) and raw == _canonical(value) and hashlib.sha256(raw).hexdigest() == expected_sha256,
            "bootstrap packet identity")
    return value


def _bootstrap_modules(packet: dict[str, Any]) -> None:
    global phase_a, analyzer, operational
    body = packet["body"]
    phase_a = _load_module("run_laguna_m8_gather_sharded_phase_a", body["runner"])
    analyzer = _load_module("analyze_laguna_m8_gather_sharded_phase_a", body["analyzer"])
    # The operational helper identity is bound by the mutually-authorized B
    # packet, not discovered from PYTHONPATH.
    b_path = Path(body["phase_b_reference"]["authorization_path"])
    b_fd = os.open(b_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        b_meta = os.fstat(b_fd)
        b_raw = os.pread(b_fd, b_meta.st_size, 0)
    finally:
        os.close(b_fd)
    b_packet = json.loads(b_raw)
    require(b_raw == _canonical(b_packet) and hashlib.sha256(b_raw).hexdigest() == packet["paired_phase_b_packet_sha256"],
            "bootstrap Phase-B packet identity")
    operational = _load_module("preflight_laguna_m8_gather_sharded_operational", b_packet["body"]["tools"]["operational_preflight"])


def _ensure_sealed_self(packet: dict[str, Any], packet_path: Path, expected_sha256: str,
                        sealed_self_fd: int | None) -> None:
    identity = packet["body"]["coordinator"]
    if sealed_self_fd is not None:
        require(Path(__file__).as_posix() == f"/proc/self/fd/{sealed_self_fd}", "coordinator not running from sealed source")
        raw = os.pread(sealed_self_fd, os.fstat(sealed_self_fd).st_size, 0)
        require(hashlib.sha256(raw).hexdigest() == identity["sha256"] and fcntl.fcntl(sealed_self_fd, F_GET_SEALS) & REQUIRED_SEALS == REQUIRED_SEALS,
                "sealed coordinator source drift")
        return
    raw = _read_source(Path(identity["path"]), identity["sha256"])
    descriptor = _sealed_source(raw, "laguna-phase-a-coordinator")
    os.set_inheritable(descriptor, True)
    python = packet["body"]["common"]["runtime_identity"]["observed_identity"]["python_executable"]
    argv = [python, "-I", "-S", f"/proc/self/fd/{descriptor}", "--sealed-self-fd", str(descriptor),
            "--authorization-json", str(packet_path), "--expected-authorization-sha256", expected_sha256]
    os.execve(python, argv, {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})


def _write_at(directory_fd: int, name: str, value: dict[str, Any]) -> str:
    return _raw_at(directory_fd, name, phase_a.canonical_json(value))


def _raw_at(directory_fd: int, name: str, value: bytes) -> str:
    require(name and "/" not in name and name not in {".", ".."}, "unsafe evidence name")
    descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400,
                         dir_fd=directory_fd)
    try:
        position = 0
        while position < len(value):
            written = os.write(descriptor, value[position:])
            require(written > 0, "short raw log write")
            position += written
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o444)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(directory_fd)
    return hashlib.sha256(value).hexdigest()


def _validate_idle_snapshot(value: object) -> dict[str, Any]:
    """Revalidate every self-observer field before a one-shot campaign."""
    required = {"format", "status", "observed_utc", "argv", "environment", "timeout_seconds", "xpu_smi", "child_identity", "raw_capture", "idle"}
    require(isinstance(value, dict) and set(value) == required and value["format"] == operational.FORMAT and value["status"] == "passed", "idle observer schema")
    require(value["argv"] == ["/usr/bin/xpu-smi", "ps", "-j"] and value["environment"] == operational.OBSERVER_ENVIRONMENT and value["timeout_seconds"] == 20.0, "idle observer invocation")
    xpu = value["xpu_smi"]
    require(isinstance(xpu, dict) and set(xpu) == {"configured_path", "resolved_path", "sha256", "device", "inode"} and xpu["configured_path"] == "/usr/bin/xpu-smi" and xpu["resolved_path"] == "/usr/bin/xpu-smi" and xpu["sha256"] == operational.EXPECTED_XPU_SMI_SHA256 and _positive_int(xpu["device"]) and _positive_int(xpu["inode"]), "idle observer identity")
    child = value["child_identity"]
    require(isinstance(child, dict) and set(child) == {"process_id", "proc_dir_fd_acquired", "pidfd_acquired", "proc_exe_resolved", "executable_device", "executable_inode"} and _positive_int(child["process_id"]) and child["proc_dir_fd_acquired"] is True and isinstance(child["pidfd_acquired"], bool) and child["proc_exe_resolved"] == "/usr/bin/xpu-smi" and child["executable_device"] == xpu["device"] and child["executable_inode"] == xpu["inode"], "idle observer child identity")
    capture = value["raw_capture"]
    require(isinstance(capture, dict) and set(capture) == {"stdout_bytes", "stdout_sha256", "stdout_base64", "stderr_bytes", "stderr_sha256", "stderr_base64"}, "idle raw capture schema")
    for stream in ("stdout", "stderr"):
        decoded = base64.b64decode(capture[f"{stream}_base64"], validate=True)
        require(_positive_or_zero_int(capture[f"{stream}_bytes"]) and len(decoded) == capture[f"{stream}_bytes"] and hashlib.sha256(decoded).hexdigest() == capture[f"{stream}_sha256"], f"idle {stream} capture binding")
    idle = value["idle"]
    require(isinstance(idle, dict) and set(idle) == {"accepted_mode", "row_count", "device_ids", "sanitized_payload"} and idle["accepted_mode"] in {"empty", "self_observer_rows"} and isinstance(idle["device_ids"], list) and isinstance(idle["sanitized_payload"], dict), "idle observer result schema")
    if idle["accepted_mode"] == "empty":
        require(idle == {"accepted_mode": "empty", "row_count": 0, "device_ids": [], "sanitized_payload": {"device_util_by_proc_list": []}}, "idle empty binding")
    else:
        rows = idle["sanitized_payload"].get("device_util_by_proc_list")
        require(idle["row_count"] == 4 and idle["device_ids"] == [0, 1, 2, 3] and isinstance(rows, list) and len(rows) == 4 and all(isinstance(row, dict) and set(row) == {"device_id", "mem_size", "process_id", "process_name", "process_name_mode", "shared_mem_size"} and row["device_id"] in {0, 1, 2, 3} and row["process_id"] == "<observer-child-pid>" and row["process_name_mode"] in {"absolute_normalized", "basename_non_authoritative"} and _positive_or_zero_int(row["mem_size"]) and _positive_or_zero_int(row["shared_mem_size"]) for row in rows), "idle self-observer binding")
        require([row["device_id"] for row in rows] == [0, 1, 2, 3], "idle device IDs are not unique and ordered")
    stdout = base64.b64decode(capture["stdout_base64"], validate=True)
    parsed = operational.strict_json_loads(stdout.decode("utf-8", errors="strict"))
    recomputed = operational.validate_idle_payload(
        parsed,
        child_identity=operational.ChildIdentity(**child),
        launched_executable=Path(xpu["resolved_path"]),
    )
    require(recomputed == idle, "idle sanitized result does not match strict raw stdout")
    return value


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _positive_or_zero_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _spawn(packet_path: Path, packet_sha256: str, rank: int, environment: dict[str, str], campaign: Path,
           python: str, body: dict[str, Any], campaign_fd: int, card_fd: int, packet_fd: int) -> dict[str, Any]:
    """Spawn once from sealed source over an authenticated seqpacket peer."""
    require(_SEALED_SELF_FD is not None, "coordinator source FD unavailable")
    parent_sock, child_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
    child_sock.set_inheritable(True)
    root_meta, campaign_meta = os.fstat(card_fd), os.fstat(campaign_fd)
    cmdline = Path("/proc/self/cmdline").read_bytes()
    capability = {"format": "laguna-m8-gather-sharded-phase-a-capability-v2", "packet_sha256": packet_sha256,
                  "rank": rank, "nonce": secrets.token_hex(32), "one_shot": True,
                  "root_dev": root_meta.st_dev, "root_inode": root_meta.st_ino,
                  "campaign_dev": campaign_meta.st_dev, "campaign_inode": campaign_meta.st_ino,
                  "peer_pid": os.getpid(), "peer_uid": os.getuid(), "peer_gid": os.getgid(),
                  "coordinator_source_fd": _SEALED_SELF_FD,
                  "coordinator_cmdline_sha256": hashlib.sha256(cmdline).hexdigest()}
    payload = phase_a.canonical_json(capability)
    runner_raw = _read_source(Path(body["runner"]["path"]), body["runner"]["sha256"])
    runner_fd = _sealed_source(runner_raw, f"laguna-phase-a-runner-card{rank}")
    os.set_inheritable(runner_fd, True)
    command = [python, "-I", "-S", f"/proc/self/fd/{runner_fd}",
               "--authorization-json", str(packet_path), "--expected-authorization-sha256", packet_sha256,
               "--rank", str(rank), "--capability-fd", str(child_sock.fileno()),
               "--campaign-fd", str(campaign_fd), "--card-fd", str(card_fd),
               "--runner-source-fd", str(runner_fd), "--packet-fd", str(packet_fd)]
    try:
        process = subprocess.Popen(command, cwd="/", env=environment, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   pass_fds=(child_sock.fileno(), campaign_fd, card_fd, runner_fd, packet_fd), start_new_session=True)
    finally:
        child_sock.close()
        os.close(runner_fd)
    try:
        require(parent_sock.send(payload) == len(payload), "short capability seqpacket send")
    finally:
        parent_sock.close()
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                stdout, stderr = process.communicate(timeout=15)
            except subprocess.TimeoutExpired as error:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired as wait_error:
                    raise RuntimeError("timed-out Phase-A process could not be reaped") from wait_error
                stdout, stderr = error.output or b"", error.stderr or b""
        require(process.returncode is not None, "timed-out Phase-A process remains unresolved")
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError("timed-out Phase-A process group remains live")
    stdout_hash = _raw_at(campaign_fd, f"card{rank}.stdout.raw", stdout)
    stderr_hash = _raw_at(campaign_fd, f"card{rank}.stderr.raw", stderr)
    return {"rank": rank, "command": command, "pid": process.pid, "returncode": process.returncode,
            "timed_out": timed_out, "stdout_path": str(campaign / f"card{rank}.stdout.raw"), "stdout_sha256": stdout_hash,
            "stderr_path": str(campaign / f"card{rank}.stderr.raw"), "stderr_sha256": stderr_hash,
            "capability_nonce_sha256": hashlib.sha256(capability["nonce"].encode()).hexdigest()}


def _prepare_campaign_roots(campaign: Path) -> tuple[int, list[int]]:
    """Create the only four accepted roots before any child receives a token."""
    phase_a.assert_live_internal_nvme(campaign.parent, "Phase-A campaign parent")
    os.mkdir(campaign, 0o700)
    phase_a.assert_live_internal_nvme(campaign, "Phase-A campaign root")
    campaign_fd = os.open(campaign, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    card_fds: list[int] = []
    try:
        for rank in range(4):
            os.mkdir(f"card{rank}", 0o700, dir_fd=campaign_fd)
            card_fd = os.open(f"card{rank}", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                              dir_fd=campaign_fd)
            card_fds.append(card_fd)
            os.mkdir("evidence", 0o700, dir_fd=card_fd)
            os.mkdir("scratch", 0o700, dir_fd=card_fd)
            root = campaign / f"card{rank}"
            phase_a.assert_live_internal_nvme(root, f"Phase-A card{rank} root")
        os.fsync(campaign_fd)
        return campaign_fd, card_fds
    except BaseException:
        for descriptor in card_fds:
            os.close(descriptor)
        os.close(campaign_fd)
        raise


def _seal_namespace(campaign_fd: int, card_fds: list[int]) -> None:
    """Seal evidence namespaces without traversing runtime-created scratch."""
    allowed = {f"card{rank}" for rank in range(4)} | {"campaign-start.json", "campaign-terminal.json", "aggregate.json"}
    allowed |= {f"card{rank}.{stream}.raw" for rank in range(4) for stream in ("stdout", "stderr")}
    inventory = set(os.listdir(campaign_fd))
    require({f"card{rank}" for rank in range(4)} | {"campaign-start.json", "campaign-terminal.json"} <= inventory <= allowed,
            "campaign evidence inventory")
    for name in inventory - {f"card{rank}" for rank in range(4)}:
        descriptor = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=campaign_fd)
        try:
            metadata = os.fstat(descriptor)
            require(stat.S_ISREG(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) == 0o444,
                    f"campaign evidence not immutable: {name}")
        finally:
            os.close(descriptor)
    for card_fd in card_fds:
        require(set(os.listdir(card_fd)) == {"evidence", "scratch"}, "card namespace inventory")
        for name in ("evidence", "scratch"):
            descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                                 dir_fd=card_fd)
            try:
                os.fchmod(descriptor, 0o555)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        os.fchmod(card_fd, 0o555)
        os.fsync(card_fd)
    os.fchmod(campaign_fd, 0o555)
    os.fsync(campaign_fd)


def _live_idle_gate(snapshot: Any = None, sleep: Any = time.sleep, monotonic: Any = time.monotonic) -> dict[str, Any]:
    """Observe a full 65-second interval, not merely 65 instant samples."""
    boot = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
    require(bool(boot), "current boot identity absent")
    if snapshot is None:
        require(operational is not None, "operational helper not bootstrapped")
        snapshot = operational.capture_idle_snapshot
    started = float(monotonic())
    samples: list[dict[str, Any]] = []
    for index in range(LIVE_IDLE_SECONDS + 1):
        value = snapshot()
        _validate_idle_snapshot(value)
        samples.append({"monotonic_offset_seconds": float(monotonic()) - started, "snapshot": value})
        if index < LIVE_IDLE_SECONDS:
            sleep(1.0)
    elapsed = float(monotonic()) - started
    require(elapsed >= LIVE_IDLE_SECONDS, "idle observation interval was shorter than 65 seconds")
    require(Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip() == boot, "boot identity changed during idle gate")
    return {"format": "laguna-m8-gather-sharded-phase-a-live-idle-v1", "boot_id": boot,
            "samples": samples, "strict_idle_seconds": LIVE_IDLE_SECONDS,
            "elapsed_monotonic_seconds": elapsed, "observer": "installed_xpu_smi_ps_json_self_observer_aware"}


def orchestrate(packet_path: Path, expected_sha256: str) -> dict[str, Any]:
    packet, raw = phase_a.read_canonical_json(packet_path, "Phase-A authorization")
    require(phase_a.sha_bytes(raw) == expected_sha256, "Phase-A packet SHA")
    phase_a.validate_phase_a_packet(packet, packet_path, verify_artifacts=True)
    phase_a.verify_mutual_packets(packet)
    body = packet["body"]
    python = body["common"]["runtime_identity"]["observed_identity"]["python_executable"]
    require(isinstance(python, str) and Path(python).is_file(), "packet canonical Python absent")
    aggregate = Path(body["aggregate_path"])
    packet_fd = os.open(packet_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    campaign = aggregate.parent
    require(campaign.is_absolute() and not campaign.exists() and campaign.parent.is_dir() and not campaign.parent.is_symlink(),
            "campaign root must be fresh")
    phase_a.assert_live_internal_nvme(campaign.parent, "Phase-A campaign parent")
    require(all(Path(card["output_root"]) == campaign / f"card{rank}" for rank, card in enumerate(body["cards"])),
            "all Phase-A card roots must be the one fresh aggregate campaign root")
    parent_fd = os.open(campaign.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    gate_name = f".laguna-m8-phase-a-preflight-{expected_sha256}.json"
    gate = {"format": "laguna-m8-gather-sharded-phase-a-preflight-consumption-v1", "packet_path": str(packet_path),
            "packet_sha256": expected_sha256, "status": "one_shot_gate_started", "no_retry": True,
            "candidate_imported": False, "card_root_created": False}
    gate_sha256 = _write_at(parent_fd, gate_name, gate)
    try:
        live_idle = _live_idle_gate()
    except BaseException as error:
        _write_at(parent_fd, f".laguna-m8-phase-a-preflight-failure-{expected_sha256}.json",
                  {"format": TERMINAL_FORMAT, "status": "failed_live_pre_campaign_gate", "passed": False,
                   "packet_path": str(packet_path), "packet_sha256": expected_sha256,
                   "preflight_consumption_path": str(campaign.parent / gate_name),
                   "preflight_consumption_sha256": gate_sha256,
                   "failure": {"type": type(error).__name__, "message": str(error)}, "no_retry": True,
                   "candidate_imported": False, "card_root_created": False})
        os.close(parent_fd)
        os.close(packet_fd)
        raise
    try:
        campaign_fd, card_fds = _prepare_campaign_roots(campaign)
    except BaseException as error:
        _write_at(parent_fd, f".laguna-m8-phase-a-setup-failure-{expected_sha256}.json",
                  {"format": TERMINAL_FORMAT, "status": "failed_campaign_root_setup", "passed": False,
                   "packet_sha256": expected_sha256, "preflight_consumption_sha256": gate_sha256,
                   "failure": {"type": type(error).__name__, "message": str(error)}, "no_retry": True,
                   "phase_b_authorized": False})
        os.close(parent_fd)
        os.close(packet_fd)
        raise
    start = {"format": "laguna-m8-gather-sharded-phase-a-start-v4", "packet_path": str(packet_path),
             "packet_sha256": expected_sha256, "one_shot": True, "cards_sequential": True,
             "timeout_seconds": TIMEOUT_SECONDS, "preflight_consumption_path": str(campaign.parent / gate_name),
             "preflight_consumption_sha256": gate_sha256, "live_idle": live_idle}
    try:
        start_sha256 = _write_at(campaign_fd, "campaign-start.json", start)
    except BaseException as error:
        _write_at(campaign_fd, "campaign-terminal.json", {"format": TERMINAL_FORMAT,
                  "status": "failed_campaign_start_write", "passed": False, "packet_sha256": expected_sha256,
                  "failure": {"type": type(error).__name__, "message": str(error)}, "no_retry": True,
                  "phase_b_authorized": False})
        _seal_namespace(campaign_fd, card_fds)
        for descriptor in card_fds:
            os.close(descriptor)
        os.close(campaign_fd)
        os.close(parent_fd)
        os.close(packet_fd)
        raise
    reports: list[dict[str, Any]] = []
    try:
        for rank, card in enumerate(body["cards"]):
            report = _spawn(packet_path, expected_sha256, rank, card["environment"], campaign, python, body,
                            campaign_fd, card_fds[rank], packet_fd)
            reports.append(report)
            if report["returncode"] != 0 or report["timed_out"]:
                _write_at(campaign_fd, "campaign-terminal.json", {"format": TERMINAL_FORMAT, "status": "failed", "passed": False,
                    "packet_sha256": expected_sha256, "campaign_start_path": str(campaign / "campaign-start.json"),
                    "campaign_start_sha256": start_sha256, "failed_rank": rank, "card_process": report,
                    "no_retry": True, "phase_b_authorized": False})
                raise RuntimeError(f"Phase-A card {rank} failed")
        paths = [Path(card["output_root"]) / "evidence/component-result.json" for card in body["cards"]]
        report = analyzer.validate(packet_path, expected_sha256, paths,
                                   {"path": str(campaign / "campaign-start.json"), "sha256": start_sha256}, campaign_fd)
        aggregate_sha256 = _write_at(campaign_fd, aggregate.name, report)
        terminal = {"format": TERMINAL_FORMAT,
            "status": "component_timing_pass_pending_mandatory_counters", "passed": True, "aggregate_path": str(aggregate),
            "aggregate_sha256": aggregate_sha256, "campaign_start_path": str(campaign / "campaign-start.json"),
            "campaign_start_sha256": start_sha256, "packet_path": str(packet_path), "packet_sha256": expected_sha256,
            "card_processes": reports, "no_retry": True, "phase_b_authorized": True,
            "phase_b_authorizer": {"aggregate_format": analyzer.FORMAT,
                                   "required_status": "component_timing_pass_pending_mandatory_counters",
                                   "required_passed": True, "aggregate_sha256": aggregate_sha256,
                                   "campaign_start_sha256": start_sha256}}
        _write_at(campaign_fd, "campaign-terminal.json", terminal)
        _seal_namespace(campaign_fd, card_fds)
        return report
    except BaseException as error:
        try:
            terminal_fd = os.open("campaign-terminal.json", os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                                  dir_fd=campaign_fd)
        except FileNotFoundError:
            _write_at(campaign_fd, "campaign-terminal.json", {"format": TERMINAL_FORMAT,
                      "status": "failed_preimport_or_coordinator", "passed": False,
                      "packet_sha256": expected_sha256, "campaign_start_path": str(campaign / "campaign-start.json"),
                      "campaign_start_sha256": start_sha256,
                      "failure": {"type": type(error).__name__, "message": str(error)}, "card_processes": reports,
                      "no_retry": True, "phase_b_authorized": False})
        else:
            os.close(terminal_fd)
        _seal_namespace(campaign_fd, card_fds)
        raise
    finally:
        for descriptor in card_fds:
            os.close(descriptor)
        os.close(campaign_fd)
        os.close(parent_fd)
        os.close(packet_fd)


def main() -> int:
    global _SEALED_SELF_FD
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization-json", type=Path, required=True)
    parser.add_argument("--expected-authorization-sha256", required=True)
    parser.add_argument("--sealed-self-fd", type=int)
    args = parser.parse_args()
    packet = _bootstrap_packet(args.authorization_json, args.expected_authorization_sha256)
    _ensure_sealed_self(packet, args.authorization_json, args.expected_authorization_sha256, args.sealed_self_fd)
    _SEALED_SELF_FD = args.sealed_self_fd
    _bootstrap_modules(packet)
    orchestrate(args.authorization_json, args.expected_authorization_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
