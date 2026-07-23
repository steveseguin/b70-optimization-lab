#!/usr/bin/env python3
"""Fail-closed component gate for Laguna's exact M=8 BF16 router top-k.

Reference A materializes BF16 logits as FP32 before the incumbent sigmoid/top-k:

    logits.float() + torch.ops._moe_C.topk_sigmoid(..., True, bias, 1.0)

Candidate B loads BF16 directly but must reproduce A's FP32 sigmoid and top-k
arithmetic:

    torch.ops._moe_C.laguna_m8_bf16_topk_sigmoid(..., logits, bias)

Run one process per physical B70 with ONEAPI_DEVICE_SELECTOR and
ZE_AFFINITY_MASK set so that exactly one XPU is visible.  ``--validate-corpus-
only`` validates the complete generated corpus without importing Torch.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
import platform
import random
import statistics
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


ROWS = 8
EXPERTS = 256
TOPK = 10
RANDOM_EPOCHS = 128
ADVERSARIAL_EPOCHS = 64
SYNTHETIC_EPOCHS = RANDOM_EPOCHS + ADVERSARIAL_EPOCHS
PRODUCTION_TRACE_SETS = 3
PRODUCTION_LAYERS = 47
PRODUCTION_EPOCHS = PRODUCTION_TRACE_SETS * PRODUCTION_LAYERS
PRE_TIMING_EPOCHS = SYNTHETIC_EPOCHS + PRODUCTION_EPOCHS
POST_TIMING_EPOCHS = ADVERSARIAL_EPOCHS + PRODUCTION_LAYERS
PRODUCTION_CALLS = 47
WARMUP_CYCLES_PER_ARM = 20
TIMING_BLOCKS = 31
CYCLES_PER_ARM = 64
MIN_CANDIDATE_WINS = 24
MIN_SAVED_MS_PER_CYCLE = 0.20
MIN_GAIN_PCT = 20.0
BASE_SEED = 8_256_000

ADVERSARIAL_CATEGORIES = (
    "ties",
    "adjacent_cutoff",
    "lane_boundaries",
    "signed_zero",
    "saturation",
    "permutations",
    "bias_cutoff",
    "repeated_groups",
)
LANE_BOUNDARIES = (0, 3, 4, 7, 8, 31, 32, 63, 64, 127, 128, 255)

DEFAULT_KERNEL_ROOT = Path(
    "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc"
)
DEFAULT_VLLM_ROOT = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark")
DEFAULT_MODEL_ROOT = Path(
    "/media/steve/CorsairExternal/llm-optimization-artifacts/"
    "laguna-s-2.1/int4"
)
DEFAULT_TRACE_DIRS = (
    Path(
        "/media/steve/CorsairExternal/llm-optimization-artifacts/"
        "laguna-s-2.1/runs/"
        "exactness-all-detail-q8-rowwise-ar-eager-bf16-20260722/trace"
    ),
    Path(
        "/media/steve/CorsairExternal/llm-optimization-artifacts/"
        "laguna-s-2.1/runs/"
        "exactness-all-detail-q8-rowwise-eager-bf16-20260722/trace"
    ),
    Path(
        "/media/steve/CorsairExternal/llm-optimization-artifacts/"
        "laguna-s-2.1/runs/"
        "exactness-component-trace-q8-eager-bf16-20260722/trace"
    ),
)
DEFAULT_SOURCE_FILES = (
    DEFAULT_KERNEL_ROOT / "csrc/moe/topk.cpp",
    DEFAULT_KERNEL_ROOT / "csrc/moe/torch_bindings.cpp",
    DEFAULT_KERNEL_ROOT / "csrc/moe/moe_ops.h",
    DEFAULT_VLLM_ROOT / "vllm/_custom_ops.py",
    DEFAULT_VLLM_ROOT
    / "vllm/model_executor/layers/fused_moe/router/fused_topk_bias_router.py",
    DEFAULT_VLLM_ROOT
    / "vllm/model_executor/layers/fused_moe/router/router_factory.py",
    DEFAULT_VLLM_ROOT / "vllm/model_executor/models/laguna.py",
)


@dataclass(frozen=True)
class Fixture:
    name: str
    family: str
    category: str
    seed: int
    logits_bf16_bits: tuple[int, ...]
    bias_fp32_bits: tuple[int, ...]
    expected_tie_ids: tuple[tuple[int, ...], ...] | None = None


@dataclass
class RuntimeFixture:
    name: str
    family: str
    category: str
    seed: int | None
    logits: Any
    bias: Any
    fixture_sha256: str
    expected_tie_ids: tuple[tuple[int, ...], ...] | None
    evidence: dict[str, Any]


def f32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def f32_to_bf16_bits(value: float) -> int:
    """Round a Python number to float32 and then BF16, round-to-nearest-even."""
    bits = f32_bits(value)
    if bits & 0x7F800000 == 0x7F800000:
        return (bits >> 16) & 0xFFFF
    return ((bits + 0x7FFF + ((bits >> 16) & 1)) >> 16) & 0xFFFF


def bf16_value(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits << 16))[0]


def raw_fixture_hash(fixture: Fixture) -> str:
    digest = hashlib.sha256()
    for value in fixture.logits_bf16_bits:
        digest.update(struct.pack("<H", value))
    for value in fixture.bias_fp32_bits:
        digest.update(struct.pack("<I", value))
    return digest.hexdigest()


def make_random_fixture(epoch: int) -> Fixture:
    seed = BASE_SEED + epoch
    rng = random.Random(seed)
    scale = (0.03125, 0.125, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0)[epoch % 8]
    logits: list[int] = []
    for row in range(ROWS):
        for expert in range(EXPERTS):
            value = rng.gauss(0.0, scale)
            value += (row - 3.5) * scale / 64.0
            value += ((expert % 17) - 8) * scale / 2048.0
            logits.append(f32_to_bf16_bits(value))

    # Most epochs use the checkpoint's production-zero correction bias.  Every
    # fourth epoch additionally exercises the FP32 bias load/arithmetic.
    if epoch % 4 == 3:
        bias = tuple(f32_bits(rng.uniform(-0.015625, 0.015625)) for _ in range(EXPERTS))
    else:
        bias = (f32_bits(0.0),) * EXPERTS
    return Fixture(
        name=f"random-{epoch:03d}",
        family="random",
        category="seeded_random",
        seed=seed,
        logits_bf16_bits=tuple(logits),
        bias_fp32_bits=bias,
    )


def rotated(indices: Sequence[int], amount: int) -> list[int]:
    return [int((index + amount) % EXPERTS) for index in indices]


def make_adversarial_fixture(epoch: int) -> Fixture:
    category = ADVERSARIAL_CATEGORIES[epoch % len(ADVERSARIAL_CATEGORIES)]
    variant = epoch // len(ADVERSARIAL_CATEGORIES)
    seed = BASE_SEED + 900_000 + epoch
    rng = random.Random(seed)
    rows: list[list[int]] = []
    bias_values = [0.0] * EXPERTS
    tie_expectations: list[tuple[int, ...]] = []

    for row_index in range(ROWS):
        phase = variant * 13 + row_index * 7
        row = [
            f32_to_bf16_bits(-7.0 - ((expert * 5 + phase) % 31) / 16.0)
            for expert in range(EXPERTS)
        ]

        if category == "ties":
            winners = rotated(LANE_BOUNDARIES, phase)
            tied = f32_to_bf16_bits(2.0 + variant / 8.0)
            for expert in winners:
                row[expert] = tied
        elif category == "adjacent_cutoff":
            winners = rotated(LANE_BOUNDARIES, phase)
            base = f32_to_bf16_bits(1.0 + variant / 16.0)
            for order, expert in enumerate(winners):
                row[expert] = base + len(winners) - order
        elif category == "lane_boundaries":
            winners = rotated(LANE_BOUNDARIES, variant + row_index)
            base = f32_to_bf16_bits(3.0 + variant / 8.0)
            for order, expert in enumerate(winners):
                row[expert] = base + len(winners) - order
        elif category == "signed_zero":
            for expert in range(EXPERTS):
                row[expert] = 0x8000 if (expert + phase) % 3 == 0 else 0x0000
        elif category == "saturation":
            saturation = (64.0, 32.0, 16.0, 12.0, 10.0, 8.0)
            winners = rotated(LANE_BOUNDARIES, phase)
            for order, expert in enumerate(winners):
                row[expert] = f32_to_bf16_bits(saturation[order % len(saturation)])
            for expert in rotated((1, 5, 33, 65, 129, 253), phase):
                row[expert] = f32_to_bf16_bits(-saturation[expert % len(saturation)])
        elif category == "permutations":
            row = [
                f32_to_bf16_bits((expert - 128) / 16.0)
                for expert in range(EXPERTS)
            ]
            rng.shuffle(row)
        elif category == "bias_cutoff":
            winners = rotated(LANE_BOUNDARIES, phase)
            tied = f32_to_bf16_bits(0.75 + variant / 16.0)
            for order, expert in enumerate(winners):
                row[expert] = tied
                bias_values[expert] = (len(winners) - order) * 2.0**-18
        elif category == "repeated_groups":
            for expert in range(EXPERTS):
                group = expert // 4
                row[expert] = f32_to_bf16_bits(((group + phase) % 23 - 11) / 8.0)
            for order, expert in enumerate(rotated(LANE_BOUNDARIES, phase)):
                row[expert] = f32_to_bf16_bits(4.0 - order / 16.0)
        else:
            raise AssertionError(f"unknown adversarial category {category}")

        # A far-negative, epoch-specific marker makes the logits themselves
        # change in every adversarial epoch without entering the selected set.
        marker_expert = (241 + epoch * 17 + row_index * 11) % EXPERTS
        row[marker_expert] = f32_to_bf16_bits(-20.0 - epoch - row_index / 8.0)
        if category == "ties":
            actual_tied = tuple(
                expert for expert, value in enumerate(row) if value == tied
            )
            if len(actual_tied) < TOPK:
                raise AssertionError("designed tie no longer straddles top-k")
            tie_expectations.append(actual_tied[:TOPK])
        rows.append(row)

    return Fixture(
        name=f"adversarial-{epoch:02d}-{category}",
        family="adversarial",
        category=category,
        seed=seed,
        logits_bf16_bits=tuple(value for row in rows for value in row),
        bias_fp32_bits=tuple(f32_bits(value) for value in bias_values),
        expected_tie_ids=(
            tuple(tie_expectations) if category == "ties" else None
        ),
    )


def build_corpus() -> list[Fixture]:
    return [
        *(make_random_fixture(epoch) for epoch in range(RANDOM_EPOCHS)),
        *(
            make_adversarial_fixture(epoch)
            for epoch in range(ADVERSARIAL_EPOCHS)
        ),
    ]


def validate_corpus(corpus: Sequence[Fixture]) -> dict[str, Any]:
    if len(corpus) != SYNTHETIC_EPOCHS:
        raise AssertionError(
            f"expected {SYNTHETIC_EPOCHS} fixtures, got {len(corpus)}"
        )
    family_counts = {
        family: sum(fixture.family == family for fixture in corpus)
        for family in ("random", "adversarial")
    }
    if family_counts != {"random": RANDOM_EPOCHS, "adversarial": ADVERSARIAL_EPOCHS}:
        raise AssertionError(f"bad corpus family counts: {family_counts}")

    category_counts = {
        category: sum(fixture.category == category for fixture in corpus)
        for category in ADVERSARIAL_CATEGORIES
    }
    expected_per_category = ADVERSARIAL_EPOCHS // len(ADVERSARIAL_CATEGORIES)
    if any(count != expected_per_category for count in category_counts.values()):
        raise AssertionError(f"bad adversarial category counts: {category_counts}")

    hashes: list[str] = []
    for fixture in corpus:
        if len(fixture.logits_bf16_bits) != ROWS * EXPERTS:
            raise AssertionError(f"{fixture.name} logits shape is invalid")
        if len(fixture.bias_fp32_bits) != EXPERTS:
            raise AssertionError(f"{fixture.name} bias shape is invalid")
        if any(not 0 <= value <= 0xFFFF for value in fixture.logits_bf16_bits):
            raise AssertionError(f"{fixture.name} contains invalid BF16 bits")
        if any(value & 0x7F80 == 0x7F80 for value in fixture.logits_bf16_bits):
            raise AssertionError(f"{fixture.name} contains non-finite BF16")
        if any(not 0 <= value <= 0xFFFFFFFF for value in fixture.bias_fp32_bits):
            raise AssertionError(f"{fixture.name} contains invalid FP32 bias bits")
        hashes.append(raw_fixture_hash(fixture))
    if len(set(hashes)) != len(hashes):
        raise AssertionError("corpus contains duplicate raw logits+bias fixtures")

    adversarial = {category: [] for category in ADVERSARIAL_CATEGORIES}
    for fixture in corpus[RANDOM_EPOCHS:]:
        adversarial[fixture.category].append(fixture)
    signed_zero_bits = set(adversarial["signed_zero"][0].logits_bf16_bits)
    if not {0x0000, 0x8000}.issubset(signed_zero_bits):
        raise AssertionError("signed-zero fixtures do not contain both zero signs")
    if not any(
        abs(bf16_value(bits)) >= 16.0
        for fixture in adversarial["saturation"]
        for bits in fixture.logits_bf16_bits
    ):
        raise AssertionError("saturation fixtures do not reach |logit| >= 16")
    if not any(
        value + 1 in set(fixture.logits_bf16_bits)
        for fixture in adversarial["adjacent_cutoff"]
        for value in fixture.logits_bf16_bits
    ):
        raise AssertionError("adjacent-cutoff fixtures lack adjacent BF16 values")
    if not any(
        value != f32_bits(0.0)
        for fixture in adversarial["bias_cutoff"]
        for value in fixture.bias_fp32_bits
    ):
        raise AssertionError("bias-cutoff fixtures lack nonzero FP32 bias")
    first_tie = adversarial["ties"][0].logits_bf16_bits[:EXPERTS]
    if max(first_tie.count(value) for value in set(first_tie)) < TOPK + 1:
        raise AssertionError("tie fixtures do not straddle the top-k cutoff")
    for fixture in adversarial["ties"]:
        if fixture.expected_tie_ids is None or len(fixture.expected_tie_ids) != ROWS:
            raise AssertionError(f"{fixture.name} lacks lower-ID tie expectations")
        for row_index, expected in enumerate(fixture.expected_tie_ids):
            if len(expected) != TOPK or tuple(sorted(expected)) != expected:
                raise AssertionError(
                    f"{fixture.name} row {row_index} tie expectation is invalid"
                )
            row = fixture.logits_bf16_bits[
                row_index * EXPERTS : (row_index + 1) * EXPERTS
            ]
            tied_value = row[expected[0]]
            all_tied = tuple(
                expert for expert, value in enumerate(row) if value == tied_value
            )
            if expected != all_tied[:TOPK] or len(all_tied) <= TOPK:
                raise AssertionError(
                    f"{fixture.name} row {row_index} does not encode "
                    "the expected lower-ID cutoff tie"
                )

    return {
        "passed": True,
        "rows": ROWS,
        "experts": EXPERTS,
        "topk": TOPK,
        "total_epochs": len(corpus),
        "family_counts": family_counts,
        "adversarial_category_counts": category_counts,
        "unique_raw_fixture_hashes": len(set(hashes)),
        "aggregate_raw_sha256": hashlib.sha256(
            "".join(hashes).encode("ascii")
        ).hexdigest(),
        "coverage": {
            "seeded_random": True,
            "ties_across_cutoff": True,
            "lower_id_tie_winners_explicit": True,
            "adjacent_bf16_cutoff_values": True,
            "load_lane_boundaries": list(LANE_BOUNDARIES),
            "signed_zero": True,
            "sigmoid_saturation": True,
            "permutations": True,
            "fp32_bias_cutoff": True,
            "repeated_four_value_load_groups": True,
        },
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_file_range(path: Path, offset: int, length: int) -> tuple[str, bool]:
    digest = hashlib.sha256()
    all_zero = True
    remaining = length
    with path.open("rb") as handle:
        handle.seek(offset)
        while remaining:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                raise EOFError(
                    f"short read from {path} at {offset}, wanted {length} bytes"
                )
            digest.update(chunk)
            all_zero = all_zero and not any(chunk)
            remaining -= len(chunk)
    return digest.hexdigest(), all_zero


def production_source_manifest(
    model_root: Path,
    trace_dirs: Sequence[Path],
) -> dict[str, Any]:
    """Validate and hash retained traces plus exact checkpoint router tensors.

    This is intentionally stdlib-only so corpus validation does not import
    Torch or initialize an XPU runtime.
    """
    if len(trace_dirs) != PRODUCTION_TRACE_SETS:
        raise AssertionError(
            f"expected {PRODUCTION_TRACE_SETS} trace dirs, got {len(trace_dirs)}"
        )
    resolved_trace_dirs = tuple(path.resolve() for path in trace_dirs)
    if len(set(resolved_trace_dirs)) != PRODUCTION_TRACE_SETS:
        raise AssertionError("production trace directories must be distinct")

    trace_rows: list[dict[str, Any]] = []
    for trace_set, trace_dir in enumerate(resolved_trace_dirs):
        if not trace_dir.is_dir():
            raise FileNotFoundError(f"missing production trace dir: {trace_dir}")
        for layer in range(1, PRODUCTION_LAYERS + 1):
            path = trace_dir / f"layer{layer:02d}-mlp-input-q8-rank0.pt"
            if not path.is_file():
                raise FileNotFoundError(f"missing production trace: {path}")
            trace_rows.append(
                {
                    "trace_set": trace_set,
                    "layer": layer,
                    "path": str(path),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    if len(trace_rows) != PRODUCTION_EPOCHS:
        raise AssertionError(
            f"expected {PRODUCTION_EPOCHS} trace files, got {len(trace_rows)}"
        )

    model_root = model_root.resolve()
    index_path = model_root / "model.safetensors.index.json"
    if not index_path.is_file():
        raise FileNotFoundError(f"missing checkpoint index: {index_path}")
    index_payload = json.loads(index_path.read_text())
    weight_map = index_payload.get("weight_map")
    if not isinstance(weight_map, dict):
        raise AssertionError("checkpoint index lacks weight_map")

    header_cache: dict[Path, tuple[int, dict[str, Any]]] = {}

    def tensor_row(name: str, dtype: str, shape: list[int]) -> dict[str, Any]:
        shard_name = weight_map.get(name)
        if not isinstance(shard_name, str):
            raise AssertionError(f"checkpoint index lacks tensor {name}")
        shard_path = (model_root / shard_name).resolve()
        if not shard_path.is_file():
            raise FileNotFoundError(f"missing checkpoint shard: {shard_path}")
        if shard_path not in header_cache:
            with shard_path.open("rb") as handle:
                header_length_raw = handle.read(8)
                if len(header_length_raw) != 8:
                    raise AssertionError(f"invalid safetensors file: {shard_path}")
                header_length = struct.unpack("<Q", header_length_raw)[0]
                if header_length <= 0 or header_length > 256 * 1024 * 1024:
                    raise AssertionError(
                        f"invalid safetensors header length in {shard_path}"
                    )
                header = json.loads(handle.read(header_length))
            header_cache[shard_path] = (8 + header_length, header)
        data_start, header = header_cache[shard_path]
        metadata = header.get(name)
        if not isinstance(metadata, dict):
            raise AssertionError(f"{name} missing from its declared shard")
        if metadata.get("dtype") != dtype or metadata.get("shape") != shape:
            raise AssertionError(
                f"{name} contract drift: dtype={metadata.get('dtype')} "
                f"shape={metadata.get('shape')}"
            )
        offsets = metadata.get("data_offsets")
        if (
            not isinstance(offsets, list)
            or len(offsets) != 2
            or not all(isinstance(value, int) for value in offsets)
        ):
            raise AssertionError(f"{name} has invalid data_offsets")
        start, end = offsets
        expected_bytes = math.prod(shape) * (2 if dtype == "BF16" else 4)
        if start < 0 or end - start != expected_bytes:
            raise AssertionError(
                f"{name} byte span drift: {end - start} != {expected_bytes}"
            )
        tensor_sha256, all_zero = hash_file_range(
            shard_path, data_start + start, expected_bytes
        )
        return {
            "name": name,
            "shard": shard_name,
            "dtype": dtype,
            "shape": shape,
            "size_bytes": expected_bytes,
            "raw_sha256": tensor_sha256,
            "all_raw_bytes_zero": all_zero,
        }

    checkpoint_rows: list[dict[str, Any]] = []
    for layer in range(1, PRODUCTION_LAYERS + 1):
        gate = tensor_row(
            f"model.layers.{layer}.mlp.gate.weight",
            "BF16",
            [EXPERTS, 3072],
        )
        bias = tensor_row(
            f"model.layers.{layer}.mlp.experts.e_score_correction_bias",
            "F32",
            [EXPERTS],
        )
        if not bias["all_raw_bytes_zero"]:
            raise AssertionError(
                f"layer {layer} correction bias is not checkpoint-exact zero"
            )
        checkpoint_rows.append({"layer": layer, "gate": gate, "bias": bias})

    aggregate = hashlib.sha256()
    for row in trace_rows:
        aggregate.update(
            f"trace:{row['trace_set']}:{row['layer']}:{row['size_bytes']}:"
            f"{row['sha256']}\n".encode()
        )
    for row in checkpoint_rows:
        aggregate.update(
            f"checkpoint:{row['layer']}:{row['gate']['raw_sha256']}:"
            f"{row['bias']['raw_sha256']}\n".encode()
        )
    return {
        "passed": True,
        "model_root": str(model_root),
        "checkpoint_index": {
            "path": str(index_path),
            "size_bytes": index_path.stat().st_size,
            "sha256": sha256_file(index_path),
        },
        "trace_directories": [str(path) for path in resolved_trace_dirs],
        "trace_sets": PRODUCTION_TRACE_SETS,
        "layers_per_set": PRODUCTION_LAYERS,
        "trace_file_count": len(trace_rows),
        "trace_files": trace_rows,
        "checkpoint_tensor_count": len(checkpoint_rows) * 2,
        "checkpoint_layers": checkpoint_rows,
        "aggregate_source_sha256": aggregate.hexdigest(),
    }


def git_value(root: Path, *arguments: str) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def source_identity(paths: Iterable[Path]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in paths:
        resolved = path.resolve()
        result[str(resolved)] = {
            "exists": resolved.is_file(),
            "sha256": sha256_file(resolved) if resolved.is_file() else None,
        }
    return result


def repository_identity(root: Path) -> dict[str, Any]:
    resolved = root.resolve()
    status = git_value(resolved, "status", "--porcelain", "--untracked-files=no")
    return {
        "path": str(resolved),
        "head": git_value(resolved, "rev-parse", "HEAD"),
        "tree": git_value(resolved, "rev-parse", "HEAD^{tree}"),
        "tracked_worktree_dirty": bool(status) if status is not None else None,
        "tracked_status": status,
    }


def static_identity(args: argparse.Namespace) -> dict[str, Any]:
    sources = tuple(args.source_file) if args.source_file else DEFAULT_SOURCE_FILES
    binary = args.kernel_binary.resolve() if args.kernel_binary else None
    return {
        "script": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "sources": source_identity(sources),
        "kernel_repository": repository_identity(args.kernel_root),
        "vllm_repository": repository_identity(args.vllm_root),
        "kernel_binary": (
            {
                "path": str(binary),
                "exists": binary.is_file(),
                "sha256": sha256_file(binary) if binary.is_file() else None,
            }
            if binary
            else {"path": None, "exists": None, "sha256": None}
        ),
        "labels": dict(args.identity),
    }


def make_xpu_tensor(
    torch: Any,
    bits: Sequence[int],
    dtype: Any,
    shape: tuple[int, ...],
) -> Any:
    item_format = "H" if dtype == torch.uint16 else "I"
    raw = bytearray().join(struct.pack(f"<{item_format}", value) for value in bits)
    cpu = torch.frombuffer(raw, dtype=dtype).clone()
    viewed = cpu.view(torch.bfloat16 if dtype == torch.uint16 else torch.float32)
    return viewed.reshape(shape).to(device="xpu:0")


def synthetic_fixture_to_xpu(torch: Any, fixture: Fixture) -> RuntimeFixture:
    logits = make_xpu_tensor(
        torch, fixture.logits_bf16_bits, torch.uint16, (ROWS, EXPERTS)
    )
    bias = make_xpu_tensor(torch, fixture.bias_fp32_bits, torch.uint32, (EXPERTS,))
    return RuntimeFixture(
        name=fixture.name,
        family=fixture.family,
        category=fixture.category,
        seed=fixture.seed,
        logits=logits,
        bias=bias,
        fixture_sha256=raw_fixture_hash(fixture),
        expected_tie_ids=fixture.expected_tie_ids,
        evidence={},
    )


def allocate_outputs(torch: Any) -> tuple[Any, Any, Any]:
    return (
        torch.empty((ROWS, TOPK), dtype=torch.float32, device="xpu:0"),
        torch.empty((ROWS, TOPK), dtype=torch.int32, device="xpu:0"),
        torch.empty((ROWS, TOPK), dtype=torch.int32, device="xpu:0"),
    )


def reference_call(torch: Any, logits: Any, bias: Any, outputs: tuple[Any, Any, Any]) -> None:
    weights, ids, source_rows = outputs
    torch.ops._moe_C.topk_sigmoid(
        weights,
        ids,
        source_rows,
        logits.float(),
        True,
        bias,
        1.0,
    )


def candidate_call(torch: Any, logits: Any, bias: Any, outputs: tuple[Any, Any, Any]) -> None:
    weights, ids, source_rows = outputs
    torch.ops._moe_C.laguna_m8_bf16_topk_sigmoid(
        weights,
        ids,
        source_rows,
        logits,
        bias,
    )


def raw_tensor_hashes(torch: Any, tensors: Sequence[Any]) -> list[str]:
    hashes: list[str] = []
    for tensor in tensors:
        raw = tensor.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()
        hashes.append(hashlib.sha256(raw).hexdigest())
    return hashes


def prepare_production_fixtures(
    torch: Any,
    manifest: dict[str, Any],
) -> tuple[list[RuntimeFixture], dict[str, Any]]:
    from safetensors import safe_open

    checkpoint_rows = manifest["checkpoint_layers"]
    trace_rows = manifest["trace_files"]
    if len(checkpoint_rows) != PRODUCTION_LAYERS:
        raise AssertionError("production manifest has wrong checkpoint layer count")
    if len(trace_rows) != PRODUCTION_EPOCHS:
        raise AssertionError("production manifest has wrong trace count")

    model_root = Path(manifest["model_root"])
    requested_by_shard: dict[str, list[tuple[int, str, str]]] = {}
    for row in checkpoint_rows:
        layer = int(row["layer"])
        for kind in ("gate", "bias"):
            tensor = row[kind]
            requested_by_shard.setdefault(tensor["shard"], []).append(
                (layer, kind, tensor["name"])
            )

    checkpoint_cpu: dict[tuple[int, str], Any] = {}
    for shard_name, requested in requested_by_shard.items():
        with safe_open(
            model_root / shard_name,
            framework="pt",
            device="cpu",
        ) as handle:
            for layer, kind, name in requested:
                # Detach from the shard mmap before the safe_open context
                # closes; later validation and XPU transfer must not depend on
                # a backend-specific mapping lifetime.
                checkpoint_cpu[(layer, kind)] = handle.get_tensor(name).clone()

    checkpoint_xpu: dict[tuple[int, str], Any] = {}
    checkpoint_hashes: dict[int, dict[str, str]] = {}
    manifest_by_layer = {int(row["layer"]): row for row in checkpoint_rows}
    for layer in range(1, PRODUCTION_LAYERS + 1):
        gate = checkpoint_cpu[(layer, "gate")]
        bias = checkpoint_cpu[(layer, "bias")]
        if (
            gate.dtype != torch.bfloat16
            or tuple(gate.shape) != (EXPERTS, 3072)
            or not gate.is_contiguous()
        ):
            raise AssertionError(
                f"layer {layer} checkpoint gate contract drift: "
                f"{gate.dtype} {tuple(gate.shape)} {gate.stride()}"
            )
        if (
            bias.dtype != torch.float32
            or tuple(bias.shape) != (EXPERTS,)
            or not bias.is_contiguous()
        ):
            raise AssertionError(
                f"layer {layer} checkpoint bias contract drift: "
                f"{bias.dtype} {tuple(bias.shape)} {bias.stride()}"
            )
        gate_hash, bias_hash = raw_tensor_hashes(torch, (gate, bias))
        expected = manifest_by_layer[layer]
        if gate_hash != expected["gate"]["raw_sha256"]:
            raise AssertionError(f"layer {layer} gate hash changed during load")
        if bias_hash != expected["bias"]["raw_sha256"]:
            raise AssertionError(f"layer {layer} bias hash changed during load")
        if not bool((bias == 0).all().item()):
            raise AssertionError(f"layer {layer} checkpoint bias is not zero")
        checkpoint_xpu[(layer, "gate")] = gate.to(device="xpu:0")
        checkpoint_xpu[(layer, "bias")] = bias.to(device="xpu:0")
        checkpoint_hashes[layer] = {"gate": gate_hash, "bias": bias_hash}

    fixtures: list[RuntimeFixture] = []
    aggregate = hashlib.sha256()
    hidden_hashes: set[str] = set()
    logit_hashes: set[str] = set()
    for trace_row in trace_rows:
        trace_set = int(trace_row["trace_set"])
        layer = int(trace_row["layer"])
        trace_path = Path(trace_row["path"])
        payload = torch.load(trace_path, map_location="cpu", weights_only=True)
        if not isinstance(payload, dict):
            raise AssertionError(f"{trace_path} is not a trace dictionary")
        if (
            payload.get("layer_idx") != layer
            or payload.get("stage") != "mlp-input"
            or payload.get("tp_rank") != 0
        ):
            raise AssertionError(f"{trace_path} trace identity drift")
        hidden = payload.get("hidden_states")
        positions = payload.get("positions")
        if (
            not isinstance(hidden, torch.Tensor)
            or hidden.dtype != torch.bfloat16
            or tuple(hidden.shape) != (ROWS, 3072)
            or not hidden.is_contiguous()
        ):
            raise AssertionError(f"{trace_path} hidden_states contract drift")
        if (
            not isinstance(positions, torch.Tensor)
            or positions.dtype != torch.int64
            or tuple(positions.shape) != (ROWS,)
        ):
            raise AssertionError(f"{trace_path} positions contract drift")

        hidden_hash, positions_hash = raw_tensor_hashes(torch, (hidden, positions))
        hidden_hashes.add(hidden_hash)
        hidden_xpu = hidden.to(device="xpu:0")
        gate_xpu = checkpoint_xpu[(layer, "gate")]
        expanded_gate = gate_xpu.t().unsqueeze(0).expand(ROWS, -1, -1)
        if expanded_gate.stride(0) != 0:
            raise AssertionError("incumbent gate projection lost stride-zero batch")
        logits = torch.bmm(hidden_xpu.unsqueeze(1), expanded_gate).squeeze(1)
        if (
            logits.dtype != torch.bfloat16
            or tuple(logits.shape) != (ROWS, EXPERTS)
            or not logits.is_contiguous()
        ):
            raise AssertionError(
                f"trace set {trace_set} layer {layer} projection contract drift"
            )
        torch.xpu.synchronize()
        bias_xpu = checkpoint_xpu[(layer, "bias")]
        logit_hash, xpu_bias_hash = raw_tensor_hashes(torch, (logits, bias_xpu))
        if xpu_bias_hash != checkpoint_hashes[layer]["bias"]:
            raise AssertionError(f"layer {layer} XPU bias bytes changed")
        logit_hashes.add(logit_hash)
        fixture_hash = hashlib.sha256(
            f"{logit_hash}:{xpu_bias_hash}".encode("ascii")
        ).hexdigest()
        evidence = {
            "trace_set": trace_set,
            "layer": layer,
            "trace_path": str(trace_path),
            "trace_file_sha256": trace_row["sha256"],
            "hidden_sha256": hidden_hash,
            "positions_sha256": positions_hash,
            "gate_weight_sha256": checkpoint_hashes[layer]["gate"],
            "bias_sha256": xpu_bias_hash,
            "router_logits_sha256": logit_hash,
            "projection": (
                "torch.bmm(hidden.unsqueeze(1), "
                "gate.t().unsqueeze(0).expand(8,-1,-1)).squeeze(1)"
            ),
            "expanded_gate_stride": list(expanded_gate.stride()),
        }
        fixtures.append(
            RuntimeFixture(
                name=f"production-set{trace_set}-layer{layer:02d}",
                family="production",
                category=f"retained_trace_set_{trace_set}",
                seed=None,
                logits=logits,
                bias=bias_xpu,
                fixture_sha256=fixture_hash,
                expected_tie_ids=None,
                evidence=evidence,
            )
        )
        aggregate.update(
            f"{trace_set}:{layer}:{trace_row['sha256']}:{hidden_hash}:"
            f"{positions_hash}:{checkpoint_hashes[layer]['gate']}:"
            f"{xpu_bias_hash}:{logit_hash}\n".encode()
        )

    if len(fixtures) != PRODUCTION_EPOCHS:
        raise AssertionError(
            f"expected {PRODUCTION_EPOCHS} production fixtures, got {len(fixtures)}"
        )
    if len(hidden_hashes) != PRODUCTION_EPOCHS:
        raise AssertionError("production hidden-state traces are not all changing")
    if len(logit_hashes) != PRODUCTION_EPOCHS:
        raise AssertionError("production router logits are not all changing")
    report = {
        "passed": True,
        "fixture_count": len(fixtures),
        "trace_sets": PRODUCTION_TRACE_SETS,
        "layers_per_set": PRODUCTION_LAYERS,
        "unique_hidden_sha256": len(hidden_hashes),
        "unique_router_logits_sha256": len(logit_hashes),
        "aggregate_fixture_sha256": aggregate.hexdigest(),
        "fixtures": [fixture.evidence for fixture in fixtures],
    }
    return fixtures, report


def validate_outputs(
    torch: Any,
    label: str,
    outputs: tuple[Any, Any, Any],
    expected_tie_ids: tuple[tuple[int, ...], ...] | None,
) -> None:
    weights, ids, source_rows = outputs
    expected_dtypes = (torch.float32, torch.int32, torch.int32)
    for tensor, dtype in zip(outputs, expected_dtypes, strict=True):
        if tensor.dtype != dtype or tuple(tensor.shape) != (ROWS, TOPK):
            raise AssertionError(
                f"{label} output contract drift: {tensor.dtype} {tuple(tensor.shape)}"
            )
    if not bool(torch.isfinite(weights).all().item()):
        raise AssertionError(f"{label} emitted non-finite weights")
    if not bool(((ids >= 0) & (ids < EXPERTS)).all().item()):
        raise AssertionError(f"{label} emitted an out-of-range expert id")
    sorted_ids = ids.sort(dim=1).values
    if not bool((sorted_ids[:, 1:] != sorted_ids[:, :-1]).all().item()):
        raise AssertionError(f"{label} selected a duplicate expert within a row")
    expected_sources = (
        torch.arange(TOPK, dtype=torch.int32, device="xpu:0").unsqueeze(1) * ROWS
        + torch.arange(ROWS, dtype=torch.int32, device="xpu:0").unsqueeze(0)
    ).t()
    if not torch.equal(source_rows, expected_sources):
        raise AssertionError(f"{label} emitted incorrect source-row indices")
    if expected_tie_ids is not None:
        expected_ids = torch.tensor(
            expected_tie_ids,
            dtype=torch.int32,
            device="xpu:0",
        )
        if not torch.equal(ids, expected_ids):
            raise AssertionError(
                f"{label} violated designed lower-expert-ID tie winners"
            )


def output_equal(torch: Any, left: Sequence[Any], right: Sequence[Any]) -> list[bool]:
    return [torch.equal(a, b) for a, b in zip(left, right, strict=True)]


def correctness_pass(
    torch: Any,
    fixtures: Sequence[RuntimeFixture],
    *,
    phase: str,
    include_detail: bool,
    expected_epochs: int,
) -> dict[str, Any]:
    if len(fixtures) != expected_epochs:
        raise AssertionError(
            f"{phase} expected {expected_epochs} fixtures, got {len(fixtures)}"
        )
    rows: list[dict[str, Any]] = []
    aggregate = hashlib.sha256()
    input_hashes: set[str] = set()
    equal_checks = 0
    raw_checks = 0
    lower_id_tie_checks = 0
    for epoch, fixture in enumerate(fixtures):
        logits, bias = fixture.logits, fixture.bias
        before_hashes = raw_tensor_hashes(torch, (logits, bias))
        combined_input_hash = hashlib.sha256(
            ":".join(before_hashes).encode("ascii")
        ).hexdigest()
        input_hashes.add(combined_input_hash)
        reference = allocate_outputs(torch)
        candidate_first = allocate_outputs(torch)
        candidate_repeat = allocate_outputs(torch)
        reference_call(torch, logits, bias, reference)
        candidate_call(torch, logits, bias, candidate_first)
        candidate_call(torch, logits, bias, candidate_repeat)
        torch.xpu.synchronize()

        validate_outputs(
            torch,
            f"{phase} epoch {epoch} reference",
            reference,
            fixture.expected_tie_ids,
        )
        validate_outputs(
            torch,
            f"{phase} epoch {epoch} candidate",
            candidate_first,
            fixture.expected_tie_ids,
        )
        if fixture.expected_tie_ids is not None:
            lower_id_tie_checks += ROWS * 2
        ref_hashes = raw_tensor_hashes(torch, reference)
        candidate_hashes = raw_tensor_hashes(torch, candidate_first)
        repeat_hashes = raw_tensor_hashes(torch, candidate_repeat)
        ref_equal = output_equal(torch, reference, candidate_first)
        repeat_equal = output_equal(torch, candidate_first, candidate_repeat)
        after_hashes = raw_tensor_hashes(torch, (logits, bias))
        unchanged = before_hashes == after_hashes
        exact = (
            all(ref_equal)
            and all(repeat_equal)
            and ref_hashes == candidate_hashes == repeat_hashes
            and unchanged
        )
        if not exact:
            raise AssertionError(
                f"{phase} epoch {epoch} ({fixture.name}) exactness failed: "
                f"A==B {ref_equal}, B repeat {repeat_equal}, "
                f"raw A/B/B2 {ref_hashes == candidate_hashes == repeat_hashes}, "
                f"inputs unchanged {unchanged}"
            )
        equal_checks += len(ref_equal) + len(repeat_equal)
        raw_checks += len(ref_hashes) * 2 + len(before_hashes)
        for value in (*ref_hashes, *candidate_hashes, *repeat_hashes):
            aggregate.update(value.encode("ascii"))
        if include_detail:
            rows.append(
                {
                    "epoch": epoch,
                    "name": fixture.name,
                    "family": fixture.family,
                    "category": fixture.category,
                    "seed": fixture.seed,
                    "fixture_sha256": fixture.fixture_sha256,
                    "input_sha256": before_hashes,
                    "reference_output_sha256": ref_hashes,
                    "candidate_output_sha256": candidate_hashes,
                    "candidate_repeat_output_sha256": repeat_hashes,
                    "torch_equal_reference_candidate": ref_equal,
                    "torch_equal_candidate_repeat": repeat_equal,
                    "inputs_unchanged": unchanged,
                    "expected_lower_id_tie_winners": fixture.expected_tie_ids,
                    "evidence": fixture.evidence,
                }
            )
    if len(input_hashes) != len(fixtures):
        raise AssertionError(
            f"{phase} fixtures are not all changing: "
            f"{len(input_hashes)}/{len(fixtures)} unique inputs"
        )
    return {
        "passed": True,
        "phase": phase,
        "epochs": len(fixtures),
        "unique_input_sha256": len(input_hashes),
        "torch_equal_checks": equal_checks,
        "raw_byte_hash_checks": raw_checks,
        "explicit_lower_id_tie_checks": lower_id_tie_checks,
        "candidate_repeat_deterministic": True,
        "inputs_unchanged": True,
        "aggregate_output_sha256": aggregate.hexdigest(),
        "epochs_detail": rows,
    }


def timed_arm_ms(torch: Any, call_cycle: Callable[[], None]) -> float:
    torch.xpu.synchronize()
    started_ns = time.perf_counter_ns()
    for _ in range(CYCLES_PER_ARM):
        call_cycle()
    torch.xpu.synchronize()
    return (time.perf_counter_ns() - started_ns) / 1_000_000.0 / CYCLES_PER_ARM


def collect_timing(
    torch: Any,
    production_fixtures: Sequence[RuntimeFixture],
) -> dict[str, Any]:
    if len(production_fixtures) != PRODUCTION_CALLS:
        raise AssertionError(
            f"timing requires {PRODUCTION_CALLS} production fixtures"
        )
    layers = [fixture.evidence.get("layer") for fixture in production_fixtures]
    trace_sets = {
        fixture.evidence.get("trace_set") for fixture in production_fixtures
    }
    if layers != list(range(1, PRODUCTION_LAYERS + 1)) or len(trace_sets) != 1:
        raise AssertionError("timing fixtures are not one ordered 47-layer trace")
    inputs = [(fixture.logits, fixture.bias) for fixture in production_fixtures]
    before_input_hashes = [
        raw_tensor_hashes(torch, pair) for pair in inputs
    ]
    reference_outputs = allocate_outputs(torch)
    candidate_outputs = allocate_outputs(torch)

    def reference_cycle() -> None:
        for logits, bias in inputs:
            reference_call(torch, logits, bias, reference_outputs)

    def candidate_cycle() -> None:
        for logits, bias in inputs:
            candidate_call(torch, logits, bias, candidate_outputs)

    for _ in range(WARMUP_CYCLES_PER_ARM):
        reference_cycle()
        candidate_cycle()
    torch.xpu.synchronize()

    blocks: list[dict[str, Any]] = []
    for block in range(TIMING_BLOCKS):
        # Every block is preregistered A-B-B-A.  The block comparison averages
        # its two same-arm observations to remove first/last position bias.
        a1 = timed_arm_ms(torch, reference_cycle)
        b1 = timed_arm_ms(torch, candidate_cycle)
        b2 = timed_arm_ms(torch, candidate_cycle)
        a2 = timed_arm_ms(torch, reference_cycle)
        a_ms = statistics.fmean((a1, a2))
        b_ms = statistics.fmean((b1, b2))
        saved_ms = a_ms - b_ms
        gain_pct = 100.0 * saved_ms / a_ms
        blocks.append(
            {
                "block": block,
                "order": "ABBA",
                "a1_ms_per_47_call_cycle": a1,
                "b1_ms_per_47_call_cycle": b1,
                "b2_ms_per_47_call_cycle": b2,
                "a2_ms_per_47_call_cycle": a2,
                "a_mean_ms_per_cycle": a_ms,
                "b_mean_ms_per_cycle": b_ms,
                "saved_ms_per_cycle": saved_ms,
                "gain_pct": gain_pct,
                "candidate_faster": b_ms < a_ms,
            }
        )
    after_input_hashes = [
        raw_tensor_hashes(torch, pair) for pair in inputs
    ]
    if before_input_hashes != after_input_hashes:
        raise AssertionError("timing mutated a production logit or bias tensor")

    a_samples = [float(block["a_mean_ms_per_cycle"]) for block in blocks]
    b_samples = [float(block["b_mean_ms_per_cycle"]) for block in blocks]
    savings = [float(block["saved_ms_per_cycle"]) for block in blocks]
    gains = [float(block["gain_pct"]) for block in blocks]
    wins = sum(bool(block["candidate_faster"]) for block in blocks)
    median_saved_ms = statistics.median(savings)
    median_gain_pct = statistics.median(gains)
    passed = (
        wins >= MIN_CANDIDATE_WINS
        and median_saved_ms >= MIN_SAVED_MS_PER_CYCLE
        and median_gain_pct >= MIN_GAIN_PCT
    )
    return {
        "passed": passed,
        "contract": {
            "production_calls_per_cycle": PRODUCTION_CALLS,
            "warmup_cycles_per_arm": WARMUP_CYCLES_PER_ARM,
            "blocks": TIMING_BLOCKS,
            "order_per_block": "ABBA",
            "cycles_per_timed_arm": CYCLES_PER_ARM,
        },
        "thresholds": {
            "minimum_candidate_faster_blocks": MIN_CANDIDATE_WINS,
            "minimum_saved_ms_per_47_call_cycle": MIN_SAVED_MS_PER_CYCLE,
            "minimum_gain_pct": MIN_GAIN_PCT,
        },
        "summary": {
            "candidate_faster_blocks": wins,
            "reference_median_ms_per_47_call_cycle": statistics.median(a_samples),
            "candidate_median_ms_per_47_call_cycle": statistics.median(b_samples),
            "paired_median_saved_ms_per_47_call_cycle": median_saved_ms,
            "paired_median_gain_pct": median_gain_pct,
            "reference_mean_ms_per_47_call_cycle": statistics.fmean(a_samples),
            "candidate_mean_ms_per_47_call_cycle": statistics.fmean(b_samples),
        },
        "inputs_unchanged": True,
        "production_fixture_sha256": [
            fixture.fixture_sha256 for fixture in production_fixtures
        ],
        "blocks_detail": blocks,
    }


def load_torch_and_op(args: argparse.Namespace) -> tuple[Any, Path | None]:
    import torch

    binary_path: Path | None = None
    if args.kernel_binary is not None:
        binary_path = args.kernel_binary.resolve()
        if not binary_path.is_file():
            raise FileNotFoundError(f"kernel binary does not exist: {binary_path}")
        torch.ops.load_library(str(binary_path))
    else:
        module = importlib.import_module(args.kernel_module)
        module_path = getattr(module, "__file__", None)
        binary_path = Path(module_path).resolve() if module_path else None
    if not hasattr(torch.ops._moe_C, "topk_sigmoid"):
        raise RuntimeError("incumbent _moe_C::topk_sigmoid is unavailable")
    if not hasattr(torch.ops._moe_C, "laguna_m8_bf16_topk_sigmoid"):
        raise RuntimeError("candidate _moe_C::laguna_m8_bf16_topk_sigmoid is unavailable")
    return torch, binary_path


def run_gpu_gate(
    args: argparse.Namespace,
    synthetic_corpus: Sequence[Fixture],
    synthetic_report: dict[str, Any],
    production_sources: dict[str, Any],
    identity: dict[str, Any],
) -> dict[str, Any]:
    torch, binary_path = load_torch_and_op(args)
    if not hasattr(torch, "xpu") or not torch.xpu.is_available():
        raise RuntimeError("XPU is not available")
    visible_xpus = torch.xpu.device_count()
    if visible_xpus != 1:
        raise RuntimeError(
            "gate requires exactly one visible XPU per process; "
            f"got {visible_xpus}"
        )
    torch.xpu.set_device(0)
    if binary_path is not None:
        identity["kernel_binary"] = {
            "path": str(binary_path),
            "exists": binary_path.is_file(),
            "sha256": sha256_file(binary_path) if binary_path.is_file() else None,
        }

    production_fixtures, production_report = prepare_production_fixtures(
        torch, production_sources
    )
    synthetic_fixtures = [
        synthetic_fixture_to_xpu(torch, fixture) for fixture in synthetic_corpus
    ]
    pre_timing_fixtures = [*production_fixtures, *synthetic_fixtures]
    if len(pre_timing_fixtures) != PRE_TIMING_EPOCHS:
        raise AssertionError("pre-timing fixture count is not 333")
    pre_timing = correctness_pass(
        torch,
        pre_timing_fixtures,
        phase="pre_timing",
        include_detail=True,
        expected_epochs=PRE_TIMING_EPOCHS,
    )
    timing_production = production_fixtures[:PRODUCTION_LAYERS]
    timing = collect_timing(torch, timing_production)
    post_timing_fixtures = [
        *synthetic_fixtures[RANDOM_EPOCHS:],
        *timing_production,
    ]
    post_timing = correctness_pass(
        torch,
        post_timing_fixtures,
        phase="post_timing",
        include_detail=False,
        expected_epochs=POST_TIMING_EPOCHS,
    )
    passed = (
        bool(synthetic_report["passed"])
        and bool(production_sources["passed"])
        and bool(production_report["passed"])
        and bool(pre_timing["passed"])
        and bool(timing["passed"])
        and bool(post_timing["passed"])
    )
    if not passed:
        failed = [
            name
            for name, result in (
                ("synthetic_corpus", synthetic_report),
                ("production_sources", production_sources),
                ("production_fixtures", production_report),
                ("pre_timing", pre_timing),
                ("timing", timing),
                ("post_timing", post_timing),
            )
            if not bool(result["passed"])
        ]
    else:
        failed = []
    return {
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "rank": args.rank,
        "contract": {
            "reference": (
                "BF16 logits.float() + _moe_C.topk_sigmoid("
                "renormalize=True,bias=FP32,routed_scaling_factor=1.0)"
            ),
            "candidate": "_moe_C.laguna_m8_bf16_topk_sigmoid(BF16 logits, FP32 bias)",
            "shape": [ROWS, EXPERTS],
            "topk": TOPK,
            "weight_dtype": "torch.float32",
            "id_dtype": "torch.int32",
            "source_row_dtype": "torch.int32",
        },
        "environment": {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python": sys.version,
            "torch": torch.__version__,
            "visible_xpus": visible_xpus,
            "device": torch.xpu.get_device_name(0),
            "ONEAPI_DEVICE_SELECTOR": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
            "ZE_AFFINITY_MASK": os.environ.get("ZE_AFFINITY_MASK"),
            "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": os.environ.get(
                "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK"
            ),
        },
        "identity": identity,
        "synthetic_corpus": synthetic_report,
        "production_sources": production_sources,
        "production_fixtures": production_report,
        "pre_timing_exactness": pre_timing,
        "timing": timing,
        "post_timing_replay": post_timing,
        "failed_gates": failed,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def parse_identity(values: Sequence[str]) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError(
                f"--identity must be NAME=VALUE, got {value!r}"
            )
        name, identity_value = value.split("=", 1)
        if not name:
            raise argparse.ArgumentTypeError("--identity name cannot be empty")
        parsed.append((name, identity_value))
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rank", type=int, required=True, choices=range(4))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--validate-corpus-only",
        action="store_true",
        help="validate corpus/static identity and exit without importing Torch",
    )
    parser.add_argument(
        "--kernel-module",
        default="vllm_xpu_kernels._moe_C",
        help="extension module to import when --kernel-binary is omitted",
    )
    parser.add_argument("--kernel-binary", type=Path)
    parser.add_argument("--kernel-root", type=Path, default=DEFAULT_KERNEL_ROOT)
    parser.add_argument("--vllm-root", type=Path, default=DEFAULT_VLLM_ROOT)
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    parser.add_argument(
        "--trace-dir",
        action="append",
        type=Path,
        help=(
            "retained rank0 M=8 mlp-input trace directory; repeat exactly "
            "three times (defaults to the preregistered trace sets)"
        ),
    )
    parser.add_argument(
        "--source-file",
        action="append",
        type=Path,
        help="source file to hash; repeatable (defaults to candidate-relevant files)",
    )
    parser.add_argument(
        "--identity",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="additional frozen run identity label; repeatable",
    )
    args = parser.parse_args()
    args.identity = parse_identity(args.identity)
    args.trace_dir = tuple(args.trace_dir) if args.trace_dir else DEFAULT_TRACE_DIRS
    return args


def main() -> int:
    args = parse_args()
    try:
        corpus = build_corpus()
        corpus_report = validate_corpus(corpus)
        production_sources = production_source_manifest(
            args.model_root,
            args.trace_dir,
        )
        identity = static_identity(args)
        if args.validate_corpus_only:
            payload = {
                "status": "PASS",
                "passed": True,
                "mode": "validate_corpus_only",
                "rank": args.rank,
                "torch_imported": "torch" in sys.modules,
                "identity": identity,
                "synthetic_corpus": corpus_report,
                "production_sources": production_sources,
            }
        else:
            payload = run_gpu_gate(
                args,
                corpus,
                corpus_report,
                production_sources,
                identity,
            )
    except Exception as exc:
        payload = {
            "status": "FAIL",
            "passed": False,
            "rank": args.rank,
            "mode": (
                "validate_corpus_only"
                if args.validate_corpus_only
                else "xpu_component_gate"
            ),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    write_json(args.output, payload)
    print(json.dumps({"status": payload["status"], "output": str(args.output)}))
    return 0 if bool(payload["passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
