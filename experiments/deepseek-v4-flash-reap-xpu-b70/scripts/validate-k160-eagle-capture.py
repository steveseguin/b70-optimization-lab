#!/usr/bin/env python3
"""Validate K160 EAGLE feature shards, alignment, isolation, and checksums."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import torch
from safetensors import safe_open


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_requests(path: Path) -> list[dict[str, Any]]:
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def validate_rank(rank_dir: Path) -> dict[str, Any]:
    shards = sorted(rank_dir.glob("features-*.safetensors"))
    if not shards:
        raise RuntimeError(f"no feature shards in {rank_dir}")
    checksums = []
    rows = 0
    alignment_checks = 0
    alignment_failures = 0
    previous: dict[str, int] | None = None
    request_counts: Counter[int] = Counter()
    for shard in shards:
        manifest_path = shard.with_suffix(".json")
        manifest = json.loads(manifest_path.read_text())
        actual_sha = sha256(shard)
        if actual_sha != manifest["sha256"]:
            raise RuntimeError(f"checksum mismatch: {shard}")
        if manifest["feature_boundary_ids"] != [4, 22, 43]:
            raise RuntimeError(f"wrong feature boundaries: {shard}")
        with safe_open(shard, framework="pt", device="cpu") as tensors:
            features = tensors.get_tensor("features_bf16")
            final_hidden = tensors.get_tensor("target_final_hidden_bf16")
            input_ids = tensors.get_tensor("input_token_id")
            target_ids = tensors.get_tensor("next_target_token_id")
            positions = tensors.get_tensor("position_id")
            request_keys = tensors.get_tensor("request_key")
        shard_rows = features.shape[0]
        if features.shape != (shard_rows, 3, 4096):
            raise RuntimeError(f"wrong feature shape: {shard}")
        if final_hidden.shape != (shard_rows, 4096):
            raise RuntimeError(f"wrong final hidden shape: {shard}")
        if features.dtype != torch.bfloat16 or final_hidden.dtype != torch.bfloat16:
            raise RuntimeError(f"feature dtype is not BF16: {shard}")
        for index in range(shard_rows):
            current = {
                "request_key": int(request_keys[index]),
                "position": int(positions[index]),
                "input": int(input_ids[index]),
                "target": int(target_ids[index]),
            }
            request_counts[current["request_key"]] += 1
            if previous and current["request_key"] == previous["request_key"]:
                alignment_checks += 1
                if (
                    current["position"] != previous["position"] + 1
                    or current["input"] != previous["target"]
                ):
                    alignment_failures += 1
            previous = current
        rows += shard_rows
        checksums.append(
            {
                "path": str(shard),
                "sha256": actual_sha,
                "rows": shard_rows,
                "bytes": shard.stat().st_size,
            }
        )
    if alignment_failures:
        raise RuntimeError(
            f"{alignment_failures}/{alignment_checks} sequential rows misaligned"
        )
    return {
        "rank_dir": str(rank_dir),
        "rows": rows,
        "request_counts": dict(request_counts),
        "alignment_checks": alignment_checks,
        "alignment_failures": alignment_failures,
        "shards": checksums,
    }


def compare_ranks(rank_results: list[dict[str, Any]]) -> None:
    if len(rank_results) < 2:
        return
    reference_dir = Path(rank_results[0]["rank_dir"])
    reference = sorted(reference_dir.glob("features-*.safetensors"))
    for result in rank_results[1:]:
        other = sorted(Path(result["rank_dir"]).glob("features-*.safetensors"))
        if len(other) != len(reference):
            raise RuntimeError("TP rank shard counts differ")
        for left, right in zip(reference, other, strict=True):
            with safe_open(left, framework="pt", device="cpu") as a, safe_open(
                right, framework="pt", device="cpu"
            ) as b:
                for name in a.keys():
                    if not torch.equal(a.get_tensor(name), b.get_tensor(name)):
                        raise RuntimeError(
                            f"TP rank capture mismatch for {name}: {left} vs {right}"
                        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--other-requests", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare-ranks", action="store_true")
    args = parser.parse_args()

    namespace_dir = args.capture_root / args.namespace
    rank_dirs = sorted(namespace_dir.glob("rank-*"))
    rank_results = [validate_rank(path) for path in rank_dirs]
    if args.compare_ranks:
        compare_ranks(rank_results)
    requests = load_requests(args.requests)
    request_by_key = {int(row["request_key"]): row for row in requests}
    if len(request_by_key) != len(requests):
        raise RuntimeError("request-key collision")
    captured_keys = set(map(int, rank_results[0]["request_counts"]))
    missing_metadata = captured_keys - set(request_by_key)
    if missing_metadata:
        raise RuntimeError(f"captured request keys lack metadata: {missing_metadata}")
    prompt_hashes = {row["prompt_sha256"] for row in requests}
    disjoint = True
    if args.other_requests:
        other = load_requests(args.other_requests)
        other_hashes = {row["prompt_sha256"] for row in other}
        disjoint = not bool(prompt_hashes & other_hashes)
        if not disjoint:
            raise RuntimeError("train and DEV prompt hashes overlap")

    category_rows: Counter[str] = Counter()
    for key, count in rank_results[0]["request_counts"].items():
        category_rows[request_by_key[int(key)]["category"]] += count
    total_rows = rank_results[0]["rows"]
    response_tokens = sum(
        int(row["response"]["usage"].get("completion_tokens") or 0)
        for row in requests
    )
    output_token_ids_available = all(
        bool(row["response"].get("output_token_ids")) for row in requests
    )
    summary = {
        "schema_version": "k160-eagle-capture-validation-v1",
        "namespace": args.namespace,
        "capture_root": str(args.capture_root),
        "rank_results": rank_results,
        "captured_rows": total_rows,
        "response_completion_tokens": response_tokens,
        "category_rows": dict(category_rows),
        "category_fractions": {
            name: count / total_rows for name, count in category_rows.items()
        },
        "prompt_count": len(requests),
        "prompt_set_sha256": hashlib.sha256(
            "\n".join(sorted(prompt_hashes)).encode()
        ).hexdigest(),
        "other_prompt_set_disjoint": disjoint,
        "output_token_ids_available": output_token_ids_available,
        "tp_rank_comparison": "passed" if args.compare_ranks else "not-requested",
        "alignment_passed": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
