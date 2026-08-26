#!/usr/bin/env python3
"""Create-only Qwen3.8 Q4_K_M/F16 TP1 SYCL-graph 8K mechanism sentinel."""

from __future__ import annotations
import copy, hashlib, importlib.util, json, sys
from pathlib import Path
from typing import Any

REPO=Path(__file__).resolve().parents[3]; LANE=REPO/"experiments/qwen38-27b-b70"
MANIFEST=LANE/"data/2026-08-26-qwen38-q4km-f16kv-tp1-target-sycl-graph-8k-sentinel-r1-prereg.json"
VALIDATOR=LANE/"scripts/validate-20260826-qwen38-q4km-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"
BASE_RUNNER=LANE/"scripts/run-20260826-qwen38-q5ks-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"
CAMPAIGN_ID="qwen38-q4km-f16kv-tp1-target-sycl-graph-8k-sentinel-20260826-r1"; ACK=f"RUN {CAMPAIGN_ID}"
ARMS=("control-graph-off-cache0","candidate-graph-on-cache20")

def load_module(path: Path,name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module); return module

BASE=load_module(BASE_RUNNER,"qwen38_q5_graph_sentinel_base_for_q4km")
GateError,CORE,GRAPH,EXPECTED_CLEANUP=BASE.GateError,BASE.CORE,BASE.GRAPH,BASE.EXPECTED_CLEANUP
BASE_LOAD,BASE_VALIDATE,BASE_VERIFY,BASE_STATIC,BASE_GRAPH=BASE.load_manifest,BASE.validate_manifest,BASE.verify_dependencies,BASE.static_check,BASE.graph_manifest

def sha256_file(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(4<<20),b""): digest.update(chunk)
    return digest.hexdigest()

def resolve(raw: str) -> Path:
    path=Path(raw); return path if path.is_absolute() else REPO/path

