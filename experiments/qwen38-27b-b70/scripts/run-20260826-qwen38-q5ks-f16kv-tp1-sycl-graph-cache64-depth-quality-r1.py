#!/usr/bin/env python3
"""Create-only Q5_K_S/F16 TP1 cache64 graph depth/quality curve."""

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
OVERLAY = LANE / "data/2026-08-26-qwen38-q5ks-f16kv-tp1-sycl-graph-cache64-depth-quality-r1-prereg.json"
BASE_RUNNER = LANE / "scripts/run-20260826-qwen38-q5ks-f16kv-tp1-target-http-depth-quality-r1.py"
SENTINEL_RUNNER = LANE / "scripts/run-20260826-qwen38-q5ks-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2.py"
VALIDATOR = LANE / "scripts/validate-20260826-qwen38-q5ks-f16kv-tp1-sycl-graph-cache64-depth-quality-r1.py"
CAMPAIGN_ID = "qwen38-q5ks-f16kv-tp1-sycl-graph-cache64-depth-quality-20260826-r1"
ACK = f"RUN {CAMPAIGN_ID}"
DEPTHS = (0, 2048, 4096, 8192, 16384, 24576, 32768)
ARM = "target-mtp0-graph-cache64"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load(BASE_RUNNER, "qwen38_q5ks_graph_curve_base")
SENTINEL = _load(SENTINEL_RUNNER, "qwen38_q5ks_graph_curve_sentinel")
GateError = BASE.GateError
CORE = BASE.CORE
EXPECTED_CLEANUP = BASE.EXPECTED_CLEANUP
BASE_VALUE = copy.deepcopy(BASE.load_manifest())
BASE_STATIC_CHECK = BASE.static_check
SENTINEL_VALUE = copy.deepcopy(SENTINEL.load_manifest())
GRAPH_TEMPLATE = copy.deepcopy(SENTINEL.BASE.graph_manifest(SENTINEL_VALUE))
GRAPH_EXECUTION = SENTINEL.Execution
ZERO_CONTEXT_SEMANTICS = copy.deepcopy(BASE.merged_manifest(BASE_VALUE)["zero_context_semantics"])

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
    capacity = value.get("capacity_decision") or {}
    lifecycle = value.get("lifecycle") or {}
    frozen = value.get("frozen_interpretation") or {}
    if not (
        value.get("schema") == "neural.download.qwen38-q5ks-f16kv-tp1-sycl-graph-cache64-depth-quality-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors == {"revision":"qwen3.8-27b-current-weights","target_quantization":"UD-Q5_K_S","tp":1,"mtp":0,"active_context_tokens":list(DEPTHS),"target_kv":"f16","graph_mode":"SYCL graph cache64","fit":"off","transport":"HTTP /v1/completions"}
        and execution == {"arm":ARM,"fresh_server_lifetimes":1,"depth_order":list(DEPTHS),"completion_tokens_per_depth":128,"quality_after_all_depths":True,"require_cached_tokens_zero_everywhere":True,"graph_environment":{"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"64"},"require_cache20_sentinel_recovery_passed":True,"require_report_composition_preflight":True,"require_cleanup":True}
        and graph == {"summary_count":1,"cache_limit":64,"minimum_direct_replays":896,"requested_equals_cache_hit_plus_cache_miss":True,"cache_hit_equals_direct_replay":True,"recorded_equals_created_equals_cache_entries":True,"replayed_equals_cache_hit_plus_created":True,"cache_full_equals_cache_miss_minus_created":True,"requested_equals_replayed_plus_cache_full":True,"compatibility_rejected_device_unsupported_updated_recreated_zero":True,"cache_full_permitted_for_additional_prefill_and_quality_shapes":True}
        and capacity.get("selected_cache_size") == capacity.get("source_supported_maximum") == 64
        and capacity.get("q5_cache20_sentinel_requested") == 146
        and capacity.get("q5_cache20_sentinel_direct_replays") == 126
        and capacity.get("same_workload_cache20_requested") == 1182
        and capacity.get("same_workload_cache20_direct_replays") == 471
        and capacity.get("same_workload_cache20_cache_full") == 691
        and capacity.get("same_workload_cache64_direct_replays") == 947
        and capacity.get("minimum_direct_replays") == 896
        and capacity.get("no_further_capacity_escalation") is True
        and lifecycle == {"output_root":f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}","exact_ack":ACK,"default_is_inert":True,"requires_clean_pushed_main":True,"create_only":True}
        and frozen.get("speed_floor") is None
        and frozen.get("evidence_grade") == "C"
        and frozen.get("graph_q5ks_f16_serving_curve_cells_if_all_gates_pass") == 7
        and all(frozen.get(key) == 0 for key in ("graph_off_cells_authorized","other_quantization_cells_authorized","speculative_cells_authorized","tp2_or_tp4_cells_authorized","prefill_cells_authorized"))
        and frozen.get("headline_or_protected_replacement_authorized") is False
        and frozen.get("protected_decode_values") == [71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144]
    ):
        raise GateError("Q5_K_S cache64 graph curve overlay invariant failed")
    return value


def verify_base(overlay: dict[str, Any]) -> None:
    for name, row in overlay["dependencies"].items():
        path = resolve(row["path"])
        if not path.is_file() or sha256_file(path) != row["sha256"]:
            raise GateError(f"sealed Q5 graph curve dependency changed: {name}: {path}")
    off_terminal = load_json(resolve(overlay["dependencies"]["graph_off_terminal"]["path"]))
    off_result = load_json(resolve(overlay["dependencies"]["graph_off_result"]["path"]))
    sentinel = load_json(resolve(overlay["dependencies"]["cache20_sentinel_recovery"]["path"]))
    q4_prereg = load_json(resolve(overlay["dependencies"]["same_workload_cache64_prereg"]["path"]))
    q4_result = load_json(resolve(overlay["dependencies"]["same_workload_cache64_result"]["path"]))
    sg = sentinel.get("graph_counters", {}).get("candidate-graph-on-cache20", {})
    q4_20 = q4_prereg.get("preserved_r2_evidence", {}).get("graph_summary", {})
    q4_64 = q4_result.get("graph_mechanism") or {}
    if not (
        off_terminal.get("status") == "completed-valid-target-only-f16kv-depth-quality"
        and (off_terminal.get("authority") or {}).get("target_only_f16_serving_curve_cells") == 7
        and off_result.get("status") == "passed"
        and sentinel.get("classification") == "recovered-valid-mechanism-sentinel-original-procedural-failure-preserved"
        and (sentinel.get("authority") or {}).get("full_curve_preregistration") is True
        and sg.get("requested") == 146 and sg.get("cache_limit") == 20
        and sg.get("cache_hit") == sg.get("direct_replay") == 126 and sg.get("cache_full") == 0
        and q4_20.get("requested") == 1182 and q4_20.get("cache_limit") == 20
        and q4_20.get("direct_replay") == 471 and q4_20.get("cache_full") == 691
        and q4_result.get("status") == "passed" and q4_64.get("passed") is True
        and q4_64.get("requested") == 1182 and q4_64.get("cache_limit") == 64
        and q4_64.get("direct_replay") == 947 and q4_64.get("minimum_direct_replays") == 896
        and (q4_64.get("capacity_delta") or {}).get("source_supported_maximum") == 64
        and (q4_64.get("capacity_delta") or {}).get("no_further_capacity_escalation") is True
    ):
        raise GateError("graph-off, sentinel, or capacity-decision evidence changed")


def load_manifest() -> dict[str, Any]:
    overlay = load_overlay()
    verify_base(overlay)
    value = copy.deepcopy(BASE_VALUE)
    value["schema"] = "neural.download.qwen38-q5ks-f16kv-tp1-sycl-graph-cache64-depth-quality-effective.v1"
    value["campaign_id"] = CAMPAIGN_ID
    value["purpose"] = overlay["purpose"]
    value["graph_parent"] = copy.deepcopy(overlay["dependencies"])
    runtime = SENTINEL_VALUE["graph_runtime"]
    value["runtime"] = {
        "binary": runtime["binary"], "binary_sha256": runtime["binary_sha256"],
        "binary_size_bytes": runtime["binary_size_bytes"], "source_commit": runtime["source_base_head"],
        "graph_backend_sha256": runtime["graph_backend_sha256"],
        "effective_dso_count": runtime["effective_dso_count"],
        "effective_dso_canonical_sha256": runtime["effective_dso_canonical_sha256"],
        "patch_chain_sha256": copy.deepcopy(runtime["patch_chain_sha256"]),
        "effective_local_shared_libraries": [],
    }
    value["selectors"] = copy.deepcopy(overlay["selectors"])
    value["server_contract"].update({"port":19451,"model_alias":"qwen38-q5ks-f16kv-tp1-graph-cache64-depth-r1","graph":"SYCL cache64"})
    value["execution_contract"] = copy.deepcopy(overlay["execution_contract"])
    value["graph_acceptance"] = copy.deepcopy(overlay["graph_acceptance"])
    value["capacity_decision"] = copy.deepcopy(overlay["capacity_decision"])
    value["lifecycle"].update(overlay["lifecycle"])
    value["frozen_interpretation"] = copy.deepcopy(overlay["frozen_interpretation"])
    validate_manifest(value)
    return value


def validate_manifest(value: dict[str, Any]) -> None:
    overlay = load_overlay()
    if not (
        value.get("schema") == "neural.download.qwen38-q5ks-f16kv-tp1-sycl-graph-cache64-depth-quality-effective.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("model") == BASE_VALUE["model"]
        and value.get("selectors") == overlay["selectors"]
        and value.get("execution_contract") == overlay["execution_contract"]
        and value.get("graph_acceptance") == overlay["graph_acceptance"]
        and value.get("capacity_decision") == overlay["capacity_decision"]
        and value.get("server_contract", {}).get("cache_type_k") == "f16"
        and value.get("server_contract", {}).get("cache_type_v") == "f16"
        and value.get("server_contract", {}).get("spec_type") == "none"
        and value.get("runtime", {}).get("binary") == SENTINEL_VALUE["graph_runtime"]["binary"]
        and value.get("runtime", {}).get("binary_sha256") == SENTINEL_VALUE["graph_runtime"]["binary_sha256"]
        and value.get("runtime", {}).get("patch_chain_sha256") == SENTINEL_VALUE["graph_runtime"]["patch_chain_sha256"]
        and value.get("lifecycle", {}).get("output_root") == f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}"
        and value.get("lifecycle", {}).get("exact_ack") == ACK
        and value.get("frozen_interpretation") == overlay["frozen_interpretation"]
    ):
        raise GateError("effective Q5_K_S graph curve manifest invariant failed")


def merged_manifest(value: dict[str, Any]) -> dict[str, Any]:
    manifest = copy.deepcopy(GRAPH_TEMPLATE)
    manifest["campaign_id"] = CAMPAIGN_ID
    for key in ("model", "server_contract", "fixture", "clients", "lifecycle"):
        manifest[key] = copy.deepcopy(value[key])
    argv = manifest["server_argv"]
    for flag, replacement in {"-m":value["model"]["path"],"--alias":value["server_contract"]["model_alias"],"--port":str(value["server_contract"]["port"]),"-c":str(value["server_contract"]["context_capacity"])}.items():
        argv[argv.index(flag) + 1] = replacement
    if "-fit" not in argv:
        argv.extend(["-fit", "off"])
    manifest["environment"]["GGML_SYCL_ENABLE_GRAPH"] = "1"
    manifest["environment"]["GGML_SYCL_GRAPH_CACHE_SIZE"] = "64"
    manifest["zero_context_semantics"] = copy.deepcopy(ZERO_CONTEXT_SEMANTICS)
    return manifest


class Execution(GRAPH_EXECUTION):
    pass


def parse_graph_evidence(text: str) -> dict[str, int]:
    rows = [{key:int(item) for key,item in match.groupdict().items()} for match in SUMMARY_RE.finditer(text)]
    if len(rows) != 1:
        raise GateError(f"expected exactly one cache64 lifetime graph summary, observed {len(rows)}")
    row = rows[0]
    evidence = {**row, "summary_count": 1}
    if not (
        row["device"] == 0 and row["cache_limit"] == 64
        and row["requested"] == row["cache_hit"] + row["cache_miss"]
        and row["cache_hit"] == row["direct_replay"] >= 896
        and row["recorded"] == row["created"] == row["cache_entries"]
        and 1 <= row["cache_entries"] <= 64
        and row["replayed"] == row["cache_hit"] + row["created"]
        and row["cache_full"] == row["cache_miss"] - row["created"]
        and row["requested"] == row["replayed"] + row["cache_full"]
        and all(row[key] == 0 for key in ("compatibility_rejected","device_unsupported","updated","recreated"))
    ):
        raise GateError(f"full-curve cache64 graph evidence failed: {row}")
    return evidence


def compose_terminal_report(base_result: dict[str, Any], graph: dict[str, int], value: dict[str, Any]) -> dict[str, Any]:
    """Pure final-report composition, shared by preflight and validator."""
    result = copy.deepcopy(base_result)
    checks = result.get("checks")
    if not isinstance(checks, dict) or not checks or not isinstance(graph, dict):
        raise GateError("terminal report composition inputs are incomplete")
    passed = all(item is True for item in checks.values())
    result.update({
        "schema": "neural.download.qwen38-q5ks-f16kv-tp1-sycl-graph-cache64-depth-quality-terminal.v1",
        "campaign_id": CAMPAIGN_ID,
        "status": "completed-valid-q5ks-f16kv-graph-cache64-depth-quality" if passed else "failed-invalid-do-not-publish",
        "classification": "Grade C UD-Q5_K_S/F16-KV cache64 graph exact-depth serving curve with full Qwen3.8 quality battery" if passed else "invalid",
        "graph_evidence": copy.deepcopy(graph),
        "authority": {
            "graph_q5ks_f16_serving_curve_cells": 7 if passed else 0,
            "target_only_selectors": copy.deepcopy(value["selectors"]) if passed else None,
            "site_graph_q5ks_f16_curve_publication": passed,
            "graph_off_cells": 0, "other_quantization_cells": 0,
            "speculative_cells": 0, "tp2_or_tp4_cells": 0, "prefill_cells": 0,
            "protected_or_headline_replacement": False, "localmaxxing_submission": False,
        },
        "capacity_decision": copy.deepcopy(value["capacity_decision"]),
    })
    return result


def static_check(value: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(value)
    verify_base(load_overlay())
    BASE_STATIC_CHECK(BASE_VALUE)
    SENTINEL.static_check(SENTINEL_VALUE)
    source = Path(SENTINEL_VALUE["graph_runtime"]["source_path"]) / "ggml/src/ggml-sycl/ggml-sycl.cpp"
    if "std::min(g_ggml_sycl_graph_cache_size, 64)" not in source.read_text(encoding="utf-8"):
        raise GateError("sealed source cache maximum changed")
    merged = merged_manifest(value)
    argv = Execution(merged).server_argv()
    if not (
        argv[argv.index("--spec-type") + 1] == "none" and "--spec-draft-model" not in argv
        and argv[argv.index("-ctk") + 1] == "f16" and argv[argv.index("-ctv") + 1] == "f16"
        and argv[argv.index("-fit") + 1] == "off" and argv[argv.index("--port") + 1] == "19451"
        and merged["zero_context_semantics"] == ZERO_CONTEXT_SEMANTICS
        and merged["zero_context_semantics"].get("definition") == "zero prior active context before submitting the minimal explicit prompt token"
    ):
        raise GateError("effective Q5_K_S graph curve argv/report invariant failed")
    synthetic_graph = parse_graph_evidence("[SYCL-GRAPH] summary device=0 requested=1182 compatibility_rejected=0 device_unsupported=0 cache_entries=64 cache_limit=64 cache_hit=947 cache_miss=235 cache_full=171 direct_replay=947 recorded=64 created=64 updated=0 recreated=0 replayed=1011")
    synthetic_report = compose_terminal_report({"checks":{"base_validator":True,"graph_mechanism":True}},synthetic_graph,value)
    if not (synthetic_report["status"] == "completed-valid-q5ks-f16kv-graph-cache64-depth-quality" and synthetic_report["authority"]["graph_q5ks_f16_serving_curve_cells"] == 7 and synthetic_report["graph_evidence"] == synthetic_graph):
        raise GateError("terminal report composition preflight failed")
    return {"schema":"neural.download.qwen38-q5ks-f16kv-tp1-sycl-graph-cache64-depth-quality-plan.v1","mode":"check","default_is_inert":True,"gpu_actions":0,"network_requests":0,"output_writes":0,"campaign_id":CAMPAIGN_ID,"exact_ack":ACK,"arm":ARM,"fresh_server_lifetimes":1,"depths":list(DEPTHS),"quality_batteries":1,"graph_q5ks_f16_cells_if_valid":7,"speed_floor":None,"candidate_cache_limit":64,"minimum_direct_replays":896,"further_capacity_escalation":False,"report_composition_preflight":True,"server_argv":argv}


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
    run.acquire_locks()
    run.require_idle()
    if run.root.exists():
        raise GateError(f"create-only root exists: {run.root}")
    run.root.parent.mkdir(parents=True, exist_ok=True)
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
        CORE.write_json_x(run.root/"identity.json",{"campaign_id":CAMPAIGN_ID,"created_at_utc":dt.datetime.now(dt.UTC).isoformat(),"git_head":head,"origin_main":origin,"model":value["model"],"runtime":{**value["runtime"],"local_dsos":[]},"graph_runtime":SENTINEL_VALUE["graph_runtime"],"fixture":value["fixture"],"server_argv":{ARM:argv},"runtime_environment":{key:env[key] for key in ("ONEAPI_DEVICE_SELECTOR","GGML_SYCL_ENABLE_GRAPH","GGML_SYCL_GRAPH_CACHE_SIZE")},"parent":value["parent"],"graph_parent":value["graph_parent"],"capacity_decision":value["capacity_decision"]})
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
        CORE.write_json_x(terminal,{"schema":"neural.download.qwen38-q5ks-f16kv-tp1-sycl-graph-cache64-depth-quality-terminal.v1","campaign_id":CAMPAIGN_ID,"status":"failed-preserve-do-not-publish","error":error or f"cleanup failed: {cleanup}","authority":{"graph_q5ks_f16_serving_curve_cells":0,"other_cells":0,"protected_replacement":False}})
        raise GateError(error or f"cleanup failed: {cleanup}")
    with (run.root/"validator.stdout.json").open("xb") as stdout:
        subprocess.run([sys.executable,"-B",str(VALIDATOR),"--root",str(run.root),"--manifest",str(OVERLAY),"--output",str(terminal)],cwd=REPO,check=True,stdout=stdout)
    return terminal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--ack", default="")
    args = parser.parse_args()
    if args.check and args.execute:
        parser.error("choose --check or --execute")
    try:
        value = load_manifest()
        if not args.execute:
            print(json.dumps(static_check(value),indent=2,sort_keys=True))
            return 0
        if args.ack != ACK:
            raise GateError(f"exact --ack required: {ACK}")
        print(execute(value))
        return 0
    except (GateError,OSError,ValueError,json.JSONDecodeError,subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
