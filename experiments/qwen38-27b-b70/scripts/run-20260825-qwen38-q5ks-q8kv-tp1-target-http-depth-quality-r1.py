#!/usr/bin/env python3
"""Create-only current-Qwen3.8 Q5_K_S target HTTP depth/quality runner."""

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
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-25-qwen38-q5ks-q8kv-tp1-target-http-depth-quality-r1-prereg.json"
VALIDATOR = LANE / "scripts/validate-20260825-qwen38-q5ks-q8kv-tp1-target-http-depth-quality-r1.py"
PARENT_RUNNER = LANE / "scripts/run-20260825-qwen38-q5ks-external-q4mtp-q8kv-tp1-route-8k-sentinel-r1.py"
CAMPAIGN_ID = "qwen38-q5ks-q8kv-tp1-target-http-depth-quality-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
DEPTHS = (0, 2048, 4096, 8192, 16384, 24576, 32768)
ARM = "target-mtp0"
EXPECTED_CLEANUP = {
    "forced_kill": False, "port_closed": True,
    "render_node_idle": True, "server_survivor": False,
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PARENT = load_module(PARENT_RUNNER, "qwen38_q5ks_route_parent_for_target_depth")
CORE = PARENT.CORE
GateError = PARENT.GateError


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"JSON root must be an object: {path}")
    return value


def referenced_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else REPO / path


def validate_manifest(value: dict[str, Any]) -> None:
    s = value.get("selectors") or {}
    e = value.get("execution_contract") or {}
    l = value.get("lifecycle") or {}
    f = value.get("frozen_interpretation") or {}
    if not (
        value.get("schema") == "neural.download.qwen38-q5ks-target-http-depth-quality-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and s == {
            "revision": "qwen3.8-27b-current-weights",
            "target_quantization": "UD-Q5_K_S", "tp": 1, "mtp": 0,
            "active_context_tokens": list(DEPTHS), "target_kv": "q8_0",
            "graph_mode": "off", "fit": "off",
            "transport": "HTTP /v1/completions",
        }
        and e.get("arm") == ARM
        and e.get("fresh_server_lifetimes") == 1
        and e.get("depth_order") == list(DEPTHS)
        and e.get("quality_after_all_depths") is True
        and e.get("require_parent_8k_output_parity") is True
        and l.get("output_root") == f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}"
        and l.get("exact_ack") == ACK
        and l.get("default_is_inert") is True
        and f.get("speed_floor") is None
        and f.get("target_only_serving_curve_cells_if_all_gates_pass") == 7
        and f.get("speculative_cells_authorized") == 0
        and f.get("tp2_or_tp4_cells_authorized") == 0
        and f.get("headline_or_protected_replacement_authorized") is False
        and f.get("protected_decode_values")
        == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]
    ):
        raise GateError("target HTTP depth manifest invariant failed")


def load_manifest() -> dict[str, Any]:
    value = load_json(MANIFEST)
    validate_manifest(value)
    return value


