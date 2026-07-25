#!/usr/bin/env python3
"""Aggregate the frozen four-card Laguna W1 N32 component gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
from pathlib import Path
from typing import Any


EXPECTED_RANKS = {0, 1, 2, 3}
EXPECTED_EPOCHS = 64
EXPECTED_BLOCKS = 31
EXPECTED_CYCLES_PER_ARM = 64
EXPECTED_LAYERS = 47
MIN_CROSS_CARD_RELATIVE_IMPROVEMENT = 0.02
EXPECTED_VLLM_COMMIT = "ef334233deabeaeedb607056a2db1c90edb3887c"
EXPECTED_KERNEL_COMMIT = "a5f99d8ed98c02eef87e29be44a8cd63b1ec9155"
EXPECTED_EXTENSION_SHA256 = (
    "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8"
)
EXPECTED_GROUPED_GEMM_SHA256 = (
    "8cdada551eab55e55aae2d33d852999df21c816f1f4575a51a259c714c12567f"
)
EXPECTED_FIXTURE_SHA256 = (
    "478a23508e635c91fa62ff0a4b737016266bc308e8fe60111e81abad3d47c1f6"
)
EXPECTED_FIXTURE_AGGREGATE_SHA256 = (
    "2830da5e5e7ee2f4118b8d6c5618be6d36bb9a567c17df230bb87e20890734af"
)
EXPECTED_PRODUCTION_SOURCE_AGGREGATE_SHA256 = (
    "bd1d6ef31f8ee359f04c6af1ccc55e39d79b21fc1592ae2377734e64f2512a47"
)
NVME_MOUNT = Path("/mnt/fast-ai").resolve()
NVME_SOURCE = "/dev/nvme0n1p2"
NVME_FSTYPE = "ext4"
GATE_PATH = Path(__file__).with_name("gate_laguna_w1_n32.py").resolve()


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


def require_local_nvme_paths(*paths: Path) -> None:
    mount = subprocess.run(
        [
            "findmnt",
            "--noheadings",
            "--output",
            "SOURCE,FSTYPE",
            "--target",
            str(NVME_MOUNT),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    reported = {
        tuple(line.split(None, 1))
        for line in mount.stdout.splitlines()
        if len(line.split(None, 1)) == 2
    }
    if mount.returncode != 0 or (NVME_SOURCE, NVME_FSTYPE) not in reported:
        raise RuntimeError("required internal NVMe/ext4 mount identity drifted")
    for path in paths:
        resolved = path.resolve()
        try:
            resolved.relative_to(NVME_MOUNT)
        except ValueError as error:
            raise RuntimeError(
                f"component evidence path is outside internal NVMe: {resolved}"
            ) from error


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
        "tile_contract": (
            contract.get("control_tile") == 64
            and contract.get("candidate_tile") == 32
            and contract.get("w2_tile") == 64
        ),
        "source_identity": (
            runtime.get("vllm_commit") == EXPECTED_VLLM_COMMIT
            and runtime.get("kernel_commit") == EXPECTED_KERNEL_COMMIT
        ),
        "binary_identity": (
            runtime.get("extension_sha256") == EXPECTED_EXTENSION_SHA256
            and runtime.get("grouped_gemm_sha256")
            == EXPECTED_GROUPED_GEMM_SHA256
        ),
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
            and fixture.get("sha256") == EXPECTED_FIXTURE_SHA256
            and fixture.get("aggregate_tensor_sha256")
            == EXPECTED_FIXTURE_AGGREGATE_SHA256
            and fixture.get("production_source_aggregate_sha256")
            == EXPECTED_PRODUCTION_SOURCE_AGGREGATE_SHA256
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


def aggregate_cards(cards: list[dict[str, Any]]) -> dict[str, Any]:
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
    return {
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
    require_local_nvme_paths(*args.card_result, args.out)
    cards = [
        check_card(path, load_result(path)) for path in args.card_result
    ]
    result = aggregate_cards(cards)
    result["tool_identity"] = {
        "gate_path": str(GATE_PATH),
        "gate_sha256": sha256_file(GATE_PATH),
        "analyzer_path": str(Path(__file__).resolve()),
        "analyzer_sha256": sha256_file(Path(__file__).resolve()),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
