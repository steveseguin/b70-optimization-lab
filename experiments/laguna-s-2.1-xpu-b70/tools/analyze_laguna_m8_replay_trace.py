#!/usr/bin/env python3
"""Fail-closed reduction of paired eager/graph Laguna replay traces."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def die(message: str) -> None:
    raise SystemExit(f"Laguna M8 replay trace analysis: {message}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def section_total(text: str, section: str, label: str) -> int | None:
    match = re.search(
        rf"=== {re.escape(section)} ===(?P<body>.*?)(?=\n=== |\Z)",
        text,
        flags=re.DOTALL,
    )
    if match is None:
        return None
    value = re.search(
        rf"{re.escape(label)}\s*:\s*([0-9]+)", match.group("body")
    )
    return int(value.group(1)) if value else None


def trace_records(arm_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(arm_dir.glob("unitrace.*")):
        if not path.is_file() or path.is_symlink() or ".json" in path.name:
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        if not raw.strip():
            continue
        record = {
            "path": str(path),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "has_host_timing": "=== API Timing Summary ===" in raw,
            "has_device_timing": "=== Device Timing Summary ===" in raw,
            "has_kernel_submission": "=== Kernel Submission Summary ===" in raw,
            "device_l0_ns": section_total(
                raw, "Device Timing Summary", "Total Device Time for L0 backend (ns)"
            ),
            "api_l0_ns": section_total(
                raw, "API Timing Summary", "Total API Time for L0 backend (ns)"
            ),
            "submission_l0_ns": section_total(
                raw,
                "Kernel Submission Summary",
                "Total Device Time for L0 backend (ns)",
            ),
        }
        if any(
            record[key]
            for key in (
                "has_host_timing",
                "has_device_timing",
                "has_kernel_submission",
            )
        ):
            records.append(record)
    return records


def main() -> int:
    args = parse_args()
    root = args.run_dir.resolve(strict=True)
    if args.out.exists():
        die("refusing to overwrite analysis")
    arms: dict[str, Any] = {}
    for arm in ("eager", "graph"):
        arm_dir = root / arm
        driver_path = arm_dir / "driver.json"
        if not driver_path.is_file() or driver_path.is_symlink():
            die(f"{arm} driver evidence is missing")
        driver = json.loads(driver_path.read_text())
        required = {
            "schema": "laguna-m8-replay-trace-arm-v1",
            "status": "complete",
            "diagnostic_only": True,
            "not_benchmark_evidence": True,
            "single_generate_call": True,
            "fresh_process": True,
            "arm": arm,
            "cached_tokens": 0,
            "completion_tokens": 128,
        }
        for key, expected in required.items():
            if driver.get(key) != expected:
                die(f"{arm} driver {key} drifted")
        traces = trace_records(arm_dir)
        complete = [
            row
            for row in traces
            if row["has_host_timing"]
            and row["has_device_timing"]
            and row["has_kernel_submission"]
            and isinstance(row["api_l0_ns"], int)
            and row["api_l0_ns"] > 0
            and isinstance(row["device_l0_ns"], int)
            and row["device_l0_ns"] > 0
            and isinstance(row["submission_l0_ns"], int)
            and row["submission_l0_ns"] > 0
        ]
        if len(complete) != 4:
            die(
                f"{arm} produced {len(complete)} complete worker traces, "
                "expected exactly four"
            )
        pids = []
        for row in complete:
            match = re.fullmatch(r"unitrace\.([1-9][0-9]*)", Path(row["path"]).name)
            if match is None:
                die(f"{arm} trace lacks a PID-bound filename: {row['path']}")
            pids.append(int(match.group(1)))
        if len(set(pids)) != 4:
            die(f"{arm} traces do not bind four unique worker PIDs")
        stderr_path = arm_dir / "stderr.log"
        stdout_path = arm_dir / "stdout.log"
        if not stderr_path.is_file() or stderr_path.is_symlink():
            die(f"{arm} stderr evidence is missing")
        if not stdout_path.is_file() or stdout_path.is_symlink():
            die(f"{arm} stdout evidence is missing")
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
        session = driver.get("session")
        if stderr.count(f"[INFO] Session {session} is paused\n") != 1:
            die(f"{arm} lacks one fresh start-paused acknowledgement")
        captures = [
            line
            for line in stdout.splitlines()
            if "Captured audited breakable cudagraph" in line
        ]
        replays = [
            line
            for line in stdout.splitlines()
            if "Replayed audited breakable cudagraph" in line
        ]
        if arm == "graph":
            topology = "BreakableCUDAGraphCapture(graphs=146, eager_breaks=145)"
            rank_pattern = re.compile(r"Worker_TP([0-3])_EP([0-3])")
            capture_ranks = {
                tuple(map(int, match.groups()))
                for line in captures
                if (match := rank_pattern.search(line))
            }
            replay_ranks = {
                tuple(map(int, match.groups()))
                for line in replays
                if (match := rank_pattern.search(line))
            }
            expected_ranks = {(0, 0), (1, 1), (2, 2), (3, 3)}
            if (
                len(captures) != 4
                or len(replays) != 4
                or capture_ranks != expected_ranks
                or replay_ranks != expected_ranks
                or any(topology not in line for line in captures + replays)
            ):
                die("graph arm lacks the four-rank audited 146/145 topology")
            if (
                stdout.count(
                    "Resumed audited Laguna PTI session at first graph replay"
                )
                != 1
            ):
                die("graph arm lacks one rank-zero first-replay resume proof")
        elif captures or replays:
            die("eager arm unexpectedly captured or replayed a Breakable graph")
        arms[arm] = {
            "driver": driver,
            "driver_path": str(driver_path),
            "driver_sha256": sha256_file(driver_path),
            "trace_files": complete,
            "auxiliary_trace_files": [
                row for row in traces if row not in complete
            ],
            "auxiliary_trace_count": len(traces) - len(complete),
            "worker_pids": sorted(pids),
            "device_trace_count": len(complete),
            "device_l0_ns": [
                row["device_l0_ns"]
                for row in complete
                if row["device_l0_ns"] is not None
            ],
            "api_l0_ns": [row["api_l0_ns"] for row in complete],
            "submission_l0_ns": [
                row["submission_l0_ns"] for row in complete
            ],
            "generation_wall_ns": driver["generation_wall_ns"],
            "graph_capture_log_count": len(captures),
            "graph_replay_log_count": len(replays),
            "stderr_sha256": sha256_file(stderr_path),
            "stdout_sha256": sha256_file(stdout_path),
        }

    eager = arms["eager"]["driver"]
    graph = arms["graph"]["driver"]
    exact_fields = (
        "prompt_sha256",
        "prompt_tokens",
        "completion_tokens",
        "token_ids",
        "token_ids_sha256",
        "text_sha256",
        "finish_reason",
    )
    mismatched = [key for key in exact_fields if eager.get(key) != graph.get(key)]
    if mismatched:
        die(f"eager/graph greedy outputs differ: {mismatched}")
    result = {
        "schema": "laguna-m8-replay-trace-analysis-v1",
        "status": "pass",
        "diagnostic_only": True,
        "not_benchmark_or_submission_evidence": True,
        "bitwise_exact": True,
        "exact_fields": list(exact_fields),
        "arms": arms,
        "wall_speedup": (
            arms["eager"]["generation_wall_ns"]
            / arms["graph"]["generation_wall_ns"]
        ),
    }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        "Laguna M8 replay trace analysis PASS: "
        f"wall_speedup={result['wall_speedup']:.4f}x"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
