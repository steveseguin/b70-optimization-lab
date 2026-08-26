#!/usr/bin/env python3
"""Create-only Q4_K_XL/F16 TP1 cache20 graph depth/quality curve."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
OVERLAY = LANE / "data/2026-08-26-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-r1-prereg.json"
BASE_RUNNER = LANE / "scripts/run-20260826-qwen38-q4kxl-f16kv-tp1-target-http-depth-quality-r1.py"
SENTINEL_RUNNER = LANE / "scripts/run-20260826-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2.py"
VALIDATOR = LANE / "scripts/validate-20260826-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-r1.py"
CAMPAIGN_ID = "qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-20260826-r1"
ACK = f"RUN {CAMPAIGN_ID}"
DEPTHS = (0, 2048, 4096, 8192, 16384, 24576, 32768)
ARM = "target-mtp0-graph-cache20"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load(BASE_RUNNER, "qwen38_q4kxl_graph_curve_base")
SENTINEL = _load(SENTINEL_RUNNER, "qwen38_q4kxl_graph_curve_sentinel_base")
GateError = BASE.GateError
CORE = SENTINEL.R1.CORE
EXPECTED_CLEANUP = BASE.EXPECTED_CLEANUP
BASE_VALUE = copy.deepcopy(BASE.load_manifest())
BASE_STATIC_CHECK = BASE.static_check
SENTINEL_VALUE = copy.deepcopy(SENTINEL.load_manifest())
GRAPH_TEMPLATE = copy.deepcopy(SENTINEL.graph_manifest(SENTINEL_VALUE))
GRAPH_EXECUTION = SENTINEL.Execution

SUMMARY_RE = re.compile(
    r"\[SYCL-GRAPH\] summary device=(?P<device>\d+) requested=(?P<requested>\d+) "
    r"compatibility_rejected=(?P<compatibility_rejected>\d+) device_unsupported=(?P<device_unsupported>\d+) "
    r"cache_entries=(?P<cache_entries>\d+) cache_limit=(?P<cache_limit>\d+) cache_hit=(?P<cache_hit>\d+) "
    r"cache_miss=(?P<cache_miss>\d+) cache_full=(?P<cache_full>\d+) direct_replay=(?P<direct_replay>\d+) "
    r"recorded=(?P<recorded>\d+) created=(?P<created>\d+) updated=(?P<updated>\d+) "
    r"recreated=(?P<recreated>\d+) replayed=(?P<replayed>\d+)"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"JSON root must be object: {path}")
    return value


def resolve(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else REPO / path


def load_overlay() -> dict[str, Any]:
    value = load_json(OVERLAY)
    selectors = value.get("selectors") or {}
    execution = value.get("execution_contract") or {}
    graph = value.get("graph_acceptance") or {}
    lifecycle = value.get("lifecycle") or {}
    frozen = value.get("frozen_interpretation") or {}
    if not (
        value.get("schema") == "neural.download.qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors == {"revision":"qwen3.8-27b-current-weights","target_quantization":"UD-Q4_K_XL","tp":1,"mtp":0,"active_context_tokens":list(DEPTHS),"target_kv":"f16","graph_mode":"SYCL graph cache20","fit":"off","transport":"HTTP /v1/completions"}
        and execution.get("arm") == ARM
        and execution.get("fresh_server_lifetimes") == 1
        and execution.get("depth_order") == list(DEPTHS)
        and execution.get("quality_after_all_depths") is True
        and execution.get("graph_environment") == {"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"20"}
        and execution.get("require_cache20_sentinel_passed") is True
        and graph == {"summary_count":1,"cache_limit":20,"minimum_direct_replays":896,"requested_equals_cache_hit_plus_cache_miss":True,"cache_hit_equals_direct_replay":True,"recorded_equals_created_equals_cache_entries":True,"replayed_equals_cache_hit_plus_created":True,"cache_full_equals_cache_miss_minus_created":True,"requested_equals_replayed_plus_cache_full":True,"compatibility_rejected_device_unsupported_updated_recreated_zero":True,"cache_full_permitted_for_additional_prefill_and_quality_shapes":True}
        and lifecycle == {"output_root":f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}","exact_ack":ACK,"default_is_inert":True,"requires_clean_pushed_main":True,"create_only":True}
        and frozen.get("speed_floor") is None
        and frozen.get("evidence_grade") == "C"
        and frozen.get("graph_q4kxl_f16_serving_curve_cells_if_all_gates_pass") == 7
        and frozen.get("graph_off_cells_authorized") == 0
        and frozen.get("headline_or_protected_replacement_authorized") is False
        and frozen.get("protected_decode_values") == [71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144]
    ):
        raise GateError("Q4_K_XL graph curve overlay invariant failed")
    for name, row in value["dependencies"].items():
        path = resolve(row["path"])
        if not path.is_file() or sha256_file(path) != row["sha256"]:
            raise GateError(f"sealed graph curve dependency changed: {name}: {path}")
    terminal = load_json(resolve(value["dependencies"]["cache20_sentinel_terminal"]["path"]))
    evidence = terminal.get("graph_evidence") or {}
    if not (
        terminal.get("status") == "completed-valid-target-only-q4kxl-graph-8k-sentinel"
        and (terminal.get("authority") or {}).get("full_curve_preregistration") is True
        and evidence.get("cache_limit") == 20
        and evidence.get("cache_hit") == evidence.get("direct_replay") == 126
        and evidence.get("cache_full") == 0
    ):
        raise GateError("passed cache20 sentinel authority changed")
    return value


def load_manifest() -> dict[str, Any]:
    overlay = load_overlay()
    value = copy.deepcopy(BASE_VALUE)
    value["schema"] = "neural.download.qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-effective.v1"
    value["campaign_id"] = CAMPAIGN_ID
    value["purpose"] = overlay["purpose"]
    value["graph_parent"] = copy.deepcopy(overlay["dependencies"])
    graph_runtime = SENTINEL_VALUE["graph_runtime"]
    value["runtime"] = {
        "binary": graph_runtime["binary"],
        "binary_sha256": graph_runtime["binary_sha256"],
        "binary_size_bytes": graph_runtime["binary_size_bytes"],
        "source_commit": graph_runtime["source_base_head"],
        "graph_backend_sha256": graph_runtime["graph_backend_sha256"],
        "effective_dso_count": graph_runtime["effective_dso_count"],
        "effective_dso_canonical_sha256": graph_runtime["effective_dso_canonical_sha256"],
        "patch_chain_sha256": copy.deepcopy(graph_runtime["patch_chain_sha256"]),
        "effective_local_shared_libraries": [],
    }
    value["selectors"] = copy.deepcopy(overlay["selectors"])
    value["server_contract"].update({"port":19450,"model_alias":"qwen38-q4kxl-f16kv-tp1-graph-cache20-depth-r1","graph":"SYCL cache20"})
    value["execution_contract"] = copy.deepcopy(overlay["execution_contract"])
    value["graph_acceptance"] = copy.deepcopy(overlay["graph_acceptance"])
    value["lifecycle"].update(overlay["lifecycle"])
    value["frozen_interpretation"] = copy.deepcopy(overlay["frozen_interpretation"])
    validate_manifest(value)
    return value


def validate_manifest(value: dict[str, Any]) -> None:
    overlay = load_overlay()
    if not (
        value.get("schema") == "neural.download.qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-effective.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("selectors") == overlay["selectors"]
        and value.get("execution_contract") == overlay["execution_contract"]
        and value.get("graph_acceptance") == overlay["graph_acceptance"]
        and value.get("lifecycle", {}).get("output_root") == f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}"
        and value.get("lifecycle", {}).get("exact_ack") == ACK
        and value.get("server_contract", {}).get("cache_type_k") == "f16"
        and value.get("server_contract", {}).get("cache_type_v") == "f16"
        and value.get("server_contract", {}).get("spec_type") == "none"
        and value.get("runtime", {}).get("binary") == SENTINEL_VALUE["graph_runtime"]["binary"]
        and value.get("runtime", {}).get("binary_sha256") == SENTINEL_VALUE["graph_runtime"]["binary_sha256"]
        and value.get("runtime", {}).get("patch_chain_sha256") == SENTINEL_VALUE["graph_runtime"]["patch_chain_sha256"]
        and value.get("frozen_interpretation") == overlay["frozen_interpretation"]
    ):
        raise GateError("effective Q4_K_XL graph curve manifest invariant failed")


def merged_manifest(value: dict[str, Any]) -> dict[str, Any]:
    manifest = copy.deepcopy(GRAPH_TEMPLATE)
    manifest["campaign_id"] = CAMPAIGN_ID
    for key in ("model", "server_contract", "fixture", "clients", "lifecycle"):
        manifest[key] = copy.deepcopy(value[key])
    argv = manifest["server_argv"]
    replacements = {
        "-m": value["model"]["path"],
        "--alias": value["server_contract"]["model_alias"],
        "--port": str(value["server_contract"]["port"]),
        "-c": str(value["server_contract"]["context_capacity"]),
    }
    for flag, replacement in replacements.items():
        argv[argv.index(flag) + 1] = replacement
    if "-fit" not in argv:
        argv.extend(["-fit", "off"])
    manifest["environment"]["GGML_SYCL_ENABLE_GRAPH"] = "1"
    manifest["environment"]["GGML_SYCL_GRAPH_CACHE_SIZE"] = "20"
    return manifest


class Execution(GRAPH_EXECUTION):
    pass


def parse_graph_evidence(text: str) -> dict[str, int]:
    rows = [{key:int(item) for key,item in match.groupdict().items()} for match in SUMMARY_RE.finditer(text)]
    if len(rows) != 1:
        raise GateError(f"expected exactly one lifetime graph summary, observed {len(rows)}")
    row = rows[0]
    evidence = {**row, "summary_count": 1}
    if not (
        row["device"] == 0
        and row["cache_limit"] == 20
        and row["requested"] == row["cache_hit"] + row["cache_miss"]
        and row["cache_hit"] == row["direct_replay"] >= 896
        and row["recorded"] == row["created"] == row["cache_entries"]
        and 1 <= row["cache_entries"] <= 20
        and row["replayed"] == row["cache_hit"] + row["created"]
        and row["cache_full"] == row["cache_miss"] - row["created"]
        and row["requested"] == row["replayed"] + row["cache_full"]
        and all(row[key] == 0 for key in ("compatibility_rejected","device_unsupported","updated","recreated"))
    ):
        raise GateError(f"full-curve cache20 graph evidence failed: {row}")
    return evidence


def static_check(value: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(value)
    BASE_STATIC_CHECK(BASE_VALUE)
    SENTINEL.static_check(SENTINEL_VALUE)
    argv = Execution(merged_manifest(value)).server_argv()
    if not (
        argv[argv.index("--spec-type") + 1] == "none"
        and "--spec-draft-model" not in argv
        and argv[argv.index("-ctk") + 1] == "f16"
        and argv[argv.index("-ctv") + 1] == "f16"
        and argv[argv.index("-fit") + 1] == "off"
        and argv[argv.index("--port") + 1] == "19450"
    ):
        raise GateError("effective Q4_K_XL graph curve argv invariant failed")
    return {"schema":"neural.download.qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-plan.v1","mode":"check","default_is_inert":True,"gpu_actions":0,"network_requests":0,"output_writes":0,"campaign_id":CAMPAIGN_ID,"exact_ack":ACK,"arm":ARM,"fresh_server_lifetimes":1,"depths":list(DEPTHS),"quality_batteries":1,"graph_q4kxl_f16_cells_if_valid":7,"speed_floor":None,"server_argv":argv}


def execute(value: dict[str, Any]) -> Path:
    manifest = merged_manifest(value)
    unexpected = [name for name in os.environ if name.startswith(("GGML_","SYCL_","ZE_","ZES_","UR_","ONEAPI_DEVICE_SELECTOR","LLAMA_ARG_")) or name == "LD_PRELOAD"]
    if unexpected:
        raise GateError("unexpected inherited runtime environment: " + ",".join(sorted(unexpected)))
    subprocess.run(["git","fetch","origin","main","--quiet"],cwd=REPO,check=True)
    head = subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO,text=True).strip()
    origin = subprocess.check_output(["git","rev-parse","origin/main"],cwd=REPO,text=True).strip()
    if head != origin or subprocess.check_output(["git","status","--porcelain"],cwd=REPO,text=True).strip():
        raise GateError("execution requires clean pushed main")
    run = Execution(manifest)
    run.acquire_locks(); run.require_idle()
    if run.root.exists():
        raise GateError(f"create-only root exists: {run.root}")
    run.root.parent.mkdir(parents=True,exist_ok=True)
    if subprocess.check_output(["findmnt","-no","FSTYPE","--target",str(run.root.parent)],text=True).strip() != "ext4":
        raise GateError("run-root parent must be ext4")
    run.root.mkdir()
    for relative in ("runtime-home", "runtime-cache/sycl", "runtime-tmp"):
        (run.root / relative).mkdir(parents=True, exist_ok=False)
    error: str | None = None
    cleanup: dict[str, bool] | None = None
    try:
        static_check(value)
        CORE.verify_file(Path(value["model"]["path"]),value["model"]["sha256"],value["model"]["size_bytes"])
        CORE.verify_file(Path(value["runtime"]["binary"]),value["runtime"]["binary_sha256"],value["runtime"]["binary_size_bytes"])
        SENTINEL.GRAPH.static_check()
        env = SENTINEL.GRAPH.IMPL.BASE.oneapi_environment(run.root,SENTINEL.GRAPH.load_manifest()["environment"])
        env.update(value["execution_contract"]["graph_environment"])
        argv = run.server_argv()
        CORE.write_json_x(run.root/"identity.json",{"campaign_id":CAMPAIGN_ID,"created_at_utc":dt.datetime.now(dt.UTC).isoformat(),"git_head":head,"origin_main":origin,"model":value["model"],"runtime":{**value["runtime"],"local_dsos":[]},"graph_runtime":SENTINEL_VALUE["graph_runtime"],"fixture":value["fixture"],"server_argv":{ARM:argv},"runtime_environment":{key:env[key] for key in ("ONEAPI_DEVICE_SELECTOR","GGML_SYCL_ENABLE_GRAPH","GGML_SYCL_GRAPH_CACHE_SIZE")},"parent":value["parent"],"graph_parent":value["graph_parent"]})
        run.start(ARM,argv,env)
        for depth in DEPTHS:
            run.run_depth(ARM,depth,False)
        q = value["clients"]["quality"]
        command = [q["interpreter"],"-I","-B",str(resolve(q["path"])),"--base-url",f"http://127.0.0.1:{run.port}","--model",value["server_contract"]["model_alias"],"--tokenizer",q["tokenizer_path"],"--timeout",str(value["lifecycle"]["request_timeout_seconds"]),"--seed","1","--repeat-runs",str(q["repeat_runs"]),"--long-context-tokens",str(q["long_context_tokens"]),"--request-id-prefix",f"{CAMPAIGN_ID}-quality","--output-json",str(run.root/ARM/"quality.json")]
        with (run.root/ARM/"quality.stdout.json").open("xb") as stdout, (run.root/ARM/"quality.stderr.log").open("xb") as stderr:
            subprocess.run(command,cwd=REPO,check=True,stdout=stdout,stderr=stderr)
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        (run.root/ARM).mkdir(exist_ok=True)
        cleanup = run.stop(ARM)
    if error is None:
        try:
            evidence = parse_graph_evidence((run.root/ARM/"server.log").read_text(encoding="utf-8",errors="replace"))
            CORE.write_json_x(run.root/ARM/"graph-evidence.json",evidence)
        except BaseException as exc:
            error = f"{type(exc).__name__}: {exc}"
    complete = error is None and cleanup == EXPECTED_CLEANUP
    CORE.write_json_x(run.root/ARM/"arm-result.json",{"status":"completed-awaiting-validation" if complete else "failed-preserve","error":error,"cleanup":cleanup})
    terminal = run.root/"terminal-receipt.json"
    if not complete:
        CORE.write_json_x(terminal,{"schema":"neural.download.qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-terminal.v1","campaign_id":CAMPAIGN_ID,"status":"failed-preserve-do-not-publish","error":error or f"cleanup failed: {cleanup}","authority":{"graph_q4kxl_f16_serving_curve_cells":0,"other_cells":0,"protected_replacement":False}})
        raise GateError(error or f"cleanup failed: {cleanup}")
    with (run.root/"validator.stdout.json").open("xb") as stdout:
        subprocess.run([sys.executable,"-B",str(VALIDATOR),"--root",str(run.root),"--manifest",str(OVERLAY),"--output",str(terminal)],cwd=REPO,check=True,stdout=stdout)
    return terminal


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--check",action="store_true"); parser.add_argument("--execute",action="store_true"); parser.add_argument("--ack",default=""); args = parser.parse_args()
    if args.check and args.execute:
        parser.error("choose --check or --execute")
    try:
        value = load_manifest()
        if not args.execute:
            print(json.dumps(static_check(value),indent=2,sort_keys=True)); return 0
        if args.ack != ACK:
            raise GateError(f"exact --ack required: {ACK}")
        print(execute(value)); return 0
    except (GateError,OSError,ValueError,json.JSONDecodeError,subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
