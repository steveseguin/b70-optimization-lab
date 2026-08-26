#!/usr/bin/env python3
"""Inert readiness check and explicit strict O_DIRECT+ordinary FP8 verifier."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

REPO=Path(__file__).resolve().parents[3]
LANE=REPO/"experiments/qwen38-27b-b70"
PREREG=LANE/"data/2026-08-26-qwen38-official-fp8-tp1-fit-depth-r1-prereg.json"
DIRECT_MANIFEST=REPO/"repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json"
BASE_VERIFIER=REPO/"repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
TARGET=Path("/mnt/usb-models/llm-models/qwen3.8-27b-fp8-official-017b9c7")
CAMPAIGN_ID="qwen38-official-fp8-tp1-fit-depth-20260826-r1"

class GateError(RuntimeError):pass

def _load(path: Path,name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:raise RuntimeError(path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

BASE=_load(BASE_VERIFIER,"qwen38_official_fp8_strict_direct_base")

def sha256_file(path: Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(4<<20),b""):digest.update(chunk)
    return digest.hexdigest()

def load_json(path: Path)->dict[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict):raise GateError(f"JSON root must be object: {path}")
    return value

def load_contract()->tuple[dict[str,Any],dict[str,Any]]:
    value=load_json(PREREG);model=value.get("model") or {};runtime=value.get("runtime") or {};execution=value.get("execution_contract") or {};failure=value.get("failure_policy") or {};publication=value.get("publication") or {};lifecycle=value.get("lifecycle") or {}
    if not (value.get("schema")=="neural.download.qwen38-official-fp8-tp1-fit-depth-prereg.v1" and value.get("campaign_id")==CAMPAIGN_ID and value.get("state")=="preregistered-not-launched-download-incomplete" and model.get("repository")=="Qwen/Qwen3.8-27B-FP8" and model.get("revision")=="017b9c7af6b5689d5dd426a76e0bc077eb5ca20a" and model.get("target_path")==str(TARGET) and model.get("download_policy","").startswith("This packet never downloads") and runtime.get("image")=="vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f" and runtime.get("vllm_version")=="0.27.2rc1.dev77+gac7509e2b" and value.get("fit_ladder")==[{"arm":"fit-8k","active_context_tokens":8192,"context_capacity_tokens":8448,"cells_if_first_success":[8192,4096,2048]},{"arm":"fit-4k","active_context_tokens":4096,"context_capacity_tokens":4352,"cells_if_first_success":[4096,2048]},{"arm":"fit-2k","active_context_tokens":2048,"context_capacity_tokens":2304,"cells_if_first_success":[2048]}] and execution.get("descending_order")==[8192,4096,2048] and execution.get("stop_after_first_success") is True and failure.get("2k_explicit_fit_failure","").startswith("Durable unsupported closure") and publication.get("protected_decode_values")==[71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144] and lifecycle.get("default_is_inert") is True and lifecycle.get("create_only") is True):raise GateError("FP8 TP1 fit preregistration invariant failed")
    refs={"direct_manifest":(DIRECT_MANIFEST,"61e3df11c49cb0dc2b7fe49ba56fe97a6a95d05732e5a52911343ecca7edc4fb"),"base_verifier":(BASE_VERIFIER,"5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9")}
    for name,(path,digest) in refs.items():
        if not path.is_file() or sha256_file(path)!=digest:raise GateError(f"sealed {name} changed: {path}")
    for name,row in runtime["audit_inputs"].items():
        path=Path(row["path"]);path=path if path.is_absolute() else REPO/path
        if not path.is_file() or sha256_file(path)!=row["sha256"]:raise GateError(f"sealed runtime audit changed: {name}: {path}")
    manifest=load_json(DIRECT_MANIFEST);errors=BASE.validate_manifest(manifest)
    if errors:raise GateError("invalid direct manifest: "+"; ".join(errors))
    files=manifest["lfs_files"]
    if len(files)!=66 or sum(row["bytes"] for row in files)!=30866866928:raise GateError("publisher weight manifest count/bytes changed")
    return value,manifest

def readiness(manifest:dict[str,Any])->dict[str,Any]:
    missing=[];wrong=[];complete=[]
    for row in manifest["lfs_files"]:
        path=TARGET/row["path"]
        if not path.is_file():missing.append(row["path"])
        elif path.stat().st_size!=row["bytes"]:wrong.append({"path":row["path"],"observed_bytes":path.stat().st_size,"expected_bytes":row["bytes"]})
        else:complete.append(row["path"])
    return {"target":str(TARGET),"expected_files":len(manifest["lfs_files"]),"expected_weight_bytes":sum(row["bytes"] for row in manifest["lfs_files"]),"complete_size_matched_files":len(complete),"missing_files":missing,"wrong_size_files":wrong,"ready_for_full_verification":not missing and not wrong}

def verify(manifest:dict[str,Any])->dict[str,Any]:
    ready=readiness(manifest)
    if not ready["ready_for_full_verification"]:raise GateError(f"model download is incomplete: {len(ready['missing_files'])} missing, {len(ready['wrong_size_files'])} wrong-size; packet will not download or hash partial files")
    direct={}
    for row in manifest["lfs_files"]:
        path=str(TARGET/row["path"])
        try:actual=BASE.hash_direct(path,"sha256")
        except BASE.DirectUnavailable as exc:raise GateError(f"strict O_DIRECT unavailable for {row['path']}: {exc}") from exc
        if actual!=row["sha256"]:raise GateError(f"O_DIRECT SHA-256 mismatch: {row['path']}")
        direct[row["path"]]=actual
    verified=[]
    for row in manifest["lfs_files"]:
        path=str(TARGET/row["path"]);actual=BASE.hash_ordinary(path,"sha256")
        if actual!=row["sha256"] or actual!=direct[row["path"]]:raise GateError(f"ordinary/O_DIRECT SHA-256 mismatch: {row['path']}")
        verified.append(row["path"])
    return {"schema":"neural.download.qwen38-official-fp8-strict-model-verification.v1","campaign_id":CAMPAIGN_ID,"status":"verified","target":str(TARGET),"revision":"017b9c7af6b5689d5dd426a76e0bc077eb5ca20a","files_verified":len(verified),"bytes_verified_each_read_path":sum(row["bytes"] for row in manifest["lfs_files"]),"direct_mode":"strict O_DIRECT; no fallback","ordinary_mode":"complete unbuffered ordinary read after all direct reads","paths_coherent":True}

def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--verify",action="store_true",help="perform the explicit full O_DIRECT and ordinary verification");args=parser.parse_args()
    try:
        value,manifest=load_contract()
        if args.verify:result=verify(manifest)
        else:result={"schema":"neural.download.qwen38-official-fp8-tp1-fit-depth-readiness.v1","campaign_id":CAMPAIGN_ID,"mode":"inert-check","gpu_actions":0,"network_actions":0,"download_actions":0,"output_writes":0,"verification_actions":0,"runtime_image":value["runtime"]["image"],"fit_ladder":value["fit_ladder"],"readiness":readiness(manifest)}
        print(json.dumps(result,indent=2,sort_keys=True));return 0
    except (GateError,OSError,ValueError,json.JSONDecodeError) as exc:parser.error(str(exc))
    return 2

if __name__=="__main__":raise SystemExit(main())
