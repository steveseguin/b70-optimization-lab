#!/usr/bin/env python3
"""Validate the b2dd/1e90 AutoRound INT4 TP2 exact-depth/quality packet."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


RUNNER_PATH = Path(__file__).with_name("run-20260826-qwen38-b2dd9ce73d-tp2-exact-depth-quality-r1.py")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_module(RUNNER_PATH, "qwen38_b2dd_tp2_exact_depth_validator_runner")
CampaignError = RUNNER.CampaignError


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CampaignError(f"JSON root must be object: {path}")
    return value


def validate(root: Path, manifest_path: Path) -> dict[str, Any]:
    if manifest_path.resolve() != RUNNER.MANIFEST.resolve():
        raise CampaignError("validator requires exact sealed TP2 manifest")
    manifest = load_json(manifest_path)
    RUNNER.verify_dependencies()
    stage = load_json(root / "stage-receipt.json")
    if stage.get("output") != str(root):
        raise CampaignError("stage receipt root mismatch")
    launch_head = stage.get("lab_git_head")
    cache = Path(stage.get("cache", ""))
    identity = RUNNER.verify_exact_run_identity(root, launch_head=launch_head, expected_cache=cache)
    depth = RUNNER.BASE.exact_depth_gate(root)
    quality_passed, quality = RUNNER.COMMON.full_quality_passes(load_json(root / "quality.json"))
    graph = RUNNER.BASE.graph_capture_gate(root)
    canary = load_json(root / "canary.json")
    final_status = (root / "final.status").read_text(encoding="utf-8").strip()
    gates = stage.get("gates") or {}
    exact_rows = depth.get("rows") or []
    cached = [((row.get("response") or {}).get("usage") or {}).get("prompt_tokens_details", {}).get("cached_tokens") for row in exact_rows]
    checks = {
        "manifest": manifest.get("campaign_id") == RUNNER.CAMPAIGN_ID
        and (manifest.get("frozen_interpretation") or {}).get("speed_floor") is None,
        "stage_terminal_pass": stage.get("state") == "passed"
        and stage.get("terminal") is True
        and stage.get("receipt_complete") is True,
        "identity": identity.get("passed") is True
        and identity.get("tp") == 2
        and identity.get("worker_ranks") == [0, 1],
        "six_exact_depths": depth.get("passed") is True
        and depth.get("passed_depths") == list(RUNNER.DEPTHS)
        and len(exact_rows) == 6,
        "depth_cache_zero": len(cached) == 6 and all(item == 0 for item in cached),
        "depth_zero_missing": depth.get("depth_zero_state") == "missing",
        "configured_capacity_not_cell": (manifest.get("exact_depth_contract") or {}).get("configured_capacity_is_not_active_context") is True,
        "canary": canary.get("content") == "14" and canary.get("cached_tokens") == 0,
        "full_quality": quality_passed is True
        and quality.get("exact_count") == 7
        and quality.get("repeat_count") == 8
        and quality.get("baseline_comparison_count") == 24
        and quality.get("baseline_match_all") is True
        and quality.get("cached_count") == 16
        and quality.get("cached_zero_count") == 16,
        "graph_capture": graph.get("passed") is True,
        "runner_final_pass": final_status == "pass",
        "cleanup": gates.get("post_cleanup_passed") is True,
        "git_unchanged": gates.get("local_lab_unchanged") is True,
        "narrow_authority": (stage.get("authority") or {}) == {
            "nonzero_exact_context_cells": 6,
            "depth_zero_cells": 0,
            "other_cells": 0,
            "protected_or_headline_replacement": False,
            "localmaxxing_submission": False,
        },
        "protected_values": (manifest.get("frozen_interpretation") or {}).get("protected_decode_values")
        == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        "parent_does_not_claim_qualification": (manifest.get("identity_parent") or {}).get("state") == "preregistered-not-launched",
    }
    passed = all(checks.values())
    cells = []
    for row in exact_rows:
        response = row.get("response") or {}
        window = row.get("metric_window") or {}
        cells.append({
            "active_context_tokens": row.get("depth"),
            "serving_decode_tok_s_99_interval": window.get("conventional_99_interval_tok_s"),
            "output_token_ids_sha256": response.get("output_token_ids_sha256"),
            "cached_tokens": ((response.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens"),
        })
    return {
        "schema": "neural.download.qwen38-b2dd-tp2-exact-depth-quality-terminal.v1",
        "campaign_id": RUNNER.CAMPAIGN_ID,
        "status": "completed-valid-six-nonzero-exact-context-cells" if passed else "failed-invalid-do-not-publish",
        "checks": checks,
        "cells": cells,
        "depth_zero": {"state": "missing", "configured_capacity_is_not_active_context": True},
        "authority": {"nonzero_exact_context_cells": 6 if passed else 0, "depth_zero_cells": 0, "other_cells": 0, "protected_or_headline_replacement": False, "localmaxxing_submission": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(args.root, args.manifest)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"].startswith("completed-valid-") else 2
    except (CampaignError, KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
