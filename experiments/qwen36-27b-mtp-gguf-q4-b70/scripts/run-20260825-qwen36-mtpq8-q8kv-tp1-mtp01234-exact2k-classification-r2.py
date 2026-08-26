#!/usr/bin/env python3
"""Create-only Q8-KV MTP0-4 exact-2K repeat classification packet."""

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
import time
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r2-prereg.json"
VALIDATOR = LANE / "scripts/validate-20260825-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r2.py"
R1_RUNNER = LANE / "scripts/run-20260825-qwen36-mtpq8-q8kv-tp1-mtp1234-exact-depth-quality-r1.py"
CAMPAIGN_ID = "qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-20260825-r2"
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-20260825-r2")
ACK = f"RUN {CAMPAIGN_ID}"
PORT = 19438
DEPTH = 2048
REPEATS = (1, 2, 3)
ROUTES = (0, 1, 2, 3, 4)
ARMS = {0: "control-mtp0", 1: "candidate-mtp1", 2: "candidate-mtp2", 3: "candidate-mtp3", 4: "candidate-mtp4"}
ARM_PLAN = (("control-mtp0a", 0), ("candidate-mtp1", 1), ("candidate-mtp2", 2), ("candidate-mtp3", 3), ("candidate-mtp4", 4), ("control-mtp0b", 0))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R1 = load_module(R1_RUNNER, "qwen36_q8kv_full_r1_for_exact2k_classification")
CORE = R1.CORE
GateError = R1.BASE.GateError


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def load_manifest() -> dict[str, Any]:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    validate_manifest(value)
    return value


