#!/usr/bin/env python3
"""Create-only Qwen3.8 Q5_K_S + external Q4_0 MTP route sentinel."""

from __future__ import annotations
import argparse, copy, datetime as dt, importlib.util, json, os, re, subprocess, sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-25-qwen38-q5ks-external-q4mtp-q8kv-tp1-route-8k-sentinel-r1-prereg.json"
VALIDATOR = LANE / "scripts/validate-20260825-qwen38-q5ks-external-q4mtp-q8kv-tp1-route-8k-sentinel-r1.py"
BASE_RUNNER = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-r1.py"
CAMPAIGN_ID = "qwen38-q5ks-external-q4mtp-q8kv-tp1-route-8k-sentinel-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"; DEPTH = 8192; ROUTES = (0,1,2,3,4)
ARMS = {n: ("control-mtp0" if n == 0 else f"candidate-mtp{n}") for n in ROUTES}

def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module

BASE_ROUTE = load_module(BASE_RUNNER, "qwen36_q8kv_route_base_for_qwen38_q5ks")
F16, CORE, GateError = BASE_ROUTE.F16, BASE_ROUTE.CORE, BASE_ROUTE.GateError

def sha256_file(path: Path) -> str: return F16.ROUTE_R2.sha256_file(path)
def load_manifest() -> dict[str, Any]:
    value = json.loads(MANIFEST.read_text(encoding="utf-8")); validate_manifest(value); return value

def validate_manifest(v: dict[str, Any]) -> None:
    s, r, l, f = v.get("selectors") or {}, v.get("route_contract") or {}, v.get("lifecycle") or {}, v.get("frozen_interpretation") or {}
    if (v.get("server_contract") or {}).get("fit") != "off": raise GateError("Qwen3.8 route fit policy changed")
    if not (v.get("schema") == "neural.download.qwen38-q5ks-external-mtp-route-8k-sentinel-prereg.v1" and v.get("campaign_id") == CAMPAIGN_ID and v.get("state") == "preregistered-not-launched" and s == {"revision":"qwen3.8-27b-current-weights","tp":1,"route_mtp":[0,1,2,3,4],"active_context_tokens":8192,"target_kv":"q8_0","draft_kv":"q8_0","graph_mode":"off"} and r.get("arm_order") == [ARMS[n] for n in ROUTES] and r.get("fresh_server_lifetime_per_arm") is True and r.get("quality_after_route_gates") is True and l.get("output_root") == "/mnt/fast-ai/bench-results/qwen38-q5ks-external-q4mtp-q8kv-tp1-route-8k-sentinel-20260825-r1" and l.get("exact_ack") == ACK and l.get("default_is_inert") is True and f.get("speed_floor") is None and f.get("site_cells_authorized") == 0 and f.get("curve_expansion_authorized") is False): raise GateError("Qwen3.8 route manifest invariant failed")

def verify_file(row: dict[str, Any]) -> None: CORE.verify_file(Path(row["path"]), row["sha256"], row["size_bytes"])

