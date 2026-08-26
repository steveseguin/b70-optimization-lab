#!/usr/bin/env python3
"""Create-only Q8_0-weight/F16-KV TP1 cache64 graph mechanism sentinel."""

from __future__ import annotations
import argparse, copy, datetime as dt, hashlib, importlib.util, json, os, re, subprocess, sys
from pathlib import Path
from typing import Any

REPO=Path(__file__).resolve().parents[3]; LANE=REPO/"experiments/qwen38-27b-b70"
MANIFEST=LANE/"data/2026-08-26-qwen38-q8weights-f16kv-tp1-target-sycl-graph-cache64-8k-sentinel-r1-prereg.json"
VALIDATOR=LANE/"scripts/validate-20260826-qwen38-q8weights-f16kv-tp1-target-sycl-graph-cache64-8k-sentinel-r1.py"
Q8_RUNNER=LANE/"scripts/run-20260826-qwen38-q8weights-f16kv-tp1-target-http-depth-quality-r1.py"
GRAPH_RUNNER=LANE/"scripts/run-20260826-qwen38-q5ks-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"
CAMPAIGN_ID="qwen38-q8weights-f16kv-tp1-target-sycl-graph-cache64-8k-sentinel-20260826-r1"; ACK=f"RUN {CAMPAIGN_ID}"
ARMS=("control-graph-off-cache0","candidate-graph-on-cache64")
EXPECTED_CLEANUP={"forced_kill":False,"port_closed":True,"render_node_idle":True,"server_survivor":False}
SUMMARY_RE=re.compile(r"\[SYCL-GRAPH\] summary device=(?P<device>\d+) requested=(?P<requested>\d+) compatibility_rejected=(?P<compatibility_rejected>\d+) device_unsupported=(?P<device_unsupported>\d+) cache_entries=(?P<cache_entries>\d+) cache_limit=(?P<cache_limit>\d+) cache_hit=(?P<cache_hit>\d+) cache_miss=(?P<cache_miss>\d+) cache_full=(?P<cache_full>\d+) direct_replay=(?P<direct_replay>\d+) recorded=(?P<recorded>\d+) created=(?P<created>\d+) updated=(?P<updated>\d+) recreated=(?P<recreated>\d+) replayed=(?P<replayed>\d+)")

def _load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module); return module

Q8=_load(Q8_RUNNER,"qwen38_q8_graph_sentinel_base"); GRAPH=_load(GRAPH_RUNNER,"qwen38_q8_graph_sentinel_template")
GateError=Q8.GateError; CORE=Q8.CORE

def load_json(path:Path)->dict[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise GateError(f"JSON root must be object: {path}")
    return value

def resolve(raw:str)->Path:
    path=Path(raw); return path if path.is_absolute() else REPO/path

def sha256_file(path:Path)->str:
    d=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(4<<20),b""): d.update(chunk)
    return d.hexdigest()

def validate_manifest(v:dict[str,Any])->None:
    s=v.get("selectors") or {}; e=v.get("execution_contract") or {}; c=v.get("capacity_decision") or {}; l=v.get("lifecycle") or {}; f=v.get("frozen_interpretation") or {}
    if not (v.get("schema")=="neural.download.qwen38-q8weights-f16kv-target-sycl-graph-cache64-8k-sentinel-prereg.v1" and v.get("campaign_id")==CAMPAIGN_ID and v.get("state")=="preregistered-not-launched"
        and s=={"revision":"qwen3.8-27b-current-weights","target_quantization":"Q8_0","tp":1,"mtp":0,"active_context_tokens":8192,"target_kv":"f16","graph_mode":"matched control: off versus SYCL graph cache64","fit":"off","transport":"HTTP /v1/completions"}
        and e.get("arm_order")==list(ARMS) and e.get("same_exact_8k_and_full_quality_workload_per_arm") is True and e.get("only_graph_flags_may_differ_between_arms") is True
        and e.get("control_environment_delta")=={"GGML_SYCL_ENABLE_GRAPH":"0","GGML_SYCL_GRAPH_CACHE_SIZE":"0"} and e.get("candidate_environment_delta")=={"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"64"}
        and e.get("minimum_direct_replays")==120 and e.get("minimum_direct_replay_fraction")==0.35
        and c.get("selected_cache_size")==c.get("source_supported_maximum")==64 and c.get("no_further_capacity_escalation") is True and len(c.get("full_workload_replicas",[]))==3
        and all(x.get("requested")==1182 and x.get("direct_replay")==947 and x.get("minimum_direct_replays")==896 for x in c["full_workload_replicas"])
        and l.get("output_root")==f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}" and l.get("exact_ack")==ACK and l.get("default_is_inert") is True and l.get("requires_clean_pushed_main") is True and l.get("create_only") is True
        and f.get("speed_floor") is None and f.get("site_cells_authorized")==0 and f.get("sentinel_pass_authorizes_separate_seven_depth_full_curve_preregistration") is True and f.get("full_graph_curve_authorized") is False
        and f.get("protected_decode_values")==[71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144]): raise GateError("Q8 graph sentinel manifest invariant failed")

