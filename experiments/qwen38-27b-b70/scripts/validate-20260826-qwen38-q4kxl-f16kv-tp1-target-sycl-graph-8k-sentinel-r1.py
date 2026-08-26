#!/usr/bin/env python3
"""Validate the Qwen3.8 Q4_K_XL/F16 TP1 HTTP SYCL-graph 8K sentinel."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
RUNNER_PATH = Path(__file__).with_name(
    "run-20260826-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"
)
DEPTH_VALIDATOR_PATH = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/validate-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r3.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_module(RUNNER_PATH, "qwen38_q4kxl_graph_sentinel_validator_runner")
DEPTH = load_module(DEPTH_VALIDATOR_PATH, "qwen38_q4kxl_graph_sentinel_depth_validator")
GateError = RUNNER.GateError


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"JSON root must be object: {path}")
    return value


def validate(root: Path, manifest_path: Path) -> dict[str, Any]:
    value = load_json(manifest_path)
    if manifest_path.resolve() != RUNNER.MANIFEST.resolve():
        raise GateError("validator requires exact sealed Q4_K_XL sentinel manifest")
    RUNNER.validate_manifest(value)
    RUNNER.verify_dependencies(value)
    graph_manifest = RUNNER.graph_manifest(value)
    identity = load_json(root / "identity.json")
    argv = RUNNER.Execution(graph_manifest).server_argv()
    checks = {
        "identity": identity.get("campaign_id") == RUNNER.CAMPAIGN_ID
        and identity.get("git_head") == identity.get("origin_main")
        and identity.get("model") == value["model"]
        and identity.get("graph_runtime") == value["graph_runtime"],
        "q4kxl_identity": value["model"]["quantization"] == "UD-Q4_K_XL"
        and argv[argv.index("-m") + 1] == value["model"]["path"],
        "target_only": argv[argv.index("--spec-type") + 1] == "none" and "--spec-draft-model" not in argv,
        "f16_kv": argv[argv.index("-ctk") + 1] == "f16" and argv[argv.index("-ctv") + 1] == "f16",
        "fit_off": "-fit" not in argv,
        "arm_argv_equal": identity.get("server_argv") == {arm: argv for arm in RUNNER.ARMS},
        "only_graph_env_diff": identity.get("runtime_environment")
        == {
            RUNNER.ARMS[0]: {
                "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
                "GGML_SYCL_ENABLE_GRAPH": "0",
                "GGML_SYCL_GRAPH_CACHE_SIZE": "0",
            },
            RUNNER.ARMS[1]: {
                "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
                "GGML_SYCL_ENABLE_GRAPH": "1",
                "GGML_SYCL_GRAPH_CACHE_SIZE": "20",
            },
        },
        "protected_values_immutable": value["frozen_interpretation"]["protected_decode_values"]
        == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        "no_speed_floor": value["frozen_interpretation"]["speed_floor"] is None,
    }
    cells = []
    for arm in RUNNER.ARMS:
        arm_root = root / arm
        result = load_json(arm_root / "arm-result.json")
        cleanup = load_json(arm_root / "cleanup.json")
        checks[f"{arm}_complete"] = result.get("status") == "completed-awaiting-validation" and result.get("error") is None
        checks[f"{arm}_cleanup"] = cleanup == RUNNER.EXPECTED_CLEANUP and result.get("cleanup") == RUNNER.EXPECTED_CLEANUP
        raw = load_json(arm_root / "depth-8192/exact-depth.json")
        receipt = DEPTH.validate_depth_receipt(
            raw,
            depth=8192,
            model=value["server_contract"]["model_alias"],
            fixture_sha=value["fixture"]["sha256"],
            prompt_sha=value["fixture"]["prompt_token_ids_sha256"],
            capacity=value["server_contract"]["context_capacity"],
        )
        cells.append(
            {
                "arm": arm,
                "serving_decode_tok_s_99_interval": receipt["serving_decode_tok_s_99_interval"],
                "output_token_ids_sha256": receipt["output_token_ids_sha256"],
                "text_sha256": raw["response"]["text_sha256"],
                "cached_tokens": receipt["cached_tokens"],
                "token_ids": raw["response"]["token_ids"],
                "usage": raw["response"]["usage"],
                "returned_prompt_token_ids_sha256": raw["response"]["returned_prompt_token_ids_sha256"],
            }
        )
    parity_keys = (
        "output_token_ids_sha256",
        "text_sha256",
        "token_ids",
        "usage",
        "returned_prompt_token_ids_sha256",
    )
    checks["exact_output_text_tokens_usage_and_prompt_parity"] = all(
        cells[0][key] == cells[1][key] for key in parity_keys
    )
    checks["depth_cache_zero"] = all(cell["cached_tokens"] == 0 for cell in cells)
    control_text = (root / RUNNER.ARMS[0] / "server.log").read_text(encoding="utf-8", errors="replace")
    control_rows = [
        {key: int(item) for key, item in match.groupdict().items()}
        for match in RUNNER.GRAPH.CURVE.R1.SUMMARY_RE.finditer(control_text)
    ]
    action_keys = (
        "requested", "cache_hit", "cache_miss", "cache_full", "direct_replay",
        "recorded", "created", "updated", "recreated", "replayed",
        "compatibility_rejected", "device_unsupported",
    )
    checks["control_graph_disabled"] = not control_rows or (
        len(control_rows) == 1 and all(control_rows[0][key] == 0 for key in action_keys)
    )
    graph = load_json(root / RUNNER.ARMS[1] / "graph-evidence.json")
    checks["graph_mechanism_engaged_and_reused"] = (
        graph.get("summary_count") == 1
        and graph.get("requested", 0) > 0
        and graph.get("cache_hit", 0) >= 120
        and graph.get("direct_replay", 0) >= 120
        and graph.get("requested") == graph.get("cache_hit", 0) + graph.get("cache_miss", 0)
        and graph.get("requested") == graph.get("replayed")
        and graph.get("cache_hit") == graph.get("direct_replay")
        and graph.get("cache_miss") == graph.get("recorded") == graph.get("created")
        and 1 <= graph.get("cache_entries", 0) <= 20
        and graph.get("cache_limit") == 20
        and all(
            graph.get(key) == 0
            for key in ("cache_full", "compatibility_rejected", "device_unsupported", "updated", "recreated")
        )
    )
    passed = all(checks.values())
    public_cells = [{key: item for key, item in cell.items() if key != "token_ids"} for cell in cells]
    return {
        "schema": "neural.download.qwen38-q4kxl-f16kv-target-sycl-graph-8k-sentinel-terminal.v1",
        "campaign_id": RUNNER.CAMPAIGN_ID,
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "status": "completed-valid-target-only-q4kxl-graph-8k-sentinel" if passed else "failed-invalid-do-not-publish",
        "classification": "matched-control Q4_K_XL/F16-KV graph mechanism sentinel" if passed else "invalid",
        "checks": checks,
        "measurements": public_cells,
        "control_graph_summary_count": len(control_rows),
        "graph_evidence": graph,
        "authority": {
            "site_cells": 0,
            "selectors": value["selectors"] if passed else None,
            "full_graph_curve": False,
            "full_curve_preregistration": passed,
            "failure_stops_same_design_full_curve": not passed,
            "mtp_or_speculative_cells": 0,
            "tp2_or_tp4_cells": 0,
            "prefill_cells": 0,
            "protected_or_headline_replacement": False,
            "localmaxxing_submission": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.root, args.manifest)
        payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(payload)
        print(payload, end="")
        return 0 if result["status"].startswith("completed-valid-") else 2
    except (GateError, KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
