#!/usr/bin/env python3
"""Create-only embedded-Q8/Q8-KV TP1 graph-off MTP0-4 route sentinel."""

from __future__ import annotations

import argparse, copy, datetime as dt, importlib.util, json, os, re, subprocess, sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-r1-prereg.json"
VALIDATOR = LANE / "scripts/validate-20260825-qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-r1.py"
F16_RUNNER = LANE / "scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-r1.py"
CAMPAIGN_ID = "qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"; DEPTH = 8192; ROUTES = (0, 1, 2, 3, 4)
ARMS = {0: "control-mtp0", 1: "candidate-mtp1", 2: "candidate-mtp2", 3: "candidate-mtp3", 4: "candidate-mtp4"}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


F16 = load_module(F16_RUNNER, "qwen36_mtp124_f16_for_q8kv_route")
BASE = F16.BASE; CORE = F16.CORE; GateError = F16.GateError


def load_overlay() -> dict[str, Any]:
    value = json.loads(MANIFEST.read_text(encoding="utf-8")); validate_overlay(value); return value


def validate_overlay(value: dict[str, Any]) -> None:
    s, r, l, f = value.get("selectors") or {}, value.get("route_contract") or {}, value.get("lifecycle") or {}, value.get("frozen_interpretation") or {}
    if not (value.get("schema") == "neural.download.qwen36-llama-mtp-q8kv-route-8k-sentinel-prereg.v1" and value.get("campaign_id") == CAMPAIGN_ID and value.get("state") == "preregistered-not-launched" and s.get("route_mtp") == list(ROUTES) and s.get("active_context_tokens") == DEPTH and s.get("target_kv") == s.get("draft_kv") == "q8_0" and s.get("graph_mode") == "off" and r.get("arm_order") == [ARMS[n] for n in ROUTES] and r.get("candidate_failure_is_route_local") is True and r.get("control_failure_invalidates_all") is True and l.get("output_root") == "/mnt/fast-ai/bench-results/qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-20260825-r1" and l.get("exact_ack") == ACK and l.get("default_is_inert") is True and f.get("site_publication_authorized") is False and f.get("graph_claim_authorized") is False and f.get("headline_or_protected_replacement_authorized") is False):
        raise GateError("Q8-KV route overlay invariant failed")


