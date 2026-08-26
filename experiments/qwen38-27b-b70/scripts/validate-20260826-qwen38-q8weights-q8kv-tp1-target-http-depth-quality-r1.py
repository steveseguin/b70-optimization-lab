#!/usr/bin/env python3
"""Validate the Q8_0-weight/Q8_0-KV TP1 HTTP depth and quality packet."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


REPO = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260826-qwen38-q8weights-q8kv-tp1-target-http-depth-quality-r1.py"
DEPTH_VALIDATOR_PATH = (
    REPO
    / "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/validate-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r3.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_module(RUNNER_PATH, "qwen38_q8weights_q8kv_validator_runner")
DEPTH = load_module(DEPTH_VALIDATOR_PATH, "qwen38_q8weights_q8kv_depth_validator")
GateError = RUNNER.GateError


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"JSON root must be object: {path}")
    return value


def cached_counts(value: dict[str, Any]) -> list[int | None]:
    rows = [row for row in value.get("exact_cases", []) if isinstance(row, dict)]
    rows.extend(
        row for row in (value.get("repeat_case") or {}).get("runs", [])
        if isinstance(row, dict)
    )
    if isinstance(value.get("long_context_case"), dict):
        rows.append(value["long_context_case"])
    return [
        (((row.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens"))
        for row in rows
    ]


def validate(root: Path, manifest_path: Path) -> dict[str, Any]:
    value = RUNNER.load_manifest()
    if manifest_path.resolve() != RUNNER.OVERLAY.resolve() or load_json(manifest_path) != RUNNER.load_overlay():
        raise GateError("validator requires exact sealed Q8_0-weight/Q8_0-KV overlay")
    RUNNER.verify_base(RUNNER.load_overlay())
    identity = load_json(root / "identity.json")
    argv = RUNNER.Execution(RUNNER.merged_manifest(value)).server_argv()
    environment = identity.get("runtime_environment") or {}
    checks = {
        "manifest": value["selectors"]["target_quantization"] == "Q8_0"
        and value["selectors"]["target_kv"] == "q8_0"
        and value["selectors"]["tp"] == 1
        and value["selectors"]["mtp"] == 0,
        "identity": identity.get("campaign_id") == RUNNER.CAMPAIGN_ID
        and identity.get("git_head") == identity.get("origin_main")
        and identity.get("model") == value["model"]
        and identity.get("fixture") == value["fixture"],
        "runtime": all(
            (identity.get("runtime") or {}).get(key) == value["runtime"][key]
            for key in ("binary", "binary_sha256", "source_commit")
        )
        and (identity.get("runtime") or {}).get("local_dsos")
        == value["runtime"]["effective_local_shared_libraries"],
        "argv_exact": identity.get("server_argv") == {RUNNER.ARM: argv},
        "target_only": argv[argv.index("--spec-type") + 1] == "none"
        and "--spec-draft-model" not in argv,
        "graph_fit_off": environment.get("GGML_SYCL_ENABLE_GRAPH") == "0"
        and environment.get("GGML_SYCL_GRAPH_CACHE_SIZE") == "0"
        and argv[argv.index("-fit") + 1] == "off",
        "q8_kv": argv[argv.index("-ctk") + 1] == "q8_0"
        and argv[argv.index("-ctv") + 1] == "q8_0",
        "q8weights_model": argv[argv.index("-m") + 1] == value["model"]["path"],
        "base_bound": identity.get("parent") == value["parent"],
        "protected": value["frozen_interpretation"]["protected_decode_values"]
        == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
    }
    arm = root / RUNNER.ARM
    arm_result = load_json(arm / "arm-result.json")
    cleanup = load_json(arm / "cleanup.json")
    checks["complete"] = (
        arm_result.get("status") == "completed-awaiting-validation"
        and arm_result.get("error") is None
    )
    checks["cleanup"] = (
        cleanup == RUNNER.EXPECTED_CLEANUP
        and arm_result.get("cleanup") == RUNNER.EXPECTED_CLEANUP
    )
    checks["alias"] = any(
        isinstance(row, dict) and row.get("id") == value["server_contract"]["model_alias"]
        for row in load_json(arm / "models.json").get("data", [])
    )

    cells = []
    for depth, prompt_hash in zip(
        RUNNER.DEPTHS,
        value["fixture"]["prompt_token_ids_sha256"],
        strict=True,
    ):
        receipt = DEPTH.validate_depth_receipt(
            load_json(arm / f"depth-{depth}/exact-depth.json"),
            depth=depth,
            model=value["server_contract"]["model_alias"],
            fixture_sha=value["fixture"]["sha256"],
            prompt_sha=prompt_hash,
            capacity=value["server_contract"]["context_capacity"],
        )
        cells.append({
            "active_context_tokens": depth,
            "serving_decode_tok_s_99_interval": receipt["serving_decode_tok_s_99_interval"],
            "output_token_ids_sha256": receipt["output_token_ids_sha256"],
            "cached_tokens": receipt["cached_tokens"],
            "context_semantics": receipt.get("context_semantics", "exact submitted token depth"),
        })
    checks["seven_depths"] = [row["active_context_tokens"] for row in cells] == list(RUNNER.DEPTHS)
    checks["depth_cache_zero"] = all(row["cached_tokens"] == 0 for row in cells)

    quality = load_json(arm / "quality.json")
    cached = cached_counts(quality)
    checks["quality"] = (
        quality.get("pass_all") is True
        and quality.get("model") == value["server_contract"]["model_alias"]
        and quality.get("tokenizer") == value["clients"]["quality"]["tokenizer_path"]
        and len(quality.get("exact_cases", [])) == 7
        and all(row.get("pass") is True for row in quality.get("exact_cases", []))
        and (quality.get("repeat_case") or {}).get("repeats") == 2
        and (quality.get("repeat_case") or {}).get("pass") is True
        and (quality.get("long_context_case") or {}).get("pass") is True
        and (quality.get("long_context_case") or {}).get("requested_context_tokens")
        == value["clients"]["quality"]["long_context_tokens"]
        and len(cached) == 10
        and all(count == 0 for count in cached)
    )
    passed = all(checks.values())
    return {
        "schema": "neural.download.qwen38-q8weights-q8kv-target-http-depth-quality-terminal.v1",
        "campaign_id": RUNNER.CAMPAIGN_ID,
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "status": "completed-valid-target-only-q8weights-q8kv-depth-quality"
        if passed else "failed-invalid-do-not-publish",
        "classification": "Grade C Q8_0-weight/Q8_0-KV exact-depth serving curve with full Qwen3.8 quality battery"
        if passed else "invalid",
        "checks": checks,
        "cells": cells,
        "quality": {
            "pass_all": quality.get("pass_all") is True,
            "exact_cases": len(quality.get("exact_cases", [])),
            "repeat_runs": (quality.get("repeat_case") or {}).get("repeats"),
            "long_context_actual_prompt_tokens": (quality.get("long_context_case") or {}).get("actual_prompt_tokens"),
            "cache_zero_requests": sum(count == 0 for count in cached),
        },
        "authority": {
            "target_only_q8weights_q8kv_serving_curve_cells": 7 if passed else 0,
            "target_only_selectors": value["selectors"] if passed else None,
            "site_target_only_q8weights_q8kv_curve_publication": passed,
            "estimate_replacement_only_for_exact_same_selectors": passed,
            "f16_kv_cells": 0,
            "other_weight_quantization_cells": 0,
            "speculative_cells": 0,
            "tp2_or_tp4_cells": 0,
            "graph_cells": 0,
            "prefill_cells": 0,
            "protected_or_headline_replacement": False,
            "localmaxxing_submission": False,
        },
        "context_axis_disclosure": {
            "x0": "zero prior active context plus one explicit ordinary prompt token",
            "positive_depths": "exact submitted token counts",
            "configured_capacity_is_not_active_context": True,
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
