#!/usr/bin/env python3
"""Validate the report-corrected Q4_K_XL cache20 graph sentinel."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260826-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2.py"
R1_VALIDATOR_PATH = HERE / "validate-20260826-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = _load(RUNNER_PATH, "qwen38_q4kxl_graph_cache20_r2_validator_runner")
R1_VALIDATOR = _load(R1_VALIDATOR_PATH, "qwen38_q4kxl_graph_cache20_r1_validator_base")
GateError = RUNNER.GateError
_R1_LOAD_JSON = R1_VALIDATOR.load_json


def _load_json(path: Path):
    if path.resolve() == RUNNER.MANIFEST.resolve():
        return RUNNER.load_manifest()
    return _R1_LOAD_JSON(path)


def validate(root: Path, manifest_path: Path):
    if manifest_path.resolve() != RUNNER.MANIFEST.resolve():
        raise GateError("validator requires exact sealed R2 overlay")
    if _R1_LOAD_JSON(manifest_path) != RUNNER.load_overlay():
        raise GateError("R2 reporting overlay changed during validation")
    R1_VALIDATOR.RUNNER = RUNNER
    R1_VALIDATOR.load_json = _load_json
    result = R1_VALIDATOR.validate(root, manifest_path)
    result["schema"] = "neural.download.qwen38-q4kxl-f16kv-target-sycl-graph-cache20-8k-sentinel-terminal.v2"
    result["campaign_id"] = RUNNER.CAMPAIGN_ID
    result["classification"] = "matched-control Q4_K_XL/F16-KV graph mechanism sentinel with cache20-aware reporting"
    result["reporting_delta"] = RUNNER.load_overlay()["reporting_delta"]
    return result


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
