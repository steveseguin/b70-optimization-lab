#!/usr/bin/env python3
"""R3 validator with explicit zero-prior-context/minimal-token disclosure."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
R3_RUNNER = HERE / "run-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r3.py"


spec = importlib.util.spec_from_file_location("qwen36_mtp3_r3_runner_for_validator", R3_RUNNER)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot import R3 runner")
R3 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = R3
spec.loader.exec_module(R3)

v2_spec = importlib.util.spec_from_file_location("qwen36_mtp3_r2_validator_for_r3", R3.R2_VALIDATOR)
if v2_spec is None or v2_spec.loader is None:
    raise RuntimeError("cannot import R2 validator")
V2 = importlib.util.module_from_spec(v2_spec)
sys.modules[v2_spec.name] = V2
v2_spec.loader.exec_module(V2)
BASE = V2.BASE
ORIGINAL_LOAD_JSON = BASE.load_json
ORIGINAL_VALIDATE_DEPTH = BASE.validate_depth_receipt
ORIGINAL_VALIDATE = BASE.validate
BASE.CAMPAIGN_ID = R3.CAMPAIGN_ID


def load_json(path: Path):
    if Path(path).resolve() == R3.OVERLAY.resolve():
        value = R3.load_overlay(); R3.verify_references(value)
        return R3.merge_manifest(value)
    return ORIGINAL_LOAD_JSON(path)


def validate_depth_receipt(value: dict[str, Any], *, depth: int, model: str,
                           fixture_sha: str, prompt_sha: str, capacity: int) -> dict[str, Any]:
    if depth != 0:
        return ORIGINAL_VALIDATE_DEPTH(value, depth=depth, model=model, fixture_sha=fixture_sha, prompt_sha=prompt_sha, capacity=capacity)
    identity, fixture = value.get("run_identity") or {}, value.get("fixture") or {}
    metric, response, gate = value.get("metric_window") or {}, value.get("response") or {}, value.get("gate") or {}
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), dict) else {}
    output_hash = response.get("output_token_ids_sha256")
    checks = {
        "schema": value.get("schema") == R3.ZERO_RECEIPT_SCHEMA,
        "status": value.get("status") == "passed" and gate.get("passed") is True,
        "model": identity.get("model") == model,
        "zero_prior_context": identity.get("display_context_axis_tokens") == 0 and identity.get("prior_active_context_tokens") == 0,
        "minimal_request": identity.get("submitted_prompt_tokens") == 1 and usage.get("prompt_tokens") == 1,
        "capacity": identity.get("configured_context_capacity") == capacity,
        "shape": identity.get("max_tokens") == 128 and identity.get("metric_events") == 100 and identity.get("metric_intervals") == 99,
        "fixture": fixture.get("fixture_sha256") == fixture_sha and fixture.get("original_depth_zero_prompt_token_ids_sha256") == prompt_sha,
        "explicit_token": fixture.get("minimal_explicit_prompt_token_id") == R3.ZERO_TOKEN_ID and fixture.get("minimal_explicit_prompt_token_ids_sha256") == R3.ZERO_TOKEN_HASH,
        "cache_zero": details.get("cached_tokens") == 0,
        "metric": metric.get("timestamped_events") == 100 and metric.get("inter_token_intervals") == 99 and isinstance(metric.get("conventional_99_interval_tok_s"), (int, float)) and math.isfinite(float(metric.get("conventional_99_interval_tok_s", 0))) and float(metric.get("conventional_99_interval_tok_s", 0)) > 0,
        "output_hash": isinstance(output_hash, str) and len(output_hash) == 64,
        "disclosure": value.get("context_semantics", {}).get("literal_empty_prompt") is False and value.get("context_semantics", {}).get("raw_engine_zero_token_invocation") is False,
    }
    if not all(checks.values()):
        raise BASE.GateError(f"zero-prior-context receipt invariant failed: {checks}")
    return {"depth": 0, "serving_decode_tok_s_99_interval": float(metric["conventional_99_interval_tok_s"]),
            "output_token_ids_sha256": output_hash, "cached_tokens": 0,
            "context_semantics": "zero prior active context plus one explicit ordinary prompt token",
            "usage_prompt_tokens": 1}


def validate(root: Path, manifest_path: Path):
    result = ORIGINAL_VALIDATE(root, manifest_path)
    result["context_axis_disclosure"] = {
        "x0_definition": "zero prior active context plus one explicit ordinary prompt token",
        "x0_usage_prompt_tokens": 1,
        "x0_literal_empty_prompt": False,
        "positive_depths_exact_and_unchanged": [2048, 4096, 8192, 16384, 24576, 32768],
        "site_disclosure_required": True,
    }
    return result


BASE.load_json = load_json
BASE.validate_depth_receipt = validate_depth_receipt
BASE.validate = validate


def main() -> int:
    R3.verify_references(R3.load_overlay())
    return BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())
