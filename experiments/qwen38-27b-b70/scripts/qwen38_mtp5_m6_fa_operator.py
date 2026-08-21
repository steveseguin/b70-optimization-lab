#!/usr/bin/env python3
"""Exact-shape Qwen3.8 MTP5/M6 FlashAttention operator qualifier.

The XPU run path deliberately imports torch and the staged extension only after
all output-collision and stage-identity checks.  The compare path is CPU-only.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import random
import re
import socket
import statistics
import sys
import time
from typing import Any, Callable, Iterable


SCHEMA_RUN = "qwen38-mtp5-m6-fa-operator-run-v1"
SCHEMA_COMPARE = "qwen38-mtp5-m6-fa-operator-compare-v1"
SCHEMA_STAGE = "qwen38-mtp5-m6-fa-stage-v1"
CONTROL_STAGE = Path("/home/steve/staged-xpu-commitfix-graphfa-composite-20260820")
ROWS = 6
Q_HEADS = 12
KV_HEADS = 2
HEAD_DIM = 256
BLOCK_SIZE = 64
KV_LENGTHS = (128, 1024, 1300, 2048)
ATOL = 2e-2
RTOL = 1e-2
MIN_SAMPLES = 30
MIN_LAUNCHES_PER_SAMPLE = 50
MIN_STABILITY_REPLAYS = 16
MUTATION_REPETITIONS_PER_MODE = 2
MIN_SAVING_US_PER_CALL = 21.844
MIN_SAVING_MS_PER_16 = 0.3495
MAX_KV128_REGRESSION_US_PER_CALL = 2.0
EXPECTED_PHYSICAL_GPUS = (2, 3)
EXPECTED_DEVICE_NAME = "Intel(R) Arc(TM) Pro B70 Graphics"
POLICY_ENV = "VLLM_XPU_FA2_M6_HEAD256_Q8K64_POLICY"
POLICY_MARKER = "VLLM_XPU_FA2_M6_HEAD256_Q8K64_POLICY engaged"
CANDIDATE_PATCH = Path(
    "/home/steve/llm-optimizations/experiments/qwen38-27b-b70/patches/"
    "vllm-xpu-kernels-qwen38-m6-head256-q8k64-chunk-prefill-20260820.patch"
)
CANDIDATE_PATCH_SHA256 = (
    "06467757a7482ad0e3225c9a59ce3d2de144453a608016737c7a24dbe48b5fc1"
)
BUILD_HELPER = Path(
    "/home/steve/llm-optimizations/experiments/qwen38-27b-b70/scripts/"
    "build-qwen38-m6-head256-q8k64-attn-override-20260820.sh"
)
BUILD_HELPER_SHA256 = "abf3701374d658c5d2fe1d6ef16a659c2955147eb65cd6f74f628d4f8278f4b1"
BUILD_INPUTS_BASENAME = "qwen38-m6-head256-q8k64-build-inputs.sha256"
GRAPH_MANIFEST_BASENAME = "qwen38-m6-head256-q8k64-candidate.graph.sha256"
CONTROL_GRAPH_MANIFEST = Path(
    "/home/steve/llm-optimizations/repro/qwen38-27b-autoround-int4-b70/manifests/"
    "staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256"
)
CONTROL_GRAPH_MANIFEST_SHA256 = (
    "47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da"
)

RELATIVE_FILES = {
    "extension": "vllm_xpu_kernels/_vllm_fa2_C.abi3.so",
    "interface": "vllm_xpu_kernels/flash_attn_interface.py",
    "device_library": "vllm_xpu_kernels/libattn_kernels_xe_2.so",
    "stock_library": "vllm_xpu_kernels/libattn_stock.so",
}
CONTROL_HASHES = {
    "extension": "33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739",
    "interface": "869c79f5f678252c341cfb8fb5cf9ee34f95c3d2debf4d169b759510da432480",
    "device_library": "604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c",
    "stock_library": "3cbd3ed2ff51a477e6746b3e5860c070d093fd2d29b0b7a58e6dd081e9ad1289",
}


class ContractError(RuntimeError):
    """A fail-closed qualification-contract violation."""


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
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
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json_atomic(output: Path, temporary: Path, payload: dict[str, Any]) -> None:
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
        os.replace(temporary, output)
        directory_descriptor = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def parse_sha256_manifest(
    path: Path, *, relative_root: Path | None = None
) -> dict[Path, str]:
    entries: dict[Path, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise ContractError(f"invalid checksum manifest {path}: {error}") from error
    if not lines:
        raise ContractError(f"checksum manifest is empty: {path}")
    for line_number, line in enumerate(lines, 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise ContractError(
                f"malformed checksum manifest line {path}:{line_number}"
            )
        entry_path = Path(match.group(2))
        if not entry_path.is_absolute():
            entry_path = (
                relative_root if relative_root is not None else path.parent
            ) / entry_path
        resolved = entry_path.resolve(strict=False)
        if resolved in entries:
            raise ContractError(f"duplicate checksum target in {path}: {resolved}")
        entries[resolved] = match.group(1)
    return entries


def _canonical_absolute(path_text: str, where: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        raise ContractError(f"{where} must be absolute: {path}")
    resolved = path.resolve(strict=True)
    if resolved != path:
        raise ContractError(f"{where} must already be canonical: {path} -> {resolved}")
    return resolved


def validate_candidate_manifest(path: Path) -> dict[str, Any]:
    manifest = load_json(path)
    if not isinstance(manifest, dict):
        raise ContractError("candidate manifest must be an object")
    require_exact_keys(
        manifest, ("schema", "role", "stage", "files", "artifact"), "manifest"
    )
    if manifest["schema"] != SCHEMA_STAGE or manifest["role"] != "candidate":
        raise ContractError("candidate manifest schema/role mismatch")
    stage = _canonical_absolute(manifest["stage"], "manifest.stage")
    if stage == CONTROL_STAGE:
        raise ContractError("candidate stage must differ from the control stage")
    files = manifest["files"]
    if not isinstance(files, dict):
        raise ContractError("manifest.files must be an object")
    require_exact_keys(files, RELATIVE_FILES, "manifest.files")
    hashes: dict[str, str] = {}
    for name, relative_path in RELATIVE_FILES.items():
        entry = files[name]
        if not isinstance(entry, dict):
            raise ContractError(f"manifest.files.{name} must be an object")
        require_exact_keys(entry, ("relative_path", "sha256"), f"files.{name}")
        if entry["relative_path"] != relative_path:
            raise ContractError(f"files.{name}.relative_path mismatch")
        digest = entry["sha256"]
        if not isinstance(digest, str) or len(digest) != 64:
            raise ContractError(f"files.{name}.sha256 is not a SHA-256")
        try:
            int(digest, 16)
        except ValueError as error:
            raise ContractError(f"files.{name}.sha256 is not hexadecimal") from error
        hashes[name] = digest
    for fixed_name in ("extension", "interface", "stock_library"):
        if hashes[fixed_name] != CONTROL_HASHES[fixed_name]:
            raise ContractError(
                f"candidate {fixed_name} must remain byte-identical to control"
            )
    if hashes["device_library"] == CONTROL_HASHES["device_library"]:
        raise ContractError("candidate device library must differ from control")
    artifact = manifest["artifact"]
    if not isinstance(artifact, dict):
        raise ContractError("manifest.artifact must be an object")
    require_exact_keys(artifact, ("path", "sha256"), "manifest.artifact")
    artifact_path = _canonical_absolute(artifact["path"], "artifact.path")
    artifact_sha = artifact["sha256"]
    if not isinstance(artifact_sha, str) or len(artifact_sha) != 64:
        raise ContractError("artifact.sha256 is not a SHA-256")
    if sha256_file(artifact_path) != artifact_sha:
        raise ContractError("candidate artifact SHA mismatch")
    if artifact_path.name != BUILD_INPUTS_BASENAME:
        raise ContractError("candidate artifact is not the helper build-input manifest")
    if sha256_file(CANDIDATE_PATCH) != CANDIDATE_PATCH_SHA256:
        raise ContractError("frozen candidate policy patch SHA mismatch")
    build_entries = parse_sha256_manifest(artifact_path)
    if build_entries.get(CANDIDATE_PATCH) != CANDIDATE_PATCH_SHA256:
        raise ContractError(
            "build-input manifest does not bind the frozen candidate patch"
        )
    helper_sha = sha256_file(BUILD_HELPER)
    if (
        helper_sha != BUILD_HELPER_SHA256
        or build_entries.get(BUILD_HELPER) != BUILD_HELPER_SHA256
    ):
        raise ContractError(
            "build-input manifest does not bind the current build helper"
        )
    candidate_dso_entries = [
        digest
        for entry_path, digest in build_entries.items()
        if entry_path.name == "libattn_kernels_xe_2.so"
    ]
    if candidate_dso_entries != [hashes["device_library"]]:
        raise ContractError(
            "build-input manifest must bind exactly one matching candidate device DSO"
        )
    graph_manifest_entries = [
        (entry_path, digest)
        for entry_path, digest in build_entries.items()
        if entry_path.name == GRAPH_MANIFEST_BASENAME
    ]
    if len(graph_manifest_entries) != 1:
        raise ContractError("build-input manifest must bind exactly one graph manifest")
    graph_manifest_path, graph_manifest_sha = graph_manifest_entries[0]
    if (
        not graph_manifest_path.is_file()
        or sha256_file(graph_manifest_path) != graph_manifest_sha
    ):
        raise ContractError("candidate graph manifest is missing or changed")
    graph_entries = parse_sha256_manifest(graph_manifest_path, relative_root=stage)
    package_root = stage / "vllm_xpu_kernels"
    stage_files: set[Path] = set()
    for candidate_path in package_root.rglob("*"):
        if candidate_path.is_symlink():
            raise ContractError(f"candidate stage contains a symlink: {candidate_path}")
        if candidate_path.is_file():
            stage_files.add(candidate_path.resolve(strict=True))
    if set(graph_entries) != stage_files:
        raise ContractError(
            "candidate graph manifest inventory differs from stage: "
            f"missing={sorted(str(item) for item in stage_files - set(graph_entries))} "
            f"extra={sorted(str(item) for item in set(graph_entries) - stage_files)}"
        )
    for stage_file, expected_sha in graph_entries.items():
        if sha256_file(stage_file) != expected_sha:
            raise ContractError(f"candidate graph-manifest SHA mismatch: {stage_file}")
    for name, relative_path in RELATIVE_FILES.items():
        if graph_entries.get(stage / relative_path) != hashes[name]:
            raise ContractError(f"candidate graph manifest disagrees for {name}")
    if sha256_file(CONTROL_GRAPH_MANIFEST) != CONTROL_GRAPH_MANIFEST_SHA256:
        raise ContractError("pinned control graph manifest SHA mismatch")
    control_graph_entries = parse_sha256_manifest(
        CONTROL_GRAPH_MANIFEST, relative_root=CONTROL_STAGE
    )
    control_by_relative = {
        entry_path.relative_to(CONTROL_STAGE): digest
        for entry_path, digest in control_graph_entries.items()
    }
    candidate_by_relative = {
        entry_path.relative_to(stage): digest
        for entry_path, digest in graph_entries.items()
    }
    if set(candidate_by_relative) != set(control_by_relative):
        raise ContractError("candidate/control graph-manifest inventories differ")
    device_relative = Path(RELATIVE_FILES["device_library"])
    for relative_path, control_sha in control_by_relative.items():
        candidate_sha = candidate_by_relative[relative_path]
        if relative_path == device_relative:
            if candidate_sha == control_sha:
                raise ContractError("candidate graph device library equals control")
        elif candidate_sha != control_sha:
            raise ContractError(
                f"candidate graph changed out-of-boundary file: {relative_path}"
            )
    return {
        "role": "candidate",
        "stage": str(stage),
        "hashes": hashes,
        "manifest_path": str(path.resolve(strict=True)),
        "manifest_sha256": sha256_file(path),
        "artifact_path": str(artifact_path),
        "artifact_sha256": artifact_sha,
        "graph_manifest_path": str(graph_manifest_path),
        "graph_manifest_sha256": graph_manifest_sha,
        "verified_graph_hashes": {
            str(entry_path): digest for entry_path, digest in graph_entries.items()
        },
    }


def control_identity(stage_text: str) -> dict[str, Any]:
    stage = _canonical_absolute(stage_text, "control stage")
    if stage != CONTROL_STAGE:
        raise ContractError(f"control stage must be exactly {CONTROL_STAGE}")
    return {
        "role": "control",
        "stage": str(stage),
        "hashes": dict(CONTROL_HASHES),
        "manifest_path": None,
        "manifest_sha256": None,
        "artifact_path": None,
        "artifact_sha256": None,
        "graph_manifest_path": None,
        "graph_manifest_sha256": None,
    }


def stage_identity(args: argparse.Namespace) -> dict[str, Any]:
    if args.role == "control":
        if args.stage_manifest is not None:
            raise ContractError("control must not use --stage-manifest")
        if args.stage is None:
            raise ContractError("control requires --stage")
        identity = control_identity(args.stage)
    else:
        if args.stage is not None:
            raise ContractError("candidate must not use --stage")
        if args.stage_manifest is None:
            raise ContractError("candidate requires --stage-manifest")
        identity = validate_candidate_manifest(Path(args.stage_manifest))
    stage = Path(identity["stage"])
    verified_graph_hashes = identity.pop("verified_graph_hashes", {})
    actual_files: dict[str, dict[str, str]] = {}
    for name, relative in RELATIVE_FILES.items():
        expected_path = stage / relative
        resolved = expected_path.resolve(strict=True)
        if not resolved.is_relative_to(stage):
            raise ContractError(f"{name} resolves outside selected stage: {resolved}")
        if str(resolved) in verified_graph_hashes:
            digest = verified_graph_hashes[str(resolved)]
        else:
            digest = sha256_file(resolved)
        expected_digest = identity["hashes"][name]
        if digest != expected_digest:
            raise ContractError(
                f"{name} SHA mismatch: actual={digest} expected={expected_digest}"
            )
        actual_files[name] = {
            "path": str(resolved),
            "relative_path": relative,
            "sha256": digest,
        }
    identity["files"] = actual_files
    return identity


def tensor_digest(tensor: Any) -> str:
    data = tensor.detach().cpu().contiguous().numpy().tobytes(order="C")
    return sha256_bytes(data)


def fixture_digest(*tensors: Any) -> str:
    digest = hashlib.sha256()
    for tensor in tensors:
        raw = tensor.detach().cpu().contiguous().numpy().tobytes(order="C")
        digest.update(raw)
    return digest.hexdigest()


def mutation_input_digest(*tensors: Any, seqused_k: int) -> str:
    digest = hashlib.sha256()
    for tensor in tensors:
        raw = tensor.detach().cpu().contiguous().numpy().tobytes(order="C")
        digest.update(raw)
    digest.update(seqused_k.to_bytes(8, byteorder="little", signed=False))
    return digest.hexdigest()


def mapped_paths() -> set[Path]:
    result: set[Path] = set()
    for line in Path("/proc/self/maps").read_text(encoding="utf-8").splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6 or not fields[5].startswith("/"):
            continue
        if fields[5].endswith(" (deleted)"):
            raise ContractError(f"deleted mapped object: {fields[5]}")
        try:
            result.add(Path(fields[5]).resolve(strict=True))
        except FileNotFoundError as error:
            raise ContractError(f"mapped path disappeared: {fields[5]}") from error
    return result


def _device_properties(torch: Any, device: int) -> dict[str, Any]:
    properties = torch.xpu.get_device_properties(device)
    selected = {}
    for name in (
        "name",
        "total_memory",
        "gpu_eu_count",
        "gpu_subslice_count",
        "max_work_group_size",
    ):
        value = getattr(properties, name, None)
        if isinstance(value, (str, int, float, bool)) or value is None:
            selected[name] = value
        else:
            selected[name] = str(value)
    return selected


def _cpu_reference(torch: Any, q: Any, k: Any, v: Any) -> Any:
    qf = q.float().cpu()
    kf = k.float().cpu().repeat_interleave(Q_HEADS // KV_HEADS, dim=1)
    vf = v.float().cpu().repeat_interleave(Q_HEADS // KV_HEADS, dim=1)
    logits = torch.einsum("qhd,khd->hqk", qf * (HEAD_DIM**-0.5), kf)
    q_positions = torch.arange(k.size(0) - ROWS, k.size(0))
    k_positions = torch.arange(k.size(0))
    causal_mask = k_positions[None, :] > q_positions[:, None]
    logits.masked_fill_(causal_mask[None, :, :], float("-inf"))
    probabilities = torch.softmax(logits, dim=-1)
    return torch.einsum("hqk,khd->qhd", probabilities, vf).half()


def _event_samples_us(
    torch: Any, fn: Callable[[], Any], samples: int, launches: int
) -> list[float]:
    values: list[float] = []
    for _ in range(samples):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(launches):
            fn()
        end.record()
        torch.xpu.synchronize()
        elapsed_us = float(start.elapsed_time(end)) * 1000.0 / launches
        if not math.isfinite(elapsed_us) or elapsed_us <= 0:
            raise ContractError(f"invalid device-event timing: {elapsed_us}")
        values.append(elapsed_us)
    return values


def _assert_close(torch: Any, actual: Any, expected: Any, where: str) -> float:
    if bool(torch.isnan(actual).any().item()):
        raise ContractError(f"{where} left poisoned NaNs")
    difference = float((actual.float() - expected.float()).abs().max().item())
    try:
        torch.testing.assert_close(actual, expected, atol=ATOL, rtol=RTOL)
    except AssertionError as error:
        raise ContractError(f"{where} differs from CPU oracle: {error}") from error
    return difference


def _run_case(
    torch: Any,
    flash_attn_varlen_func: Callable[..., Any],
    device: int,
    kv_len: int,
    samples: int,
    launches: int,
    stability_replays: int,
) -> dict[str, Any]:
    generator = torch.Generator(device="cpu").manual_seed(380000 + kv_len)
    q_cpu = torch.randn(
        ROWS, Q_HEADS, HEAD_DIM, dtype=torch.float16, generator=generator
    )
    logical_blocks = (kv_len + BLOCK_SIZE - 1) // BLOCK_SIZE
    num_blocks = logical_blocks + 3
    block_order = torch.randperm(num_blocks, generator=generator)[:logical_blocks]
    k_cache_cpu = torch.randn(
        num_blocks,
        BLOCK_SIZE,
        KV_HEADS,
        HEAD_DIM,
        dtype=torch.float16,
        generator=generator,
    )
    v_cache_cpu = torch.randn(
        num_blocks,
        BLOCK_SIZE,
        KV_HEADS,
        HEAD_DIM,
        dtype=torch.float16,
        generator=generator,
    )
    logical_k = k_cache_cpu[block_order].reshape(-1, KV_HEADS, HEAD_DIM)[:kv_len]
    logical_v = v_cache_cpu[block_order].reshape(-1, KV_HEADS, HEAD_DIM)[:kv_len]
    expected = _cpu_reference(torch, q_cpu, logical_k, logical_v)

    xpu = torch.device("xpu", device)
    q = q_cpu.to(xpu)
    k_cache = k_cache_cpu.to(xpu)
    v_cache = v_cache_cpu.to(xpu)
    cu_q = torch.tensor([0, ROWS], dtype=torch.int32, device=xpu)
    seqused_k = torch.tensor([kv_len], dtype=torch.int32, device=xpu)
    block_table = block_order.to(dtype=torch.int32, device=xpu).view(1, -1)

    def launch(out: Any | None = None) -> Any:
        return flash_attn_varlen_func(
            q,
            k_cache,
            v_cache,
            ROWS,
            cu_q,
            kv_len,
            seqused_k=seqused_k,
            softmax_scale=HEAD_DIM**-0.5,
            causal=True,
            block_table=block_table,
            out=out,
            is_mix_batch=True,
        )

    for _ in range(10):
        launch()
    torch.xpu.synchronize()

    eager_out = torch.empty_like(q)
    eager_digests: list[str] = []
    eager_max_abs_diff = 0.0
    eager_pointer_honored = True
    for replay in range(stability_replays):
        eager_out.fill_(float("nan"))
        torch.xpu.synchronize()
        returned = launch(eager_out)
        if returned.data_ptr() != eager_out.data_ptr():
            eager_pointer_honored = False
            raise ContractError(f"KV {kv_len} eager call ignored static out")
        torch.xpu.synchronize()
        actual = eager_out.cpu()
        eager_max_abs_diff = max(
            eager_max_abs_diff,
            _assert_close(torch, actual, expected, f"KV {kv_len} eager {replay}"),
        )
        eager_digests.append(tensor_digest(actual))
    if len(set(eager_digests)) != 1:
        raise ContractError(f"KV {kv_len} eager output is not bit-stable")

    graph_out = torch.empty_like(q)
    graph_out.fill_(float("nan"))
    torch.xpu.synchronize()
    graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(graph):
        captured_out = launch(graph_out)
    if captured_out.data_ptr() != graph_out.data_ptr():
        raise ContractError(f"KV {kv_len} graph capture ignored static out")
    torch.xpu.synchronize()
    _assert_close(torch, graph_out.cpu(), expected, f"KV {kv_len} capture")

    graph_digests: list[str] = []
    graph_max_abs_diff = 0.0
    for replay in range(stability_replays):
        graph_out.fill_(float("nan"))
        torch.xpu.synchronize()
        graph.replay()
        torch.xpu.synchronize()
        actual = graph_out.cpu()
        graph_max_abs_diff = max(
            graph_max_abs_diff,
            _assert_close(torch, actual, expected, f"KV {kv_len} graph {replay}"),
        )
        graph_digests.append(tensor_digest(actual))
    if len(set(graph_digests)) != 1:
        raise ContractError(f"KV {kv_len} graph output is not bit-stable")
    if eager_digests[0] != graph_digests[0]:
        raise ContractError(f"KV {kv_len} eager and graph outputs differ bitwise")

    mutation_records: list[dict[str, Any]] = []
    mutation_inputs = (
        (
            "q_scale_0p875",
            "q",
            0.875,
            q_cpu * 0.875,
            k_cache_cpu,
            v_cache_cpu,
            kv_len,
        ),
        (
            "k_cache_scale_0p875",
            "k_cache",
            0.875,
            q_cpu,
            k_cache_cpu * 0.875,
            v_cache_cpu,
            kv_len,
        ),
        (
            "v_cache_scale_0p875",
            "v_cache",
            0.875,
            q_cpu,
            k_cache_cpu,
            v_cache_cpu * 0.875,
            kv_len,
        ),
        (
            "seqused_k_minus_64",
            "seqused_k",
            None,
            q_cpu,
            k_cache_cpu,
            v_cache_cpu,
            kv_len - BLOCK_SIZE,
        ),
    )
    for (
        mutation_name,
        mutation_target,
        mutation_scale,
        mutation_q_cpu,
        mutation_k_cache_cpu,
        mutation_v_cache_cpu,
        mutation_kv_len,
    ) in mutation_inputs:
        q.copy_(mutation_q_cpu)
        k_cache.copy_(mutation_k_cache_cpu)
        v_cache.copy_(mutation_v_cache_cpu)
        seqused_k.fill_(mutation_kv_len)
        mutation_logical_k = mutation_k_cache_cpu[block_order].reshape(
            -1, KV_HEADS, HEAD_DIM
        )[:mutation_kv_len]
        mutation_logical_v = mutation_v_cache_cpu[block_order].reshape(
            -1, KV_HEADS, HEAD_DIM
        )[:mutation_kv_len]
        mutation_expected = _cpu_reference(
            torch,
            mutation_q_cpu,
            mutation_logical_k,
            mutation_logical_v,
        )
        torch.xpu.synchronize()
        mode_digests: dict[str, list[str]] = {"eager": [], "graph": []}
        max_diffs: dict[str, float] = {"eager": 0.0, "graph": 0.0}
        for mode, output_tensor, mode_launch in (
            ("eager", eager_out, lambda: launch(eager_out)),
            ("graph", graph_out, graph.replay),
        ):
            for replay in range(MUTATION_REPETITIONS_PER_MODE):
                output_tensor.fill_(float("nan"))
                torch.xpu.synchronize()
                returned = mode_launch()
                if mode == "eager" and returned.data_ptr() != output_tensor.data_ptr():
                    raise ContractError(
                        f"KV {kv_len} mutation {mutation_name} ignored eager out"
                    )
                torch.xpu.synchronize()
                actual = output_tensor.cpu()
                max_diffs[mode] = max(
                    max_diffs[mode],
                    _assert_close(
                        torch,
                        actual,
                        mutation_expected,
                        f"KV {kv_len} {mutation_name} {mode} {replay}",
                    ),
                )
                mode_digests[mode].append(tensor_digest(actual))
        if len(set(mode_digests["eager"])) != 1 or len(set(mode_digests["graph"])) != 1:
            raise ContractError(
                f"KV {kv_len} mutation {mutation_name} is not bit-stable"
            )
        if mode_digests["eager"][0] != mode_digests["graph"][0]:
            raise ContractError(
                f"KV {kv_len} mutation {mutation_name} eager/graph mismatch"
            )
        if mode_digests["eager"][0] == eager_digests[0]:
            raise ContractError(
                f"KV {kv_len} mutation {mutation_name} was output-inert"
            )
        mutation_records.append(
            {
                "name": mutation_name,
                "target": mutation_target,
                "scale": mutation_scale,
                "seqused_k": mutation_kv_len,
                "input_sha256": mutation_input_digest(
                    mutation_q_cpu,
                    mutation_k_cache_cpu,
                    mutation_v_cache_cpu,
                    block_order,
                    seqused_k=mutation_kv_len,
                ),
                "oracle_sha256": tensor_digest(mutation_expected),
                "eager_output_sha256": mode_digests["eager"][0],
                "graph_output_sha256": mode_digests["graph"][0],
                "eager_max_abs_diff": max_diffs["eager"],
                "graph_max_abs_diff": max_diffs["graph"],
                "repetitions_per_mode": MUTATION_REPETITIONS_PER_MODE,
                "output_changed_from_baseline": True,
                "eager_graph_exact": True,
                "restored_before_next": True,
                "passed": True,
            }
        )

    q.copy_(q_cpu)
    k_cache.copy_(k_cache_cpu)
    v_cache.copy_(v_cache_cpu)
    seqused_k.fill_(kv_len)
    torch.xpu.synchronize()
    eager_out.fill_(float("nan"))
    returned = launch(eager_out)
    torch.xpu.synchronize()
    if returned.data_ptr() != eager_out.data_ptr():
        raise ContractError(f"KV {kv_len} post-mutation eager call ignored out")
    _assert_close(torch, eager_out.cpu(), expected, f"KV {kv_len} post-mutation eager")
    graph_out.fill_(float("nan"))
    torch.xpu.synchronize()
    graph.replay()
    torch.xpu.synchronize()
    _assert_close(torch, graph_out.cpu(), expected, f"KV {kv_len} post-mutation graph")

    eager_samples = _event_samples_us(
        torch, lambda: launch(eager_out), samples, launches
    )
    graph_samples = _event_samples_us(torch, graph.replay, samples, launches)
    return {
        "kv_length": kv_len,
        "fixture_seed": 380000 + kv_len,
        "fixture_sha256": fixture_digest(q_cpu, k_cache_cpu, v_cache_cpu, block_order),
        "oracle_sha256": tensor_digest(expected),
        "eager_output_sha256": eager_digests[0],
        "graph_output_sha256": graph_digests[0],
        "eager_bit_stable": True,
        "graph_bit_stable": True,
        "eager_graph_exact": True,
        "eager_static_out_honored": eager_pointer_honored,
        "graph_static_out_honored": True,
        "poison_checked_replays_per_mode": stability_replays,
        "eager_max_abs_diff": eager_max_abs_diff,
        "graph_max_abs_diff": graph_max_abs_diff,
        "mutations": mutation_records,
        "eager_samples_us_per_call": eager_samples,
        "graph_samples_us_per_call": graph_samples,
        "eager_median_us_per_call": statistics.median(eager_samples),
        "graph_median_us_per_call": statistics.median(graph_samples),
        "passed": True,
    }


def run_xpu(args: argparse.Namespace) -> dict[str, Any]:
    output = Path(args.output)
    temporary = Path(f"{output}.tmp")
    stderr_output = Path(f"{output}.stderr.log")
    stderr_temporary = Path(f"{stderr_output}.tmp")
    if any(
        path.exists() for path in (output, temporary, stderr_output, stderr_temporary)
    ):
        raise ContractError(f"refusing existing output or temporary path: {output}")
    started_ns = time.time_ns()
    identity = stage_identity(args)
    stage = Path(identity["stage"])
    if os.environ.get("VLLM_XPU_FA2_FORCE_CHUNK_DECODE") != "1":
        raise ContractError("VLLM_XPU_FA2_FORCE_CHUNK_DECODE must equal 1")
    expected_policy = "0" if args.role == "control" else "1"
    if os.environ.get(POLICY_ENV) != expected_policy:
        raise ContractError(
            f"{POLICY_ENV} must equal {expected_policy} for role {args.role}"
        )
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1" or not sys.dont_write_bytecode:
        raise ContractError(
            "PYTHONDONTWRITEBYTECODE=1 is required for sealed stage inventory"
        )
    pythonpath = os.environ.get("PYTHONPATH", "").split(os.pathsep)
    ld_library_path = os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep)
    if not pythonpath or Path(pythonpath[0]).resolve() != stage:
        raise ContractError("selected stage must be first in PYTHONPATH")
    if (
        not ld_library_path
        or Path(ld_library_path[0]).resolve() != stage / "vllm_xpu_kernels"
    ):
        raise ContractError("selected stage package must be first in LD_LIBRARY_PATH")
    if args.physical_gpu not in EXPECTED_PHYSICAL_GPUS:
        raise ContractError(
            f"physical GPU must be one of the preregistered {EXPECTED_PHYSICAL_GPUS}"
        )
    if os.environ.get("ZE_AFFINITY_MASK") != str(args.physical_gpu):
        raise ContractError("ZE_AFFINITY_MASK must select exactly the physical GPU")
    driver_text = os.environ.get("QWEN38_FA_CAMPAIGN_DRIVER")
    driver_sha = os.environ.get("QWEN38_FA_CAMPAIGN_DRIVER_SHA256")
    repo_head = os.environ.get("QWEN38_FA_LAB_REPO_HEAD")
    if not driver_text or not driver_sha or not repo_head:
        raise ContractError("campaign driver path/SHA and lab repo HEAD are required")
    driver_path = _canonical_absolute(driver_text, "campaign driver")
    if sha256_file(driver_path) != driver_sha:
        raise ContractError("campaign driver SHA mismatch")

    import torch  # pylint: disable=import-outside-toplevel

    if not torch.xpu.is_available():
        raise ContractError("XPU is unavailable")
    if torch.xpu.device_count() != 1:
        raise ContractError(
            f"expected exactly one affinity-scoped XPU, got {torch.xpu.device_count()}"
        )
    if not hasattr(torch.xpu, "XPUGraph") or not hasattr(torch.xpu, "graph"):
        raise ContractError("this PyTorch build lacks XPU graph support")
    logical_device = 0
    torch.xpu.set_device(logical_device)
    interface = importlib.import_module("vllm_xpu_kernels.flash_attn_interface")
    extension = importlib.import_module("vllm_xpu_kernels._vllm_fa2_C")
    if not bool(getattr(interface, "FA2_AVAILABLE", False)):
        raise ContractError(
            f"staged FA extension unavailable: {interface.FA2_UNAVAILABLE_REASON}"
        )
    if Path(interface.__file__).resolve() != Path(
        identity["files"]["interface"]["path"]
    ):
        raise ContractError(
            "imported FlashAttention interface is outside selected stage"
        )
    if Path(extension.__file__).resolve() != Path(
        identity["files"]["extension"]["path"]
    ):
        raise ContractError("imported FA extension is outside selected stage")

    output.parent.mkdir(parents=True, exist_ok=True)
    saved_stderr = os.dup(2)
    try:
        with stderr_temporary.open("wb") as stderr_stream:
            os.dup2(stderr_stream.fileno(), 2)
            try:
                cases = [
                    _run_case(
                        torch,
                        interface.flash_attn_varlen_func,
                        logical_device,
                        kv_len,
                        args.samples,
                        args.launches_per_sample,
                        args.stability_replays,
                    )
                    for kv_len in KV_LENGTHS
                ]
            finally:
                sys.stderr.flush()
                ctypes.CDLL(None).fflush(None)
                os.fsync(stderr_stream.fileno())
                os.dup2(saved_stderr, 2)
    except Exception:
        stderr_temporary.unlink(missing_ok=True)
        raise
    finally:
        os.close(saved_stderr)
    stderr_text = stderr_temporary.read_text(encoding="utf-8")
    marker_related = [line for line in stderr_text.splitlines() if POLICY_ENV in line]
    expected_markers = [] if args.role == "control" else [POLICY_MARKER]
    if marker_related != expected_markers:
        stderr_temporary.unlink(missing_ok=True)
        raise ContractError(
            f"policy marker mismatch: actual={marker_related} expected={expected_markers}"
        )
    os.chmod(stderr_temporary, 0o444)
    os.replace(stderr_temporary, stderr_output)
    mappings = mapped_paths()
    required_mappings = {
        "extension": Path(identity["files"]["extension"]["path"]),
        "device_library": Path(identity["files"]["device_library"]["path"]),
        "stock_library": Path(identity["files"]["stock_library"]["path"]),
    }
    for name, path in required_mappings.items():
        if path not in mappings:
            same_name = sorted(str(item) for item in mappings if item.name == path.name)
            raise ContractError(
                f"selected {name} not mapped: expected={path} mapped_same_name={same_name}"
            )

    process_stat = Path("/proc/self/stat").read_text(encoding="utf-8").split()
    packet = {
        "schema": SCHEMA_RUN,
        "passed": True,
        "role": args.role,
        "arm_id": args.arm_id,
        "campaign_slot": args.campaign_slot,
        "process": {
            "pid": os.getpid(),
            "start_ticks": require_int(int(process_stat[21]), "process start ticks"),
            "boot_id": Path("/proc/sys/kernel/random/boot_id")
            .read_text(encoding="utf-8")
            .strip(),
            "started_time_ns": started_ns,
            "finished_time_ns": time.time_ns(),
        },
        "operator_identity": {
            "dtype": "float16",
            "rows": ROWS,
            "mtp_depth": ROWS - 1,
            "q_heads_tp2_local": Q_HEADS,
            "kv_heads_tp2_local": KV_HEADS,
            "head_dim": HEAD_DIM,
            "block_size": BLOCK_SIZE,
            "kv_lengths": list(KV_LENGTHS),
            "causal": True,
            "paged_kv": True,
            "is_mix_batch": True,
            "vllm_xpu_fa2_force_chunk_decode": "1",
            "m6_head256_q8k64_policy": expected_policy,
        },
        "stage_identity": identity,
        "mapped_libraries": {
            name: {
                "path": str(path),
                "sha256": identity["files"][name]["sha256"],
            }
            for name, path in required_mappings.items()
        },
        "engagement": {
            "policy_env": POLICY_ENV,
            "policy_value": expected_policy,
            "expected_marker_count": 0 if args.role == "control" else 1,
            "marker_count": len(marker_related),
            "marker": None if args.role == "control" else POLICY_MARKER,
            "stderr_log_path": str(stderr_output.resolve(strict=True)),
            "stderr_log_sha256": sha256_file(stderr_output),
            "stderr_line_count": len(stderr_text.splitlines()),
        },
        "runtime_identity": {
            "script_path": str(Path(__file__).resolve()),
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "campaign_driver_path": str(driver_path),
            "campaign_driver_sha256": driver_sha,
            "lab_repo_head": repo_head,
            "python": sys.version,
            "python_dont_write_bytecode": True,
            "torch_version": torch.__version__,
            "xpu_device_count": torch.xpu.device_count(),
            "hostname": socket.gethostname(),
            "physical_gpu": args.physical_gpu,
            "logical_device": "xpu:0",
            "ze_affinity_mask": os.environ["ZE_AFFINITY_MASK"],
            "device_name": torch.xpu.get_device_name(logical_device),
            "device_properties": _device_properties(torch, logical_device),
            "pythonpath_first": pythonpath[0],
            "ld_library_path_first": ld_library_path[0],
        },
        "timing_contract": {
            "clock": "torch.xpu.Event device elapsed time",
            "samples_per_shape_mode": args.samples,
            "launches_per_sample": args.launches_per_sample,
            "stability_replays_per_shape_mode": args.stability_replays,
            "gated_mode": "xpu_graph_replay",
        },
        "cases": cases,
    }
    write_json_atomic(output, temporary, packet)
    return packet


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _case_center(
    packet: dict[str, Any], case_index: int, sample_indices: list[int] | None = None
) -> float:
    values = packet["cases"][case_index]["graph_samples_us_per_call"]
    if sample_indices is not None:
        values = [values[index] for index in sample_indices]
    return statistics.median(values)


def _validate_run_packet(packet: Any, path: Path) -> dict[str, Any]:
    if not isinstance(packet, dict):
        raise ContractError(f"{path}: run packet must be an object")
    require_exact_keys(
        packet,
        (
            "schema",
            "passed",
            "role",
            "arm_id",
            "campaign_slot",
            "process",
            "operator_identity",
            "stage_identity",
            "mapped_libraries",
            "engagement",
            "runtime_identity",
            "timing_contract",
            "cases",
        ),
        str(path),
    )
    if packet["schema"] != SCHEMA_RUN or packet["passed"] is not True:
        raise ContractError(f"{path}: schema/pass mismatch")
    if packet["role"] not in ("control", "candidate"):
        raise ContractError(f"{path}: invalid role")
    if not isinstance(packet["arm_id"], str) or not packet["arm_id"]:
        raise ContractError(f"{path}: invalid arm ID")
    slot = require_int(packet["campaign_slot"], f"{path}.campaign_slot")
    if slot not in (1, 2, 3, 4):
        raise ContractError(f"{path}: invalid campaign slot")
    identity = packet["operator_identity"]
    expected_identity = {
        "dtype": "float16",
        "rows": ROWS,
        "mtp_depth": 5,
        "q_heads_tp2_local": Q_HEADS,
        "kv_heads_tp2_local": KV_HEADS,
        "head_dim": HEAD_DIM,
        "block_size": BLOCK_SIZE,
        "kv_lengths": list(KV_LENGTHS),
        "causal": True,
        "paged_kv": True,
        "is_mix_batch": True,
        "vllm_xpu_fa2_force_chunk_decode": "1",
        "m6_head256_q8k64_policy": "0" if packet["role"] == "control" else "1",
    }
    if identity != expected_identity:
        raise ContractError(f"{path}: operator identity mismatch")
    timing = packet["timing_contract"]
    if not isinstance(timing, dict):
        raise ContractError(f"{path}: timing contract must be an object")
    require_exact_keys(
        timing,
        (
            "clock",
            "samples_per_shape_mode",
            "launches_per_sample",
            "stability_replays_per_shape_mode",
            "gated_mode",
        ),
        f"{path}.timing_contract",
    )
    samples = require_int(timing["samples_per_shape_mode"], f"{path}.samples")
    launches = require_int(timing["launches_per_sample"], f"{path}.launches")
    stability = require_int(
        timing["stability_replays_per_shape_mode"], f"{path}.stability"
    )
    if (
        timing["clock"] != "torch.xpu.Event device elapsed time"
        or timing["gated_mode"] != "xpu_graph_replay"
        or samples < MIN_SAMPLES
        or launches < MIN_LAUNCHES_PER_SAMPLE
        or stability < MIN_STABILITY_REPLAYS
    ):
        raise ContractError(f"{path}: timing contract is below preregistered minimum")
    cases = packet["cases"]
    if (
        not isinstance(cases, list)
        or not all(isinstance(case, dict) for case in cases)
        or [case.get("kv_length") for case in cases] != list(KV_LENGTHS)
    ):
        raise ContractError(f"{path}: case inventory/order mismatch")
    for case in cases:
        if not isinstance(case, dict):
            raise ContractError(f"{path}: case must be an object")
        require_exact_keys(
            case,
            (
                "kv_length",
                "fixture_seed",
                "fixture_sha256",
                "oracle_sha256",
                "eager_output_sha256",
                "graph_output_sha256",
                "eager_bit_stable",
                "graph_bit_stable",
                "eager_graph_exact",
                "eager_static_out_honored",
                "graph_static_out_honored",
                "poison_checked_replays_per_mode",
                "eager_max_abs_diff",
                "graph_max_abs_diff",
                "mutations",
                "eager_samples_us_per_call",
                "graph_samples_us_per_call",
                "eager_median_us_per_call",
                "graph_median_us_per_call",
                "passed",
            ),
            f"{path}.case",
        )
        kv_len = case["kv_length"]
        required_true = (
            "eager_bit_stable",
            "graph_bit_stable",
            "eager_graph_exact",
            "eager_static_out_honored",
            "graph_static_out_honored",
            "passed",
        )
        if any(case.get(name) is not True for name in required_true):
            raise ContractError(f"{path}: KV {kv_len} correctness gate false")
        if case.get("fixture_seed") != 380000 + kv_len:
            raise ContractError(f"{path}: KV {kv_len} fixture seed mismatch")
        if case.get("poison_checked_replays_per_mode") != stability:
            raise ContractError(f"{path}: KV {kv_len} poison count mismatch")
        for digest_name in (
            "fixture_sha256",
            "oracle_sha256",
            "eager_output_sha256",
            "graph_output_sha256",
        ):
            value = case.get(digest_name)
            if not isinstance(value, str) or len(value) != 64:
                raise ContractError(f"{path}: KV {kv_len} bad {digest_name}")
        eager_values = case.get("eager_samples_us_per_call")
        graph_values = case.get("graph_samples_us_per_call")
        if not isinstance(eager_values, list) or len(eager_values) != samples:
            raise ContractError(f"{path}: KV {kv_len} eager sample count mismatch")
        if not isinstance(graph_values, list) or len(graph_values) != samples:
            raise ContractError(f"{path}: KV {kv_len} graph sample count mismatch")
        eager = [
            require_finite(value, f"{path}: eager sample") for value in eager_values
        ]
        graph = [
            require_finite(value, f"{path}: graph sample") for value in graph_values
        ]
        if min(eager + graph) <= 0:
            raise ContractError(f"{path}: KV {kv_len} non-positive timing")
        if not math.isclose(
            require_finite(case.get("eager_median_us_per_call"), "eager median"),
            statistics.median(eager),
            rel_tol=0,
            abs_tol=1e-12,
        ) or not math.isclose(
            require_finite(case.get("graph_median_us_per_call"), "graph median"),
            statistics.median(graph),
            rel_tol=0,
            abs_tol=1e-12,
        ):
            raise ContractError(f"{path}: KV {kv_len} median does not recompute")
        if require_finite(case.get("eager_max_abs_diff"), "eager diff") > ATOL:
            raise ContractError(
                f"{path}: KV {kv_len} eager diff exceeds absolute tolerance"
            )
        if require_finite(case.get("graph_max_abs_diff"), "graph diff") > ATOL:
            raise ContractError(
                f"{path}: KV {kv_len} graph diff exceeds absolute tolerance"
            )
        mutations = case["mutations"]
        expected_mutations = (
            ("q_scale_0p875", "q", 0.875, kv_len),
            ("k_cache_scale_0p875", "k_cache", 0.875, kv_len),
            ("v_cache_scale_0p875", "v_cache", 0.875, kv_len),
            ("seqused_k_minus_64", "seqused_k", None, kv_len - BLOCK_SIZE),
        )
        if (
            not isinstance(mutations, list)
            or len(mutations) != len(expected_mutations)
            or not all(isinstance(item, dict) for item in mutations)
            or [item["name"] for item in mutations]
            != [item[0] for item in expected_mutations]
        ):
            raise ContractError(f"{path}: KV {kv_len} mutation inventory mismatch")
        input_digests: set[str] = set()
        for mutation, expected_mutation in zip(mutations, expected_mutations):
            require_exact_keys(
                mutation,
                (
                    "name",
                    "target",
                    "scale",
                    "seqused_k",
                    "input_sha256",
                    "oracle_sha256",
                    "eager_output_sha256",
                    "graph_output_sha256",
                    "eager_max_abs_diff",
                    "graph_max_abs_diff",
                    "repetitions_per_mode",
                    "output_changed_from_baseline",
                    "eager_graph_exact",
                    "restored_before_next",
                    "passed",
                ),
                f"{path}.case.mutation",
            )
            expected_name, expected_target, expected_scale, expected_kv = (
                expected_mutation
            )
            actual_scale = mutation["scale"]
            if expected_scale is not None:
                actual_scale = require_finite(actual_scale, "mutation scale")
            if (
                mutation["name"] != expected_name
                or mutation["target"] != expected_target
                or actual_scale != expected_scale
                or require_int(mutation["seqused_k"], "mutation seqused_k")
                != expected_kv
                or require_int(mutation["repetitions_per_mode"], "mutation repetitions")
                != MUTATION_REPETITIONS_PER_MODE
                or mutation["output_changed_from_baseline"] is not True
                or mutation["eager_graph_exact"] is not True
                or mutation["restored_before_next"] is not True
                or mutation["passed"] is not True
                or mutation["eager_output_sha256"] != mutation["graph_output_sha256"]
            ):
                raise ContractError(f"{path}: KV {kv_len} mutation contract failed")
            for digest_name in (
                "input_sha256",
                "oracle_sha256",
                "eager_output_sha256",
                "graph_output_sha256",
            ):
                digest = mutation[digest_name]
                if not isinstance(digest, str) or len(digest) != 64:
                    raise ContractError(
                        f"{path}: KV {kv_len} mutation bad {digest_name}"
                    )
                try:
                    int(digest, 16)
                except ValueError as error:
                    raise ContractError(
                        f"{path}: KV {kv_len} mutation non-hex {digest_name}"
                    ) from error
            input_digests.add(mutation["input_sha256"])
            if mutation["eager_output_sha256"] == case["eager_output_sha256"]:
                raise ContractError(f"{path}: KV {kv_len} mutation was output-inert")
            if (
                require_finite(mutation["eager_max_abs_diff"], "mutation eager diff")
                > ATOL
            ):
                raise ContractError(
                    f"{path}: KV {kv_len} mutation eager diff too large"
                )
            if (
                require_finite(mutation["graph_max_abs_diff"], "mutation graph diff")
                > ATOL
            ):
                raise ContractError(
                    f"{path}: KV {kv_len} mutation graph diff too large"
                )
        if len(input_digests) != len(expected_mutations):
            raise ContractError(f"{path}: KV {kv_len} mutation input digests collide")
    runtime = packet["runtime_identity"]
    if not isinstance(runtime, dict):
        raise ContractError(f"{path}: runtime identity must be an object")
    require_exact_keys(
        runtime,
        (
            "script_path",
            "script_sha256",
            "campaign_driver_path",
            "campaign_driver_sha256",
            "lab_repo_head",
            "python",
            "python_dont_write_bytecode",
            "torch_version",
            "xpu_device_count",
            "hostname",
            "physical_gpu",
            "logical_device",
            "ze_affinity_mask",
            "device_name",
            "device_properties",
            "pythonpath_first",
            "ld_library_path_first",
        ),
        f"{path}.runtime_identity",
    )
    if (
        runtime.get("xpu_device_count") != 1
        or runtime.get("physical_gpu") not in EXPECTED_PHYSICAL_GPUS
        or runtime.get("logical_device") != "xpu:0"
        or runtime.get("ze_affinity_mask") != str(runtime.get("physical_gpu"))
        or runtime.get("device_name") != EXPECTED_DEVICE_NAME
        or not isinstance(runtime.get("hostname"), str)
        or not runtime.get("hostname")
    ):
        raise ContractError(f"{path}: device identity mismatch")
    if runtime["python_dont_write_bytecode"] is not True:
        raise ContractError(f"{path}: bytecode writes were not disabled")
    for name in ("script_sha256", "campaign_driver_sha256"):
        value = runtime.get(name)
        if not isinstance(value, str) or len(value) != 64:
            raise ContractError(f"{path}: missing or malformed {name}")
        try:
            int(value, 16)
        except ValueError as error:
            raise ContractError(f"{path}: non-hexadecimal {name}") from error
    repo_head = runtime.get("lab_repo_head")
    if not isinstance(repo_head, str) or len(repo_head) != 40:
        raise ContractError(f"{path}: malformed lab_repo_head")
    try:
        int(repo_head, 16)
    except ValueError as error:
        raise ContractError(f"{path}: non-hexadecimal lab_repo_head") from error
    stage = packet["stage_identity"]
    if not isinstance(stage, dict) or stage.get("role") != packet["role"]:
        raise ContractError(f"{path}: stage role mismatch")
    require_exact_keys(
        stage,
        (
            "role",
            "stage",
            "hashes",
            "manifest_path",
            "manifest_sha256",
            "artifact_path",
            "artifact_sha256",
            "graph_manifest_path",
            "graph_manifest_sha256",
            "files",
        ),
        f"{path}.stage_identity",
    )
    if set(stage.get("hashes", {})) != set(RELATIVE_FILES):
        raise ContractError(f"{path}: stage hash inventory mismatch")
    files = stage.get("files")
    if not isinstance(files, dict) or set(files) != set(RELATIVE_FILES):
        raise ContractError(f"{path}: stage file inventory mismatch")
    for name, entry in files.items():
        if not isinstance(entry, dict):
            raise ContractError(f"{path}: stage file {name} is not an object")
        require_exact_keys(
            entry, ("path", "relative_path", "sha256"), f"{path}.files.{name}"
        )
        if (
            entry["relative_path"] != RELATIVE_FILES[name]
            or entry["sha256"] != stage["hashes"][name]
            or entry["path"] != str(Path(stage["stage"]) / RELATIVE_FILES[name])
        ):
            raise ContractError(f"{path}: stage file {name} identity mismatch")
    if packet["role"] == "control":
        if (
            stage.get("stage") != str(CONTROL_STAGE)
            or stage.get("hashes") != CONTROL_HASHES
        ):
            raise ContractError(f"{path}: control stage identity mismatch")
        if any(
            stage.get(name) is not None
            for name in (
                "manifest_path",
                "manifest_sha256",
                "artifact_path",
                "artifact_sha256",
                "graph_manifest_path",
                "graph_manifest_sha256",
            )
        ):
            raise ContractError(
                f"{path}: control unexpectedly has candidate provenance"
            )
    else:
        manifest_sha = stage.get("manifest_sha256")
        if not isinstance(manifest_sha, str) or len(manifest_sha) != 64:
            raise ContractError(f"{path}: candidate manifest SHA missing")
        for fixed_name in ("extension", "interface", "stock_library"):
            if stage["hashes"][fixed_name] != CONTROL_HASHES[fixed_name]:
                raise ContractError(
                    f"{path}: candidate changed fixed {fixed_name} boundary"
                )
        if stage["hashes"]["device_library"] == CONTROL_HASHES["device_library"]:
            raise ContractError(f"{path}: candidate device library equals control")
        artifact_path = stage.get("artifact_path")
        artifact_sha = stage.get("artifact_sha256")
        if (
            not isinstance(artifact_path, str)
            or Path(artifact_path).name != BUILD_INPUTS_BASENAME
            or not isinstance(artifact_sha, str)
            or len(artifact_sha) != 64
        ):
            raise ContractError(f"{path}: candidate build-input artifact mismatch")
        graph_manifest_path = stage.get("graph_manifest_path")
        graph_manifest_sha = stage.get("graph_manifest_sha256")
        if (
            not isinstance(graph_manifest_path, str)
            or Path(graph_manifest_path).name != GRAPH_MANIFEST_BASENAME
            or not isinstance(graph_manifest_sha, str)
            or len(graph_manifest_sha) != 64
        ):
            raise ContractError(f"{path}: candidate graph manifest identity missing")
    mappings = packet["mapped_libraries"]
    if not isinstance(mappings, dict) or set(mappings) != {
        "extension",
        "device_library",
        "stock_library",
    }:
        raise ContractError(f"{path}: mapped library inventory mismatch")
    for name, mapping in mappings.items():
        if not isinstance(mapping, dict):
            raise ContractError(f"{path}: mapped {name} is not an object")
        require_exact_keys(mapping, ("path", "sha256"), f"{path}.mapped.{name}")
        file_entry = stage.get("files", {}).get(name, {})
        if mapping != {
            "path": file_entry.get("path"),
            "sha256": file_entry.get("sha256"),
        }:
            raise ContractError(f"{path}: mapped {name} does not match stage identity")
    if runtime["pythonpath_first"] != stage["stage"] or runtime[
        "ld_library_path_first"
    ] != str(Path(stage["stage"]) / "vllm_xpu_kernels"):
        raise ContractError(f"{path}: runtime search path does not select packet stage")
    engagement = packet["engagement"]
    if not isinstance(engagement, dict):
        raise ContractError(f"{path}: engagement must be an object")
    require_exact_keys(
        engagement,
        (
            "policy_env",
            "policy_value",
            "expected_marker_count",
            "marker_count",
            "marker",
            "stderr_log_path",
            "stderr_log_sha256",
            "stderr_line_count",
        ),
        f"{path}.engagement",
    )
    expected_marker_count = 0 if packet["role"] == "control" else 1
    expected_marker = None if packet["role"] == "control" else POLICY_MARKER
    if (
        engagement["policy_env"] != POLICY_ENV
        or engagement["policy_value"] != ("0" if packet["role"] == "control" else "1")
        or require_int(engagement["expected_marker_count"], "expected marker count")
        != expected_marker_count
        or require_int(engagement["marker_count"], "marker count")
        != expected_marker_count
        or engagement["marker"] != expected_marker
        or require_int(engagement["stderr_line_count"], "stderr line count") < 0
    ):
        raise ContractError(f"{path}: policy engagement marker mismatch")
    stderr_sha = engagement["stderr_log_sha256"]
    if not isinstance(stderr_sha, str) or len(stderr_sha) != 64:
        raise ContractError(f"{path}: malformed stderr log SHA")
    process = packet["process"]
    if not isinstance(process, dict):
        raise ContractError(f"{path}: process identity missing")
    require_exact_keys(
        process,
        (
            "pid",
            "start_ticks",
            "boot_id",
            "started_time_ns",
            "finished_time_ns",
        ),
        f"{path}.process",
    )
    if not isinstance(process["boot_id"], str) or not process["boot_id"]:
        raise ContractError(f"{path}: invalid boot ID")
    for name in ("pid", "start_ticks", "started_time_ns", "finished_time_ns"):
        require_int(process.get(name), f"{path}.process.{name}")
    if process["finished_time_ns"] <= process["started_time_ns"]:
        raise ContractError(f"{path}: invalid process time interval")
    return packet


def compare_packets(
    packets: list[dict[str, Any]], bootstrap_iterations: int
) -> dict[str, Any]:
    if len(packets) != 8:
        raise ContractError(f"expected eight fresh-process packets, got {len(packets)}")
    if bootstrap_iterations < 5000:
        raise ContractError("bootstrap iterations must be at least 5000")
    script_shas = {packet["runtime_identity"]["script_sha256"] for packet in packets}
    driver_shas = {
        packet["runtime_identity"]["campaign_driver_sha256"] for packet in packets
    }
    repo_heads = {packet["runtime_identity"]["lab_repo_head"] for packet in packets}
    hostnames = {packet["runtime_identity"]["hostname"] for packet in packets}
    timing_contracts = {
        json.dumps(packet["timing_contract"], sort_keys=True) for packet in packets
    }
    if (
        len(script_shas) != 1
        or len(driver_shas) != 1
        or len(repo_heads) != 1
        or len(hostnames) != 1
        or len(timing_contracts) != 1
    ):
        raise ContractError("run harness/timing contract differs across packets")
    process_ids = {
        (
            packet["process"]["boot_id"],
            packet["process"]["pid"],
            packet["process"]["start_ticks"],
        )
        for packet in packets
    }
    if len(process_ids) != 8:
        raise ContractError("the eight arms are not eight distinct processes")
    if len({packet["process"]["boot_id"] for packet in packets}) != 1:
        raise ContractError("campaign packets do not come from one boot")
    chronological = sorted(
        packets, key=lambda packet: packet["process"]["started_time_ns"]
    )
    expected_global_order = [
        "gpu2-a1",
        "gpu2-b1",
        "gpu2-b2",
        "gpu2-a2",
        "gpu3-a1",
        "gpu3-b1",
        "gpu3-b2",
        "gpu3-a2",
    ]
    if [packet["arm_id"] for packet in chronological] != expected_global_order:
        raise ContractError("campaign process order is not the preregistered sequence")
    for previous, current in zip(chronological, chronological[1:]):
        if (
            previous["process"]["finished_time_ns"]
            > current["process"]["started_time_ns"]
        ):
            raise ContractError("campaign processes overlap")
    for role in ("control", "candidate"):
        identities = {
            json.dumps(
                {
                    "stage": packet["stage_identity"]["stage"],
                    "hashes": packet["stage_identity"]["hashes"],
                    "manifest_sha256": packet["stage_identity"]["manifest_sha256"],
                    "artifact_sha256": packet["stage_identity"]["artifact_sha256"],
                    "graph_manifest_sha256": packet["stage_identity"][
                        "graph_manifest_sha256"
                    ],
                },
                sort_keys=True,
            )
            for packet in packets
            if packet["role"] == role
        }
        if len(identities) != 1:
            raise ContractError(f"{role} stage identity differs across devices")

    by_device: dict[int, list[dict[str, Any]]] = {2: [], 3: []}
    for packet in packets:
        by_device[packet["runtime_identity"]["physical_gpu"]].append(packet)
    if any(len(items) != 4 for items in by_device.values()):
        raise ContractError("each preregistered B70 must have exactly four arms")

    device_results: list[dict[str, Any]] = []
    all_passed = True
    for device, arms in sorted(by_device.items()):
        arms.sort(key=lambda packet: packet["campaign_slot"])
        if [packet["role"] for packet in arms] != [
            "control",
            "candidate",
            "candidate",
            "control",
        ]:
            raise ContractError(f"device {device}: order is not ABBA")
        if [packet["arm_id"] for packet in arms] != [
            f"gpu{device}-a1",
            f"gpu{device}-b1",
            f"gpu{device}-b2",
            f"gpu{device}-a2",
        ]:
            raise ContractError(f"device {device}: arm IDs do not match ABBA slots")
        for previous, current in zip(arms, arms[1:]):
            if (
                previous["process"]["finished_time_ns"]
                > current["process"]["started_time_ns"]
            ):
                raise ContractError(
                    f"device {device}: arms overlap or are out of order"
                )
        if (
            len(
                {
                    json.dumps(
                        {
                            "name": arm["runtime_identity"]["device_name"],
                            "properties": arm["runtime_identity"]["device_properties"],
                            "python": arm["runtime_identity"]["python"],
                            "torch": arm["runtime_identity"]["torch_version"],
                        },
                        sort_keys=True,
                    )
                    for arm in arms
                }
            )
            != 1
        ):
            raise ContractError(f"device {device}: device name changed across ABBA")
        control_ids = {
            json.dumps(arm["stage_identity"]["hashes"], sort_keys=True)
            for arm in arms
            if arm["role"] == "control"
        }
        candidate_ids = {
            (
                arm["stage_identity"]["manifest_sha256"],
                json.dumps(arm["stage_identity"]["hashes"], sort_keys=True),
            )
            for arm in arms
            if arm["role"] == "candidate"
        }
        if len(control_ids) != 1 or len(candidate_ids) != 1:
            raise ContractError(f"device {device}: stage identity drifted within role")
        for case_index, kv_len in enumerate(KV_LENGTHS):
            fixtures = {arm["cases"][case_index]["fixture_sha256"] for arm in arms}
            oracles = {arm["cases"][case_index]["oracle_sha256"] for arm in arms}
            outputs = {
                arm["cases"][case_index][mode]
                for arm in arms
                for mode in ("eager_output_sha256", "graph_output_sha256")
            }
            if len(fixtures) != 1 or len(oracles) != 1 or len(outputs) != 1:
                raise ContractError(
                    f"device {device} KV {kv_len}: fixture/oracle/exact output parity failed"
                )
            for mutation_index, mutation_name in enumerate(
                (
                    "q_scale_0p875",
                    "k_cache_scale_0p875",
                    "v_cache_scale_0p875",
                    "seqused_k_minus_64",
                )
            ):
                mutation_inputs = {
                    arm["cases"][case_index]["mutations"][mutation_index][
                        "input_sha256"
                    ]
                    for arm in arms
                }
                mutation_oracles = {
                    arm["cases"][case_index]["mutations"][mutation_index][
                        "oracle_sha256"
                    ]
                    for arm in arms
                }
                mutation_outputs = {
                    arm["cases"][case_index]["mutations"][mutation_index][mode]
                    for arm in arms
                    for mode in ("eager_output_sha256", "graph_output_sha256")
                }
                if (
                    len(mutation_inputs) != 1
                    or len(mutation_oracles) != 1
                    or len(mutation_outputs) != 1
                ):
                    raise ContractError(
                        f"device {device} KV {kv_len} {mutation_name}: "
                        "mutation digest parity failed"
                    )
        control_arms = [arm for arm in arms if arm["role"] == "control"]
        candidate_arms = [arm for arm in arms if arm["role"] == "candidate"]
        abba_pairs = ((arms[0], arms[1]), (arms[3], arms[2]))
        case_results: list[dict[str, Any]] = []
        central_savings: dict[int, float] = {}
        control_centers_by_kv: dict[int, list[float]] = {}
        candidate_centers_by_kv: dict[int, list[float]] = {}
        for case_index, kv_len in enumerate(KV_LENGTHS):
            control_centers = [_case_center(arm, case_index) for arm in control_arms]
            candidate_centers = [
                _case_center(arm, case_index) for arm in candidate_arms
            ]
            control_centers_by_kv[kv_len] = control_centers
            candidate_centers_by_kv[kv_len] = candidate_centers
            paired_savings = [
                _case_center(control_arm, case_index)
                - _case_center(candidate_arm, case_index)
                for control_arm, candidate_arm in abba_pairs
            ]
            central_savings[kv_len] = statistics.mean(paired_savings)

        rng = random.Random(386000 + device)
        bootstrap_savings: dict[int, list[float]] = {
            kv_len: [] for kv_len in KV_LENGTHS
        }
        for _ in range(bootstrap_iterations):
            for case_index, kv_len in enumerate(KV_LENGTHS):
                pair_savings: list[float] = []
                for control_arm, candidate_arm in abba_pairs:
                    sample_count = len(
                        control_arm["cases"][case_index]["graph_samples_us_per_call"]
                    )
                    indices = [rng.randrange(sample_count) for _ in range(sample_count)]
                    pair_savings.append(
                        _case_center(control_arm, case_index, indices)
                        - _case_center(candidate_arm, case_index, indices)
                    )
                bootstrap_savings[kv_len].append(statistics.mean(pair_savings))
        ci_by_kv: dict[int, tuple[float, float]] = {}
        for kv_len in KV_LENGTHS:
            saving_ci = (
                _percentile(bootstrap_savings[kv_len], 0.025),
                _percentile(bootstrap_savings[kv_len], 0.975),
            )
            ci_by_kv[kv_len] = saving_ci
            case_results.append(
                {
                    "kv_length": kv_len,
                    "control_arm_medians_us_per_call": control_centers_by_kv[kv_len],
                    "candidate_arm_medians_us_per_call": candidate_centers_by_kv[
                        kv_len
                    ],
                    "paired_abba_savings_us_per_call": [
                        _case_center(control_arm, KV_LENGTHS.index(kv_len))
                        - _case_center(candidate_arm, KV_LENGTHS.index(kv_len))
                        for control_arm, candidate_arm in abba_pairs
                    ],
                    "central_saving_us_per_call": central_savings[kv_len],
                    "bootstrap_95_ci_saving_us_per_call": list(saving_ci),
                    "bootstrap_95_ci_candidate_regression_us_per_call": [
                        -saving_ci[1],
                        -saving_ci[0],
                    ],
                }
            )
        kv1300_saving = central_savings[1300]
        saving_per_16_ms = kv1300_saving * 16.0 / 1000.0
        kv128_regression_ci_upper = -ci_by_kv[128][0]
        passed = (
            kv1300_saving >= MIN_SAVING_US_PER_CALL
            and saving_per_16_ms >= MIN_SAVING_MS_PER_16
            and ci_by_kv[1024][0] > 0.0
            and ci_by_kv[1300][0] > 0.0
            and ci_by_kv[2048][0] > 0.0
            and kv128_regression_ci_upper <= MAX_KV128_REGRESSION_US_PER_CALL
        )
        all_passed = all_passed and passed
        device_results.append(
            {
                "physical_gpu": device,
                "logical_device": "xpu:0",
                "device_name": arms[0]["runtime_identity"]["device_name"],
                "cases": case_results,
                "kv1300_central_saving_us_per_call": kv1300_saving,
                "kv1300_saving_ms_per_16_fa_calls": saving_per_16_ms,
                "kv1024_1300_2048_ci_lower_positive": all(
                    ci_by_kv[kv_len][0] > 0.0 for kv_len in (1024, 1300, 2048)
                ),
                "kv128_regression_ci_upper_us_per_call": kv128_regression_ci_upper,
                "kv128_regression_within_2us": (
                    kv128_regression_ci_upper <= MAX_KV128_REGRESSION_US_PER_CALL
                ),
                "exact_control_candidate_output_parity": True,
                "passed": passed,
            }
        )
    return {
        "schema": SCHEMA_COMPARE,
        "passed": all_passed,
        "classification": (
            "candidate-qualified-for-endpoint-campaign"
            if all_passed
            else "candidate-rejected-at-operator-gate"
        ),
        "gated_mode": "xpu_graph_replay",
        "primary_kv_length": 1300,
        "minimum_kv1300_saving_us_per_call_each_gpu": MIN_SAVING_US_PER_CALL,
        "minimum_kv1300_saving_ms_per_16_fa_calls_each_gpu": MIN_SAVING_MS_PER_16,
        "positive_ci_required_kv_lengths": [1024, 1300, 2048],
        "maximum_kv128_regression_ci_upper_us_per_call": (
            MAX_KV128_REGRESSION_US_PER_CALL
        ),
        "bootstrap_iterations": bootstrap_iterations,
        "requires_ci_excluding_zero": True,
        "requires_bit_stability": True,
        "requires_exact_control_candidate_output_parity": True,
        "device_results": device_results,
    }


def compare_command(args: argparse.Namespace) -> dict[str, Any]:
    output = Path(args.output)
    temporary = Path(f"{output}.tmp")
    if output.exists() or temporary.exists():
        raise ContractError(f"refusing existing comparison output: {output}")
    loaded = [
        _validate_run_packet(load_json(Path(path)), Path(path)) for path in args.packets
    ]
    candidate_packets = [packet for packet in loaded if packet["role"] == "candidate"]
    manifest_references = {
        (
            packet["stage_identity"]["manifest_path"],
            packet["stage_identity"]["manifest_sha256"],
        )
        for packet in candidate_packets
    }
    if len(manifest_references) != 1:
        raise ContractError("candidate manifest identity differs across packets")
    manifest_path_text, manifest_sha = next(iter(manifest_references))
    manifest_path = Path(manifest_path_text)
    if not manifest_path.is_file() or sha256_file(manifest_path) != manifest_sha:
        raise ContractError(
            f"candidate stage manifest missing or changed: {manifest_path}"
        )
    identity = validate_candidate_manifest(manifest_path)
    for packet in candidate_packets:
        for key in (
            "stage",
            "hashes",
            "manifest_path",
            "manifest_sha256",
            "artifact_path",
            "artifact_sha256",
            "graph_manifest_path",
            "graph_manifest_sha256",
        ):
            if packet["stage_identity"][key] != identity[key]:
                raise ContractError(
                    f"candidate manifest revalidation differs for {key}: {manifest_path}"
                )
    for packet in loaded:
        stderr_path = Path(packet["engagement"]["stderr_log_path"])
        if (
            not stderr_path.is_file()
            or sha256_file(stderr_path) != packet["engagement"]["stderr_log_sha256"]
        ):
            raise ContractError(
                f"stderr engagement log missing or changed: {stderr_path}"
            )
        try:
            stderr_lines = stderr_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            raise ContractError(
                f"invalid stderr engagement log: {stderr_path}"
            ) from error
        if len(stderr_lines) != packet["engagement"]["stderr_line_count"]:
            raise ContractError(f"stderr line count changed: {stderr_path}")
        marker_lines = [line for line in stderr_lines if POLICY_ENV in line]
        expected_lines = [] if packet["role"] == "control" else [POLICY_MARKER]
        if marker_lines != expected_lines:
            raise ContractError(f"stderr policy marker evidence changed: {stderr_path}")
    result = compare_packets(loaded, args.bootstrap_iterations)
    result["packet_paths"] = [
        str(Path(path).resolve(strict=True)) for path in args.packets
    ]
    result["packet_sha256"] = [sha256_file(Path(path)) for path in args.packets]
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output, temporary, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-stage")
    validate.add_argument("--role", choices=("control", "candidate"), required=True)
    validate.add_argument("--stage")
    validate.add_argument("--stage-manifest")

    run = subparsers.add_parser("run")
    run.add_argument("--role", choices=("control", "candidate"), required=True)
    run.add_argument("--stage")
    run.add_argument("--stage-manifest")
    run.add_argument("--physical-gpu", type=int, required=True)
    run.add_argument("--arm-id", required=True)
    run.add_argument("--campaign-slot", type=int, choices=(1, 2, 3, 4), required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--samples", type=int, default=40)
    run.add_argument("--launches-per-sample", type=int, default=100)
    run.add_argument("--stability-replays", type=int, default=32)

    compare = subparsers.add_parser("compare")
    compare.add_argument("--output", required=True)
    compare.add_argument("--bootstrap-iterations", type=int, default=10000)
    compare.add_argument("packets", nargs=8)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "validate-stage":
            identity = stage_identity(args)
            print(json.dumps(identity, indent=2, sort_keys=True))
            return 0
        if args.command == "run":
            if args.samples < MIN_SAMPLES:
                parser.error(f"--samples must be >= {MIN_SAMPLES}")
            if args.launches_per_sample < MIN_LAUNCHES_PER_SAMPLE:
                parser.error(
                    f"--launches-per-sample must be >= {MIN_LAUNCHES_PER_SAMPLE}"
                )
            if args.stability_replays < MIN_STABILITY_REPLAYS:
                parser.error(f"--stability-replays must be >= {MIN_STABILITY_REPLAYS}")
            packet = run_xpu(args)
            print(
                json.dumps(
                    {"passed": True, "output": args.output, "arm": packet["arm_id"]}
                )
            )
            return 0
        result = compare_command(args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["passed"] else 14
    except ContractError as error:
        print(f"error: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
