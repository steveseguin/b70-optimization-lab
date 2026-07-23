#!/usr/bin/env python3
"""Aggregate the frozen four-card Laguna W1 N128 component gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any


EXPECTED_RANKS = {0, 1, 2, 3}
EXPECTED_EPOCHS = 64
EXPECTED_BLOCKS = 31
EXPECTED_CYCLES_PER_ARM = 64
EXPECTED_LAYERS = 47
MIN_CROSS_CARD_RELATIVE_IMPROVEMENT = 0.02


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_result(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def check_card(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    rank = payload.get("rank")
    runtime = payload.get("runtime", {})
    contract = payload.get("frozen_contract", {})
    pre = payload.get("pre_correctness", {})
    post = payload.get("post_correctness", {})
    tails = payload.get("tail_and_rejection_gate", {})
    timing = payload.get("timing", {})
    fixture = timing.get("real_production_fixture_identity", {})
    physical = runtime.get("physical_device", {})
    checks = {
        "top_level_pass": payload.get("passed") is True,
        "formal_component_pass": payload.get("formal_component_pass") is True,
        "formal_mode": payload.get("mode") == "formal",
        "rank_valid": rank in EXPECTED_RANKS,
        "affinity_matches_rank": runtime.get("ze_affinity_mask") == str(rank),
        "oneapi_selector": (
            runtime.get("oneapi_device_selector") == "level_zero:0"
        ),
        "physical_device_matches_rank": (
            physical.get("device_id") == rank
            and isinstance(physical.get("uuid"), str)
            and bool(physical.get("uuid"))
            and isinstance(physical.get("pci_bdf_address"), str)
            and bool(physical.get("pci_bdf_address"))
        ),
        "int32_topk": contract.get("topk_ids_dtype") == "torch.int32",
        "epochs": contract.get("epochs") == EXPECTED_EPOCHS,
        "blocks": contract.get("formal_blocks") == EXPECTED_BLOCKS,
        "cycles_per_arm": (
            contract.get("formal_cycles_per_arm")
            == EXPECTED_CYCLES_PER_ARM
        ),
        "layers": contract.get("target_layers") == EXPECTED_LAYERS,
        "pre_exact": (
            pre.get("passed") is True
            and len(pre.get("cases", [])) == EXPECTED_EPOCHS
            and all(case.get("passed") is True for case in pre.get("cases", []))
        ),
        "post_exact": (
            post.get("passed") is True
            and len(post.get("cases", [])) == EXPECTED_EPOCHS
            and all(
                case.get("passed") is True
                for case in post.get("cases", [])
            )
        ),
        "tail_and_rejections": tails.get("passed") is True,
        "timing": timing.get("passed") is True,
        "representative_routes": (
            timing.get("representative_ep4_route_share") is True
        ),
        "real_production_fixtures": (
            fixture.get("format")
            == "laguna-w1-real-m8-timing-fixtures-v1"
            and fixture.get("fixture_count") == 3 * EXPECTED_LAYERS
            and fixture.get("trace_sets") == 3
            and fixture.get("layers_per_set") == EXPECTED_LAYERS
        ),
        "constants_unchanged": (
            payload.get("constant_inputs_unchanged") is True
        ),
    }
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "rank": rank,
        "device": payload.get("device"),
        "extension_sha256": runtime.get("extension_sha256"),
        "grouped_gemm_sha256": runtime.get("grouped_gemm_sha256"),
        "timing_fixture_sha256": fixture.get("sha256"),
        "physical_uuid": physical.get("uuid"),
        "physical_bdf": physical.get("pci_bdf_address"),
        "wins": timing.get("wins"),
        "paired_median_saving_ms_per_47_layers": timing.get(
            "paired_median_saving_ms_per_47_layers"
        ),
        "relative_median_improvement": timing.get(
            "relative_median_improvement"
        ),
        "local_route_fractions": timing.get(
            "fixture_set_local_route_fractions"
        ),
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--card-result",
        action="append",
        type=Path,
        required=True,
        help="formal per-card result; provide exactly four times",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if len(args.card_result) != 4:
        raise SystemExit("exactly four --card-result paths are required")
    cards = [
        check_card(path, load_result(path)) for path in args.card_result
    ]
    ranks = [card["rank"] for card in cards]
    relative_values = [
        card["relative_median_improvement"]
        for card in cards
        if isinstance(card["relative_median_improvement"], (int, float))
    ]
    cross_card_relative = (
        statistics.fmean(relative_values)
        if len(relative_values) == 4
        else None
    )
    extension_hashes = {card["extension_sha256"] for card in cards}
    grouped_hashes = {card["grouped_gemm_sha256"] for card in cards}
    fixture_hashes = {card["timing_fixture_sha256"] for card in cards}
    physical_uuids = {card["physical_uuid"] for card in cards}
    physical_bdfs = {card["physical_bdf"] for card in cards}
    aggregate_checks = {
        "all_cards_pass": all(card["passed"] for card in cards),
        "four_distinct_declared_ranks": set(ranks) == EXPECTED_RANKS,
        "four_distinct_physical_uuids": len(physical_uuids) == 4,
        "four_distinct_physical_bdfs": len(physical_bdfs) == 4,
        "one_extension_binary": len(extension_hashes) == 1,
        "one_grouped_gemm_binary": len(grouped_hashes) == 1,
        "one_real_timing_fixture_artifact": len(fixture_hashes) == 1,
        "cross_card_relative_improvement": (
            cross_card_relative is not None
            and cross_card_relative
            >= MIN_CROSS_CARD_RELATIVE_IMPROVEMENT
        ),
    }
    passed = all(aggregate_checks.values())
    result = {
        "passed": passed,
        "component_exactness_and_timing_pass": passed,
        "counter_gate_evaluated": False,
        "endpoint_authorized": False,
        "required_ranks": sorted(EXPECTED_RANKS),
        "declared_ranks": ranks,
        "mean_relative_improvement": cross_card_relative,
        "required_mean_relative_improvement": (
            MIN_CROSS_CARD_RELATIVE_IMPROVEMENT
        ),
        "aggregate_checks": aggregate_checks,
        "cards": sorted(
            cards,
            key=lambda card: (
                card["rank"] if isinstance(card["rank"], int) else 99
            ),
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
