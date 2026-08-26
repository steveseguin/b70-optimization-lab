#!/usr/bin/env python3
"""Create-only combined embedded-Q8/F16 MTP1/2/4 exact-depth quality run."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-r1-prereg.json"
VALIDATOR = LANE / "scripts/validate-20260825-qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-r1.py"
ROUTE_R2_RUNNER = LANE / "scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r2.py"
CAMPAIGN_ID = "qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
DEPTHS = (0, 2048, 4096, 8192, 16384, 24576, 32768)
ROUTES = (0, 1, 2, 4)
ARMS = {0: "control-mtp0", 1: "candidate-mtp1", 2: "candidate-mtp2", 4: "candidate-mtp4"}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ROUTE_R2 = load_module(ROUTE_R2_RUNNER, "qwen36_mtp_route_r2_for_mtp124_curve")
BASE = ROUTE_R2.BASE
R3 = BASE.PARENT
CORE = R3.BASE
GateError = BASE.GateError


def load_overlay() -> dict[str, Any]:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError("manifest must be an object")
    validate_overlay(value)
    return value


def validate_overlay(value: dict[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    execution = value.get("execution_contract") or {}
    lifecycle = value.get("lifecycle") or {}
    frozen = value.get("frozen_interpretation") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-mtp124-exact-depth-quality-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors.get("candidate_mtp") == [1, 2, 4]
        and selectors.get("control_mtp") == 0
        and selectors.get("active_context_tokens") == list(DEPTHS)
        and selectors.get("target_kv") == selectors.get("draft_kv") == "f16"
        and selectors.get("graph_mode") == "off"
        and execution.get("arm_order") == [ARMS[n] for n in ROUTES]
        and execution.get("quality_battery_per_candidate") is True
        and execution.get("candidate_failure_is_route_local") is True
        and execution.get("control_failure_invalidates_all") is True
        and lifecycle.get("output_root") == "/mnt/fast-ai/bench-results/qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-20260825-r1"
        and lifecycle.get("exact_ack") == ACK
        and lifecycle.get("default_is_inert") is True
        and frozen.get("speed_floor") is None
        and frozen.get("site_publication_authorized") is False
        and frozen.get("graph_claim_authorized") is False
        and frozen.get("headline_or_protected_replacement_authorized") is False
    ):
        raise GateError("MTP124 expansion overlay invariant failed")


def r3_manifest() -> dict[str, Any]:
    return R3.merge_manifest(R3.load_overlay())


def merged_manifest(value: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(r3_manifest())
    for key in (
        "schema", "campaign_id", "state", "purpose", "parents", "selectors",
        "sealed_target_output_hashes", "server_contract", "execution_contract",
        "lifecycle", "frozen_interpretation",
    ):
        merged[key] = copy.deepcopy(value[key])
    merged["arms"] = [
        {"id": ARMS[mtp], "mtp": mtp, "spec_type": "none" if mtp == 0 else "draft-mtp",
         "workload": "seven exact-depth completions" if mtp == 0 else "seven exact-depth completions followed by its own full quality battery"}
        for mtp in ROUTES
    ]
    return merged


def verify_parents(value: dict[str, Any]) -> None:
    parents = value["parents"]
    r3 = parents["sealed_mtp3_r3_result"]
    route = parents["route_screen_r2"]
    refs = (
        (r3["path"], r3["sha256"], "sealed MTP3 R3 result"),
        (r3["raw_terminal"], r3["raw_terminal_sha256"], "MTP3 R3 terminal"),
        (route["manifest"], route["manifest_sha256"], "route R2 manifest"),
        (route["runner"], route["runner_sha256"], "route R2 runner"),
        (route["validator"], route["validator_sha256"], "route R2 validator"),
        (route["raw_terminal"], route["raw_terminal_sha256"], "route R2 terminal"),
    )
    for raw, expected, label in refs:
        path = Path(raw) if Path(raw).is_absolute() else REPO / raw
        if not path.is_file() or ROUTE_R2.sha256_file(path) != expected:
            raise GateError(f"{label} changed: {path}")
    r3_result = CORE.load_json(REPO / r3["path"])
    result_hashes = {str(row["active_context_tokens"]): row["output_token_ids_sha256"] for row in r3_result.get("cells", [])}
    route_terminal = CORE.load_json(Path(route["raw_terminal"]))
    if not (
        r3_result.get("classification") == "quality-battery-certified-family-research-profile"
        and result_hashes == value["sealed_target_output_hashes"]
        and route_terminal.get("status") == route["required_status"]
        and route_terminal.get("screen_gate", {}).get("passed") is True
        and route_terminal.get("authority", {}).get("candidate_routes_eligible_for_separately_preregistered_curve") == route["required_eligible_routes"]
    ):
        raise GateError("parent result invariant failed")


def static_check(value: dict[str, Any]) -> dict[str, Any]:
    validate_overlay(value)
    verify_parents(value)
    R3.BASE.static_check(r3_manifest())
    return {
        "schema": "neural.download.qwen36-llama-mtp124-exact-depth-quality-plan.v1",
        "mode": "check", "default_is_inert": True,
        "gpu_actions": 0, "network_requests": 0, "output_writes": 0,
        "campaign_id": CAMPAIGN_ID, "exact_ack": ACK,
        "depths": list(DEPTHS), "arms": [ARMS[n] for n in ROUTES],
        "fresh_server_lifetimes": 4, "candidate_quality_batteries": 3,
    }


class Execution(BASE.Execution):
    pass


def execute(value: dict[str, Any]) -> Path:
    validate_overlay(value)
    verify_parents(value)
    manifest = merged_manifest(value)
    unexpected = [name for name in os.environ if name.startswith(("GGML_", "SYCL_", "ZE_", "ZES_", "UR_", "ONEAPI_DEVICE_SELECTOR", "LLAMA_ARG_")) or name == "LD_PRELOAD"]
    if unexpected:
        raise GateError("unexpected inherited runtime environment: " + ",".join(sorted(unexpected)))
    subprocess.run(["git", "fetch", "origin", "main", "--quiet"], cwd=REPO, check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    origin = subprocess.check_output(["git", "rev-parse", "origin/main"], cwd=REPO, text=True).strip()
    if head != origin or subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip():
        raise GateError("execution requires clean pushed main")
    run = Execution(manifest)
    run.acquire_locks(); run.require_idle()
    if run.root.exists():
        raise GateError(f"create-only root exists: {run.root}")
    run.root.parent.mkdir(parents=True, exist_ok=True)
    if subprocess.check_output(["findmnt", "-no", "FSTYPE", "--target", str(run.root.parent)], text=True).strip() != "ext4":
        raise GateError("run-root parent must be ext4")
    run.root.mkdir()
    current_arm: str | None = None
    try:
        model, runtime = manifest["model"], manifest["runtime"]
        CORE.verify_file(Path(model["path"]), model["sha256"], model["size_bytes"])
        static_check(value)
        env = CORE.oneapi_environment(Path(runtime["binary"]).parent)
        version = subprocess.check_output([runtime["binary"], "--version"], env=env, stderr=subprocess.STDOUT, text=True).strip()
        if runtime["reported_version"] not in version.splitlines():
            raise GateError("runtime version drift")
        if "draft-mtp" not in subprocess.check_output([runtime["binary"], "--help"], env=env, stderr=subprocess.STDOUT, text=True):
            raise GateError("runtime lacks draft-mtp")
        ldd = subprocess.check_output(["ldd", runtime["binary"]], env=env, text=True)
        captured = []
        for row in runtime["effective_local_shared_libraries"]:
            match = re.search(rf"^\s*{re.escape(row['soname'])}\s+=>\s+(\S+)", ldd, re.M)
            if not match or str(Path(match.group(1)).resolve()) != str(Path(row["path"]).resolve()):
                raise GateError(f"ldd closure mismatch: {row['soname']}")
            captured.append(row)
        local_names = sorted({line.split()[0] for line in ldd.splitlines() if " => " in line and line.split()[2].startswith(str(Path(runtime["binary"]).parent) + "/")})
        if local_names != sorted(row["soname"] for row in captured):
            raise GateError("unexpected runtime-origin DSO")
        argv_by_arm = {ARMS[mtp]: run.server_argv_for_mtp(mtp) for mtp in ROUTES}
        identity = {
            "campaign_id": CAMPAIGN_ID, "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "git_head": head, "origin_main": origin,
            "model": {key: model[key] for key in ("path", "size_bytes", "sha256", "repository", "revision")},
            "runtime": {"binary": runtime["binary"], "binary_sha256": runtime["binary_sha256"], "manifest": runtime["manifest"], "manifest_sha256": runtime["manifest_sha256"], "source_commit": runtime["source_commit"], "version": version, "local_dsos": captured, "ldd": ldd.splitlines()},
            "fixture_sha256": manifest["fixture"]["sha256"], "server_argv": argv_by_arm,
            "runtime_environment": {key: env[key] for key in ("ONEAPI_DEVICE_SELECTOR", "ZE_AFFINITY_MASK", "GGML_SYCL_ENABLE_GRAPH", "GGML_SYCL_GRAPH_CACHE_SIZE", "GGML_SYCL_ENABLE_DNN", "GGML_SYCL_ENABLE_OPT", "GGML_SYCL_ENABLE_VMM")},
            "parent_hashes": {"mtp3_r3_result": value["parents"]["sealed_mtp3_r3_result"]["sha256"], "route_r2_terminal": value["parents"]["route_screen_r2"]["raw_terminal_sha256"]},
        }
        CORE.write_json_x(run.root / "identity.json", identity)
        for mtp in ROUTES:
            arm = ARMS[mtp]; current_arm = arm; run.require_idle(); arm_error: str | None = None
            try:
                run.start(arm, argv_by_arm[arm], env)
                for depth in DEPTHS:
                    run.run_depth(arm, depth, mtp > 0)
                if mtp > 0:
                    q = manifest["clients"]["quality"]
                    command = [q["interpreter"], "-I", "-B", str(CORE.referenced_path(q["path"])), "--base-url", f"http://127.0.0.1:{run.port}", "--model", manifest["server_contract"]["model_alias"], "--tokenizer", q["tokenizer_path"], "--timeout", str(manifest["lifecycle"]["request_timeout_seconds"]), "--repeat-runs", str(q["repeat_runs"]), "--long-context-tokens", str(q["long_context_tokens"]), "--request-id-prefix", f"qwen36-mtpq8-mtp{mtp}-depth-quality-r1", "--output-json", str(run.root / arm / "quality.json")]
                    with (run.root / arm / "quality.stdout.json").open("xb") as stdout, (run.root / arm / "quality.stderr.log").open("xb") as stderr:
                        subprocess.run(command, cwd=REPO, check=True, stdout=stdout, stderr=stderr)
            except BaseException as exc:
                arm_error = f"{type(exc).__name__}: {exc}"
            finally:
                cleanup = run.stop(arm)
            passed_cleanup = cleanup == {"forced_kill": False, "port_closed": True, "render_node_idle": True, "server_survivor": False}
            CORE.write_json_x(run.root / arm / "arm-result.json", {"status": "completed-awaiting-validation" if arm_error is None and passed_cleanup else "failed-preserve", "error": arm_error, "cleanup": cleanup})
            current_arm = None
            if mtp == 0 and (arm_error is not None or not passed_cleanup):
                raise GateError("fresh MTP0 control failed; all candidate authority invalid")
        terminal = run.root / "terminal-receipt.json"
        with (run.root / "validator.stdout.json").open("xb") as stdout:
            subprocess.run([sys.executable, "-B", str(VALIDATOR), "--root", str(run.root), "--manifest", str(MANIFEST), "--output", str(terminal)], cwd=REPO, check=True, stdout=stdout)
        return terminal
    except BaseException as exc:
        if run.proc is not None and current_arm is not None:
            try: run.stop(current_arm)
            except Exception: pass
        terminal = run.root / "terminal-receipt.json"
        if not terminal.exists():
            CORE.write_json_x(terminal, {"schema": "neural.download.qwen36-llama-mtp124-exact-depth-quality-terminal.v1", "campaign_id": CAMPAIGN_ID, "created_at_utc": dt.datetime.now(dt.UTC).isoformat(), "status": "failed-preserve-do-not-publish", "error": f"{type(exc).__name__}: {exc}", "authority": {"family_cells_if_reviewed": {}, "site_publication": False, "protected_replacement": False}})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); parser.add_argument("--execute", action="store_true"); parser.add_argument("--ack", default="")
    args = parser.parse_args()
    if args.check and args.execute: parser.error("choose --check or --execute")
    try:
        value = load_overlay()
        if not args.execute:
            print(json.dumps(static_check(value), indent=2, sort_keys=True)); return 0
        if args.ack != ACK: raise GateError(f"exact --ack required: {ACK}")
        print(execute(value)); return 0
    except (GateError, OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
