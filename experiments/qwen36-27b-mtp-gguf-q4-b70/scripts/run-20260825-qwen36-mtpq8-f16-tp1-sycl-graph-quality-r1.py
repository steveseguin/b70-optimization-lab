#!/usr/bin/env python3
"""Run the sealed embedded-MTP-artifact Q8/F16 TP1 graph quality battery."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-sycl-graph-quality-r1-prereg.json"
BASE_RUNNER = LANE / "scripts/run-20260825-qwen36-q8-f16-tp1-sycl-graph-quality-r1.py"
CURVE_RUNNER = LANE / "scripts/run-20260825-qwen36-mtpq8-f16-tp1-sycl-graph-exact-depth-r1.py"
CAMPAIGN_ID = "qwen36-mtpq8-f16-tp1-sycl-graph-quality-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
RUN_ROOT = Path(f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}")
SERVER_ALIAS = "qwen36-mtpq8-f16-tp1-graph-quality-r1"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import sealed runner: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASEQ = _load(BASE_RUNNER, "qwen36_target_graph_quality_for_mtpq8")
CURVE = _load(CURVE_RUNNER, "qwen36_mtpq8_graph_curve_for_quality")
BASE_MANIFEST_VALUE = copy.deepcopy(BASEQ.load_manifest())
BASE_STATIC_CHECK = BASEQ.static_check
GateError = BASEQ.GateError


def load_manifest() -> dict[str, Any]:
    return CURVE.R1.load_json(MANIFEST)


def validate_manifest(value: Mapping[str, Any]) -> None:
    curve = value.get("curve_parent") or {}
    selectors = value.get("selectors") or {}
    model = value.get("model") or {}
    quality = value.get("quality") or {}
    lifecycle = value.get("lifecycle") or {}
    authority = value.get("authority") or {}
    argv = value.get("server_argv")
    if not (
        value.get("schema") == "neural.download.qwen36-llama-sycl-graph-quality-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "sealed-preregistered-not-launched"
        and curve.get("campaign_id") == "qwen36-mtpq8-f16-tp1-sycl-graph-exact-depth-20260825-r1"
        and curve.get("depths") == [0, 2048, 4096, 8192, 16384, 24576, 32768]
        and selectors == {
            "revision": "qwen3.6-27b", "artifact_id": "qwen36-27b-unsloth-mtp-q8-0-5cb35eb",
            "quantization": "Q8_0", "runtime_family": "llama.cpp SYCL", "tp": 1,
            "mtp": 0, "graph_mode": "SYCL", "kv": "f16",
        }
        and model.get("path") == "/mnt/usb-models/models/qwen36-27b-mtp-q8-gguf/Qwen3.6-27B-Q8_0.gguf"
        and model.get("repository") == "unsloth/Qwen3.6-27B-MTP-GGUF"
        and model.get("revision") == "5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace"
        and model.get("size_bytes") == 29047084160
        and model.get("sha256") == "9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8"
        and model.get("direct_sha256") == model.get("sha256")
        and model.get("ordinary_sha256") == model.get("sha256")
        and model.get("embedded_mtp_capability") is True
        and value.get("environment", {}).get("GGML_SYCL_ENABLE_GRAPH") == "1"
        and value.get("environment", {}).get("GGML_SYCL_GRAPH_CACHE_SIZE") == "8"
        and quality.get("exact_case_count") == 4
        and quality.get("repeat_runs") == 8
        and quality.get("near_32k_needle_target_tokens") == 31744
        and quality.get("expected_request_count") == 13
        and lifecycle.get("output_root") == str(RUN_ROOT)
        and lifecycle.get("exact_ack") == ACK
        and lifecycle.get("create_only") is True
        and authority.get("quality_may_cover_all_seven_curve_cells_on_pass") is True
        and authority.get("per_depth_quality_reruns_required") is False
        and authority.get("raw_engine_speed_measurements_unchanged") is True
        and authority.get("mixed_partial_prefill_graph_claim_preserved") is True
        and authority.get("site_publication_authorized") is False
        and authority.get("record_or_submission_authorized") is False
        and authority.get("protected_graph_off_values_may_be_replaced") is False
        and isinstance(argv, list)
        and argv[0] == value["runtime"]["server"]["path"]
    ):
        raise GateError("embedded-MTP graph quality manifest invariant failed")
    for flag, expected in (("-m", model["path"]), ("--alias", SERVER_ALIAS), ("-c", "32768"), ("-ctk", "f16"), ("-ctv", "f16"), ("--spec-type", "none")):
        if argv.count(flag) != 1 or argv[argv.index(flag) + 1] != expected:
            raise GateError(f"server argv selector changed: {flag}")
    if value["environment"] != CURVE.load_manifest()["environment"]:
        raise GateError("quality environment differs from the passed embedded-MTP curve")

    # Fail closed unless this is the passed target battery with only complete
    # model/curve and create-only campaign identity mechanically replaced.
    base = copy.deepcopy(BASE_MANIFEST_VALUE)
    reconstructed = copy.deepcopy(dict(value))
    reconstructed.pop("adapted_from", None)
    reconstructed["campaign_id"] = base["campaign_id"]
    reconstructed["purpose"] = base["purpose"]
    reconstructed["curve_parent"] = copy.deepcopy(base["curve_parent"])
    reconstructed["selectors"]["artifact_id"] = base["selectors"]["artifact_id"]
    reconstructed["model"] = copy.deepcopy(base["model"])
    reconstructed["server_argv"] = copy.deepcopy(base["server_argv"])
    reconstructed["lifecycle"] = copy.deepcopy(base["lifecycle"])
    reconstructed["authority"]["coverage_reason"] = base["authority"]["coverage_reason"]
    if reconstructed != base:
        raise GateError("embedded-MTP packet changes more than model/curve/campaign/output identity")


# Rebind the proven implementation to the embedded-MTP curve and new
# create-only namespace.  All quality and graph gates stay byte-for-byte base.
BASEQ.CURVE = CURVE
BASEQ.BASE = CURVE.R1.BASE
BASEQ.MANIFEST = MANIFEST
BASEQ.CAMPAIGN_ID = CAMPAIGN_ID
BASEQ.ACK = ACK
BASEQ.RUN_ROOT = RUN_ROOT
BASEQ.load_manifest = load_manifest
BASEQ.validate_manifest = validate_manifest


def static_check():
    result = BASE_STATIC_CHECK()
    BASEQ.verify_ref(load_manifest()["model"], "embedded-MTP model", size=True)
    return result


def execute(ack: str) -> int:
    if ack != ACK:
        raise GateError(f"exact acknowledgement required: {ACK}")
    manifest, environment, libraries = static_check()
    state, error, cleanup = "failed", None, False
    head = ""
    with BASEQ.BASE.campaign_locks():
        head = BASEQ.BASE.require_clean_pushed_main()
        BASEQ.BASE.require_idle()
        if RUN_ROOT.exists():
            raise GateError(f"create-only output root exists: {RUN_ROOT}")
        fstype = subprocess.check_output(["/usr/bin/findmnt", "-n", "-o", "FSTYPE", "--target", str(RUN_ROOT.parent)], text=True).strip()
        if fstype != "ext4":
            raise GateError(f"output parent must be ext4, got {fstype}")
        RUN_ROOT.mkdir(mode=0o700)
        for name in ("runtime-home", "runtime-cache/sycl", "runtime-tmp"):
            (RUN_ROOT / name).mkdir(parents=True, exist_ok=False)
        server_log = RUN_ROOT / "server.log"
        process: subprocess.Popen[bytes] | None = None
        try:
            with server_log.open("xb") as log:
                process = subprocess.Popen(manifest["server_argv"], cwd=REPO, env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                models = BASEQ.wait_ready(process, "http://127.0.0.1:19436/v1/models", SERVER_ALIAS)
                BASEQ.BASE.write_json_exclusive(RUN_ROOT / "models.json", models)
                quality = manifest["quality"]
                result = subprocess.run([
                    quality["python"]["path"], "-I", "-B", str(BASEQ.resolve(quality["helper"]["path"])),
                    "--base-url", "http://127.0.0.1:19436", "--model", SERVER_ALIAS,
                    "--tokenizer", quality["tokenizer"]["path"], "--timeout", "3600", "--repeat-runs", "8",
                    "--long-context-tokens", "31744", "--request-id-prefix", CAMPAIGN_ID,
                    "--output-json", str(RUN_ROOT / "quality.json"),
                ], cwd=REPO, env=environment, text=True, capture_output=True, timeout=7200, check=False)
                (RUN_ROOT / "quality.stdout.json").write_text(result.stdout, encoding="utf-8")
                (RUN_ROOT / "quality.stderr.log").write_text(result.stderr, encoding="utf-8")
                if result.returncode != 0:
                    raise GateError(f"quality helper exited {result.returncode}")
            cleanup_row = BASEQ.stop_server(process); process = None
            if not cleanup_row["process_group_empty"]:
                raise GateError("server process group remained live")
            quality_gate = BASEQ.validate_quality(BASEQ.load_json(RUN_ROOT / "quality.json"), manifest)
            graph_gate = BASEQ.graph_evidence(server_log.read_text(encoding="utf-8", errors="replace"))
            BASEQ.BASE.write_json_exclusive(RUN_ROOT / "quality-gate.json", {"passed": True, "quality": quality_gate, "graph": graph_gate, "server_effective_shared_libraries": libraries})
            BASEQ.BASE.require_idle(); cleanup = True
            state = "passed-quality-covers-seven-raw-curve-cells"
        except Exception as exc:
            error = str(exc)
            if process is not None:
                try:
                    cleanup = BASEQ.stop_server(process)["process_group_empty"]
                except Exception as cleanup_exc:
                    error += f"; cleanup: {cleanup_exc}"
        terminal = {
            "schema": "neural.download.qwen36-llama-sycl-graph-quality-terminal.v1", "campaign_id": CAMPAIGN_ID,
            "state": state, "created_at_utc": BASEQ.dt.datetime.now(BASEQ.dt.UTC).isoformat(), "lab_git_head": head,
            "cleanup_passed": cleanup, "error": error, "quality_covers_depths": manifest["curve_parent"]["depths"] if state.startswith("passed-") else [],
            "raw_engine_speed_measurements_unchanged": True, "mixed_partial_prefill_graph_claim_preserved": True,
            "site_publication_authorized": False, "record_or_submission_authorized": False,
            "protected_graph_off_values_replaced": False,
        }
        BASEQ.BASE.write_json_exclusive(RUN_ROOT / "terminal-receipt.json", terminal)
    print(json.dumps(terminal, indent=2, sort_keys=True))
    return 0 if state.startswith("passed-") else 20


def plan(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {"campaign_id": CAMPAIGN_ID, "state": manifest["state"], "default_is_inert": True, "output_root": str(RUN_ROOT), "ack": ACK, "request_count": 13, "quality_may_cover_all_seven_curve_cells_on_pass": True, "site_publication_authorized": False}


BASEQ.static_check = static_check
BASEQ.execute = execute
BASEQ.plan = plan


def main(argv: list[str] | None = None) -> int:
    return BASEQ.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