def verify_parent(value: dict[str, Any]) -> None:
    p = value["parent"]
    for key in ("manifest", "runner", "validator", "terminal", "identity", "control_8k_receipt"):
        path = referenced_path(p[key])
        if not path.is_file() or PARENT.sha256_file(path) != p[f"{key}_sha256"]:
            raise GateError(f"sealed parent changed: {path}")
    terminal = load_json(referenced_path(p["terminal"]))
    control = next((row for row in terminal.get("arms", []) if row.get("mtp") == 0), {})
    receipt = load_json(referenced_path(p["control_8k_receipt"]))
    output_hash = (receipt.get("response") or {}).get("output_token_ids_sha256")
    if not (
        terminal.get("campaign_id") == p["campaign_id"]
        and terminal.get("status") == "completed-valid-route-screen-pending-review"
        and control.get("passed") is True
        and output_hash == p["required_control_output_token_ids_sha256"]
        and (receipt.get("gate") or {}).get("passed") is True
        and (((receipt.get("response") or {}).get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens") == 0
    ):
        raise GateError("successful target-only 8K parent invariant failed")


def merged_manifest(value: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(PARENT.merged_manifest(PARENT.load_manifest()))
    merged.pop("draft_model", None)
    for key in (
        "schema", "campaign_id", "state", "purpose", "model", "runtime",
        "fixture", "clients", "parent", "selectors", "server_contract",
        "execution_contract", "lifecycle", "frozen_interpretation",
    ):
        merged[key] = copy.deepcopy(value[key])
    return merged


class Execution(PARENT.Execution):
    def server_argv(self) -> list[str]:
        return self.server_argv_for_mtp(0)


def static_check(value: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(value)
    verify_parent(value)
    runtime, clients, fixture = value["runtime"], value["clients"], value["fixture"]
    CORE.verify_file(Path(runtime["binary"]), runtime["binary_sha256"])
    for row in runtime["effective_local_shared_libraries"]:
        CORE.verify_file(Path(row["path"]), row["sha256"], row["size_bytes"])
    CORE.verify_file(referenced_path(fixture["path"]), fixture["sha256"])
    CORE.verify_file(referenced_path(clients["exact_depth"]["path"]), clients["exact_depth"]["sha256"])
    CORE.verify_file(referenced_path(clients["quality"]["path"]), clients["quality"]["sha256"])
    CORE.verify_file(Path(clients["quality"]["interpreter"]), clients["quality"]["interpreter_sha256"], allow_symlink=True)
    model = Path(value["model"]["path"])
    if not model.is_file() or model.is_symlink() or model.stat().st_size != value["model"]["size_bytes"]:
        raise GateError("model path/size identity failed (full hash is execute-only)")
    if not Path(clients["quality"]["tokenizer_path"]).is_dir():
        raise GateError("Qwen3.8 tokenizer directory missing")
    fixture_value = load_json(referenced_path(fixture["path"]))
    rows = {row.get("id"): row for row in fixture_value.get("cases", []) if isinstance(row, dict)}
    for depth, case_id, prompt_hash in zip(DEPTHS, fixture["case_ids"], fixture["prompt_token_ids_sha256"], strict=True):
        row = rows.get(case_id) or {}
        if row.get("depth") != depth or row.get("prompt_token_ids_sha256") != prompt_hash:
            raise GateError(f"fixture case changed: {case_id}")
    argv = Execution(merged_manifest(value)).server_argv()
    if argv[argv.index("--spec-type") + 1] != "none" or "--spec-draft-model" in argv:
        raise GateError("target-only argv gained a draft model")
    return {
        "schema": "neural.download.qwen38-q5ks-target-http-depth-quality-plan.v1",
        "mode": "check", "default_is_inert": True,
        "gpu_actions": 0, "network_requests": 0, "output_writes": 0,
        "campaign_id": CAMPAIGN_ID, "exact_ack": ACK,
        "arm": ARM, "fresh_server_lifetimes": 1, "depths": list(DEPTHS),
        "quality_batteries": 1, "target_only_cells_if_valid": 7,
        "server_argv": argv,
    }


def execute(value: dict[str, Any]) -> Path:
    manifest = merged_manifest(value)
    unexpected = [name for name in os.environ if name.startswith((
        "GGML_", "SYCL_", "ZE_", "ZES_", "UR_", "ONEAPI_DEVICE_SELECTOR", "LLAMA_ARG_"
    )) or name == "LD_PRELOAD"]
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
    error: str | None = None
    cleanup: dict[str, bool] | None = None
    try:
        static_check(value)
        CORE.verify_file(Path(value["model"]["path"]), value["model"]["sha256"], value["model"]["size_bytes"])
        env = CORE.oneapi_environment(Path(value["runtime"]["binary"]).parent)
        version = subprocess.check_output([value["runtime"]["binary"], "--version"], env=env, stderr=subprocess.STDOUT, text=True).strip()
        if value["runtime"]["reported_version"] not in version.splitlines():
            raise GateError("runtime version drift")
        ldd = subprocess.check_output(["ldd", value["runtime"]["binary"]], env=env, text=True)
        captured = []
        for row in value["runtime"]["effective_local_shared_libraries"]:
            match = re.search(rf"^\s*{re.escape(row['soname'])}\s+=>\s+(\S+)", ldd, re.M)
            if not match or Path(match.group(1)).resolve() != Path(row["path"]).resolve():
                raise GateError(f"ldd closure mismatch: {row['soname']}")
            captured.append(row)
        argv = run.server_argv()
        CORE.write_json_x(run.root / "identity.json", {
            "campaign_id": CAMPAIGN_ID, "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "git_head": head, "origin_main": origin, "model": value["model"],
            "runtime": {**value["runtime"], "version": version, "ldd": ldd.splitlines(), "local_dsos": captured},
            "fixture": value["fixture"], "server_argv": {ARM: argv},
            "runtime_environment": {key: env[key] for key in (
                "ONEAPI_DEVICE_SELECTOR", "ZE_AFFINITY_MASK", "GGML_SYCL_ENABLE_GRAPH",
                "GGML_SYCL_GRAPH_CACHE_SIZE", "GGML_SYCL_ENABLE_VMM",
            )},
            "parent": value["parent"],
        })
        run.start(ARM, argv, env)
        for depth in DEPTHS:
            run.run_depth(ARM, depth, False)
        q = value["clients"]["quality"]
        command = [
            q["interpreter"], "-I", "-B", str(referenced_path(q["path"])),
            "--base-url", f"http://127.0.0.1:{run.port}",
            "--model", value["server_contract"]["model_alias"],
            "--tokenizer", q["tokenizer_path"], "--timeout", str(value["lifecycle"]["request_timeout_seconds"]),
            "--seed", "1", "--repeat-runs", str(q["repeat_runs"]),
            "--long-context-tokens", str(q["long_context_tokens"]),
            "--request-id-prefix", f"{CAMPAIGN_ID}-quality",
            "--output-json", str(run.root / ARM / "quality.json"),
        ]
        with (run.root / ARM / "quality.stdout.json").open("xb") as stdout, (run.root / ARM / "quality.stderr.log").open("xb") as stderr:
            subprocess.run(command, cwd=REPO, check=True, stdout=stdout, stderr=stderr)
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        (run.root / ARM).mkdir(exist_ok=True)
        cleanup = run.stop(ARM)
    complete = error is None and cleanup == EXPECTED_CLEANUP
    CORE.write_json_x(run.root / ARM / "arm-result.json", {
        "status": "completed-awaiting-validation" if complete else "failed-preserve",
        "error": error, "cleanup": cleanup,
    })
    terminal = run.root / "terminal-receipt.json"
    if not complete:
        CORE.write_json_x(terminal, {
            "schema": "neural.download.qwen38-q5ks-target-http-depth-quality-terminal.v1",
            "campaign_id": CAMPAIGN_ID, "status": "failed-preserve-do-not-publish",
            "error": error or f"cleanup failed: {cleanup}",
            "authority": {"target_only_serving_curve_cells": 0, "other_cells": 0, "protected_replacement": False},
        })
        raise GateError(error or f"cleanup failed: {cleanup}")
    with (run.root / "validator.stdout.json").open("xb") as stdout:
        subprocess.run([
            sys.executable, "-B", str(VALIDATOR), "--root", str(run.root),
            "--manifest", str(MANIFEST), "--output", str(terminal),
        ], cwd=REPO, check=True, stdout=stdout)
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