def load_manifest()->dict[str,Any]:
    v=load_json(MANIFEST); validate_manifest(v); return v

def verify_dependencies(v:dict[str,Any])->None:
    for name,row in v["dependencies"].items():
        path=resolve(row["path"])
        if not path.is_file() or sha256_file(path)!=row["sha256"]: raise GateError(f"sealed dependency changed: {name}: {path}")
    terminal=load_json(resolve(v["dependencies"]["q8_graph_off_terminal"]["path"])); off=load_json(resolve(v["dependencies"]["q8_graph_off_result"]["path"])); receipt=load_json(resolve(v["dependencies"]["q8_graph_off_8k_receipt"]["path"]))
    if not (terminal.get("status")=="completed-valid-target-only-q8weights-f16kv-depth-quality" and off.get("status")=="passed" and (off.get("quality") or {}).get("pass_all") is True and (terminal.get("authority") or {}).get("target_only_q8weights_f16_serving_curve_cells")==7 and (receipt.get("gate") or {}).get("passed") is True): raise GateError("Q8 graph-off parent no longer passes")
    for key in ("q4km_cache64_full_result","q5ks_cache64_full_result","q4kxl_cache64_full_result"):
        result=load_json(resolve(v["dependencies"][key]["path"])); graph=result.get("graph_mechanism") or {}
        if not (result.get("status")=="passed" and graph.get("passed") is True and graph.get("requested")==1182 and graph.get("cache_limit")==64 and graph.get("direct_replay")==947 and graph.get("minimum_direct_replays")==896 and (graph.get("capacity_delta") or {}).get("source_supported_maximum")==64): raise GateError(f"cache64 evidence changed: {key}")

def graph_manifest(v:dict[str,Any])->dict[str,Any]:
    value=copy.deepcopy(GRAPH.graph_manifest(GRAPH.load_manifest())); value["campaign_id"]=CAMPAIGN_ID
    for key in ("model","fixture","clients","server_contract","lifecycle"): value[key]=copy.deepcopy(v[key])
    argv=value["server_argv"]
    for flag,replacement in {"-m":v["model"]["path"],"--alias":v["server_contract"]["model_alias"],"--port":str(v["server_contract"]["port"]),"-c":str(v["server_contract"]["context_capacity"])}.items(): argv[argv.index(flag)+1]=replacement
    if "-fit" not in argv: argv.extend(["-fit","off"])
    return value

class Execution(GRAPH.Execution): pass

def parse_graph_evidence(text:str,v:dict[str,Any])->dict[str,Any]:
    rows=[{k:int(x) for k,x in m.groupdict().items()} for m in SUMMARY_RE.finditer(text)]
    if len(rows)!=1: raise GateError(f"expected one graph summary, observed {len(rows)}")
    r=rows[0]; fraction=r["direct_replay"]/r["requested"] if r["requested"] else 0.0
    if not (r["device"]==0 and r["cache_limit"]==64 and r["requested"]==r["cache_hit"]+r["cache_miss"] and r["cache_hit"]==r["direct_replay"]>=v["execution_contract"]["minimum_direct_replays"] and fraction>=v["execution_contract"]["minimum_direct_replay_fraction"] and r["recorded"]==r["created"]==r["cache_entries"] and 1<=r["cache_entries"]<=64 and r["replayed"]==r["cache_hit"]+r["created"] and r["cache_full"]==r["cache_miss"]-r["created"] and r["requested"]==r["replayed"]+r["cache_full"] and all(r[k]==0 for k in ("compatibility_rejected","device_unsupported","updated","recreated"))): raise GateError(f"cache64 graph mechanism failed: {r}")
    return {**r,"summary_count":1,"direct_replay_fraction":fraction}

