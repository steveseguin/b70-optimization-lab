#!/usr/bin/env python3
"""Run the sealed Qwen3.6 target-Q8/F16 TP1 graph-on quality battery."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any, Mapping
import urllib.request


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-q8-f16-tp1-sycl-graph-quality-r1-prereg.json"
CURVE_RUNNER = LANE / "scripts/run-20260825-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r4.py"
CAMPAIGN_ID = "qwen36-q8-f16-tp1-sycl-graph-quality-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-sycl-graph-quality-20260825-r1")


def _load_curve():
    spec = importlib.util.spec_from_file_location("qwen36_graph_curve_r4_for_quality", CURVE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import curve runner: {CURVE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CURVE = _load_curve()
BASE = CURVE.R1.BASE
GateError = BASE.GateError


def sha256_file(path: Path) -> str:
    return CURVE.sha256_file(path)


def load_json(path: Path) -> dict[str, Any]:
    return CURVE.R1.load_json(path)


def load_manifest() -> dict[str, Any]:
    return load_json(MANIFEST)


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


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def validate_manifest(value: Mapping[str, Any]) -> None:
    curve = value.get("curve_parent") or {}
    selectors = value.get("selectors") or {}
    quality = value.get("quality") or {}
    lifecycle = value.get("lifecycle") or {}
    authority = value.get("authority") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-sycl-graph-quality-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "sealed-preregistered-not-launched"
        and curve.get("campaign_id") == "qwen36-q8-f16-tp1-sycl-graph-exact-depth-20260825-r4"
        and curve.get("depths") == [0, 2048, 4096, 8192, 16384, 24576, 32768]
        and selectors == {
            "revision": "qwen3.6-27b", "artifact_id": "qwen36-27b-unsloth-q8-0-82d411a",
            "quantization": "Q8_0", "runtime_family": "llama.cpp SYCL", "tp": 1,
            "mtp": 0, "graph_mode": "SYCL", "kv": "f16",
        }
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
    ):
        raise GateError("graph quality manifest invariant failed")
    argv = value.get("server_argv")
    if not isinstance(argv, list) or argv[0] != value["runtime"]["server"]["path"]:
        raise GateError("server argv identity changed")
    for flag, expected in (("-c", "32768"), ("-ctk", "f16"), ("-ctv", "f16"), ("--spec-type", "none")):
        if argv.count(flag) != 1 or argv[argv.index(flag) + 1] != expected:
            raise GateError(f"server argv selector changed: {flag}")
    if value["environment"] != CURVE.load_manifest()["environment"]:
        raise GateError("quality environment differs from the passed curve")


def static_check() -> tuple[dict[str, Any], dict[str, str], list[list[str]]]:
    manifest = load_manifest()
    validate_manifest(manifest)
    # R4 deliberately rebinds the mature R1 lifecycle rather than exporting a
    # duplicate static checker.  Calling the rebound checker validates the
    # synthesized R4 manifest and every inherited sealed identity.
    CURVE.R1.static_check()
    parent = manifest["curve_parent"]
    paths = {key: verify_ref(parent[key], f"curve {key}") for key in (
        "preregistration", "runner", "terminal_receipt", "exact_depth_receipt", "metadata", "graph_evidence")}
    terminal = load_json(paths["terminal_receipt"])
    receipt = load_json(paths["exact_depth_receipt"])
    if not (
        terminal.get("campaign_id") == parent["campaign_id"]
        and terminal.get("state") == "passed-raw-graph-cells-quality-pending"
        and terminal.get("cleanup_passed") is True
        and terminal.get("launched_depths") == parent["depths"]
        and terminal.get("protected_graph_off_values_replaced") is False
        and receipt.get("status") == "passed"
        and (receipt.get("gate") or {}).get("exact_cell_ready") is True
        and len(receipt.get("cells") or []) == 7
    ):
        raise GateError("curve parent is not a passed seven-cell raw packet")
    runtime = manifest["runtime"]
    server = verify_ref(runtime["server"], "llama-server", size=True)
    verify_ref(runtime["server_impl"], "llama-server implementation")
    verify_ref(runtime["graph_backend"], "graph backend", size=True)
    quality = manifest["quality"]
    verify_ref(quality["helper"], "quality helper")
    verify_ref(quality["python"], "quality Python")
    tokenizer = Path(quality["tokenizer"]["path"])
    if (
        sha256_file(tokenizer / "tokenizer.json") != quality["tokenizer"]["tokenizer_json_sha256"]
        or sha256_file(tokenizer / "tokenizer_config.json") != quality["tokenizer"]["tokenizer_config_sha256"]
    ):
        raise GateError("tokenizer identity changed")
    for patch in manifest["source"]["patch_chain_in_order"]:
        verify_ref(patch, "source patch")
    environment = BASE.oneapi_environment(RUN_ROOT, manifest["environment"])
    libraries = BASE.effective_libraries(server, environment)
    closure = runtime["server_effective_shared_libraries"]
    if len(libraries) != closure["count"] or canonical_sha256(libraries) != closure["canonical_json_sha256"]:
        raise GateError("llama-server effective DSO closure changed")
    return manifest, environment, libraries


def cached_counts(quality: Mapping[str, Any]) -> list[int | None]:
    rows = [item for item in quality.get("exact_cases", []) if isinstance(item, dict)]
    repeat = quality.get("repeat_case") or {}
    rows.extend(item for item in repeat.get("runs", []) if isinstance(item, dict))
    long_context = quality.get("long_context_case")
    if isinstance(long_context, dict):
        rows.append(long_context)
    result: list[int | None] = []
    for row in rows:
        usage = row.get("usage") or {}
        details = usage.get("prompt_tokens_details") or {}
        value = details.get("cached_tokens")
        result.append(value if type(value) is int else None)
    return result


def validate_quality(value: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    exact = value.get("exact_cases") or []
    repeat = value.get("repeat_case") or {}
    long_case = value.get("long_context_case") or {}
    counts = cached_counts(value)
    if not (
        value.get("pass_all") is True
        and len(exact) == manifest["quality"]["exact_case_count"]
        and all(item.get("pass") is True for item in exact if isinstance(item, dict))
        and repeat.get("repeats") == manifest["quality"]["repeat_runs"]
        and repeat.get("pass") is True
        and len(repeat.get("unique_hashes") or []) == 1
        and long_case.get("requested_context_tokens") == manifest["quality"]["near_32k_needle_target_tokens"]
        and long_case.get("pass") is True
        and len(counts) == manifest["quality"]["expected_request_count"]
        and all(count == 0 for count in counts)
    ):
        raise GateError("quality battery did not pass all objective/cache-zero gates")
    return {"request_count": len(counts), "cached_tokens": counts, "actual_prompt_tokens": long_case.get("actual_prompt_tokens")}


def graph_evidence(text: str) -> dict[str, int]:
    rows = [{key: int(item) for key, item in match.groupdict().items()} for match in CURVE.R1.SUMMARY_RE.finditer(text)]
    if not rows:
        raise GateError("server emitted no SYCL graph summary")
    result = {key: sum(row[key] for row in rows) for key in rows[0] if key not in {"device", "cache_entries", "cache_limit"}}
    result.update({"device": 0, "cache_entries": max(row["cache_entries"] for row in rows), "cache_limit": 8, "summary_count": len(rows)})
    if not (
        all(row["device"] == 0 and row["cache_limit"] == 8 and row["compatibility_rejected"] == 0 and row["device_unsupported"] == 0 for row in rows)
        and result["requested"] > 0 and result["recorded"] > 0 and result["created"] > 0
        and result["direct_replay"] > 0 and result["replayed"] > 0
    ):
        raise GateError("server graph mechanism evidence failed")
    return result


def process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


def stop_server(process: subprocess.Popen[bytes]) -> dict[str, Any]:
    term = kill = False
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM); term = True
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL); kill = True
            process.wait(timeout=10)
    return {"term_sent": term, "kill_sent": kill, "process_group_empty": not process_group_exists(process.pid)}


def wait_ready(process: subprocess.Popen[bytes], url: str, alias: str) -> dict[str, Any]:
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise GateError(f"llama-server exited during readiness: {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                value = json.loads(response.read())
            if any(row.get("id") == alias for row in value.get("data", []) if isinstance(row, dict)):
                return value
        except Exception:
            time.sleep(2)
    raise GateError("llama-server readiness timeout")


def execute(ack: str) -> int:
    if ack != ACK:
        raise GateError(f"exact acknowledgement required: {ACK}")
    manifest, environment, libraries = static_check()
    state, error, cleanup = "failed", None, False
    head = ""
    with BASE.campaign_locks():
        head = BASE.require_clean_pushed_main()
        BASE.require_idle()
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
                models = wait_ready(process, "http://127.0.0.1:19436/v1/models", "qwen36-q8-f16-tp1-graph-quality-r1")
                BASE.write_json_exclusive(RUN_ROOT / "models.json", models)
                quality = manifest["quality"]
                result = subprocess.run([
                    quality["python"]["path"], "-I", "-B", str(resolve(quality["helper"]["path"])),
                    "--base-url", "http://127.0.0.1:19436", "--model", "qwen36-q8-f16-tp1-graph-quality-r1",
                    "--tokenizer", quality["tokenizer"]["path"], "--timeout", "3600", "--repeat-runs", "8",
                    "--long-context-tokens", "31744", "--request-id-prefix", CAMPAIGN_ID,
                    "--output-json", str(RUN_ROOT / "quality.json"),
                ], cwd=REPO, env=environment, text=True, capture_output=True, timeout=7200, check=False)
                (RUN_ROOT / "quality.stdout.json").write_text(result.stdout, encoding="utf-8")
                (RUN_ROOT / "quality.stderr.log").write_text(result.stderr, encoding="utf-8")
                if result.returncode != 0:
                    raise GateError(f"quality helper exited {result.returncode}")
            cleanup_row = stop_server(process); process = None
            if not cleanup_row["process_group_empty"]:
                raise GateError("server process group remained live")
            quality_gate = validate_quality(load_json(RUN_ROOT / "quality.json"), manifest)
            graph_gate = graph_evidence(server_log.read_text(encoding="utf-8", errors="replace"))
            BASE.write_json_exclusive(RUN_ROOT / "quality-gate.json", {"passed": True, "quality": quality_gate, "graph": graph_gate, "server_effective_shared_libraries": libraries})
            BASE.require_idle(); cleanup = True
            state = "passed-quality-covers-seven-raw-curve-cells"
        except Exception as exc:
            error = str(exc)
            if process is not None:
                try:
                    cleanup = stop_server(process)["process_group_empty"]
                except Exception as cleanup_exc:
                    error += f"; cleanup: {cleanup_exc}"
        terminal = {
            "schema": "neural.download.qwen36-llama-sycl-graph-quality-terminal.v1", "campaign_id": CAMPAIGN_ID,
            "state": state, "created_at_utc": dt.datetime.now(dt.UTC).isoformat(), "lab_git_head": head,
            "cleanup_passed": cleanup, "error": error, "quality_covers_depths": manifest["curve_parent"]["depths"] if state.startswith("passed-") else [],
            "raw_engine_speed_measurements_unchanged": True, "mixed_partial_prefill_graph_claim_preserved": True,
            "site_publication_authorized": False, "record_or_submission_authorized": False,
            "protected_graph_off_values_replaced": False,
        }
        BASE.write_json_exclusive(RUN_ROOT / "terminal-receipt.json", terminal)
    print(json.dumps(terminal, indent=2, sort_keys=True))
    return 0 if state.startswith("passed-") else 20


def plan(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {"campaign_id": CAMPAIGN_ID, "state": manifest["state"], "default_is_inert": True, "output_root": str(RUN_ROOT), "ack": ACK, "request_count": 13, "quality_may_cover_all_seven_curve_cells_on_pass": True, "site_publication_authorized": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(); mode.add_argument("--check", action="store_true"); mode.add_argument("--execute", action="store_true")
    parser.add_argument("--ack", default=""); args = parser.parse_args(argv)
    try:
        manifest = load_manifest(); validate_manifest(manifest)
        if args.execute:
            return execute(args.ack)
        if args.check:
            static_check(); payload = {"status": "PASS", "launched": False, **plan(manifest)}
        else:
            payload = plan(manifest)
        print(json.dumps(payload, indent=2, sort_keys=True)); return 0
    except (GateError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