def validate_manifest(value: dict[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    execution = value.get("execution_contract") or {}
    lifecycle = value.get("lifecycle") or {}
    frozen = value.get("frozen_interpretation") or {}
    grades = frozen.get("packet_grade_mapping") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-mtp01234-q8kv-exact2k-classification-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors.get("mtp") == list(ROUTES)
        and selectors.get("active_context_tokens") == DEPTH
        and selectors.get("target_kv") == selectors.get("draft_kv") == "q8_0"
        and selectors.get("graph_mode") == "off"
        and selectors.get("completion_tokens") == 128
        and selectors.get("uncached_repeats_per_arm") == len(REPEATS)
        and execution.get("arm_order") == [arm for arm, _ in ARM_PLAN]
        and execution.get("requests_per_arm") == 3
        and execution.get("total_requests") == 18
        and execution.get("fresh_server_lifetime_per_arm") is True
        and execution.get("same_frozen_2k_fixture_for_every_request") is True
        and execution.get("request_cache_disabled") is True
        and execution.get("capture_full_token_ids") is True
        and execution.get("compare_within_arm_repeat_hashes") is True
        and execution.get("compare_cross_arm_token_ids_and_first_divergence") is True
        and execution.get("candidate_draft_counter_conservation_required") is True
        and execution.get("cache_zero_required") is True
        and execution.get("clean_shutdown_required") is True
        and execution.get("whitespace_tolerant_ldd") is True
        and execution.get("no_quality_battery") is True
        and execution.get("no_speed_gate") is True
        and lifecycle.get("output_root") == str(RUN_ROOT)
        and lifecycle.get("port") == PORT
        and lifecycle.get("exact_ack") == ACK
        and lifecycle.get("default_is_inert") is True
        and lifecycle.get("create_only") is True
        and grades.get("A", "").startswith("unreachable")
        and grades.get("B", "").startswith("all routes exact-repeat-stable")
        and grades.get("C", "").startswith("valid repeat-stable evidence")
        and grades.get("D", "").startswith("temporal-control-drift")
        and frozen.get("prior_q8kv_control_hash_is_observation_not_oracle") == "e11b5a317688e28bf0cd4b1e1d234b72327feb06a435357ef846acc5344a620d"
        and frozen.get("site_cells_authorized") == 0
        and frozen.get("site_publication_authorized") is False
        and frozen.get("curve_expansion_authorized") is False
        and frozen.get("speed_claim_authorized") is False
        and frozen.get("graph_claim_authorized") is False
        and frozen.get("headline_or_protected_replacement_authorized") is False
        and frozen.get("localmaxxing_submission_authorized") is False
        and frozen.get("post_hoc_grade_changes_authorized") is False
    ):
        raise GateError("exact-2K classification manifest invariant failed")


def verify_failed_r1(value: dict[str, Any]) -> None:
    parent = value["failed_r1_parent"]
    for entry in parent["tracked"].values():
        path = REPO / entry["path"]
        if not path.is_file() or sha256_file(path) != entry["sha256"]:
            raise GateError(f"tracked R1 parent changed: {path}")
    root = Path(parent["root"])
    for relative, expected in parent["raw"].items():
        path = root / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise GateError(f"raw R1 parent changed: {path}")
    terminal = json.loads((root / "terminal-receipt.json").read_text(encoding="utf-8"))
    observed = {}
    for route in ROUTES:
        receipt = json.loads((root / ARMS[route] / "depth-2048/exact-depth.json").read_text(encoding="utf-8"))
        observed[ARMS[route]] = receipt["response"]["output_token_ids_sha256"]
    if not (
        terminal.get("campaign_id") == parent["campaign_id"]
        and terminal.get("status") == parent["required_status"]
        and terminal.get("authority", {}).get("site_publication") is False
        and observed == parent["observed_2k_output_hashes"]
    ):
        raise GateError("failed R1 terminal or exact-2K observation changed")


def runtime_manifest(value: dict[str, Any]) -> dict[str, Any]:
    base = R1.merged_manifest(R1.load_overlay())
    merged = copy.deepcopy(base)
    merged["schema"] = value["schema"]
    merged["campaign_id"] = CAMPAIGN_ID
    merged["purpose"] = value["purpose"]
    merged["selectors"] = copy.deepcopy(value["selectors"])
    merged["execution_contract"] = copy.deepcopy(value["execution_contract"])
    merged["frozen_interpretation"] = copy.deepcopy(value["frozen_interpretation"])
    merged["lifecycle"]["output_root"] = str(RUN_ROOT)
    merged["lifecycle"]["exact_ack"] = ACK
    merged["server_contract"]["port"] = PORT
    merged["server_contract"]["model_alias"] = "qwen36-mtpq8-q8kv-tp1-exact2k-classification-r2"
    return merged


def verify_ldd_closure(ldd: str, runtime: dict[str, Any]) -> list[dict[str, Any]]:
    captured = []
    for row in runtime["effective_local_shared_libraries"]:
        match = re.search(rf"^\s*{re.escape(row['soname'])}\s+=>\s+(\S+)", ldd, re.M)
        if not match or str(Path(match.group(1)).resolve()) != str(Path(row["path"]).resolve()):
            raise GateError(f"ldd closure mismatch: {row['soname']}")
        captured.append(row)
    local_names = sorted({
        line.split()[0] for line in ldd.splitlines()
        if " => " in line and line.split()[2].startswith(str(Path(runtime["binary"]).parent) + "/")
    })
    if local_names != sorted(row["soname"] for row in captured):
        raise GateError("unexpected runtime-origin DSO")
    return captured


def static_check(value: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(value)
    verify_failed_r1(value)
    R1.static_check(R1.load_overlay())
    merged = runtime_manifest(value)
    execution = R1.Execution(merged)
    argv = {arm: execution.server_argv_for_mtp(route) for arm, route in ARM_PLAN}
    for arm, route in ARM_PLAN:
        args = argv[arm]
        if not (args[args.index("-ctk") + 1] == args[args.index("-ctv") + 1] == "q8_0"):
            raise GateError("target Q8-KV argv drift")
        if route > 0 and not (
            args[args.index("--spec-draft-type-k") + 1]
            == args[args.index("--spec-draft-type-v") + 1]
            == "q8_0"
        ):
            raise GateError("draft Q8-KV argv drift")
    return {
        "schema": "neural.download.qwen36-llama-mtp01234-q8kv-exact2k-classification-plan.v1",
        "mode": "check",
        "default_is_inert": True,
        "gpu_actions": 0,
        "network_requests": 0,
        "output_writes": 0,
        "campaign_id": CAMPAIGN_ID,
        "exact_ack": ACK,
        "active_context_tokens": DEPTH,
        "repeats_per_arm": len(REPEATS),
        "total_requests": len(REPEATS) * len(ARM_PLAN),
        "fresh_server_lifetimes": len(ARM_PLAN),
        "arms": [arm for arm, _ in ARM_PLAN],
        "site_cells_authorized": 0,
    }


def run_repeat(run: Any, manifest: dict[str, Any], arm: str, route: int, repeat: int) -> None:
    directory = run.root / arm / f"repeat-{repeat}"
    directory.mkdir()
    candidate = route > 0
    before = len(CORE.acceptance_rows(run.root / arm / "server.log")) if candidate else 0
    client = CORE.referenced_path(manifest["clients"]["exact_depth"]["path"])
    fixture = CORE.referenced_path(manifest["fixture"]["path"])
    command = [
        sys.executable, "-B", str(client), "--execute",
        "--fixture", str(fixture), "--depth", str(DEPTH),
        "--case-id", f"q8kv-exact2k-mtp{route}-repeat-{repeat}",
        "--context-capacity", str(manifest["server_contract"]["context_capacity"]),
        "--base-url", f"http://127.0.0.1:{run.port}",
        "--model", manifest["server_contract"]["model_alias"],
        "--response-adapter", "llama-server",
        "--timeout", str(manifest["lifecycle"]["request_timeout_seconds"]),
        "--out", str(directory / "exact-depth.json"),
    ]
    with (directory / "exact-depth.stdout.json").open("xb") as stdout:
        subprocess.run(command, cwd=REPO, check=True, stdout=stdout)
    if candidate:
        deadline = time.monotonic() + 30
        rows = CORE.acceptance_rows(run.root / arm / "server.log")
        while len(rows) <= before and time.monotonic() < deadline:
            time.sleep(0.2)
            rows = CORE.acceptance_rows(run.root / arm / "server.log")
        CORE.write_json_x(directory / "draft-counters.json", {
            "active_context_tokens": DEPTH,
            "repeat": repeat,
            "rows_before": before,
            "rows_after": len(rows),
            "new_rows": rows[before:],
        })


def execute(value: dict[str, Any]) -> Path:
    validate_manifest(value)
    verify_failed_r1(value)
    manifest = runtime_manifest(value)
    unexpected = [
        name for name in os.environ
        if name.startswith(("GGML_", "SYCL_", "ZE_", "ZES_", "UR_", "ONEAPI_DEVICE_SELECTOR", "LLAMA_ARG_"))
        or name == "LD_PRELOAD"
    ]
    if unexpected:
        raise GateError("unexpected inherited runtime environment: " + ",".join(sorted(unexpected)))
    subprocess.run(["git", "fetch", "origin", "main", "--quiet"], cwd=REPO, check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    origin = subprocess.check_output(["git", "rev-parse", "origin/main"], cwd=REPO, text=True).strip()
    if head != origin or subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip():
        raise GateError("execution requires clean pushed main")
    run = R1.Execution(manifest)
    run.acquire_locks()
    run.require_idle()
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
        captured = verify_ldd_closure(ldd, runtime)
        argv_by_arm = {arm: run.server_argv_for_mtp(route) for arm, route in ARM_PLAN}
        env_keys = (
            "ONEAPI_DEVICE_SELECTOR", "ZE_AFFINITY_MASK", "ZES_ENABLE_SYSMAN",
            "UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS", "GGML_SYCL_ENABLE_VMM",
            "GGML_SYCL_ENABLE_GRAPH", "GGML_SYCL_GRAPH_CACHE_SIZE",
            "GGML_SYCL_ENABLE_DNN", "GGML_SYCL_ENABLE_OPT", "GGML_SYCL_FA_ONEDNN",
            "GGML_SYCL_FA_ONEDNN_MAX_KV", "GGML_SYCL_ENABLE_MKL_FA",
            "GGML_SYCL_ENABLE_FLASH_ATTN", "NO_PROXY", "no_proxy",
        )
        identity = {
            "campaign_id": CAMPAIGN_ID,
            "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "git_head": head,
            "origin_main": origin,
            "model": {key: model[key] for key in ("path", "size_bytes", "sha256", "repository", "revision")},
            "runtime": {
                "binary": runtime["binary"], "binary_sha256": runtime["binary_sha256"],
                "manifest": runtime["manifest"], "manifest_sha256": runtime["manifest_sha256"],
                "source_commit": runtime["source_commit"], "version": version,
                "local_dsos": captured, "ldd": ldd.splitlines(),
            },
            "fixture_sha256": manifest["fixture"]["sha256"],
            "server_argv": argv_by_arm,
            "runtime_environment": {key: env[key] for key in env_keys},
            "explicitly_unset_environment": [
                "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"
            ],
            "failed_r1_parent_hashes": {
                "terminal": value["failed_r1_parent"]["raw"]["terminal-receipt.json"],
                "identity": value["failed_r1_parent"]["raw"]["identity.json"],
            },
        }
        CORE.write_json_x(run.root / "identity.json", identity)
        for arm, route in ARM_PLAN:
            current_arm = arm
            run.require_idle()
            arm_error: str | None = None
            try:
                run.start(arm, argv_by_arm[arm], env)
                for repeat in REPEATS:
                    run_repeat(run, manifest, arm, route, repeat)
            except BaseException as exc:
                arm_error = f"{type(exc).__name__}: {exc}"
            finally:
                cleanup = run.stop(arm)
            passed_cleanup = cleanup == {
                "forced_kill": False, "port_closed": True,
                "render_node_idle": True, "server_survivor": False,
            }
            CORE.write_json_x(run.root / arm / "arm-result.json", {
                "status": "completed-awaiting-classification" if arm_error is None and passed_cleanup else "failed-preserve",
                "error": arm_error,
                "cleanup": cleanup,
            })
            current_arm = None
        terminal = run.root / "terminal-receipt.json"
        with (run.root / "validator.stdout.json").open("xb") as stdout:
            subprocess.run([
                sys.executable, "-B", str(VALIDATOR),
                "--root", str(run.root), "--manifest", str(MANIFEST),
                "--output", str(terminal),
            ], cwd=REPO, check=True, stdout=stdout)
        return terminal
    except BaseException as exc:
        if run.proc is not None and current_arm is not None:
            try:
                run.stop(current_arm)
            except Exception:
                pass
        terminal = run.root / "terminal-receipt.json"
        if not terminal.exists():
            CORE.write_json_x(terminal, {
                "schema": "neural.download.qwen36-llama-mtp01234-q8kv-exact2k-classification-terminal.v1",
                "campaign_id": CAMPAIGN_ID,
                "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
                "status": "failed-infrastructure-preserve",
                "error": f"{type(exc).__name__}: {exc}",
                "packet_grade": "D",
                "authority": {"site_cells": 0, "site_publication": False, "curve_expansion": False, "speed_claim": False},
            })
        raise


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
            print(json.dumps(static_check(value), indent=2, sort_keys=True))
            return 0
        if args.ack != ACK:
            raise GateError(f"exact --ack required: {ACK}")
        print(execute(value))
        return 0
    except (GateError, OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
