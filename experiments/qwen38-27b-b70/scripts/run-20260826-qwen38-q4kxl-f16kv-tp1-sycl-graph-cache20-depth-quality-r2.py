#!/usr/bin/env python3
"""R2 metadata-complete wrapper for the Q4_K_XL cache20 graph curve."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


REPO=Path(__file__).resolve().parents[3]; LANE=REPO/"experiments/qwen38-27b-b70"
OVERLAY=LANE/"data/2026-08-26-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-r2-prereg.json"
R1_RUNNER=LANE/"scripts/run-20260826-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-r1.py"
VALIDATOR=LANE/"scripts/validate-20260826-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-r2.py"
CAMPAIGN_ID="qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-20260826-r2"; ACK=f"RUN {CAMPAIGN_ID}"


def _load(path: Path,name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module); return module


R1=_load(R1_RUNNER,"qwen38_q4kxl_graph_curve_r1_for_r2"); GateError=R1.GateError
R1_VALUE=copy.deepcopy(R1.load_manifest()); R1_CAMPAIGN_ID=R1.CAMPAIGN_ID; R1_STATIC=R1.static_check; R1_MERGED=R1.merged_manifest
GRAPH_OFF_MERGED=copy.deepcopy(R1.BASE.merged_manifest(R1.BASE_VALUE))
ZERO_CONTEXT_SEMANTICS=copy.deepcopy(GRAPH_OFF_MERGED["zero_context_semantics"])


def load_json(path: Path) -> dict[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise GateError(f"JSON root must be object: {path}")
    return value


def resolve(raw: str) -> Path:
    path=Path(raw); return path if path.is_absolute() else REPO/path


def load_overlay() -> dict[str,Any]:
    value=load_json(OVERLAY); failure=value.get("preserved_r1_failure") or {}; delta=value.get("manifest_delta") or {}; lifecycle=value.get("lifecycle") or {}
    if not (
      value.get("schema")=="neural.download.qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-r2-overlay.v1" and value.get("campaign_id")==CAMPAIGN_ID and value.get("state")=="preregistered-not-launched"
      and failure.get("exact_error")=="KeyError: 'zero_context_semantics'" and failure.get("server_started") is True and failure.get("measurement_requests_sent")==0 and failure.get("clean_shutdown") is True and failure.get("must_remain_immutable") is True
      and delta=={"add_exact_graph_off_zero_context_semantics":True,"zero_context_definition":"zero prior active context before submitting the minimal explicit prompt token","model_runtime_binary_dso_patch_chain_change":False,"server_argv_change":False,"graph_environment_change":False,"depth_quality_workload_change":False,"acceptance_or_authority_change":False}
      and lifecycle=={"output_root":f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}","exact_ack":ACK,"default_is_inert":True,"requires_clean_pushed_main":True,"create_only":True}):
        raise GateError("Q4_K_XL graph curve R2 overlay invariant failed")
    for group in ("sealed_r1_packet","preserved_r1_failure"):
        for name,row in value[group].items():
            if not isinstance(row,dict) or "path" not in row: continue
            path=resolve(row["path"])
            if not path.is_file() or R1.sha256_file(path)!=row["sha256"]: raise GateError(f"sealed R2 dependency changed: {group}.{name}: {path}")
    arm=load_json(resolve(failure["arm_result"]["path"])); terminal=load_json(resolve(failure["terminal"]["path"])); identity=load_json(resolve(failure["identity"]["path"]))
    if not (arm.get("status")=="failed-preserve" and arm.get("error")==failure["exact_error"] and arm.get("cleanup")==R1.EXPECTED_CLEANUP and terminal.get("status")=="failed-preserve-do-not-publish" and identity.get("campaign_id")==R1_CAMPAIGN_ID):
        raise GateError("preserved R1 procedural failure changed")
    return value


def load_manifest() -> dict[str,Any]:
    overlay=load_overlay(); value=copy.deepcopy(R1_VALUE); value["campaign_id"]=CAMPAIGN_ID; value["purpose"]=overlay["purpose"]; value["lifecycle"].update(overlay["lifecycle"]); value["r1_failure_parent"]=copy.deepcopy(overlay["preserved_r1_failure"]); validate_manifest(value); return value


def validate_manifest(value: dict[str,Any]) -> None:
    if not (value.get("campaign_id")==CAMPAIGN_ID and value.get("lifecycle",{}).get("output_root")==f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}" and value.get("lifecycle",{}).get("exact_ack")==ACK and value.get("r1_failure_parent")==load_overlay()["preserved_r1_failure"]): raise GateError("effective R2 manifest invariant failed")
    reconstructed=copy.deepcopy(value); reconstructed["campaign_id"]=R1_VALUE["campaign_id"]; reconstructed["purpose"]=R1_VALUE["purpose"]; reconstructed["lifecycle"]=copy.deepcopy(R1_VALUE["lifecycle"]); reconstructed.pop("r1_failure_parent")
    if reconstructed!=R1_VALUE: raise GateError("R2 changes more than metadata-complete lifecycle identity")


def merged_manifest(value: dict[str,Any]) -> dict[str,Any]:
    manifest=R1_MERGED(value)
    if "zero_context_semantics" in manifest: raise GateError("R1 unexpectedly gained zero-context semantics")
    manifest["zero_context_semantics"]=copy.deepcopy(ZERO_CONTEXT_SEMANTICS)
    return manifest


def static_check(value: dict[str,Any]) -> dict[str,Any]:
    validate_manifest(value); plan=R1_STATIC(value); merged=merged_manifest(value)
    if merged["zero_context_semantics"]!=ZERO_CONTEXT_SEMANTICS or merged["zero_context_semantics"].get("definition")!="zero prior active context before submitting the minimal explicit prompt token": raise GateError("R2 zero-context semantics changed")
    plan.update({"schema":"neural.download.qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-r2-plan.v1","campaign_id":CAMPAIGN_ID,"exact_ack":ACK,"r1_measurement_requests":0,"zero_context_semantics_added":True}); return plan


for module in (R1,):
    module.OVERLAY=OVERLAY; module.VALIDATOR=VALIDATOR; module.CAMPAIGN_ID=CAMPAIGN_ID; module.ACK=ACK; module.load_overlay=load_overlay; module.load_manifest=load_manifest; module.validate_manifest=validate_manifest; module.merged_manifest=merged_manifest; module.static_check=static_check

Execution=R1.Execution; EXPECTED_CLEANUP=R1.EXPECTED_CLEANUP; DEPTHS=R1.DEPTHS; ARM=R1.ARM


def main() -> int: return R1.main()
if __name__=="__main__": raise SystemExit(main())
