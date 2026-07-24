#!/usr/bin/env python3
"""One-shot sequential Phase-B unitrace coordinator for sharded MoeGather.

The runner is intentionally unusable without a frozen Phase-B packet and a
passing, hash-bound Phase-A aggregate.  It creates one new root, runs A1/B1/
B2/A2 on card 0 then card 1, 2 and 3, and seals the first failure.  There is
no retry or fallback path.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import ctypes
import fcntl
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import sys
import time
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

counters: Any = None
operational: Any = None
fixture: Any = None
phase_a: Any = None
phase_a_analysis: Any = None
analyzer: Any = None
SOURCE_TOOL_IDENTITIES: dict[str, Any] | None = None

MAIN = Path("/home/steve/llm-optimizations")
ROOT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
RUNS = ROOT / "runs"
PYTHON = Path("/home/steve/.venvs/deepseek-v4-xpu/bin/python")
SUDO_PASSWORD = Path("/home/steve/SUDOPASSWORD.txt")
UNITRACE = Path("/home/steve/src/pti-gpu/build-unitrace/unitrace")
UNITRACE_SHA256 = "5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a"
LIBUNITRACE_SHA256 = "00f9e1c95f1b53f1466f15dafa97ddcd709899ad7ca2869626456deb5e177e04"
PTI_COMMIT = "a5bab309f4ffdd78bd127035c46f5f75371160f8"
LOADER = Path("/usr/lib/x86_64-linux-gnu/libze_loader.so.1.28.2")
LOADER_SHA256 = "0fe232b18985ae078dd546b57bc6d11bacf1030834c0544f7e3feb53ed71c1d0"
DRIVER = Path("/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1.15.38308")
DRIVER_SHA256 = "26fa68779adb03b200a8c3001cf81e59fc9a3d63e0f38627ec0005ffce574e7a"
INNER_TIMEOUT, OUTER_TIMEOUT = 900, 930  # preregistered, deliberately not yet tested
STRICT_IDLE_SECONDS, IDLE_SAMPLE_INTERVAL_SECONDS, IDLE_MIN_SAMPLES = 65, 5, 14
ARMS = ("A1", "B1", "B2", "A2")
TOOL_NAMES = (
    "laguna_m8_gather_sharded_counter_parser.py",
    "profile_laguna_m8_gather_sharded_phase_b_fixture.py",
    "run_laguna_m8_gather_sharded_phase_b.py",
    "analyze_laguna_m8_gather_sharded_phase_b.py",
    "test_laguna_m8_gather_sharded_phase_b.py",
    "preflight_laguna_m8_gather_sharded_operational.py",
)
TOOL_ROLES = {
    "runner": "run_laguna_m8_gather_sharded_phase_b.py",
    "analyzer": "analyze_laguna_m8_gather_sharded_phase_b.py",
    "fixture": "profile_laguna_m8_gather_sharded_phase_b_fixture.py",
    "counter_parser": "laguna_m8_gather_sharded_counter_parser.py",
    "tests": "test_laguna_m8_gather_sharded_phase_b.py",
    "operational_preflight": "preflight_laguna_m8_gather_sharded_operational.py",
}
LIBRARY_NAMES = {
    "shared-_C.abi3.so", "shared-_xpu_C.abi3.so", "candidate-_moe_C.abi3.so",
    "libgdn_attn_kernels_xe_2.so", "libgrouped_gemm_xe_2.so",
    "libgrouped_gemm_xe_default.so", "libmhc_kernels_xe_2.so",
    "libmqa_logits_kernels_xe_2.so",
}
BODY_KEYS = {"phase", "common", "common_binding_sha256", "phase_a_binding", "output_root", "cards", "protocol", "counter_gates", "counter_header", "tools", "counter_tools", "temporal_control"}
F_ADD_SEALS = getattr(fcntl, "F_ADD_SEALS", 1033)
F_GET_SEALS = getattr(fcntl, "F_GET_SEALS", 1034)
REQUIRED_SEALS = (
    getattr(fcntl, "F_SEAL_SEAL", 1)
    | getattr(fcntl, "F_SEAL_SHRINK", 2)
    | getattr(fcntl, "F_SEAL_GROW", 4)
    | getattr(fcntl, "F_SEAL_WRITE", 8)
)

def expected_environment(rank: int, arm_root: Path) -> dict[str, str]:
    """Exact env-i surface, with every writable path below one fresh arm."""
    require(arm_root.is_absolute(), "arm environment root must be absolute")
    return phase_a.expected_environment(rank, arm_root)

def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)

def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def sha(path: Path) -> str:
    return file_identity(path)["sha256"]


def file_identity(path: Path) -> dict[str, Any]:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    before = os.fstat(descriptor)
    require(stat.S_ISREG(before.st_mode), f"not a regular retained file: {path}")
    digest = hashlib.sha256()
    try:
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            digest.update(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode), f"file changed during retained read: {path}")
    return {"sha256": digest.hexdigest(), "bytes": before.st_size, "mode": stat.S_IMODE(before.st_mode), "dev": before.st_dev, "inode": before.st_ino}


def manifest_entry(path: Path) -> dict[str, Any]:
    identity = file_identity(path)
    return {"path": str(path), "sha256": identity["sha256"], "bytes": identity["bytes"]}

def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _boot_id() -> str:
    path = Path("/proc/sys/kernel/random/boot_id")
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        raw = os.read(descriptor, 129)
    finally:
        os.close(descriptor)
    value = raw.decode("ascii", "strict").strip()
    require(re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value) is not None, "malformed boot identity")
    return value


def validate_operational_sample(value: object) -> dict[str, Any]:
    """Recompute the observer result from its exact raw bytes and child identity."""
    require(operational is not None, "sealed operational helper was not bootstrapped")
    required = {"format", "status", "observed_utc", "argv", "environment", "timeout_seconds", "xpu_smi", "child_identity", "raw_capture", "idle"}
    require(isinstance(value, dict) and set(value) == required and value["format"] == operational.FORMAT and value["status"] == "passed", "operational sample schema/status drift")
    xpu = value["xpu_smi"]
    resolved, metadata, digest = operational.resolve_executable(operational.DEFAULT_XPU_SMI, expected_sha256=operational.EXPECTED_XPU_SMI_SHA256)
    require(xpu == {"configured_path": str(operational.DEFAULT_XPU_SMI), "resolved_path": str(resolved), "sha256": digest, "device": metadata.st_dev, "inode": metadata.st_ino}, "operational xpu-smi identity drift")
    require(value["argv"] == [str(resolved), *operational.PS_ARGUMENTS] and value["environment"] == operational.OBSERVER_ENVIRONMENT and value["timeout_seconds"] == operational.DEFAULT_TIMEOUT_SECONDS, "operational argv/environment/timeout drift")
    child = value["child_identity"]
    child_keys = {"process_id", "proc_dir_fd_acquired", "pidfd_acquired", "proc_exe_resolved", "executable_device", "executable_inode"}
    require(isinstance(child, dict) and set(child) == child_keys and isinstance(child["process_id"], int) and not isinstance(child["process_id"], bool) and child["process_id"] > 0 and child["proc_dir_fd_acquired"] is True and isinstance(child["pidfd_acquired"], bool) and child["proc_exe_resolved"] == str(resolved) and child["executable_device"] == metadata.st_dev and child["executable_inode"] == metadata.st_ino, "operational child identity drift")
    capture = value["raw_capture"]
    capture_keys = {"stdout_bytes", "stdout_sha256", "stdout_base64", "stderr_bytes", "stderr_sha256", "stderr_base64"}
    require(isinstance(capture, dict) and set(capture) == capture_keys, "operational raw capture schema drift")
    decoded: dict[str, bytes] = {}
    for stream in ("stdout", "stderr"):
        try:
            raw = base64.b64decode(capture[f"{stream}_base64"], validate=True)
        except (TypeError, ValueError, binascii.Error) as error:
            raise RuntimeError(f"operational {stream} base64 drift") from error
        require(isinstance(capture[f"{stream}_bytes"], int) and not isinstance(capture[f"{stream}_bytes"], bool) and len(raw) == capture[f"{stream}_bytes"] and hashlib.sha256(raw).hexdigest() == capture[f"{stream}_sha256"], f"operational {stream} length/hash drift")
        decoded[stream] = raw
    try:
        payload = operational.strict_json_loads(decoded["stdout"].decode("utf-8", "strict"))
    except (UnicodeDecodeError, ValueError) as error:
        raise RuntimeError("operational raw stdout parse drift") from error
    identity = operational.ChildIdentity(**child)
    require(operational.validate_idle_payload(payload, child_identity=identity, launched_executable=resolved) == value["idle"], "operational parsed idle evidence drift")
    return value


def continuous_strict_idle() -> tuple[dict[str, Any], int]:
    """Sample the exact fail-closed observer throughout a 65-second cooling window."""
    started_utc, boot_before = now(), _boot_id()
    start = time.monotonic()
    samples: list[dict[str, Any]] = []
    status = 0
    while True:
        sample, sample_status = operational.execute_preflight()
        if sample_status == 0:
            validate_operational_sample(sample)
        samples.append({"ordinal": len(samples), "elapsed_seconds": time.monotonic() - start, "report": sample})
        if sample_status != 0:
            status = 1
            break
        elapsed = time.monotonic() - start
        if elapsed >= STRICT_IDLE_SECONDS and len(samples) >= IDLE_MIN_SAMPLES:
            break
        target = start + len(samples) * IDLE_SAMPLE_INTERVAL_SECONDS
        delay = target - time.monotonic()
        if delay > 0:
            time.sleep(delay)
    elapsed = time.monotonic() - start
    boot_after = _boot_id()
    passed = status == 0 and elapsed >= STRICT_IDLE_SECONDS and len(samples) >= IDLE_MIN_SAMPLES and boot_before == boot_after
    report = {
        "format": "laguna-m8-gather-sharded-phase-b-continuous-idle-v1",
        "status": "passed" if passed else "failed",
        "started_utc": started_utc,
        "ended_utc": now(),
        "duration_required_seconds": STRICT_IDLE_SECONDS,
        "sample_interval_seconds": IDLE_SAMPLE_INTERVAL_SECONDS,
        "minimum_samples": IDLE_MIN_SAMPLES,
        "elapsed_seconds": elapsed,
        "boot_id_before": boot_before,
        "boot_id_after": boot_after,
        "samples": samples,
    }
    return report, 0 if passed else 1

def exclusive(path: Path, value: dict[str, Any]) -> None:
    require(not path.exists() and not path.is_symlink() and path.parent.is_dir() and not path.parent.is_symlink(), "refusing evidence overwrite")
    data = canonical(value) + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(data)
        while view:
            wrote = os.write(fd, view)
            require(wrote > 0, "short evidence write")
            view = view[wrote:]
        os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)

def exclusive_bytes(path: Path, data: bytes) -> None:
    require(not path.exists() and not path.is_symlink() and path.parent.is_dir() and not path.parent.is_symlink(), "refusing raw evidence overwrite")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(data)
        while view:
            wrote = os.write(fd, view)
            require(wrote > 0, "short raw evidence write")
            view = view[wrote:]
        os.fsync(fd)
    finally:
        os.close(fd)

def read(path: Path, expected: str) -> dict[str, Any]:
    require(path.is_absolute() and not path.is_symlink(), "unsafe packet/aggregate path")
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= 128 * 1024 * 1024, "unsafe packet/aggregate retained file")
        raw = bytearray()
        while len(raw) <= before.st_size:
            block = os.read(descriptor, min(1024 * 1024, before.st_size + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require(len(raw) == before.st_size and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "packet/aggregate changed during retained read")
    raw = bytes(raw)
    require(hashlib.sha256(raw).hexdigest() == expected, "packet/aggregate SHA mismatch")
    value = json.loads(raw)
    require(isinstance(value, dict) and raw == canonical(value) + b"\n", "noncanonical packet/aggregate")
    return value

def tool_identity() -> dict[str, Any]:
    lib = UNITRACE.parent / "libunitrace_tool.so"
    require(UNITRACE.is_file() and sha(UNITRACE) == UNITRACE_SHA256 and lib.is_file() and sha(lib) == LIBUNITRACE_SHA256, "unitrace/libunitrace identity drift")
    require(LOADER.is_file() and sha(LOADER) == LOADER_SHA256 and DRIVER.is_file() and sha(DRIVER) == DRIVER_SHA256, "Level Zero loader/driver identity drift")
    commit = subprocess.run(["/usr/bin/git", "-c", f"safe.directory={UNITRACE.parents[1]}", "-C", str(UNITRACE.parents[1]), "rev-parse", "HEAD"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, check=False)
    require(commit.returncode == 0 and commit.stdout.strip() == PTI_COMMIT, "PTI commit drift")
    return {"unitrace": {"path": str(UNITRACE), "sha256": UNITRACE_SHA256}, "libunitrace_tool": {"path": str(lib), "sha256": LIBUNITRACE_SHA256}, "pti_commit": PTI_COMMIT, "level_zero_loader": {"path": str(LOADER), "sha256": LOADER_SHA256}, "level_zero_driver": {"path": str(DRIVER), "sha256": DRIVER_SHA256}}

def tool_hashes() -> dict[str, str]:
    require(isinstance(SOURCE_TOOL_IDENTITIES, dict), "sealed tool identities not bootstrapped")
    by_name = {Path(identity["path"]).name: identity["sha256"] for identity in SOURCE_TOOL_IDENTITIES["phase_b"].values()}
    require(set(by_name) == set(TOOL_NAMES), "sealed Phase-B tool filename closure")
    return by_name

def _sha_value(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _common_sha(common: object) -> str:
    require(isinstance(common, dict), "shared common must be an object")
    return phase_a.common_hash(common)


def _read_unbound(path: Path, label: str) -> tuple[dict[str, Any], str]:
    require(path.is_absolute() and not path.is_symlink(), f"unsafe {label} path")
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= 128 * 1024 * 1024, f"unsafe {label} retained file")
        raw = bytearray()
        while len(raw) < before.st_size:
            block = os.read(descriptor, min(1024 * 1024, before.st_size - len(raw)))
            require(bool(block), f"short {label} retained read")
            raw.extend(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), f"{label} changed during retained read")
    raw = bytes(raw)
    value = json.loads(raw)
    require(isinstance(value, dict) and raw == canonical(value) + b"\n", f"noncanonical {label}")
    return value, hashlib.sha256(raw).hexdigest()


def _sealed_source(raw: bytes, name: str) -> int:
    create = getattr(os, "memfd_create", None)
    if callable(create):
        descriptor = create(
            name,
            getattr(os, "MFD_CLOEXEC", 1) | getattr(os, "MFD_ALLOW_SEALING", 2),
        )
    else:
        libc = ctypes.CDLL(None, use_errno=True)
        descriptor = int(libc.memfd_create(name.encode(), 1 | 2))
        if descriptor < 0:
            raise OSError(ctypes.get_errno(), "memfd_create failed")
    position = 0
    while position < len(raw):
        written = os.write(descriptor, raw[position:])
        require(written > 0, "short sealed-source write")
        position += written
    os.lseek(descriptor, 0, os.SEEK_SET)
    fcntl.fcntl(descriptor, F_ADD_SEALS, REQUIRED_SEALS)
    require(fcntl.fcntl(descriptor, F_GET_SEALS) & REQUIRED_SEALS == REQUIRED_SEALS, "source memfd sealing failed")
    return descriptor


def _load_sealed_module(name: str, identity: dict[str, str]) -> Any:
    raw = _source_bytes(identity)
    descriptor = _sealed_source(raw, f"laguna-phase-b-{name}")
    module = types.ModuleType(name)
    module.__file__ = identity["path"]
    module.__package__ = ""
    module.__sealed_source_sha256__ = identity["sha256"]
    sys.modules[name] = module
    try:
        exec(compile(raw, identity["path"], "exec"), module.__dict__)
        return module
    except BaseException:
        sys.modules.pop(name, None)
        raise
    finally:
        os.close(descriptor)


def _bootstrap_modules(packet: dict[str, Any], packet_sha: str) -> None:
    """Load every project helper from packet-hash-bound bytes, never PYTHONPATH."""
    global SOURCE_TOOL_IDENTITIES, analyzer, counters, fixture, operational, phase_a, phase_a_analysis
    require(all(value is None for value in (analyzer, counters, fixture, operational, phase_a, phase_a_analysis)), "project modules already imported")
    body = packet.get("body")
    require(isinstance(body, dict) and isinstance(body.get("tools"), dict), "bootstrap Phase-B body/tool schema")
    binding = body.get("phase_a_binding")
    require(isinstance(binding, dict), "bootstrap Phase-A binding schema")
    phase_a_path = Path(binding.get("authorization_path", ""))
    phase_a_packet, _phase_a_sha = _read_unbound(phase_a_path, "bootstrap Phase-A packet")
    phase_a_body = phase_a_packet.get("body")
    require(
        isinstance(phase_a_body, dict)
        and phase_a_packet.get("paired_phase_b_packet_sha256") == packet_sha
        and hashlib.sha256(canonical(phase_a_body) + b"\n").hexdigest() == binding.get("phase_a_body_sha256"),
        "bootstrap Phase-A mutual binding drift",
    )
    SOURCE_TOOL_IDENTITIES = {
        "phase_b": body["tools"],
        "phase_a": {"runner": phase_a_body["runner"], "analyzer": phase_a_body["analyzer"]},
    }
    phase_a = _load_sealed_module("run_laguna_m8_gather_sharded_phase_a", SOURCE_TOOL_IDENTITIES["phase_a"]["runner"])
    phase_a_analysis = _load_sealed_module("analyze_laguna_m8_gather_sharded_phase_a", SOURCE_TOOL_IDENTITIES["phase_a"]["analyzer"])
    counters = _load_sealed_module("laguna_m8_gather_sharded_counter_parser", SOURCE_TOOL_IDENTITIES["phase_b"]["counter_parser"])
    operational = _load_sealed_module("preflight_laguna_m8_gather_sharded_operational", SOURCE_TOOL_IDENTITIES["phase_b"]["operational_preflight"])
    fixture = _load_sealed_module("profile_laguna_m8_gather_sharded_phase_b_fixture", SOURCE_TOOL_IDENTITIES["phase_b"]["fixture"])
    fixture.counters = counters
    fixture.phase_a = phase_a
    fixture.phase_a_analysis = phase_a_analysis
    fixture.SOURCE_TOOL_IDENTITIES = SOURCE_TOOL_IDENTITIES
    sys.modules["run_laguna_m8_gather_sharded_phase_b"] = sys.modules[__name__]
    analyzer = _load_sealed_module("analyze_laguna_m8_gather_sharded_phase_b", SOURCE_TOOL_IDENTITIES["phase_b"]["analyzer"])
    require(
        all(
            getattr(module, "__sealed_source_sha256__", None) is not None
            for module in (phase_a, phase_a_analysis, counters, operational, fixture, analyzer)
        ),
        "unsealed project module in execution closure",
    )


def _ensure_sealed_self(packet: dict[str, Any], packet_path: Path, packet_sha: str, aggregate_path: Path, aggregate_sha: str, sealed_self_fd: int | None) -> None:
    identity = packet["body"]["tools"]["runner"]
    if sealed_self_fd is not None:
        require(Path(__file__).as_posix() == f"/proc/self/fd/{sealed_self_fd}", "runner is not executing from sealed source")
        metadata = os.fstat(sealed_self_fd)
        raw = os.pread(sealed_self_fd, metadata.st_size, 0)
        require(
            len(raw) == metadata.st_size
            and hashlib.sha256(raw).hexdigest() == identity["sha256"]
            and fcntl.fcntl(sealed_self_fd, F_GET_SEALS) & REQUIRED_SEALS == REQUIRED_SEALS,
            "sealed runner source drift",
        )
        return
    raw = _source_bytes(identity)
    descriptor = _sealed_source(raw, "laguna-phase-b-runner")
    os.set_inheritable(descriptor, True)
    python = packet["body"]["common"]["runtime_identity"]["observed_identity"]["python_executable"]
    command = [
        python, "-I", "-S", f"/proc/self/fd/{descriptor}",
        "--sealed-self-fd", str(descriptor),
        "--packet", str(packet_path), "--packet-sha256", packet_sha,
        "--phase-a-aggregate", str(aggregate_path),
        "--phase-a-aggregate-sha256", aggregate_sha,
    ]
    os.execve(
        python,
        command,
        {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
    )


def expected_tools() -> dict[str, dict[str, str]]:
    require(isinstance(SOURCE_TOOL_IDENTITIES, dict), "sealed tool identities not bootstrapped")
    identities = SOURCE_TOOL_IDENTITIES["phase_b"]
    require(isinstance(identities, dict) and set(identities) == set(TOOL_ROLES), "sealed Phase-B tool-role closure")
    return {role: {"path": identities[role]["path"], "sha256": identities[role]["sha256"]} for role in TOOL_ROLES}


def temporal_control_identity() -> dict[str, Any]:
    source_root = Path("/home/steve/src/pti-gpu/tools/unitrace")
    source_paths = {
        "README.md": source_root / "README.md",
        "unitrace.cc": source_root / "src/unitrace.cc",
        "unicontrol.h": source_root / "src/unicontrol.h",
        "shared_memory.h": source_root / "src/utils/shared_memory.h",
    }
    return {
        "pti_commit": PTI_COMMIT,
        "source_files": {name: {"path": str(path), "sha256": sha(path)} for name, path in source_paths.items()},
        "session_pattern": "Laguna<ARM>Card<RANK><32-lowercase-hex>",
        "session_minimum_bits": 128,
        "session_count": 16,
        "shm_prefix": "/uctrl",
        "prelaunch_shm_absent": True,
        "start_paused": True,
        "follow_child_process": 0,
        "capture_sequence": ["resume", "13x47_selected_gather", "xpu_synchronize", "pause", "stop"],
        "resume_acknowledgement": "[INFO] Session {session} is resumed\n",
        "pause_acknowledgement": "[INFO] Session {session} is paused\n",
        "stop_acknowledgement": "[INFO] Session {session} is stopped and can no longer be paused or resumed\n",
        "post_stop_shm_unlinked": True,
        "normal_return_and_metric_flush_required": True,
        "graph_capture_compile_apis_allowed": False,
    }


def _validate_phase_a_aggregate(aggregate: dict[str, Any], aggregate_path: Path, aggregate_sha: str, phase_a_packet: dict[str, Any], phase_a_path: Path, phase_a_full_sha: str, binding: dict[str, Any]) -> None:
    require(aggregate_path == Path(binding["aggregate_path"]) and hashlib.sha256(canonical(aggregate) + b"\n").hexdigest() == aggregate_sha, "Phase-A aggregate path/hash drift")
    require(aggregate.get("format") == binding["aggregate_format"] and aggregate.get("status") == binding["required_status"] and aggregate.get("passed") is binding["required_passed"] and aggregate.get("packet_path") == str(phase_a_path) and aggregate.get("packet_sha256") == phase_a_full_sha, "Phase-A aggregate identity drift")
    entries = aggregate.get("card_results")
    require(isinstance(entries, list) and len(entries) == 4, "Phase-A aggregate must bind four card results")
    paths: list[Path] = []
    for rank, entry in enumerate(entries):
        require(isinstance(entry, dict) and set(entry) == {"rank", "path", "sha256"} and entry["rank"] == rank and _sha_value(entry["sha256"]), "Phase-A card-result entry schema/order drift")
        path = Path(entry["path"])
        require(path.is_absolute() and path.is_file() and not path.is_symlink() and sha(path) == entry["sha256"], "Phase-A card-result path/hash drift")
        result, result_sha = _read_unbound(path, f"Phase-A card{rank} result")
        require(result_sha == entry["sha256"], "Phase-A card-result changed while reading")
        phase_a.validate_card_result(result, phase_a_packet, rank)
        paths.append(path)
    recomputed = phase_a_analysis.validate(phase_a_path, phase_a_full_sha, paths)
    require(recomputed == aggregate, "Phase-A aggregate/card thresholds/cross-card evidence failed independent recomputation")


def _read_campaign_fd(descriptor: int, label: str, maximum: int = 128 * 1024 * 1024) -> tuple[dict[str, Any], dict[str, Any]]:
    before = os.fstat(descriptor)
    require(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o444 and 0 <= before.st_size <= maximum, f"unsafe sealed {label}")
    raw = os.pread(descriptor, before.st_size, 0)
    after = os.fstat(descriptor)
    require(
        len(raw) == before.st_size
        and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode),
        f"sealed {label} changed during retained read",
    )
    value = json.loads(raw)
    require(isinstance(value, dict) and raw == canonical(value) + b"\n", f"noncanonical sealed {label}")
    return value, {"sha256": hashlib.sha256(raw).hexdigest(), "dev": before.st_dev, "inode": before.st_ino, "bytes": before.st_size, "mode": stat.S_IMODE(before.st_mode)}


def _open_phase_a_predecessor(binding: dict[str, Any], phase_a_path: Path, phase_a_sha: str, aggregate_path: Path, aggregate_sha: str) -> dict[str, Any]:
    campaign = aggregate_path.parent
    require(campaign.is_absolute() and aggregate_path.name == "aggregate.json", "unsafe Phase-A campaign/aggregate path")
    campaign_fd = os.open(campaign, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    descriptors: dict[str, int] = {}
    try:
        campaign_metadata = os.fstat(campaign_fd)
        require(stat.S_ISDIR(campaign_metadata.st_mode) and stat.S_IMODE(campaign_metadata.st_mode) == 0o555, "Phase-A campaign is not sealed")
        for name in ("campaign-start.json", "campaign-terminal.json", aggregate_path.name):
            descriptors[name] = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=campaign_fd)
        start, start_identity = _read_campaign_fd(descriptors["campaign-start.json"], "Phase-A campaign start")
        terminal, terminal_identity = _read_campaign_fd(descriptors["campaign-terminal.json"], "Phase-A campaign terminal")
        aggregate, aggregate_identity = _read_campaign_fd(descriptors[aggregate_path.name], "Phase-A aggregate")
        require(
            start.get("format") == "laguna-m8-gather-sharded-phase-a-start-v4"
            and start.get("packet_path") == str(phase_a_path)
            and start.get("packet_sha256") == phase_a_sha
            and start.get("one_shot") is True
            and start.get("cards_sequential") is True,
            "Phase-A campaign-start authorization drift",
        )
        require(
            terminal.get("format") == "laguna-m8-gather-sharded-phase-a-campaign-terminal-v3"
            and terminal.get("status") == binding["required_status"]
            and terminal.get("passed") is True
            and terminal.get("aggregate_path") == str(aggregate_path)
            and terminal.get("aggregate_sha256") == aggregate_sha
            and terminal.get("campaign_start_path") == str(campaign / "campaign-start.json")
            and terminal.get("campaign_start_sha256") == start_identity["sha256"]
            and terminal.get("packet_path") == str(phase_a_path)
            and terminal.get("packet_sha256") == phase_a_sha
            and terminal.get("no_retry") is True
            and terminal.get("phase_b_authorized") is True,
            "Phase-A terminal does not authorize Phase B",
        )
        require(
            terminal.get("phase_b_authorizer")
            == {
                "aggregate_format": binding["aggregate_format"],
                "required_status": binding["required_status"],
                "required_passed": binding["required_passed"],
                "aggregate_sha256": aggregate_sha,
                "campaign_start_sha256": start_identity["sha256"],
            },
            "Phase-A terminal authorizer tuple drift",
        )
        require(aggregate_identity["sha256"] == aggregate_sha and aggregate.get("passed") is True, "sealed Phase-A aggregate drift")
    except BaseException:
        for descriptor in descriptors.values():
            os.close(descriptor)
        os.close(campaign_fd)
        raise
    evidence = {
        "format": "laguna-m8-gather-sharded-phase-b-predecessor-binding-v1",
        "campaign_path": str(campaign),
        "campaign": {"dev": campaign_metadata.st_dev, "inode": campaign_metadata.st_ino, "mode": stat.S_IMODE(campaign_metadata.st_mode)},
        "campaign_start": {"path": str(campaign / "campaign-start.json"), **start_identity},
        "campaign_terminal": {"path": str(campaign / "campaign-terminal.json"), **terminal_identity, "phase_b_authorized": True},
        "aggregate": {"path": str(aggregate_path), **aggregate_identity},
    }
    return {"campaign_fd": campaign_fd, "descriptors": descriptors, "evidence": evidence}


def _validate_phase_a_predecessor_state(state: dict[str, Any]) -> dict[str, Any]:
    campaign = os.fstat(state["campaign_fd"])
    expected = state["evidence"]
    require(stat.S_ISDIR(campaign.st_mode) and campaign.st_dev == expected["campaign"]["dev"] and campaign.st_ino == expected["campaign"]["inode"] and stat.S_IMODE(campaign.st_mode) == expected["campaign"]["mode"] == 0o555, "retained Phase-A campaign directory drift")
    mapping = {"campaign-start.json": "campaign_start", "campaign-terminal.json": "campaign_terminal", "aggregate.json": "aggregate"}
    for filename, evidence_name in mapping.items():
        _value, identity = _read_campaign_fd(state["descriptors"][filename], f"retained Phase-A {filename}")
        expected_identity = expected[evidence_name]
        require(all(identity[key] == expected_identity[key] for key in ("sha256", "dev", "inode", "bytes", "mode")), f"retained Phase-A predecessor changed: {filename}")
    return expected


def _close_phase_a_predecessor(state: dict[str, Any]) -> None:
    for descriptor in state["descriptors"].values():
        os.close(descriptor)
    os.close(state["campaign_fd"])


def validate(packet: dict[str, Any], packet_path: Path, packet_sha: str, aggregate: dict[str, Any], aggregate_path: Path, aggregate_sha: str, *, retain_predecessor: bool = False) -> dict[str, Any]:
    """Verify both packet wrappers and the post-Phase-A aggregate before import."""
    require(set(packet) == {"format", "packet_path", "body"} and packet["format"] == "laguna-m8-gather-sharded-phase-b-authorization-v3" and packet["packet_path"] == str(packet_path), "wrong Phase-B wrapper")
    phase_a.validate_phase_b_packet_shape(packet, packet_path, verify_artifacts=True)
    body = packet["body"]
    require(isinstance(body, dict) and set(body) == BODY_KEYS and body["phase"] == "B", "Phase-B body schema")
    common = phase_a.validate_common(body["common"])
    common_sha = _common_sha(common)
    require(body["common_binding_sha256"] == common_sha, "Phase-B common binding drift")
    runtime_identity = common["runtime_identity"]["observed_identity"]
    require(PYTHON == Path(runtime_identity["python_executable"]) and PYTHON == Path(runtime_identity["files"]["python"]["path"]), "Phase-B Python differs from shared runtime identity")
    binding = body["phase_a_binding"]
    required_binding = {"authorization_path", "phase_a_body_sha256", "phase_a_runner_path", "phase_a_runner_sha256", "aggregate_path", "aggregate_format", "required_status", "required_passed", "common_binding_sha256"}
    require(isinstance(binding, dict) and set(binding) == required_binding and binding["aggregate_path"] == str(aggregate_path) and binding["aggregate_format"] == "laguna-m8-gather-sharded-phase-a-aggregate-v3" and binding["required_status"] == "component_timing_pass_pending_mandatory_counters" and binding["required_passed"] is True and binding["common_binding_sha256"] == common_sha, "Phase-A binding schema/drift")
    phase_a_path = Path(binding["authorization_path"])
    phase_a_packet, phase_a_full_sha = _read_unbound(phase_a_path, "Phase-A wrapper")
    phase_a.validate_phase_a_packet(phase_a_packet, phase_a_path, verify_artifacts=True)
    require(phase_a_packet["paired_phase_b_packet_sha256"] == packet_sha, "Phase-A wrapper does not bind this full Phase-B packet")
    require(hashlib.sha256(canonical(phase_a_packet["body"]) + b"\n").hexdigest() == binding["phase_a_body_sha256"] and phase_a_packet["body"]["common"] == common and phase_a_packet["body"]["common_binding_sha256"] == common_sha, "Phase-A body/common binding drift")
    require(Path(binding["phase_a_runner_path"]).is_file() and sha(Path(binding["phase_a_runner_path"])) == binding["phase_a_runner_sha256"], "Phase-A runner drift")
    phase_a.verify_mutual_packets(phase_a_packet, packet)
    _validate_phase_a_aggregate(aggregate, aggregate_path, aggregate_sha, phase_a_packet, phase_a_path, phase_a_full_sha, binding)
    require(body["protocol"] == {"cycles": 13, "layers_per_cycle": 47, "raw_selected_rows": 611, "discard_cycles": [0, 1], "retained_selected_rows": 517, "arm_order": ["A1", "B1", "B2", "A2"], "unitrace_inner_timeout_seconds": INNER_TIMEOUT, "runner_outer_timeout_seconds": OUTER_TIMEOUT, "pre_arm_strict_idle_seconds": STRICT_IDLE_SECONDS, "pre_arm_idle_sample_interval_seconds": IDLE_SAMPLE_INTERVAL_SECONDS, "pre_arm_idle_min_samples": IDLE_MIN_SAMPLES, "same_boot_required": True, "fresh_private_runtime_per_arm": True}, "Phase-B counter protocol drift")
    require(body["counter_gates"] == {"gpu_memory_per_field_max_ratio": 1.02, "gpu_memory_total_max_ratio": 1.02, "lsc_per_field_max_ratio": 1.02, "lsc_total_max_ratio": 1.02, "xve_active_max_decline_pp": 0.5, "thread_occupancy_max_decline_pp": 0.5, "xve_stall_max_increase_pp": 0.5, "no_global_rescue": True}, "counter gate drift")
    require(body["counter_header"] == {"fields": 86, "sha256": counters.METRIC_HEADER_SHA256} and body["tools"] == expected_tools() and body["counter_tools"] == tool_identity() and body["temporal_control"] == temporal_control_identity(), "counter/tool/temporal identity drift")
    root = Path(body["output_root"])
    require(root.is_absolute() and root.parent == RUNS, "Phase-B output root drift")
    cards, sessions = body["cards"], []
    require(isinstance(cards, list) and len(cards) == 4, "Phase-B four-card schema")
    for rank, card in enumerate(cards):
        require(isinstance(card, dict) and set(card) == {"rank", "output_root", "environments", "sessions"} and card["rank"] == rank and card["output_root"] == str(root / f"card{rank}") and isinstance(card["environments"], dict) and set(card["environments"]) == set(ARMS) and isinstance(card["sessions"], dict) and set(card["sessions"]) == set(ARMS), "Phase-B card/env/output schema drift")
        for arm in ARMS:
            arm_root = root / f"card{rank}" / arm
            require(card["environments"][arm] == expected_environment(rank, arm_root), "Phase-B packet arm environment drift")
            for key in ("HOME", "HF_HOME", "NUMBA_CACHE_DIR", "PYTHONPYCACHEPREFIX", "SYCL_CACHE_DIR", "TORCHINDUCTOR_CACHE_DIR", "TRANSFORMERS_CACHE", "TRITON_CACHE_DIR", "VLLM_CACHE_ROOT", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "TEMP", "TMP", "TMPDIR"):
                private = Path(card["environments"][arm][key])
                require(private.is_absolute() and private.is_relative_to(arm_root), "Phase-B private arm path escapes arm root")
            session = card["sessions"][arm]
            require(re.fullmatch(rf"Laguna{arm}Card{rank}[0-9a-f]{{32}}", session or "") is not None, "Phase-B session entropy/prefix drift")
            sessions.append(session)
    require(len(set(sessions)) == 16, "all 16 Phase-B sessions must be globally unique")
    predecessor_state = _open_phase_a_predecessor(binding, phase_a_path, phase_a_full_sha, aggregate_path, aggregate_sha)
    predecessor_evidence = _validate_phase_a_predecessor_state(predecessor_state)
    if not retain_predecessor:
        _close_phase_a_predecessor(predecessor_state)
        predecessor_state = None
    return {
        "body": body,
        "common": common,
        "phase_a_packet": phase_a_packet,
        "phase_a_full_sha256": phase_a_full_sha,
        "phase_a_predecessor": predecessor_evidence,
        "phase_a_predecessor_state": predecessor_state,
    }


def _source_bytes(identity: dict[str, str]) -> bytes:
    require(
        isinstance(identity, dict)
        and set(identity) == {"path", "sha256"}
        and _sha_value(identity["sha256"]),
        "tool source identity schema",
    )
    path = Path(identity["path"])
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= 8 * 1024 * 1024, f"unsafe tool source: {path}")
        raw = os.pread(descriptor, before.st_size, 0)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require(
        len(raw) == before.st_size
        and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode)
        and hashlib.sha256(raw).hexdigest() == identity["sha256"],
        f"tool source changed or hash drifted: {path}",
    )
    return raw


def _hash_retained(descriptor: int, size: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    while offset < size:
        block = os.pread(descriptor, min(1024 * 1024, size - offset), offset)
        require(bool(block), "short retained staged-tool read")
        digest.update(block)
        offset += len(block)
    return digest.hexdigest()


def _stage_tool_closure(directory: Path, body: dict[str, Any], phase_a_packet: dict[str, Any]) -> dict[str, Any]:
    """Copy the full Python closure once, seal it, and retain every descriptor."""
    stage = directory / "tool-stage"
    require(not stage.exists() and not stage.is_symlink(), "tool stage must be fresh")
    os.mkdir(stage, 0o700)
    source_identities = {
        "phase_b": body["tools"],
        "phase_a": {
            "runner": phase_a_packet["body"]["runner"],
            "analyzer": phase_a_packet["body"]["analyzer"],
        },
    }
    staged_files: dict[str, dict[str, str]] = {"phase_b": {}, "phase_a": {}}
    seen_names: dict[str, dict[str, str]] = {}
    for family, identities in source_identities.items():
        require(isinstance(identities, dict), f"{family} tool identities")
        for role, identity in identities.items():
            name = Path(identity["path"]).name
            require(name and "/" not in name and "\\" not in name, f"unsafe staged tool name: {family}/{role}")
            previous = seen_names.get(name)
            if previous is not None:
                require(previous == identity, f"colliding staged tool name: {name}")
            else:
                raw = _source_bytes(identity)
                exclusive_bytes(stage / name, raw)
                os.chmod(stage / name, 0o444, follow_symlinks=False)
                seen_names[name] = identity
            staged_files[family][role] = name
    closure = {
        "format": "laguna-m8-gather-sharded-phase-b-tool-closure-v1",
        "source_identities": source_identities,
        "staged_files": staged_files,
    }
    exclusive(stage / "tool-closure.json", closure)
    os.chmod(stage / "tool-closure.json", 0o444, follow_symlinks=False)
    os.chmod(stage, 0o555, follow_symlinks=False)
    stage_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    descriptors: dict[str, int] = {}
    signatures: dict[str, dict[str, Any]] = {}
    try:
        for name, identity in {**seen_names, "tool-closure.json": {"sha256": sha(stage / "tool-closure.json")}}.items():
            descriptor = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=stage_fd)
            metadata = os.fstat(descriptor)
            require(
                stat.S_ISREG(metadata.st_mode)
                and stat.S_IMODE(metadata.st_mode) == 0o444
                and _hash_retained(descriptor, metadata.st_size) == identity["sha256"],
                f"staged tool retained identity drift: {name}",
            )
            descriptors[name] = descriptor
            signatures[name] = {
                "sha256": identity["sha256"],
                "dev": metadata.st_dev,
                "inode": metadata.st_ino,
                "bytes": metadata.st_size,
                "mode": stat.S_IMODE(metadata.st_mode),
            }
    except BaseException:
        for descriptor in descriptors.values():
            os.close(descriptor)
        os.close(stage_fd)
        raise
    evidence = {
        "format": "laguna-m8-gather-sharded-phase-b-retained-tool-stage-v1",
        "path": str(stage),
        "source_identities": source_identities,
        "staged_files": staged_files,
        "retained_files": signatures,
        "directory_mode": 0o555,
    }
    return {"path": stage, "directory_fd": stage_fd, "descriptors": descriptors, "evidence": evidence}


def _validate_tool_stage(state: dict[str, Any]) -> dict[str, Any]:
    stage_metadata = os.fstat(state["directory_fd"])
    require(stat.S_ISDIR(stage_metadata.st_mode) and stat.S_IMODE(stage_metadata.st_mode) == 0o555, "retained tool-stage directory drift")
    expected = state["evidence"]["retained_files"]
    for name, descriptor in state["descriptors"].items():
        metadata = os.fstat(descriptor)
        record = expected[name]
        require(
            stat.S_ISREG(metadata.st_mode)
            and stat.S_IMODE(metadata.st_mode) == 0o444
            and metadata.st_dev == record["dev"]
            and metadata.st_ino == record["inode"]
            and metadata.st_size == record["bytes"]
            and _hash_retained(descriptor, metadata.st_size) == record["sha256"],
            f"retained tool stage changed: {name}",
        )
    return state["evidence"]


def _close_tool_stage(state: dict[str, Any]) -> None:
    for descriptor in state["descriptors"].values():
        os.close(descriptor)
    os.close(state["directory_fd"])


def argv(packet: Path, packet_sha: str, aggregate: Path, aggregate_sha: str, rank: int, arm: str, out: Path, environment: dict[str, str], session: str, tool_stage: Path | None = None, pinned_unitrace: str | None = None) -> list[str]:
    require(re.fullmatch(r"[A-Za-z0-9]{40,64}", session) is not None, "unitrace session must be frozen high-entropy alphanumeric")
    tool_stage = tool_stage or out.parent / "tool-stage"
    pinned_unitrace = pinned_unitrace or str(UNITRACE)
    assignments = [f"{key}={environment[key]}" for key in sorted(environment)]
    staged_fixture = tool_stage / TOOL_ROLES["fixture"]
    return ["/usr/bin/sudo", "-S", "-p", "", "-E", "--", "/usr/bin/env", "-i", *assignments, "/usr/bin/timeout", "--signal=TERM", "--kill-after=5s", f"{INNER_TIMEOUT}s", pinned_unitrace, "--device-timing", "--metric-query", "--group", "ComputeBasic", "--include-kernels", "MoeGather", "--verbose", "--pid", "--devices-to-sample", "0", "--follow-child-process", "0", "--start-paused", "--session", session, "--output", "unitrace", str(PYTHON), "-I", str(staged_fixture), "--packet", str(packet), "--packet-sha256", packet_sha, "--phase-a-aggregate", str(aggregate), "--phase-a-aggregate-sha256", aggregate_sha, "--rank", str(rank), "--arm", arm, "--out", str(out), "--unitrace", str(UNITRACE), "--session", session, "--tool-stage", str(tool_stage)]

def outputs(directory: Path, pid: int) -> tuple[Path, Path]:
    timing, metrics = directory / f"unitrace.{pid}", directory / f"unitrace.metrics.{pid}"
    require(not timing.is_symlink() and not metrics.is_symlink() and file_identity(timing)["bytes"] > 0 and file_identity(metrics)["bytes"] > 0, "unitrace two-file PID closure drift")
    extras = [name for name in os.listdir(directory) if name.startswith("unitrace") and name not in {timing.name, metrics.name}]
    require(not extras, "unexpected unitrace output")
    return timing, metrics


def _session_path(session: str) -> Path:
    require(re.fullmatch(r"[A-Za-z0-9]{40,64}", session) is not None, "unsafe unitrace session")
    return Path("/dev/shm") / f"uctrl{session}"


def _run_isolated(command: list[str], directory: Path) -> dict[str, Any]:
    """Return every terminal state and raw stream; never discard a failed attempt."""
    process: subprocess.Popen[bytes] | None = None
    stdout = stderr = b""
    timed_out = False
    error_type: str | None = None
    error_message: str | None = None
    termination: list[str] = []
    reaped = False
    group_dead = False

    def communicate_bounded(timeout: float) -> bool:
        nonlocal stdout, stderr, reaped, error_type, error_message
        require(process is not None, "process absent during bounded reap")
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            reaped = process.returncode is not None
            return reaped
        except subprocess.TimeoutExpired as error:
            stdout = error.output or stdout
            stderr = error.stderr or stderr
            if error_type is None:
                error_type, error_message = "UnreapedProcess", f"process did not reap within {timeout} seconds"
            return False

    def signal_group(selected: signal.Signals) -> None:
        require(process is not None, "process absent during group termination")
        try:
            os.killpg(process.pid, selected)
            termination.append(selected.name)
        except ProcessLookupError:
            termination.append(f"already_exited_before_{selected.name}")

    try:
        password = os.open(SUDO_PASSWORD, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            process = subprocess.Popen(command, cwd=directory, stdin=password, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        finally:
            os.close(password)
        try:
            stdout, stderr = process.communicate(timeout=OUTER_TIMEOUT)
            reaped = process.returncode is not None
        except subprocess.TimeoutExpired as error:
            timed_out, error_type, error_message = True, type(error).__name__, str(error)
            stdout, stderr = error.output or b"", error.stderr or b""
            signal_group(signal.SIGTERM)
            if not communicate_bounded(5):
                signal_group(signal.SIGKILL)
                communicate_bounded(15)
        except BaseException as error:
            error_type, error_message = type(error).__name__, str(error)
            signal_group(signal.SIGTERM)
            if not communicate_bounded(5):
                signal_group(signal.SIGKILL)
                communicate_bounded(15)
    except BaseException as error:
        if error_type is None:
            error_type, error_message = type(error).__name__, str(error)
    if process is not None:
        reaped = process.returncode is not None
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            group_dead = True
        except PermissionError:
            group_dead = False
        if not group_dead:
            if error_type is None:
                error_type, error_message = "LiveProcessGroup", "isolated process group survived terminal collection"
            signal_group(signal.SIGKILL)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                try:
                    os.killpg(process.pid, 0)
                except ProcessLookupError:
                    group_dead = True
                    break
                time.sleep(0.05)
    return {
        "process_started": process is not None,
        "pid": process.pid if process is not None else None,
        "returncode": process.returncode if process is not None else None,
        "reaped": reaped,
        "process_group_dead": group_dead,
        "timed_out": timed_out,
        "error_type": error_type,
        "error_message": error_message,
        "termination": termination,
        "stdout": stdout,
        "stderr": stderr,
    }

def one_arm(root: Path, packet_path: Path, packet_sha: str, aggregate_path: Path, aggregate_sha: str, body: dict[str, Any], common: dict[str, Any], phase_a_packet: dict[str, Any], rank: int, arm: str) -> dict[str, Any]:
    card_root = root / f"card{rank}"
    arm_index = ARMS.index(arm)
    if arm_index == 0:
        require(not card_root.exists() and not card_root.is_symlink(), "card root must be fresh")
        os.mkdir(card_root, 0o700)
    else:
        require(card_root.is_dir() and not card_root.is_symlink() and set(os.listdir(card_root)) == set(ARMS[:arm_index]), "card root prior-arm inventory drift")
    directory = card_root / arm
    require(not directory.exists() and not directory.is_symlink(), "arm directory must be fresh")
    os.mkdir(directory, 0o700)
    card = body["cards"][rank]
    environment, session = card["environments"][arm], card["sessions"][arm]
    out = directory / "fixture.json"
    shm = _session_path(session)
    tool_stage_state: dict[str, Any] | None = None
    unitrace_descriptor: int | None = None
    try:
        created_runtime = phase_a._prepare_runtime_directories(directory, environment)
        runtime_leaves = sorted({value for key, value in environment.items() if key in {"HOME", "HF_HOME", "NUMBA_CACHE_DIR", "PYTHONPYCACHEPREFIX", "SYCL_CACHE_DIR", "TORCHINDUCTOR_CACHE_DIR", "TRANSFORMERS_CACHE", "TRITON_CACHE_DIR", "VLLM_CACHE_ROOT", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "TEMP", "TMP", "TMPDIR"}})
        require(all(Path(path).is_dir() and not Path(path).is_symlink() and not os.listdir(path) for path in runtime_leaves), "fresh arm runtime leaf is not empty")
        exclusive(directory / "runtime-prelaunch.json", {"format": "laguna-m8-gather-sharded-phase-b-runtime-prelaunch-v1", "rank": rank, "arm": arm, "arm_root": str(directory), "created_directories": created_runtime, "empty_runtime_leaves": runtime_leaves, "fresh": True})
        tool_stage_state = _stage_tool_closure(directory, body, phase_a_packet)
        tool_stage_before = _validate_tool_stage(tool_stage_state)
        unitrace_descriptor = os.open(UNITRACE, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        unitrace_metadata = os.fstat(unitrace_descriptor)
        require(stat.S_ISREG(unitrace_metadata.st_mode) and _hash_retained(unitrace_descriptor, unitrace_metadata.st_size) == UNITRACE_SHA256, "retained unitrace launch descriptor drift")
        pinned_unitrace = f"/proc/{os.getpid()}/fd/{unitrace_descriptor}"
        unitrace_launch = {"configured_path": str(UNITRACE), "exec_path": pinned_unitrace, "sha256": UNITRACE_SHA256, "dev": unitrace_metadata.st_dev, "inode": unitrace_metadata.st_ino, "bytes": unitrace_metadata.st_size, "mode": stat.S_IMODE(unitrace_metadata.st_mode), "retained_through_child_exit": True}
        command = argv(packet_path, packet_sha, aggregate_path, aggregate_sha, rank, arm, out, environment, session, tool_stage_state["path"], pinned_unitrace)
        require(not os.path.lexists(shm), "unitrace session shared memory already exists; no deletion/reuse allowed")
        exclusive(directory / "session-prelaunch.json", {"format": "laguna-m8-gather-sharded-phase-b-session-prelaunch-v1", "session": session, "shm_path": str(shm), "absent": True, "checked_utc": now()})
        idle, status = continuous_strict_idle()
        require(status == 0 and idle.get("status") == "passed", "continuous 65-second strict-idle/cooling preflight failed")
        exclusive(directory / "current-idle-preflight.json", idle)
        completed = _run_isolated(command, directory)
        unitrace_after = os.fstat(unitrace_descriptor)
        require((unitrace_metadata.st_dev, unitrace_metadata.st_ino, unitrace_metadata.st_size, unitrace_metadata.st_mtime_ns, unitrace_metadata.st_mode) == (unitrace_after.st_dev, unitrace_after.st_ino, unitrace_after.st_size, unitrace_after.st_mtime_ns, unitrace_after.st_mode) and _hash_retained(unitrace_descriptor, unitrace_after.st_size) == UNITRACE_SHA256, "unitrace launch descriptor changed across child")
        tool_stage_after = _validate_tool_stage(tool_stage_state)
        require(tool_stage_after == tool_stage_before, "retained tool stage changed across child")
        exclusive_bytes(directory / "stdout.log", completed["stdout"])
        exclusive_bytes(directory / "stderr.log", completed["stderr"])
        process_terminal = {
            key: completed[key]
            for key in (
                "process_started", "pid", "returncode", "reaped",
                "process_group_dead", "timed_out", "error_type",
                "error_message", "termination",
            )
        }
        process_terminal.update({"format": "laguna-m8-gather-sharded-phase-b-process-terminal-v1", "stdout_sha256": sha(directory / "stdout.log"), "stderr_sha256": sha(directory / "stderr.log")})
        exclusive(directory / "process-terminal.json", process_terminal)
        require(completed["process_started"] is True and completed["reaped"] is True and completed["process_group_dead"] is True and completed["timed_out"] is False and completed["error_type"] is None and completed["returncode"] == 0, f"unitrace arm terminal failure: {process_terminal}")
        initial_pause = f"[INFO] Session {session} is paused\n".encode()
        require(completed["stderr"].count(initial_pause) == 1 and b"was not stopped before reusing" not in completed["stderr"], "fresh start-paused session acknowledgement missing/reused")
        require(not os.path.lexists(shm), "unitrace stop did not unlink owned session shared memory")
        exclusive(directory / "session-poststop.json", {"format": "laguna-m8-gather-sharded-phase-b-session-poststop-v1", "session": session, "shm_path": str(shm), "absent": True, "checked_utc": now()})
        record, _ = fixture.read_canonical(out)
        require(file_identity(out)["mode"] == fixture.FIXTURE_OUTPUT_MODE, "root-owned fixture evidence mode drift")
        require(record.get("format") == "laguna-m8-gather-sharded-phase-b-fixture-v3" and record.get("status") == "complete" and record.get("rank") == rank and record.get("arm") == arm and record.get("selected_gather_calls") == 611 and record.get("session") == session, "fixture closure drift")
        timing, metrics = outputs(directory, int(record["pid"]))
        manifest = {"format": "laguna-m8-gather-sharded-phase-b-arm-v3", "status": "complete", "rank": rank, "arm": arm, "packet_sha256": packet_sha, "phase_a_aggregate_sha256": aggregate_sha, "command": command, "environment": environment, "session": session, "unitrace_launch": unitrace_launch, "tool_stage": {"before": tool_stage_before, "after": tool_stage_after, "retained_through_child_exit": True}, "unitrace_returncode": 0, "normal_return_metric_flush_closed": True, "initial_start_paused_acknowledged": True, "fixture": record, "files": {path.name: manifest_entry(path) for path in (out, timing, metrics, directory / "current-idle-preflight.json", directory / "runtime-prelaunch.json", directory / "session-prelaunch.json", directory / "session-poststop.json", directory / "process-terminal.json", directory / "stdout.log", directory / "stderr.log")}}
        exclusive(directory / "manifest.json", manifest)
        return manifest
    except BaseException as exc:
        if not (directory / "stdout.log").exists():
            exclusive_bytes(directory / "stdout.log", b"")
        if not (directory / "stderr.log").exists():
            exclusive_bytes(directory / "stderr.log", b"")
        if not (directory / "process-terminal.json").exists():
            exclusive(directory / "process-terminal.json", {"format": "laguna-m8-gather-sharded-phase-b-process-terminal-v1", "process_started": False, "pid": None, "returncode": None, "reaped": False, "process_group_dead": False, "timed_out": False, "error_type": type(exc).__name__, "error_message": str(exc), "termination": [], "stdout_sha256": sha(directory / "stdout.log"), "stderr_sha256": sha(directory / "stderr.log")})
        exclusive(directory / "failure.json", {"format": "laguna-m8-gather-sharded-phase-b-arm-failure-v1", "status": "failed", "rank": rank, "arm": arm, "packet_sha256": packet_sha, "session": session, "shm_path": str(shm), "shm_present_after_failure": os.path.lexists(shm), "error_type": type(exc).__name__, "error": str(exc), "failed_utc": now()})
        raise
    finally:
        if unitrace_descriptor is not None:
            os.close(unitrace_descriptor)
        if tool_stage_state is not None:
            _close_tool_stage(tool_stage_state)


def _is_runtime_scratch(relative: str) -> bool:
    parts = Path(relative).parts
    return (
        len(parts) == 3
        and re.fullmatch(r"card[0-3]", parts[0]) is not None
        and parts[1] in ARMS
        and parts[2] == "scratch"
    )


def _scan_evidence_tree(root: Path) -> dict[str, Any]:
    """Retain the evidence namespace while never looking inside runtime scratch."""
    require(root.is_absolute(), "campaign evidence root must be absolute")
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    file_fds: dict[str, int] = {}
    directory_fds: dict[str, int] = {}
    files: list[dict[str, Any]] = []
    directories: list[dict[str, Any]] = []
    scratch_roots: list[dict[str, Any]] = []

    def walk(directory_fd: int, prefix: str) -> None:
        for name in sorted(os.listdir(directory_fd)):
            require(name not in {"", ".", ".."} and "/" not in name, "unsafe evidence entry name")
            relative = f"{prefix}/{name}" if prefix else name
            if _is_runtime_scratch(relative):
                descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory_fd)
                try:
                    metadata = os.fstat(descriptor)
                    require(stat.S_ISDIR(metadata.st_mode), f"runtime scratch root is not a directory: {relative}")
                    scratch_roots.append({"path": relative, "dev": metadata.st_dev, "inode": metadata.st_ino, "mode": stat.S_IMODE(metadata.st_mode)})
                finally:
                    os.close(descriptor)
                continue
            metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            require(not stat.S_ISLNK(metadata.st_mode), f"symlink outside excluded scratch: {relative}")
            if stat.S_ISDIR(metadata.st_mode):
                descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory_fd)
                retained = os.fstat(descriptor)
                require((metadata.st_dev, metadata.st_ino) == (retained.st_dev, retained.st_ino), f"evidence directory changed while opening: {relative}")
                directory_fds[relative] = descriptor
                directories.append({"path": relative, "dev": retained.st_dev, "inode": retained.st_ino, "mode": stat.S_IMODE(retained.st_mode)})
                walk(descriptor, relative)
                continue
            require(stat.S_ISREG(metadata.st_mode), f"nonregular file outside excluded scratch: {relative}")
            descriptor = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory_fd)
            retained = os.fstat(descriptor)
            require(stat.S_ISREG(retained.st_mode) and (metadata.st_dev, metadata.st_ino) == (retained.st_dev, retained.st_ino), f"evidence file changed while opening: {relative}")
            digest = _hash_retained(descriptor, retained.st_size)
            after = os.fstat(descriptor)
            require((retained.st_dev, retained.st_ino, retained.st_size, retained.st_mtime_ns, retained.st_mode) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode), f"evidence file changed while hashing: {relative}")
            file_fds[relative] = descriptor
            files.append({"path": relative, "sha256": digest, "bytes": retained.st_size})

    try:
        root_metadata = os.fstat(root_fd)
        require(stat.S_ISDIR(root_metadata.st_mode), "campaign evidence root is not a directory")
        walk(root_fd, "")
    except BaseException:
        for descriptor in (*file_fds.values(), *directory_fds.values()):
            os.close(descriptor)
        os.close(root_fd)
        raise
    return {
        "root_fd": root_fd,
        "root": {"dev": root_metadata.st_dev, "inode": root_metadata.st_ino, "mode": stat.S_IMODE(root_metadata.st_mode)},
        "file_fds": file_fds,
        "directory_fds": directory_fds,
        "files": sorted(files, key=lambda value: value["path"]),
        "directories": sorted(directories, key=lambda value: value["path"]),
        "scratch_roots": sorted(scratch_roots, key=lambda value: value["path"]),
    }


def _close_evidence_scan(scan: dict[str, Any]) -> None:
    for descriptor in (*scan["file_fds"].values(), *scan["directory_fds"].values()):
        os.close(descriptor)
    os.close(scan["root_fd"])


def _tree_inventory(root: Path) -> list[dict[str, Any]]:
    scan = _scan_evidence_tree(root)
    try:
        return scan["files"]
    finally:
        _close_evidence_scan(scan)


def _chmod_retained(descriptors: list[int], mode: int) -> None:
    pending: list[int] = []
    for descriptor in descriptors:
        try:
            os.fchmod(descriptor, mode)
        except PermissionError:
            pending.append(descriptor)
    for offset in range(0, len(pending), 64):
        batch = pending[offset:offset + 64]
        password = os.open(SUDO_PASSWORD, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            completed = subprocess.run(
                ["/usr/bin/sudo", "-S", "-p", "", "--", "/usr/bin/chmod", f"{mode:04o}", "--", *(f"/proc/{os.getpid()}/fd/{descriptor}" for descriptor in batch)],
                stdin=password,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=False,
            )
        finally:
            os.close(password)
        require(completed.returncode == 0 and completed.stdout == b"" and completed.stderr == b"", "failed to freeze retained root-owned campaign evidence")


def _freeze_tree(root: Path, inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scan = _scan_evidence_tree(root)
    try:
        require(scan["files"] == inventory, "registered evidence inventory changed before freeze")
        _chmod_retained(list(scan["file_fds"].values()), 0o444)
        _chmod_retained(list(scan["directory_fds"].values()), 0o555)
        expected = {entry["path"]: entry for entry in inventory}
        for relative, descriptor in scan["file_fds"].items():
            metadata = os.fstat(descriptor)
            entry = expected[relative]
            require(stat.S_ISREG(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) == 0o444 and metadata.st_size == entry["bytes"] and _hash_retained(descriptor, metadata.st_size) == entry["sha256"], f"frozen retained evidence verification drift: {relative}")
        for relative, descriptor in scan["directory_fds"].items():
            metadata = os.fstat(descriptor)
            require(stat.S_ISDIR(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) == 0o555, f"frozen retained evidence-directory drift: {relative}")
        return scan["scratch_roots"]
    finally:
        _close_evidence_scan(scan)


def _finalize_campaign(root: Path, terminal: dict[str, Any]) -> dict[str, Any]:
    require(not (root / "freeze-manifest.json").exists() and not (root / "campaign-terminal.json").exists(), "campaign terminal already exists")
    prior_scan = _scan_evidence_tree(root)
    try:
        prior_inventory = prior_scan["files"]
        excluded_scratch = prior_scan["scratch_roots"]
    finally:
        _close_evidence_scan(prior_scan)
    freeze_manifest = {"format": "laguna-m8-gather-sharded-phase-b-freeze-manifest-v1", "root": str(root), "prior_files": prior_inventory, "excluded_scratch_roots": excluded_scratch, "scratch_policy": "excluded_non_evidence_never_traversed_or_chmodded", "required_file_mode": 0o444, "required_directory_mode": 0o555}
    exclusive(root / "freeze-manifest.json", freeze_manifest)
    freeze_inventory = prior_inventory + [
        {"path": "freeze-manifest.json", **{key: value for key, value in manifest_entry(root / "freeze-manifest.json").items() if key in {"sha256", "bytes"}}},
    ]
    require(_freeze_tree(root, freeze_inventory) == excluded_scratch, "excluded scratch roots changed before evidence freeze")
    terminal = {**terminal, "freeze_manifest": {"path": str(root / "freeze-manifest.json"), "sha256": sha(root / "freeze-manifest.json")}, "required_file_mode": 0o444, "required_directory_mode": 0o555, "frozen_tree_verified_before_terminal": True}
    exclusive(root / "campaign-terminal.json", terminal)
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    terminal_fd = os.open("campaign-terminal.json", os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=root_fd)
    try:
        _chmod_retained([terminal_fd], 0o444)
        _chmod_retained([root_fd], 0o555)
    finally:
        os.close(terminal_fd)
        os.close(root_fd)
    terminal_identity = file_identity(root / "campaign-terminal.json")
    root_identity = os.stat(root, follow_symlinks=False)
    require(terminal_identity["mode"] == 0o444 and stat.S_ISDIR(root_identity.st_mode) and stat.S_IMODE(root_identity.st_mode) == 0o555, "final campaign terminal/root mode drift")
    return terminal


def run(packet_path: Path, packet_sha: str, aggregate_path: Path, aggregate_sha: str) -> dict[str, Any]:
    packet, aggregate = read(packet_path, packet_sha), read(aggregate_path, aggregate_sha)
    authorization = validate(packet, packet_path, packet_sha, aggregate, aggregate_path, aggregate_sha, retain_predecessor=True)
    body, common = authorization["body"], authorization["common"]
    phase_a_packet = authorization["phase_a_packet"]
    predecessor = authorization["phase_a_predecessor"]
    predecessor_state = authorization["phase_a_predecessor_state"]
    require(isinstance(predecessor_state, dict), "retained Phase-A predecessor state absent")
    root = Path(body["output_root"])
    require(root.is_absolute() and root.parent == RUNS and not root.exists(), "fresh internal-NVMe Phase-B root required")
    complete: list[dict[str, Any]] = []
    try:
        storage = operational.attest_internal_nvme(RUNS)
        boot_id = _boot_id()
        root.mkdir(mode=0o700)
        exclusive(root / "preimport-seal.json", {"format": "laguna-m8-gather-sharded-phase-b-preimport-v3", "packet_sha256": packet_sha, "phase_a_aggregate_sha256": aggregate_sha, "phase_a_predecessor": predecessor, "all_phase_a_packet_shared_campaign_fixture_bundle_profiler_identity_checks_complete": True, "torch_or_native_imported_by_fixture": False, "boot_id": boot_id, "storage": storage})
        for rank in range(4):
            for arm in ARMS:
                require(_validate_phase_a_predecessor_state(predecessor_state) == predecessor, "Phase-A predecessor changed before arm")
                complete.append(one_arm(root, packet_path, packet_sha, aggregate_path, aggregate_sha, body, common, phase_a_packet, rank, arm))
                require(_validate_phase_a_predecessor_state(predecessor_state) == predecessor, "Phase-A predecessor changed after arm")
        final_idle, final_status = operational.execute_preflight()
        require(final_status == 0, "post-arm global idle preflight failed")
        validate_operational_sample(final_idle)
        exclusive(root / "post-arm-idle-preflight.json", final_idle)
        require(_boot_id() == boot_id, "boot identity changed during Phase-B capture")
        report = {"format": "laguna-m8-gather-sharded-phase-b-capture-v3", "status": "complete_pending_mandatory_in_process_analysis", "packet_sha256": packet_sha, "phase_a_aggregate_sha256": aggregate_sha, "phase_a_predecessor": predecessor, "boot_id": boot_id, "storage": storage, "post_arm_idle_preflight": {"path": str(root / "post-arm-idle-preflight.json"), "sha256": sha(root / "post-arm-idle-preflight.json")}, "arms": [{"ordinal": index, "rank": item["rank"], "arm": item["arm"], "manifest": str(root / f"card{item['rank']}" / item["arm"] / "manifest.json")} for index, item in enumerate(complete)]}
        exclusive(root / "capture.json", report)
        require(analyzer is not None, "sealed Phase-B analyzer was not bootstrapped")
        analysis = analyzer.analyze(packet_path, packet_sha, aggregate_path, aggregate_sha, root / "capture.json")
        analyzer.write(root / "analysis.json", analysis)
        require(_validate_phase_a_predecessor_state(predecessor_state) == predecessor, "Phase-A predecessor changed before Phase-B terminal")
        terminal = _finalize_campaign(root, {"format": "laguna-m8-gather-sharded-phase-b-terminal-v3", "status": "passed" if analysis["passed"] is True else "failed_counter_no_retry", "passed": analysis["passed"] is True, "packet_sha256": packet_sha, "phase_a_aggregate_sha256": aggregate_sha, "phase_a_predecessor": predecessor, "capture": {"path": str(root / "capture.json"), "sha256": sha(root / "capture.json")}, "analysis": {"path": str(root / "analysis.json"), "sha256": sha(root / "analysis.json")}, "completed_arms": len(complete), "boot_id": boot_id, "storage": storage, "endpoint_authorized": False})
        require(terminal["passed"] is True, "mandatory Phase-B analysis failed; campaign frozen with no retry")
        return terminal
    except BaseException as exc:
        if root.is_dir() and not (root / "campaign-terminal.json").exists():
            _finalize_campaign(root, {"format": "laguna-m8-gather-sharded-phase-b-terminal-v3", "status": "failed_stop_no_retry", "passed": False, "packet_sha256": packet_sha, "phase_a_aggregate_sha256": aggregate_sha, "phase_a_predecessor": predecessor, "completed_arms": len(complete), "error_type": type(exc).__name__, "error": str(exc), "failed_utc": now(), "endpoint_authorized": False})
        raise
    finally:
        _close_phase_a_predecessor(predecessor_state)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--packet-sha256", required=True)
    parser.add_argument("--phase-a-aggregate", type=Path, required=True)
    parser.add_argument("--phase-a-aggregate-sha256", required=True)
    parser.add_argument("--sealed-self-fd", type=int)
    args = parser.parse_args()
    packet = read(args.packet, args.packet_sha256)
    _ensure_sealed_self(packet, args.packet, args.packet_sha256, args.phase_a_aggregate, args.phase_a_aggregate_sha256, args.sealed_self_fd)
    _bootstrap_modules(packet, args.packet_sha256)
    print(json.dumps(run(args.packet, args.packet_sha256, args.phase_a_aggregate, args.phase_a_aggregate_sha256), sort_keys=True))
    return 0

if __name__ == "__main__":
    sys.exit(main())
