#!/usr/bin/env python3
"""Validate and classify the bounded Q8-KV exact-2K repeat packet."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r2.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_module(RUNNER_PATH, "qwen36_q8kv_exact2k_classification_validator_runner")
GateError = RUNNER.GateError


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"JSON object required: {path}")
    return value


def token_ids_sha256(token_ids: list[int]) -> str:
    payload = json.dumps(token_ids, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def flag_value(argv: list[str], flag: str) -> str | None:
    try:
        return argv[argv.index(flag) + 1]
    except (ValueError, IndexError):
        return None


def divergence(control: list[int], candidate: list[int]) -> dict[str, Any]:
    common = 0
    for left, right in zip(control, candidate):
        if left != right:
            break
        common += 1
    first = None if control == candidate else common
    return {
        "equal": control == candidate,
        "common_prefix_tokens": common,
        "first_divergence_zero_based_index": first,
        "first_divergence_one_based_position": None if first is None else first + 1,
        "control_token_id": None if first is None else control[first],
        "candidate_token_id": None if first is None else candidate[first],
        "aligned_positions_different": sum(left != right for left, right in zip(control, candidate)),
    }


def validate(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    RUNNER.validate_manifest(manifest)
    RUNNER.verify_failed_r1(manifest)
    runtime = RUNNER.runtime_manifest(manifest)
    checks: dict[str, bool] = {}
    identity_path = root / "identity.json"
    identity = load_json(identity_path) if identity_path.is_file() else {}
    checks["identity_campaign"] = identity.get("campaign_id") == RUNNER.CAMPAIGN_ID
    checks["identity_parent_terminal"] = identity.get("failed_r1_parent_hashes", {}).get("terminal") == manifest["failed_r1_parent"]["raw"]["terminal-receipt.json"]
    checks["identity_parent_identity"] = identity.get("failed_r1_parent_hashes", {}).get("identity") == manifest["failed_r1_parent"]["raw"]["identity.json"]
    checks["identity_model"] = identity.get("model") == {key: runtime["model"][key] for key in ("path", "size_bytes", "sha256", "repository", "revision")}
    checks["identity_runtime"] = all(identity.get("runtime", {}).get(key) == runtime["runtime"][key] for key in ("binary", "binary_sha256", "manifest", "manifest_sha256", "source_commit"))
    checks["identity_dsos"] = identity.get("runtime", {}).get("local_dsos") == runtime["runtime"]["effective_local_shared_libraries"]
    checks["identity_fixture"] = identity.get("fixture_sha256") == runtime["fixture"]["sha256"]
    checks["identity_environment"] = all(identity.get("runtime_environment", {}).get(key) == value for key, value in {
        "ONEAPI_DEVICE_SELECTOR": "level_zero:*", "ZE_AFFINITY_MASK": "0",
        "ZES_ENABLE_SYSMAN": "1", "UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS": "1",
        "GGML_SYCL_ENABLE_VMM": "1", "GGML_SYCL_ENABLE_GRAPH": "0",
        "GGML_SYCL_GRAPH_CACHE_SIZE": "0", "GGML_SYCL_ENABLE_DNN": "0",
        "GGML_SYCL_ENABLE_OPT": "1", "GGML_SYCL_FA_ONEDNN": "1",
        "GGML_SYCL_FA_ONEDNN_MAX_KV": "0", "GGML_SYCL_ENABLE_MKL_FA": "1",
        "GGML_SYCL_ENABLE_FLASH_ATTN": "1",
    }.items())
    argv_by_arm = identity.get("server_argv") if isinstance(identity.get("server_argv"), dict) else {}
    summaries: list[dict[str, Any]] = []
    tokens_by_arm: dict[str, list[int]] = {}
    stable_by_arm: dict[str, bool] = {}
    valid_by_arm: dict[str, bool] = {}
    for arm, route in RUNNER.ARM_PLAN:
        argv = argv_by_arm.get(arm) if isinstance(argv_by_arm.get(arm), list) else []
        argv_ok = (
            flag_value(argv, "--port") == str(RUNNER.PORT)
            and flag_value(argv, "--alias") == runtime["server_contract"]["model_alias"]
            and flag_value(argv, "-ctk") == flag_value(argv, "-ctv") == "q8_0"
            and flag_value(argv, "--spec-type") == ("none" if route == 0 else "draft-mtp")
        )
        if route > 0:
            argv_ok = argv_ok and (
                flag_value(argv, "--spec-draft-n-max") == str(route)
                and flag_value(argv, "--spec-draft-n-min") == "0"
                and flag_value(argv, "--spec-draft-type-k") == flag_value(argv, "--spec-draft-type-v") == "q8_0"
            )
        arm_result_path = root / arm / "arm-result.json"
        models_path = root / arm / "models.json"
        arm_result = load_json(arm_result_path) if arm_result_path.is_file() else {}
        models = load_json(models_path) if models_path.is_file() else {}
        cleanup_ok = arm_result.get("cleanup") == {
            "forced_kill": False, "port_closed": True,
            "render_node_idle": True, "server_survivor": False,
        }
        models_ok = any(row.get("id") == runtime["server_contract"]["model_alias"] for row in models.get("data", []) if isinstance(row, dict))
        hashes: list[str] = []
        token_rows: list[list[int]] = []
        repeats: list[dict[str, Any]] = []
        repeats_valid = True
        for repeat in RUNNER.REPEATS:
            directory = root / arm / f"repeat-{repeat}"
            receipt_path = directory / "exact-depth.json"
            receipt = load_json(receipt_path) if receipt_path.is_file() else {}
            response = receipt.get("response") if isinstance(receipt.get("response"), dict) else {}
            token_ids = response.get("token_ids") if isinstance(response.get("token_ids"), list) else []
            token_ids_valid = len(token_ids) == 128 and all(isinstance(token, int) and not isinstance(token, bool) for token in token_ids)
            output_hash = response.get("output_token_ids_sha256")
            receipt_ok = (
                receipt.get("status") == "passed"
                and receipt.get("gate", {}).get("passed") is True
                and token_ids_valid
                and output_hash == token_ids_sha256(token_ids)
                and response.get("llama_cache_n") == 0
            )
            counter_summary = None
            counter_ok = True
            if route > 0:
                counter_path = directory / "draft-counters.json"
                counter = load_json(counter_path) if counter_path.is_file() else {}
                rows = counter.get("new_rows") if isinstance(counter.get("new_rows"), list) else []
                counter_ok = (
                    counter.get("active_context_tokens") == RUNNER.DEPTH
                    and counter.get("repeat") == repeat
                    and counter.get("rows_after") == counter.get("rows_before", -2) + 1
                    and len(rows) == 1
                    and isinstance(rows[0].get("accepted"), int)
                    and isinstance(rows[0].get("generated"), int)
                    and 0 < rows[0]["accepted"] <= rows[0]["generated"]
                    and 0 < rows[0].get("ratio", 0) <= 1
                )
                counter_summary = rows[0] if len(rows) == 1 else None
            else:
                counter_ok = not (directory / "draft-counters.json").exists()
            valid = receipt_ok and counter_ok
            repeats_valid = repeats_valid and valid
            if token_ids_valid:
                hashes.append(output_hash)
                token_rows.append(token_ids)
            repeats.append({
                "repeat": repeat, "valid": valid,
                "output_token_ids_sha256": output_hash,
                "cached_tokens": response.get("llama_cache_n"),
                "draft_counters": counter_summary,
                "receipt_sha256": RUNNER.sha256_file(receipt_path) if receipt_path.is_file() else None,
            })
        stable = len(hashes) == 3 and len(set(hashes)) == 1 and all(row == token_rows[0] for row in token_rows)
        arm_valid = argv_ok and cleanup_ok and models_ok and repeats_valid
        valid_by_arm[arm] = arm_valid
        stable_by_arm[arm] = stable
        if stable:
            tokens_by_arm[arm] = token_rows[0]
        prior_name = "control-mtp0" if route == 0 else arm
        prior_hash = manifest["failed_r1_parent"]["observed_2k_output_hashes"].get(prior_name)
        summaries.append({
            "arm": arm, "mtp": route, "valid": arm_valid,
            "within_arm_repeat_stable": stable,
            "canonical_output_token_ids_sha256": hashes[0] if stable else None,
            "matches_failed_r1_prior_observation": stable and hashes[0] == prior_hash,
            "prior_observation_is_not_an_acceptance_gate": True,
            "argv_passed": argv_ok, "models_passed": models_ok,
            "cleanup_passed": cleanup_ok, "repeats": repeats,
        })
    all_valid = all(valid_by_arm.values()) and all(checks.values())
    all_stable = all(stable_by_arm.values())
    controls_stable = stable_by_arm.get("control-mtp0a", False) and stable_by_arm.get("control-mtp0b", False)
    controls_equal = controls_stable and tokens_by_arm["control-mtp0a"] == tokens_by_arm["control-mtp0b"]
    route_comparisons: list[dict[str, Any]] = []
    if controls_equal:
        control = tokens_by_arm["control-mtp0a"]
        for route in (1, 2, 3, 4):
            arm = f"candidate-mtp{route}"
            comparison = divergence(control, tokens_by_arm[arm]) if stable_by_arm.get(arm, False) else None
            route_comparisons.append({
                "arm": arm,
                "classification": (
                    "invalid-evidence" if not valid_by_arm.get(arm, False)
                    else "within-arm-run-noise" if not stable_by_arm.get(arm, False)
                    else "exact-repeat-stable" if comparison and comparison["equal"]
                    else "deterministic-route-divergence"
                ),
                "comparison_to_bracketing_mtp0": comparison,
            })
    else:
        for route in (1, 2, 3, 4):
            arm = f"candidate-mtp{route}"
            route_comparisons.append({
                "arm": arm,
                "classification": "invalid-evidence" if not all_valid else "temporal-control-drift" if controls_stable else "within-arm-run-noise",
                "comparison_to_bracketing_mtp0": None,
            })
    if not all_valid:
        overall = "invalid-evidence"
        grade = "D"
    elif not all_stable:
        overall = "within-arm-run-noise"
        grade = "D"
    elif not controls_equal:
        overall = "temporal-control-drift"
        grade = "D"
    elif all(row["classification"] == "exact-repeat-stable" for row in route_comparisons):
        overall = "all-routes-exact-repeat-stable"
        grade = "B"
    else:
        overall = "deterministic-route-divergence"
        grade = "C"
    terminal = {
        "schema": "neural.download.qwen36-llama-mtp01234-q8kv-exact2k-classification-terminal.v1",
        "campaign_id": RUNNER.CAMPAIGN_ID,
        "status": "completed-classification-only" if all_valid else "failed-evidence-preserve",
        "overall_classification": overall,
        "packet_grade": grade,
        "checks": checks,
        "controls": {
            "opening_repeat_stable": stable_by_arm.get("control-mtp0a", False),
            "closing_repeat_stable": stable_by_arm.get("control-mtp0b", False),
            "temporally_equal": controls_equal,
            "comparison": divergence(tokens_by_arm["control-mtp0a"], tokens_by_arm["control-mtp0b"]) if controls_stable else None,
        },
        "arms": summaries,
        "route_comparisons": route_comparisons,
        "failed_r1_parent": {
            "terminal_sha256": manifest["failed_r1_parent"]["raw"]["terminal-receipt.json"],
            "identity_sha256": manifest["failed_r1_parent"]["raw"]["identity.json"],
            "prior_hashes_are_observations_not_acceptance_oracles": True,
        },
        "frozen_grade_mapping": manifest["frozen_interpretation"]["packet_grade_mapping"],
        "authority": {
            "site_cells": 0, "site_publication": False,
            "curve_expansion": False, "speed_claim": False,
            "graph_claim": False, "headline_or_protected_replacement": False,
            "localmaxxing_submission": False,
        },
    }
    return terminal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(args.root, args.manifest)
        if args.output.exists():
            raise GateError(f"create-only output exists: {args.output}")
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (GateError, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
