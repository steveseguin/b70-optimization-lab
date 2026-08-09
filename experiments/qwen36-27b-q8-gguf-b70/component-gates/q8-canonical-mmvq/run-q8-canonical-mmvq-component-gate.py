#!/usr/bin/env python3
"""Build and run the Qwen3.6 Q8 c2 canonical-MMVQ component gate.

The three worker invocations are deliberately separate processes. One supplies
a selector-off M=1 oracle, one bootstraps through selector-on M=1, and the last
starts with recurrent BA so M=2 must bootstrap a virgin weight correctly.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import mmap
import os
import re
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


K = 6144
M = 5120
FLOAT_BYTES = 4
SELECTOR = "GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ"
FIRST_HIT_PREFIX = "SYCL_Q8_0_C2_CANONICAL_MMVQ first-hit:"
VIOLATION_PREFIX = "SYCL_Q8_0_C2_CANONICAL_MMVQ violation:"
SUMMARY_PREFIX = "SYCL_Q8_0_C2_CANONICAL_MMVQ summary:"
ROUTE_FIELDS = (
    "flat_dispatches",
    "recurrent_dispatches",
    "flat_multicol_suppressed",
    "recurrent_dmmv_suppressed",
    "reorder_ready_dispatches",
    "single_col_mmvq_calls",
    "violations",
)
GGML_RUNTIME_OBJECTS = (
    "libggml.so",
    "libggml-base.so",
    "libggml-cpu.so",
    "libggml-sycl.so",
)
EXPECTED_ROUTES = {
    "flat_dispatches": 1,
    "recurrent_dispatches": 1,
    "flat_multicol_suppressed": 1,
    "recurrent_dmmv_suppressed": 1,
    "reorder_ready_dispatches": 2,
    "single_col_mmvq_calls": 4,
    "violations": 0,
}
EXPECTED_SELECTOR_CONTRACT = {
    "supported": True,
    "default": "0",
    "values": ["0", "1"],
    "scope": "Q8_0/F32 MUL_MAT with exactly two vectors in the recognized flat or recurrent layouts",
    "fail_closed": True,
}
SANITIZED_PREFIXES = ("GGML_", "SYCL_", "ZE_", "ZES_", "UR_")
KERNEL_FAULT_PATTERN = re.compile(
    r"xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|Fault response|"
    r"VM.*fault|PCIe.*AER|RAS.*error|UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST",
    re.IGNORECASE,
)
WORKER_FAULT_PATTERN = re.compile(
    r"UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST|out of memory|"
    r"segmentation fault|core dumped|Aborted",
    re.IGNORECASE,
)


class GateError(RuntimeError):
    """A fail-closed gate error."""


class GateSignal(GateError):
    """A termination signal converted into a cleanup-aware gate error."""


def raise_on_termination_signal(signum: int, _frame: Any) -> None:
    raise GateSignal(f"received termination signal {signal.Signals(signum).name}")


@contextlib.contextmanager
def cleanup_aware_termination_signals():
    previous = {
        signum: signal.signal(signum, raise_on_termination_signal)
        for signum in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def run_checked(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        rendered = " ".join(command)
        raise GateError(
            f"command failed with exit {result.returncode}: {rendered}\n"
            f"stdout:\n{result.stdout.decode(errors='replace')}\n"
            f"stderr:\n{result.stderr.decode(errors='replace')}"
        )
    return result


def load_oneapi_environment(setvars: Path) -> dict[str, str]:
    if not setvars.is_file():
        raise GateError(f"oneAPI environment script is missing: {setvars}")
    # The path is supplied as argv[1], not interpolated into shell source text.
    result = run_checked(
        [
            "/bin/bash",
            "--noprofile",
            "--norc",
            "-c",
            'set +u; source "$1" --force >/dev/null; env -0',
            "q8-component-gate",
            str(setvars),
        ]
    )
    environment: dict[str, str] = {}
    for item in result.stdout.split(b"\0"):
        if not item:
            continue
        key, separator, value = item.partition(b"=")
        if not separator:
            raise GateError("oneAPI environment contained a malformed entry")
        environment[key.decode()] = value.decode()
    return environment


def worker_environment(
    oneapi_env: dict[str, str],
    library_dir: Path,
    gpu_index: int,
    *,
    selector_enabled: bool = True,
) -> dict[str, str]:
    environment = dict(oneapi_env)
    for name in list(environment):
        if (
            name in {"LD_PRELOAD", "ONEAPI_DEVICE_SELECTOR", "QWEN36_GPU_LEASE_FD"}
            or name.startswith(SANITIZED_PREFIXES)
        ):
            environment.pop(name)

    old_library_path = environment.get("LD_LIBRARY_PATH", "")
    environment.update(
        {
            "LD_LIBRARY_PATH": str(library_dir) + (f":{old_library_path}" if old_library_path else ""),
            "ONEAPI_DEVICE_SELECTOR": "level_zero:*",
            "ZE_AFFINITY_MASK": str(gpu_index),
            "GGML_SYCL_ENABLE_DNN": "0",
            "GGML_SYCL_ENABLE_OPT": "1",
            "GGML_SYCL_ENABLE_GRAPH": "0",
            "GGML_SYCL_PRIORITIZE_DMMV": "0",
            SELECTOR: "1" if selector_enabled else "0",
        }
    )
    return environment


def library_environment(oneapi_env: dict[str, str], library_dir: Path) -> dict[str, str]:
    """Return an origin-first environment for linking and dependency attestation."""
    environment = dict(oneapi_env)
    environment.pop("LD_PRELOAD", None)
    old_library_path = environment.get("LD_LIBRARY_PATH", "")
    environment["LD_LIBRARY_PATH"] = str(library_dir) + (
        f":{old_library_path}" if old_library_path else ""
    )
    return environment


@contextlib.contextmanager
def selected_gpu_lease(gpu_index: int):
    lease_dir = Path(f"/run/user/{os.getuid()}/qwen36-b70-gpu-leases")
    lease_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    lease_path = (lease_dir / f"gpu{gpu_index}.lock").resolve()
    inherited_raw = os.environ.get("QWEN36_GPU_LEASE_FD")

    if inherited_raw is not None:
        if not inherited_raw.isdigit():
            raise GateError("QWEN36_GPU_LEASE_FD must be numeric")
        descriptor = int(inherited_raw)
        descriptor_path = Path(f"/proc/{os.getpid()}/fd/{descriptor}")
        try:
            actual_path = descriptor_path.resolve(strict=True)
        except OSError as error:
            raise GateError(f"cannot resolve inherited GPU lease descriptor: {error}") from error
        if actual_path != lease_path:
            raise GateError(f"inherited GPU lease path mismatch: {actual_path} != {lease_path}")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise GateError(f"inherited GPU lease is not exclusively held: {error}") from error
        yield {"mode": "inherited", "path": str(lease_path), "fd": descriptor}
        return

    flags = os.O_WRONLY | os.O_CREAT | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(lease_path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise GateError(f"GPU lease is not a regular file: {lease_path}")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise GateError(f"GPU {gpu_index} is leased by another Qwen process") from error
        yield {"mode": "acquired", "path": str(lease_path), "fd": descriptor}
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def parse_gpu_used_mib(text: str) -> int:
    for line in text.splitlines():
        if "GPU Memory Used" not in line:
            continue
        fields = line.split("|")
        if len(fields) < 3:
            break
        value = fields[2].strip()
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
            break
        return int(float(value))
    raise GateError("could not parse GPU Memory Used from xpu-smi output")


def sample_gpu_once(
    gpu_index: int,
    label: str,
    evidence_dir: Path,
    environment: dict[str, str],
    idle_max_mib: int,
) -> dict[str, Any]:
    stdout_path = evidence_dir / f"xpu-smi-{label}.stdout.txt"
    stderr_path = evidence_dir / f"xpu-smi-{label}.stderr.txt"
    lifecycle = run_bounded_to_files(
        ["xpu-smi", "stats", "-d", str(gpu_index)],
        stdout_path,
        stderr_path,
        environment=environment,
        timeout_seconds=20,
    )
    write_summary(evidence_dir / f"xpu-smi-{label}.lifecycle.json", lifecycle)
    if lifecycle["timed_out"]:
        raise GateError(f"bounded {label} xpu-smi sample timed out")
    if lifecycle["survivor_pids"]:
        raise GateError(f"bounded {label} xpu-smi sample left survivors: {lifecycle['survivor_pids']}")
    if lifecycle["cleanup_required"]:
        raise GateError(f"bounded {label} xpu-smi sample required cleanup")
    if lifecycle["returncode"] != 0:
        raise GateError(f"bounded {label} xpu-smi sample exited {lifecycle['returncode']}")
    used_mib = parse_gpu_used_mib(stdout_path.read_text(errors="replace"))
    return {
        "label": label,
        "gpu_index": gpu_index,
        "used_mib": used_mib,
        "idle_max_mib": idle_max_mib,
        "idle": used_mib <= idle_max_mib,
        "process_lifecycle": lifecycle,
    }


def process_group_members(process_group: int) -> list[int]:
    members = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat_text = (entry / "stat").read_text()
            closing = stat_text.rfind(")")
            if closing < 0:
                continue
            fields = stat_text[closing + 2 :].split()
            if len(fields) < 3:
                continue
            if int(fields[2]) == process_group:
                members.append(int(entry.name))
        except (OSError, ValueError):
            continue
    return sorted(members)


def terminate_process_group(
    process_group: int,
    grace_seconds: int = 10,
    leader: subprocess.Popen[Any] | None = None,
) -> dict[str, Any]:
    forced_kill = False
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process_group, signal.SIGTERM)
    deadline = time.monotonic() + grace_seconds
    if leader is not None:
        leader.poll()
    survivors = process_group_members(process_group)
    while survivors and time.monotonic() < deadline:
        time.sleep(0.1)
        if leader is not None:
            leader.poll()
        survivors = process_group_members(process_group)
    if survivors:
        forced_kill = True
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process_group, signal.SIGKILL)
        deadline = time.monotonic() + 5
        while survivors and time.monotonic() < deadline:
            time.sleep(0.1)
            if leader is not None:
                leader.poll()
            survivors = process_group_members(process_group)
    return {"forced_kill": forced_kill, "survivor_pids": survivors}


def run_bounded_to_files(
    command: list[str],
    stdout_path: Path,
    stderr_path: Path,
    *,
    environment: dict[str, str],
    timeout_seconds: int,
) -> dict[str, Any]:
    with stdout_path.open("wb") as stdout_stream, stderr_path.open("wb") as stderr_stream:
        process: subprocess.Popen[Any] | None = None
        try:
            process = subprocess.Popen(
                command,
                env=environment,
                stdout=stdout_stream,
                stderr=stderr_stream,
                start_new_session=True,
            )
            process_group = process.pid
            deadline = time.monotonic() + timeout_seconds
            while process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.1)
            timed_out = process.poll() is None
            cleanup_required = False
            cleanup = {"forced_kill": False, "survivor_pids": []}
            if timed_out:
                cleanup_required = True
                cleanup = terminate_process_group(process_group, leader=process)
            process.poll()
            survivors = process_group_members(process_group)
            if survivors:
                cleanup_required = True
                cleanup = terminate_process_group(process_group, leader=process)
                survivors = cleanup["survivor_pids"]
            return {
                "pid": process.pid,
                "process_group": process_group,
                "returncode": process.returncode,
                "timed_out": timed_out,
                "cleanup_required": cleanup_required,
                "forced_kill": cleanup["forced_kill"],
                "survivor_pids": survivors,
                "clean_exit_no_survivor": (
                    process.returncode == 0 and not timed_out and not cleanup_required and not survivors
                ),
            }
        except BaseException as error:
            if process is not None:
                previous_handlers = {
                    signum: signal.signal(signum, signal.SIG_IGN)
                    for signum in (signal.SIGINT, signal.SIGTERM)
                }
                try:
                    cleanup = terminate_process_group(process.pid, leader=process)
                    process.poll()
                    interruption = {
                        "pid": process.pid,
                        "process_group": process.pid,
                        "returncode": process.returncode,
                        "interrupted": True,
                        "interruption_type": type(error).__name__,
                        "cleanup_required": True,
                        "forced_kill": cleanup["forced_kill"],
                        "survivor_pids": cleanup["survivor_pids"],
                        "clean_exit_no_survivor": False,
                    }
                    with contextlib.suppress(OSError):
                        write_summary(
                            stdout_path.with_name(f"{stdout_path.stem}.interruption.json"),
                            interruption,
                        )
                finally:
                    for signum, previous in previous_handlers.items():
                        signal.signal(signum, previous)
            raise


def capture_fault_window(start_epoch: int, evidence_dir: Path, label: str) -> dict[str, Any]:
    journal_path = evidence_dir / f"kernel-journal-{label}.txt"
    journal_stderr_path = evidence_dir / f"kernel-journal-{label}.stderr.log"
    lifecycle = run_bounded_to_files(
        ["journalctl", "-k", "--since", f"@{start_epoch}", "--no-pager"],
        journal_path,
        journal_stderr_path,
        environment=dict(os.environ),
        timeout_seconds=30,
    )
    write_summary(evidence_dir / f"kernel-journal-{label}.lifecycle.json", lifecycle)
    journal_text = journal_path.read_text(errors="replace")
    kernel_hits = [line for line in journal_text.splitlines() if KERNEL_FAULT_PATTERN.search(line)]
    (evidence_dir / f"device-error-scan-{label}.txt").write_text(
        "\n".join(kernel_hits) + ("\n" if kernel_hits else "")
    )

    worker_hits = []
    for path in sorted(evidence_dir.glob("*/std*.log")):
        for line in path.read_text(errors="replace").splitlines():
            if WORKER_FAULT_PATTERN.search(line):
                worker_hits.append(f"{path.relative_to(evidence_dir)}:{line}")
    (evidence_dir / f"worker-error-scan-{label}.txt").write_text(
        "\n".join(worker_hits) + ("\n" if worker_hits else "")
    )
    journal_command_passed = bool(lifecycle["clean_exit_no_survivor"])
    return {
        "journal_command_passed": journal_command_passed,
        "journal_lifecycle": lifecycle,
        "kernel_fault_count": len(kernel_hits),
        "worker_fault_count": len(worker_hits),
        "passed": journal_command_passed and not kernel_hits and not worker_hits,
    }


def source_identity(source_dir: Path) -> dict[str, Any]:
    head = run_checked(["git", "-C", str(source_dir), "rev-parse", "HEAD"]).stdout.decode().strip()
    status = run_checked(
        ["git", "-C", str(source_dir), "status", "--porcelain=v1", "--untracked-files=all"]
    ).stdout
    diff = run_checked(["git", "-C", str(source_dir), "diff", "--binary", "HEAD", "--"]).stdout
    sycl_source = source_dir / "ggml" / "src" / "ggml-sycl" / "ggml-sycl.cpp"
    if not sycl_source.is_file():
        raise GateError(f"candidate SYCL source is missing: {sycl_source}")
    return {
        "head": head,
        "status_sha256": sha256_bytes(status),
        "status_line_count": len(status.splitlines()),
        "tracked_diff_sha256": sha256_bytes(diff),
        "ggml_sycl_cpp_sha256": sha256_file(sycl_source),
    }


def assert_source_identity_unchanged(before: dict[str, Any], after: dict[str, Any]) -> None:
    if before != after:
        raise GateError("candidate source identity changed while the component gate was running")


def assert_candidate_markers(source_dir: Path, sycl_library: Path) -> None:
    source = source_dir / "ggml" / "src" / "ggml-sycl" / "ggml-sycl.cpp"
    if not source.is_file():
        raise GateError(f"candidate SYCL source is missing: {source}")
    source_text = source.read_text(errors="replace")
    for marker in (SELECTOR, FIRST_HIT_PREFIX, VIOLATION_PREFIX, SUMMARY_PREFIX):
        if marker not in source_text:
            raise GateError(f"candidate source is missing observability marker: {marker}")

    with sycl_library.open("rb") as stream:
        with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
            for marker in (SELECTOR, FIRST_HIT_PREFIX, VIOLATION_PREFIX, SUMMARY_PREFIX):
                if mapped.find(marker.encode()) < 0:
                    raise GateError(f"candidate libggml-sycl is missing observability marker: {marker}")


def build_component(
    component_dir: Path,
    component_build_dir: Path,
    source_dir: Path,
    ggml_library_dir: Path,
    environment: dict[str, str],
    evidence_dir: Path,
) -> Path:
    component_build_dir.mkdir(parents=True, exist_ok=True)
    configure = run_checked(
        [
            "cmake",
            "-S",
            str(component_dir),
            "-B",
            str(component_build_dir),
            f"-DGGML_SOURCE_DIR={source_dir}",
            f"-DGGML_LIBRARY_DIR={ggml_library_dir}",
            "-DCMAKE_BUILD_TYPE=Release",
        ],
        env=environment,
    )
    (evidence_dir / "cmake-configure.stdout.log").write_bytes(configure.stdout)
    (evidence_dir / "cmake-configure.stderr.log").write_bytes(configure.stderr)
    build = run_checked(
        [
            "cmake",
            "--build",
            str(component_build_dir),
            "--target",
            "q8-canonical-mmvq-component-gate",
            "--parallel",
            "4",
        ],
        env=environment,
        timeout=600,
    )
    (evidence_dir / "cmake-build.stdout.log").write_bytes(build.stdout)
    (evidence_dir / "cmake-build.stderr.log").write_bytes(build.stderr)
    executable = component_build_dir / "q8-canonical-mmvq-component-gate"
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise GateError(f"component executable was not built: {executable}")
    return executable


def parse_ldd(output: str) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("linux-vdso.so"):
            continue
        if "=>" not in line:
            continue
        soname, right = (item.strip() for item in line.split("=>", 1))
        if right.startswith("not found"):
            raise GateError(f"unresolved runtime dependency: {soname}")
        match = re.match(r"(/\S+)\s+\(0x[0-9a-fA-F]+\)$", right)
        if not match:
            raise GateError(f"cannot parse ldd line: {raw_line!r}")
        resolved[soname] = Path(match.group(1)).resolve()
    return resolved


def verify_runtime_mapping(
    executable: Path,
    ggml_library_dir: Path,
    environment: dict[str, str],
    evidence_dir: Path,
) -> dict[str, Any]:
    result = run_checked(["ldd", str(executable)], env=environment)
    (evidence_dir / "component.ldd.txt").write_bytes(result.stdout)
    parsed = parse_ldd(result.stdout.decode(errors="replace"))
    library_dir = ggml_library_dir.resolve()
    expected_links = {stem: library_dir / stem for stem in GGML_RUNTIME_OBJECTS}
    mapped: dict[str, Any] = {}
    for stem, expected_link in expected_links.items():
        matches = [(soname, path) for soname, path in parsed.items() if soname == stem or soname.startswith(stem + ".")]
        if len(matches) != 1:
            raise GateError(f"expected exactly one ldd mapping for {stem}, observed {matches}")
        soname, actual = matches[0]
        expected = expected_link.resolve(strict=True)
        if not expected.is_relative_to(library_dir):
            raise GateError(f"selected runtime link escapes its directory: {expected_link} -> {expected}")
        if actual != expected:
            raise GateError(f"{soname} mapped outside the selected runtime: {actual} != {expected}")
        mapped[stem] = {
            "soname": soname,
            "link_path": str(expected_link),
            "resolved_path": str(actual),
            "size_bytes": actual.stat().st_size,
            "sha256": sha256_file(actual),
        }
    return mapped


def validate_runtime_manifest(
    manifest_path: Path,
    ggml_library_dir: Path,
    mapped: dict[str, Any],
    source_dir: Path,
    source: dict[str, Any],
) -> dict[str, Any]:
    metadata = manifest_path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise GateError(f"runtime manifest is not a regular file: {manifest_path}")
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as error:
        raise GateError(f"runtime manifest is not valid JSON: {manifest_path}: {error}") from error
    if not isinstance(manifest, dict):
        raise GateError("runtime manifest root must be an object")
    if manifest.get("runtime_bundle_schema_version") != 1:
        raise GateError("runtime manifest schema must be runtime_bundle_schema_version=1")
    if source.get("status_line_count") != 0:
        raise GateError("candidate source must be clean for a sealed runtime binding")
    if manifest.get("llama_cpp_commit") != source.get("head"):
        raise GateError("runtime manifest llama_cpp_commit does not match the candidate source HEAD")
    source_provenance = manifest.get("source_provenance")
    if not isinstance(source_provenance, dict):
        raise GateError("runtime manifest source_provenance must be an object")
    if source_provenance.get("ggml_sycl_cpp_sha256") != source.get("ggml_sycl_cpp_sha256"):
        raise GateError("runtime manifest GGML SYCL source hash does not match the candidate source")
    selector_contracts = manifest.get("experimental_controls")
    if not isinstance(selector_contracts, dict):
        raise GateError("runtime manifest experimental_controls must be an object")
    if selector_contracts.get(SELECTOR) != EXPECTED_SELECTOR_CONTRACT:
        raise GateError("runtime manifest does not declare the exact canonical-MMVQ selector contract")
    policy = manifest.get("runtime_loader_policy")
    if policy != {"mode": "origin-first", "variable": "LD_LIBRARY_PATH"}:
        raise GateError(f"runtime manifest does not declare the required origin-first policy: {policy!r}")
    objects = manifest.get("origin_shared_objects")
    if not isinstance(objects, list):
        raise GateError("runtime manifest origin_shared_objects must be a list")

    library_dir = ggml_library_dir.resolve(strict=True)
    matched: dict[str, Any] = {}
    for stem in GGML_RUNTIME_OBJECTS:
        entries = [
            item
            for item in objects
            if isinstance(item, dict)
            and isinstance(item.get("soname"), str)
            and (item["soname"] == stem or item["soname"].startswith(stem + "."))
        ]
        if len(entries) != 1:
            raise GateError(f"runtime manifest must contain exactly one {stem} entry; observed {len(entries)}")
        entry = entries[0]
        declared_path = entry.get("resolved_path")
        declared_size = entry.get("size_bytes")
        declared_sha = entry.get("sha256")
        if not isinstance(declared_path, str) or not declared_path.startswith("$ORIGIN/"):
            raise GateError(f"runtime manifest {stem} resolved_path must be $ORIGIN-relative")
        if not isinstance(declared_size, int) or declared_size < 0:
            raise GateError(f"runtime manifest {stem} has an invalid size_bytes")
        if not isinstance(declared_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", declared_sha):
            raise GateError(f"runtime manifest {stem} has an invalid SHA-256")
        expected_path = (library_dir / declared_path.removeprefix("$ORIGIN/")).resolve(strict=True)
        if not expected_path.is_relative_to(library_dir):
            raise GateError(f"runtime manifest {stem} escapes the selected library directory")
        observed = mapped[stem]
        mismatches = []
        if Path(observed["resolved_path"]) != expected_path:
            mismatches.append("resolved_path")
        if observed["size_bytes"] != declared_size:
            mismatches.append("size_bytes")
        if observed["sha256"] != declared_sha:
            mismatches.append("sha256")
        if mismatches:
            raise GateError(f"selected runtime disagrees with manifest for {stem}: {mismatches}")
        matched[stem] = {
            "manifest_soname": entry["soname"],
            "resolved_path": str(expected_path),
            "size_bytes": declared_size,
            "sha256": declared_sha,
        }
    return {
        "path": str(manifest_path),
        "size_bytes": len(manifest_bytes),
        "sha256": sha256_bytes(manifest_bytes),
        "runtime_loader_policy": policy,
        "source_binding": {
            "source_dir": str(source_dir),
            "head": source["head"],
            "ggml_sycl_cpp_sha256": source["ggml_sycl_cpp_sha256"],
            "selector_contract": EXPECTED_SELECTOR_CONTRACT,
        },
        "matched_objects": matched,
    }


def assert_manifest_identity_unchanged(binding: dict[str, Any]) -> None:
    path = Path(binding["path"])
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise GateError(f"runtime manifest stopped being a regular file: {path}")
    if metadata.st_size != binding["size_bytes"] or sha256_file(path) != binding["sha256"]:
        raise GateError("runtime manifest changed while the component gate was running")


def assert_runtime_identity_unchanged(runtime: dict[str, Any]) -> None:
    for stem in GGML_RUNTIME_OBJECTS:
        recorded = runtime[stem]
        link_path = Path(recorded["link_path"])
        try:
            resolved = link_path.resolve(strict=True)
        except OSError as error:
            raise GateError(f"selected runtime link changed or disappeared for {stem}: {error}") from error
        if resolved != Path(recorded["resolved_path"]):
            raise GateError(f"selected runtime link target changed for {stem}")
        if resolved.stat().st_size != recorded["size_bytes"] or sha256_file(resolved) != recorded["sha256"]:
            raise GateError(f"selected runtime object changed for {stem}")


def parse_route_summary_fields(payload: str) -> dict[str, int]:
    pairs = []
    for token in payload.strip().split():
        match = re.fullmatch(r"([a-z][a-z0-9_]*)=([0-9]+)", token)
        if match is None:
            raise GateError(f"route summary contains a malformed token: {token!r}")
        pairs.append(match.groups())
    names = [name for name, _value in pairs]
    if len(names) != len(set(names)):
        raise GateError("route summary contains a duplicate field")
    if set(names) != set(ROUTE_FIELDS):
        raise GateError(
            f"route summary fields differ: expected {sorted(ROUTE_FIELDS)}, observed {sorted(names)}"
        )
    return {name: int(value) for name, value in pairs}


def parse_selector_echo(lines: list[str], expected: int) -> bool:
    visible = [line for line in lines if f"{SELECTOR}:" in line]
    if len(visible) > 1:
        raise GateError(f"expected at most one selector startup marker, observed {len(visible)}")
    if not visible:
        return False
    match = re.search(rf"{re.escape(SELECTOR)}:\s*([0-9]+)(?:\s|$)", visible[0])
    if match is None:
        raise GateError(f"malformed selector startup marker: {visible[0]!r}")
    observed = int(match.group(1))
    if observed != expected:
        raise GateError(
            f"candidate startup selector echo disagrees with the launcher: {observed} != {expected}"
        )
    return True


def parse_route_log(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    # GGML's common logger may prefix these lines, and verbosity can suppress
    # the startup echo. Execution identity is therefore bound by the sanitized
    # child environment; any startup echo that is visible must agree with it.
    startup_echo_observed = parse_selector_echo(lines, 1)
    violations = [line for line in lines if VIOLATION_PREFIX in line]
    if violations:
        raise GateError(f"candidate emitted {len(violations)} route violation marker(s)")

    first_hit_lines = [line for line in lines if FIRST_HIT_PREFIX in line]
    first_hits: dict[str, dict[str, str]] = {}
    for line in first_hit_lines:
        payload = line[line.index(FIRST_HIT_PREFIX) + len(FIRST_HIT_PREFIX) :].strip()
        match = re.fullmatch(
            r"layout=(flat|recurrent) path=reordered_single_col_mmvq "
            r"reorder_ready=1 calls_per_dispatch=2 "
            r"src0=qwen36-q8-control-weight-6144x5120 "
            r"src0_ne=\[6144,5120,1,1\] "
            r"src1_ne=(\[[0-9,]+\]) dst_ne=(\[[0-9,]+\])",
            payload,
        )
        if match is None:
            raise GateError(f"malformed or noncanonical first-hit marker: {payload!r}")
        layout, src1_ne, dst_ne = match.groups()
        if layout in first_hits:
            raise GateError(f"duplicate first-hit marker for layout {layout}")
        expected_dimensions = {
            "flat": ("[6144,2,1,1]", "[5120,2,1,1]"),
            "recurrent": ("[6144,1,2,1]", "[5120,1,2,1]"),
        }
        if (src1_ne, dst_ne) != expected_dimensions[layout]:
            raise GateError(
                f"first-hit dimensions for {layout} are not model-exact: "
                f"src1={src1_ne}, dst={dst_ne}"
            )
        fields = {
            "layout": layout,
            "path": "reordered_single_col_mmvq",
            "reorder_ready": "1",
            "calls_per_dispatch": "2",
            "src0": "qwen36-q8-control-weight-6144x5120",
            "src0_ne": "[6144,5120,1,1]",
            "src1_ne": src1_ne,
            "dst_ne": dst_ne,
        }
        first_hits[layout] = fields
    if set(first_hits) != {"flat", "recurrent"}:
        raise GateError(f"missing per-layout first-hit markers: observed {sorted(first_hits)}")

    summary_lines = [line for line in lines if SUMMARY_PREFIX in line]
    if len(summary_lines) != 1:
        raise GateError(f"expected one route summary, observed {len(summary_lines)}")
    routes = parse_route_summary_fields(
        summary_lines[0][summary_lines[0].index(SUMMARY_PREFIX) + len(SUMMARY_PREFIX) :]
    )
    if routes != EXPECTED_ROUTES:
        raise GateError(f"route counter mismatch: expected {EXPECTED_ROUTES}, observed {routes}")

    dispatches = routes["flat_dispatches"] + routes["recurrent_dispatches"]
    if routes["flat_multicol_suppressed"] != routes["flat_dispatches"]:
        raise GateError("not every flat multi-column dispatch was suppressed")
    if routes["recurrent_dmmv_suppressed"] != routes["recurrent_dispatches"]:
        raise GateError("not every recurrent DMMV dispatch was suppressed")
    if routes["reorder_ready_dispatches"] != dispatches:
        raise GateError("not every controlled dispatch observed a ready reordered weight")
    if routes["single_col_mmvq_calls"] != 2 * dispatches:
        raise GateError("controlled dispatches did not issue exactly two single-column MMVQ calls")
    return {"startup_echo_observed": startup_echo_observed, "first_hits": first_hits, "summary": routes}


def parse_selector_off_log(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    startup_echo_observed = parse_selector_echo(lines, 0)
    forbidden = [
        line
        for line in lines
        if FIRST_HIT_PREFIX in line or SUMMARY_PREFIX in line or VIOLATION_PREFIX in line
    ]
    if forbidden:
        raise GateError(f"selector-off worker emitted {len(forbidden)} canonical route marker(s)")
    return {"startup_echo_observed": startup_echo_observed, "canonical_markers_observed": 0}


def parse_worker_record(stdout: str, expected_order: str) -> dict[str, Any]:
    records = []
    for line in stdout.splitlines():
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("schema_version") == 1 and "bootstrap_order" in value:
            records.append(value)
    if len(records) != 1:
        raise GateError(f"expected one worker result record, observed {len(records)}")
    record = records[0]
    expected = {
        "schema_version": 1,
        "bootstrap_order": expected_order,
        "weight_type": "Q8_0",
        "weight_shape": [K, M, 1, 1],
        "flat_input_shape": [K, 2, 1, 1],
        "recurrent_input_shape": [K, 1, 2, 1],
        "inputs_distinct": True,
        "bitwise_comparisons": 0 if expected_order == "selector-off-m1-ab" else 4,
        "bitwise_equal": True,
    }
    for field, expected_value in expected.items():
        if record.get(field) != expected_value:
            raise GateError(
                f"worker record field {field} mismatch: expected {expected_value!r}, observed {record.get(field)!r}"
            )
    if not isinstance(record.get("pid"), int) or record["pid"] <= 0:
        raise GateError("worker record is missing a valid PID")
    if not isinstance(record.get("device_name"), str) or not record["device_name"]:
        raise GateError("worker record is missing the device name")
    if not isinstance(record.get("device_description"), str) or not record["device_description"]:
        raise GateError("worker record is missing the device description")
    return record


def require_regular_file(path: Path, expected_size: int) -> bytes:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise GateError(f"component output is not a regular file: {path}")
    if metadata.st_size != expected_size:
        raise GateError(f"component output size mismatch for {path}: {metadata.st_size} != {expected_size}")
    return path.read_bytes()


def require_equal(left: bytes, right: bytes, label: str) -> None:
    if left == right:
        return
    first = next(index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1])
    raise GateError(f"bitwise mismatch for {label} at byte {first}")


def inspect_worker_outputs(worker_dir: Path, order: str, *, k: int = K, m: int = M) -> dict[str, Any]:
    vector_bytes = k * FLOAT_BYTES
    output_bytes = m * FLOAT_BYTES
    input_a = require_regular_file(worker_dir / "input-a.f32", vector_bytes)
    input_b = require_regular_file(worker_dir / "input-b.f32", vector_bytes)
    if input_a == input_b:
        raise GateError("retained F32 inputs A and B are not distinct")

    if order == "selector-off-m1-ab":
        names_and_sizes = {
            "m1-a": output_bytes,
            "m1-b": output_bytes,
        }
        data = {
            name: require_regular_file(worker_dir / f"{name}.f32", size)
            for name, size in names_and_sizes.items()
        }
    elif order == "m1-first-ab":
        names_and_sizes = {
            "m1-a": output_bytes,
            "m1-b": output_bytes,
            "flat-ab": 2 * output_bytes,
            "recurrent-ab": 2 * output_bytes,
        }
        data = {name: require_regular_file(worker_dir / f"{name}.f32", size) for name, size in names_and_sizes.items()}
        require_equal(data["flat-ab"][:output_bytes], data["m1-a"], "forward flat column 0/M1 A")
        require_equal(data["flat-ab"][output_bytes:], data["m1-b"], "forward flat column 1/M1 B")
        require_equal(data["recurrent-ab"][:output_bytes], data["m1-a"], "forward recurrent sequence 0/M1 A")
        require_equal(data["recurrent-ab"][output_bytes:], data["m1-b"], "forward recurrent sequence 1/M1 B")
    elif order == "batched-first-ba":
        names_and_sizes = {
            "recurrent-ba": 2 * output_bytes,
            "flat-ba": 2 * output_bytes,
            "m1-b": output_bytes,
            "m1-a": output_bytes,
        }
        data = {name: require_regular_file(worker_dir / f"{name}.f32", size) for name, size in names_and_sizes.items()}
        require_equal(data["recurrent-ba"][:output_bytes], data["m1-b"], "reverse recurrent sequence 0/M1 B")
        require_equal(data["recurrent-ba"][output_bytes:], data["m1-a"], "reverse recurrent sequence 1/M1 A")
        require_equal(data["flat-ba"][:output_bytes], data["m1-b"], "reverse flat column 0/M1 B")
        require_equal(data["flat-ba"][output_bytes:], data["m1-a"], "reverse flat column 1/M1 A")
    else:
        raise GateError(f"unsupported output inspection order: {order}")

    return {
        "input_a_sha256": sha256_bytes(input_a),
        "input_b_sha256": sha256_bytes(input_b),
        "outputs": {name: {"size_bytes": len(value), "sha256": sha256_bytes(value)} for name, value in data.items()},
        "raw": data,
    }


def compare_fresh_processes(
    forward: dict[str, Any], reverse: dict[str, Any], *, m: int = M
) -> dict[str, bool]:
    output_bytes = m * FLOAT_BYTES
    checks = {
        "input_a_equal": forward["input_a_sha256"] == reverse["input_a_sha256"],
        "input_b_equal": forward["input_b_sha256"] == reverse["input_b_sha256"],
        "m1_a_equal": forward["raw"]["m1-a"] == reverse["raw"]["m1-a"],
        "m1_b_equal": forward["raw"]["m1-b"] == reverse["raw"]["m1-b"],
        "flat_ab_vs_reversed_ba_equal": (
            forward["raw"]["flat-ab"]
            == reverse["raw"]["flat-ba"][output_bytes:] + reverse["raw"]["flat-ba"][:output_bytes]
        ),
        "recurrent_ab_vs_reversed_ba_equal": (
            forward["raw"]["recurrent-ab"]
            == reverse["raw"]["recurrent-ba"][output_bytes:]
            + reverse["raw"]["recurrent-ba"][:output_bytes]
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise GateError(f"fresh-process reverse-bootstrap comparison failed: {failed}")
    return checks


def compare_selector_off_oracle(
    selector_off: dict[str, Any],
    forward: dict[str, Any],
    reverse: dict[str, Any],
) -> dict[str, bool]:
    checks = {
        "off_vs_forward_input_a_equal": selector_off["input_a_sha256"] == forward["input_a_sha256"],
        "off_vs_forward_input_b_equal": selector_off["input_b_sha256"] == forward["input_b_sha256"],
        "off_vs_reverse_input_a_equal": selector_off["input_a_sha256"] == reverse["input_a_sha256"],
        "off_vs_reverse_input_b_equal": selector_off["input_b_sha256"] == reverse["input_b_sha256"],
        "selector_off_vs_forward_m1_a_equal": selector_off["raw"]["m1-a"] == forward["raw"]["m1-a"],
        "selector_off_vs_forward_m1_b_equal": selector_off["raw"]["m1-b"] == forward["raw"]["m1-b"],
        "selector_off_vs_reverse_m1_a_equal": selector_off["raw"]["m1-a"] == reverse["raw"]["m1-a"],
        "selector_off_vs_reverse_m1_b_equal": selector_off["raw"]["m1-b"] == reverse["raw"]["m1-b"],
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise GateError(f"selector-off c1 oracle comparison failed: {failed}")
    return checks


def run_worker(
    executable: Path,
    order: str,
    worker_dir: Path,
    environment: dict[str, str],
    timeout: int,
    *,
    selector_enabled: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    expected_selector = "1" if selector_enabled else "0"
    if environment.get(SELECTOR) != expected_selector:
        raise GateError(
            f"{order} worker environment has selector={environment.get(SELECTOR)!r}, "
            f"expected {expected_selector}"
        )
    worker_dir.mkdir()
    artifact_dir = worker_dir / "artifacts"
    artifact_dir.mkdir()
    lifecycle = run_bounded_to_files(
        [
            str(executable),
            "--bootstrap-order",
            order,
            "--output-dir",
            str(artifact_dir),
            "--gpu-ordinal",
            "0",
        ],
        worker_dir / "stdout.log",
        worker_dir / "stderr.log",
        environment=environment,
        timeout_seconds=timeout,
    )
    (worker_dir / "lifecycle.json").write_text(json.dumps(lifecycle, indent=2, sort_keys=True) + "\n")
    if lifecycle["timed_out"]:
        raise GateError(f"{order} worker timed out; cleanup evidence is in {worker_dir}")
    if lifecycle["survivor_pids"]:
        raise GateError(f"{order} worker left process-group survivors: {lifecycle['survivor_pids']}")
    if lifecycle["cleanup_required"]:
        raise GateError(f"{order} worker required unexpected descendant cleanup")
    if lifecycle["returncode"] != 0:
        raise GateError(f"{order} worker exited {lifecycle['returncode']}; see {worker_dir}")
    stdout = (worker_dir / "stdout.log").read_text(errors="replace")
    stderr = (worker_dir / "stderr.log").read_text(errors="replace")
    record = parse_worker_record(stdout, order)
    if record["pid"] != lifecycle["pid"]:
        raise GateError(
            f"{order} worker PID record does not match the launched process: "
            f"{record['pid']} != {lifecycle['pid']}"
        )
    route = (
        parse_route_log(stdout + "\n" + stderr)
        if selector_enabled
        else parse_selector_off_log(stdout + "\n" + stderr)
    )
    outputs = inspect_worker_outputs(artifact_dir, order)
    outputs.pop("raw")
    return record, route, outputs


def serializable_output_view(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "raw"}


def worker_lifecycle_allows_postflight(status: dict[str, Any]) -> bool:
    return bool(
        status.get("returncode") == 0
        and status.get("clean_exit_no_survivor") is True
        and status.get("timed_out") is False
        and status.get("cleanup_required") is False
        and status.get("forced_kill") is False
        and status.get("survivor_pids") == []
    )


def execute_component_gate(
    executable: Path,
    environment: dict[str, str],
    evidence_dir: Path,
    gpu_index: int,
    idle_max_mib: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    start_epoch = int(time.time())
    lifecycle: dict[str, Any] = {
        "start_epoch": start_epoch,
        "selected_gpu_lease": None,
        "preflight": None,
        "postflight": None,
        "vram_returned": False,
        "fault_window": None,
        "inter_worker_fault_windows": {},
        "workers": {},
        "passed": False,
    }
    lifecycle_path = evidence_dir / "lifecycle-summary.json"
    execution_error: Exception | None = None
    selector_off_record = None
    selector_off_route = None
    forward_record = None
    forward_route = None
    reverse_record = None
    reverse_route = None
    selector_off_outputs = None
    forward_outputs = None
    reverse_outputs = None
    cross_process = None
    selector_off_oracle = None
    inter_worker_probe_safe = True

    with selected_gpu_lease(gpu_index) as lease:
        lifecycle["selected_gpu_lease"] = {key: value for key, value in lease.items() if key != "fd"}
        try:
            preflight = sample_gpu_once(gpu_index, "preflight", evidence_dir, environment, idle_max_mib)
        except (GateError, OSError) as error:
            lifecycle["preflight_error"] = str(error)
            lifecycle["postflight_status"] = "SKIPPED_AFTER_PREFLIGHT_FAILURE"
            try:
                lifecycle["fault_window"] = capture_fault_window(
                    start_epoch, evidence_dir, "after-preflight-failure"
                )
            except (GateError, OSError, subprocess.TimeoutExpired) as fault_error:
                lifecycle["fault_window_error"] = str(fault_error)
            write_summary(lifecycle_path, lifecycle)
            raise
        lifecycle["preflight"] = preflight
        if not preflight["idle"]:
            lifecycle["postflight_status"] = "SKIPPED_GPU_NOT_IDLE_NO_WORKLOAD_LAUNCHED"
            try:
                lifecycle["fault_window"] = capture_fault_window(
                    start_epoch, evidence_dir, "gpu-not-idle"
                )
            except (GateError, OSError, subprocess.TimeoutExpired) as fault_error:
                lifecycle["fault_window_error"] = str(fault_error)
            write_summary(lifecycle_path, lifecycle)
            raise GateError(
                f"selected GPU {gpu_index} is not idle: {preflight['used_mib']} MiB > {idle_max_mib} MiB"
            )

        try:
            selector_off_dir = evidence_dir / "selector-off-m1-ab"
            forward_dir = evidence_dir / "m1-first-ab"
            reverse_dir = evidence_dir / "batched-first-ba"
            selector_off_environment = dict(environment)
            selector_off_environment[SELECTOR] = "0"
            selector_off_record, selector_off_route, _ = run_worker(
                executable,
                "selector-off-m1-ab",
                selector_off_dir,
                selector_off_environment,
                timeout_seconds,
                selector_enabled=False,
            )
            try:
                off_checkpoint = capture_fault_window(
                    start_epoch, evidence_dir, "after-selector-off-m1"
                )
            except (GateError, OSError) as checkpoint_error:
                inter_worker_probe_safe = False
                lifecycle["inter_worker_fault_windows"]["after-selector-off-m1"] = {
                    "passed": False,
                    "error": str(checkpoint_error),
                }
                raise
            lifecycle["inter_worker_fault_windows"]["after-selector-off-m1"] = off_checkpoint
            if not off_checkpoint["passed"]:
                inter_worker_probe_safe = False
                raise GateError("passive fault checkpoint after selector-off M1 worker did not pass")

            forward_record, forward_route, _ = run_worker(
                executable, "m1-first-ab", forward_dir, environment, timeout_seconds
            )
            try:
                forward_checkpoint = capture_fault_window(
                    start_epoch, evidence_dir, "after-m1-first-ab"
                )
            except (GateError, OSError) as checkpoint_error:
                inter_worker_probe_safe = False
                lifecycle["inter_worker_fault_windows"]["after-m1-first-ab"] = {
                    "passed": False,
                    "error": str(checkpoint_error),
                }
                raise
            lifecycle["inter_worker_fault_windows"]["after-m1-first-ab"] = forward_checkpoint
            if not forward_checkpoint["passed"]:
                inter_worker_probe_safe = False
                raise GateError("passive fault checkpoint after first selector-on worker did not pass")

            reverse_record, reverse_route, _ = run_worker(
                executable, "batched-first-ba", reverse_dir, environment, timeout_seconds
            )
            worker_pids = {
                selector_off_record["pid"],
                forward_record["pid"],
                reverse_record["pid"],
            }
            if len(worker_pids) != 3:
                raise GateError("fresh-process requirement failed: worker PIDs are not distinct")
            device_names = {
                selector_off_record["device_name"],
                forward_record["device_name"],
                reverse_record["device_name"],
            }
            device_descriptions = {
                selector_off_record["device_description"],
                forward_record["device_description"],
                reverse_record["device_description"],
            }
            if len(device_names) != 1 or len(device_descriptions) != 1:
                raise GateError("fresh workers selected different GGML devices")

            # Re-read retained bytes for the independent parent comparison.
            selector_off_outputs = inspect_worker_outputs(
                selector_off_dir / "artifacts", "selector-off-m1-ab"
            )
            forward_outputs = inspect_worker_outputs(forward_dir / "artifacts", "m1-first-ab")
            reverse_outputs = inspect_worker_outputs(reverse_dir / "artifacts", "batched-first-ba")
            cross_process = compare_fresh_processes(forward_outputs, reverse_outputs)
            selector_off_oracle = compare_selector_off_oracle(
                selector_off_outputs, forward_outputs, reverse_outputs
            )
        except (GateError, OSError, subprocess.TimeoutExpired, ValueError) as error:
            execution_error = error
        finally:
            lifecycle_probe_safe = inter_worker_probe_safe
            for worker_name in ("selector-off-m1-ab", "m1-first-ab", "batched-first-ba"):
                worker_dir = evidence_dir / worker_name
                worker_lifecycle = evidence_dir / worker_name / "lifecycle.json"
                if worker_lifecycle.is_file():
                    try:
                        worker_status = json.loads(worker_lifecycle.read_text())
                        lifecycle["workers"][worker_name] = worker_status
                        if not worker_lifecycle_allows_postflight(worker_status):
                            lifecycle_probe_safe = False
                    except (OSError, json.JSONDecodeError) as error:
                        lifecycle["workers"][worker_name] = {"lifecycle_read_error": str(error)}
                        lifecycle_probe_safe = False
                elif worker_dir.exists():
                    lifecycle["workers"][worker_name] = {"lifecycle_missing": True}
                    lifecycle_probe_safe = False

            try:
                fault_window = capture_fault_window(start_epoch, evidence_dir, "before-postflight")
                lifecycle["pre_postflight_fault_window"] = fault_window
            except (GateError, OSError, subprocess.TimeoutExpired) as error:
                lifecycle["fault_window_error"] = str(error)
                fault_window = None

            passive_probe_safe = lifecycle_probe_safe and fault_window is not None and fault_window["passed"]
            lifecycle["passive_probe_safe"] = passive_probe_safe
            if not passive_probe_safe:
                lifecycle["postflight_status"] = "SKIPPED_PROBE_UNSAFE_AFTER_PASSIVE_CLASSIFICATION"
                lifecycle["fault_window"] = fault_window
                if execution_error is None:
                    execution_error = GateError(
                        "passive lifecycle/fault classification made an active postflight probe unsafe"
                    )
            else:
                lifecycle["postflight_status"] = "ATTEMPTED_AFTER_CLEAN_PASSIVE_CLASSIFICATION"
                try:
                    postflight = sample_gpu_once(gpu_index, "postflight", evidence_dir, environment, idle_max_mib)
                    lifecycle["postflight"] = postflight
                    lifecycle["vram_returned"] = bool(
                        postflight["idle"]
                        and postflight["used_mib"] <= preflight["used_mib"] + idle_max_mib
                    )
                    if not lifecycle["vram_returned"] and execution_error is None:
                        execution_error = GateError(
                            "selected GPU did not return to its bounded preflight VRAM envelope"
                        )
                except (GateError, OSError) as error:
                    lifecycle["postflight_error"] = str(error)
                    if execution_error is None:
                        execution_error = error
                try:
                    final_fault_window = capture_fault_window(start_epoch, evidence_dir, "final")
                    lifecycle["fault_window"] = final_fault_window
                    if not final_fault_window["passed"] and execution_error is None:
                        execution_error = GateError("final passive kernel/worker fault window did not pass")
                except (GateError, OSError, subprocess.TimeoutExpired) as error:
                    lifecycle["final_fault_window_error"] = str(error)
                    if execution_error is None:
                        execution_error = error

            lifecycle["passed"] = execution_error is None
            write_summary(lifecycle_path, lifecycle)

    if execution_error is not None:
        raise GateError(str(execution_error))
    if any(not item.get("clean_exit_no_survivor") for item in lifecycle["workers"].values()):
        raise GateError("one or more workers did not exit cleanly without survivors")
    if set(lifecycle["workers"]) != {
        "selector-off-m1-ab",
        "m1-first-ab",
        "batched-first-ba",
    }:
        raise GateError("lifecycle evidence is missing one or more fresh workers")
    assert selector_off_record is not None and selector_off_route is not None
    assert forward_record is not None and forward_route is not None
    assert reverse_record is not None and reverse_route is not None
    assert selector_off_outputs is not None
    assert forward_outputs is not None and reverse_outputs is not None and cross_process is not None
    assert selector_off_oracle is not None
    return {
        "workers": {
            "selector_off_m1_ab": {
                "record": selector_off_record,
                "route_activation": selector_off_route,
                "artifacts": serializable_output_view(selector_off_outputs),
                "lifecycle": lifecycle["workers"]["selector-off-m1-ab"],
            },
            "m1_first_ab": {
                "record": forward_record,
                "route_activation": forward_route,
                "artifacts": serializable_output_view(forward_outputs),
                "lifecycle": lifecycle["workers"]["m1-first-ab"],
            },
            "batched_first_ba": {
                "record": reverse_record,
                "route_activation": reverse_route,
                "artifacts": serializable_output_view(reverse_outputs),
                "lifecycle": lifecycle["workers"]["batched-first-ba"],
            },
        },
        "fresh_processes": True,
        "selector_off_c1_oracle_checks": selector_off_oracle,
        "cross_process_bitwise_checks": cross_process,
        "lifecycle": lifecycle,
    }


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True, help="candidate llama.cpp source worktree")
    parser.add_argument(
        "--ggml-library-dir",
        type=Path,
        required=True,
        help="exact runtime directory containing libggml*.so (the authoritative GPU gate uses the hybrid)",
    )
    parser.add_argument(
        "--runtime-manifest",
        type=Path,
        help="manifest sealing the selected runtime; mandatory with --execute",
    )
    parser.add_argument("--component-build-dir", type=Path, required=True, help="out-of-tree build for this component")
    parser.add_argument("--output-dir", type=Path, required=True, help="new evidence directory")
    parser.add_argument("--gpu-index", type=int, default=0, help="physical ZE_AFFINITY_MASK index")
    parser.add_argument("--gpu-idle-max-mib", type=int, default=256)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--oneapi-setvars", type=Path, default=Path("/opt/intel/oneapi/setvars.sh"))
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--build-only", action="store_true", help="compile and map dependencies without GPU discovery")
    action.add_argument("--execute", action="store_true", help="run all three fresh-process GPU gates")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    component_dir = Path(__file__).resolve().parent
    for name in ("source_dir", "ggml_library_dir", "component_build_dir", "output_dir"):
        value = getattr(args, name).expanduser().resolve()
        setattr(args, name, value)
    if args.runtime_manifest is not None:
        args.runtime_manifest = args.runtime_manifest.expanduser().resolve()
    if args.gpu_index not in range(4):
        raise SystemExit("--gpu-index must be 0, 1, 2, or 3")
    if args.gpu_idle_max_mib < 0 or args.gpu_idle_max_mib > 256:
        raise SystemExit("--gpu-idle-max-mib must be from 0 through 256")
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be positive")
    if not args.source_dir.is_dir():
        raise SystemExit(f"candidate source directory is missing: {args.source_dir}")
    if not args.ggml_library_dir.is_dir():
        raise SystemExit(f"GGML library directory is missing: {args.ggml_library_dir}")
    if args.execute and args.runtime_manifest is None:
        raise SystemExit("--runtime-manifest is mandatory with --execute")
    if args.runtime_manifest is not None and not args.runtime_manifest.is_file():
        raise SystemExit(f"runtime manifest is missing: {args.runtime_manifest}")
    if args.output_dir.exists():
        raise SystemExit(f"refusing to reuse output directory: {args.output_dir}")
    if args.component_build_dir.exists():
        raise SystemExit(f"refusing to reuse component build directory: {args.component_build_dir}")
    if args.component_build_dir.is_relative_to(args.source_dir):
        raise SystemExit("--component-build-dir must be outside the candidate source tree")
    if args.output_dir.is_relative_to(args.source_dir):
        raise SystemExit("--output-dir must be outside the candidate source tree")
    if args.component_build_dir.is_relative_to(args.ggml_library_dir):
        raise SystemExit("--component-build-dir must be outside the selected runtime directory")
    if args.output_dir.is_relative_to(args.ggml_library_dir):
        raise SystemExit("--output-dir must be outside the selected runtime directory")
    if args.output_dir.is_relative_to(args.component_build_dir) or args.component_build_dir.is_relative_to(
        args.output_dir
    ):
        raise SystemExit("--output-dir and --component-build-dir must not contain one another")
    args.output_dir.mkdir(parents=True)
    summary_path = args.output_dir / "summary.json"
    summary: dict[str, Any] = {
        "schema_version": 1,
        "gate": "qwen36_q8_canonical_mmvq_component",
        "classification": "component_diagnostic_only",
        "performance_promotable": False,
        "passed": False,
        "mode": "execute" if args.execute else "build-only",
    }
    identity_before: dict[str, Any] | None = None
    runtime: dict[str, Any] | None = None
    manifest_binding: dict[str, Any] | None = None

    try:
        oneapi_env = load_oneapi_environment(args.oneapi_setvars)
        link_environment = library_environment(oneapi_env, args.ggml_library_dir)
        identity_before = source_identity(args.source_dir)
        executable = build_component(
            component_dir,
            args.component_build_dir,
            args.source_dir,
            args.ggml_library_dir,
            link_environment,
            args.output_dir,
        )
        runtime = verify_runtime_mapping(
            executable, args.ggml_library_dir, link_environment, args.output_dir
        )
        if args.runtime_manifest is not None:
            manifest_binding = validate_runtime_manifest(
                args.runtime_manifest,
                args.ggml_library_dir,
                runtime,
                args.source_dir,
                identity_before,
            )
        summary.update(
            {
                "source": identity_before,
                "component_source_sha256": sha256_file(component_dir / "q8-canonical-mmvq-component-gate.cpp"),
                "component_executable": {
                    "path": str(executable),
                    "size_bytes": executable.stat().st_size,
                    "sha256": sha256_file(executable),
                },
                "ggml_library_dir": str(args.ggml_library_dir),
                "selected_runtime_objects": runtime,
                "runtime_identity_sealed": manifest_binding is not None,
                "runtime_manifest_binding": manifest_binding,
            }
        )
        sycl_library = Path(runtime["libggml-sycl.so"]["resolved_path"])
        assert_candidate_markers(args.source_dir, sycl_library)
        summary["observability_markers_present"] = True

        if args.build_only:
            assert_source_identity_unchanged(identity_before, source_identity(args.source_dir))
            assert_runtime_identity_unchanged(runtime)
            if manifest_binding is not None:
                assert_manifest_identity_unchanged(manifest_binding)
            summary["passed"] = True
            summary["result"] = (
                "BUILD_ONLY_PASS_NO_GPU_EXECUTION_SEALED_RUNTIME"
                if manifest_binding is not None
                else "BUILD_ONLY_PASS_NO_GPU_EXECUTION_UNSEALED_RUNTIME"
            )
            write_summary(summary_path, summary)
            return 0

        environment = worker_environment(oneapi_env, args.ggml_library_dir, args.gpu_index)
        summary["execution_environment"] = {
            "gpu_index": args.gpu_index,
            "oneapi_device_selector": environment["ONEAPI_DEVICE_SELECTOR"],
            "ze_affinity_mask": environment["ZE_AFFINITY_MASK"],
            "ggml_sycl_enable_dnn": environment["GGML_SYCL_ENABLE_DNN"],
            "ggml_sycl_enable_opt": environment["GGML_SYCL_ENABLE_OPT"],
            "ggml_sycl_enable_graph": environment["GGML_SYCL_ENABLE_GRAPH"],
            "ggml_sycl_prioritize_dmmv": environment["GGML_SYCL_PRIORITIZE_DMMV"],
            "ggml_sycl_q8_0_c2_canonical_mmvq": environment[SELECTOR],
        }

        with cleanup_aware_termination_signals():
            execution = execute_component_gate(
                executable,
                environment,
                args.output_dir,
                args.gpu_index,
                args.gpu_idle_max_mib,
                args.timeout_seconds,
            )
        assert_source_identity_unchanged(identity_before, source_identity(args.source_dir))
        assert_runtime_identity_unchanged(runtime)
        assert manifest_binding is not None
        assert_manifest_identity_unchanged(manifest_binding)

        summary.update(
            {
                **execution,
                "passed": True,
                "result": "COMPONENT_GATE_PASS",
                "limitations": [
                    "This gate proves only the isolated Q8_0 MUL_MAT shape and routes.",
                    "A candidate-runtime-matched c1 oracle and sealed model-level c2 crossover remain mandatory.",
                ],
            }
        )
        write_summary(summary_path, summary)
        return 0
    except (GateError, OSError, subprocess.TimeoutExpired, ValueError) as error:
        summary["error"] = str(error)
        if identity_before is not None:
            try:
                identity_after_failure = source_identity(args.source_dir)
                summary["source_identity_unchanged_after_failure"] = identity_after_failure == identity_before
                summary["source_after_failure"] = identity_after_failure
            except (GateError, OSError):
                summary["source_identity_after_failure_unavailable"] = True
        lifecycle_path = args.output_dir / "lifecycle-summary.json"
        if lifecycle_path.is_file():
            try:
                summary["lifecycle"] = json.loads(lifecycle_path.read_text())
            except (OSError, json.JSONDecodeError):
                summary["lifecycle_read_failed"] = True
        if runtime is not None:
            try:
                assert_runtime_identity_unchanged(runtime)
                summary["runtime_identity_unchanged_after_failure"] = True
            except (GateError, OSError) as runtime_error:
                summary["runtime_identity_unchanged_after_failure"] = False
                summary["runtime_identity_after_failure_error"] = str(runtime_error)
        if manifest_binding is not None:
            try:
                assert_manifest_identity_unchanged(manifest_binding)
                summary["runtime_manifest_unchanged_after_failure"] = True
            except (GateError, OSError) as manifest_error:
                summary["runtime_manifest_unchanged_after_failure"] = False
                summary["runtime_manifest_after_failure_error"] = str(manifest_error)
        write_summary(summary_path, summary)
        print(f"component gate failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
