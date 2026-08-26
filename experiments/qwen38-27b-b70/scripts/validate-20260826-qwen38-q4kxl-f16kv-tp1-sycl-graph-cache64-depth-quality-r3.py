#!/usr/bin/env python3
"""Validate the final-capacity Q4_K_XL graph curve R3."""
from __future__ import annotations
import argparse,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; RUNNER_PATH=HERE/"run-20260826-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache64-depth-quality-r3.py"; R2V_PATH=HERE/"validate-20260826-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-r2.py"
def _load(path: Path,name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module); return module
RUNNER=_load(RUNNER_PATH,"qwen38_q4kxl_graph_curve_r3_validator_runner"); R2V=_load(R2V_PATH,"qwen38_q4kxl_graph_curve_r2_validator_base"); GateError=RUNNER.GateError
def validate(root: Path,manifest_path: Path):
    R2V.RUNNER=RUNNER; result=R2V.validate(root,manifest_path); result["schema"]="neural.download.qwen38-q4kxl-f16kv-tp1-sycl-graph-cache64-depth-quality-terminal.v3"; result["campaign_id"]=RUNNER.CAMPAIGN_ID; result["classification"]="Grade C UD-Q4_K_XL/F16-KV cache64 graph exact-depth serving curve with full Qwen3.8 quality battery" if result["status"].startswith("completed-valid-") else "invalid"; result["r3_mechanism_delta"]=RUNNER.load_overlay()["mechanism_delta"]; return result
def main() -> int:
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);p.add_argument("--manifest",type=Path,required=True);p.add_argument("--output",type=Path);a=p.parse_args()
    try:
        result=validate(a.root,a.manifest);payload=json.dumps(result,indent=2,sort_keys=True)+"\n"
        if a.output:
            with a.output.open("x",encoding="utf-8") as stream:stream.write(payload)
        print(payload,end="");return 0 if result["status"].startswith("completed-valid-") else 2
    except (GateError,KeyError,OSError,ValueError,json.JSONDecodeError) as exc:p.error(str(exc))
    return 2
if __name__=="__main__":raise SystemExit(main())
