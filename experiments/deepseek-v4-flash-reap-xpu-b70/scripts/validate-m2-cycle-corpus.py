#!/usr/bin/env python3
"""Validate and summarize a content-addressed DeepSeek V4 M=2 cycle corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import torch


RANKS = 4
ALLREDUCES = 87
MHC_BOUNDARIES = 85


def raw_bytes(tensor: torch.Tensor) -> bytes:
    return tensor.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()


def blob_identity(tensor: torch.Tensor) -> tuple[str, str]:
    cpu = tensor.detach().cpu().contiguous()
    raw = raw_bytes(cpu)
    raw_sha = hashlib.sha256(raw).hexdigest()
    identity = hashlib.sha256()
    identity.update(str(cpu.dtype).encode())
    identity.update(b"\0")
    identity.update(json.dumps(list(cpu.shape), separators=(",", ":")).encode())
    identity.update(b"\0")
    identity.update(raw)
    return identity.hexdigest(), raw_sha


def load_rows(root: Path, rank: int, category: str, expected: int) -> list[dict[str, Any]]:
    paths = sorted((root / f"rank{rank}" / category).glob("*.json"))
    if len(paths) != expected:
        raise ValueError(
            f"rank {rank} {category}: expected {expected} records, got {len(paths)}"
        )
    rows = [json.loads(path.read_text()) for path in paths]
    indices = [row["index"] for row in rows]
    if indices != list(range(expected)):
        raise ValueError(f"rank {rank} {category}: non-contiguous indices {indices}")
    return rows


def validate_ref(
    root: Path,
    ref: dict[str, Any],
    cache: dict[str, torch.Tensor],
) -> torch.Tensor:
    relative = ref["blob"]
    if relative not in cache:
        path = root / relative
        if not path.is_file():
            raise ValueError(f"missing blob {path}")
        cache[relative] = torch.load(path, map_location="cpu", weights_only=True)
    tensor = cache[relative]
    blob_sha, raw_sha = blob_identity(tensor)
    if blob_sha != ref["blob_sha256"] or Path(relative).stem != blob_sha:
        raise ValueError(f"content identity mismatch for {relative}")
    if raw_sha != ref["raw_sha256"]:
        raise ValueError(f"raw SHA mismatch for {relative}")
    if list(tensor.shape) != ref["shape"] or str(tensor.dtype) != ref["dtype"]:
        raise ValueError(f"shape/dtype mismatch for {relative}")
    if tensor.numel() != ref["numel"] or len(raw_bytes(tensor)) != ref["nbytes"]:
        raise ValueError(f"size mismatch for {relative}")
    return tensor


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.capture_dir.resolve()
    blob_cache: dict[str, torch.Tensor] = {}
    rank_rows: list[dict[str, Any]] = []
    allreduce_reduced_by_index: list[list[str]] = [[] for _ in range(ALLREDUCES)]

    for rank in range(RANKS):
        allreduce = load_rows(root, rank, "allreduce_m2", ALLREDUCES)
        mhc = load_rows(root, rank, "mhc_post_pre_m2", MHC_BOUNDARIES)
        for row in (*allreduce, *mhc):
            for ref in row["tensors"].values():
                validate_ref(root, ref, blob_cache)

        for index, row in enumerate(allreduce):
            if row["kind"] != "tp4_bf16_sum_2x4096" or row["world_size"] != 4:
                raise ValueError(f"rank {rank} allreduce {index}: invalid identity")
            for name in ("local_partial", "reduced"):
                ref = row["tensors"][name]
                if ref["shape"] != [2, 4096] or ref["dtype"] != "torch.bfloat16":
                    raise ValueError(f"rank {rank} allreduce {index}: invalid {name}")
            allreduce_reduced_by_index[index].append(
                row["tensors"]["reduced"]["raw_sha256"]
            )

        expected_boundaries = [(0, "ffn")]
        expected_boundaries.extend(
            (layer, boundary)
            for layer in range(1, 43)
            for boundary in ("attn", "ffn")
        )
        actual_boundaries = [
            (row["layer_index"], row["boundary"]) for row in mhc
        ]
        if actual_boundaries != expected_boundaries:
            raise ValueError(f"rank {rank}: unexpected MHC boundary order")

        reduced_hashes = {
            row["tensors"]["reduced"]["raw_sha256"] for row in allreduce
        }
        linked = 0
        for index, row in enumerate(mhc):
            if row["kind"] != "deepseek_v4_mhc_post_pre_m2":
                raise ValueError(f"rank {rank} MHC {index}: invalid identity")
            expected_shapes = {
                "x_reduced": ([2, 4096], "torch.bfloat16"),
                "residual": ([2, 4, 4096], "torch.bfloat16"),
                "post_mix": ([2, 4, 1], "torch.float32"),
                "comb_res_mix": ([2, 4, 4], "torch.float32"),
                "fn": ([24, 16384], "torch.float32"),
                "hc_scale": ([3], "torch.float32"),
                "hc_base": ([24], "torch.float32"),
                "residual_out": ([2, 4, 4096], "torch.bfloat16"),
                "next_post_mix": ([2, 4, 1], "torch.float32"),
                "next_comb_mix": ([2, 4, 4], "torch.float32"),
                "layer_input": ([2, 4096], "torch.bfloat16"),
            }
            for name, (shape, dtype) in expected_shapes.items():
                ref = row["tensors"][name]
                if ref["shape"] != shape or ref["dtype"] != dtype:
                    raise ValueError(f"rank {rank} MHC {index}: invalid {name}")
            linked += int(row["tensors"]["x_reduced"]["raw_sha256"] in reduced_hashes)
        if linked != MHC_BOUNDARIES:
            raise ValueError(
                f"rank {rank}: only {linked}/{MHC_BOUNDARIES} MHC inputs link to reductions"
            )

        alias_links = 0
        for previous, current in zip(mhc, mhc[1:], strict=False):
            previous_metadata = previous["tensor_metadata"]
            current_metadata = current["tensor_metadata"]
            alias_links += int(
                previous_metadata["residual_out"]["storage_data_ptr"]
                == current_metadata["residual"]["storage_data_ptr"]
            )
        rank_rows.append(
            {
                "rank": rank,
                "allreduces": len(allreduce),
                "mhc_boundaries": len(mhc),
                "mhc_inputs_linked_to_reductions": linked,
                "successive_residual_storage_aliases": alias_links,
            }
        )

    for index, hashes in enumerate(allreduce_reduced_by_index):
        if len(set(hashes)) != 1:
            raise ValueError(f"allreduce {index}: reduced result differs across ranks")

    manifests = sorted(root.glob("rank*/*/*.json"))
    aggregate = hashlib.sha256()
    for path in manifests:
        aggregate.update(str(path.relative_to(root)).encode())
        aggregate.update(b"\0")
        aggregate.update(path.read_bytes())
    result = {
        "classification": "deepseek_v4_mtp1_m2_real_cycle_corpus",
        "passed": True,
        "capture_dir": str(root),
        "ranks": rank_rows,
        "record_files": len(manifests),
        "unique_blobs": len(blob_cache),
        "logical_tensor_bytes": sum(
            len(raw_bytes(tensor)) for tensor in blob_cache.values()
        ),
        "manifest_aggregate_sha256": aggregate.hexdigest(),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
