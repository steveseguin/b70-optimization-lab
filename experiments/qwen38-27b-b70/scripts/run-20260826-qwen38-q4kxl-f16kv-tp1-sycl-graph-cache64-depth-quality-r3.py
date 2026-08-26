#!/usr/bin/env python3
"""Cache64 final-capacity wrapper for the Q4_K_XL full graph curve."""
from __future__ import annotations
import copy, importlib.util, json, re, sys
from pathlib import Path
from typing import Any

REPO=Path(__file__).resolve().parents[3]; LANE=REPO/"experiments/qwen38-27b-b70"
OVERLAY=LANE/"data/2026-08-26-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache64-depth-quality-r3-prereg.json"
R2_RUNNER=LANE/"scripts/run-20260826-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-r2.py"
VALIDATOR=LANE/"scripts/validate-20260826-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache64-depth-quality-r3.py"
CAMPAIGN_ID="qwen38-q4kxl-f16kv-tp1-sycl-graph-cache64-depth-quality-20260826-r3"; ACK=f"RUN {CAMPAIGN_ID}"; ARM="target-mtp0-graph-cache64"

def _load(path: Path,name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module); return module

R2=_load(R2_RUNNER,"qwen38_q4kxl_graph_curve_r2_for_r3"); GateError=R2.GateError
R2_VALUE=copy.deepcopy(R2.load_manifest()); R2_STATIC=R2.static_check; R2_MERGED=R2.merged_manifest

