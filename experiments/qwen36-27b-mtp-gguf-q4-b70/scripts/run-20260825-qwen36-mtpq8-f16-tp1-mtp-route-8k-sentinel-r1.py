#!/usr/bin/env python3
"""Create-only embedded-Q8/F16 TP1 graph-off MTP route screen at exact 8K."""

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
MANIFEST = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r1-prereg.json"
VALIDATOR = LANE / "scripts/validate-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r1.py"
PARENT_RUNNER = LANE / "scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r3.py"
CAMPAIGN_ID = "qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
DEPTH = 8192
ROUTES = (0, 1, 2, 3, 4)
ARMS = {
    0: "control-mtp0",
    1: "candidate-mtp1",
    2: "candidate-mtp2",
    3: "positive-control-mtp3",
    4: "candidate-mtp4",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PARENT = load_module(PARENT_RUNNER, "qwen36_mtpq8_mtp3_r3_for_route_screen")
BASE = PARENT.BASE
GateError = BASE.GateError


def load_overlay() -> dict[str, Any]:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    validate_overlay(value)
    return value


def validate_overlay(value: dict[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    server = value.get("server_contract") or {}
    route = value.get("route_contract") or {}
    lifecycle = value.get("lifecycle") or {}
    frozen = value.get("frozen_interpretation") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-mtp-route-8k-sentinel-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors.get("active_context_tokens") == DEPTH
        and selectors.get("route_mtp") == list(ROUTES)
        and selectors.get("target_kv") == selectors.get("draft_kv") == "f16"
        and selectors.get("graph_mode") == "off"
        and route.get("arm_order") == [ARMS[n] for n in ROUTES]
        and route.get("fresh_server_lifetime_per_arm") is True
        and route.get("required_target_output_parity_tokens") == 128
        and route.get("positive_control_mtp") == 3
        and server.get("context_capacity", 0) >= DEPTH + 128
        and server.get("ggml_sycl_enable_graph") == "0"
        and server.get("ggml_sycl_graph_cache_size") == "0"
        and lifecycle.get("output_root")
        == "/mnt/fast-ai/bench-results/qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-20260825-r1"
        and lifecycle.get("default_is_inert") is True
        and lifecycle.get("continue_after_candidate_failure") is True
        and frozen.get("speed_floor") is None
        and frozen.get("site_publication_authorized") is False
        and frozen.get("headline_or_protected_replacement_authorized") is False
        and frozen.get("successful_r3_or_protected_speed_replacement_authorized") is False
    ):
        raise GateError("route sentinel manifest invariant failed")


def parent_manifest() -> dict[str, Any]:
    overlay = PARENT.load_overlay()
    PARENT.verify_references(overlay)
    return PARENT.merge_manifest(overlay)


def merged_manifest(value: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(parent_manifest())
    for key in (
        "schema", "campaign_id", "state", "purpose", "parent_r3", "selectors",
        "server_contract", "route_contract", "lifecycle", "frozen_interpretation",
    ):
        merged[key] = copy.deepcopy(value[key])
    return merged


def verify_parent(value: dict[str, Any]) -> None:
    parent = value["parent_r3"]
    for raw_path, expected, label in (
        (parent["manifest"], parent["manifest_sha256"], "R3 manifest"),
        (parent["runner"], parent["runner_sha256"], "R3 runner"),
        (parent["validator"], parent["validator_sha256"], "R3 validator"),
        (parent["terminal_receipt"], parent["terminal_receipt_sha256"], "R3 terminal"),
    ):
        path = Path(raw_path) if Path(raw_path).is_absolute() else REPO / raw_path
        if not path.is_file() or BASE.sha256_file(path) != expected:
            raise GateError(f"{label} changed: {path}")
    terminal = BASE.load_json(Path(parent["terminal_receipt"]))
    controls = {row.get("depth"): row for row in terminal.get("control_mtp0", []) if isinstance(row, dict)}
    candidates = {row.get("depth"): row for row in terminal.get("candidate_mtp3", []) if isinstance(row, dict)}
    counters = {row.get("depth"): row for row in terminal.get("candidate_draft_counters", []) if isinstance(row, dict)}
    expected_hash = parent["required_8k_output_token_ids_sha256"]
    if not (
        terminal.get("status") == parent["required_status"]
        and terminal.get("gate", {}).get("passed") is parent["required_gate_passed"]
        and controls.get(DEPTH, {}).get("output_token_ids_sha256") == expected_hash
        and candidates.get(DEPTH, {}).get("output_token_ids_sha256") == expected_hash
        and counters.get(DEPTH, {}).get("generated") == parent["required_8k_mtp3_generated"]
        and counters.get(DEPTH, {}).get("accepted") == parent["required_8k_mtp3_accepted"]
        and counters.get(DEPTH, {}).get("conserved") is True
    ):
        raise GateError("successful R3 8K parent invariant failed")


def static_check(value: dict[str, Any]) -> dict[str, Any]:
    validate_overlay(value)
    verify_parent(value)
    parent = parent_manifest()
    BASE.static_check(parent)
    fixture = BASE.load_json(BASE.referenced_path(parent["fixture"]["path"]))
    selected = next((row for row in fixture.get("cases", []) if row.get("id") == "depth-8192"), None)
    if not isinstance(selected, dict) or selected.get("prompt_token_ids_sha256") != parent["fixture"]["prompt_token_ids_sha256"][3]:
        raise GateError("8K fixture identity failed")
    return {
        "schema": "neural.download.qwen36-llama-mtp-route-8k-sentinel-plan.v1",
        "mode": "check",
        "default_is_inert": True,
        "gpu_actions": 0,
        "network_requests": 0,
        "output_writes": 0,
        "campaign_id": CAMPAIGN_ID,
        "exact_ack": ACK,
        "active_context_tokens": DEPTH,
        "arms": [ARMS[n] for n in ROUTES],
        "fresh_server_lifetimes": len(ROUTES),
        "authority": "route-expansion-screen-only",
    }


def replace_flag(argv: list[str], flag: str, value: str) -> None:
    try:
        argv[argv.index(flag) + 1] = value
    except (ValueError, IndexError) as exc:
        raise GateError(f"missing inherited argv flag: {flag}") from exc


class Execution(BASE.Execution):
    def server_argv_for_mtp(self, mtp: int) -> list[str]:
        argv = super().server_argv(mtp > 0)
        replace_flag(argv, "--alias", self.m["server_contract"]["model_alias"])
        replace_flag(argv, "--port", str(self.m["server_contract"]["port"]))
        replace_flag(argv, "-c", str(self.m["server_contract"]["context_capacity"]))
        if mtp > 0:
            replace_flag(argv, "--spec-draft-n-max", str(mtp))
        return argv


def execute(value: dict[str, Any]) -> Path:
    validate_overlay(value)
    verify_parent(value)
    manifest = merged_manifest(value)
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
    run = Execution(manifest)
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
        BASE.verify_file(Path(model["path"]), model["sha256"], model["size_bytes"])
        static_check(value)
        env = BASE.oneapi_environment(Path(runtime["binary"]).parent)
        version = subprocess.check_output([runtime["binary"], "--version"], env=env, stderr=subprocess.STDOUT, text=True).strip()
        if runtime["reported_version"] not in version.splitlines():
            raise GateError("runtime version drift")
        help_text = subprocess.check_output([runtime["binary"], "--help"], env=env, stderr=subprocess.STDOUT, text=True)
        if "draft-mtp" not in help_text:
            raise GateError("runtime lacks draft-mtp")
        ldd = subprocess.check_output(["ldd", runtime["binary"]], env=env, text=True)
        captured = []
        for row in runtime["effective_local_shared_libraries"]:
            match = re.search(rf"^{re.escape(row['soname'])}\s+=>\s+(\S+)", ldd, re.M)
            if not match or str(Path(match.group(1)).resolve()) != str(Path(row["path"]).resolve()):
                raise GateError(f"ldd closure mismatch: {row['soname']}")
            captured.append(row)
        local_names = sorted({
            line.split()[0] for line in ldd.splitlines()
            if " => " in line and line.split()[2].startswith(str(Path(runtime["binary"]).parent) + "/")
        })
        if local_names != sorted(row["soname"] for row in captured):
            raise GateError("unexpected runtime-origin DSO")
        argv_by_arm = {ARMS[mtp]: run.server_argv_for_mtp(mtp) for mtp in ROUTES}
        identity = {
            "campaign_id": CAMPAIGN_ID,
            "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "git_head": head,
            "origin_main": origin,
            "model": {key: model[key] for key in ("path", "size_bytes", "sha256", "repository", "revision")},
            "runtime": {
                "binary": runtime["binary"],
                "binary_sha256": runtime["binary_sha256"],
                "manifest": runtime["manifest"],
                "manifest_sha256": runtime["manifest_sha256"],
                "source_commit": runtime["source_commit"],
                "version": version,
                "local_dsos": captured,
                "ldd": ldd.splitlines(),
            },
            "fixture_sha256": manifest["fixture"]["sha256"],
            "fixture_8k_prompt_token_ids_sha256": manifest["fixture"]["prompt_token_ids_sha256"][3],
            "server_argv": argv_by_arm,
            "runtime_environment": {
                key: env[key] for key in (
                    "ONEAPI_DEVICE_SELECTOR", "ZE_AFFINITY_MASK", "GGML_SYCL_ENABLE_GRAPH",
                    "GGML_SYCL_GRAPH_CACHE_SIZE", "GGML_SYCL_ENABLE_DNN", "GGML_SYCL_ENABLE_OPT",
                    "GGML_SYCL_ENABLE_VMM",
                )
            },
            "parent_r3_terminal_receipt_sha256": value["parent_r3"]["terminal_receipt_sha256"],
        }
        BASE.write_json_x(run.root / "identity.json", identity)
        for mtp in ROUTES:
            arm = ARMS[mtp]
            current_arm = arm
            run.require_idle()
            arm_error: str | None = None
            try:
                run.start(arm, argv_by_arm[arm], env)
                run.run_depth(arm, DEPTH, mtp > 0)
            except BaseException as exc:
                arm_error = f"{type(exc).__name__}: {exc}"
            finally:
                cleanup = run.stop(arm)
            if arm_error is not None or cleanup != {
                "forced_kill": False,
                "port_closed": True,
                "render_node_idle": True,
                "server_survivor": False,
            }:
                BASE.write_json_x(
                    run.root / arm / "arm-result.json",
                    {"status": "failed-preserve", "error": arm_error, "cleanup": cleanup},
                )
            else:
                BASE.write_json_x(
                    run.root / arm / "arm-result.json",
                    {"status": "completed-awaiting-validation", "error": None, "cleanup": cleanup},
                )
            current_arm = None
        terminal = run.root / "terminal-receipt.json"
        with (run.root / "validator.stdout.json").open("xb") as stdout:
            subprocess.run(
                [sys.executable, "-B", str(VALIDATOR), "--root", str(run.root), "--manifest", str(MANIFEST), "--output", str(terminal)],
                cwd=REPO,
                check=True,
                stdout=stdout,
            )
        return terminal
    except BaseException as exc:
        if run.proc is not None and current_arm is not None:
            try:
                run.stop(current_arm)
            except Exception:
                pass
        terminal = run.root / "terminal-receipt.json"
        if not terminal.exists():
            BASE.write_json_x(
                terminal,
                {
                    "schema": "neural.download.qwen36-llama-mtp-route-8k-sentinel-terminal.v1",
                    "campaign_id": CAMPAIGN_ID,
                    "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
                    "status": "failed-preserve-do-not-expand",
                    "error": f"{type(exc).__name__}: {exc}",
                    "authority": {"curve_expansion_routes": [], "site_publication": False, "protected_replacement": False},
                },
            )
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
        value = load_overlay()
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
