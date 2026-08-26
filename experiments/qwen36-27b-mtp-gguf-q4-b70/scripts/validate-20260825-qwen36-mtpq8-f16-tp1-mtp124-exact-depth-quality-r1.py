#!/usr/bin/env python3
"""Validate the combined embedded-Q8/F16 MTP1/2/4 depth and quality packet."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-r1.py"
R3_VALIDATOR_PATH = HERE / "validate-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r3.py"
CAMPAIGN_ID = "qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-20260825-r1"
TERMINAL_SCHEMA = "neural.download.qwen36-llama-mtp124-exact-depth-quality-terminal.v1"
DEPTHS = (0, 2048, 4096, 8192, 16384, 24576, 32768)
ROUTES = (0, 1, 2, 4)
ARMS = {0: "control-mtp0", 1: "candidate-mtp1", 2: "candidate-mtp2", 4: "candidate-mtp4"}
EXPECTED_CLEANUP = {"forced_kill": False, "port_closed": True, "render_node_idle": True, "server_survivor": False}


class GateError(RuntimeError):
    pass


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise GateError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


RUNNER = load(RUNNER_PATH, "qwen36_mtp124_runner_for_validator")
R3_VALIDATOR = load(R3_VALIDATOR_PATH, "qwen36_mtp3_r3_validator_for_mtp124")


def load_json(path: Path) -> dict[str, Any]:
    try: value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise GateError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict): raise GateError(f"{path} must contain an object")
    return value


def flag_value(argv: list[str], flag: str) -> str | None:
    try: return argv[argv.index(flag) + 1]
    except (ValueError, IndexError): return None


def validate_counter(value: dict[str, Any], depth: int) -> dict[str, Any]:
    rows = value.get("new_rows")
    row = rows[0] if isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict) else {}
    generated, accepted, ratio = row.get("generated"), row.get("accepted"), row.get("ratio")
    passed = value.get("depth") == depth and value.get("rows_after") == value.get("rows_before", -2) + 1 and type(generated) is int and type(accepted) is int and isinstance(ratio, (int, float)) and generated > 0 and 0 < accepted <= generated and math.isclose(float(ratio), accepted / generated, rel_tol=0, abs_tol=5.1e-5)
    return {"passed": passed, "generated": generated, "accepted": accepted, "ratio": ratio}


def validate_quality(value: dict[str, Any]) -> dict[str, Any]:
    counts = R3_VALIDATOR.BASE.quality_cached_counts(value)
    checks = {
        "pass_all": value.get("pass_all") is True,
        "request_count": len(counts) == 7,
        "cache_zero": len(counts) == 7 and all(count == 0 for count in counts),
        "repeat_count": value.get("repeat_case", {}).get("repeats") == 2,
        "needle": value.get("long_context_case", {}).get("requested_context_tokens") == 29400 and value.get("long_context_case", {}).get("pass") is True,
    }
    return {"passed": all(checks.values()), "checks": checks, "cached_tokens": counts}


def validate(root: Path, manifest_path: Path) -> dict[str, Any]:
    overlay = load_json(manifest_path); RUNNER.validate_overlay(overlay); RUNNER.verify_parents(overlay)
    manifest = RUNNER.merged_manifest(overlay)
    identity = load_json(root / "identity.json")
    checks: dict[str, bool] = {
        "manifest_identity": manifest.get("campaign_id") == CAMPAIGN_ID and manifest.get("selectors", {}).get("candidate_mtp") == [1, 2, 4] and manifest.get("selectors", {}).get("active_context_tokens") == list(DEPTHS),
        "primary_identity": identity.get("campaign_id") == CAMPAIGN_ID and identity.get("git_head") == identity.get("origin_main") and identity.get("model", {}).get("sha256") == manifest["model"]["sha256"] and identity.get("runtime", {}).get("binary_sha256") == manifest["runtime"]["binary_sha256"] and identity.get("runtime", {}).get("manifest_sha256") == manifest["runtime"]["manifest_sha256"] and identity.get("fixture_sha256") == manifest["fixture"]["sha256"],
        "parent_identity": identity.get("parent_hashes") == {"mtp3_r3_result": overlay["parents"]["sealed_mtp3_r3_result"]["sha256"], "route_r2_terminal": overlay["parents"]["route_screen_r2"]["raw_terminal_sha256"]},
        "runtime_dso_closure": identity.get("runtime", {}).get("local_dsos") == manifest["runtime"]["effective_local_shared_libraries"],
        "graph_off": identity.get("runtime_environment", {}).get("GGML_SYCL_ENABLE_GRAPH") == "0" and identity.get("runtime_environment", {}).get("GGML_SYCL_GRAPH_CACHE_SIZE") == "0",
        "frozen_authority": manifest["frozen_interpretation"]["site_publication_authorized"] is False and manifest["frozen_interpretation"]["graph_claim_authorized"] is False and manifest["frozen_interpretation"]["headline_or_protected_replacement_authorized"] is False,
    }
    argv_by_arm = identity.get("server_argv") if isinstance(identity.get("server_argv"), dict) else {}
    for mtp in ROUTES:
        arm = ARMS[mtp]; argv = argv_by_arm.get(arm) if isinstance(argv_by_arm.get(arm), list) else []
        common = flag_value(argv, "--alias") == manifest["server_contract"]["model_alias"] and flag_value(argv, "--port") == str(manifest["server_contract"]["port"]) and flag_value(argv, "-ctk") == flag_value(argv, "-ctv") == "f16" and flag_value(argv, "--ctx-checkpoints") == "0" and "--no-context-shift" in argv
        route = flag_value(argv, "--spec-type") == "none" if mtp == 0 else flag_value(argv, "--spec-type") == "draft-mtp" and flag_value(argv, "--spec-draft-n-max") == str(mtp) and flag_value(argv, "--spec-draft-n-min") == "0"
        checks[f"{arm}_argv"] = common and route

    prompt_hashes = manifest["fixture"]["prompt_token_ids_sha256"]
    sealed = manifest["sealed_target_output_hashes"]
    control_hashes: dict[int, str] = {}
    arm_summaries: list[dict[str, Any]] = []
    all_cleanup = True
    for mtp in ROUTES:
        arm = ARMS[mtp]; arm_root = root / arm
        for required in (arm_root / "server.log", arm_root / "cleanup.json", arm_root / "arm-result.json"):
            if not required.is_file(): raise GateError(f"missing {required}")
        cleanup = load_json(arm_root / "cleanup.json"); arm_result = load_json(arm_root / "arm-result.json")
        cleanup_passed = cleanup == EXPECTED_CLEANUP and arm_result.get("cleanup") == EXPECTED_CLEANUP
        all_cleanup = all_cleanup and cleanup_passed
        completed = arm_result.get("status") == "completed-awaiting-validation" and arm_result.get("error") is None
        models_path = arm_root / "models.json"
        models = load_json(models_path).get("data") if models_path.is_file() else None
        alias_passed = isinstance(models, list) and any(isinstance(row, dict) and row.get("id") == manifest["server_contract"]["model_alias"] for row in models)
        cells = []; cells_passed = completed and alias_passed and cleanup_passed
        for index, depth in enumerate(DEPTHS):
            receipt_path = arm_root / f"depth-{depth}" / "exact-depth.json"
            if completed and receipt_path.is_file():
                try:
                    receipt = R3_VALIDATOR.validate_depth_receipt(load_json(receipt_path), depth=depth, model=manifest["server_contract"]["model_alias"], fixture_sha=manifest["fixture"]["sha256"], prompt_sha=prompt_hashes[index], capacity=manifest["server_contract"]["context_capacity"])
                    receipt_ok = receipt["output_token_ids_sha256"] == sealed[str(depth)]
                except Exception:
                    receipt = {}; receipt_ok = False
            else: receipt = {}; receipt_ok = False
            if mtp == 0:
                parity = receipt_ok
                if receipt_ok: control_hashes[depth] = receipt["output_token_ids_sha256"]
                counter = None; draft_ok = True
            else:
                parity = receipt_ok and control_hashes.get(depth) == receipt.get("output_token_ids_sha256")
                counter_path = arm_root / f"depth-{depth}" / "draft-counters.json"
                counter = validate_counter(load_json(counter_path), depth) if completed and counter_path.is_file() else {"passed": False, "generated": None, "accepted": None, "ratio": None}
                draft_ok = counter["passed"]
            cell_passed = receipt_ok and parity and draft_ok
            cells_passed = cells_passed and cell_passed
            cells.append({"active_context_tokens": depth, "passed": cell_passed, "target_output_parity": parity, "receipt": receipt, "draft_counters": counter, "receipt_sha256": RUNNER.ROUTE_R2.sha256_file(receipt_path) if receipt_path.is_file() else None})
        if mtp == 0:
            quality = None; quality_passed = True
        else:
            quality_path = arm_root / "quality.json"
            quality = validate_quality(load_json(quality_path)) if completed and quality_path.is_file() else {"passed": False, "checks": {}, "cached_tokens": []}
            quality_passed = quality["passed"]
        passed = cells_passed and quality_passed
        arm_summaries.append({"arm": arm, "mtp": mtp, "passed": passed, "status": "passed-seven-cells-and-quality" if passed else "failed-route-local-preserve", "error": arm_result.get("error"), "cleanup_passed": cleanup_passed, "model_alias_passed": alias_passed, "cells": cells, "quality": quality})
    by_mtp = {row["mtp"]: row for row in arm_summaries}
    checks["all_arm_cleanup"] = all_cleanup
    checks["mtp0_control_all_seven"] = by_mtp[0]["passed"]
    screen_valid = all(checks.values())
    eligible = [mtp for mtp in (1, 2, 4) if screen_valid and by_mtp[mtp]["passed"]]
    return {
        "schema": TERMINAL_SCHEMA, "campaign_id": CAMPAIGN_ID, "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "status": "completed-valid-candidate-expansion-pending-review" if screen_valid else "failed-invalid-control-frame-do-not-publish",
        "screen_gate": {"passed": screen_valid, "checks": checks}, "arms": arm_summaries,
        "context_axis_disclosure": {"x0_definition": manifest["execution_contract"]["x0_definition"], "x0_physical_prompt_tokens": 1, "x0_display_active_context_tokens": 0},
        "authority": {"candidate_routes_with_seven_quality-complete_cells_if_reviewed": eligible, "family_cells_if_reviewed": {str(mtp): 7 for mtp in eligible}, "site_publication": False, "graph_claim": False, "headline_or_protected_replacement": False, "localmaxxing_submission": False, "sealed_mtp3_r3_replacement": False},
        "interpretation": "Each listed route has seven exact parity/conservation/cache-zero cells plus its own passed quality battery; separate tracked ingestion remains required." if screen_valid else "The fresh MTP0 control or shared identity failed; no candidate cell has authority.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", required=True, type=Path); parser.add_argument("--manifest", required=True, type=Path); parser.add_argument("--output", type=Path); args = parser.parse_args()
    try:
        result = validate(args.root, args.manifest)
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream: json.dump(result, stream, indent=2, sort_keys=True); stream.write("\n")
        print(json.dumps(result, indent=2, sort_keys=True)); return 0 if result["screen_gate"]["passed"] else 2
    except (GateError, KeyError, OSError, ValueError, ZeroDivisionError) as exc: parser.error(str(exc))
    return 2


if __name__ == "__main__": raise SystemExit(main())
