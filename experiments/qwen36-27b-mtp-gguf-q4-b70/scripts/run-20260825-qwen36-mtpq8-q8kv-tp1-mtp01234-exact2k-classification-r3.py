#!/usr/bin/env python3
"""Create-only R3 retry for the Q8-KV exact-2K classifier."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r3-prereg.json"
R2_RUNNER = LANE / "scripts/run-20260825-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r2.py"
MANIFEST = OVERLAY
VALIDATOR = LANE / "scripts/validate-20260825-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r3.py"
CAMPAIGN_ID = "qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-20260825-r3"
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-20260825-r3")
ACK = f"RUN {CAMPAIGN_ID}"
PORT = 19439
CASE_ID = "depth-2048"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R2 = load_module(R2_RUNNER, "qwen36_q8kv_exact2k_classification_r2_for_r3")
GateError = R2.GateError
CORE = R2.CORE
R1 = R2.R1
verify_ldd_closure = R2.verify_ldd_closure
DEPTH, REPEATS, ROUTES, ARMS, ARM_PLAN = R2.DEPTH, R2.REPEATS, R2.ROUTES, R2.ARMS, R2.ARM_PLAN
_R2_LOAD = R2.load_manifest
_R2_VALIDATE = R2.validate_manifest
_R2_VERIFY_R1 = R2.verify_failed_r1
_R2_RUNTIME = R2.runtime_manifest
_R2_STATIC = R2.static_check
_R2_EXECUTE = R2.execute
_WRITE_JSON_X = CORE.write_json_x


def sha256_file(path: Path) -> str:
    return R2.sha256_file(path)


def load_overlay() -> dict[str, Any]:
    value = json.loads(OVERLAY.read_text(encoding="utf-8"))
    delta = value.get("sole_execution_delta") or {}
    preserved = value.get("preserved_contract") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-mtp01234-q8kv-exact2k-classification-retry-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and delta == {"case_id": CASE_ID, "port": PORT, "output_root": str(RUN_ROOT), "exact_ack": ACK}
        and preserved.get("arm_order") == [arm for arm, _ in ARM_PLAN]
        and preserved.get("fresh_server_lifetimes") == 6
        and preserved.get("repeats_per_arm") == 3
        and preserved.get("total_requests") == 18
        and preserved.get("site_cells_authorized") == 0
    ):
        raise GateError("R3 retry overlay invariant failed")
    return value


def _configure_base() -> None:
    R2.MANIFEST, R2.VALIDATOR = MANIFEST, VALIDATOR
    R2.CAMPAIGN_ID, R2.RUN_ROOT, R2.ACK, R2.PORT = CAMPAIGN_ID, RUN_ROOT, ACK, PORT
    R2.load_manifest = load_manifest
    R2.validate_manifest = validate_manifest
    R2.verify_failed_r1 = verify_parents
    R2.runtime_manifest = runtime_manifest
    R2.static_check = static_check
    R2.run_repeat = run_repeat


def load_manifest() -> dict[str, Any]:
    overlay = load_overlay()
    base_path = REPO / overlay["base_r2"]["manifest"]["path"]
    base = json.loads(base_path.read_text(encoding="utf-8"))
    base["campaign_id"] = CAMPAIGN_ID
    base["purpose"] = "Valid-fixture-key retry of the bounded Q8-KV exact-2K classifier; no authority expansion."
    base["lifecycle"] = {
        **base["lifecycle"], "output_root": str(RUN_ROOT), "port": PORT, "exact_ack": ACK,
    }
    base["failed_r2_parent"] = copy.deepcopy(overlay["failed_r2_parent"])
    validate_manifest(base)
    return base


def validate_manifest(value: dict[str, Any]) -> None:
    _configure_base()
    _R2_VALIDATE(value)
    if value.get("failed_r2_parent") != load_overlay()["failed_r2_parent"]:
        raise GateError("failed R2 parent binding changed")


def verify_parents(value: dict[str, Any]) -> None:
    _R2_VERIFY_R1(value)
    overlay = load_overlay()
    for entry in overlay["base_r2"].values():
        path = REPO / entry["path"]
        if not path.is_file() or sha256_file(path) != entry["sha256"]:
            raise GateError(f"R2 tracked parent changed: {path}")
    parent = overlay["failed_r2_parent"]
    root = Path(parent["root"])
    terminal, identity = root / "terminal-receipt.json", root / "identity.json"
    if not terminal.is_file() or sha256_file(terminal) != parent["terminal_sha256"]:
        raise GateError("failed R2 terminal changed")
    if not identity.is_file() or sha256_file(identity) != parent["identity_sha256"]:
        raise GateError("failed R2 identity changed")
    receipt = json.loads(terminal.read_text(encoding="utf-8"))
    if receipt.get("campaign_id") != parent["campaign_id"] or receipt.get("status") != parent["required_status"]:
        raise GateError("failed R2 terminal invariant changed")


# Compatibility name used by the mechanically reused R2 classifier.
verify_failed_r1 = verify_parents


def runtime_manifest(value: dict[str, Any]) -> dict[str, Any]:
    _configure_base()
    merged = _R2_RUNTIME(value)
    merged["server_contract"]["model_alias"] = "qwen36-mtpq8-q8kv-tp1-exact2k-classification-r3"
    return merged


def repeat_command(run: Any, manifest: dict[str, Any], directory: Path) -> list[str]:
    return [
        sys.executable, "-B", str(CORE.referenced_path(manifest["clients"]["exact_depth"]["path"])), "--execute",
        "--fixture", str(CORE.referenced_path(manifest["fixture"]["path"])), "--depth", str(DEPTH),
        "--case-id", CASE_ID, "--context-capacity", str(manifest["server_contract"]["context_capacity"]),
        "--base-url", f"http://127.0.0.1:{run.port}", "--model", manifest["server_contract"]["model_alias"],
        "--response-adapter", "llama-server", "--timeout", str(manifest["lifecycle"]["request_timeout_seconds"]),
        "--out", str(directory / "exact-depth.json"),
    ]


def run_repeat(run: Any, manifest: dict[str, Any], arm: str, route: int, repeat: int) -> None:
    directory = run.root / arm / f"repeat-{repeat}"
    directory.mkdir()
    candidate = route > 0
    before = len(CORE.acceptance_rows(run.root / arm / "server.log")) if candidate else 0
    with (directory / "exact-depth.stdout.json").open("xb") as stdout:
        subprocess.run(repeat_command(run, manifest, directory), cwd=REPO, check=True, stdout=stdout)
    if candidate:
        deadline = time.monotonic() + 30
        rows = CORE.acceptance_rows(run.root / arm / "server.log")
        while len(rows) <= before and time.monotonic() < deadline:
            time.sleep(0.2)
            rows = CORE.acceptance_rows(run.root / arm / "server.log")
        _WRITE_JSON_X(directory / "draft-counters.json", {
            "active_context_tokens": DEPTH, "repeat": repeat,
            "rows_before": before, "rows_after": len(rows), "new_rows": rows[before:],
        })


def static_check(value: dict[str, Any]) -> dict[str, Any]:
    _configure_base()
    validate_manifest(value)
    verify_parents(value)
    plan = _R2_STATIC(value)
    fixture = json.loads(CORE.referenced_path(runtime_manifest(value)["fixture"]["path"]).read_text(encoding="utf-8"))
    selected = [row for row in fixture.get("cases", []) if row.get("id") == CASE_ID]
    if len(selected) != 1 or selected[0].get("depth") != DEPTH or selected[0].get("token_count") != DEPTH:
        raise GateError("valid frozen depth-2048 fixture key not found exactly once")
    plan.update({"campaign_id": CAMPAIGN_ID, "exact_ack": ACK, "case_id": CASE_ID, "port": PORT})
    return plan


def _bound_write(path: Path, value: Any) -> None:
    if path.name == "identity.json" and isinstance(value, dict):
        parent = load_overlay()["failed_r2_parent"]
        value["failed_r2_parent_hashes"] = {
            "terminal": parent["terminal_sha256"], "identity": parent["identity_sha256"],
        }
    _WRITE_JSON_X(path, value)


def execute(value: dict[str, Any]) -> Path:
    _configure_base()
    CORE.write_json_x = _bound_write
    try:
        return _R2_EXECUTE(value)
    finally:
        CORE.write_json_x = _WRITE_JSON_X


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
            print(json.dumps(static_check(value), indent=2, sort_keys=True)); return 0
        if args.ack != ACK:
            raise GateError(f"exact --ack required: {ACK}")
        print(execute(value)); return 0
    except (GateError, OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
