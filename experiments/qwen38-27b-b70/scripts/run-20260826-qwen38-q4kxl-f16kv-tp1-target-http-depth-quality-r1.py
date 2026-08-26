#!/usr/bin/env python3
"""Create-only UD-Q4_K_XL/F16-KV sibling of the passed Q5_K_S HTTP curve."""

from __future__ import annotations
import copy, hashlib, importlib.util, json, sys
from pathlib import Path
from typing import Any

REPO=Path(__file__).resolve().parents[3]; LANE=REPO/"experiments/qwen38-27b-b70"
OVERLAY=LANE/"data/2026-08-26-qwen38-q4kxl-f16kv-tp1-target-http-depth-quality-r1-prereg.json"
BASE_RUNNER=LANE/"scripts/run-20260826-qwen38-q5ks-f16kv-tp1-target-http-depth-quality-r1.py"
VALIDATOR=LANE/"scripts/validate-20260826-qwen38-q4kxl-f16kv-tp1-target-http-depth-quality-r1.py"
CAMPAIGN_ID="qwen38-q4kxl-f16kv-tp1-target-http-depth-quality-20260826-r1"; ACK=f"RUN {CAMPAIGN_ID}"
DEPTHS=(0,2048,4096,8192,16384,24576,32768); ARM="target-mtp0"

def load_module(path: Path,name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module); return module

BASE=load_module(BASE_RUNNER,"qwen38_q5ks_f16_base_for_q4kxl")
GateError,CORE,EXPECTED_CLEANUP=BASE.GateError,BASE.CORE,BASE.EXPECTED_CLEANUP
BASE_LOAD=BASE.load_manifest; BASE_EXECUTION=BASE.Execution; BASE_VALUE=copy.deepcopy(BASE_LOAD())

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

def load_overlay() -> dict[str,Any]:
    v=load_json(OVERLAY); s=v.get("selectors") or {}; e=v.get("execution_contract") or {}; l=v.get("lifecycle") or {}; f=v.get("frozen_interpretation") or {}
    if not (v.get("schema")=="neural.download.qwen38-q4kxl-f16kv-target-http-depth-quality-sibling-prereg.v1" and v.get("campaign_id")==CAMPAIGN_ID and v.get("state")=="preregistered-not-launched"
      and s=={"revision":"qwen3.8-27b-current-weights","target_quantization":"UD-Q4_K_XL","tp":1,"mtp":0,"active_context_tokens":list(DEPTHS),"target_kv":"f16","graph_mode":"off","fit":"off","transport":"HTTP /v1/completions"}
      and e.get("arm")==ARM and e.get("depth_order")==list(DEPTHS) and e.get("quality_after_all_depths") is True and e.get("require_q5_f16_base_passed") is True
      and l=={"output_root":f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}","exact_ack":ACK,"default_is_inert":True,"requires_clean_pushed_main":True,"create_only":True}
      and f.get("speed_floor") is None and f.get("target_only_q4kxl_f16_serving_curve_cells_if_all_gates_pass")==7 and f.get("other_quantization_cells_authorized")==0
      and f.get("speculative_cells_authorized")==0 and f.get("tp2_or_tp4_cells_authorized")==0 and f.get("graph_cells_authorized")==0 and f.get("prefill_cells_authorized")==0
      and f.get("headline_or_protected_replacement_authorized") is False and f.get("protected_decode_values")==[71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144]):
        raise GateError("UD-Q4_K_XL/F16 sibling overlay invariant failed")
    return v

def verify_base(v: dict[str,Any]) -> None:
    for key in ("manifest","runner","validator","result","terminal"):
        path=resolve(v["base"][key])
        if not path.is_file() or sha256_file(path)!=v["base"][f"{key}_sha256"]: raise GateError(f"sealed Q5/F16 base changed: {path}")
    terminal=load_json(resolve(v["base"]["terminal"])); result=load_json(resolve(v["base"]["result"]))
    if terminal.get("status")!=v["base"]["required_status"] or result.get("status")!="passed" or (terminal.get("authority") or {}).get("target_only_f16_serving_curve_cells")!=7: raise GateError("passed Q5/F16 base invariant failed")
    raw=resolve(v["existing_raw_evidence"]["path"])
    if not raw.is_file() or sha256_file(raw)!=v["existing_raw_evidence"]["sha256"]: raise GateError("UD-Q4_K_XL raw evidence changed")
    evidence=load_json(raw)
    variant=(evidence.get("variants") or {}).get(v["existing_raw_evidence"]["variant"]) or {}
    if evidence.get("depths")!=list(DEPTHS) or variant.get("file")!="Qwen3.8-27B-UD-Q4_K_XL.gguf" or variant.get("sha256_16")!=v["model"]["sha256"][:16] or len(variant.get("decode_tg128",[]))!=7: raise GateError("UD-Q4_K_XL F16 raw identity failed")

