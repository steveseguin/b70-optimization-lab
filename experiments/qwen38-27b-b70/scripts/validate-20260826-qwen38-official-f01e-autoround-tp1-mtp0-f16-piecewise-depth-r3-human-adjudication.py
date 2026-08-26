#!/usr/bin/env python3
"""Compose R3 raw receipts into a target-parity-aware TP1 graph profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
RESULT = REPO / (
    "experiments/qwen38-27b-b70/data/"
    "2026-08-26-qwen38-official-f01e-autoround-tp1-mtp0-f16-piecewise-depth-r3-human-adjudication-result.json"
)
DEPTHS = [2048, 4096, 8192, 16384, 24576, 32768]
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


def quality_cache_values(quality):
    return [
        *(case["usage"]["prompt_tokens_details"]["cached_tokens"] for case in quality["exact_cases"]),
        *(run["usage"]["prompt_tokens_details"]["cached_tokens"] for run in quality["repeat_case"]["runs"]),
        quality["long_context_case"]["usage"]["prompt_tokens_details"]["cached_tokens"],
    ]


def validate_arm(root: Path, arm_id: str, binding, image: str, image_id: str):
    arm_root = root / arm_id
    for field, filename in (
        ("arm_result_sha256", "arm-result.json"),
        ("quality_sha256", "quality.json"),
        ("server_args_sha256", "server-args.shell.txt"),
        ("server_startup_sha256", "server-startup.log"),
        ("server_log_sha256", "server.log"),
        ("container_inspect_sha256", "container-inspect.json"),
    ):
        path = arm_root / filename
        need(digest(path) == binding[field], f"{arm_id} raw binding changed: {filename}")

    arm = load(arm_root / "arm-result.json")
    quality = load(arm_root / "quality.json")
    need(
        arm["state"] == "passed"
        and arm["passed_depth_count"] == 6
        and arm["quality_return_code"] == 0
        and arm["startup_identity_passed"],
        f"{arm_id} arm authority weakened",
    )
    need(
        quality["pass_all"]
        and quality["baseline_match_all"]
        and len(quality["exact_cases"]) == 7
        and all(case["pass"] for case in quality["exact_cases"])
        and quality["repeat_case"]["pass"]
        and quality["repeat_case"]["repeats"] == 8
        and len(quality["repeat_case"]["unique_hashes"]) == 1
        and quality["long_context_case"]["pass"]
        and len(quality["baseline_comparisons"]) == 24,
        f"{arm_id} full quality authority weakened",
    )
    caches = quality_cache_values(quality)
    need(len(caches) == 16 and all(value == 0 for value in caches), f"{arm_id} quality cache reuse appeared")

    inspection = load(arm_root / "container-inspect.json")
    need(isinstance(inspection, list) and len(inspection) == 1, f"{arm_id} container inspection changed")
    container = inspection[0]
    need(container["Image"] == image_id and container["Config"]["Image"] == image, f"{arm_id} image changed")
    environment = set(container["Config"]["Env"])
    need("ONEAPI_DEVICE_SELECTOR=level_zero:0" in environment and "ZE_AFFINITY_MASK=0" in environment, f"{arm_id} device selector changed")
    need("VLLM_CACHE_ROOT=/run-cache/vllm" in environment, f"{arm_id} cache environment changed")
    cache_mounts = [mount for mount in container["Mounts"] if mount["Destination"] == "/run-cache"]
    need(len(cache_mounts) == 1 and cache_mounts[0]["Source"] == binding["cache_root"], f"{arm_id} cache root changed")
    model_mounts = [mount for mount in container["Mounts"] if mount["Destination"].endswith("qwen3.8-27b-int4-autoround-devan")]
    need(len(model_mounts) == 1 and not model_mounts[0]["RW"], f"{arm_id} model mount is not read-only")

    startup = (arm_root / "server-startup.log").read_text(encoding="utf-8", errors="replace")
    args = (arm_root / "server-args.shell.txt").read_text(encoding="utf-8", errors="replace")
    need("world_size=1 rank=0 local_rank=0" in startup and "TP rank 0" in startup, f"{arm_id} TP1 topology not proven")
    if arm_id == "piecewise-f16":
        need("VLLM_XPU_ENABLE_XPU_GRAPH=1" in environment, "piecewise graph environment missing")
        need(
            "cudagraph_mode" in args
            and "PIECEWISE" in args
            and "cudagraph_capture_sizes" in args,
            "piecewise graph argv missing",
        )
        need("enforce_eager=False" in startup, "piecewise graph resolved eager")
        need("Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)" in startup, "piecewise capture missing")
        need("Graph capturing finished" in startup and "Capturing CUDA graphs (decode, FULL)" not in startup, "piecewise graph identity changed")
    else:
        need("--enforce-eager" in args and "enforce_eager=True" in startup, "eager target identity changed")
        need("Graph capturing finished" not in startup, "eager target unexpectedly captured a graph")
    return quality, cache_mounts[0]["Source"]


def raw_cell(root: Path, depth: int):
    eager_path = root / "eager-f16" / "exact-depth" / f"depth-{depth}.json"
    graph_path = root / "piecewise-f16" / "exact-depth" / f"depth-{depth}.json"
    eager, graph = load(eager_path), load(graph_path)
    for arm_id, raw in (("eager", eager), ("piecewise", graph)):
        need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), f"{arm_id} exact-depth gate failed: {depth}")
        usage = raw["response"]["usage"]
        need(usage["prompt_tokens"] == depth and usage["completion_tokens"] == 128, f"{arm_id} usage changed: {depth}")
        need(usage["prompt_tokens_details"]["cached_tokens"] == 0, f"{arm_id} cache reuse appeared: {depth}")
    candidate_ids = graph["response"]["token_ids"]
    target_ids = eager["response"]["token_ids"]
    first_divergence = next((index for index, pair in enumerate(zip(candidate_ids, target_ids)) if pair[0] != pair[1]), None)
    common = {
        "x": depth,
        "evidence_grade": "C",
        "cached_tokens": 0,
        "completion_tokens": 128,
        "candidate_token_ids_sha256": graph["response"]["output_token_ids_sha256"],
        "target_token_ids_sha256": eager["response"]["output_token_ids_sha256"],
        "piecewise_raw_sha256": digest(graph_path),
        "eager_target_raw_sha256": digest(eager_path),
    }
    if candidate_ids == target_ids:
        return {
            **common,
            "publication_state": "lab-measured",
            "target_parity": True,
            "decode_tok_s": graph["metric_window"]["conventional_99_interval_tok_s"],
            "ttft_ms": graph["metric_window"]["time_to_first_token_s"] * 1000,
        }
    need(depth == 8192 and first_divergence == 98, f"unexpected target divergence: {depth}")
    return {
        **common,
        "publication_state": "quarantined",
        "target_parity": False,
        "reason": "same-image TP1/MTP0 PIECEWISE output diverges from eager TP1/MTP0 at token 99",
        "speed_publication_authorized": False,
        "first_divergence": {
            "zero_based": first_divergence,
            "one_based": first_divergence + 1,
            "candidate": candidate_ids[first_divergence],
            "target": target_ids[first_divergence],
        },
    }


def validate(result_path: Path):
    result = load(result_path)
    need(result["status"] == "mixed-depth-human-adjudicated-grade-c", "adjudication status changed")
    source_binding = result["source_artifacts"]["original_compact"]
    source_path = REPO / source_binding["result_path"]
    validator_path = REPO / source_binding["validator_path"]
    root = Path(source_binding["raw_root"])
    need(digest(source_path) == source_binding["result_sha256"], "original compact result changed")
    need(digest(validator_path) == source_binding["validator_sha256"], "original frozen validator changed")
    source_validator = runpy.run_path(str(validator_path), run_name="composed_graphmodes_r3_validator")["validate"]
    source_report = source_validator(root, source_path)
    need(
        source_report == {"status": "pass", "arms_verified": 2, "cells_verified": 12, "x0": "missing", "headline_replacement": False},
        "original compact validator report changed",
    )
    source = load(source_path)
    need(source["status"] == "passed-qualified-exact-depth", "original compact status changed")
    need(source["cleanup"]["terminal_receipt_sha256"] == source_binding["terminal_receipt_sha256"], "terminal binding changed")
    need(source["model_verification"]["raw_sha256"] == source_binding["model_verification_sha256"], "model verification binding changed")
    need(source["tracked_inputs"] == source_binding["tracked_inputs"], "preregistration or runner binding changed")

    raw_bindings = result["source_artifacts"]["raw_receipts"]
    eager_quality, eager_cache = validate_arm(root, "eager-f16", raw_bindings["eager-f16"], result["identity"]["image"], result["identity"]["image_id"])
    graph_quality, graph_cache = validate_arm(root, "piecewise-f16", raw_bindings["piecewise-f16"], result["identity"]["image"], result["identity"]["image_id"])
    need(eager_cache != graph_cache, "eager and graph cache roots are not isolated")

    terminal = load(root / "terminal-receipt.json")
    need(digest(root / "terminal-receipt.json") == source_binding["terminal_receipt_sha256"], "raw terminal changed")
    need(terminal["terminal"] and terminal["state"] == "passed" and all(value == 0 for value in terminal["arm_return_codes"].values()), "terminal cleanup authority weakened")
    need(source["cleanup"] == {
        "status": "clean",
        "terminal_receipt_sha256": source_binding["terminal_receipt_sha256"],
        "campaign_containers_absent_at_sealing": True,
        "ports_19466_and_19467_closed_at_sealing": True,
    }, "sealed cleanup record changed")

    need(result["identity"]["model_revision"] == source["identity"]["model_revision"], "model identity changed")
    need(result["identity"]["image"] == source["identity"]["image"], "image identity changed")
    need(result["identity"]["vllm_source"] == source["identity"]["vllm_source"], "source identity changed")
    config = result["config"]
    need(config["tp"] == 1 and config["mtp"] == 0 and config["graph_mode"] == "PIECEWISE" and config["kv"] == "f16", "profile selector changed")

    cells = [{"x": 0, "publication_state": "missing", "reason": "no exact zero-context measurement exists"}]
    cells.extend(raw_cell(root, depth) for depth in DEPTHS)
    need(result["cells"] == cells, "adjudicated cells differ from immutable raw receipts")
    measured = [cell for cell in cells if cell["publication_state"] == "lab-measured"]
    quarantined = [cell for cell in cells if cell["publication_state"] == "quarantined"]
    need([cell["x"] for cell in measured] == [2048, 4096, 16384, 24576, 32768], "measured depth mapping changed")
    need([cell["decode_tok_s"] for cell in measured] == [30.075429359128265, 29.41347238250489, 28.192761390148664, 27.463520678399885, 26.759466347975422], "measured speeds changed")
    need(len(quarantined) == 1 and quarantined[0]["x"] == 8192, "quarantine mapping changed")
    need("decode_tok_s" not in quarantined[0] and "ttft_ms" not in quarantined[0] and not quarantined[0]["speed_publication_authorized"], "8K speed was selected")
    need(quarantined[0]["first_divergence"] == {"zero_based": 98, "one_based": 99, "candidate": 411, "target": 579}, "8K divergence changed")

    coverage = result["coverage"]
    need(coverage == {"missing_depths": [0], "lab_measured_depths": [2048, 4096, 16384, 24576, 32768], "quarantined_depths": [8192], "evidence_grade": "C"}, "coverage mapping changed")
    controls = result["evidence_controls"]
    need(controls["original_validator_passes_but_does_not_compare_arms"], "original validator limitation was hidden")
    need(controls["both_full_quality_batteries_passed"] and controls["quality_cache_zero"] == "32/32", "quality authority weakened")
    need(controls["graph_identity"] == "PIECEWISE capture size 1; no FULL capture", "graph identity changed")
    need(controls["topology"] == "TP1 world_size=1 rank=0 on level_zero:0", "topology statement changed")
    need(controls["cache_isolation"] == "distinct eager-f16 and piecewise-f16 ext4 cache roots", "cache isolation statement changed")
    need(controls["cleanup"] == "terminal clean; both campaign containers absent and ports 19466/19467 closed at sealing", "cleanup statement changed")
    need(eager_quality["pass_all"] and graph_quality["pass_all"], "quality disappeared")

    adjudication = result["adjudication"]
    need(adjudication["original_result_preserved_immutable"] and not adjudication["automatic_publication_authority"], "adjudication authority widened")
    need(adjudication["selected_speed_depths"] == [2048, 4096, 16384, 24576, 32768] and adjudication["no_selected_speed_depths"] == [8192], "speed selection changed")
    authority = result["authority"]
    need(authority["lab_measured_speed_cells"] == 5 and authority["quarantined_cells"] == 1 and authority["zero_context_cells"] == 0, "authority counts changed")
    need(not authority["headline_or_protected_replacement"] and not authority["quarantined_8k_speed_selection"] and not authority["localmaxxing_submission"], "replacement authority appeared")
    need(authority["protected_decode_values_unchanged"] == PROTECTED, "protected values changed")
    return {"status": "pass", "lab_measured": 5, "quarantined": 1, "missing": 1, "selected_speed_depths": [2048, 4096, 16384, 24576, 32768]}


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