def merged_manifest(v: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(F16.merged_manifest(F16.load_overlay()))
    merged["campaign_id"] = CAMPAIGN_ID
    merged["model"] = copy.deepcopy(v["model"])
    merged["draft_model"] = copy.deepcopy(v["draft_model"])
    merged["runtime"] = copy.deepcopy(v["runtime"])
    merged["server_contract"].update(v["server_contract"])
    merged["server_contract"].update({"cache_type_k":"q8_0","cache_type_v":"q8_0","draft_cache_type_k":"q8_0","draft_cache_type_v":"q8_0","ggml_sycl_enable_graph":"0","ggml_sycl_graph_cache_size":"0"})
    merged["lifecycle"].update(v["lifecycle"])
    merged["lifecycle"]["request_timeout_seconds"] = 900
    return merged

def static_check(v: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(v); verify_file(v["model"]); verify_file(v["draft_model"])
    for row in v["runtime"]["effective_local_shared_libraries"]: verify_file(row)
    CORE.verify_file(Path(v["runtime"]["binary"]), v["runtime"]["binary_sha256"])
    for ref in (v["artifact_manifest"], {"path":v["quality"]["helper"],"sha256":v["quality"]["helper_sha256"]}, {"path":v["fixture"]["path"],"sha256":v["fixture"]["sha256"]}):
        path = REPO / ref["path"]
        if not path.is_file() or sha256_file(path) != ref["sha256"]: raise GateError(f"bound input changed: {path}")
    fixture = json.loads((REPO / v["fixture"]["path"]).read_text())
    selected = [row for row in fixture["cases"] if row["id"] == v["fixture"]["case_id"]]
    if len(selected) != 1 or selected[0]["depth"] != DEPTH or selected[0]["prompt_token_ids_sha256"] != v["fixture"]["prompt_token_ids_sha256"]: raise GateError("8K fixture changed")
    argv = {ARMS[n]: Execution(merged_manifest(v)).server_argv_for_mtp(n) for n in ROUTES}
    return {"schema":"neural.download.qwen38-q5ks-external-mtp-route-8k-plan.v1","mode":"check","default_is_inert":True,"gpu_actions":0,"network_requests":0,"output_writes":0,"campaign_id":CAMPAIGN_ID,"exact_ack":ACK,"arms":[ARMS[n] for n in ROUTES],"fresh_server_lifetimes":5,"exact_depth":DEPTH,"quality_batteries_max":4,"site_cells_authorized":0,"server_argv":argv}

def replace_flag(argv: list[str], flag: str, value: str) -> None:
    try: argv[argv.index(flag)+1] = value
    except (ValueError, IndexError) as exc: raise GateError(f"missing inherited flag: {flag}") from exc

class Execution(BASE_ROUTE.Execution):
    def server_argv_for_mtp(self, mtp: int) -> list[str]:
        argv = super().server_argv_for_mtp(mtp)
        replace_flag(argv, "-m", self.m["model"]["path"]); replace_flag(argv, "-ctk", "q8_0"); replace_flag(argv, "-ctv", "q8_0"); replace_flag(argv, "-fit", "off")
        if mtp > 0:
            marker = argv.index("--spec-draft-n-max")
            argv[marker:marker] = ["--spec-draft-model", self.m["draft_model"]["path"]]
            replace_flag(argv, "--spec-draft-type-k", "q8_0"); replace_flag(argv, "--spec-draft-type-v", "q8_0")
        return argv

def run_quality(run: Execution, v: dict[str, Any], arm: str) -> None:
    out = run.root / arm / "quality.json"
    subprocess.run([sys.executable,"-B",str(REPO/v["quality"]["helper"]),"--base-url",f"http://127.0.0.1:{run.port}","--model",run.m["server_contract"]["model_alias"],"--tokenizer",v["quality"]["tokenizer"],"--timeout","900","--seed","1","--repeat-runs","2","--request-id-prefix",f"{CAMPAIGN_ID}-{arm}","--output-json",str(out)],cwd=REPO,check=True)

def counter_engaged(path: Path) -> bool:
    value = CORE.load_json(path); rows = value.get("new_rows")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict): return False
    accepted, generated = rows[0].get("accepted"), rows[0].get("generated")
    return bool(value.get("depth") == DEPTH and value.get("rows_after") == value.get("rows_before", -2) + 1 and type(accepted) is int and type(generated) is int and 0 < accepted <= generated)

def execute(v: dict[str, Any]) -> Path:
    validate_manifest(v); manifest = merged_manifest(v); manifest["draft_model"] = copy.deepcopy(v["draft_model"])
    unexpected = [n for n in os.environ if n.startswith(("GGML_","SYCL_","ZE_","ZES_","UR_","ONEAPI_DEVICE_SELECTOR","LLAMA_ARG_")) or n == "LD_PRELOAD"]
    if unexpected: raise GateError("unexpected inherited runtime environment: "+",".join(sorted(unexpected)))
    subprocess.run(["git","fetch","origin","main","--quiet"],cwd=REPO,check=True)
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO,text=True).strip(); origin=subprocess.check_output(["git","rev-parse","origin/main"],cwd=REPO,text=True).strip()
    if head != origin or subprocess.check_output(["git","status","--porcelain"],cwd=REPO,text=True).strip(): raise GateError("execution requires clean pushed main")
    run=Execution(manifest); run.acquire_locks(); run.require_idle()
    if run.root.exists(): raise GateError(f"create-only root exists: {run.root}")
    run.root.parent.mkdir(parents=True,exist_ok=True)
    if subprocess.check_output(["findmnt","-no","FSTYPE","--target",str(run.root.parent)],text=True).strip() != "ext4": raise GateError("run root must be ext4")
    run.root.mkdir(); current=None
    try:
        static_check(v); env=CORE.oneapi_environment(Path(v["runtime"]["binary"]).parent)
        version=subprocess.check_output([v["runtime"]["binary"],"--version"],env=env,stderr=subprocess.STDOUT,text=True).strip()
        if v["runtime"]["reported_version"] not in version.splitlines(): raise GateError("runtime version drift")
        help_text=subprocess.check_output([v["runtime"]["binary"],"--help"],env=env,stderr=subprocess.STDOUT,text=True)
        if not all(flag in help_text for flag in ("--spec-draft-model","draft-mtp","--spec-draft-type-k","--spec-draft-type-v")): raise GateError("external MTP flags unavailable")
        ldd=subprocess.check_output(["ldd",v["runtime"]["binary"]],env=env,text=True); captured=[]
        for row in v["runtime"]["effective_local_shared_libraries"]:
            match=re.search(rf"^\s*{re.escape(row['soname'])}\s+=>\s+(\S+)",ldd,re.M)
            if not match or Path(match.group(1)).resolve()!=Path(row["path"]).resolve(): raise GateError(f"ldd mismatch: {row['soname']}")
            captured.append(row)
        argv={ARMS[n]:run.server_argv_for_mtp(n) for n in ROUTES}
        CORE.write_json_x(run.root/"identity.json",{"campaign_id":CAMPAIGN_ID,"created_at_utc":dt.datetime.now(dt.UTC).isoformat(),"git_head":head,"origin_main":origin,"model":v["model"],"draft_model":v["draft_model"],"runtime":{**v["runtime"],"version":version,"ldd":ldd.splitlines(),"local_dsos":captured},"fixture":v["fixture"],"server_argv":argv,"runtime_environment":{k:env[k] for k in ("ONEAPI_DEVICE_SELECTOR","ZE_AFFINITY_MASK","GGML_SYCL_ENABLE_GRAPH","GGML_SYCL_GRAPH_CACHE_SIZE")}})
        control_hash=None
        for mtp in ROUTES:
            arm=ARMS[mtp]; current=arm; error=None; quality="not-applicable"
            try:
                run.require_idle(); run.start(arm,argv[arm],env); run.run_depth(arm,DEPTH,mtp>0)
                receipt=CORE.load_json(run.root/arm/"depth-8192/exact-depth.json"); output_hash=receipt["response"]["output_token_ids_sha256"]
                if mtp==0: control_hash=output_hash
                elif output_hash == control_hash and counter_engaged(run.root/arm/"depth-8192/draft-counters.json"):
                    run_quality(run,v,arm); quality="executed"
                else: quality="skipped-route-gate-failure"
            except BaseException as exc: error=f"{type(exc).__name__}: {exc}"
            finally: cleanup=run.stop(arm)
            clean=cleanup=={"forced_kill":False,"port_closed":True,"render_node_idle":True,"server_survivor":False}
            CORE.write_json_x(run.root/arm/"arm-result.json",{"status":"completed-awaiting-validation" if error is None and clean else "failed-preserve","error":error,"cleanup":cleanup,"quality":quality}); current=None
            if mtp==0 and (error or not clean): raise GateError("MTP0 control failed")
        terminal=run.root/"terminal-receipt.json"
        with (run.root/"validator.stdout.json").open("xb") as stdout: subprocess.run([sys.executable,"-B",str(VALIDATOR),"--root",str(run.root),"--manifest",str(MANIFEST),"--output",str(terminal)],cwd=REPO,check=True,stdout=stdout)
        return terminal
    except BaseException as exc:
        if run.proc is not None and current is not None:
            try: run.stop(current)
            except Exception: pass
        terminal=run.root/"terminal-receipt.json"
        if not terminal.exists(): CORE.write_json_x(terminal,{"campaign_id":CAMPAIGN_ID,"status":"failed-preserve","error":f"{type(exc).__name__}: {exc}","authority":{"site_cells":0,"curve_expansion":False}})
        raise

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--check",action="store_true"); p.add_argument("--execute",action="store_true"); p.add_argument("--ack",default=""); a=p.parse_args()
    try:
        v=load_manifest()
        if not a.execute: print(json.dumps(static_check(v),indent=2,sort_keys=True)); return 0
        if a.ack!=ACK: raise GateError(f"exact --ack required: {ACK}")
        print(execute(v)); return 0
    except (GateError,OSError,ValueError,json.JSONDecodeError,subprocess.SubprocessError) as exc: p.error(str(exc))
    return 2

if __name__ == "__main__": raise SystemExit(main())