def load_manifest() -> dict[str,Any]:
    overlay=load_overlay(); verify_base(overlay); value=copy.deepcopy(BASE_VALUE)
    value.update({"schema":"neural.download.qwen38-q4kxl-f16kv-target-http-depth-quality-prereg.v1","campaign_id":CAMPAIGN_ID,"state":"preregistered-not-launched","purpose":overlay["purpose"],"model":copy.deepcopy(overlay["model"]),"parent":copy.deepcopy(overlay["base"]),"existing_raw_evidence":copy.deepcopy(overlay["existing_raw_evidence"]),"selectors":copy.deepcopy(overlay["selectors"]),"execution_contract":copy.deepcopy(overlay["execution_contract"]),"frozen_interpretation":copy.deepcopy(overlay["frozen_interpretation"])})
    value["server_contract"].update(overlay["server_contract"]); value["lifecycle"].update(overlay["lifecycle"]); validate_manifest(value); return value

def validate_manifest(v: dict[str,Any]) -> None:
    o=load_overlay()
    if not (v.get("campaign_id")==CAMPAIGN_ID and v.get("model")==o["model"] and v.get("selectors")==o["selectors"] and v.get("execution_contract")==o["execution_contract"] and v.get("frozen_interpretation")==o["frozen_interpretation"] and v.get("server_contract",{}).get("cache_type_k")=="f16" and v.get("server_contract",{}).get("cache_type_v")=="f16" and v.get("server_contract",{}).get("spec_type")=="none"):
        raise GateError("effective UD-Q4_K_XL/F16 manifest invariant failed")

def merged_manifest(v: dict[str,Any]) -> dict[str,Any]: return BASE.merged_manifest(v)

class Execution(BASE_EXECUTION): pass

def static_check(v: dict[str,Any]) -> dict[str,Any]:
    validate_manifest(v); verify_base(load_overlay())
    pristine=load_module(BASE_RUNNER,"qwen38_q5ks_f16_pristine_for_q4kxl_static")
    pristine.static_check(pristine.load_manifest())
    model=Path(v["model"]["path"])
    if not model.is_file() or model.is_symlink() or model.stat().st_size!=v["model"]["size_bytes"]: raise GateError("UD-Q4_K_XL model path/size failed; full hash is execute-only")
    argv=Execution(merged_manifest(v)).server_argv()
    if not (argv[argv.index("-m")+1]==v["model"]["path"] and argv[argv.index("--spec-type")+1]=="none" and "--spec-draft-model" not in argv and argv[argv.index("-ctk")+1]=="f16" and argv[argv.index("-ctv")+1]=="f16" and argv[argv.index("-fit")+1]=="off"):
        raise GateError("effective UD-Q4_K_XL target-only argv invariant failed")
    return {"schema":"neural.download.qwen38-q4kxl-f16kv-target-http-depth-quality-plan.v1","mode":"check","default_is_inert":True,"gpu_actions":0,"network_requests":0,"output_writes":0,"campaign_id":CAMPAIGN_ID,"exact_ack":ACK,"arm":ARM,"fresh_server_lifetimes":1,"depths":list(DEPTHS),"quality_batteries":1,"target_only_q4kxl_f16_cells_if_valid":7,"server_argv":argv}

# Reuse the audited Q5/F16 create-only lifecycle with this sealed model sibling.
for module in (BASE,BASE.BASE):
    module.OVERLAY=OVERLAY; module.MANIFEST=OVERLAY; module.VALIDATOR=VALIDATOR; module.CAMPAIGN_ID=CAMPAIGN_ID; module.ACK=ACK; module.DEPTHS=DEPTHS; module.ARM=ARM; module.Execution=Execution; module.load_manifest=load_manifest; module.validate_manifest=validate_manifest; module.static_check=static_check

def main() -> int: return BASE.main()
if __name__=="__main__": raise SystemExit(main())
