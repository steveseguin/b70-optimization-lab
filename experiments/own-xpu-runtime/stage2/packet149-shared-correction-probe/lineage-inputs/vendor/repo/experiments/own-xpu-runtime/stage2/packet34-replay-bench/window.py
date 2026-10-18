#!/usr/bin/env python3
"""CPU-only admission; R1 may launch the explicitly authorized coordinator binary."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
SCHEMA = "own-runtime.packet34.window.v1"
FAULT = re.compile(r"Fault response|CAT error|(?:GPU |engine )reset|(?:device |GPU |xe.*)coredump|job.*timed out", re.I)
EXPECTED_SECONDS = 300.0
DRAIN_SECONDS = 60.0
ANONYMOUS_LIMIT_BYTES = 8 * 1024**3
ANONYMOUS_STOP_BYTES = ANONYMOUS_LIMIT_BYTES - 512 * 1024**2
NATIVE_KEYS = {"LD_LIBRARY_PATH", "OMP_NUM_THREADS", "PATH"}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, row):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        json.dump(row, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)



GATE_RECEIPTS = frozenset({"cpu-tests.json", "capture-gates.json", "lifetime-tests.json",
                           "window-tests.json", "raw-abi-gate.json"})
HOST_MODES = frozenset({"host", "icpx-host", "asan"})


def sealed_build_gate(build, native_binaries, root=HERE, repo=None):
    """Verify complete sealed CPU evidence before ldd or any native launch."""
    root = Path(root).resolve()
    repo = HERE.parents[3] if repo is None else Path(repo).resolve()
    require(build.get("passed") is True, "build is incomplete or unsealed")
    require(build.get("device_executed") is False, "preparation receipt must be CPU-only")
    recorded = build.get("binaries", {})
    native_names = {"device/jit-smoke", "device/replay-bench"}
    require(set(native_binaries) == native_names, "native binary identity incomplete")
    require(all(recorded.get(name) == digest for name, digest in native_binaries.items()),
            "native binaries differ from sealed build")
    hashes = build.get("gate_receipts", {})
    require(set(hashes) == GATE_RECEIPTS, "complete exact gate receipt set required")
    gates = {}
    for name in sorted(GATE_RECEIPTS):
        path = root / name
        require(sha(path) == hashes[name], "gate receipt changed: " + name)
        row = json.loads(path.read_text())
        require(row.get("passed") is True, "gate failed: " + name)
        require(row.get("device_executed") is False, "gate was not CPU-only: " + name)
        gates[name] = row
    capture = gates["capture-gates.json"]
    require(capture.get("binary_sha256") == native_binaries and
            capture.get("k0_r1_device_images_identical") is True and
            capture.get("negative_1025_rejected") is True and
            0 < capture.get("maximum_capture_bytes", 0) <= 1024,
            "capture gate is incomplete or belongs to other binaries")
    raw = gates["raw-abi-gate.json"]
    require(raw.get("raw_available") is False and raw.get("qualified") is False,
            "raw capability gate must remain unqualified/unavailable")
    expected_rows = {(mode, fresh) for mode in HOST_MODES for fresh in range(2)}
    rows = gates["cpu-tests.json"].get("rows", [])
    require(len(rows) == len(expected_rows) and
            {(row.get("compiler"), row.get("fresh_process")) for row in rows} == expected_rows,
            "both fresh processes of every host configuration required")
    host_hashes = {}
    for mode in sorted(HOST_MODES):
        name = mode + "/replay-bench"
        actual = sha(root / "build" / name)
        require(recorded.get(name) == actual, "host binary changed: " + name)
        host_hashes[mode] = actual
    for row in rows:
        require(row.get("passed") is True and row.get("device_executed") is False and
                row.get("safe_to_exit") is True and
                row.get("binary_sha256") == host_hashes[row["compiler"]],
                "CPU row failed or belongs to another binary")
    def source_hashes(files, label):
        require(isinstance(files, dict) and bool(files), label + " source closure missing")
        for name, digest in files.items():
            relative = Path(name)
            path = (repo / relative).resolve()
            require(not relative.is_absolute() and path.is_relative_to(repo),
                    label + " source path outside repository")
            require(sha(path) == digest, label + " source changed: " + name)
    source_hashes(build.get("source_files"), "packet34")
    proof_path = root / "source-proof.json"
    require(sha(proof_path) == build.get("upstream_source_proof_sha256"),
            "upstream source proof changed")
    source_hashes(json.loads(proof_path.read_text()).get("unchanged_packet29_inputs"), "upstream")
    return {"sealed_gates_verified": True, "gate_receipts": hashes,
            "source_closure_verified": True, "host_binaries_verified": host_hashes}


def environment_gate(source=None):
    source = dict(os.environ if source is None else source)
    # Python may add LC_CTYPE during C-locale coercion under env -i; it is not forwarded.
    require(set(source) <= {"LD_LIBRARY_PATH", "LC_CTYPE"}, "closed environment required; use env -i and supply only LD_LIBRARY_PATH")
    require("LC_CTYPE" not in source or source["LC_CTYPE"] == "C.UTF-8",
            "only Python C.UTF-8 locale coercion is admitted")
    require(bool(source.get("LD_LIBRARY_PATH")), "LD_LIBRARY_PATH must be supplied")
    return {"LD_LIBRARY_PATH": source["LD_LIBRARY_PATH"], "OMP_NUM_THREADS": "2", "PATH": "/usr/bin:/bin"}


def helper(argv):
    return ["/usr/bin/nice", "-n", "19", "/usr/bin/ionice", "-c", "3", *map(str, argv)]


def watchdog(seconds):
    minimum = max(300, math.ceil(EXPECTED_SECONDS * 4))
    value = 1200 if seconds is None else seconds
    require(math.isfinite(value) and value >= minimum, "watchdog must be at least " + str(minimum) + " seconds")
    return value


def journal(cursor=None, runner=subprocess.run, *, since_us=None):
    argv = ["/usr/bin/journalctl", "-k", "-b", "--no-pager", "--show-cursor", "--output=json"]
    if since_us is not None:
        # journalctl's bare calendar times are LOCAL. Epoch syntax is timezone independent.
        # --since is inclusive; journal timestamps have microsecond resolution.
        after_us = since_us + 1
        argv += ["--since", f"@{after_us // 1000000}.{after_us % 1000000:06d}"]
    elif cursor:
        argv += ["--after-cursor", cursor]
    row = runner(helper(argv), capture_output=True, text=True, timeout=2,
                 env={"PATH": "/usr/bin:/bin", "OMP_NUM_THREADS": "2"})
    require(row.returncode == 0 and not row.stderr.strip(), "kernel journal unavailable: " + row.stderr)
    lines = row.stdout.splitlines()
    cursors = [line[11:] for line in lines if line.startswith("-- cursor: ")]
    require(bool(cursors or cursor), "kernel journal boundary missing")
    return "\n".join(line for line in lines if not line.startswith("-- cursor: ")) + "\n", cursors[-1] if cursors else cursor



def fault_review(value, started_us):
    if value is None:
        return None, None
    require("T" in value, "fault review must be a UTC ISO time")
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(instant.tzinfo is not None and instant.utcoffset() == timedelta(0),
            "fault review must include UTC Z or +00:00")
    micros = (instant - datetime(1970, 1, 1, tzinfo=timezone.utc)) // timedelta(microseconds=1)
    require(0 <= micros <= started_us, "fault review cannot be in the future")
    return instant.isoformat().replace("+00:00", "Z"), micros


def journal_entries(text):
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows.append((int(row["__REALTIME_TIMESTAMP"]), line))
    return rows


def packet_started_on_boot(boot, root=HERE):
    # Include archived receipts. A durable pre-Popen command is conservative evidence
    # of a launch attempt, even if the wrapper died before recording the child PID.
    for path in root.rglob("window.json"):
        row = json.loads(path.read_text())
        if row.get("boot_id") == boot and (row.get("device_executed") or
                                          row.get("pid") or row.get("command")):
            return True
    return False


def initial_fault_gate(initial, started_us, reviewed, boot, latch, root=HERE):
    if not FAULT.search(initial):
        return
    if not reviewed:
        rows = journal_entries(initial)
        faults = [stamp for stamp, line in rows if FAULT.search(line)]
        if (faults and all(stamp < started_us - 3600 * 1000000 for stamp in faults)
                and not packet_started_on_boot(boot, root)):
            raise ValueError("old fault lines in this boot: coordinator review argument required")
    reason = "recent kernel fault requires coordinator review"
    latch(reason)
    raise ValueError(reason)


def review_identity_gate(previous, current):
    def through(row):
        return (row.get("coordinator_fault_review") or {}).get("through")
    require(through(previous) == through(current), "K0 identity changed: fault review instant")


def ldd_preflight(binary, environment, runner=subprocess.run):
    row = runner(helper(["/usr/bin/ldd", binary]), env=environment,
                 capture_output=True, text=True, timeout=10)
    require(row.returncode == 0 and "not found" not in row.stdout + row.stderr, "ldd preflight failed")
    return {"returncode": row.returncode, "stdout": row.stdout, "stderr": row.stderr}


def process_tree_anon(pid, proc=Path("/proc")):
    """Sum RssAnon once per process, including descendants of helper threads."""
    pending, seen, rows = [pid], set(), []
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        base = proc / str(current)
        try:
            status = base.joinpath("status").read_text()
            values = [line.split() for line in status.splitlines() if line.startswith("RssAnon:")]
            require(len(values) == 1 and len(values[0]) == 3 and values[0][2] == "kB",
                    "missing/malformed RssAnon for pid " + str(current))
            amount = int(values[0][1]) * 1024
            require(amount >= 0, "negative RssAnon")
            rows.append({"pid": current, "rss_anon_bytes": amount})
            for task in base.joinpath("task").iterdir():
                try:
                    pending.extend(int(child) for child in task.joinpath("children").read_text().split())
                except FileNotFoundError:
                    pass  # A thread exited between the two proc reads.
        except FileNotFoundError:
            pass  # A child may exit between discovery and inspection.
    return {"anonymous_bytes": sum(row["rss_anon_bytes"] for row in rows),
            "root_seen": any(row["pid"] == pid for row in rows),
            "processes": sorted(rows, key=lambda row: row["pid"])}


def finalize_r1(run, summarize_fn=None):
    if summarize_fn is None:
        from summarize import summarize as summarize_fn
    row = summarize_fn(run)
    require(row.get("passed") is True and row.get("device_executed") is True,
            "R1 summary is incomplete or not a native measurement")
    return {"summary_sha256": sha(run / "summary.json"),
            "summary_passed": True, "replay_pays": row.get("replay_pays")}


def supervise(child, seconds, cursor, kernel, reasons, latch, persist,
              read_journal=journal, now=time.monotonic, sleep=time.sleep,
              drain_seconds=DRAIN_SECONDS, postflight_seconds=5, cooperative_stop=True,
              memory_sensor=process_tree_anon, observe_memory=lambda row: None):
    start = now()
    sent = None
    peak_memory = 0
    memory_status = {"anonymous_peak_bytes": 0, "anonymous_limit_bytes": ANONYMOUS_LIMIT_BYTES,
                     "anonymous_stop_bytes": ANONYMOUS_STOP_BYTES}
    while True:
        if child.poll() is None:
            try:
                sample = memory_sensor(child.pid)
                if not sample["root_seen"] and child.poll() is None:
                    raise ValueError("native process missing from memory sensor")
                peak_memory = max(peak_memory, sample["anonymous_bytes"])
                memory_status.update(anonymous_peak_bytes=peak_memory, memory_last_sample=sample)
                observe_memory(memory_status)
                if sample["anonymous_bytes"] >= ANONYMOUS_STOP_BYTES:
                    reasons.append("native process tree anonymous memory reached stop threshold below 8 GiB")
            except Exception as error:
                reasons.append("anonymous-memory sensor unavailable: " + str(error))
        try:
            fresh, cursor = read_journal(cursor)
            kernel.write(fresh)
            kernel.flush()
            if FAULT.search(fresh):
                reasons.append("new GPU fault signature")
        except Exception as error:
            reasons.append("kernel journal unavailable: " + str(error))
        if now() - start >= seconds and not reasons:
            reasons.append("watchdog expired")
        if reasons and sent is None:
            latch(reasons[0])
            persist()  # Failure exists durably before any stop/teardown request.
            if cooperative_stop and child.poll() is None:
                child.send_signal(signal.SIGTERM)
            sent = now()
        if child.poll() is not None:
            break
        if sent is not None and now() - sent >= drain_seconds:
            reasons.append("drain budget expired; busy child retained for coordinator")
            latch(reasons[-1])
            persist()
            return {"returncode": None, "child_still_running": True, "sigterm_sent": cooperative_stop,
                    "elapsed_seconds": now() - start, **memory_status}
        sleep(.25)
    end = now() + postflight_seconds
    while now() < end:
        sleep(min(.25, end - now()))
        try:
            fresh, cursor = read_journal(cursor)
            kernel.write(fresh)
            kernel.flush()
            if FAULT.search(fresh):
                reasons.append("postflight GPU fault signature")
        except Exception as error:
            reasons.append("postflight kernel journal unavailable: " + str(error))
    if reasons:
        latch(reasons[0])
    return {"returncode": child.returncode, "child_still_running": False,
            "sigterm_sent": cooperative_stop and sent is not None, "elapsed_seconds": now() - start, **memory_status}


def native_gate(row):
    teardown = row.get("teardown", {})
    safe = row.get("safe_to_exit") is True or isinstance(teardown, dict) and teardown.get("safe_to_exit") is True
    require(row.get("passed") is True and safe, "native receipt failed or teardown not safe")


def under_packet(path):
    path = Path(path).resolve()
    require(path.is_relative_to(HERE), "outputs must remain under packet34")
    return path


def main(argv=None):
    started_us = time.time_ns() // 1000
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", choices=["K0", "R1"], required=True)
    parser.add_argument("--card", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--k0", type=Path)
    parser.add_argument("--faults-reviewed-through", help="coordinator-reviewed UTC ISO time (Z or +00:00)")
    parser.add_argument("--seconds", type=float)
    parser.add_argument("--authorized-device-window", action="store_true")
    args = parser.parse_args(argv)
    require(args.card >= 0, "card must be nonnegative")
    require(args.authorized_device_window, "window needs explicit coordinator authorization")
    reviewed_through, reviewed_us = fault_review(args.faults_reviewed_through, started_us)
    environment = environment_gate()
    out = under_packet(args.output)
    require(not out.exists(), "output must be new")
    out.mkdir(parents=True)
    binary = HERE / "build/device" / ("jit-smoke" if args.window == "K0" else "replay-bench")
    build_receipt = HERE / "build-receipt.json"
    record = dict(schema=SCHEMA, window=args.window, card=args.card, passed=False,
                  device_executed=False, environment=environment, started_epoch_us=started_us,
                  affinity=sorted(os.sched_getaffinity(0)), native_nice=os.getpriority(os.PRIO_PROCESS, 0))
    if reviewed_through is not None:
        record["coordinator_fault_review"] = {"through": reviewed_through,
                                              "lines_before": None, "fault_lines_before": None}
    reasons = []
    child = None
    def persist():
        record["stop_reasons"] = list(reasons)
        save(out / "window.json", record)
    persist()
    try:
        seconds = watchdog(args.seconds)
        build = json.loads(build_receipt.read_text())
        binaries = {name: sha(HERE / "build" / name) for name in ("device/jit-smoke", "device/replay-bench")}
        record.update(sealed_build_gate(build, binaries))
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        latch_path = HERE / "build" / ("fault-" + boot + ".json")
        require(not latch_path.exists(), "boot fault latch exists; coordinator recovery needed")
        def latch(reason):
            save(latch_path, dict(boot_id=boot, pid=record.get("pid"), reason=reason, output=str(out)))
        record.update(boot_id=boot, binaries=binaries, build_receipt_sha256=sha(build_receipt),
                      watchdog_seconds=seconds, expected_seconds=EXPECTED_SECONDS,
                      expectation_enforced=False, drain_seconds=DRAIN_SECONDS)
        if args.window == "R1":
            require(args.k0 is not None, "R1 requires K0 receipt")
            previous = json.loads(args.k0.read_text())
            require(previous.get("schema") == SCHEMA and previous.get("window") == "K0" and
                    previous.get("passed") is True and previous.get("kernel_execution") is False,
                    "K0 compile receipt incomplete")
            for key in ("boot_id", "card", "environment", "binaries", "build_receipt_sha256"):
                require(previous.get(key) == record.get(key), "K0 identity changed: " + key)
            review_identity_gate(previous, record)
            prior_native = args.k0.parent / "run/receipt.json"
            require(previous.get("native_receipt_sha256") == sha(prior_native), "K0 native receipt changed")
            record["k0_sha256"] = sha(args.k0)
        record["ldd"] = ldd_preflight(binary, environment)
        initial, cursor = journal()
        if reviewed_us is not None:
            (out / "kernel-boot-before-review.txt").write_text(initial)
            before = [line for stamp, line in journal_entries(initial) if stamp <= reviewed_us]
            record["coordinator_fault_review"].update(
                lines_before=len(before), fault_lines_before=sum(bool(FAULT.search(line)) for line in before))
            # Preserve the first cursor if the reviewed interval has no entries.
            initial, cursor = journal(cursor, since_us=reviewed_us)
        (out / "kernel-before.txt").write_text(initial)
        initial_fault_gate(initial, started_us, reviewed_through is not None, boot, latch, root=HERE)
        requested = lambda signum, frame: reasons.append("watcher signal " + str(signum))
        previous_signals = {sig: signal.signal(sig, requested) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            command = [str(binary), "--card", str(args.card), "--output", str(out / "run"),
                       "--authorized-device-window"]
            if args.window == "K0":
                command += ["--cards", "1"]
            record["command"] = command
            persist()
            with (out / "native.txt").open("w") as log, (out / "kernel.txt").open("w") as kernel:
                child = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                         start_new_session=True)
                record.update(pid=child.pid, device_executed=True)
                persist()
                record.update(supervise(child, seconds, cursor, kernel, reasons, latch, persist,
                                        cooperative_stop=args.window == "R1", observe_memory=record.update))
            if record["child_still_running"]:
                persist()
                return 75
            require(not reasons and child.returncode == 0, "native failure or interrupted window")
            native = out / "run/receipt.json"
            record["native_receipt_sha256"] = sha(native)
            native_row = json.loads(native.read_text())
            if args.window == "K0":
                require(native_row.get("passed") is True and native_row.get("kernel_execution") is False and
                        native_row.get("explicit_allocations") == 0 and native_row.get("cards") == 1 and
                        native_row.get("kernels_per_device", 0) > 0, "K0 kernel build receipt incomplete")
                record["kernel_execution"] = False
            else:
                native_gate(native_row)
                record.update(finalize_r1(out / "run"))
                record["kernel_execution"] = True
            record["passed"] = True
            persist()
            return 0
        finally:
            for sig, handler in previous_signals.items():
                signal.signal(sig, handler)
    except Exception as error:
        reasons.append(str(error))
        if child is not None and child.poll() is None:
            record.update(child_still_running=True, child_retained=True)
            reasons.append("supervision failure; live child retained for coordinator, no cleanup retry")
        persist()
        return 75 if record.get("child_still_running") else 1


if __name__ == "__main__":
    raise SystemExit(main())
