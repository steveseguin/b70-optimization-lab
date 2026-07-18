#!/usr/bin/env python3
"""Validate a genuine sequential DeepSeek V4 M=4/M=8 verifier corpus."""

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
    if [row["index"] for row in rows] != list(range(expected)):
        raise ValueError(f"rank {rank} {category}: indices are not contiguous")
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
    parser.add_argument("--width", type=int, choices=(4, 8), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    width = args.width
    root = args.capture_dir.resolve()
    identity_text = (root / "capture-identity.txt").read_text()
    if "predictor_acceptance_evaluated=false" not in identity_text:
        raise ValueError("capture identity does not disable acceptance claims")

    blob_cache: dict[str, torch.Tensor] = {}
    rank_rows = []
    reduced_by_index: list[list[str]] = [[] for _ in range(ALLREDUCES)]
    verifier_ids = []
    verifier_positions = []
    verifier_top1 = []

    expected_boundaries = [(0, "ffn")]
    expected_boundaries.extend(
        (layer, boundary)
        for layer in range(1, 43)
        for boundary in ("attn", "ffn")
    )

    for rank in range(RANKS):
        allreduce = load_rows(root, rank, f"allreduce_m{width}", ALLREDUCES)
        mhc = load_rows(root, rank, f"mhc_post_pre_m{width}", MHC_BOUNDARIES)
        verifier = load_rows(root, rank, f"verifier_forward_m{width}", 1)[0]
        logits = load_rows(root, rank, f"verifier_logits_m{width}", 1)[0]
        for row in (*allreduce, *mhc, verifier, logits):
            for ref in row["tensors"].values():
                validate_ref(root, ref, blob_cache)

        for index, row in enumerate(allreduce):
            if row["kind"] != f"tp4_bf16_sum_{width}x4096" or row["world_size"] != 4:
                raise ValueError(f"rank {rank} allreduce {index}: invalid identity")
            for name in ("local_partial", "reduced"):
                ref = row["tensors"][name]
                if ref["shape"] != [width, 4096] or ref["dtype"] != "torch.bfloat16":
                    raise ValueError(f"rank {rank} allreduce {index}: invalid {name}")
            reduced_by_index[index].append(row["tensors"]["reduced"]["raw_sha256"])

        if [(row["layer_index"], row["boundary"]) for row in mhc] != expected_boundaries:
            raise ValueError(f"rank {rank}: unexpected MHC boundary order")
        reduced_hashes = {row["tensors"]["reduced"]["raw_sha256"] for row in allreduce}
        linked = 0
        non_tiled = 0
        for index, row in enumerate(mhc):
            if row["kind"] != f"deepseek_v4_mhc_post_pre_m{width}":
                raise ValueError(f"rank {rank} MHC {index}: invalid identity")
            expected_shapes = {
                "x_reduced": ([width, 4096], "torch.bfloat16"),
                "residual": ([width, 4, 4096], "torch.bfloat16"),
                "post_mix": ([width, 4, 1], "torch.float32"),
                "comb_res_mix": ([width, 4, 4], "torch.float32"),
                "fn": ([24, 16384], "torch.float32"),
                "hc_scale": ([3], "torch.float32"),
                "hc_base": ([24], "torch.float32"),
                "residual_out": ([width, 4, 4096], "torch.bfloat16"),
                "next_post_mix": ([width, 4, 1], "torch.float32"),
                "next_comb_mix": ([width, 4, 4], "torch.float32"),
                "layer_input": ([width, 4096], "torch.bfloat16"),
            }
            for name, (shape, dtype) in expected_shapes.items():
                ref = row["tensors"][name]
                if ref["shape"] != shape or ref["dtype"] != dtype:
                    raise ValueError(f"rank {rank} MHC {index}: invalid {name}")
            linked += int(row["tensors"]["x_reduced"]["raw_sha256"] in reduced_hashes)
            x_reduced = validate_ref(root, row["tensors"]["x_reduced"], blob_cache)
            tiled_pair = torch.cat([x_reduced[:2]] * (width // 2), dim=0)
            non_tiled += int(not torch.equal(x_reduced, tiled_pair))
        if linked != MHC_BOUNDARIES or non_tiled != MHC_BOUNDARIES:
            raise ValueError(
                f"rank {rank}: linked={linked}, non_tiled={non_tiled}, expected=85"
            )

        alias_links = sum(
            int(
                previous["tensor_metadata"]["residual_out"]["storage_data_ptr"]
                == current["tensor_metadata"]["residual"]["storage_data_ptr"]
            )
            for previous, current in zip(mhc, mhc[1:], strict=False)
        )

        ids = validate_ref(root, verifier["tensors"]["input_ids"], blob_cache)
        positions = validate_ref(root, verifier["tensors"]["positions"], blob_cache)
        top1 = validate_ref(root, logits["tensors"]["top1_token_ids"], blob_cache)
        if list(ids.shape) != [width] or list(positions.shape) != [width]:
            raise ValueError(f"rank {rank}: invalid verifier input shape")
        if not torch.equal(positions[1:], positions[:-1] + 1):
            raise ValueError(f"rank {rank}: verifier positions are not consecutive")
        if torch.equal(ids, torch.cat([ids[:2]] * (width // 2), dim=0)):
            raise ValueError(f"rank {rank}: verifier IDs are an M=2 row tile")
        verifier_ids.append(raw_bytes(ids))
        verifier_positions.append(raw_bytes(positions))
        verifier_top1.append(raw_bytes(top1))
        rank_rows.append(
            {
                "rank": rank,
                "allreduces": len(allreduce),
                "mhc_boundaries": len(mhc),
                "mhc_inputs_linked_to_reductions": linked,
                "non_tiled_mhc_boundaries": non_tiled,
                "successive_residual_storage_aliases": alias_links,
                "positions": positions.tolist(),
                "input_ids": ids.tolist(),
                "top1_token_ids": top1.tolist(),
            }
        )

    for index, hashes in enumerate(reduced_by_index):
        if len(set(hashes)) != 1:
            raise ValueError(f"allreduce {index}: reduced result differs across ranks")
    if len(set(verifier_ids)) != 1 or len(set(verifier_positions)) != 1:
        raise ValueError("verifier inputs differ across TP ranks")
    if len(set(verifier_top1)) != 1:
        raise ValueError("verifier top1 differs across TP ranks")

    manifests = sorted(root.glob("rank*/*/*.json"))
    aggregate = hashlib.sha256()
    for path in manifests:
        aggregate.update(str(path.relative_to(root)).encode())
        aggregate.update(b"\0")
        aggregate.update(path.read_bytes())
    result = {
        "classification": f"deepseek_v4_sequential_m{width}_verifier_corpus",
        "passed": True,
        "scope": "sequential target geometry; predictor acceptance and throughput unevaluated",
        "capture_dir": str(root),
        "width": width,
        "proposal_source": "attached_k160_mtp_repeated_geometry_only",
        "predictor_acceptance_evaluated": False,
        "localmax_eligible": False,
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
