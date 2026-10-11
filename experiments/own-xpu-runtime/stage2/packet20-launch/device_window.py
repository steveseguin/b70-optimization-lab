#!/usr/bin/env python3
"""CPU check or separately authorized one-card packet20 window. Never auto-retry."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import statistics
import subprocess
import time

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
LATCH = BUILD / "device-fault-latch.json"
PREFIX = ["nice", "-n", "19", "ionice", "-c", "3", "env", "OMP_NUM_THREADS=2"]
FAULT = re.compile(r"Fault response|CAT error|engine.*reset|reset.*engine|devcoredump|device coredump|GPU.*coredump|GuC.*(?:hang|lockup)|timed.out.*(?:job|fence)", re.I)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")

def require(value, reason):
    if not value:
        raise ValueError(reason)

def journal(cursor=None):
    args = PREFIX + ["journalctl", "-k", "--no-pager", "--show-cursor"]
    args += ["--after-cursor", cursor] if cursor else ["-n", "200"]
    p = subprocess.run(args, capture_output=True, text=True, timeout=2)
    require(p.returncode == 0 and not p.stderr.strip(), "kernel journal unavailable: " + p.stderr)
    lines = p.stdout.splitlines()
    positions = [s[11:] for s in lines if s.startswith("-- cursor: ")]
    require(positions or cursor, "missing kernel journal cursor")
    return "\n".join(s for s in lines if not s.startswith("-- cursor: ")) + "\n", positions[-1] if positions else cursor

def ldd_preflight(binary, runner=None):
    p = (runner or subprocess.run)(PREFIX + ["ldd", str(binary)], capture_output=True, text=True, timeout=10)
    require(p.returncode == 0 and "not found" not in p.stdout + p.stderr, "ldd preflight failed: " + p.stdout + p.stderr)
    return dict(returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)

def check(card, output):
    require(0 <= card < 4, "one physical card index 0..3 required")
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and os.environ.get("OMP_NUM_THREADS") == "2", "nice19 and OMP_NUM_THREADS=2 required")
    p = subprocess.run(PREFIX + ["ionice", "-p", str(os.getpid())], capture_output=True, text=True, timeout=2)
    require(p.returncode == 0 and "idle" in p.stdout, "ionice -c3 required")
    for key in ("ONEAPI_DEVICE_SELECTOR", "SYCL_DEVICE_FILTER", "ZE_AFFINITY_MASK"):
        require(not os.environ.get(key), "unmasked physical card mapping required: " + key)
    out = output.resolve()
    require(not BUILD.is_symlink() and BUILD in out.parents and not out.exists(), "fresh output beneath packet20/build required")
    require(not LATCH.exists(), "unresolved packet20 latch; coordinator review required")
    manifest = json.loads((BUILD / "prepared.json").read_text())
    require(manifest.get("passed") is True and manifest.get("device_executed") is False, "invalid CPU preparation")
    for rel, digest in manifest["hashes"].items():
        path = HERE / rel
        require(sha(path) == digest, "changed prepared identity: " + rel)
    binary = HERE / manifest["binary"]
    loader = ldd_preflight(binary)  # Always before creating a latch or invoking native code.
    return out, binary, manifest, loader

def latch(value):
    # Preserve the first reason. A concurrent admission cannot overwrite it.
    try:
        fd = os.open(LATCH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return
    with os.fdopen(fd, "w") as f:
        json.dump(value, f, indent=2)
        f.write("\n")

def supervise(child, kernel, cursor, requested, persist, now=time.monotonic, sleep=time.sleep, reader=journal, seconds=50, drain_seconds=5):
    start = now()
    sent = None
    while True:
        try:
            text, cursor = reader(cursor)
            kernel.write(text)
            kernel.flush()
            if FAULT.search(text):
                requested.append("new GPU fault")
        except Exception as error:
            requested.append("journal lost: " + str(error))
        if now() - start >= seconds:
            requested.append("50-second work deadline")
        if requested and sent is None:
            latch(dict(reason=requested[0], pid=child.pid))
            if child.poll() is None:
                child.send_signal(signal.SIGTERM)  # Only the child created by this window.
            sent = now()
            persist()
        if child.poll() is not None:
            break
        if sent is not None and now() - sent >= drain_seconds:
            requested.append("bounded drain expired; child retained for coordinator")
            return dict(returncode=None, child_still_running=True, elapsed_seconds=now()-start)
        sleep(.05)
    until = now() + 3
    while now() < until:
        sleep(min(.1, until - now()))
        try:
            text, cursor = reader(cursor)
            kernel.write(text)
            kernel.flush()
            if FAULT.search(text):
                requested.append("postflight GPU fault")
        except Exception as error:
            requested.append("postflight journal lost: " + str(error))
    if requested:
        latch(dict(reason=requested[0], pid=child.pid))
    return dict(returncode=child.returncode, child_still_running=False, elapsed_seconds=now()-start)

METHODS = ("explicit_in_order", "explicit_out_of_order", "explicit_wait_each", "implicit_in_order", "discard_in_order", "graph", "raw_regular", "raw_immediate", "fusion8")
WORKLOADS = ("bf16_elementwise_17ptr", "gemv_like")

def validate_rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    expected = {(m, w, n, r) for m in METHODS for w in WORKLOADS for n in (100, 1000, 4000) for r in range(5)}
    keys = [(r.get("method"), r.get("workload"), r.get("n"), r.get("repeat")) for r in rows]
    require(len(keys) == len(expected) and set(keys) == expected, "missing/duplicate issuing matrix rows")
    for row in rows:
        launches = (row["n"] + 7)//8 if row["method"] == "fusion8" else row["n"]
        require(row.get("launches") == launches, "physical launch denominator mismatch")
        for field in ("wall_ns", "wall_ns_per_launch", "device_envelope_ns", "device_envelope_ns_per_launch"):
            value = row.get(field)
            require(type(value) in (int, float) and math.isfinite(value) and value >= 0, "invalid timing: " + field)
        require(math.isclose(row["wall_ns_per_launch"]*launches, row["wall_ns"], rel_tol=1e-4), "wall denominator mismatch")
        require(math.isclose(row["device_envelope_ns_per_launch"]*launches, row["device_envelope_ns"], rel_tol=1e-4), "device denominator mismatch")
        span = row.get("profiled_span_ns")
        require(span is None or (type(span) in (int, float) and math.isfinite(span) and span >= 0), "invalid profiled span")
        require(row.get("output_verified") is True, "unverified or inert replay output")
    return rows

def summarize_rows(rows):
    summary=[]
    for method in METHODS:
        for workload in WORKLOADS:
            for n in (100,1000,4000):
                selected=[r for r in rows if (r["method"],r["workload"],r["n"])==(method,workload,n)]
                require(len(selected)==5, "five repeats required")
                profile=[r["profiled_span_ns"] for r in selected if r.get("profiled_span_ns") is not None]
                summary.append(dict(method=method,workload=workload,n=n,samples=5,
                    median_wall_ns=statistics.median(r["wall_ns"] for r in selected),
                    median_wall_ns_per_logical_operation=statistics.median(r["wall_ns"]/n for r in selected),
                    median_wall_ns_per_physical_launch=statistics.median(r["wall_ns_per_launch"] for r in selected),
                    median_device_envelope_ns=statistics.median(r["device_envelope_ns"] for r in selected),
                    median_profiled_span_ns=statistics.median(profile) if len(profile)==5 else None))
    return dict(scope="single-owner surrogate issuing comparison; no model speed verdict",fresh_owners=1,rows=summary)

def execute(card, output):
    out, binary, manifest, loader = check(card, output)
    pre, cursor = journal()
    out.mkdir(parents=True)
    (out / "preflight-kernel.txt").write_text(pre)
    record = dict(schema="own-runtime.packet20.window.v1", card=card, passed=False, device_executed=False,
                  prepared_sha256=sha(BUILD / "prepared.json"), ldd=loader, external_idle_health_still_required=True)
    requested = []
    def persist():
        record["stop_reason"] = requested[0] if requested else None
        save(out / "window.json", record)
    previous = {sig:signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig in previous:
        signal.signal(sig, lambda s, f: requested.append("watcher signal " + str(s)))
    # Admission latch is created only after ldd and journal preflights; never auto-cleared on failure.
    fd = os.open(LATCH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(dict(reason="window in progress", output=str(out)), f)
    try:
        require(not requested, "stop before launch")
        with (out / "stdout.txt").open("w") as log, (out / "kernel-window.txt").open("w") as kernel:
            cmd = PREFIX + [str(binary), "--authorized-device-window", "--card", str(card), "--output", str(out), "--seconds", "50"]
            record["command"] = cmd
            child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
            record.update(pid=child.pid, device_executed=True)
            persist()
            record.update(supervise(child, kernel, cursor, requested, persist))
        require(record["returncode"] == 0 and not requested, "native child failed/stopped")
        raw = json.loads((out / "device.json").read_text())
        require(raw.get("device_executed") is True and raw.get("passed") is True and raw.get("safe_to_exit") is True and raw.get("live_bytes") == 0 and raw.get("in_flight") == 0, "native coverage/teardown failed")
        for rel, digest in manifest["hashes"].items():
            require(sha(HERE / rel) == digest, "identity changed during run: " + rel)
        rows = validate_rows(out / "rows.jsonl")
        require(raw.get("rows") == raw.get("expected_rows") == len(rows) == 270, "native coverage mismatch")
        save(out / "summary.json", summarize_rows(rows))
        record["native_sha256"] = sha(out / "device.json")
        record["rows_sha256"] = sha(out / "rows.jsonl")
        record["passed"] = True
        LATCH.unlink()  # Clean completion only; fault or interrupted admission stays latched.
    except Exception as error:
        record["error"] = str(error)
        save(LATCH, dict(reason=str(error), output=str(out), pid=record.get("pid")))
    finally:
        persist()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return record

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true")
    p.add_argument("--authorized-device-window", action="store_true")
    p.add_argument("--card", required=True, type=int)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    if a.check:
        check(a.card, a.output)
        print("CPU identity and ldd passed; no device queried or binary executed.")
        return 0
    require(a.authorized_device_window, "separately authorized device window required; host halt remains binding")
    return 0 if execute(a.card, a.output)["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
