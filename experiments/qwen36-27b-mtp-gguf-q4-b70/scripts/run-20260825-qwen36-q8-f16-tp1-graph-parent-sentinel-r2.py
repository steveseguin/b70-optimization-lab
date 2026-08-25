#!/usr/bin/env python3
"""Fresh R2 wrapper for the hardened Qwen3.6 Q8 graph parent sentinel."""

from __future__ import annotations

import copy
import datetime as dt
import importlib.util
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


HERE = Path(__file__).resolve().parent
BASE_SCRIPT = HERE / "run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r1.py"
SPEC = importlib.util.spec_from_file_location("qwen36_graph_parent_sentinel_r1_base", BASE_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import frozen base runner: {BASE_SCRIPT}")
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)

R1_MANIFEST = BASE.MANIFEST
R2_MANIFEST = BASE.LANE / "data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r2-prereg.json"
ORIGINAL_LOAD_JSON = BASE.load_json
R2_CAMPAIGN_ID = "qwen36-q8-f16-tp1-graph-sentinel-20260825-r2"
R2_RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-graph-sentinel-20260825-r2")
R2_ACK = f"RUN {R2_CAMPAIGN_ID}"
R2_EXTRA_ARGV = (
    "--single-turn", "--no-show-timings", "--log-verbosity", "4",
)


def effective_manifest() -> dict[str, Any]:
    base = copy.deepcopy(ORIGINAL_LOAD_JSON(R1_MANIFEST))
    delta = ORIGINAL_LOAD_JSON(R2_MANIFEST)
    if delta != {
        **delta,
        "campaign_id": R2_CAMPAIGN_ID,
        "state": "preregistered-not-launched",
    }:
        raise BASE.GateError("R2 delta campaign/state invariant failed")
    if delta.get("base_manifest") != str(R1_MANIFEST.relative_to(BASE.REPO)):
        raise BASE.GateError("R2 base-manifest reference changed")
    if tuple(delta.get("common_argv_append_before_prompt") or ()) != R2_EXTRA_ARGV:
        raise BASE.GateError("R2 common argv delta changed")
    lifecycle = delta.get("lifecycle_delta") or {}
    if lifecycle != {
        "output_root": str(R2_RUN_ROOT),
        "exact_ack": R2_ACK,
        "child_stdin": "/dev/null",
        "single_turn_required": True,
        "ui_timings_disabled": True,
        "graph_log_verbosity": 4,
    }:
        raise BASE.GateError("R2 lifecycle delta changed")
    predecessor = delta.get("predecessor") or {}
    if not (
        predecessor.get("classification") == "failed-incomplete-harness-lifecycle"
        and predecessor.get("terminal_sha256")
        == "dfe5befea05b65df0271e3b00c0ba69f2fa847e4330b41b2eba5c1e1651f70c8"
        and predecessor.get("control_stdout_sha256")
        == "887eaca797104ec80fab21ab8634416f95647bb0ee4b461a801a2f9970fafdc3"
        and predecessor.get("reuse_any_arm") is False
    ):
        raise BASE.GateError("R1 quarantine identity changed")

    prompt_index = base["canary"]["common_argv"].index("--prompt")
    base["canary"]["common_argv"][prompt_index:prompt_index] = list(R2_EXTRA_ARGV)
    base["campaign_id"] = R2_CAMPAIGN_ID
    base["purpose"] = delta["purpose"]
    base["lifecycle"].update(lifecycle)
    base["r2_delta"] = delta
    return base


def r2_load_json(path: Path) -> dict[str, Any]:
    if path == R2_MANIFEST:
        return effective_manifest()
    return ORIGINAL_LOAD_JSON(path)


def run_process_group(
    *, name: str, argv: Sequence[str], environment: Mapping[str, str],
    stdout_path: Path, stderr_path: Path, timeout_seconds: float,
    grace_seconds: float = 10,
) -> dict[str, Any]:
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    begin = time.monotonic()
    timed_out = False
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.Popen(
            list(argv), env=dict(environment), cwd=BASE.REPO,
            stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            start_new_session=True,
        )
        cleanup = {"term_sent": False, "kill_sent": False, "process_group_empty": False}
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            cleanup = BASE.stop_process_group(process, grace_seconds)
    receipt = {
        "name": name,
        "pid": process.pid,
        "pgid": process.pid,
        "started_utc": started,
        "elapsed_seconds": time.monotonic() - begin,
        "return_code": process.returncode,
        "timed_out": timed_out,
        "stdin": "/dev/null",
        **cleanup,
    }
    if timed_out:
        raise BASE.GateError(f"{name} timed out; process group was cleaned")
    if process.returncode != 0:
        raise BASE.GateError(f"{name} exited {process.returncode}")
    return receipt


BASE.CAMPAIGN_ID = R2_CAMPAIGN_ID
BASE.ACK = R2_ACK
BASE.RUN_ROOT = R2_RUN_ROOT
BASE.MANIFEST = R2_MANIFEST
prompt_at = BASE.COMMON_ARGV.index("--prompt")
BASE.COMMON_ARGV = BASE.COMMON_ARGV[:prompt_at] + R2_EXTRA_ARGV + BASE.COMMON_ARGV[prompt_at:]
BASE.PACKET_PATHS = (
    "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-prereg.json",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r1.py",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r1-result.json",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r1-result.md",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r2-prereg.json",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r2-preregistration.md",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r2.py",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/test_qwen36_q8_f16_tp1_graph_parent_sentinel_r2.py",
)
BASE.load_json = r2_load_json
BASE.run_process_group = run_process_group


if __name__ == "__main__":
    raise SystemExit(BASE.main())