def quality_command(v:dict[str,Any],run:Execution,arm:str)->list[str]:
    q=v["clients"]["quality"]
    return [q["interpreter"],"-I","-B",str(resolve(q["path"])),"--base-url",f"http://127.0.0.1:{run.port}","--model",v["server_contract"]["model_alias"],"--tokenizer",q["tokenizer_path"],"--timeout",str(v["lifecycle"]["request_timeout_seconds"]),"--seed","1","--repeat-runs",str(q["repeat_runs"]),"--long-context-tokens",str(q["long_context_tokens"]),"--request-id-prefix",f"{CAMPAIGN_ID}-{arm}-quality","--output-json",str(run.root/arm/"quality.json")]

def static_check(v:dict[str,Any])->dict[str,Any]:
    validate_manifest(v); verify_dependencies(v); Q8.static_check(Q8.load_manifest()); GRAPH.static_check(GRAPH.load_manifest())
    source=Path(v["graph_runtime"]["source_path"])/"ggml/src/ggml-sycl/ggml-sycl.cpp"
    if "std::min(g_ggml_sycl_graph_cache_size, 64)" not in source.read_text(encoding="utf-8"): raise GateError("source cache maximum changed")
    gm=graph_manifest(v); argv=Execution(gm).server_argv(); runtime=v["graph_runtime"]
    if not (argv[argv.index("-m")+1]==v["model"]["path"] and argv[argv.index("--spec-type")+1]=="none" and "--spec-draft-model" not in argv and argv[argv.index("-ctk")+1]==argv[argv.index("-ctv")+1]=="f16" and argv[argv.index("-fit")+1]=="off" and argv[argv.index("--port")+1]=="19454" and sha256_file(Path(runtime["binary"]))==runtime["binary_sha256"]): raise GateError("effective Q8 graph argv/runtime invariant failed")
    parse_graph_evidence("[SYCL-GRAPH] summary device=0 requested=306 compatibility_rejected=0 device_unsupported=0 cache_entries=64 cache_limit=64 cache_hit=200 cache_miss=106 cache_full=42 direct_replay=200 recorded=64 created=64 updated=0 recreated=0 replayed=264",v)
    return {"schema":"neural.download.qwen38-q8weights-f16kv-graph-cache64-8k-sentinel-plan.v1","mode":"check","default_is_inert":True,"gpu_actions":0,"network_requests":0,"output_writes":0,"campaign_id":CAMPAIGN_ID,"exact_ack":ACK,"arms":list(ARMS),"fresh_server_lifetimes":2,"quality_batteries":2,"site_cells_if_valid":0,"full_curve_authorized":False,"seven_depth_curve_preregistration_if_valid":True,"candidate_cache_limit":64,"minimum_direct_replays":120,"server_argv":argv}

