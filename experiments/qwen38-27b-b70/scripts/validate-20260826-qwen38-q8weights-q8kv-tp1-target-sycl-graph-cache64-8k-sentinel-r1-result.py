#!/usr/bin/env python3
"""Validate the compact Q8/Q8-KV graph sentinel negative against raw hashes."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any

REPO=Path(__file__).resolve().parents[3]
RESULT=REPO/"experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q8weights-q8kv-tp1-target-sycl-graph-cache64-8k-sentinel-r1-result.json"
CAMPAIGN_ID="qwen38-q8weights-q8kv-tp1-target-sycl-graph-cache64-8k-sentinel-20260826-r1"
EXPECTED_CLEANUP={"forced_kill":False,"port_closed":True,"render_node_idle":True,"server_survivor":False}
PROTECTED=[71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144]

class SealError(RuntimeError): pass
def load(path:Path)->dict[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise SealError(f"JSON root must be object: {path}")
    return value
def sha256_file(path:Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(4<<20),b""): digest.update(chunk)
    return digest.hexdigest()
def resolve(raw:str)->Path:
    path=Path(raw); return path if path.is_absolute() else REPO/path
def require(condition:bool,message:str)->None:
    if not condition: raise SealError(message)

def validate(result_path:Path)->dict[str,Any]:
    require(result_path.resolve()==RESULT.resolve(),"exact result path required")
    value=load(result_path); authority=value.get("frozen_authority") or {}; raw=value.get("raw_artifacts") or {}
    require(value.get("schema")=="neural.download.qwen38-q8weights-q8kv-graph-cache64-8k-sentinel-negative.v1" and value.get("campaign_id")==CAMPAIGN_ID and value.get("status")=="failed-closed","negative result identity changed")
    require(authority=={"site_cells":0,"performance_cells":0,"full_q8kv_graph_curve_design_closed":True,"seven_depth_q8kv_graph_curve_authorized":False,"graph_off_q8kv_curve_changed":False,"f16_kv_paths_changed":False,"protected_or_headline_replacement":False,"localmaxxing_submission":False,"protected_decode_values":PROTECTED},"frozen authority changed")
    prereg=value["preregistration"]; prereg_path=resolve(prereg["path"]); require(prereg_path.is_file() and sha256_file(prereg_path)==prereg["sha256"],"preregistration changed")

    root=Path(raw["root"]); expected=raw["files"]
    observed={str(path.relative_to(root)):path for path in root.rglob("*") if path.is_file()}
    require(raw.get("file_count")==18 and set(observed)==set(expected),"raw file inventory changed")
    for relative,row in expected.items():
        path=observed[relative]; require(path.stat().st_size==row["bytes"],f"raw byte size changed: {relative}"); require(sha256_file(path)==row["sha256"],f"raw hash changed: {relative}")
    for relative in raw["missing_by_design_or_failure"]: require(not (root/relative).exists(),f"failed-run absence changed: {relative}")

    identity=load(root/"identity.json"); expected_identity=value["identity"]
    require(identity.get("campaign_id")==CAMPAIGN_ID and identity.get("git_head")==identity.get("origin_main")==expected_identity["git_head"],"raw Git identity changed")
    require((identity.get("model") or {}).get("sha256")==expected_identity["model_sha256"] and (identity.get("graph_runtime") or {}).get("binary_sha256")==expected_identity["graph_runtime_binary_sha256"] and (identity.get("graph_runtime") or {}).get("graph_backend_sha256")==expected_identity["graph_backend_sha256"],"raw model/runtime identity changed")
    argv=(identity.get("server_argv") or {}).get("candidate-graph-on-cache64") or []
    require(argv[argv.index("-ctk")+1]==argv[argv.index("-ctv")+1]=="q8_0" and argv[argv.index("-fit")+1]=="off" and argv[argv.index("--spec-type")+1]=="none","raw selectors changed")
    require(identity.get("runtime_environment")=={"candidate-graph-on-cache64":{"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"64","ONEAPI_DEVICE_SELECTOR":"level_zero:0"},"control-graph-off-cache0":{"GGML_SYCL_ENABLE_GRAPH":"0","GGML_SYCL_GRAPH_CACHE_SIZE":"0","ONEAPI_DEVICE_SELECTOR":"level_zero:0"}},"matched arm delta changed")

    control=load(root/"control-graph-off-cache0/depth-8192/exact-depth.json"); candidate=load(root/"candidate-graph-on-cache64/depth-8192/exact-depth.json"); left=control["response"]; right=candidate["response"]; matched=value["matched_8k"]
    require((control.get("gate") or {}).get("passed") is True and (candidate.get("gate") or {}).get("passed") is True,"8K gate no longer passes")
    require(left.get("token_ids")==right.get("token_ids") and left.get("output_token_ids_sha256")==right.get("output_token_ids_sha256")==matched["parity"]["output_token_ids_sha256"] and left.get("text_sha256")==right.get("text_sha256")==matched["parity"]["text_sha256"] and left.get("usage")==right.get("usage")==matched["parity"]["usage"] and left.get("returned_prompt_token_ids_sha256")==right.get("returned_prompt_token_ids_sha256"),"8K exact parity changed")
    require(control["metric_window"]["conventional_99_interval_tok_s"]==matched["control_graph_off_cache0"]["serving_decode_tok_s_99_interval"] and candidate["metric_window"]["conventional_99_interval_tok_s"]==matched["candidate_graph_on_cache64"]["serving_decode_tok_s_99_interval"],"8K diagnostic speed changed")

    quality=load(root/"control-graph-off-cache0/quality.json"); cached=[x["usage"]["prompt_tokens_details"]["cached_tokens"] for x in quality["exact_cases"]]+[x["usage"]["prompt_tokens_details"]["cached_tokens"] for x in quality["repeat_case"]["runs"]]+[quality["long_context_case"]["usage"]["prompt_tokens_details"]["cached_tokens"]]
    require(quality.get("pass_all") is True and len(quality["exact_cases"])==7 and all(x.get("pass") is True for x in quality["exact_cases"]) and quality["repeat_case"].get("pass") is True and quality["repeat_case"].get("repeats")==2 and quality["long_context_case"].get("pass") is True and quality["long_context_case"].get("requested_context_tokens")==27200 and len(cached)==10 and all(x==0 for x in cached),"control full quality changed")

    control_arm=load(root/"control-graph-off-cache0/arm-result.json"); candidate_arm=load(root/"candidate-graph-on-cache64/arm-result.json")
    require(control_arm=={"cleanup":EXPECTED_CLEANUP,"error":None,"status":"completed-awaiting-validation"},"control arm result changed")
    require(candidate_arm.get("status")=="failed-preserve" and candidate_arm.get("cleanup")==EXPECTED_CLEANUP and "returned non-zero exit status 1" in (candidate_arm.get("error") or ""),"candidate arm result changed")
    require(load(root/"control-graph-off-cache0/cleanup.json")==EXPECTED_CLEANUP and load(root/"candidate-graph-on-cache64/cleanup.json")==EXPECTED_CLEANUP,"cleanup changed")
    server=(root/"candidate-graph-on-cache64/server.log").read_text(encoding="utf-8",errors="replace"); stderr=(root/"candidate-graph-on-cache64/quality.stderr.log").read_text(encoding="utf-8",errors="replace")
    markers=("wait cannot be called for a queue which is recording to a command graph.","CHECK_TRY_ERROR(qptr->wait())","in function ensure_half","fattn-buffers.cpp:23","ggml_sycl_flash_attn_ext_mma","ggml_backend_sycl_graph_compute_impl")
    require(all(marker in server for marker in markers),"candidate crash signature changed")
    require("run_long_context_case" in stderr and "http.client.RemoteDisconnected: Remote end closed connection without response" in stderr,"candidate client failure changed")
    require("n_tokens = 25212" in server and "n_tokens =   8192, progress = 0.32" in server,"long-context failure stage changed")
    require("[SYCL-GRAPH] summary" not in server,"candidate unexpectedly gained terminal graph summary")
    return {"schema":"neural.download.qwen38-q8weights-q8kv-graph-cache64-8k-negative-seal-validation.v1","status":"passed-negative-seal","campaign_id":CAMPAIGN_ID,"raw_file_count":len(observed),"raw_hashes_validated":len(expected),"exact_8k_parity":True,"control_full_quality":True,"candidate_long_context_command_graph_crash":True,"cleanup_valid":True,"terminal_receipt_absent":True,"site_cells":0,"performance_cells":0,"full_curve_design_closed":True}

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--result",type=Path,default=RESULT); args=parser.parse_args()
    try: print(json.dumps(validate(args.result),indent=2,sort_keys=True)); return 0
    except (SealError,KeyError,IndexError,OSError,ValueError,json.JSONDecodeError) as exc: parser.error(str(exc))
    return 2
if __name__=="__main__": raise SystemExit(main())
