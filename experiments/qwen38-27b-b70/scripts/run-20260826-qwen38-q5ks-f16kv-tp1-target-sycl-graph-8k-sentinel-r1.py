#!/usr/bin/env python3
"""Create-only Qwen3.8 Q5_K_S F16-KV TP1 SYCL graph 8K quality sentinel."""

from __future__ import annotations
import argparse, copy, datetime as dt, hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-q5ks-f16kv-tp1-target-sycl-graph-8k-sentinel-r1-prereg.json"
VALIDATOR = LANE / "scripts/validate-20260826-qwen38-q5ks-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"
Q5_RUNNER = LANE / "scripts/run-20260826-qwen38-q5ks-f16kv-tp1-target-http-depth-quality-r1.py"
GRAPH_RUNNER = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q4km-f16-tp1-sycl-graph-quality-r1.py"
CAMPAIGN_ID = "qwen38-q5ks-f16kv-tp1-target-sycl-graph-8k-sentinel-20260826-r1"
ACK = f"RUN {CAMPAIGN_ID}"
ARMS = ("control-graph-off-cache0", "candidate-graph-on-cache8")
EXPECTED_CLEANUP = {"forced_kill": False, "port_closed": True, "render_node_idle": True, "server_survivor": False}

def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module

Q5 = load_module(Q5_RUNNER, "qwen38_q5_graph_sentinel_base")
GRAPH = load_module(GRAPH_RUNNER, "qwen36_graph_sentinel_identity_base")
CORE, GateError = Q5.CORE, Q5.GateError

def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise GateError(f"JSON root must be object: {path}")
    return value

def resolve(raw: str) -> Path:
    path = Path(raw); return path if path.is_absolute() else REPO / path

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()

def validate_manifest(v: dict[str, Any]) -> None:
    s, e, l, f = v.get("selectors") or {}, v.get("execution_contract") or {}, v.get("lifecycle") or {}, v.get("frozen_interpretation") or {}
    if not (v.get("schema") == "neural.download.qwen38-q5ks-f16kv-target-sycl-graph-8k-sentinel-prereg.v1"
            and v.get("campaign_id") == CAMPAIGN_ID and v.get("state") == "preregistered-not-launched"
            and s == {"revision":"qwen3.8-27b-current-weights","target_quantization":"UD-Q5_K_S","tp":1,"mtp":0,"active_context_tokens":8192,"target_kv":"f16","fit":"off","transport":"HTTP /v1/completions"}
            and e.get("arm_order") == list(ARMS) and e.get("only_graph_flags_may_differ_between_arms") is True
            and e.get("control_environment_delta") == {"GGML_SYCL_ENABLE_GRAPH":"0","GGML_SYCL_GRAPH_CACHE_SIZE":"0"}
            and e.get("candidate_environment_delta") == {"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"8"}
            and l.get("output_root") == f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}" and l.get("exact_ack") == ACK
            and l.get("default_is_inert") is True and l.get("create_only") is True and l.get("requires_clean_pushed_main") is True
            and e.get("candidate_quality_battery") is False
            and f.get("speed_floor") is None and f.get("site_cells_authorized") == 0
            and f.get("sentinel_pass_authorizes_full_curve_preregistration") is True
            and f.get("graph_off_control_cells_authorized") == 0 and f.get("full_graph_curve_authorized") is False
            and f.get("mtp_or_speculative_cells_authorized") == 0 and f.get("tp2_or_tp4_cells_authorized") == 0
            and f.get("headline_or_protected_replacement_authorized") is False
            and f.get("protected_decode_values") == [71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144]):
        raise GateError("graph sentinel manifest invariant failed")

def load_manifest() -> dict[str, Any]:
    value = load_json(MANIFEST); validate_manifest(value); return value

