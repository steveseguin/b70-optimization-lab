#!/usr/bin/env python3
"""Run the CPU-only correctness suite for the EP4 M=1 sparse candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch

from ep4_m1_sparse_expert_assignment import (
    EP_SIZE,
    GLOBAL_EXPERTS,
    TOP_K,
    adversarial_routes,
    assert_exact_assignment,
    build_contiguous_ep4_expert_map,
    sparse_m1_ep4_candidate,
)

SEEDS = (20260827, 20260828, 20260829)
CHANGING_INPUTS_PER_SEED = 100


def tensor_digest(tensor: torch.Tensor) -> str:
    return hashlib.sha256(tensor.contiguous().numpy().tobytes()).hexdigest()


def run_suite() -> dict[str, object]:
    changing_cases = 0
    adversarial_cases = 0
    route_digests: set[str] = set()
    for seed in SEEDS:
        generator = torch.Generator(device="cpu").manual_seed(seed)
        for _ in range(CHANGING_INPUTS_PER_SEED):
            topk_ids = (
                torch.randperm(GLOBAL_EXPERTS, generator=generator, dtype=torch.int64)[
                    :TOP_K
                ]
                .to(torch.int32)
                .reshape(1, TOP_K)
            )
            route_digests.add(tensor_digest(topk_ids))
            for ep_rank in range(EP_SIZE):
                expert_map = build_contiguous_ep4_expert_map(ep_rank)
                topk_before = topk_ids.clone()
                map_before = expert_map.clone()
                assert_exact_assignment(topk_ids, expert_map)
                if not torch.equal(topk_ids, topk_before) or not torch.equal(
                    expert_map, map_before
                ):
                    raise AssertionError("candidate mutated an input tensor")
                changing_cases += 1

    for ep_rank in range(EP_SIZE):
        expert_map = build_contiguous_ep4_expert_map(ep_rank)
        for label, topk_ids in adversarial_routes(ep_rank).items():
            assert_exact_assignment(topk_ids, expert_map)
            outputs = sparse_m1_ep4_candidate(topk_ids, expert_map)
            expected_hits = int(label.rsplit("_", 1)[1])
            observed_hits = int(outputs[2].item()) // 16
            if observed_hits != expected_hits:
                raise AssertionError(
                    f"rank {ep_rank} {label}: expected {expected_hits} local blocks, "
                    f"got {observed_hits}"
                )
            adversarial_cases += 1

    if len(route_digests) != len(SEEDS) * CHANGING_INPUTS_PER_SEED:
        raise AssertionError("changing-input suite unexpectedly repeated a route")

    return {
        "schema_version": 1,
        "status": "cpu_exact_candidate_positive",
        "candidate": "ep4_m1_sparse_expert_assignment",
        "launch_authorized": False,
        "endpoint_authorized": False,
        "gpu_execution_authorized": False,
        "device": "cpu",
        "contract": {
            "global_experts": GLOBAL_EXPERTS,
            "local_experts_per_rank": 128,
            "ep_size": EP_SIZE,
            "tokens": 1,
            "top_k": TOP_K,
            "block_size_m": 16,
            "expert_placement": "contiguous_128_per_rank",
            "semantics": (
                "map_global_to_local_filter_remote_then_stable_sort_by_local_id"
            ),
        },
        "coverage": {
            "seeds": list(SEEDS),
            "changing_inputs_per_seed": CHANGING_INPUTS_PER_SEED,
            "unique_changing_routes": len(route_digests),
            "changing_rank_cases": changing_cases,
            "adversarial_rank_cases": adversarial_cases,
            "adversarial_local_hit_counts": [0, 1, 5, 10],
        },
        "outputs_compared_exactly": [
            "sorted_token_ids",
            "expert_ids",
            "num_tokens_post_pad",
        ],
        "input_tensors_unchanged": True,
        "next_required_gate": (
            "deferred native source-bound XPU component gate; this CPU runner "
            "cannot authorize a vLLM patch or endpoint launch"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        help="optional JSON receipt path; omission writes only to stdout",
    )
    args = parser.parse_args()
    result = run_suite()
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
