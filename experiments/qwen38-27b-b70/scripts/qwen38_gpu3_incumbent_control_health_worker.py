#!/usr/bin/env python3
"""Bounded GPU3 stock FlashAttention health worker.

This worker is intentionally subordinate to an external supervisor.  It loads
the frozen exact-shape qualifier in memory, runs only its KV-128 warmup prefix,
and stops immediately after the first explicit ``torch.xpu.synchronize``
returns.  It never selects or imports a candidate stage.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import socket
import sys
import time
from typing import Any, Iterable


SCHEMA_CONTRACT = "qwen38-gpu3-incumbent-control-health-contract-v1"
SCHEMA_RECEIPT = "qwen38-gpu3-incumbent-control-health-phase-v1"
SCHEMA_RESULT = "qwen38-gpu3-incumbent-control-health-worker-result-v1"
SCHEMA_FAILURE = "qwen38-gpu3-incumbent-control-health-worker-failure-v1"
REPO = Path("/home/steve/llm-optimizations")
BASE_QUALIFIER = Path(
    "/home/steve/llm-optimizations/experiments/qwen38-27b-b70/scripts/"
    "qwen38_mtp5_m6_fa_operator.py"
)
SUPERVISOR = REPO / (
    "experiments/qwen38-27b-b70/scripts/"
    "qwen38_gpu3_incumbent_control_health_supervisor.py"
)
BASE_QUALIFIER_SHA256 = (
    "0dd7b945ef35a11ff4d0a1ec085e604920524b996d539e089d89b4a019a5de1f"
)
CONTROL_STAGE = Path("/home/steve/staged-xpu-commitfix-graphfa-composite-20260820")
CONTROL_GRAPH_MANIFEST = REPO / (
    "repro/qwen38-27b-autoround-int4-b70/manifests/"
    "staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256"
)
CONTROL_GRAPH_MANIFEST_SHA256 = (
    "47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da"
)
PHYSICAL_GPU = 3
LOGICAL_DEVICE = "xpu:0"
EXPECTED_DEVICE_NAME = "Intel(R) Arc(TM) Pro B70 Graphics"
EXPECTED_DEVICE_UUID = "868023e2-0000-0000-4700-000000000000"
EXPECTED_PCI_BDF_CONTEXT = "0000:47:00.0"
EXPECTED_HOSTNAME = "steve-b70s"
EXPECTED_KV_LENGTH = 128
EXPECTED_RETURNED_LAUNCHES = 10
Q64_POLICY_ENV = "VLLM_XPU_FA2_M6_HEAD256_Q64K32_POLICY"
Q8_POLICY_ENV = "VLLM_XPU_FA2_M6_HEAD256_Q8K64_POLICY"


class ContractError(RuntimeError):
    """A fail-closed diagnostic-contract violation."""


class ExpectedStop(RuntimeError):
    """Internal sentinel raised only after the first synchronize returns."""


def reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise ContractError(f"invalid JSON {path}: {error}") from error


def require_exact_keys(obj: dict[str, Any], keys: Iterable[str], where: str) -> None:
    expected = set(keys)
    actual = set(obj)
    if actual != expected:
        raise ContractError(
            f"{where} keys differ: missing={sorted(expected - actual)} "
            f"extra={sorted(actual - expected)}"
        )


def require_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{where} must be an integer")
    return value


def require_finite(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{where} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ContractError(f"{where} must be finite")
    return result


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_file(path: Path, where: str) -> Path:
    if not path.is_absolute():
        raise ContractError(f"{where} must be absolute: {path}")
    resolved = path.resolve(strict=True)
    if resolved != path:
        raise ContractError(f"{where} must already be canonical: {path} -> {resolved}")
    if not resolved.is_file():
        raise ContractError(f"{where} must be a regular file: {resolved}")
    return resolved


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = Path(f"{path}.tmp")
    if path.exists() or temporary.exists():
        raise ContractError(f"refusing existing output or temporary path: {path}")
    encoded = (
        json.dumps(payload, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o444)
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def parse_proc_stat(text: str, where: str) -> dict[str, int]:
    left = text.find("(")
    right = text.rfind(")")
    if left <= 0 or right <= left:
        raise ContractError(f"malformed process stat: {where}")
    try:
        pid = int(text[:left].strip())
        fields = text[right + 2 :].split()
        return {
            "pid": pid,
            "pgid": int(fields[2]),
            "sid": int(fields[3]),
            "start_ticks": int(fields[19]),
        }
    except (IndexError, ValueError) as error:
        raise ContractError(f"malformed process stat: {where}") from error


def process_identity(pid: int | None = None) -> dict[str, Any]:
    target = os.getpid() if pid is None else pid
    stat_path = Path(f"/proc/{target}/stat")
    stat = parse_proc_stat(stat_path.read_text(encoding="utf-8"), str(stat_path))
    if stat["pid"] != target:
        raise ContractError(f"process stat PID mismatch: {stat_path}")
    return {
        "boot_id": Path("/proc/sys/kernel/random/boot_id")
        .read_text(encoding="utf-8")
        .strip(),
        "pid": target,
        "pgid": stat["pgid"],
        "sid": stat["sid"],
        "start_ticks": stat["start_ticks"],
    }


class ReceiptChain:
    """Append-only immutable per-writer receipt chain."""

    def __init__(
        self,
        directory: Path,
        writer: str,
        contract_path: Path,
        contract_sha256: str,
        identity: dict[str, Any],
    ) -> None:
        self.directory = directory
        self.writer = writer
        self.contract_path = contract_path
        self.contract_sha256 = contract_sha256
        self.identity = identity
        self.index = 0
        self.previous_sha256: str | None = None
        if directory.exists():
            raise ContractError(f"refusing existing receipt directory: {directory}")
        directory.mkdir(mode=0o700)

    def emit(self, phase: str, data: dict[str, Any]) -> tuple[Path, str]:
        if re.fullmatch(r"[a-z0-9][a-z0-9-]*", phase) is None:
            raise ContractError(f"invalid phase name: {phase}")
        path = self.directory / f"{self.index:04d}-{phase}.json"
        payload = {
            "schema": SCHEMA_RECEIPT,
            "writer": self.writer,
            "index": self.index,
            "phase": phase,
            "time_ns": time.time_ns(),
            "monotonic_ns": time.monotonic_ns(),
            "contract_path": str(self.contract_path),
            "contract_sha256": self.contract_sha256,
            "previous_receipt_sha256": self.previous_sha256,
            "process": self.identity,
            "data": data,
        }
        atomic_json(path, payload)
        digest = sha256_file(path)
        self.previous_sha256 = digest
        self.index += 1
        return path, digest


def validate_receipt_chain(
    directory: Path,
    writer: str,
    contract_path: Path,
    contract_sha256: str,
) -> list[dict[str, Any]]:
    if not directory.is_dir():
        raise ContractError(f"missing receipt directory: {directory}")
    files = sorted(directory.glob("*.json"))
    if not files:
        raise ContractError(f"empty receipt directory: {directory}")
    result: list[dict[str, Any]] = []
    previous_sha: str | None = None
    process: dict[str, Any] | None = None
    for index, path in enumerate(files):
        if path.stat().st_mode & 0o222:
            raise ContractError(f"receipt is writable: {path}")
        payload = load_json(path)
        if not isinstance(payload, dict):
            raise ContractError(f"receipt is not an object: {path}")
        require_exact_keys(
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
        expected_name = f"{index:04d}-{phase}.json"
        if (
            payload["schema"] != SCHEMA_RECEIPT
            or payload["writer"] != writer
            or require_int(payload["index"], f"{path}.index") != index
            or not isinstance(phase, str)
            or path.name != expected_name
            or payload["contract_path"] != str(contract_path)
            or payload["contract_sha256"] != contract_sha256
            or payload["previous_receipt_sha256"] != previous_sha
            or not isinstance(payload["data"], dict)
        ):
            raise ContractError(f"receipt chain mismatch: {path}")
        require_int(payload["time_ns"], f"{path}.time_ns")
        require_int(payload["monotonic_ns"], f"{path}.monotonic_ns")
        receipt_process = payload["process"]
        if not isinstance(receipt_process, dict):
            raise ContractError(f"receipt process is not an object: {path}")
        require_exact_keys(
            receipt_process,
            ("boot_id", "pid", "pgid", "sid", "start_ticks"),
            f"{path}.process",
        )
        if (
            not isinstance(receipt_process["boot_id"], str)
            or not receipt_process["boot_id"]
        ):
            raise ContractError(f"receipt boot ID is missing: {path}")
        require_int(receipt_process["pid"], f"{path}.process.pid")
        require_int(receipt_process["pgid"], f"{path}.process.pgid")
        require_int(receipt_process["sid"], f"{path}.process.sid")
        require_int(receipt_process["start_ticks"], f"{path}.process.start_ticks")
        if process is None:
            process = receipt_process
        elif receipt_process != process:
            raise ContractError(f"receipt process identity changed: {path}")
        previous_sha = sha256_file(path)
        result.append({"path": str(path), "sha256": previous_sha, "phase": phase})
    return result


def load_base_qualifier() -> Any:
    canonical_file(BASE_QUALIFIER, "base qualifier")
    if sha256_file(BASE_QUALIFIER) != BASE_QUALIFIER_SHA256:
        raise ContractError("frozen base qualifier SHA mismatch")
    spec = importlib.util.spec_from_file_location(
        "qwen38_gpu3_health_frozen_base", BASE_QUALIFIER
    )
    if spec is None or spec.loader is None:
        raise ContractError("cannot construct frozen base qualifier import")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def device_uuid_text(properties: Any) -> str:
    value = getattr(properties, "uuid", None)
    text = str(value).lower()
    if re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", text) is None:
        raise ContractError(f"malformed XPU device UUID: {text!r}")
    return text


def mapping_evidence(
    base: Any, stage_identity: dict[str, Any], raw_maps: str | None = None
) -> dict[str, Any]:
    if raw_maps is None:
        raw_maps = Path("/proc/self/maps").read_text(encoding="utf-8")
    lines = raw_maps.splitlines()
    names = ("extension", "device_library", "stock_library")
    required = {
        name: {
            "path": stage_identity["files"][name]["path"],
            "sha256": stage_identity["files"][name]["sha256"],
        }
        for name in names
    }
    selected_lines: dict[str, list[str]] = {name: [] for name in names}
    same_basename: dict[str, set[str]] = {name: set() for name in names}
    for line in lines:
        fields = line.split(maxsplit=5)
        if len(fields) != 6 or not fields[5].startswith("/"):
            continue
        path_text = fields[5]
        for name in names:
            if (
                Path(path_text.removesuffix(" (deleted)")).name
                != Path(required[name]["path"]).name
            ):
                continue
            if path_text.endswith(" (deleted)"):
                raise ContractError(f"deleted required mapping: {path_text}")
            resolved = str(Path(path_text).resolve(strict=True))
            same_basename[name].add(resolved)
            if resolved == required[name]["path"]:
                selected_lines[name].append(line)
    for name in names:
        expected_path = required[name]["path"]
        if same_basename[name] != {expected_path} or not selected_lines[name]:
            raise ContractError(
                f"mapped {name} mismatch: expected={expected_path} "
                f"same_basename={sorted(same_basename[name])}"
            )
        if base.sha256_file(Path(expected_path)) != required[name]["sha256"]:
            raise ContractError(f"mapped {name} file SHA changed")
    return {
        "proc_self_maps_sha256": sha256_bytes(raw_maps.encode("utf-8")),
        "required": required,
        "selected_lines": selected_lines,
        "same_basename_paths": {
            name: sorted(paths) for name, paths in same_basename.items()
        },
        "passed": True,
    }


def stock_graph_identity(
    base: Any,
    *,
    stage: Path = CONTROL_STAGE,
    manifest: Path = CONTROL_GRAPH_MANIFEST,
    expected_manifest_sha256: str = CONTROL_GRAPH_MANIFEST_SHA256,
) -> dict[str, Any]:
    manifest = canonical_file(manifest, "stock graph manifest")
    actual_manifest_sha = sha256_file(manifest)
    if actual_manifest_sha != expected_manifest_sha256:
        raise ContractError("stock graph manifest SHA mismatch")
    stage = stage.resolve(strict=True)
    package = stage / "vllm_xpu_kernels"
    if not package.is_dir():
        raise ContractError(f"stock stage package is missing: {package}")
    manifest_entries = base.parse_sha256_manifest(manifest, relative_root=stage)
    stage_files: set[Path] = set()
    for candidate in package.rglob("*"):
        if candidate.is_symlink():
            raise ContractError(f"stock stage contains a symlink: {candidate}")
        if candidate.is_file():
            stage_files.add(candidate.resolve(strict=True))
    if set(manifest_entries) != stage_files:
        raise ContractError(
            "stock graph manifest inventory differs from stage: "
            f"missing={sorted(str(item) for item in stage_files - set(manifest_entries))} "
            f"extra={sorted(str(item) for item in set(manifest_entries) - stage_files)}"
        )
    files: dict[str, str] = {}
    for stage_file, expected_sha in sorted(
        manifest_entries.items(), key=lambda item: str(item[0])
    ):
        actual_sha = sha256_file(stage_file)
        if actual_sha != expected_sha:
            raise ContractError(f"stock graph file SHA mismatch: {stage_file}")
        files[str(stage_file.relative_to(stage))] = actual_sha
    return {
        "manifest_path": str(manifest),
        "manifest_sha256": actual_manifest_sha,
        "stage": str(stage),
        "file_count": len(files),
        "files": files,
    }


def validate_contract(
    contract: Any,
    path: Path,
    expected_sha: str,
    *,
    check_environment: bool = True,
) -> dict[str, Any]:
    if not isinstance(contract, dict):
        raise ContractError("contract must be an object")
    require_exact_keys(
        contract,
        (
            "schema",
            "created_time_ns",
            "output_root",
            "deadline",
            "repo",
            "files",
            "stage_identity",
            "stock_graph_identity",
            "environment",
            "device",
            "workload",
        ),
        "contract",
    )
    if contract["schema"] != SCHEMA_CONTRACT or sha256_file(path) != expected_sha:
        raise ContractError("contract schema/SHA mismatch")
    require_int(contract["created_time_ns"], "contract.created_time_ns")
    root = Path(contract["output_root"])
    if not root.is_absolute() or root.resolve(strict=True) != root:
        raise ContractError("contract output root is not canonical")
    deadline = contract["deadline"]
    if deadline != {
        "wall_seconds": 60.0,
        "term_grace_seconds": 5.0,
        "kill_grace_seconds": 5.0,
    }:
        raise ContractError("contract deadline differs from preregistration")
    repo = contract["repo"]
    if not isinstance(repo, dict):
        raise ContractError("contract repo must be an object")
    require_exact_keys(
        repo,
        ("path", "branch", "head", "origin_main", "status_porcelain_sha256"),
        "repo",
    )
    if (
        repo["path"] != str(REPO)
        or repo["branch"] != "main"
        or repo["head"] != repo["origin_main"]
        or not isinstance(repo["head"], str)
        or re.fullmatch(r"[0-9a-f]{40}", repo["head"]) is None
        or repo["status_porcelain_sha256"] != sha256_bytes(b"")
    ):
        raise ContractError("contract repository identity mismatch")
    files = contract["files"]
    if not isinstance(files, dict):
        raise ContractError("contract files must be an object")
    require_exact_keys(files, ("supervisor", "worker", "base_qualifier"), "files")
    for name, entry in files.items():
        if not isinstance(entry, dict):
            raise ContractError(f"files.{name} must be an object")
        require_exact_keys(entry, ("path", "sha256"), f"files.{name}")
        file_path = canonical_file(Path(entry["path"]), f"files.{name}.path")
        if sha256_file(file_path) != entry["sha256"]:
            raise ContractError(f"files.{name} SHA mismatch")
    if (
        Path(files["worker"]["path"]).resolve() != Path(__file__).resolve()
        or Path(files["supervisor"]["path"]) != SUPERVISOR
        or Path(files["base_qualifier"]["path"]) != BASE_QUALIFIER
        or files["base_qualifier"]["sha256"] != BASE_QUALIFIER_SHA256
    ):
        raise ContractError("supervisor/worker/base file binding mismatch")
    base = load_base_qualifier()
    current_stage_identity = base.stage_identity(
        argparse.Namespace(
            role="control", stage=str(CONTROL_STAGE), stage_manifest=None
        )
    )
    if contract["stage_identity"] != current_stage_identity:
        raise ContractError("contract stock stage identity mismatch")
    current_graph_identity = stock_graph_identity(base)
    if contract["stock_graph_identity"] != current_graph_identity:
        raise ContractError("contract full stock graph identity mismatch")
    device = contract["device"]
    if device != {
        "physical_gpu": PHYSICAL_GPU,
        "logical_device": LOGICAL_DEVICE,
        "expected_name": EXPECTED_DEVICE_NAME,
        "expected_uuid": EXPECTED_DEVICE_UUID,
        "pci_bdf_context": EXPECTED_PCI_BDF_CONTEXT,
        "expected_hostname": EXPECTED_HOSTNAME,
    }:
        raise ContractError("device contract mismatch")
    workload = contract["workload"]
    if workload != {
        "kv_length": EXPECTED_KV_LENGTH,
        "returned_fa_launches": EXPECTED_RETURNED_LAUNCHES,
        "is_mix_batch": True,
        "force_chunk_decode": True,
        "stop_after_first_explicit_synchronize": True,
    }:
        raise ContractError("workload contract mismatch")
    environment = contract["environment"]
    if not isinstance(environment, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in environment.items()
    ):
        raise ContractError("contract environment must be string-to-string")
    expected_environment_values = {
        "HOME": "/home/steve",
        "USER": "steve",
        "LOGNAME": "steve",
        "SHELL": "/bin/bash",
        "LANG": "C.UTF-8",
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(CONTROL_STAGE),
        "LD_LIBRARY_PATH": (
            f"{CONTROL_STAGE}/vllm_xpu_kernels:"
            "/home/steve/.venvs/vllm-xpu/lib:"
            "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib"
        ),
        "ZE_AFFINITY_MASK": str(PHYSICAL_GPU),
        "VLLM_XPU_FA2_FORCE_CHUNK_DECODE": "1",
        Q64_POLICY_ENV: "0",
        Q8_POLICY_ENV: "0",
    }
    if environment != expected_environment_values:
        raise ContractError("contract environment values differ from sealed allowlist")
    expected_environment = dict(environment)
    expected_environment["QWEN38_GPU3_HEALTH_CONTRACT"] = str(path)
    expected_environment["QWEN38_GPU3_HEALTH_CONTRACT_SHA256"] = expected_sha
    if check_environment and dict(os.environ) != expected_environment:
        missing = sorted(set(expected_environment) - set(os.environ))
        extra = sorted(set(os.environ) - set(expected_environment))
        changed = sorted(
            key
            for key in set(os.environ) & set(expected_environment)
            if os.environ[key] != expected_environment[key]
        )
        raise ContractError(
            f"worker environment differs: missing={missing} extra={extra} changed={changed}"
        )
    return contract


def instrumented_warmup(
    base: Any,
    torch: Any,
    flash_attn_varlen_func: Any,
    chain: ReceiptChain,
    mapping: dict[str, Any],
) -> dict[str, Any]:
    returned_launches = 0
    synchronize_entries = 0
    synchronize_returns = 0
    original_synchronize = torch.xpu.synchronize

    def traced_launch(*args: Any, **kwargs: Any) -> Any:
        nonlocal returned_launches
        result = flash_attn_varlen_func(*args, **kwargs)
        if result is None:
            raise ContractError("FlashAttention launch returned None")
        returned_launches += 1
        if returned_launches > EXPECTED_RETURNED_LAUNCHES:
            raise ContractError("more than ten FA launches returned before synchronize")
        chain.emit(
            "fa-launch-returned",
            {
                "launch_index": returned_launches,
                "expected_launches": EXPECTED_RETURNED_LAUNCHES,
                "return_type": type(result).__name__,
            },
        )
        return result

    def traced_synchronize(*args: Any, **kwargs: Any) -> Any:
        nonlocal synchronize_entries, synchronize_returns
        synchronize_entries += 1
        if synchronize_entries != 1 or returned_launches != EXPECTED_RETURNED_LAUNCHES:
            raise ContractError(
                "first explicit synchronize did not follow exactly ten returned launches"
            )
        chain.emit(
            "sync-enter",
            {
                "returned_launches": returned_launches,
                "maps_sha256": mapping["proc_self_maps_sha256"],
            },
        )
        original_synchronize(*args, **kwargs)
        synchronize_returns += 1
        chain.emit(
            "sync-return",
            {
                "returned_launches": returned_launches,
                "synchronize_returns": synchronize_returns,
            },
        )
        raise ExpectedStop("first explicit synchronize returned")

    torch.xpu.synchronize = traced_synchronize
    try:
        base._run_case(
            torch,
            traced_launch,
            0,
            EXPECTED_KV_LENGTH,
            base.MIN_SAMPLES,
            base.MIN_LAUNCHES_PER_SAMPLE,
            base.MIN_STABILITY_REPLAYS,
        )
    except ExpectedStop:
        pass
    finally:
        torch.xpu.synchronize = original_synchronize
    if (
        returned_launches != EXPECTED_RETURNED_LAUNCHES
        or synchronize_entries != 1
        or synchronize_returns != 1
    ):
        raise ContractError("instrumented warmup did not reach its exact stop boundary")
    return {
        "returned_fa_launches": returned_launches,
        "synchronize_entries": synchronize_entries,
        "synchronize_returns": synchronize_returns,
    }


def run_worker(contract_path: Path) -> dict[str, Any]:
    expected_contract_path = os.environ.get("QWEN38_GPU3_HEALTH_CONTRACT")
    contract_sha = os.environ.get("QWEN38_GPU3_HEALTH_CONTRACT_SHA256")
    if expected_contract_path != str(contract_path) or contract_sha is None:
        raise ContractError("contract argv/environment binding is missing")
    canonical_file(contract_path, "contract")
    if contract_path.stat().st_mode & 0o222:
        raise ContractError("contract is writable")
    contract = validate_contract(load_json(contract_path), contract_path, contract_sha)
    output_root = Path(contract["output_root"])
    identity = process_identity()
    chain = ReceiptChain(
        output_root / "worker-phases",
        "worker",
        contract_path,
        contract_sha,
        identity,
    )
    chain.emit(
        "worker-start",
        {
            "hostname": socket.gethostname(),
            "worker_sha256": contract["files"]["worker"]["sha256"],
            "base_qualifier_sha256": BASE_QUALIFIER_SHA256,
        },
    )
    base = load_base_qualifier()
    if socket.gethostname() != EXPECTED_HOSTNAME:
        raise ContractError(f"unexpected hostname: {socket.gethostname()!r}")
    stage_identity = base.stage_identity(
        argparse.Namespace(
            role="control", stage=str(CONTROL_STAGE), stage_manifest=None
        )
    )
    if stage_identity != contract["stage_identity"]:
        raise ContractError("current control stage differs from sealed contract")
    chain.emit(
        "base-and-stage-verified",
        {
            "base_qualifier_sha256": BASE_QUALIFIER_SHA256,
            "stage": str(CONTROL_STAGE),
            "stage_hashes": stage_identity["hashes"],
            "stock_graph_manifest_path": contract["stock_graph_identity"][
                "manifest_path"
            ],
            "stock_graph_manifest_sha256": contract["stock_graph_identity"][
                "manifest_sha256"
            ],
            "stock_graph_file_count": contract["stock_graph_identity"]["file_count"],
        },
    )

    import torch  # pylint: disable=import-outside-toplevel

    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise ContractError("expected exactly one available affinity-scoped XPU")
    torch.xpu.set_device(0)
    properties = torch.xpu.get_device_properties(0)
    actual_uuid = device_uuid_text(properties)
    actual_name = torch.xpu.get_device_name(0)
    if actual_name != EXPECTED_DEVICE_NAME or actual_uuid != EXPECTED_DEVICE_UUID:
        raise ContractError(
            f"unexpected affinity-scoped device: name={actual_name!r} uuid={actual_uuid!r}"
        )
    chain.emit(
        "device-bound",
        {
            "device_count": 1,
            "logical_device": LOGICAL_DEVICE,
            "physical_gpu": PHYSICAL_GPU,
            "ze_affinity_mask": os.environ["ZE_AFFINITY_MASK"],
            "device_name": actual_name,
            "device_uuid": actual_uuid,
            "pci_bdf_context": EXPECTED_PCI_BDF_CONTEXT,
        },
    )
    interface = importlib.import_module("vllm_xpu_kernels.flash_attn_interface")
    extension = importlib.import_module("vllm_xpu_kernels._vllm_fa2_C")
    if not bool(getattr(interface, "FA2_AVAILABLE", False)):
        raise ContractError(
            f"staged FA extension unavailable: {interface.FA2_UNAVAILABLE_REASON}"
        )
    if Path(interface.__file__).resolve() != Path(
        stage_identity["files"]["interface"]["path"]
    ) or Path(extension.__file__).resolve() != Path(
        stage_identity["files"]["extension"]["path"]
    ):
        raise ContractError("imported interface/extension escaped the stock stage")
    maps = mapping_evidence(base, stage_identity)
    chain.emit("stock-maps-bound", maps)
    warmup = instrumented_warmup(
        base, torch, interface.flash_attn_varlen_func, chain, maps
    )
    chain.emit("worker-complete", warmup)
    receipts = validate_receipt_chain(
        chain.directory, "worker", contract_path, contract_sha
    )
    result = {
        "schema": SCHEMA_RESULT,
        "passed": True,
        "classification": "gpu3-incumbent-control-health-pass",
        "contract_path": str(contract_path),
        "contract_sha256": contract_sha,
        "process": identity,
        "device": {
            "physical_gpu": PHYSICAL_GPU,
            "logical_device": LOGICAL_DEVICE,
            "name": actual_name,
            "uuid": actual_uuid,
            "pci_bdf_context": EXPECTED_PCI_BDF_CONTEXT,
        },
        "stage_identity": stage_identity,
        "stock_graph_identity": contract["stock_graph_identity"],
        "mapping_evidence": maps,
        "workload": warmup,
        "phase_receipts": receipts,
    }
    atomic_json(output_root / "worker-result.json", result)
    return result


def immutable_receipt_snapshot(directory: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not directory.is_dir():
        return result
    for path in sorted(directory.glob("*.json")):
        if path.stat().st_mode & 0o222:
            raise ContractError(
                f"worker failure snapshot found writable receipt: {path}"
            )
        result.append(
            {
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return result


def write_worker_failure(contract_path: Path, error: BaseException) -> None:
    try:
        contract_sha = os.environ.get("QWEN38_GPU3_HEALTH_CONTRACT_SHA256")
        if contract_sha is None or not contract_path.is_file():
            return
        contract = load_json(contract_path)
        output_root = Path(contract["output_root"])
        failure_path = output_root / "worker-failure.json"
        if failure_path.exists() or Path(f"{failure_path}.tmp").exists():
            return
        phase_dir = output_root / "worker-phases"
        receipts = immutable_receipt_snapshot(phase_dir)
        receipt_chain_error: str | None = None
        if receipts:
            try:
                validate_receipt_chain(phase_dir, "worker", contract_path, contract_sha)
            except Exception as validation_error:  # durable, explicit invalidity
                receipt_chain_error = (
                    f"{type(validation_error).__name__}: {validation_error}"
                )
        atomic_json(
            failure_path,
            {
                "schema": SCHEMA_FAILURE,
                "passed": False,
                "classification": "gpu3-incumbent-control-health-worker-failure",
                "contract_path": str(contract_path),
                "contract_sha256": contract_sha,
                "process": process_identity(),
                "exception_type": type(error).__name__,
                "message": str(error),
                "phase_receipt_snapshot": receipts,
                "receipt_chain_validation_error": receipt_chain_error,
            },
        )
    except BaseException:
        return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    contract_path = Path(args.contract)
    try:
        result = run_worker(contract_path)
        print(json.dumps({"passed": True, "result": result["classification"]}))
        return 0
    except BaseException as error:
        write_worker_failure(contract_path, error)
        print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
