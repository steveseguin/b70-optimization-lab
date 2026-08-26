#!/usr/bin/env python3
"""Validate the Q4_K_XL/F16 TP1 cache20 graph depth/quality curve."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260826-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-r1.py"
OFF_VALIDATOR_PATH = HERE / "validate-20260826-qwen38-q4kxl-f16kv-tp1-target-http-depth-quality-r1.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


RUNNER = _load(RUNNER_PATH,"qwen38_q4kxl_graph_curve_validator_runner")
OFF = _load(OFF_VALIDATOR_PATH,"qwen38_q4kxl_graph_off_validator_base")
GateError = RUNNER.GateError


def load_json(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict):
        raise GateError(f"JSON root must be object: {path}")
    return value


def validate(root: Path, manifest_path: Path):
    if manifest_path.resolve() != RUNNER.OVERLAY.resolve() or load_json(manifest_path) != RUNNER.load_overlay():
        raise GateError("validator requires exact sealed graph curve overlay")
    OFF.RUNNER = RUNNER
    result = OFF.validate(root,manifest_path)
    checks = result["checks"]
    identity = load_json(root/"identity.json")
    env = identity.get("runtime_environment") or {}
    value = RUNNER.load_manifest()
    argv = RUNNER.Execution(RUNNER.merged_manifest(value)).server_argv()
    checks.pop("graph_fit_off")
    checks["fit_off"] = argv[argv.index("-fit")+1] == "off"
    checks["graph_cache20_environment"] = env.get("GGML_SYCL_ENABLE_GRAPH") == "1" and env.get("GGML_SYCL_GRAPH_CACHE_SIZE") == "20"
    checks["graph_parent_bound"] = identity.get("graph_parent") == value["graph_parent"]
    graph = load_json(root/RUNNER.ARM/"graph-evidence.json")
    try:
        parsed = RUNNER.parse_graph_evidence((root/RUNNER.ARM/"server.log").read_text(encoding="utf-8",errors="replace"))
        checks["graph_mechanism"] = graph == parsed
    except GateError:
        checks["graph_mechanism"] = False
    passed = all(checks.values())
    result.update({"schema":"neural.download.qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-terminal.v1","campaign_id":RUNNER.CAMPAIGN_ID,"status":"completed-valid-q4kxl-f16kv-graph-cache20-depth-quality" if passed else "failed-invalid-do-not-publish","classification":"Grade C UD-Q4_K_XL/F16-KV cache20 graph exact-depth serving curve with full Qwen3.8 quality battery" if passed else "invalid","graph_evidence":graph,"authority":{"graph_q4kxl_f16_serving_curve_cells":7 if passed else 0,"target_only_selectors":value["selectors"] if passed else None,"site_graph_q4kxl_f16_curve_publication":passed,"graph_off_cells":0,"other_quantization_cells":0,"speculative_cells":0,"tp2_or_tp4_cells":0,"prefill_cells":0,"protected_or_headline_replacement":False,"localmaxxing_submission":False}})
    return result


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--root",type=Path,required=True); parser.add_argument("--manifest",type=Path,required=True); parser.add_argument("--output",type=Path); args=parser.parse_args()
    try:
        result=validate(args.root,args.manifest); payload=json.dumps(result,indent=2,sort_keys=True)+"\n"
        if args.output:
            with args.output.open("x",encoding="utf-8") as stream: stream.write(payload)
        print(payload,end=""); return 0 if result["status"].startswith("completed-valid-") else 2
    except (GateError,KeyError,OSError,ValueError,json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
