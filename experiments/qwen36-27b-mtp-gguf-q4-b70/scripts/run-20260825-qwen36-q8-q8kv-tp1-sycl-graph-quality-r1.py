#!/usr/bin/env python3
"""Run the sealed Qwen3.6 target-Q8/q8_0-KV TP1 graph quality battery."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from typing import Any, Mapping
import urllib.request


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-q8-q8kv-tp1-sycl-graph-quality-r1-prereg.json"
BASE_MANIFEST = LANE / "data/2026-08-25-qwen36-q8-f16-tp1-sycl-graph-quality-r1-prereg.json"
BASE_RUNNER = LANE / "scripts/run-20260825-qwen36-q8-f16-tp1-sycl-graph-quality-r1.py"
CURVE_RUNNER = LANE / "scripts/run-20260825-qwen36-q8-q8kv-tp1-sycl-graph-exact-depth-r2.py"
BASE_MANIFEST_SHA256 = "0b3a0f6582f6fd71f23651450a7ca3b0fb78fccc53a8b27a31ec66babf631207"
BASE_RUNNER_SHA256 = "501d3f37e79791aa8f97c740fbbe90fdc4b75483880441df14147e21289a0cfc"
CAMPAIGN_ID = "qwen36-q8-q8kv-tp1-sycl-graph-quality-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-q8kv-tp1-sycl-graph-quality-20260825-r1")
PORT = 19437
ALIAS = "qwen36-q8-q8kv-tp1-graph-quality-r1"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import sealed runner: {path}")
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module


F16 = load_module("qwen36_f16_graph_quality_for_q8kv", BASE_RUNNER)
CURVE = load_module("qwen36_q8kv_graph_curve_for_quality", CURVE_RUNNER)
BASE = CURVE.R1.BASE
# Use the quality base's exception identity for reused quality/graph gates;
# the independently loaded curve wrapper has an equivalent but distinct class.
GateError = F16.GateError


def sha256_file(path: Path) -> str:
    return F16.sha256_file(path)


def resolve(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO / value


def verify_ref(row: Mapping[str, Any], label: str, *, size: bool = False) -> Path:
    path = resolve(str(row.get("path", "")))
    if not path.is_file() or sha256_file(path) != row.get("sha256"):
        raise GateError(f"{label} identity changed: {path}")
    if size and path.stat().st_size != row.get("size_bytes"):
        raise GateError(f"{label} size changed: {path}")
    return path


def load_overlay() -> dict[str, Any]:
    value = CURVE.R1.load_json(OVERLAY)
    if not (
        value.get("schema") == "neural.download.qwen36-llama-sycl-graph-q8kv-quality-overlay.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "sealed-preregistered-not-launched"
        and value.get("curve_parent", {}).get("campaign_id") == CURVE.CAMPAIGN_ID
        and value.get("curve_parent", {}).get("depths") == CURVE.R1.DEPTHS
        and value.get("execution_identity_delta") == {
            "only_runtime_selector_delta_from_f16_quality": "selectors.kv and server -ctk/-ctv change from f16 to q8_0",
            "selectors.kv": "q8_0", "ctk": "q8_0", "ctv": "q8_0",
            "service_alias": ALIAS, "service_port": PORT,
        }
        and value.get("lifecycle") == {"output_root": str(RUN_ROOT), "exact_ack": ACK, "create_only": True}
        and value.get("raw_terminal_writer_caveat", {}).get("tracked_adjudication_required_after_pass") is True
        and value.get("authority", {}).get("site_publication_authorized") is False
        and value.get("authority", {}).get("publication_requires_tracked_adjudication_and_separate_ingestion") is True
    ):
        raise GateError("q8-KV quality overlay invariant failed")
    return value


def replace_arg(argv: list[str], flag: str, old: str, new: str) -> None:
    if argv.count(flag) != 1 or argv[argv.index(flag) + 1] != old:
        raise GateError(f"sealed base argv changed at {flag}")
    argv[argv.index(flag) + 1] = new


def load_manifest() -> dict[str, Any]:
    overlay = load_overlay()
    for path, expected in ((BASE_MANIFEST, BASE_MANIFEST_SHA256), (BASE_RUNNER, BASE_RUNNER_SHA256)):
        if sha256_file(path) != expected:
            raise GateError(f"sealed F16 quality packet changed: {path}")
    value = copy.deepcopy(F16.load_manifest())
    value["campaign_id"] = CAMPAIGN_ID
    value["purpose"] = value["purpose"].replace("Q8_0/F16", "Q8_0/q8_0-KV")
    value["curve_parent"] = copy.deepcopy(overlay["curve_parent"])
    value["selectors"]["kv"] = "q8_0"
    replace_arg(value["server_argv"], "--alias", "qwen36-q8-f16-tp1-graph-quality-r1", ALIAS)
    replace_arg(value["server_argv"], "--port", "19436", str(PORT))
    replace_arg(value["server_argv"], "-ctk", "f16", "q8_0")
    replace_arg(value["server_argv"], "-ctv", "f16", "q8_0")
    value["lifecycle"] = copy.deepcopy(overlay["lifecycle"])
    value["raw_terminal_writer_caveat"] = copy.deepcopy(overlay["raw_terminal_writer_caveat"])
    value["authority"].update({
        "quality_may_cover_all_seven_curve_cells_on_pass": True,
        "publication_requires_tracked_adjudication_and_separate_ingestion": True,
    })
    return value


def validate_manifest(value: Mapping[str, Any]) -> None:
    expected = load_manifest()
    if dict(value) != expected:
        raise GateError("q8-KV synthesized quality manifest changed")
    argv = value["server_argv"]
    if not (value["selectors"]["kv"] == "q8_0" and argv[argv.index("-ctk") + 1] == "q8_0"
            and argv[argv.index("-ctv") + 1] == "q8_0" and argv[argv.index("--port") + 1] == str(PORT)
            and argv[argv.index("--alias") + 1] == ALIAS):
        raise GateError("q8-KV service selectors changed")
    if value["environment"] != CURVE.load_manifest()["environment"]:
        raise GateError("quality environment differs from q8-KV curve")


def static_check() -> tuple[dict[str, Any], dict[str, str], list[list[str]]]:
    manifest = load_manifest(); validate_manifest(manifest); CURVE.R1.static_check()
    parent = manifest["curve_parent"]
    paths = {key: verify_ref(parent[key], f"curve {key}") for key in (
        "preregistration", "runner", "terminal_receipt", "exact_depth_receipt", "metadata", "graph_evidence")}
    terminal = CURVE.R1.load_json(paths["terminal_receipt"])
    receipt = CURVE.R1.load_json(paths["exact_depth_receipt"])
    if not (terminal.get("campaign_id") == parent["campaign_id"]
            and terminal.get("state") == "passed-raw-graph-cells-quality-pending"
            and terminal.get("cleanup_passed") is True
            and terminal.get("launched_depths") == parent["depths"]
            and terminal.get("protected_graph_off_values_replaced") is False
            and receipt.get("status") == "passed"
            and (receipt.get("gate") or {}).get("exact_cell_ready") is True
            and len(receipt.get("cells") or []) == 7
            and all((cell.get("selectors") or {}).get("kv") == "q8_0" for cell in receipt.get("cells") or [])):
        raise GateError("q8-KV curve parent is not a passed seven-cell packet")
    runtime = manifest["runtime"]
    server = verify_ref(runtime["server"], "llama-server", size=True)
    verify_ref(runtime["server_impl"], "server implementation")
    verify_ref(runtime["graph_backend"], "graph backend", size=True)
    quality = manifest["quality"]
    verify_ref(quality["helper"], "quality helper"); verify_ref(quality["python"], "quality Python")
    tokenizer = Path(quality["tokenizer"]["path"])
    if (sha256_file(tokenizer / "tokenizer.json") != quality["tokenizer"]["tokenizer_json_sha256"]
            or sha256_file(tokenizer / "tokenizer_config.json") != quality["tokenizer"]["tokenizer_config_sha256"]):
        raise GateError("tokenizer identity changed")
    for patch in manifest["source"]["patch_chain_in_order"]:
        verify_ref(patch, "source patch")
    environment = BASE.oneapi_environment(RUN_ROOT, manifest["environment"])
    libraries = BASE.effective_libraries(server, environment)
    closure = runtime["server_effective_shared_libraries"]
    if len(libraries) != closure["count"] or F16.canonical_sha256(libraries) != closure["canonical_json_sha256"]:
        raise GateError("server DSO closure changed")
    return manifest, environment, libraries


def stop_server(process: subprocess.Popen[bytes]) -> dict[str, Any]:
    term = kill = False
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM); term = True
        try: process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL); kill = True; process.wait(timeout=10)
    return {"term_sent": term, "kill_sent": kill, "process_group_empty": not F16.process_group_exists(process.pid)}


def wait_ready(process: subprocess.Popen[bytes], url: str) -> dict[str, Any]:
    import time
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        if process.poll() is not None: raise GateError(f"llama-server exited during readiness: {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=5) as response: value = json.loads(response.read())
            if any(row.get("id") == ALIAS for row in value.get("data", []) if isinstance(row, dict)): return value
        except Exception: time.sleep(2)
    raise GateError("llama-server readiness timeout")


def execute(ack: str) -> int:
    if ack != ACK: raise GateError(f"exact acknowledgement required: {ACK}")
    manifest, environment, libraries = static_check(); state, error, cleanup, head = "failed", None, False, ""
    with BASE.campaign_locks():
        head = BASE.require_clean_pushed_main(); BASE.require_idle()
        if RUN_ROOT.exists(): raise GateError(f"create-only output root exists: {RUN_ROOT}")
        fstype = subprocess.check_output(["/usr/bin/findmnt", "-n", "-o", "FSTYPE", "--target", str(RUN_ROOT.parent)], text=True).strip()
        if fstype != "ext4": raise GateError(f"output parent must be ext4, got {fstype}")
        RUN_ROOT.mkdir(mode=0o700)
        for name in ("runtime-home", "runtime-cache/sycl", "runtime-tmp"): (RUN_ROOT / name).mkdir(parents=True, exist_ok=False)
        server_log = RUN_ROOT / "server.log"; process = None
        try:
            with server_log.open("xb") as log:
                process = subprocess.Popen(manifest["server_argv"], cwd=REPO, env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                BASE.write_json_exclusive(RUN_ROOT / "models.json", wait_ready(process, f"http://127.0.0.1:{PORT}/v1/models"))
                quality = manifest["quality"]
                result = subprocess.run([quality["python"]["path"], "-I", "-B", str(resolve(quality["helper"]["path"])),
                    "--base-url", f"http://127.0.0.1:{PORT}", "--model", ALIAS, "--tokenizer", quality["tokenizer"]["path"],
                    "--timeout", "3600", "--repeat-runs", "8", "--long-context-tokens", "31744",
                    "--request-id-prefix", CAMPAIGN_ID, "--output-json", str(RUN_ROOT / "quality.json")],
                    cwd=REPO, env=environment, text=True, capture_output=True, timeout=7200, check=False)
                (RUN_ROOT / "quality.stdout.json").write_text(result.stdout, encoding="utf-8")
                (RUN_ROOT / "quality.stderr.log").write_text(result.stderr, encoding="utf-8")
                if result.returncode != 0: raise GateError(f"quality helper exited {result.returncode}")
            cleanup_row = stop_server(process); process = None
            if not cleanup_row["process_group_empty"]: raise GateError("server process group remained live")
            quality_gate = F16.validate_quality(CURVE.R1.load_json(RUN_ROOT / "quality.json"), manifest)
            graph_gate = F16.graph_evidence(server_log.read_text(encoding="utf-8", errors="replace"))
            BASE.write_json_exclusive(RUN_ROOT / "quality-gate.json", {"passed": True, "quality": quality_gate, "graph": graph_gate, "server_effective_shared_libraries": libraries})
            BASE.require_idle(); cleanup = True; state = "passed-quality-prerequisite-awaiting-tracked-adjudication"
        except Exception as exc:
            error = str(exc)
            if process is not None:
                try: cleanup = stop_server(process)["process_group_empty"]
                except Exception as cleanup_exc: error += f"; cleanup: {cleanup_exc}"
        terminal = {"schema": "neural.download.qwen36-llama-exact-depth-terminal.v1", "campaign_id": CAMPAIGN_ID,
            "state": state, "created_at_utc": dt.datetime.now(dt.UTC).isoformat(), "lab_git_head": head,
            "cleanup_passed": cleanup, "error": error, "quality_covers_depths": manifest["curve_parent"]["depths"] if state.startswith("passed-") else [],
            "quality_claim_authorized": False, "raw_terminal_writer_caveat": "tracked adjudication required",
            "raw_engine_speed_measurements_unchanged": True, "mixed_partial_prefill_graph_claim_preserved": True,
            "site_publication_authorized": False, "record_or_submission_authorized": False, "protected_graph_off_values_replaced": False}
        BASE.write_json_exclusive(RUN_ROOT / "terminal-receipt.json", terminal)
    print(json.dumps(terminal, indent=2, sort_keys=True)); return 0 if state.startswith("passed-") else 20


def plan(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {"campaign_id": CAMPAIGN_ID, "state": manifest["state"], "default_is_inert": True, "output_root": str(RUN_ROOT),
        "ack": ACK, "request_count": 13, "kv": "q8_0", "quality_may_cover_all_seven_curve_cells_on_pass": True,
        "site_publication_authorized": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true"); mode.add_argument("--execute", action="store_true"); parser.add_argument("--ack", default="")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(); validate_manifest(manifest)
        if args.execute: return execute(args.ack)
        payload = {"status": "PASS", "launched": False, **plan(manifest)} if args.check else plan(manifest)
        if args.check: static_check()
        print(json.dumps(payload, indent=2, sort_keys=True)); return 0
    except (GateError, CURVE.GateError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