def merged_manifest(value: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(F16.merged_manifest(F16.load_overlay()))
    for key in ("schema", "campaign_id", "state", "purpose", "parents", "selectors", "sealed_8k_target_output_sha256", "server_contract", "route_contract", "lifecycle", "frozen_interpretation"):
        merged[key] = copy.deepcopy(value[key])
    return merged


def verify_parents(value: dict[str, Any]) -> None:
    f16, q8 = value["parents"]["successful_f16_expansion"], value["parents"]["q8kv_target_only"]
    refs = ((f16["manifest"], f16["manifest_sha256"]), (f16["runner"], f16["runner_sha256"]), (f16["validator"], f16["validator_sha256"]), (f16["terminal"], f16["terminal_sha256"]), (q8["preregistration"], q8["preregistration_sha256"]), (q8["result"], q8["result_sha256"]))
    for raw, expected in refs:
        path = Path(raw) if Path(raw).is_absolute() else REPO / raw
        if not path.is_file() or F16.ROUTE_R2.sha256_file(path) != expected: raise GateError(f"parent changed: {path}")
    ft = CORE.load_json(Path(f16["terminal"])); qr = CORE.load_json(REPO / q8["result"])
    if not (ft.get("status") == f16["required_status"] and ft.get("screen_gate", {}).get("passed") is True and ft.get("authority", {}).get("candidate_routes_with_seven_quality-complete_cells_if_reviewed") == f16["required_quality_complete_routes"] and qr.get("status") == q8["required_status"] and all(qr.get("selectors", {}).get(k) == v for k, v in q8["required_selectors"].items()) and len(qr.get("cells", [])) == 7):
        raise GateError("parent result invariant failed")


def static_check(value: dict[str, Any]) -> dict[str, Any]:
    validate_overlay(value); verify_parents(value); F16.static_check(F16.load_overlay())
    return {"schema": "neural.download.qwen36-llama-mtp-q8kv-route-8k-plan.v1", "mode": "check", "default_is_inert": True, "gpu_actions": 0, "network_requests": 0, "output_writes": 0, "campaign_id": CAMPAIGN_ID, "exact_ack": ACK, "active_context_tokens": DEPTH, "arms": [ARMS[n] for n in ROUTES], "fresh_server_lifetimes": 5, "target_kv": "q8_0", "draft_kv": "q8_0"}


def replace_flag(argv: list[str], flag: str, value: str) -> None:
    try: argv[argv.index(flag) + 1] = value
    except (ValueError, IndexError) as exc: raise GateError(f"missing inherited flag {flag}") from exc


class Execution(F16.Execution):
    def server_argv_for_mtp(self, mtp: int) -> list[str]:
        argv = super().server_argv_for_mtp(mtp)
        replace_flag(argv, "-ctk", "q8_0"); replace_flag(argv, "-ctv", "q8_0")
        if mtp > 0:
            replace_flag(argv, "--spec-draft-type-k", "q8_0"); replace_flag(argv, "--spec-draft-type-v", "q8_0")
        return argv


def execute(value: dict[str, Any]) -> Path:
    validate_overlay(value); verify_parents(value); manifest = merged_manifest(value)
    unexpected = [n for n in os.environ if n.startswith(("GGML_", "SYCL_", "ZE_", "ZES_", "UR_", "ONEAPI_DEVICE_SELECTOR", "LLAMA_ARG_")) or n == "LD_PRELOAD"]
    if unexpected: raise GateError("unexpected inherited runtime environment: " + ",".join(sorted(unexpected)))
    subprocess.run(["git", "fetch", "origin", "main", "--quiet"], cwd=REPO, check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(); origin = subprocess.check_output(["git", "rev-parse", "origin/main"], cwd=REPO, text=True).strip()
    if head != origin or subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip(): raise GateError("execution requires clean pushed main")
    run = Execution(manifest); run.acquire_locks(); run.require_idle()
    if run.root.exists(): raise GateError(f"create-only root exists: {run.root}")
    run.root.parent.mkdir(parents=True, exist_ok=True)
    if subprocess.check_output(["findmnt", "-no", "FSTYPE", "--target", str(run.root.parent)], text=True).strip() != "ext4": raise GateError("run-root parent must be ext4")
    run.root.mkdir(); current_arm: str | None = None
    try:
        model, runtime = manifest["model"], manifest["runtime"]; CORE.verify_file(Path(model["path"]), model["sha256"], model["size_bytes"]); static_check(value)
        env = CORE.oneapi_environment(Path(runtime["binary"]).parent); version = subprocess.check_output([runtime["binary"], "--version"], env=env, stderr=subprocess.STDOUT, text=True).strip()
        if runtime["reported_version"] not in version.splitlines(): raise GateError("runtime version drift")
        ldd = subprocess.check_output(["ldd", runtime["binary"]], env=env, text=True); captured = []
        for row in runtime["effective_local_shared_libraries"]:
            match = re.search(rf"^\s*{re.escape(row['soname'])}\s+=>\s+(\S+)", ldd, re.M)
            if not match or str(Path(match.group(1)).resolve()) != str(Path(row["path"]).resolve()): raise GateError(f"ldd closure mismatch: {row['soname']}")
            captured.append(row)
        local_names = sorted({line.split()[0] for line in ldd.splitlines() if " => " in line and line.split()[2].startswith(str(Path(runtime["binary"]).parent) + "/")})
        if local_names != sorted(row["soname"] for row in captured): raise GateError("unexpected runtime-origin DSO")
        argv_by_arm = {ARMS[m]: run.server_argv_for_mtp(m) for m in ROUTES}
        identity = {"campaign_id": CAMPAIGN_ID, "created_at_utc": dt.datetime.now(dt.UTC).isoformat(), "git_head": head, "origin_main": origin, "model": {k: model[k] for k in ("path", "size_bytes", "sha256", "repository", "revision")}, "runtime": {"binary": runtime["binary"], "binary_sha256": runtime["binary_sha256"], "manifest_sha256": runtime["manifest_sha256"], "source_commit": runtime["source_commit"], "local_dsos": captured, "ldd": ldd.splitlines()}, "fixture_sha256": manifest["fixture"]["sha256"], "server_argv": argv_by_arm, "runtime_environment": {k: env[k] for k in ("ONEAPI_DEVICE_SELECTOR", "ZE_AFFINITY_MASK", "GGML_SYCL_ENABLE_GRAPH", "GGML_SYCL_GRAPH_CACHE_SIZE")}, "parent_hashes": {"f16_terminal": value["parents"]["successful_f16_expansion"]["terminal_sha256"], "q8kv_target_result": value["parents"]["q8kv_target_only"]["result_sha256"]}}
        CORE.write_json_x(run.root / "identity.json", identity)
        for mtp in ROUTES:
            arm = ARMS[mtp]; current_arm = arm; run.require_idle(); error = None
            try: run.start(arm, argv_by_arm[arm], env); run.run_depth(arm, DEPTH, mtp > 0)
            except BaseException as exc: error = f"{type(exc).__name__}: {exc}"
            finally: cleanup = run.stop(arm)
            clean = cleanup == {"forced_kill": False, "port_closed": True, "render_node_idle": True, "server_survivor": False}
            CORE.write_json_x(run.root / arm / "arm-result.json", {"status": "completed-awaiting-validation" if error is None and clean else "failed-preserve", "error": error, "cleanup": cleanup}); current_arm = None
            if mtp == 0 and (error is not None or not clean): raise GateError("q8-KV MTP0 control failed")
        terminal = run.root / "terminal-receipt.json"
        with (run.root / "validator.stdout.json").open("xb") as stdout: subprocess.run([sys.executable, "-B", str(VALIDATOR), "--root", str(run.root), "--manifest", str(MANIFEST), "--output", str(terminal)], cwd=REPO, check=True, stdout=stdout)
        return terminal
    except BaseException as exc:
        if run.proc is not None and current_arm is not None:
            try: run.stop(current_arm)
            except Exception: pass
        terminal = run.root / "terminal-receipt.json"
        if not terminal.exists(): CORE.write_json_x(terminal, {"schema": "neural.download.qwen36-llama-mtp-q8kv-route-8k-terminal.v1", "campaign_id": CAMPAIGN_ID, "status": "failed-preserve-do-not-expand", "error": f"{type(exc).__name__}: {exc}", "authority": {"curve_expansion_routes": [], "site_publication": False, "protected_replacement": False}})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); parser.add_argument("--execute", action="store_true"); parser.add_argument("--ack", default=""); args = parser.parse_args()
    if args.check and args.execute: parser.error("choose --check or --execute")
    try:
        value = load_overlay()
        if not args.execute: print(json.dumps(static_check(value), indent=2, sort_keys=True)); return 0
        if args.ack != ACK: raise GateError(f"exact --ack required: {ACK}")
        print(execute(value)); return 0
    except (GateError, OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc: parser.error(str(exc))
    return 2


if __name__ == "__main__": raise SystemExit(main())