def verify_dependencies(v: dict[str, Any]) -> None:
    for name, row in v["dependencies"].items():
        path = resolve(row["path"])
        if not path.is_file() or sha256_file(path) != row["sha256"]: raise GateError(f"sealed dependency changed: {name}: {path}")
    terminal = load_json(resolve(v["dependencies"]["qwen38_graph_off_terminal"]["path"]))
    old8k = load_json(resolve(v["dependencies"]["qwen38_graph_off_8k_receipt"]["path"]))
    if terminal.get("status") != "completed-valid-target-only-f16kv-depth-quality" or not (old8k.get("gate") or {}).get("passed"):
        raise GateError("passed Qwen3.8 graph-off parent invariant failed")

def graph_manifest(v: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(GRAPH.load_manifest())
    argv = value["server_argv"]
    for flag, replacement in (("-m",v["model"]["path"]),("--alias",v["server_contract"]["model_alias"]),("--port",str(v["server_contract"]["port"]))):
        argv[argv.index(flag)+1] = replacement
    value["campaign_id"] = CAMPAIGN_ID; value["model"] = copy.deepcopy(v["model"])
    value["server_contract"] = copy.deepcopy(v["server_contract"]); value["fixture"] = copy.deepcopy(v["fixture"])
    value["clients"] = copy.deepcopy(v["clients"]); value["lifecycle"] = copy.deepcopy(v["lifecycle"])
    return value

class Execution(Q5.Execution):
    def server_argv(self) -> list[str]: return list(self.m["server_argv"])

def static_check(v: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(v); verify_dependencies(v); Q5.static_check(Q5.load_manifest())
    sealed, _, libraries = GRAPH.static_check(); gm = graph_manifest(v)
    runtime = v["graph_runtime"]
    if not (sealed["runtime"]["server"]["path"] == runtime["binary"] and sealed["runtime"]["server"]["sha256"] == runtime["binary_sha256"]
            and sealed["runtime"]["server_effective_shared_libraries"] == {"count":runtime["effective_dso_count"],"canonical_json_sha256":runtime["effective_dso_canonical_sha256"]}
            and [x["sha256"] for x in sealed["source"]["patch_chain_in_order"]] == runtime["patch_chain_sha256"]):
        raise GateError("sealed graph runtime identity changed")
    fixture = load_json(resolve(v["fixture"]["path"])); rows = [x for x in fixture.get("cases",[]) if x.get("id") == "depth-8192"]
    if len(rows) != 1 or rows[0].get("prompt_token_ids_sha256") != v["fixture"]["prompt_token_ids_sha256"]: raise GateError("8K fixture changed")
    argv = Execution(gm).server_argv()
    if argv[argv.index("--spec-type")+1] != "none" or "--spec-draft-model" in argv or argv[argv.index("-ctk")+1] != "f16" or argv[argv.index("-ctv")+1] != "f16" or "-fit" in argv:
        raise GateError("target-only graph argv invariant failed")
    return {"schema":"neural.download.qwen38-q5ks-f16kv-target-sycl-graph-8k-plan.v1","mode":"check","default_is_inert":True,"gpu_actions":0,"network_requests":0,"output_writes":0,"campaign_id":CAMPAIGN_ID,"exact_ack":ACK,"arms":list(ARMS),"fresh_server_lifetimes":2,"site_cells_if_valid":0,"full_curve_authorized":False,"curve_preregistration_if_valid":True,"server_argv":argv,"effective_dso_count":len(libraries)}

def execute(v: dict[str, Any]) -> Path:
    unexpected=[n for n in os.environ if n.startswith(("GGML_","SYCL_","ZE_","ZES_","UR_","ONEAPI_DEVICE_SELECTOR","LLAMA_ARG_")) or n=="LD_PRELOAD"]
    if unexpected: raise GateError("unexpected inherited runtime environment: "+",".join(sorted(unexpected)))
    subprocess.run(["git","fetch","origin","main","--quiet"],cwd=REPO,check=True)
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO,text=True).strip(); origin=subprocess.check_output(["git","rev-parse","origin/main"],cwd=REPO,text=True).strip()
    if head != origin or subprocess.check_output(["git","status","--porcelain"],cwd=REPO,text=True).strip(): raise GateError("execution requires clean pushed main")
    plan=static_check(v); gm=graph_manifest(v); run=Execution(gm); run.acquire_locks(); run.require_idle()
    if run.root.exists(): raise GateError(f"create-only root exists: {run.root}")
    run.root.parent.mkdir(parents=True,exist_ok=True)
    if subprocess.check_output(["findmnt","-no","FSTYPE","--target",str(run.root.parent)],text=True).strip() != "ext4": raise GateError("run-root parent must be ext4")
    run.root.mkdir(); [ (run.root/p).mkdir(parents=True,exist_ok=False) for p in ("runtime-home","runtime-cache/sycl","runtime-tmp") ]
    CORE.verify_file(Path(v["model"]["path"]),v["model"]["sha256"],v["model"]["size_bytes"])
    base_env=GRAPH.IMPL.BASE.oneapi_environment(run.root,GRAPH.load_manifest()["environment"])
    envs={ARMS[0]:{**base_env,**v["execution_contract"]["control_environment_delta"]},ARMS[1]:{**base_env,**v["execution_contract"]["candidate_environment_delta"]}}
    argv=run.server_argv(); graph_off_receipt=None
    CORE.write_json_x(run.root/"identity.json",{"campaign_id":CAMPAIGN_ID,"created_at_utc":dt.datetime.now(dt.UTC).isoformat(),"git_head":head,"origin_main":origin,"model":v["model"],"graph_runtime":v["graph_runtime"],"server_argv":{a:argv for a in ARMS},"runtime_environment":{a:{k:envs[a][k] for k in ("ONEAPI_DEVICE_SELECTOR","GGML_SYCL_ENABLE_GRAPH","GGML_SYCL_GRAPH_CACHE_SIZE")} for a in ARMS},"plan":plan})
    for index,arm in enumerate(ARMS):
        error=None; cleanup=None
        try:
            run.require_idle(); run.start(arm,argv,envs[arm]); run.run_depth(arm,8192,False)
            receipt=load_json(run.root/arm/"depth-8192/exact-depth.json")
            if index == 0:
                graph_off_receipt=receipt
            else:
                left = graph_off_receipt["response"]
                right = receipt["response"]
                parity_keys = ("output_token_ids_sha256", "text_sha256", "token_ids", "usage", "returned_prompt_token_ids_sha256")
                if any(left.get(key) != right.get(key) for key in parity_keys):
                    raise GateError("graph-on output or usage differs from same-binary graph-off control")
        except BaseException as exc: error=f"{type(exc).__name__}: {exc}"
        finally: cleanup=run.stop(arm)
        if index == 1 and error is None:
            try:
                evidence=GRAPH.IMPL.F16.graph_evidence((run.root/arm/"server.log").read_text(encoding="utf-8",errors="replace"))
                CORE.write_json_x(run.root/arm/"graph-evidence.json",evidence)
            except BaseException as exc:
                error=f"{type(exc).__name__}: {exc}"
        complete=error is None and cleanup==EXPECTED_CLEANUP
        CORE.write_json_x(run.root/arm/"arm-result.json",{"status":"completed-awaiting-validation" if complete else "failed-preserve","error":error,"cleanup":cleanup})
        if not complete: raise GateError(f"{arm} failed: {error or cleanup}")
    terminal=run.root/"terminal-receipt.json"
    with (run.root/"validator.stdout.json").open("xb") as stdout: subprocess.run([sys.executable,"-B",str(VALIDATOR),"--root",str(run.root),"--manifest",str(MANIFEST),"--output",str(terminal)],cwd=REPO,check=True,stdout=stdout)
    return terminal

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--check",action="store_true"); p.add_argument("--execute",action="store_true"); p.add_argument("--ack",default=""); a=p.parse_args()
    try:
        v=load_manifest()
        if not a.execute: print(json.dumps(static_check(v),indent=2,sort_keys=True)); return 0
        if a.ack != ACK: raise GateError(f"exact --ack required: {ACK}")
        print(execute(v)); return 0
    except (GateError,OSError,ValueError,json.JSONDecodeError,subprocess.SubprocessError) as exc: p.error(str(exc))
    return 2

if __name__ == "__main__": raise SystemExit(main())
