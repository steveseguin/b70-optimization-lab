#!/usr/bin/env python3
"""Validate Qwen3.8 Q5_K_S external-MTP exact-8K route sentinel."""
from __future__ import annotations
import argparse, datetime as dt, importlib.util, json, math, sys
from pathlib import Path
from typing import Any

HERE=Path(__file__).resolve().parent
RUNNER_PATH=HERE/"run-20260825-qwen38-q5ks-external-q4mtp-q8kv-tp1-route-8k-sentinel-r1.py"
R3V_PATH=Path(__file__).resolve().parents[3]/"experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/validate-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r3.py"
EXPECTED_CLEANUP={"forced_kill":False,"port_closed":True,"render_node_idle":True,"server_survivor":False}

def load(path: Path,name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
RUNNER=load(RUNNER_PATH,"qwen38_q5ks_external_mtp_route_validator_runner")
R3V=load(R3V_PATH,"qwen38_q5ks_external_mtp_depth_validator")
GateError=RUNNER.GateError

def load_json(path: Path)->dict[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise GateError(str(path))
    return value
def flag(argv:list[str],name:str)->str|None:
    try:return argv[argv.index(name)+1]
    except (ValueError,IndexError):return None
def cached_counts(q:dict[str,Any])->list[int|None]:
    rows=[r for r in q.get("exact_cases",[]) if isinstance(r,dict)]
    repeat=q.get("repeat_case") or {}; rows += [r for r in repeat.get("runs",[]) if isinstance(r,dict)]
    long=q.get("long_context_case"); rows += [long] if isinstance(long,dict) else []
    return [((r.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens") for r in rows]
def counter_ok(v:dict[str,Any])->bool:
    rows=v.get("new_rows"); row=rows[0] if isinstance(rows,list) and len(rows)==1 and isinstance(rows[0],dict) else {}
    a,g,ratio=row.get("accepted"),row.get("generated"),row.get("ratio")
    return bool(v.get("depth")==8192 and v.get("rows_after")==v.get("rows_before",-2)+1 and type(a) is int and type(g) is int and isinstance(ratio,(int,float)) and 0<a<=g and math.isclose(float(ratio),a/g,abs_tol=5.1e-5,rel_tol=0))

def validate(root:Path,manifest_path:Path)->dict[str,Any]:
    v=load_json(manifest_path);RUNNER.validate_manifest(v);m=RUNNER.merged_manifest(v);m["draft_model"]=v["draft_model"]
    identity=load_json(root/"identity.json"); execution=RUNNER.Execution(m); argv_expected={RUNNER.ARMS[n]:execution.server_argv_for_mtp(n) for n in RUNNER.ROUTES}
    checks={
      "manifest":v["selectors"]["graph_mode"]=="off" and v["selectors"]["target_kv"]==v["selectors"]["draft_kv"]=="q8_0",
      "identity":identity.get("campaign_id")==RUNNER.CAMPAIGN_ID and identity.get("git_head")==identity.get("origin_main") and identity.get("model")==v["model"] and identity.get("draft_model")==v["draft_model"],
      "runtime":all((identity.get("runtime") or {}).get(k)==v["runtime"][k] for k in ("binary","binary_sha256","source_commit")) and (identity.get("runtime") or {}).get("local_dsos")==v["runtime"]["effective_local_shared_libraries"],
      "argv_exact":identity.get("server_argv")==argv_expected,
      "graph_off":(identity.get("runtime_environment") or {}).get("GGML_SYCL_ENABLE_GRAPH")=="0" and (identity.get("runtime_environment") or {}).get("GGML_SYCL_GRAPH_CACHE_SIZE")=="0",
      "authority":v["frozen_interpretation"]["site_cells_authorized"]==0 and v["frozen_interpretation"]["curve_expansion_authorized"] is False,
    }
    summaries=[];control_hash=None;control_pass=False
    for mtp in RUNNER.ROUTES:
      arm=RUNNER.ARMS[mtp];ar=root/arm;result=load_json(ar/"arm-result.json");cleanup=load_json(ar/"cleanup.json")
      completed=result.get("status")=="completed-awaiting-validation" and result.get("error") is None
      clean=cleanup==EXPECTED_CLEANUP and result.get("cleanup")==EXPECTED_CLEANUP
      models=load_json(ar/"models.json").get("data",[]);alias=any(isinstance(row,dict) and row.get("id")==m["server_contract"]["model_alias"] for row in models)
      receipt_path=ar/"depth-8192/exact-depth.json"
      try: receipt=R3V.validate_depth_receipt(load_json(receipt_path),depth=8192,model=m["server_contract"]["model_alias"],fixture_sha=v["fixture"]["sha256"],prompt_sha=v["fixture"]["prompt_token_ids_sha256"],capacity=m["server_contract"]["context_capacity"])
      except Exception: receipt={}
      output_hash=receipt.get("output_token_ids_sha256")
      if mtp==0:
        control_hash=output_hash; parity=isinstance(control_hash,str); draft=True; quality=True
      else:
        parity=isinstance(control_hash,str) and output_hash==control_hash
        cp=ar/"depth-8192/draft-counters.json";draft=cp.is_file() and counter_ok(load_json(cp))
        qp=ar/"quality.json";q=load_json(qp) if qp.is_file() else {};counts=cached_counts(q)
        quality=q.get("pass_all") is True and len(q.get("exact_cases",[]))==7 and (q.get("repeat_case") or {}).get("repeats")==2 and len(counts)==10 and all(x==0 for x in counts)
      passed=completed and clean and alias and bool(receipt) and parity and draft and quality
      if mtp==0:control_pass=passed
      summaries.append({"arm":arm,"mtp":mtp,"passed":passed,"exact_target_parity":parity,"draft_counters_passed":draft,"quality_passed":quality,"cleanup_passed":clean,"output_token_ids_sha256":output_hash})
    shared=all(checks.values()) and control_pass
    eligible=[row["mtp"] for row in summaries if row["mtp"]>0 and shared and row["passed"]]
    return {"schema":"neural.download.qwen38-q5ks-external-mtp-route-8k-terminal.v1","campaign_id":RUNNER.CAMPAIGN_ID,"created_at_utc":dt.datetime.now(dt.UTC).isoformat(),"status":"completed-valid-route-screen-pending-review" if shared else "failed-invalid-control-frame-do-not-expand","checks":checks,"arms":summaries,"authority":{"routes_eligible_for_separate_preregistration":eligible,"site_cells":0,"site_publication":False,"curve_expansion":False,"speed_claim":False,"headline_or_protected_replacement":False,"localmaxxing_submission":False}}

def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);p.add_argument("--manifest",type=Path,required=True);p.add_argument("--output",type=Path);a=p.parse_args()
 try:
  result=validate(a.root,a.manifest);payload=json.dumps(result,indent=2,sort_keys=True)+"\n"
  if a.output:
   with a.output.open("x",encoding="utf-8") as out:out.write(payload)
  print(payload,end="");return 0 if result["status"]=="completed-valid-route-screen-pending-review" else 2
 except (GateError,KeyError,OSError,ValueError,json.JSONDecodeError) as exc:p.error(str(exc))
 return 2
if __name__=="__main__":raise SystemExit(main())
