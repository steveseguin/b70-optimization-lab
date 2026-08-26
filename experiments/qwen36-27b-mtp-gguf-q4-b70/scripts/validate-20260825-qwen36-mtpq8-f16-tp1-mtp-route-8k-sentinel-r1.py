#!/usr/bin/env python3
"""Validate the exact-8K embedded-Q8/F16 graph-off MTP route screen."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any


CAMPAIGN_ID = "qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-20260825-r1"
MANIFEST_SCHEMA = "neural.download.qwen36-llama-mtp-route-8k-sentinel-prereg.v1"
TERMINAL_SCHEMA = "neural.download.qwen36-llama-mtp-route-8k-sentinel-terminal.v1"
RECEIPT_SCHEMA = "openai-token-depth-benchmark-v1"
DEPTH = 8192
ROUTES = (0, 1, 2, 3, 4)
ARMS = {
    0: "control-mtp0",
    1: "candidate-mtp1",
    2: "candidate-mtp2",
    3: "positive-control-mtp3",
    4: "candidate-mtp4",
}
EXPECTED_CLEANUP = {
    "forced_kill": False,
    "port_closed": True,
    "render_node_idle": True,
    "server_survivor": False,
}
RUNNER_PATH = Path(__file__).resolve().parent / "run-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r1.py"


class GateError(RuntimeError):
    pass


def load_runner():
    spec = importlib.util.spec_from_file_location("qwen36_mtpq8_mtp_route_screen_runner_for_validator", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise GateError("cannot import route-screen runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GateError(f"{path} must contain a JSON object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def flag_value(argv: list[str], flag: str) -> str | None:
    try:
        return argv[argv.index(flag) + 1]
    except (ValueError, IndexError):
        return None


def validate_receipt(value: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    identity = value.get("run_identity") or {}
    fixture = value.get("fixture") or {}
    metric = value.get("metric_window") or {}
    response = value.get("response") or {}
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), dict) else {}
    output_hash = response.get("output_token_ids_sha256")
    parent = manifest["parent_r3"]
    checks = {
        "schema": value.get("schema") == RECEIPT_SCHEMA,
        "status": value.get("status") == "passed" and value.get("gate", {}).get("passed") is True,
        "model": identity.get("model") == manifest["server_contract"]["model_alias"],
        "depth": identity.get("depth") == DEPTH and identity.get("active_context_tokens") == DEPTH,
        "capacity": identity.get("configured_context_capacity") == manifest["server_contract"]["context_capacity"],
        "case": identity.get("case_id") == "depth-8192",
        "shape": identity.get("max_tokens") == 128 and identity.get("metric_events") == 100 and identity.get("metric_intervals") == 99,
        "fixture": fixture.get("fixture_sha256") == manifest["fixture"]["sha256"]
        and fixture.get("prompt_token_ids_sha256") == manifest["fixture"]["prompt_token_ids_sha256"][3],
        "metric": metric.get("timestamped_events") == 100
        and metric.get("inter_token_intervals") == 99
        and isinstance(metric.get("conventional_99_interval_tok_s"), (int, float))
        and math.isfinite(float(metric.get("conventional_99_interval_tok_s", 0)))
        and float(metric.get("conventional_99_interval_tok_s", 0)) > 0,
        "cache_zero": details.get("cached_tokens") == 0,
        "completion_tokens": usage.get("completion_tokens") == 128,
        "output_hash": isinstance(output_hash, str) and len(output_hash) == 64,
        "parent_target_hash": output_hash == parent["required_8k_output_token_ids_sha256"],
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "serving_decode_tok_s_99_interval": metric.get("conventional_99_interval_tok_s"),
        "output_token_ids_sha256": output_hash,
        "cached_tokens": details.get("cached_tokens"),
    }


def validate_counter(value: dict[str, Any], depth: int) -> dict[str, Any]:
    new_rows = value.get("new_rows")
    row = new_rows[0] if isinstance(new_rows, list) and len(new_rows) == 1 and isinstance(new_rows[0], dict) else {}
    generated, accepted, ratio = row.get("generated"), row.get("accepted"), row.get("ratio")
    conserved = (
        value.get("depth") == depth
        and value.get("rows_after") == value.get("rows_before", -2) + 1
        and type(generated) is int
        and type(accepted) is int
        and isinstance(ratio, (int, float))
        and generated > 0
        and 0 < accepted <= generated
        and math.isclose(float(ratio), accepted / generated, rel_tol=0, abs_tol=5.1e-5)
    )
    return {"passed": conserved, "generated": generated, "accepted": accepted, "ratio": ratio}


def validate(root: Path, manifest_path: Path) -> dict[str, Any]:
    overlay = load_json(manifest_path)
    runner = load_runner()
    runner.validate_overlay(overlay)
    manifest = runner.merged_manifest(overlay)
    selectors = manifest.get("selectors") or {}
    server = manifest.get("server_contract") or {}
    frozen = manifest.get("frozen_interpretation") or {}
    checks: dict[str, bool] = {
        "manifest_identity": manifest.get("schema") == MANIFEST_SCHEMA
        and manifest.get("campaign_id") == CAMPAIGN_ID
        and manifest.get("state") == "preregistered-not-launched"
        and selectors.get("active_context_tokens") == DEPTH
        and selectors.get("route_mtp") == list(ROUTES)
        and selectors.get("target_kv") == selectors.get("draft_kv") == "f16"
        and selectors.get("graph_mode") == "off",
        "frozen_authority": frozen.get("speed_floor") is None
        and frozen.get("site_publication_authorized") is False
        and frozen.get("headline_or_protected_replacement_authorized") is False
        and frozen.get("successful_r3_or_protected_speed_replacement_authorized") is False,
    }
    identity_path = root / "identity.json"
    if not identity_path.is_file():
        raise GateError("missing identity.json")
    identity = load_json(identity_path)
    checks["primary_identity"] = (
        identity.get("campaign_id") == CAMPAIGN_ID
        and identity.get("git_head") == identity.get("origin_main")
        and identity.get("parent_r3_terminal_receipt_sha256") == manifest["parent_r3"]["terminal_receipt_sha256"]
        and identity.get("fixture_sha256") == manifest["fixture"]["sha256"]
        and identity.get("fixture_8k_prompt_token_ids_sha256") == manifest["fixture"]["prompt_token_ids_sha256"][3]
        and identity.get("model", {}).get("sha256") == manifest["model"]["sha256"]
        and identity.get("runtime", {}).get("binary_sha256") == manifest["runtime"]["binary_sha256"]
        and identity.get("runtime", {}).get("manifest_sha256") == manifest["runtime"]["manifest_sha256"]
    )
    checks["runtime_dso_closure"] = identity.get("runtime", {}).get("local_dsos") == manifest["runtime"]["effective_local_shared_libraries"]
    env = identity.get("runtime_environment") or {}
    checks["graph_off"] = env.get("GGML_SYCL_ENABLE_GRAPH") == "0" and env.get("GGML_SYCL_GRAPH_CACHE_SIZE") == "0"
    argv_by_arm = identity.get("server_argv") if isinstance(identity.get("server_argv"), dict) else {}
    for mtp in ROUTES:
        arm = ARMS[mtp]
        argv = argv_by_arm.get(arm) if isinstance(argv_by_arm.get(arm), list) else []
        common = (
            flag_value(argv, "--alias") == server["model_alias"]
            and flag_value(argv, "--port") == str(server["port"])
            and flag_value(argv, "-c") == str(server["context_capacity"])
            and flag_value(argv, "-ctk") == flag_value(argv, "-ctv") == "f16"
            and flag_value(argv, "--ctx-checkpoints") == "0"
            and "--no-context-shift" in argv
            and "--no-kv-unified" in argv
        )
        if mtp == 0:
            route_ok = flag_value(argv, "--spec-type") == "none"
        else:
            route_ok = (
                flag_value(argv, "--spec-type") == "draft-mtp"
                and flag_value(argv, "--spec-draft-n-max") == str(mtp)
                and flag_value(argv, "--spec-draft-n-min") == "0"
                and flag_value(argv, "--spec-draft-type-k") == flag_value(argv, "--spec-draft-type-v") == "f16"
            )
        checks[f"{arm}_argv"] = common and route_ok

    arm_summaries: list[dict[str, Any]] = []
    control_hash: str | None = None
    structural_cleanup = True
    for mtp in ROUTES:
        arm = ARMS[mtp]
        arm_root = root / arm
        required_base = [arm_root / "server.log", arm_root / "cleanup.json", arm_root / "arm-result.json"]
        if not all(path.is_file() for path in required_base):
            raise GateError(f"missing base artifacts for {arm}")
        cleanup = load_json(arm_root / "cleanup.json")
        arm_result = load_json(arm_root / "arm-result.json")
        models_path = arm_root / "models.json"
        models = load_json(models_path).get("data") if models_path.is_file() else None
        alias_passed = isinstance(models, list) and any(
            isinstance(row, dict) and row.get("id") == server["model_alias"] for row in models
        )
        cleanup_passed = cleanup == EXPECTED_CLEANUP and arm_result.get("cleanup") == EXPECTED_CLEANUP
        structural_cleanup = structural_cleanup and cleanup_passed
        receipt_path = arm_root / f"depth-{DEPTH}" / "exact-depth.json"
        completed = arm_result.get("status") == "completed-awaiting-validation" and arm_result.get("error") is None
        receipt = validate_receipt(load_json(receipt_path), manifest) if completed and receipt_path.is_file() else {
            "passed": False,
            "checks": {},
            "serving_decode_tok_s_99_interval": None,
            "output_token_ids_sha256": None,
            "cached_tokens": None,
        }
        if mtp == 0:
            counter = None
            control_hash = receipt["output_token_ids_sha256"] if receipt["passed"] else None
            parity = receipt["passed"]
            draft = True
        else:
            counter_path = arm_root / f"depth-{DEPTH}" / "draft-counters.json"
            counter = validate_counter(load_json(counter_path), DEPTH) if completed and counter_path.is_file() else {
                "passed": False, "generated": None, "accepted": None, "ratio": None,
            }
            parity = receipt["passed"] and control_hash is not None and receipt["output_token_ids_sha256"] == control_hash
            draft = counter["passed"]
        passed = completed and alias_passed and cleanup_passed and receipt["passed"] and parity and draft
        arm_summaries.append({
            "arm": arm,
            "mtp": mtp,
            "status": "passed-route-gates" if passed else "failed-route-gates",
            "passed": passed,
            "error": arm_result.get("error"),
            "model_alias_passed": alias_passed,
            "cleanup_passed": cleanup_passed,
            "target_output_parity": parity,
            "receipt": receipt,
            "draft_counters": counter,
            "receipt_sha256": sha256_file(receipt_path) if receipt_path.is_file() else None,
        })
    by_mtp = {row["mtp"]: row for row in arm_summaries}
    checks["all_arm_cleanup"] = structural_cleanup
    checks["mtp0_target_control"] = by_mtp[0]["passed"]
    checks["mtp3_positive_control"] = by_mtp[3]["passed"]
    screen_valid = all(checks.values())
    eligible = [mtp for mtp in (1, 2, 4) if screen_valid and by_mtp[mtp]["passed"]]
    status = "completed-valid-route-screen-pending-review" if screen_valid else "failed-invalid-route-screen-do-not-expand"
    return {
        "schema": TERMINAL_SCHEMA,
        "campaign_id": CAMPAIGN_ID,
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "status": status,
        "screen_gate": {"passed": screen_valid, "checks": checks},
        "measurement_class": "HTTP serving exact-8K route sentinel; conventional 99-interval streamed token-ID decode",
        "speed_floor": None,
        "arms": arm_summaries,
        "authority": {
            "candidate_routes_eligible_for_separately_preregistered_curve": eligible,
            "curve_expansion_depths": manifest["frozen_interpretation"]["curve_expansion_depths_if_eligible"] if eligible else [],
            "site_publication": False,
            "headline_or_protected_replacement": False,
            "localmaxxing_submission": False,
            "successful_r3_replacement": False,
        },
        "interpretation": "Only listed candidate routes may proceed to separately preregistered seven-depth curves; preserve every negative arm and keep successful R3/protected speeds unchanged." if screen_valid else "The MTP0/MTP3 control frame or shared identity failed; no route may expand.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.root, args.manifest)
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, indent=2, sort_keys=True)
                stream.write("\n")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["screen_gate"]["passed"] else 2
    except (GateError, KeyError, OSError, ValueError, ZeroDivisionError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
