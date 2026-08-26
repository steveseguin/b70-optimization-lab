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
    # Enter at the graph validator directly. The R2 wrapper is intentionally
    # bound to its R2-only manifest_delta and cannot validate the R3 overlay.
    R2V.R1V.RUNNER=RUNNER; result=R2V.R1V.validate(root,manifest_path)
    checks=result["checks"]; identity=json.loads((root/"identity.json").read_text(encoding="utf-8")); env=identity.get("runtime_environment") or {}
    checks.pop("graph_cache20_environment",None)
    checks["graph_cache64_environment"]=env.get("GGML_SYCL_ENABLE_GRAPH")=="1" and env.get("GGML_SYCL_GRAPH_CACHE_SIZE")=="64"
    passed=all(checks.values()); value=RUNNER.load_manifest()
    result.update({"schema":"neural.download.qwen38-q4kxl-f16kv-tp1-sycl-graph-cache64-depth-quality-terminal.v3","campaign_id":RUNNER.CAMPAIGN_ID,"status":"completed-valid-q4kxl-f16kv-graph-cache64-depth-quality" if passed else "failed-invalid-do-not-publish","classification":"Grade C UD-Q4_K_XL/F16-KV cache64 graph exact-depth serving curve with full Qwen3.8 quality battery" if passed else "invalid","authority":{"graph_q4kxl_f16_serving_curve_cells":7 if passed else 0,"target_only_selectors":value["selectors"] if passed else None,"site_graph_q4kxl_f16_curve_publication":passed,"graph_off_cells":0,"other_quantization_cells":0,"speculative_cells":0,"tp2_or_tp4_cells":0,"prefill_cells":0,"protected_or_headline_replacement":False,"localmaxxing_submission":False},"r3_mechanism_delta":RUNNER.load_overlay()["mechanism_delta"]}); return result
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
