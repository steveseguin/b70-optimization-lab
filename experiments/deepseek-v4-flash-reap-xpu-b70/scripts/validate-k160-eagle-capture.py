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


def load_identity(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition("=")
        if not separator or key in result:
            raise RuntimeError(f"invalid capture identity line: {line!r}")
        result[key] = value
    return result


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
    target_ids_by_request: dict[int, list[int]] = {}
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
        unique_request_keys = request_keys.unique()
        if unique_request_keys.numel() != 1:
            raise RuntimeError(f"capture shard spans multiple trajectories: {shard}")
        if (
            int(manifest["rows"]) != shard_rows
            or int(manifest["request_key"]) != int(unique_request_keys[0])
            or manifest.get("assistant_loss_mask") != "all_rows"
            or manifest.get("reset_after_shard") is not True
        ):
            raise RuntimeError(f"capture transaction metadata mismatch: {shard}")
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
            target_ids_by_request.setdefault(current["request_key"], []).append(
                current["target"]
            )
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
        "_target_ids_by_request": target_ids_by_request,
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
            with (
                safe_open(left, framework="pt", device="cpu") as a,
                safe_open(right, framework="pt", device="cpu") as b,
            ):
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
    parser.add_argument("--capture-identity", type=Path, required=True)
    parser.add_argument("--replay-manifest", type=Path)
    parser.add_argument("--other-requests", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare-ranks", action="store_true")
    parser.add_argument("--expected-ranks", type=int, default=0)
    args = parser.parse_args()
    if args.namespace in {"eagletrain", "eagledev"} and not args.other_requests:
        raise ValueError("train and DEV validation require the counterpart manifest")

    capture_identity = load_identity(args.capture_identity)
    expected_identity = {
        "capture_base_vllm_commit": ("264c7f2f7df21ddeeab32ecca0353133344f1ac9"),
        "capture_patch_vllm_commit": ("ca0648d600c6c47cf163e96eb66b3a365d104987"),
        "xpu_kernel_commit": "31315673737d95da0f79179c8f755260ef02c1d6",
        "oneccl_commit": "48fda4f0e074db005596d6899d5227d3f0316c12",
        "model_revision": "7c360e1cd4a5168099dbc54d16d929bf6df04990",
        "artifact_manifest_sha256": (
            "08535b4ad7fd94419c7eadb1f6cf7f1de583d64f92a1760c86aa238972904e78"
        ),
        "feature_boundaries": "4,22,43",
        "feature_reduction": "post_mhc_mean_stream",
        "capture_dir": str(args.capture_root),
        "capture_namespace": args.namespace,
        "one_active_generation": "true",
        "speculation": "false",
    }
    mismatches = {
        key: {"expected": value, "actual": capture_identity.get(key)}
        for key, value in expected_identity.items()
        if capture_identity.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"capture identity mismatch: {mismatches}")

    namespace_dir = args.capture_root / args.namespace
    rank_dirs = sorted(namespace_dir.glob("rank-*"))
    if not rank_dirs:
        raise RuntimeError(f"no rank directories in {namespace_dir}")
    if args.expected_ranks and len(rank_dirs) != args.expected_ranks:
        raise RuntimeError(
            f"expected {args.expected_ranks} rank directories, got {len(rank_dirs)}"
        )
    if args.expected_ranks:
        expected_names = {f"rank-{rank:03d}" for rank in range(args.expected_ranks)}
        if {path.name for path in rank_dirs} != expected_names:
            raise RuntimeError(
                "rank directory names are not the expected contiguous set"
            )
    rank_results = [validate_rank(path) for path in rank_dirs]
    if args.compare_ranks:
        compare_ranks(rank_results)
    target_ids_by_request = rank_results[0].pop("_target_ids_by_request")
    for result in rank_results[1:]:
        result.pop("_target_ids_by_request")
    requests = load_requests(args.requests)
    external_request_by_key = {int(row["request_key"]): row for row in requests}
    if not args.replay_manifest and len(external_request_by_key) != len(requests):
        raise RuntimeError("request-key collision")
    captured_counts = rank_results[0]["request_counts"]
    captured_keys = list(map(int, captured_counts))
    request_by_key = external_request_by_key
    key_mapping_mode = "external-request-id-hash"
    if args.replay_manifest:
        replay_rows = load_requests(args.replay_manifest)
        if len(replay_rows) != len(requests):
            raise RuntimeError("replay and trajectory manifest lengths differ")
        request_by_key = {}
        for index, (replay_row, trajectory) in enumerate(
            zip(replay_rows, requests, strict=True)
        ):
            if (
                int(replay_row["trajectory_index"]) != index
                or replay_row["trajectory_request_id"] != trajectory["request_id"]
            ):
                raise RuntimeError("replay lineage does not match trajectories")
            key = int(replay_row["request_key"])
            if key in request_by_key:
                raise RuntimeError("replay request-key collision")
            request_by_key[key] = trajectory
        missing_metadata = set(captured_keys) - set(request_by_key)
        if missing_metadata:
            raise RuntimeError(
                f"captured request keys lack replay lineage: {missing_metadata}"
            )
        if set(request_by_key) != set(captured_keys):
            raise RuntimeError("replay lineage and captured request keys differ")
        key_mapping_mode = "exact-replay-request-id-hash"
    elif set(captured_keys) - set(request_by_key):
        # vLLM randomizes the internal engine request ID after accepting the
        # external OpenAI request ID.  Under the required one-active-generation
        # capture contract, first-seen internal keys and request-manifest rows
        # have an exact one-to-one order.  Require token counts to agree before
        # accepting that mapping.
        if len(captured_keys) != len(requests):
            raise RuntimeError("internal request-key count differs from metadata")
        request_by_key = dict(zip(captured_keys, requests, strict=True))
        for key, row in request_by_key.items():
            expected = int(row["response"]["usage"].get("completion_tokens") or 0)
            if int(captured_counts[key]) != expected:
                raise RuntimeError(
                    f"internal request-key row count mismatch for {key}: "
                    f"{captured_counts[key]} != {expected}"
                )
        key_mapping_mode = "one-active-first-seen-order"
    for key, row in request_by_key.items():
        expected_ids = [
            int(token_id) for token_id in row["response"]["output_token_ids"]
        ]
        if target_ids_by_request[key] != expected_ids:
            raise RuntimeError(
                f"captured target IDs differ from greedy trajectory for key {key}"
            )
    prompt_hashes = {row["prompt_sha256"] for row in requests}
    disjoint = True
    other_prompt_set_sha256 = None
    other_request_manifest = None
    if args.other_requests:
        other = load_requests(args.other_requests)
        other_hashes = {row["prompt_sha256"] for row in other}
        disjoint = not bool(prompt_hashes & other_hashes)
        if not disjoint:
            raise RuntimeError("train and DEV prompt hashes overlap")
        other_prompt_set_sha256 = hashlib.sha256(
            "\n".join(sorted(other_hashes)).encode()
        ).hexdigest()
        other_request_manifest = {
            "path": str(args.other_requests.resolve()),
            "sha256": sha256(args.other_requests),
            "prompt_set_sha256": other_prompt_set_sha256,
            "prompt_count": len(other),
        }

    category_rows: Counter[str] = Counter()
    for key, count in rank_results[0]["request_counts"].items():
        category_rows[request_by_key[int(key)]["category"]] += count
    total_rows = rank_results[0]["rows"]
    response_tokens = sum(
        int(row["response"]["usage"].get("completion_tokens") or 0) for row in requests
    )
    output_token_count = sum(
        len(row["response"].get("output_token_ids") or []) for row in requests
    )
    if total_rows != response_tokens or total_rows != output_token_count:
        raise RuntimeError(
            "captured rows, completion-token usage, and output IDs differ: "
            f"{total_rows}, {response_tokens}, {output_token_count}"
        )
    output_token_ids_available = all(
        bool(row["response"].get("output_token_ids")) for row in requests
    )
    summary = {
        "schema_version": "k160-eagle-capture-validation-v1",
        "namespace": args.namespace,
        "capture_root": str(args.capture_root),
        "capture_identity": {
            "path": str(args.capture_identity.resolve()),
            "sha256": sha256(args.capture_identity),
            "fields": capture_identity,
        },
        "rank_results": rank_results,
        "captured_rows": total_rows,
        "response_completion_tokens": response_tokens,
        "response_output_token_ids": output_token_count,
        "category_rows": dict(category_rows),
        "category_fractions": {
            name: count / total_rows for name, count in category_rows.items()
        },
        "prompt_count": len(requests),
        "request_manifest": {
            "path": str(args.requests.resolve()),
            "sha256": sha256(args.requests),
        },
        "prompt_set_sha256": hashlib.sha256(
            "\n".join(sorted(prompt_hashes)).encode()
        ).hexdigest(),
        "other_request_manifest": other_request_manifest,
        "other_prompt_set_sha256": other_prompt_set_sha256,
        "other_prompt_set_disjoint": disjoint,
        "output_token_ids_available": output_token_ids_available,
        "target_token_alignment_passed": True,
        "request_key_mapping_mode": key_mapping_mode,
        "request_key_mapping": [
            {
                "internal_request_key": key,
                "response_id": request_by_key[key]["response"]["response_id"],
                "prompt_id": request_by_key[key]["prompt_id"],
                "rows": int(captured_counts[key]),
            }
            for key in captured_keys
        ],
        "tp_rank_comparison": "passed" if args.compare_ranks else "not-requested",
        "alignment_passed": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
