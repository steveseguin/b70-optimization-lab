#!/usr/bin/env python3
"""Validate the metadata-complete R2 Q4_K_XL graph curve."""

from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
RUNNER_PATH=HERE/"run-20260826-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-r2.py"
R1_VALIDATOR_PATH=HERE/"validate-20260826-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-r1.py"

def _load(path: Path,name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module); return module

RUNNER=_load(RUNNER_PATH,"qwen38_q4kxl_graph_curve_r2_validator_runner"); R1V=_load(R1_VALIDATOR_PATH,"qwen38_q4kxl_graph_curve_r1_validator_base"); GateError=RUNNER.GateError

def validate(root: Path,manifest_path: Path):
    R1V.RUNNER=RUNNER; result=R1V.validate(root,manifest_path); result["schema"]="neural.download.qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-terminal.v2"; result["campaign_id"]=RUNNER.CAMPAIGN_ID; result["r2_manifest_delta"]=RUNNER.load_overlay()["manifest_delta"]; return result

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--root",type=Path,required=True); parser.add_argument("--manifest",type=Path,required=True); parser.add_argument("--output",type=Path); args=parser.parse_args()
    try:
        result=validate(args.root,args.manifest); payload=json.dumps(result,indent=2,sort_keys=True)+"\n"
        if args.output:
            with args.output.open("x",encoding="utf-8") as stream: stream.write(payload)
        print(payload,end=""); return 0 if result["status"].startswith("completed-valid-") else 2
    except (GateError,KeyError,OSError,ValueError,json.JSONDecodeError) as exc: parser.error(str(exc))
    return 2
if __name__=="__main__": raise SystemExit(main())
