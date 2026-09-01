#!/usr/bin/env python3
"""Measure a W13-only Qwen3.8 Flash-Next MoE config under XPU graph replay.

This is a component gate, not a serving benchmark.  It exercises one logical
EP4 rank at the production M1 shape with real checkpoint weights.  Candidate
configuration is restricted to a nested ``W1_CONFIG`` delta; the W2 launch is
verified against the retained common-warps-8 control before device work.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
import time
from typing import Any


GLOBAL_EXPERTS = 512
LOCAL_EXPERTS = 128
HIDDEN_SIZE = 2560
LOCAL_INTERMEDIATE_SIZE = 640
TOP_K = 10
BLOCK_SHAPE = [128, 128]
EXACT_REPLAYS = 100
MODEL_REVISION = "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"

PROTECTED_BASE_CONFIG: dict[str, int] = {
    "BLOCK_SIZE_M": 16,
    "BLOCK_SIZE_N": 64,
    "BLOCK_SIZE_K": 128,
    "GROUP_SIZE_M": 1,
    "SPLIT_K": 1,
    "num_warps": 8,
    "num_stages": 4,
}

W1_ALLOWED_VALUES: dict[str, set[int]] = {
    "BLOCK_SIZE_N": {32, 64, 128, 256},
    "BLOCK_SIZE_K": {64, 128},
    "GROUP_SIZE_M": {1, 16, 32, 64},
    "num_warps": {4, 8},
    "num_stages": {2, 3, 4, 5},
}

EXPECTED_TEXT_CONFIG = {
    "model_type": "qwen4_exp_text",
    "num_hidden_layers": 48,
    "hidden_size": HIDDEN_SIZE,
    "moe_intermediate_size": LOCAL_INTERMEDIATE_SIZE,
    "num_experts": GLOBAL_EXPERTS,
    "num_experts_per_tok": TOP_K,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tensor_sha256(tensor: Any) -> str:
    # Keep torch out of the module import path so static tests need no XPU stack.
    torch = __import__("torch")
    return hashlib.sha256(
        tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    ).hexdigest()


def hash_series_sha256(values: list[str]) -> str:
    payload = json.dumps(values, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()


def parse_candidate_config(
    encoded: str,
) -> tuple[dict[str, Any], dict[str, int], dict[str, int], dict[str, Any]]:
    """Return effective, W13, W2, and requested config receipts."""
    try:
        requested = json.loads(encoded)
    except json.JSONDecodeError as exc:
        raise ValueError("candidate config must be valid JSON") from exc
    if not isinstance(requested, dict):
        raise ValueError("candidate config must decode to an object")
    unknown_top = set(requested) - {"W1_CONFIG"}
    if unknown_top:
        raise ValueError(
            "candidate config may contain only nested W1_CONFIG; rejected: "
            f"{sorted(unknown_top)}"
        )
    delta = requested.get("W1_CONFIG", {})
    if not isinstance(delta, dict):
        raise ValueError("W1_CONFIG must be an object")
    unknown_w1 = set(delta) - set(W1_ALLOWED_VALUES)
    if unknown_w1:
        raise ValueError(f"W1_CONFIG contains unsupported fields: {sorted(unknown_w1)}")
    for key, value in delta.items():
        if type(value) is not int or value not in W1_ALLOWED_VALUES[key]:
            allowed = sorted(W1_ALLOWED_VALUES[key])
            raise ValueError(f"W1_CONFIG.{key} must be one of {allowed}")

    w1_config = PROTECTED_BASE_CONFIG | delta
    w2_config = PROTECTED_BASE_CONFIG.copy()
    effective: dict[str, Any] = PROTECTED_BASE_CONFIG.copy()
    if delta:
        effective["W1_CONFIG"] = delta.copy()
    return effective, w1_config, w2_config, requested


def expert_weight_names(layer: int, expert: int) -> dict[str, str]:
    prefix = f"model.language_model.layers.{layer}.mlp.experts.{expert}"
    return {
        "gate_weight": f"{prefix}.gate_proj.weight",
        "gate_scale": f"{prefix}.gate_proj.weight_scale_inv",
        "up_weight": f"{prefix}.up_proj.weight",
        "up_scale": f"{prefix}.up_proj.weight_scale_inv",
        "down_weight": f"{prefix}.down_proj.weight",
        "down_scale": f"{prefix}.down_proj.weight_scale_inv",
    }


def validate_model_config(config: dict[str, Any]) -> dict[str, Any]:
    text_config = config.get("text_config")
    if not isinstance(text_config, dict):
        raise ValueError("model config has no text_config object")
    actual_text = {key: text_config.get(key) for key in EXPECTED_TEXT_CONFIG}
    if actual_text != EXPECTED_TEXT_CONFIG:
        raise ValueError(
            f"model text shape is not the protected Flash-Next shape: {actual_text}"
        )
    quantization = config.get("quantization_config")
    if not isinstance(quantization, dict):
        raise ValueError("model config has no quantization_config object")
    actual_quantization = {
        "quant_method": quantization.get("quant_method"),
        "activation_scheme": quantization.get("activation_scheme"),
        "weight_block_size": quantization.get("weight_block_size"),
    }
    expected_quantization = {
        "quant_method": "fp8",
        "activation_scheme": "dynamic",
        "weight_block_size": BLOCK_SHAPE,
    }
    if actual_quantization != expected_quantization:
        raise ValueError(
            "model quantization is not the protected block-FP8 shape: "
            f"{actual_quantization}"
        )
    return {
        "text_config": actual_text,
        "quantization_config": actual_quantization,
    }


def read_result_json(path: Path) -> dict[str, Any]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not lines:
        raise ValueError(f"control authority is empty: {path}")
    try:
        value = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"control authority has no final JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("control authority must decode to an object")
    return value


def validate_checkpoint_receipt(
    receipt_path: Path,
    expected_receipt_sha256: str,
    *,
    model: Path,
    model_revision: str,
    index_sha256: str,
    config_sha256: str,
    shard_paths: dict[str, Path],
) -> dict[str, dict[str, Any]]:
    """Validate a runner-created one-time checkpoint checksum receipt.

    The optional receipt avoids hashing the same multi-GiB checkpoint shards in
    every fresh C/A/C process. The runner still hashes every distinct shard
    once, freezes the receipt digest, and each gate process verifies that digest
    plus the selected files' path and size before trusting the recorded hashes.
    Callers that omit the receipt retain the original per-process hashing path.
    """
    if not re.fullmatch(r"[0-9a-f]{64}", expected_receipt_sha256):
        raise ValueError("checkpoint receipt SHA-256 must be 64 lowercase hex digits")
    receipt = receipt_path.resolve()
    if not receipt.is_file():
        raise FileNotFoundError(f"checkpoint receipt is missing: {receipt}")
    if sha256_file(receipt) != expected_receipt_sha256:
        raise ValueError("checkpoint receipt SHA-256 mismatch")
    value = json.loads(receipt.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("checkpoint receipt must decode to an object")
    if (
        value.get("schema_version") != 1
        or value.get("status") != "pass"
        or value.get("classification") != "qwen38_w13_checkpoint_checksum_receipt"
    ):
        raise ValueError("checkpoint receipt header is invalid")
    if value.get("model_path") != str(model):
        raise ValueError("checkpoint receipt model path mismatch")
    if value.get("model_revision") != model_revision:
        raise ValueError("checkpoint receipt model revision mismatch")
    if value.get("model_index_sha256") != index_sha256:
        raise ValueError("checkpoint receipt model index mismatch")
    if value.get("model_config_sha256") != config_sha256:
        raise ValueError("checkpoint receipt model config mismatch")
    receipt_shards = value.get("checkpoint_shards")
    if not isinstance(receipt_shards, dict):
        raise ValueError("checkpoint receipt shard map is missing")

    selected: dict[str, dict[str, Any]] = {}
    for name, path in sorted(shard_paths.items()):
        row = receipt_shards.get(name)
        if not isinstance(row, dict):
            raise ValueError(f"checkpoint receipt is missing shard {name}")
        resolved = path.resolve()
        if row.get("path") != str(resolved):
            raise ValueError(f"checkpoint receipt path mismatch for {name}")
        if row.get("size") != resolved.stat().st_size:
            raise ValueError(f"checkpoint receipt size mismatch for {name}")
        file_stat = resolved.stat()
        expected_stat = {
            "device": file_stat.st_dev,
            "inode": file_stat.st_ino,
            "mtime_ns": file_stat.st_mtime_ns,
            "ctime_ns": file_stat.st_ctime_ns,
        }
        if row.get("stat_identity") != expected_stat:
            raise ValueError(f"checkpoint receipt stat identity mismatch for {name}")
        digest = row.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"checkpoint receipt digest is invalid for {name}")
        selected[name] = {
            "path": str(resolved),
            "size": row["size"],
            "sha256": digest,
            "stat_identity": expected_stat,
        }
    return selected


def validate_control_authority(
    authority: dict[str, Any], expected_identity: dict[str, Any]
) -> list[str]:
    if authority.get("status") != "pass":
        raise ValueError("control authority did not pass")
    if (
        authority.get("classification")
        != "qwen38_flash_next_w13_m1_xpu_graph_component"
    ):
        raise ValueError("control authority classification is wrong")
    identity = authority.get("identity")
    if not isinstance(identity, dict):
        raise ValueError("control authority identity is missing")
    for key, expected in expected_identity.items():
        if identity.get(key) != expected:
            raise ValueError(
                f"control authority identity mismatch for {key}: "
                f"{identity.get(key)!r} != {expected!r}"
            )
    receipt = authority.get("config_receipt")
    if not isinstance(receipt, dict):
        raise ValueError("control authority config receipt is missing")
    if receipt.get("requested") != {}:
        raise ValueError("control authority is not the protected control config")
    if receipt.get("resolved_w1") != PROTECTED_BASE_CONFIG:
        raise ValueError("control authority W13 config drifted")
    if receipt.get("resolved_w2") != PROTECTED_BASE_CONFIG:
        raise ValueError("control authority W2 config drifted")
    if receipt.get("w2_unchanged") is not True:
        raise ValueError("control authority did not attest unchanged W2")
    correctness = authority.get("correctness")
    if not isinstance(correctness, dict):
        raise ValueError("control authority correctness receipt is missing")
    eager = correctness.get("config_local_eager_output_sha256")
    graph = correctness.get("graph_output_sha256")
    if not isinstance(eager, list) or not isinstance(graph, list):
        raise ValueError("control authority hash series is missing")
    if len(eager) != EXACT_REPLAYS or len(graph) != EXACT_REPLAYS:
        raise ValueError("control authority hash series length is wrong")
    if eager != graph or len(set(eager)) != EXACT_REPLAYS:
        raise ValueError("control authority is stale or differs under graph replay")
    return graph


def resolve_weight_plan(
    index: dict[str, Any], layer: int, ep_rank: int
) -> tuple[list[dict[str, str]], list[str]]:
    if not 0 <= layer < 48:
        raise ValueError("layer must be between 0 and 47")
    if not 0 <= ep_rank < 4:
        raise ValueError("ep-rank must be between 0 and 3")
    weight_map = index.get("weight_map")
    if not isinstance(weight_map, dict):
        raise ValueError("model index has no weight_map object")
    first_expert = ep_rank * LOCAL_EXPERTS
    plan: list[dict[str, str]] = []
    shards: set[str] = set()
    for global_expert in range(first_expert, first_expert + LOCAL_EXPERTS):
        names = expert_weight_names(layer, global_expert)
        row = {"global_expert": str(global_expert)}
        for role, name in names.items():
            shard = weight_map.get(name)
            if not isinstance(shard, str) or not shard:
                raise ValueError(f"model index is missing {name}")
            row[role] = name
            row[f"{role}_shard"] = shard
            shards.add(shard)
        plan.append(row)
    return plan, sorted(shards)


def route_ids_for_replay(replay: int) -> list[int]:
    if not 0 <= replay < EXACT_REPLAYS:
        raise ValueError(f"replay must be between 0 and {EXACT_REPLAYS - 1}")
    offset = 17 + 37 * replay
    return [int((131 * slot + offset) % GLOBAL_EXPERTS) for slot in range(TOP_K)]


def local_route_count(ids: list[int], ep_rank: int) -> int:
    first = ep_rank * LOCAL_EXPERTS
    return sum(first <= expert < first + LOCAL_EXPERTS for expert in ids)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = min(len(ordered) - 1, max(0, int(fraction * (len(ordered) - 1))))
    return ordered[position]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--layer", type=int, choices=range(48), required=True)
    parser.add_argument("--ep-rank", type=int, choices=range(4), required=True)
    parser.add_argument(
        "--candidate-config-json",
        default="{}",
        help="JSON object containing only an optional nested W1_CONFIG object",
    )
    parser.add_argument(
        "--control-authority-json",
        type=Path,
        help=(
            "Passed protected-control result for the same identity; required for "
            "every non-empty W1_CONFIG and optional for a control repeat"
        ),
    )
    parser.add_argument(
        "--checkpoint-receipt-json",
        type=Path,
        help=(
            "Runner-created receipt that hashed every required checkpoint shard "
            "once; requires --checkpoint-receipt-sha256"
        ),
    )
    parser.add_argument(
        "--checkpoint-receipt-sha256",
        help="SHA-256 of --checkpoint-receipt-json",
    )
    parser.add_argument("--seed", type=int, default=20260827)
    parser.add_argument("--hidden-scale", type=float, default=0.01)
    parser.add_argument("--capture-warmups", type=int, default=5)
    parser.add_argument("--timing-warmups", type=int, default=10)
    parser.add_argument("--timing-batches", type=int, default=15)
    parser.add_argument("--iterations-per-batch", type=int, default=200)
    args = parser.parse_args()
    if not args.model_revision.strip():
        parser.error("--model-revision must be non-empty")
    if args.model_revision != MODEL_REVISION:
        parser.error(f"--model-revision must equal {MODEL_REVISION}")
    if (args.checkpoint_receipt_json is None) != (
        args.checkpoint_receipt_sha256 is None
    ):
        parser.error(
            "--checkpoint-receipt-json and --checkpoint-receipt-sha256 must be used together"
        )
    if not 0.0 < args.hidden_scale <= 10.0:
        parser.error("--hidden-scale must be in (0, 10]")
    if not 1 <= args.capture_warmups <= 20:
        parser.error("--capture-warmups must be between 1 and 20")
    if not 1 <= args.timing_warmups <= 100:
        parser.error("--timing-warmups must be between 1 and 100")
    if not 3 <= args.timing_batches <= 25:
        parser.error("--timing-batches must be between 3 and 25")
    if not 10 <= args.iterations_per_batch <= 500:
        parser.error("--iterations-per-batch must be between 10 and 500")
    return args


def run(args: argparse.Namespace) -> dict[str, Any]:
    effective_config, expected_w1, expected_w2, requested = parse_candidate_config(
        args.candidate_config_json
    )
    is_candidate = bool(requested.get("W1_CONFIG"))
    if is_candidate and args.control_authority_json is None:
        raise ValueError(
            "a non-empty W1_CONFIG requires --control-authority-json before device work"
        )

    import torch
    import triton
    import vllm
    from safetensors import safe_open

    from vllm.model_executor.layers.fused_moe import override_config
    from vllm.model_executor.layers.fused_moe.activation import MoEActivation
    from vllm.model_executor.layers.fused_moe.all2all_utils import (
        maybe_make_prepare_finalize,
    )
    from vllm.model_executor.layers.fused_moe.config import (
        FusedMoEConfig,
        FusedMoEParallelConfig,
        FusedMoEQuantConfig,
        RoutingMethodType,
    )
    from vllm.model_executor.layers.fused_moe.experts.triton_moe import TritonExperts
    from vllm.model_executor.layers.fused_moe.fused_moe import (
        resolve_moe_gemm_configs,
    )
    from vllm.model_executor.layers.fused_moe.modular_kernel import FusedMoEKernel
    from vllm.v1.worker.workspace import init_workspace_manager

    source_objects = {
        "fused_moe": resolve_moe_gemm_configs,
        "triton_experts": TritonExperts,
        "modular_kernel": FusedMoEKernel,
    }
    source_files: dict[str, dict[str, Any]] = {}
    for label, source_object in source_objects.items():
        module_path = Path(sys.modules[source_object.__module__].__file__).resolve()
        source_files[label] = {
            "path": str(module_path),
            "sha256": sha256_file(module_path),
        }
    runtime_source_receipt = {
        "gate_sha256": sha256_file(Path(__file__).resolve()),
        "torch_version": str(torch.__version__),
        "triton_version": str(triton.__version__),
        "vllm_version": str(vllm.__version__),
        "source_files": source_files,
    }

    source_w1, source_w2 = resolve_moe_gemm_configs(
        effective_config, M=1, enable_phase_configs=True
    )
    if source_w1 != expected_w1:
        raise RuntimeError(
            f"source W13 resolver disagrees with gate: {source_w1} != {expected_w1}"
        )
    if source_w2 != expected_w2 or source_w2 != PROTECTED_BASE_CONFIG:
        raise RuntimeError(f"W2 configuration changed: {source_w2}")

    model = args.model_path.resolve()
    index_path = model / "model.safetensors.index.json"
    config_path = model / "config.json"
    if not index_path.is_file() or not config_path.is_file():
        raise FileNotFoundError("model index or config is missing")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    model_config = json.loads(config_path.read_text(encoding="utf-8"))
    model_shape_receipt = validate_model_config(model_config)
    plan, shard_names = resolve_weight_plan(index, args.layer, args.ep_rank)
    shard_paths = {name: model / name for name in shard_names}
    missing_shards = [str(path) for path in shard_paths.values() if not path.is_file()]
    if missing_shards:
        raise FileNotFoundError(f"checkpoint shards are missing: {missing_shards}")

    index_sha256 = sha256_file(index_path)
    config_sha256 = sha256_file(config_path)
    if args.checkpoint_receipt_json is None:
        shard_receipts = {
            name: {
                "path": str(path),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for name, path in sorted(shard_paths.items())
        }
        checkpoint_receipt_path = None
        checkpoint_receipt_sha256 = None
    else:
        checkpoint_receipt_path = args.checkpoint_receipt_json.resolve()
        checkpoint_receipt_sha256 = args.checkpoint_receipt_sha256
        shard_receipts = validate_checkpoint_receipt(
            checkpoint_receipt_path,
            checkpoint_receipt_sha256,
            model=model,
            model_revision=args.model_revision,
            index_sha256=index_sha256,
            config_sha256=config_sha256,
            shard_paths=shard_paths,
        )
    first_expert = args.ep_rank * LOCAL_EXPERTS
    shape_receipt = {
        "tokens": 1,
        "global_experts": GLOBAL_EXPERTS,
        "local_experts": LOCAL_EXPERTS,
        "hidden": HIDDEN_SIZE,
        "local_intermediate": LOCAL_INTERMEDIATE_SIZE,
        "top_k": TOP_K,
        "block_shape": BLOCK_SHAPE,
        "input_dtype": "bfloat16",
        "weight_dtype": "float8_e4m3fn",
    }
    authority_identity = {
        "model_path": str(model),
        "model_revision": args.model_revision,
        "model_index_sha256": index_sha256,
        "model_config_sha256": config_sha256,
        "layer": args.layer,
        "ep_rank": args.ep_rank,
        "global_expert_range": [first_expert, first_expert + LOCAL_EXPERTS - 1],
        "checkpoint_shards": shard_receipts,
        "shape": shape_receipt,
        "model_shape_receipt": model_shape_receipt,
        "runtime_source_receipt": runtime_source_receipt,
        "seed": args.seed,
        "hidden_scale": args.hidden_scale,
    }
    control_authority_hashes: list[str] | None = None
    if args.control_authority_json is not None:
        authority_path = args.control_authority_json.resolve()
        control_authority_hashes = validate_control_authority(
            read_result_json(authority_path), authority_identity
        )
    else:
        authority_path = None

    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("the component gate requires exactly one visible XPU")
    device = torch.device("xpu:0")
    torch.xpu.set_device(device)
    dtype = torch.bfloat16
    weight_dtype = torch.float8_e4m3fn

    w1 = torch.empty(
        (LOCAL_EXPERTS, 2 * LOCAL_INTERMEDIATE_SIZE, HIDDEN_SIZE),
        dtype=weight_dtype,
        device=device,
    )
    w2 = torch.empty(
        (LOCAL_EXPERTS, HIDDEN_SIZE, LOCAL_INTERMEDIATE_SIZE),
        dtype=weight_dtype,
        device=device,
    )
    w1_scale = torch.empty(
        (
            LOCAL_EXPERTS,
            2 * LOCAL_INTERMEDIATE_SIZE // BLOCK_SHAPE[0],
            HIDDEN_SIZE // BLOCK_SHAPE[1],
        ),
        dtype=torch.float32,
        device=device,
    )
    w2_scale = torch.empty(
        (
            LOCAL_EXPERTS,
            HIDDEN_SIZE // BLOCK_SHAPE[0],
            LOCAL_INTERMEDIATE_SIZE // BLOCK_SHAPE[1],
        ),
        dtype=torch.float32,
        device=device,
    )

    load_started = time.monotonic()
    with ExitStack() as stack:
        handles = {
            name: stack.enter_context(safe_open(path, framework="pt", device="cpu"))
            for name, path in shard_paths.items()
        }
        for local_expert, row in enumerate(plan):
            gate_weight = handles[row["gate_weight_shard"]].get_tensor(
                row["gate_weight"]
            )
            up_weight = handles[row["up_weight_shard"]].get_tensor(row["up_weight"])
            down_weight = handles[row["down_weight_shard"]].get_tensor(
                row["down_weight"]
            )
            gate_scale = handles[row["gate_scale_shard"]].get_tensor(row["gate_scale"])
            up_scale = handles[row["up_scale_shard"]].get_tensor(row["up_scale"])
            down_scale = handles[row["down_scale_shard"]].get_tensor(row["down_scale"])
            w1[local_expert, :LOCAL_INTERMEDIATE_SIZE].copy_(gate_weight)
            w1[local_expert, LOCAL_INTERMEDIATE_SIZE:].copy_(up_weight)
            w2[local_expert].copy_(down_weight)
            w1_scale[local_expert, : LOCAL_INTERMEDIATE_SIZE // 128].copy_(gate_scale)
            w1_scale[local_expert, LOCAL_INTERMEDIATE_SIZE // 128 :].copy_(up_scale)
            w2_scale[local_expert].copy_(down_scale)
    torch.xpu.synchronize()
    load_seconds = time.monotonic() - load_started

    cpu_generator = torch.Generator(device="cpu").manual_seed(args.seed)
    hidden_series = (
        torch.randn(
            (EXACT_REPLAYS, 1, HIDDEN_SIZE),
            dtype=torch.float32,
            generator=cpu_generator,
        )
        .mul_(args.hidden_scale)
        .to(dtype)
    )
    weight_series = torch.rand(
        (EXACT_REPLAYS, 1, TOP_K),
        dtype=torch.float32,
        generator=cpu_generator,
    ).add_(0.01)
    weight_series.div_(weight_series.sum(dim=-1, keepdim=True))
    id_series = torch.tensor(
        [route_ids_for_replay(replay) for replay in range(EXACT_REPLAYS)],
        dtype=torch.int32,
    ).reshape(EXACT_REPLAYS, 1, TOP_K)
    weight_series, descending_order = torch.sort(weight_series, dim=-1, descending=True)
    id_series = torch.gather(id_series, -1, descending_order.to(torch.int64))
    local_counts = [
        local_route_count(route_ids_for_replay(replay), args.ep_rank)
        for replay in range(EXACT_REPLAYS)
    ]

    hidden_states = torch.empty((1, HIDDEN_SIZE), dtype=dtype, device=device)
    topk_weights = torch.empty((1, TOP_K), dtype=torch.float32, device=device)
    topk_ids = torch.empty((1, TOP_K), dtype=torch.int32, device=device)
    expert_map = torch.full((GLOBAL_EXPERTS,), -1, dtype=torch.int32, device=device)
    expert_map[first_expert : first_expert + LOCAL_EXPERTS] = torch.arange(
        LOCAL_EXPERTS, dtype=torch.int32, device=device
    )

    quant_config = FusedMoEQuantConfig.make(
        quant_dtype=weight_dtype,
        block_shape=BLOCK_SHAPE,
        w1_scale=w1_scale,
        w2_scale=w2_scale,
    )
    moe_config = FusedMoEConfig(
        num_experts=GLOBAL_EXPERTS,
        num_local_experts=LOCAL_EXPERTS,
        num_logical_experts=GLOBAL_EXPERTS,
        experts_per_token=TOP_K,
        hidden_dim=HIDDEN_SIZE,
        intermediate_size=LOCAL_INTERMEDIATE_SIZE,
        activation=MoEActivation.SILU,
        device=device,
        routing_method=RoutingMethodType.TopK,
        moe_parallel_config=FusedMoEParallelConfig.make_no_parallel(),
        in_dtype=dtype,
        moe_backend="triton",
        max_num_tokens=1,
    )
    prepare_finalize = maybe_make_prepare_finalize(
        moe=moe_config,
        quant_config=quant_config,
        allow_new_interface=True,
        use_monolithic=False,
    )
    if prepare_finalize is None:
        raise RuntimeError("modular prepare/finalize was not constructed")
    init_workspace_manager(device)
    kernel = FusedMoEKernel(
        prepare_finalize,
        TritonExperts(moe_config, quant_config),
    )

    def install_input(index_value: int) -> None:
        hidden_states.copy_(hidden_series[index_value])
        topk_weights.copy_(weight_series[index_value])
        topk_ids.copy_(id_series[index_value])

    def invoke() -> Any:
        return kernel.apply(
            hidden_states,
            w1,
            w2,
            topk_weights,
            topk_ids,
            activation=MoEActivation.SILU,
            global_num_experts=GLOBAL_EXPERTS,
            expert_map=expert_map,
            apply_router_weight_on_input=False,
        )

    eager_hashes: list[str] = []
    graph_hashes: list[str] = []
    compile_seconds = 0.0
    capture_seconds = 0.0
    event_us_per_replay: list[float] = []
    wall_us_per_replay: list[float] = []
    with override_config(effective_config):
        install_input(0)
        compile_started = time.monotonic()
        output = invoke()
        torch.xpu.synchronize()
        compile_seconds = time.monotonic() - compile_started

        for replay in range(EXACT_REPLAYS):
            install_input(replay)
            output = invoke()
            torch.xpu.synchronize()
            if not bool(torch.isfinite(output).all().item()):
                raise RuntimeError(f"non-finite eager output at replay {replay}")
            eager_hashes.append(tensor_sha256(output))

        for replay in range(args.capture_warmups):
            install_input(replay % EXACT_REPLAYS)
            output = invoke()
        torch.xpu.synchronize()

        install_input(0)
        graph = torch.xpu.XPUGraph()
        capture_started = time.monotonic()
        with torch.xpu.graph(graph):
            graph_output = invoke()
        torch.xpu.synchronize()
        capture_seconds = time.monotonic() - capture_started

        for replay in range(EXACT_REPLAYS):
            install_input(replay)
            graph.replay()
            torch.xpu.synchronize()
            if not bool(torch.isfinite(graph_output).all().item()):
                raise RuntimeError(f"non-finite graph output at replay {replay}")
            graph_hashes.append(tensor_sha256(graph_output))

        if graph_hashes != eager_hashes:
            first_difference = next(
                index
                for index, pair in enumerate(zip(eager_hashes, graph_hashes))
                if pair[0] != pair[1]
            )
            raise AssertionError(
                f"graph output differs from eager authority at replay {first_difference}"
            )
        if len(set(eager_hashes)) != EXACT_REPLAYS:
            raise AssertionError(
                "changing eager inputs did not produce 100 unique outputs"
            )
        if control_authority_hashes is not None:
            if eager_hashes != control_authority_hashes:
                first_difference = next(
                    index
                    for index, pair in enumerate(
                        zip(control_authority_hashes, eager_hashes)
                    )
                    if pair[0] != pair[1]
                )
                raise AssertionError(
                    "config-local eager output differs from protected control at "
                    f"replay {first_difference}"
                )

        install_input(0)
        for _ in range(args.timing_warmups):
            graph.replay()
        torch.xpu.synchronize()
        for _ in range(args.timing_batches):
            start_event = torch.xpu.Event(enable_timing=True)
            end_event = torch.xpu.Event(enable_timing=True)
            wall_started = time.perf_counter_ns()
            start_event.record()
            for _ in range(args.iterations_per_batch):
                graph.replay()
            end_event.record()
            end_event.synchronize()
            wall_elapsed = time.perf_counter_ns() - wall_started
            event_us_per_replay.append(
                start_event.elapsed_time(end_event) * 1000.0 / args.iterations_per_batch
            )
            wall_us_per_replay.append(wall_elapsed / 1000.0 / args.iterations_per_batch)
    all_timing_values = event_us_per_replay + wall_us_per_replay
    if not all(math.isfinite(value) and value > 0.0 for value in all_timing_values):
        raise RuntimeError("timing contains a non-finite or non-positive value")
    result = {
        "schema_version": 1,
        "status": "pass",
        "classification": "qwen38_flash_next_w13_m1_xpu_graph_component",
        "identity": authority_identity,
        "config_receipt": {
            "requested": requested,
            "effective": effective_config,
            "resolved_w1": source_w1,
            "resolved_w2": source_w2,
            "protected_w2": PROTECTED_BASE_CONFIG,
            "w2_unchanged": source_w2 == PROTECTED_BASE_CONFIG,
        },
        "weights": {
            "load_seconds": load_seconds,
            "selected_weight_count": len(plan) * 6,
            "selected_shard_count": len(shard_names),
            "checkpoint_checksum_mode": (
                "per_process" if checkpoint_receipt_path is None else "frozen_receipt"
            ),
            "checkpoint_receipt_path": (
                str(checkpoint_receipt_path)
                if checkpoint_receipt_path is not None
                else None
            ),
            "checkpoint_receipt_sha256": checkpoint_receipt_sha256,
        },
        "correctness": {
            "exact_replays": EXACT_REPLAYS,
            "input_schedule": (
                "changing hidden states and descending router weights paired with "
                "17+37*i routes"
            ),
            "config_local_eager_output_sha256": eager_hashes,
            "graph_output_sha256": graph_hashes,
            "config_local_eager_graph_equal": eager_hashes == graph_hashes,
            "control_authority_path": (
                str(authority_path) if authority_path is not None else None
            ),
            "control_authority_series_sha256": (
                hash_series_sha256(control_authority_hashes)
                if control_authority_hashes is not None
                else None
            ),
            "matches_control_authority": (
                eager_hashes == control_authority_hashes
                if control_authority_hashes is not None
                else not is_candidate
            ),
            "unique_eager_hashes": len(set(eager_hashes)),
            "unique_graph_hashes": len(set(graph_hashes)),
            "local_route_count_min": min(local_counts),
            "local_route_count_max": max(local_counts),
            "local_route_count_series": local_counts,
        },
        "graph": {
            "capture": "one clean static XPUGraph; inputs copied before replay",
            "compile_seconds": compile_seconds,
            "capture_seconds": capture_seconds,
            "capture_warmups": args.capture_warmups,
            "timing_warmups": args.timing_warmups,
            "timing_batches": args.timing_batches,
            "iterations_per_batch": args.iterations_per_batch,
            "timing_input_index": 0,
            "timing_local_route_count": local_counts[0],
            "timing_scope": (
                "clean fixed-fixture graph replay; compare only matched same-rank "
                "control/candidate/control ratios"
            ),
            "event_us_per_replay": event_us_per_replay,
            "event_median_us": statistics.median(event_us_per_replay),
            "event_p10_us": percentile(event_us_per_replay, 0.1),
            "event_p90_us": percentile(event_us_per_replay, 0.9),
            "wall_us_per_replay": wall_us_per_replay,
            "wall_median_us": statistics.median(wall_us_per_replay),
        },
        "memory": {
            "allocated": torch.xpu.memory_allocated(),
            "reserved": torch.xpu.memory_reserved(),
            "max_allocated": torch.xpu.max_memory_allocated(),
            "max_reserved": torch.xpu.max_memory_reserved(),
        },
        "device": {
            "visible_xpu_count": torch.xpu.device_count(),
            "name": torch.xpu.get_device_name(0),
        },
    }
    return result


def main() -> None:
    result = run(parse_args())
    print(json.dumps(result, sort_keys=True, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
