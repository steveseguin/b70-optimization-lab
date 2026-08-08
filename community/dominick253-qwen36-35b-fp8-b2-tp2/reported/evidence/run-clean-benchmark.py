#!/usr/bin/env python3
"""Run a clean llama-benchy sweep and reject overlapping endpoint traffic."""

import json
import os
import pathlib
import re
import subprocess
import threading
import time
import urllib.request

METRICS = "http://127.0.0.1:8001/metrics"
ROOT = pathlib.Path("/home/dom/scripts")
LABEL = os.environ.get("BENCH_LABEL", "clean-20260806")
RESULT = ROOT / f"qwen36-35b-fp8-concurrency-mtp-{LABEL}.json"
LOG = ROOT / f"qwen36-35b-fp8-concurrency-mtp-{LABEL}.txt"
MONITOR = ROOT / f"qwen36-35b-fp8-concurrency-mtp-{LABEL}-monitor.json"
CONCURRENCY = (1, 2, 4, 8, 12)
RUNS = 5
WARMUPS = 1


def metrics() -> dict[str, float]:
    text = urllib.request.urlopen(METRICS, timeout=5).read().decode()

    def total(name: str) -> float:
        values = re.findall(
            rf"^{re.escape(name)}{{[^\n]*}}\s+([0-9.eE+-]+)$", text, re.MULTILINE
        )
        return sum(float(value) for value in values)

    return {
        "success": total("vllm:request_success_total"),
        "running": total("vllm:num_requests_running"),
        "waiting": total("vllm:num_requests_waiting"),
    }


def fault_count() -> int:
    command = (
        "journalctl -k -b --no-pager | grep -Ec "
        "'xe 0000:(03|08):00.0.*(Faulted Address|Engine memory|Timedout job|"
        "Engine reset|CAT error|Fault response)' || true"
    )
    result = subprocess.run(command, shell=True, check=False, text=True, capture_output=True)
    return int(result.stdout.strip() or 0)


def main() -> int:
    before = metrics()
    faults_before = fault_count()
    samples: list[dict] = []
    stop = threading.Event()

    def watch() -> None:
        while not stop.is_set():
            try:
                sample = {"timestamp": time.time(), **metrics()}
            except Exception as error:  # monitoring must not kill the benchmark
                sample = {"timestamp": time.time(), "error": repr(error)}
            samples.append(sample)
            stop.wait(0.1)

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    command = [
        "/home/dom/llama-benchy/.venv/bin/llama-benchy",
        "--base-url",
        "http://127.0.0.1:8001/v1",
        "--model",
        "qwen36-35b-fp8",
        "--tokenizer",
        "Qwen/Qwen3.6-35B-A3B-FP8",
        "--pp",
        "1024",
        "--tg",
        "256",
        "--exact-tg",
        "--depth",
        "0",
        "--concurrency",
        *(str(value) for value in CONCURRENCY),
        "--runs",
        str(RUNS),
        "--warmup-runs",
        str(WARMUPS),
        "--save-result",
        str(RESULT),
        "--format",
        "json",
    ]
    try:
        process = subprocess.run(
            command,
            cwd="/home/dom/llama-benchy",
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=1200,
        )
    finally:
        stop.set()
        thread.join(timeout=2)

    LOG.write_text(process.stdout, encoding="utf-8")
    after = metrics()
    for _ in range(600):
        after = metrics()
        if after["running"] == 0 and after["waiting"] == 0:
            break
        time.sleep(0.1)

    faults_after = fault_count()
    # Two tokenizer warmups, one coherence request, then each benchmark batch.
    # The default API latency probes are GET /models and do not increment this
    # completion counter.
    expected_requests = 3 + (RUNS + WARMUPS) * sum(CONCURRENCY)
    actual_requests = int(after["success"] - before["success"])
    report = {
        "command": command,
        "started_success_total": before["success"],
        "ended_success_total": after["success"],
        "expected_requests": expected_requests,
        "actual_requests": actual_requests,
        "request_count_clean": actual_requests == expected_requests,
        "max_running": max((float(row.get("running", 0)) for row in samples), default=0),
        "max_waiting": max((float(row.get("waiting", 0)) for row in samples), default=0),
        "faults_before": faults_before,
        "faults_after": faults_after,
        "new_faults": faults_after - faults_before,
        "benchmark_exit_code": process.returncode,
        "samples": samples,
    }
    MONITOR.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(process.stdout)
    print(json.dumps({key: value for key, value in report.items() if key not in ("command", "samples")}, indent=2))
    return 0 if process.returncode == 0 and actual_requests == expected_requests and faults_after == faults_before else 1


if __name__ == "__main__":
    raise SystemExit(main())
