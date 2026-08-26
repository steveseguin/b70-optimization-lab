#!/usr/bin/env python3
"""Compose immutable TP1/MTP4 receipts into conservative additive coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
RESULT = REPO / (
    "experiments/qwen38-27b-b70/data/"
    "2026-08-26-qwen38-official-f01e-autoround-tp1-mtp4-f16-eager-depth-r1-human-adjudication-result.json"
)
PROTECTED = [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def need(value, message):
    if not value:
        raise RuntimeError(message)


def compose_source(binding):
    result_path = REPO / binding["result_path"]
    validator_path = REPO / binding["validator_path"]
    raw_root = Path(binding["raw_root"])
    need(digest(result_path) == binding["result_sha256"], f"source result changed: {result_path}")
    need(digest(validator_path) == binding["validator_sha256"], f"source validator changed: {validator_path}")
    namespace = runpy.run_path(str(validator_path), run_name=f"composed_{validator_path.stem}")
    report = namespace["validate"](raw_root, result_path)
    source = load(result_path)
    need(source["cleanup"]["terminal_receipt_sha256"] == binding["terminal_receipt_sha256"], "source terminal binding changed")
    need(source["cleanup"]["arm_result_sha256"] == binding["arm_result_sha256"], "source arm binding changed")
    return source, raw_root, report


def screened_cell(root, depth):
    raw_path = root / "exact-depth" / f"depth-{depth}.json"
    verification_path = root / "verification" / f"depth-{depth}.json"
    raw, verification = load(raw_path), load(verification_path)
    target = verification["target_verification"]
    acceptance = verification["acceptance"]
    usage = raw["response"]["usage"]
    need(raw["gate"]["passed"] and target["passed"] and acceptance["passed"], f"screened gates failed: {depth}")
    need(usage["prompt_tokens_details"]["cached_tokens"] == 0, f"cache reuse appeared: {depth}")
    need(raw["response"]["output_token_ids_sha256"] == target["target_ids_sha256"], f"target hash mismatch: {depth}")
    return {
        "x": depth,
        "publication_state": "lab-screened",
        "evidence_grade": "D",
        "decode_tok_s": raw["metric_window"]["conventional_99_interval_tok_s"],
        "ttft_s": raw["metric_window"]["time_to_first_token_s"],
        "cached_tokens": 0,
        "completion_tokens": usage["completion_tokens"],
        "accepted_tokens": acceptance["accepted_tokens"],
        "drafted_tokens": acceptance["drafted_tokens"],
        "acceptance_rate": acceptance["acceptance_rate"],
        "candidate_token_ids_sha256": raw["response"]["output_token_ids_sha256"],
        "target_token_ids_sha256": target["target_ids_sha256"],
        "raw_sha256": digest(raw_path),
        "verification_sha256": digest(verification_path),
    }


def quarantined_2k(root):
    depth = 2048
    raw_path = root / "exact-depth" / f"depth-{depth}.json"
    verification_path = root / "verification" / f"depth-{depth}.json"
    raw, verification = load(raw_path), load(verification_path)
    target = verification["target_verification"]
    acceptance = verification["acceptance"]
    usage = raw["response"]["usage"]
    need(raw["gate"]["passed"] and acceptance["passed"] and not target["passed"], "2K disposition changed")
    need(usage["prompt_tokens_details"]["cached_tokens"] == 0, "2K cache reuse appeared")
    return {
        "x": depth,
        "publication_state": "quarantined",
        "evidence_grade": "D",
        "reason": "exact and cache-zero measurement passed, but frozen target-token parity failed",
        "speed_publication_authorized": False,
        "exact_depth_gate_passed": True,
        "cached_tokens": 0,
        "completion_tokens": usage["completion_tokens"],
        "accepted_tokens": acceptance["accepted_tokens"],
        "drafted_tokens": acceptance["drafted_tokens"],
        "acceptance_rate": acceptance["acceptance_rate"],
        "candidate_token_ids_sha256": raw["response"]["output_token_ids_sha256"],
        "target_token_ids_sha256": target["target_ids_sha256"],
        "first_divergence": target["first_divergence"],
        "raw_sha256": digest(raw_path),
        "verification_sha256": digest(verification_path),
    }


def quarantined_8k(expansion_root, sentinel_root, sentinel):
    depth = 8192
    expansion_raw_path = expansion_root / "exact-depth" / f"depth-{depth}.json"
    expansion_verification_path = expansion_root / "verification" / f"depth-{depth}.json"
    sentinel_raw_path = sentinel_root / "exact-depth" / f"depth-{depth}.json"
    expansion_raw = load(expansion_raw_path)
    expansion_verification = load(expansion_verification_path)
    sentinel_raw = load(sentinel_raw_path)
    target = expansion_verification["target_verification"]
    acceptance = expansion_verification["acceptance"]
    usage = expansion_raw["response"]["usage"]
    need(sentinel["target_oracle"]["passed"] and not target["passed"], "8K cross-boot conflict disappeared")
    need(sentinel_raw["response"]["output_token_ids_sha256"] == target["target_ids_sha256"], "8K passed parent no longer matches target")
    need(expansion_raw["response"]["output_token_ids_sha256"] != target["target_ids_sha256"], "8K expansion no longer diverges")
    need(usage["prompt_tokens_details"]["cached_tokens"] == 0, "8K cache reuse appeared")
    return {
        "x": depth,
        "publication_state": "quarantined",
        "evidence_grade": "D",
        "reason": "same-profile separate boots conflict: the quality sentinel matched the target oracle and the later expansion diverged at token 99",
        "speed_publication_authorized": False,
        "cross_boot_conflict": {
            "passed_parent": {
                "target_parity_passed": True,
                "candidate_token_ids_sha256": sentinel_raw["response"]["output_token_ids_sha256"],
                "target_token_ids_sha256": sentinel["target_oracle"]["target_token_ids_sha256"],
                "quality_grade": sentinel["quality"]["grade"],
                "exact_depth_raw_sha256": digest(sentinel_raw_path),
                "verification_gates_sha256": sentinel["mechanism"]["raw_sha256"],
                "quality_sha256": sentinel["quality"]["raw_sha256"],
            },
            "later_expansion": {
                "target_parity_passed": False,
                "cached_tokens": 0,
                "completion_tokens": usage["completion_tokens"],
                "accepted_tokens": acceptance["accepted_tokens"],
                "drafted_tokens": acceptance["drafted_tokens"],
                "acceptance_rate": acceptance["acceptance_rate"],
                "candidate_token_ids_sha256": expansion_raw["response"]["output_token_ids_sha256"],
                "target_token_ids_sha256": target["target_ids_sha256"],
                "first_divergence": target["first_divergence"],
                "raw_sha256": digest(expansion_raw_path),
                "verification_sha256": digest(expansion_verification_path),
            },
        },
    }


def closed_32k(root, expansion):
    depth = 32768
    raw_path = root / "exact-depth" / f"depth-{depth}.json"
    verification_path = root / "verification" / f"depth-{depth}.json"
    raw = load(raw_path)
    need(not raw["gate"]["passed"] and raw["response"]["usage"] == {}, "32K incomplete contract changed")
    need(len(raw["response"]["token_ids"]) == 121, "32K returned-token count changed")
    return {
        "x": depth,
        "publication_state": "closed",
        "evidence_grade": "D",
        "reason": "engine-core fatal before a complete exact-depth response",
        "speed_publication_authorized": False,
        "returned_tokens": 121,
        "usage_present": False,
        "partial_timing_is_publishable_speed": False,
        "engine_error": expansion["failure"]["error"],
        "candidate_token_ids_sha256": raw["response"]["output_token_ids_sha256"],
        "target_token_ids_sha256": load(verification_path)["target_verification"]["target_ids_sha256"],
        "raw_sha256": digest(raw_path),
        "verification_sha256": digest(verification_path),
    }


def validate(result_path: Path):
    result = load(result_path)
    need(result["status"] == "mixed-depth-human-adjudicated-grade-d", "adjudication status changed")
    sources = result["source_artifacts"]
    expansion, expansion_root, expansion_report = compose_source(sources["expansion"])
    sentinel, sentinel_root, sentinel_report = compose_source(sources["passed_8k_parent"])
    need(expansion_report == {"status": "pass", "site_cells": 0, "acceptance_gates": "6/6", "exact_depth_gates": "5/6", "target_parity_gates": "3/6", "engine_fatal_depth": 32768}, "expansion validator report changed")
    need(sentinel_report["status"] == "pass" and sentinel_report["cells_published"] == 0 and sentinel_report["target_parity"], "sentinel validator report changed")

    need(result["identity"]["model_revision"] == expansion["identity"]["model_revision"] == sentinel["identity"]["model_revision"], "model identity changed")
    need(result["identity"]["image"] == expansion["identity"]["image"] == sentinel["identity"]["image"], "image identity changed")
    need(result["identity"]["vllm_source"] == expansion["identity"]["vllm_source"] == sentinel["identity"]["vllm_source"], "runtime identity changed")
    need(result["config"]["tp"] == 1 and result["config"]["mtp"] == 4 and result["config"]["graph"] == "off" and result["config"]["kv"] == "f16", "profile selector changed")
    need(result["metric_definition"]["screened_decode_field"] == "conventional_99_interval_tok_s", "metric changed")

    cells = [
        {"x": 0, "publication_state": "missing", "reason": "no exact zero-context measurement exists"},
        quarantined_2k(expansion_root),
        screened_cell(expansion_root, 4096),
        quarantined_8k(expansion_root, sentinel_root, sentinel),
        screened_cell(expansion_root, 16384),
        screened_cell(expansion_root, 24576),
        closed_32k(expansion_root, expansion),
    ]
    need(result["cells"] == cells, "adjudicated cells differ from immutable raw receipts")

    coverage = result["coverage"]
    need(coverage == {"missing_depths": [0], "quarantined_depths": [2048, 8192], "screened_depths": [4096, 16384, 24576], "closed_depths": [32768], "lab_measured_depths": [], "evidence_grade": "D"}, "coverage mapping changed")
    for cell in cells:
        if cell["publication_state"] in {"quarantined", "closed"}:
            need("decode_tok_s" not in cell and "ttft_s" not in cell and not cell["speed_publication_authorized"], f"non-screened speed appeared: {cell['x']}")
    need([cell["decode_tok_s"] for cell in cells if cell["publication_state"] == "lab-screened"] == [14.850597409841217, 12.361817762397319, 13.116686989341177], "screened speeds changed")

    controls = result["evidence_controls"]
    need(controls["source_expansion_quality"] == "not-run-engine-dead", "expansion quality overclaimed")
    need(controls["passed_parent_8k_full_quality"] and controls["passed_parent_8k_quality_is_not_transferred_to_other_depths"], "quality scope widened")
    need(controls["complete_exact_depth_cells_cached_tokens_zero"] and controls["both_source_cleanups"] == "clean", "cache or cleanup gate weakened")
    need(controls["single_rank_topology"] == "ONEAPI_DEVICE_SELECTOR=level_zero:0", "topology binding changed")

    adjudication = result["adjudication"]
    need(adjudication["both_original_receipts_preserved_immutable"] and not adjudication["automatic_publication_authority"], "source authority widened")
    need(adjudication["selected_speed_depths"] == [4096, 16384, 24576] and adjudication["no_selected_speed_depths"] == [2048, 8192, 32768], "speed selection changed")
    authority = result["authority"]
    need(authority["lab_screened_speed_cells"] == 3 and authority["lab_measured_cells"] == 0, "evidence grade widened")
    need(authority["quarantined_cells"] == 2 and authority["closed_cells"] == 1 and authority["zero_context_cells"] == 0, "authority counts changed")
    need(not authority["headline_or_protected_replacement"] and not authority["parent_8k_speed_selection"] and not authority["localmaxxing_submission"], "replacement authority appeared")
    need(authority["protected_decode_values_unchanged"] == PROTECTED, "protected values changed")
    return {"status": "pass", "lab_screened": 3, "lab_measured": 0, "quarantined": 2, "closed": 1, "missing": 1, "selected_speed_depths": [4096, 16384, 24576]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=RESULT)
    args = parser.parse_args()
    try:
        report = validate(args.result)
    except (KeyError, OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