def execute(v:dict[str,Any])->Path:
    unexpected=[n for n in os.environ if n.startswith(("GGML_","SYCL_","ZE_","ZES_","UR_","ONEAPI_DEVICE_SELECTOR","LLAMA_ARG_")) or n=="LD_PRELOAD"]
    if unexpected: raise GateError("unexpected inherited runtime environment: "+",".join(sorted(unexpected)))
    subprocess.run(["git","fetch","origin","main","--quiet"],cwd=REPO,check=True); head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO,text=True).strip(); origin=subprocess.check_output(["git","rev-parse","origin/main"],cwd=REPO,text=True).strip()
    if head!=origin or subprocess.check_output(["git","status","--porcelain"],cwd=REPO,text=True).strip(): raise GateError("execution requires clean pushed main")
    plan=static_check(v); gm=graph_manifest(v); run=Execution(gm); run.acquire_locks(); run.require_idle()
    if run.root.exists(): raise GateError(f"create-only root exists: {run.root}")
    run.root.parent.mkdir(parents=True,exist_ok=True)
    if subprocess.check_output(["findmnt","-no","FSTYPE","--target",str(run.root.parent)],text=True).strip()!="ext4": raise GateError("run-root parent must be ext4")
    run.root.mkdir(); [(run.root/p).mkdir(parents=True,exist_ok=False) for p in ("runtime-home","runtime-cache/sycl","runtime-tmp")]
    CORE.verify_file(Path(v["model"]["path"]),v["model"]["sha256"],v["model"]["size_bytes"]); CORE.verify_file(Path(v["graph_runtime"]["binary"]),v["graph_runtime"]["binary_sha256"],v["graph_runtime"]["binary_size_bytes"])
    base_env=GRAPH.GRAPH.IMPL.BASE.oneapi_environment(run.root,GRAPH.GRAPH.load_manifest()["environment"]); envs={ARMS[0]:{**base_env,**v["execution_contract"]["control_environment_delta"]},ARMS[1]:{**base_env,**v["execution_contract"]["candidate_environment_delta"]}}; argv=run.server_argv()
    CORE.write_json_x(run.root/"identity.json",{"campaign_id":CAMPAIGN_ID,"created_at_utc":dt.datetime.now(dt.UTC).isoformat(),"git_head":head,"origin_main":origin,"model":v["model"],"graph_runtime":v["graph_runtime"],"capacity_decision":v["capacity_decision"],"server_argv":{a:argv for a in ARMS},"runtime_environment":{a:{k:envs[a][k] for k in ("ONEAPI_DEVICE_SELECTOR","GGML_SYCL_ENABLE_GRAPH","GGML_SYCL_GRAPH_CACHE_SIZE")} for a in ARMS},"plan":plan})
    for arm in ARMS:
        error=None; cleanup=None
        try:
            run.require_idle(); run.start(arm,argv,envs[arm]); run.run_depth(arm,8192,False)
            with (run.root/arm/"quality.stdout.json").open("xb") as out,(run.root/arm/"quality.stderr.log").open("xb") as err: subprocess.run(quality_command(v,run,arm),cwd=REPO,check=True,stdout=out,stderr=err)
        except BaseException as exc: error=f"{type(exc).__name__}: {exc}"
        finally: cleanup=run.stop(arm)
        if arm==ARMS[1] and error is None:
            try: CORE.write_json_x(run.root/arm/"graph-evidence.json",parse_graph_evidence((run.root/arm/"server.log").read_text(encoding="utf-8",errors="replace"),v))
            except BaseException as exc: error=f"{type(exc).__name__}: {exc}"
        complete=error is None and cleanup==EXPECTED_CLEANUP; CORE.write_json_x(run.root/arm/"arm-result.json",{"status":"completed-awaiting-validation" if complete else "failed-preserve","error":error,"cleanup":cleanup})
        if not complete: raise GateError(f"{arm} failed: {error or cleanup}")
    terminal=run.root/"terminal-receipt.json"
    with (run.root/"validator.stdout.json").open("xb") as out: subprocess.run([sys.executable,"-B",str(VALIDATOR),"--root",str(run.root),"--manifest",str(MANIFEST),"--output",str(terminal)],cwd=REPO,check=True,stdout=out)
    return terminal

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--check",action="store_true"); p.add_argument("--execute",action="store_true"); p.add_argument("--ack",default=""); a=p.parse_args()
    try:
        v=load_manifest()
        if not a.execute: print(json.dumps(static_check(v),indent=2,sort_keys=True)); return 0
        if a.ack!=ACK: raise GateError(f"exact --ack required: {ACK}")
        print(execute(v)); return 0
    except (GateError,OSError,ValueError,json.JSONDecodeError,subprocess.SubprocessError) as exc: p.error(str(exc))
    return 2
if __name__=="__main__": raise SystemExit(main())