def load_json(path: Path) -> dict[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise GateError(f"JSON root must be object: {path}")
    return value

def resolve(raw: str) -> Path:
    path=Path(raw); return path if path.is_absolute() else REPO/path

def load_overlay() -> dict[str,Any]:
    value=load_json(OVERLAY); evidence=value.get("preserved_r2_evidence") or {}; delta=value.get("mechanism_delta") or {}; lifecycle=value.get("lifecycle") or {}
    expected={"requested":1182,"cache_entries":20,"cache_limit":20,"cache_hit":471,"cache_miss":711,"cache_full":691,"direct_replay":471,"recorded":20,"created":20,"updated":0,"recreated":0,"replayed":491,"compatibility_rejected":0,"device_unsupported":0}
    if not (value.get("schema")=="neural.download.qwen38-q4kxl-f16kv-tp1-sycl-graph-cache64-depth-quality-r3-overlay.v1" and value.get("campaign_id")==CAMPAIGN_ID and value.get("state")=="preregistered-not-launched" and evidence.get("graph_summary")==expected and evidence.get("seven_exact_depths_passed") is True and evidence.get("full_quality_battery_passed") is True and evidence.get("cleanup_passed") is True and evidence.get("authority_cells")==0 and evidence.get("must_remain_immutable") is True and delta=={"cache_size":{"from":20,"to":64},"source_supported_maximum":64,"evidence_basis":"cache20 recorded 20 entries then rejected 691 later requests as cache-full during the complete workload","model_runtime_binary_dso_patch_chain_change":False,"depth_quality_workload_change":False,"minimum_direct_replays":896,"no_further_capacity_escalation":True} and lifecycle=={"output_root":f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}","exact_ack":ACK,"default_is_inert":True,"requires_clean_pushed_main":True,"create_only":True}): raise GateError("Q4_K_XL cache64 R3 overlay invariant failed")
    for group in ("sealed_r2_packet","preserved_r2_evidence"):
        for name,row in value[group].items():
            if not isinstance(row,dict) or "path" not in row: continue
            path=resolve(row["path"])
            if not path.is_file() or R2.R1.sha256_file(path)!=row["sha256"]: raise GateError(f"sealed R3 dependency changed: {group}.{name}: {path}")
    text=resolve(evidence["server_log"]["path"]).read_text(encoding="utf-8",errors="replace"); matches=list(R2.R1.SUMMARY_RE.finditer(text))
    if len(matches)!=1 or {k:int(v) for k,v in matches[0].groupdict().items() if k!="device"}!=expected: raise GateError("preserved cache20 graph summary changed")
    quality=load_json(resolve(evidence["quality"]["path"])); arm=load_json(resolve(evidence["arm_result"]["path"])); terminal=load_json(resolve(evidence["terminal"]["path"]));
    if not (quality.get("pass_all") is True and arm.get("status")=="failed-preserve" and "full-curve cache20 graph evidence failed" in str(arm.get("error")) and arm.get("cleanup")==R2.EXPECTED_CLEANUP and terminal.get("status")=="failed-preserve-do-not-publish"): raise GateError("preserved R2 result changed")
    return value

def load_manifest() -> dict[str,Any]:
    overlay=load_overlay(); value=copy.deepcopy(R2_VALUE); value["campaign_id"]=CAMPAIGN_ID; value["purpose"]=overlay["purpose"]; value["selectors"]["graph_mode"]="SYCL graph cache64"; value["server_contract"]["model_alias"]="qwen38-q4kxl-f16kv-tp1-graph-cache64-depth-r3"; value["server_contract"]["graph"]="SYCL cache64"; value["execution_contract"]["arm"]=ARM; value["execution_contract"]["graph_environment"]["GGML_SYCL_GRAPH_CACHE_SIZE"]="64"; value["graph_acceptance"]["cache_limit"]=64; value["lifecycle"].update(overlay["lifecycle"]); value["r2_capacity_parent"]=copy.deepcopy(overlay["preserved_r2_evidence"]); validate_manifest(value); return value

def validate_manifest(value: dict[str,Any]) -> None:
    if not (value.get("campaign_id")==CAMPAIGN_ID and value.get("selectors",{}).get("graph_mode")=="SYCL graph cache64" and value.get("server_contract",{}).get("model_alias")=="qwen38-q4kxl-f16kv-tp1-graph-cache64-depth-r3" and value.get("server_contract",{}).get("graph")=="SYCL cache64" and value.get("execution_contract",{}).get("arm")==ARM and value.get("execution_contract",{}).get("graph_environment")=={"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"64"} and value.get("graph_acceptance",{}).get("cache_limit")==64 and value.get("graph_acceptance",{}).get("minimum_direct_replays")==896 and value.get("lifecycle",{}).get("output_root")==f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}" and value.get("lifecycle",{}).get("exact_ack")==ACK and value.get("r2_capacity_parent")==load_overlay()["preserved_r2_evidence"]): raise GateError("effective cache64 R3 manifest invariant failed")

def merged_manifest(value: dict[str,Any]) -> dict[str,Any]:
    manifest=R2_MERGED(value); manifest["environment"]["GGML_SYCL_GRAPH_CACHE_SIZE"]="64"; return manifest

def parse_graph_evidence(text: str) -> dict[str,int]:
    rows=[{k:int(v) for k,v in match.groupdict().items()} for match in R2.R1.SUMMARY_RE.finditer(text)]
    if len(rows)!=1: raise GateError(f"expected exactly one cache64 lifetime graph summary, observed {len(rows)}")
    row=rows[0]; evidence={**row,"summary_count":1}
    if not (row["device"]==0 and row["cache_limit"]==64 and row["requested"]==row["cache_hit"]+row["cache_miss"] and row["cache_hit"]==row["direct_replay"]>=896 and row["recorded"]==row["created"]==row["cache_entries"] and 1<=row["cache_entries"]<=64 and row["replayed"]==row["cache_hit"]+row["created"] and row["cache_full"]==row["cache_miss"]-row["created"] and row["requested"]==row["replayed"]+row["cache_full"] and all(row[k]==0 for k in ("compatibility_rejected","device_unsupported","updated","recreated"))): raise GateError(f"full-curve cache64 graph evidence failed: {row}")
    return evidence

def static_check(value: dict[str,Any]) -> dict[str,Any]:
    validate_manifest(value); plan=R2_STATIC(value); source=Path(R2.R1.SENTINEL_VALUE["graph_runtime"]["source_path"])/"ggml/src/ggml-sycl/ggml-sycl.cpp"
    if "std::min(g_ggml_sycl_graph_cache_size, 64)" not in source.read_text(encoding="utf-8"): raise GateError("sealed source cache maximum changed")
    plan.update({"schema":"neural.download.qwen38-q4kxl-f16kv-tp1-sycl-graph-cache64-depth-quality-r3-plan.v1","campaign_id":CAMPAIGN_ID,"exact_ack":ACK,"arm":ARM,"candidate_cache_limit":64,"minimum_direct_replays":896,"further_capacity_escalation":False}); return plan

for module in (R2,R2.R1):
    module.OVERLAY=OVERLAY; module.VALIDATOR=VALIDATOR; module.CAMPAIGN_ID=CAMPAIGN_ID; module.ACK=ACK; module.ARM=ARM; module.load_overlay=load_overlay; module.load_manifest=load_manifest; module.validate_manifest=validate_manifest; module.merged_manifest=merged_manifest; module.parse_graph_evidence=parse_graph_evidence; module.static_check=static_check

Execution=R2.Execution; EXPECTED_CLEANUP=R2.EXPECTED_CLEANUP; DEPTHS=R2.DEPTHS
# The shared target-only validator calls this through its injected runner.
# Earlier arms stopped before reaching that validator path. Translate its
# graph-overlay argument back to the sealed target-only base overlay.
def verify_base(_overlay: dict[str,Any]) -> None:
    R2.R1.BASE.verify_base(R2.R1.BASE.load_overlay())
def main() -> int: return R2.main()
if __name__=="__main__": raise SystemExit(main())
