#!/usr/bin/env python3
"""Validate the Q8_0-weight/F16-KV cache64 graph sentinel."""
from __future__ import annotations
import argparse, datetime as dt, importlib.util, json, sys
from pathlib import Path
from typing import Any

HERE=Path(__file__).resolve().parent; RUNNER_PATH=HERE/"run-20260826-qwen38-q8weights-f16kv-tp1-target-sycl-graph-cache64-8k-sentinel-r1.py"; Q8_VALIDATOR_PATH=HERE/"validate-20260826-qwen38-q8weights-f16kv-tp1-target-http-depth-quality-r1.py"
def _load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module); return module
R=_load(RUNNER_PATH,"qwen38_q8_graph_sentinel_validator_runner"); Q8V=_load(Q8_VALIDATOR_PATH,"qwen38_q8_graph_sentinel_depth_validator"); D=Q8V.DEPTH
GateError=R.GateError
def load(path:Path)->dict[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise GateError(path)
    return value
def cached_counts(q:dict[str,Any])->list[Any]:
    rows=list(q.get("exact_cases",[]))+list((q.get("repeat_case") or {}).get("runs",[])); rows.append(q.get("long_context_case") or {})
    return [(((x.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens")) for x in rows]
def quality_signature(q:dict[str,Any])->dict[str,Any]:
    return {"exact":[(x.get("name"),x.get("sha256"),x.get("normalized"),x.get("pass")) for x in q.get("exact_cases",[])],"repeat":((q.get("repeat_case") or {}).get("pass"),(q.get("repeat_case") or {}).get("repeats"),(q.get("repeat_case") or {}).get("unique_hashes")),"long":((q.get("long_context_case") or {}).get("pass"),(q.get("long_context_case") or {}).get("sha256"),(q.get("long_context_case") or {}).get("normalized"),(q.get("long_context_case") or {}).get("actual_prompt_tokens"))}
def validate(root:Path,manifest:Path)->dict[str,Any]:
    if manifest.resolve()!=R.MANIFEST.resolve(): raise GateError("exact manifest required")
    v=R.load_manifest(); R.verify_dependencies(v); identity=load(root/"identity.json"); gm=R.graph_manifest(v); argv=R.Execution(gm).server_argv()
    checks={"identity":identity.get("campaign_id")==R.CAMPAIGN_ID and identity.get("git_head")==identity.get("origin_main") and identity.get("model")==v["model"] and identity.get("graph_runtime")==v["graph_runtime"] and identity.get("capacity_decision")==v["capacity_decision"],"target_only":argv[argv.index("--spec-type")+1]=="none" and "--spec-draft-model" not in argv,"q8_f16_fit_off":argv[argv.index("-m")+1]==v["model"]["path"] and argv[argv.index("-ctk")+1]==argv[argv.index("-ctv")+1]=="f16" and argv[argv.index("-fit")+1]=="off","arm_argv_equal":identity.get("server_argv")=={a:argv for a in R.ARMS},"only_graph_env_diff":identity.get("runtime_environment")=={R.ARMS[0]:{"ONEAPI_DEVICE_SELECTOR":"level_zero:0","GGML_SYCL_ENABLE_GRAPH":"0","GGML_SYCL_GRAPH_CACHE_SIZE":"0"},R.ARMS[1]:{"ONEAPI_DEVICE_SELECTOR":"level_zero:0","GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"64"}},"no_speed_floor":v["frozen_interpretation"]["speed_floor"] is None,"protected":v["frozen_interpretation"]["protected_decode_values"]==[71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144]}
    cells=[]; qualities=[]
    for arm in R.ARMS:
        ar=load(root/arm/"arm-result.json"); cleanup=load(root/arm/"cleanup.json"); checks[f"{arm}_complete"]=ar.get("status")=="completed-awaiting-validation" and ar.get("error") is None; checks[f"{arm}_cleanup"]=cleanup==R.EXPECTED_CLEANUP and ar.get("cleanup")==R.EXPECTED_CLEANUP
        raw=load(root/arm/"depth-8192/exact-depth.json"); receipt=D.validate_depth_receipt(raw,depth=8192,model=v["server_contract"]["model_alias"],fixture_sha=v["fixture"]["sha256"],prompt_sha=v["fixture"]["prompt_token_ids_sha256"],capacity=v["server_contract"]["context_capacity"]); cells.append({"arm":arm,"speed":receipt["serving_decode_tok_s_99_interval"],"output_token_ids_sha256":receipt["output_token_ids_sha256"],"text_sha256":raw["response"]["text_sha256"],"token_ids":raw["response"]["token_ids"],"usage":raw["response"]["usage"],"cached_tokens":receipt["cached_tokens"]})
        q=load(root/arm/"quality.json"); qualities.append(q); cached=cached_counts(q); checks[f"{arm}_quality"]=q.get("pass_all") is True and len(q.get("exact_cases",[]))==7 and all(x.get("pass") is True for x in q["exact_cases"]) and (q.get("repeat_case") or {}).get("pass") is True and (q.get("repeat_case") or {}).get("repeats")==2 and (q.get("long_context_case") or {}).get("pass") is True and len(cached)==10 and all(x==0 for x in cached)
    checks["exact_output_and_usage_parity"]=all(cells[0][k]==cells[1][k] for k in ("output_token_ids_sha256","text_sha256","token_ids","usage")); checks["depth_cache_zero"]=all(x["cached_tokens"]==0 for x in cells); checks["quality_output_parity"]=quality_signature(qualities[0])==quality_signature(qualities[1])
    graph=load(root/R.ARMS[1]/"graph-evidence.json")
    try: checks["graph_mechanism"]=graph==R.parse_graph_evidence((root/R.ARMS[1]/"server.log").read_text(encoding="utf-8",errors="replace"),v)
    except GateError: checks["graph_mechanism"]=False
    control=(root/R.ARMS[0]/"server.log").read_text(encoding="utf-8",errors="replace"); control_rows=[{k:int(x) for k,x in m.groupdict().items()} for m in R.SUMMARY_RE.finditer(control)]; action=("requested","cache_hit","cache_miss","cache_full","direct_replay","recorded","created","updated","recreated","replayed","compatibility_rejected","device_unsupported"); checks["control_graph_disabled"]=not control_rows or (len(control_rows)==1 and all(control_rows[0][k]==0 for k in action))
    passed=all(checks.values()); public=[{k:x[k] for k in ("arm","speed","output_token_ids_sha256","text_sha256","cached_tokens")} for x in cells]
    return {"schema":"neural.download.qwen38-q8weights-f16kv-graph-cache64-8k-sentinel-terminal.v1","campaign_id":R.CAMPAIGN_ID,"created_at_utc":dt.datetime.now(dt.UTC).isoformat(),"status":"completed-valid-q8weights-f16kv-graph-cache64-8k-sentinel" if passed else "failed-invalid-do-not-publish","checks":checks,"measurements":public,"graph_evidence":graph,"authority":{"site_cells":0,"full_graph_curve":False,"seven_depth_full_curve_preregistration":passed,"other_cells":0,"protected_or_headline_replacement":False,"localmaxxing_submission":False}}
def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--root",type=Path,required=True); p.add_argument("--manifest",type=Path,required=True); p.add_argument("--output",type=Path); a=p.parse_args()
    try:
        result=validate(a.root,a.manifest); payload=json.dumps(result,indent=2,sort_keys=True)+"\n"
        if a.output:
            with a.output.open("x",encoding="utf-8") as stream: stream.write(payload)
        print(payload,end=""); return 0 if result["status"].startswith("completed-valid-") else 2
    except (GateError,KeyError,OSError,ValueError,json.JSONDecodeError) as exc: p.error(str(exc))
    return 2
if __name__=="__main__": raise SystemExit(main())