def load_json(path: Path) -> dict[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise GateError(f"JSON root must be object: {path}")
    return value

def validate_manifest(v: dict[str,Any]) -> None:
    s,e,l,f=v.get("selectors") or {},v.get("execution_contract") or {},v.get("lifecycle") or {},v.get("frozen_interpretation") or {}
    if not (v.get("schema")=="neural.download.qwen38-q4km-f16kv-target-sycl-graph-8k-sentinel-prereg.v1"
      and v.get("campaign_id")==CAMPAIGN_ID and v.get("state")=="preregistered-not-launched"
      and s=={"revision":"qwen3.8-27b-current-weights","target_quantization":"Q4_K_M","tp":1,"mtp":0,"active_context_tokens":8192,"target_kv":"f16","graph_mode":"matched-control sentinel","fit":"off","transport":"HTTP /v1/completions"}
      and e.get("arm_order")==list(ARMS) and e.get("fresh_server_lifetime_per_arm") is True and e.get("only_graph_flags_may_differ_between_arms") is True
      and e.get("control_environment_delta")=={"GGML_SYCL_ENABLE_GRAPH":"0","GGML_SYCL_GRAPH_CACHE_SIZE":"0"}
      and e.get("candidate_environment_delta")=={"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"20"}
      and e.get("cache_capacity_derivation")=="18 observed Q5 HTTP warmup/prefill graph requests plus two recurrent decode shapes from qualified same-architecture Qwen3.6 nonzero-depth evidence"
      and e.get("no_automatic_capacity_escalation") is True and e.get("require_exact_128_token_output_text_token_ids_usage_and_returned_prompt_parity") is True
      and e.get("candidate_quality_battery") is False and e.get("require_positive_graph_requests_hits_and_direct_replay") is True and e.get("require_minimum_cache_hits_and_direct_replays")==120
      and e.get("require_requested_equals_hits_plus_misses_and_replayed") is True and e.get("require_zero_graph_compatibility_device_cache_full_update_or_recreate_events") is True
      and l.get("output_root")==f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}" and l.get("exact_ack")==ACK and l.get("default_is_inert") is True and l.get("requires_clean_pushed_main") is True and l.get("create_only") is True
      and f.get("speed_floor") is None and f.get("site_cells_authorized")==0 and f.get("sentinel_pass_authorizes_full_curve_preregistration") is True and f.get("full_graph_curve_authorized") is False and f.get("failure_stops_same_design_full_curve") is True
      and f.get("graph_off_control_cells_authorized")==0 and f.get("mtp_or_speculative_cells_authorized")==0 and f.get("tp2_or_tp4_cells_authorized")==0 and f.get("prefill_cells_authorized")==0
      and f.get("headline_or_protected_replacement_authorized") is False and f.get("protected_decode_values")==[71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144]):
        raise GateError("Q4_K_M graph sentinel manifest invariant failed")

def load_manifest() -> dict[str,Any]:
    value=load_json(MANIFEST); validate_manifest(value); return value

def verify_dependencies(v: dict[str,Any]) -> None:
    for name,row in v["dependencies"].items():
        path=resolve(row["path"])
        if not path.is_file() or sha256_file(path)!=row["sha256"]: raise GateError(f"sealed dependency changed: {name}: {path}")
    off=load_json(resolve(v["dependencies"]["qwen38_graph_off_result"]["path"])); points=(off.get("exact_depth_http") or {}).get("points") or []
    q5=load_json(resolve(v["dependencies"]["qwen38_q5_negative_result"]["path"])); q36=load_json(resolve(v["dependencies"]["qwen36_q4km_graph_result"]["path"])); terminal=load_json(resolve(v["dependencies"]["qwen36_q4km_graph_terminal"]["path"])); evidence=load_json(resolve(v["dependencies"]["qwen36_q4km_graph_evidence"]["path"]))
    if not (off.get("status")=="passed" and off.get("identity",{}).get("model_sha256")==v["model"]["sha256"] and any(x.get("active_context_tokens")==8192 and x.get("status")=="passed" for x in points)):
        raise GateError("passed current-weight Q4_K_M graph-off parent invariant failed")
    q5_graph=((q5.get("arms") or {}).get("candidate_graph_on_cache8") or {}).get("graph_summary") or {}
    if not (q5.get("classification")=="correct-output-parity-but-no-graph-cache-reuse" and q5_graph.get("cache_hit")==0 and q5_graph.get("cache_full",0)>0):
        raise GateError("Q5 graph negative no longer proves full-curve expansion is blocked")
    q36_8k=evidence.get("8192") or {}
    if not (q36.get("state")=="passed-quality-covers-seven-raw-curve-cells" and terminal.get("state")=="passed-quality-prerequisite-awaiting-tracked-adjudication" and q36_8k.get("requested",0)>0 and q36_8k.get("cache_hit",0)>0 and q36_8k.get("direct_replay",0)>0 and q36_8k.get("decode_graph_classification")=="verified-capture-and-replay"):
        raise GateError("qualified same-architecture/quantization Qwen3.6 graph mechanism parent failed")

def graph_manifest(v: dict[str,Any]) -> dict[str,Any]: return BASE_GRAPH(v)

class Execution(BASE.Execution): pass

def static_check(v: dict[str,Any]) -> dict[str,Any]:
    validate_manifest(v); verify_dependencies(v)
    sealed,_,libraries=GRAPH.static_check(); runtime=v["graph_runtime"]
    if not (sealed["runtime"]["server"]["path"]==runtime["binary"] and sealed["runtime"]["server"]["sha256"]==runtime["binary_sha256"] and sealed["runtime"]["server_effective_shared_libraries"]=={"count":runtime["effective_dso_count"],"canonical_json_sha256":runtime["effective_dso_canonical_sha256"]} and [x["sha256"] for x in sealed["source"]["patch_chain_in_order"]]==runtime["patch_chain_sha256"] and len(libraries)==runtime["effective_dso_count"]):
        raise GateError("sealed graph runtime identity changed")
    source=Path(runtime["source_path"])/"ggml/src/ggml-sycl/ggml-sycl.cpp"; text=source.read_text(encoding="utf-8")
    if "std::min(g_ggml_sycl_graph_cache_size, 64)" not in text or "GGML_SYCL_Q8_MEMO_SLOTS * static_cast<size_t>(g_ggml_sycl_graph_cache_size)" not in text:
        raise GateError("sealed source no longer supports capacity-scaled cache 20")
    gm=graph_manifest(v); argv=Execution(gm).server_argv(); fixture=load_json(resolve(v["fixture"]["path"])); rows=[x for x in fixture.get("cases",[]) if x.get("id")=="depth-8192"]
    if len(rows)!=1 or rows[0].get("prompt_token_ids_sha256")!=v["fixture"]["prompt_token_ids_sha256"]: raise GateError("Qwen3.8 8K fixture changed")
    if not (argv[argv.index("-m")+1]==v["model"]["path"] and argv[argv.index("--spec-type")+1]=="none" and "--spec-draft-model" not in argv and argv[argv.index("-ctk")+1]=="f16" and argv[argv.index("-ctv")+1]=="f16" and "-fit" not in argv):
        raise GateError("effective Q4_K_M target-only graph argv invariant failed")
    return {"schema":"neural.download.qwen38-q4km-f16kv-target-sycl-graph-8k-sentinel-plan.v1","mode":"check","default_is_inert":True,"gpu_actions":0,"network_requests":0,"output_writes":0,"campaign_id":CAMPAIGN_ID,"exact_ack":ACK,"arms":list(ARMS),"fresh_server_lifetimes":2,"site_cells_if_valid":0,"full_curve_authorized":False,"curve_preregistration_if_valid":True,"server_argv":argv}

for module in (BASE,):
    module.MANIFEST=MANIFEST; module.VALIDATOR=VALIDATOR; module.CAMPAIGN_ID=CAMPAIGN_ID; module.ACK=ACK; module.ARMS=ARMS
    module.Execution=Execution; module.load_manifest=load_manifest; module.validate_manifest=validate_manifest; module.verify_dependencies=verify_dependencies; module.graph_manifest=graph_manifest; module.static_check=static_check

def main() -> int: return BASE.main()
if __name__=="__main__": raise SystemExit(main())
