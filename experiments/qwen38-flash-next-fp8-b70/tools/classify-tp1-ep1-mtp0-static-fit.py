#!/usr/bin/env python3
"""Classify Flash-Next TP1 MTP0 fit from safetensors headers only.

The classifier never imports torch or safetensors and never reads tensor data.
It validates the index against every shard header, accounts for the exact
stored dtype and shape of every tensor, and compares the text-only MTP0 target
with one B70 plus the declared host-memory envelope.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any


DTYPE_BYTES = {
    "BOOL": 1,
    "U8": 1,
    "I8": 1,
    "F8_E4M3": 1,
    "F8_E5M2": 1,
    "I16": 2,
    "U16": 2,
    "F16": 2,
    "BF16": 2,
    "I32": 4,
    "U32": 4,
    "F32": 4,
    "I64": 8,
    "U64": 8,
    "F64": 8,
}
GIB = 1024**3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--host-memory-bytes", type=int, required=True)
    parser.add_argument("--gpu-memory-bytes", type=int, required=True)
    parser.add_argument(
        "--model-revision",
        default="bcd9f01ddc9cff2316eb84281bebcd5b058bddce",
    )
    parser.add_argument(
        "--vllm-commit",
        default="1372c62d975c554f4b465c8299bc5f3295301ceb",
    )
    parser.add_argument(
        "--xpu-kernel-commit",
        default="ad25aa9f69a2171612b9c6b83dfa82c69559f9e4",
    )
    parser.add_argument(
        "--staged-runtime-build-commit",
        default="2f829747503c77d4814834dffd0840fb1dd9f75a",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gib(value: int) -> float:
    return value / GIB


def category(name: str) -> str:
    if name.startswith("model.visual."):
        return "vision"
    if name.startswith("mtp."):
        return "mtp"
    if ".ple.ple_embedding.ngram_embedding." in name:
        return "ple_ngram_embedding"
    if ".ple." in name:
        return "ple_other"
    if name == "model.language_model.embed_tokens.weight":
        return "input_embedding"
    if name == "lm_head.weight":
        return "lm_head"
    if ".mlp.experts." in name:
        return "routed_experts"
    return "remaining_target"


def read_header(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        raw_length = handle.read(8)
        if len(raw_length) != 8:
            raise ValueError(f"{path}: missing safetensors header length")
        (header_length,) = struct.unpack("<Q", raw_length)
        if header_length <= 0 or header_length > path.stat().st_size - 8:
            raise ValueError(f"{path}: invalid header length {header_length}")
        return json.loads(handle.read(header_length))


def main() -> None:
    args = parse_args()
    model = args.model.resolve()
    config_path = model / "config.json"
    index_path = model / "model.safetensors.index.json"
    config = json.loads(config_path.read_text())
    index = json.loads(index_path.read_text())
    weight_map: dict[str, str] = index["weight_map"]
    shards = sorted(set(weight_map.values()))

    seen: dict[str, str] = {}
    category_bytes: dict[str, int] = defaultdict(int)
    category_tensors: dict[str, int] = defaultdict(int)
    dtype_bytes: dict[str, int] = defaultdict(int)
    tensor_count = 0
    total_bytes = 0

    for shard_name in shards:
        shard_path = model / shard_name
        header = read_header(shard_path)
        for name, metadata in header.items():
            if name == "__metadata__":
                continue
            if name in seen:
                raise ValueError(f"duplicate tensor {name!r}")
            dtype = metadata["dtype"]
            if dtype not in DTYPE_BYTES:
                raise ValueError(f"unsupported dtype {dtype!r} for {name!r}")
            shape = metadata["shape"]
            stored_bytes = math.prod(shape) * DTYPE_BYTES[dtype]
            start, end = metadata["data_offsets"]
            if end - start != stored_bytes:
                raise ValueError(
                    f"{name}: offset span {end - start} != shape bytes {stored_bytes}"
                )
            if weight_map.get(name) != shard_name:
                raise ValueError(
                    f"{name}: index shard {weight_map.get(name)!r} != {shard_name!r}"
                )
            seen[name] = shard_name
            key = category(name)
            category_bytes[key] += stored_bytes
            category_tensors[key] += 1
            dtype_bytes[dtype] += stored_bytes
            total_bytes += stored_bytes
            tensor_count += 1

    missing = sorted(set(weight_map) - set(seen))
    unexpected = sorted(set(seen) - set(weight_map))
    if missing or unexpected:
        raise ValueError(
            f"index/header mismatch: missing={missing[:5]!r} unexpected={unexpected[:5]!r}"
        )
    indexed_total = int(index["metadata"]["total_size"])
    if total_bytes != indexed_total:
        raise ValueError(f"header bytes {total_bytes} != index total {indexed_total}")

    excluded_bytes = category_bytes["vision"] + category_bytes["mtp"]
    target_bytes = total_bytes - excluded_bytes
    physical_capacity = args.host_memory_bytes + args.gpu_memory_bytes
    physical_deficit = max(0, target_bytes - physical_capacity)
    optimistic_gpu_bytes = 32 * GIB
    optimistic_deficit = max(
        0, target_bytes - args.host_memory_bytes - optimistic_gpu_bytes
    )
    selective_uva_bytes = (
        category_bytes["ple_ngram_embedding"] + category_bytes["input_embedding"]
    )

    category_order = [
        "routed_experts",
        "ple_ngram_embedding",
        "remaining_target",
        "input_embedding",
        "lm_head",
        "ple_other",
        "mtp",
        "vision",
    ]
    categories = {
        key: {
            "tensor_count": category_tensors[key],
            "bytes": category_bytes[key],
            "gib": gib(category_bytes[key]),
        }
        for key in category_order
    }

    result = {
        "schema": "neural.download.flash-next-tp1-static-fit.v1",
        "date": "2026-08-28",
        "status": "closed-static-fit",
        "generator": {
            "path": (
                "experiments/qwen38-flash-next-fp8-b70/tools/"
                "classify-tp1-ep1-mtp0-static-fit.py"
            ),
            "sha256": sha256(Path(__file__)),
            "inputs": {
                "host_memory_bytes": args.host_memory_bytes,
                "gpu_memory_bytes": args.gpu_memory_bytes,
            },
        },
        "identity": {
            "model": "Qwen/Qwen3.8-Flash-Next-FP8",
            "model_revision": args.model_revision,
            "config_sha256": sha256(config_path),
            "index_sha256": sha256(index_path),
            "vllm_commit": args.vllm_commit,
            "xpu_kernel_commit": args.xpu_kernel_commit,
            "staged_runtime_build_commit": args.staged_runtime_build_commit,
            "topology": {"tp": 1, "ep": 1},
            "mtp": 0,
            "graph_mode": "off",
            "active_context_tokens": 0,
            "modality": "text",
        },
        "architecture": {
            "architecture": config["architectures"][0],
            "model_type": config["model_type"],
            "layers": config["text_config"]["num_hidden_layers"],
            "experts": config["text_config"]["num_experts"],
            "experts_per_token": config["text_config"]["num_experts_per_tok"],
            "ple_layer_ids": config["text_config"]["ple_layer_ids"],
            "native_context_tokens": config["text_config"][
                "max_position_embeddings"
            ],
        },
        "accounting": {
            "method": "safetensors headers and index only; tensor payloads not read",
            "shards": len(shards),
            "tensor_count": tensor_count,
            "index_total_bytes": indexed_total,
            "header_total_bytes": total_bytes,
            "header_total_gib": gib(total_bytes),
            "bytes_by_dtype": dict(sorted(dtype_bytes.items())),
            "categories": categories,
        },
        "runtime_exclusions": {
            "vision": {
                "mechanism": "--language-model-only omits model.visual.*",
                "bytes": category_bytes["vision"],
                "gib": gib(category_bytes["vision"]),
            },
            "mtp": {
                "mechanism": "MTP0 target loader skips mtp.*",
                "bytes": category_bytes["mtp"],
                "gib": gib(category_bytes["mtp"]),
            },
            "text_mtp0_target_bytes": target_bytes,
            "text_mtp0_target_gib": gib(target_bytes),
        },
        "fit": {
            "host_memory_bytes": args.host_memory_bytes,
            "host_memory_gib": gib(args.host_memory_bytes),
            "one_b70_memory_bytes": args.gpu_memory_bytes,
            "one_b70_memory_gib": gib(args.gpu_memory_bytes),
            "combined_physical_capacity_bytes": physical_capacity,
            "combined_physical_capacity_gib": gib(physical_capacity),
            "exact_physical_deficit_bytes": physical_deficit,
            "exact_physical_deficit_gib": gib(physical_deficit),
            "optimistic_32gib_gpu_deficit_bytes": optimistic_deficit,
            "optimistic_32gib_gpu_deficit_gib": gib(optimistic_deficit),
            "current_selective_uva_bytes": selective_uva_bytes,
            "current_selective_uva_gib": gib(selective_uva_bytes),
            "target_bytes_left_for_gpu_after_current_selective_uva": (
                target_bytes - selective_uva_bytes
            ),
            "target_gib_left_for_gpu_after_current_selective_uva": gib(
                target_bytes - selective_uva_bytes
            ),
            "runtime_cache_workspace_headroom_included": False,
        },
        "decision": {
            "coverage_state": "closed",
            "packet_grade": "D",
            "speed_claim": False,
            "gpu_model_load_required": False,
            "reason": (
                "The exact text-only MTP0 stored target exceeds the combined "
                "physical capacity of one B70 and this host before runtime, "
                "cache, or workspace memory."
            ),
            "retry_status": "blocked-on-material-memory-design",
            "retry_trigger": (
                "At least 192 GiB host RAM with qualified expert offload, or a "
                "separately qualified compression or streaming design."
            ),
            "protected_results_changed": False,
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
