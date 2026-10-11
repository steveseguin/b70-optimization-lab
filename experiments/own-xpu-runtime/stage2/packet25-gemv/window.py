#!/usr/bin/env python3
"""Prepared packet25 device windows. Only a coordinator runs this program."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import uuid
from window_safety import environment_gate, confined

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FAULT = re.compile(r"Fault response|CAT (?:error|ERROR)|(?:GPU |GT[0-9]+ )?engine reset|(?:dev)?coredump", re.I)
JIT_SECONDS = 17.
EXPECTED_WORK = {"K0": 30., "G1": 200.}
OWNERS = {"K0": 1, "G1": 2}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def save(path, row):
    Path(path).write_text(json.dumps(row, indent=2, sort_keys=True, allow_nan=False)+"\n")

def deadlines(window, seconds=None):
    estimate = EXPECTED_WORK[window] + OWNERS[window]*JIT_SECONDS
    minimum = max(300, math.ceil(4*estimate))
    seconds = max(900 if window == "G1" else 300, minimum) if seconds is None else seconds
    require(type(seconds) is int and minimum <= seconds <= 7200, "watchdog outside admitted range")
    return dict(expected_work_seconds=EXPECTED_WORK[window], first_jit_seconds_per_owner=JIT_SECONDS,
                owners=OWNERS[window], expected_total_seconds=estimate,
                expectation_enforced=False, watchdog_seconds=seconds, minimum_watchdog_seconds=minimum,
                submission_budget_seconds={"logits": .010, "other": .002})

def ldd_preflight(binary, runner=subprocess.run):
    r = runner(["ldd", str(binary)], capture_output=True, text=True, timeout=10)
    require(r.returncode == 0 and "not found" not in r.stdout+r.stderr, "ldd dependency preflight failed: "+r.stdout+r.stderr)
    return dict(argv=["ldd", str(binary)], returncode=r.returncode, stdout=r.stdout, stderr=r.stderr)

def sealed_build(root=HERE):
    path = root/"build-receipt.json"
    build = read(path)
    require(build.get("passed") is True and build.get("device_executed") is False, "build must pass CPU-only preparation")
    artifacts = build.get("artifacts_sha256", {})
    require("build/device-gemv" in artifacts, "missing device binary binding")
    bindings = {path: sha(path)}
    for section in ("artifacts_sha256", "sources_sha256"):
        require(type(build.get(section)) is dict and bool(build[section]), "missing build section "+section)
        for name, digest in build[section].items():
            p = confined(root/name, root)
            require(p.is_file() and sha(p) == digest, "build binding changed: "+name)
            bindings[p] = digest
    for name, digest in build.get("external_sources_sha256", {}).items():
        p = confined(ROOT/name, ROOT)
        require(p.is_file() and sha(p) == digest, "external source binding changed: "+name)
        bindings[p] = digest
    cpu = root/"cpu-tests.json"
    require(sha(cpu) == build.get("cpu_receipt_sha256"), "CPU receipt changed")
    r = read(cpu)
    require(r.get("passed") is True and r.get("device_executed") is False, "CPU gates incomplete")
    bindings[cpu] = sha(cpu)
    return root/"build/device-gemv", bindings

def unchanged(bindings):
    for path, digest in bindings.items():
        require(sha(path) == digest, "sealed input changed: "+str(path))

def native_gate(path, mode, allow_completed_failure=False):
    r = read(path/"receipt.json")
    require((r.get("passed") is True or (allow_completed_failure and mode == "G1" and
            r.get("completed") is True and r.get("finite_element_gate_failures", 0) > 0)) and
            r.get("safe_to_exit") is True, "native failure/unsafe teardown")
    require(r.get("device_executed") is True, "native device receipt required")
    require(r.get("live_bytes") == 0 and r.get("in_flight") == 0, "native ownership accounting incomplete")
    require(r.get("mode") == mode, "native mode differs from admitted window")
    for row in r.get("teardown", []):
        require(row.get("safe_to_exit") is True and row.get("in_flight") == 0 and row.get("live_bytes") == 0,
                "native ownership remains live")
    if mode == "G1":
        require((path/"exactness.jsonl").is_file() and (path/"timing.jsonl").is_file(), "missing exactness/timing evidence")
    return r

def k0_gate(path, identity):
    require(path is not None, "G1 requires --k0 passing K0 window receipt")
    prior = read(path)
    require(prior.get("window") == "K0" and prior.get("passed") is True, "K0 not passed")
    for key in ("boot_id", "card", "binary_sha256", "environment", "build_receipt_sha256"):
        require(prior.get(key) == identity.get(key), "K0 identity mismatch: "+key)
    owners = prior.get("owners", [])
    require(len(owners) == 1, "K0 owner coverage")
    native = Path(path).parent/"run/owner1"
    require(sha(native/"receipt.json") == owners[0].get("native_receipt_sha256"), "K0 native receipt changed")
    native_gate(native, "K0")
    return prior

def journal(cursor=None):
    command = ["journalctl", "-k", "-b", "--no-pager", "--show-cursor", "-o", "short-monotonic"]
    command += ["--after-cursor", cursor] if cursor else ["-n", "0"]
    r = subprocess.run(command, capture_output=True, text=True, timeout=2)
    require(r.returncode == 0, "kernel journal unavailable: "+r.stderr)
    match = re.search(r"^-- cursor: (.+)$", r.stdout, re.M)
    require(match is not None, "kernel journal cursor missing")
    return r.stdout[:match.start()], match.group(1)

class NativeChild:
    """One user unit, restart disabled. Signals target native owner only."""
    def __init__(self, command, *, stdout, environment):
        self.unit = "packet25-gemv-"+uuid.uuid4().hex
        self.process = subprocess.Popen([
            "systemd-run", "--user", "--quiet", "--wait", "--pipe", "--collect",
            "--unit="+self.unit, "--property=Nice=19", "--property=IOSchedulingClass=idle",
            "--property=Restart=no", "/usr/bin/env", "-i",
            *[k+"="+v for k,v in environment["native"].items()], *command],
            stdout=stdout, stderr=subprocess.STDOUT)
    @property
    def pid(self):
        return self.process.pid
    @property
    def returncode(self):
        return self.process.returncode
    def poll(self):
        return self.process.poll()
    def send_signal(self, sig):
        subprocess.run(["systemctl", "--user", "kill", "--kill-whom=main", "--signal="+str(int(sig)), self.unit],
                       check=True, timeout=5)

def supervise(child, seconds, cursor, kernel, failure, reasons, *, journal_fn=journal,
              now=time.monotonic, sleep=time.sleep, drain_seconds=60):
    start, sent = now(), None
    while True:
        try:
            fresh, cursor = journal_fn(cursor)
            kernel.write(fresh); kernel.flush()
            if FAULT.search(fresh):
                reasons.append("new GPU fault signature")
        except Exception as error:
            reasons.append("kernel journal failed: "+str(error))
        if now()-start >= seconds:
            reasons.append("window watchdog expired")
        if reasons and sent is None:
            failure(reasons[0])  # Persist failure BEFORE requesting any drain.
            sent = now()
            if child.poll() is None:
                child.send_signal(signal.SIGTERM)
        if child.poll() is not None:
            break
        if sent is not None and now()-sent >= drain_seconds:
            reasons.append("cooperative drain deadline; child retained for coordinator")
            failure(reasons[-1])
            return dict(returncode=None, child_still_running=True, sigterm_sent=True, elapsed_seconds=now()-start, journal_cursor=cursor)
        sleep(.25)
    end = now()+5
    while now() < end:
        sleep(min(.25, end-now()))
        try:
            fresh, cursor = journal_fn(cursor)
            kernel.write(fresh); kernel.flush()
            if FAULT.search(fresh):
                reasons.append("postflight GPU fault signature")
        except Exception as error:
            reasons.append("postflight journal failed: "+str(error))
    if reasons:
        failure(reasons[0])
    return dict(returncode=child.returncode, child_still_running=False, sigterm_sent=sent is not None, elapsed_seconds=now()-start, journal_cursor=cursor)

def distinct_owners(owners, count):
    require(len(owners) == count and len({r.get("unit") for r in owners}) == count and
            all(r.get("unit") for r in owners), "fresh owners must be distinct units")
    require(all(type(r.get("pid")) is int and r["pid"] > 0 for r in owners) and
            len({r["pid"] for r in owners}) == count, "owner process receipt missing or duplicated")

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--authorized-device-window", action="store_true", required=True)
    p.add_argument("--window", choices=OWNERS, required=True)
    p.add_argument("--card", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--k0", type=Path)
    p.add_argument("--seconds", type=int)
    a = p.parse_args(argv)
    require(a.card >= 0, "nonnegative card index required")
    environment = environment_gate()
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, "nice19 required")
    require("idle" in subprocess.check_output(["ionice", "-p", str(os.getpid())], text=True, timeout=2), "ionice3 required")
    limits = deadlines(a.window, a.seconds)
    out = confined(a.output, HERE)
    require(not out.exists(), "output directory already exists; no retries")
    binary, bindings = sealed_build()
    loader = ldd_preflight(binary)  # Deliberately before latch inspection/creation.
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    identity = dict(boot_id=boot, card=a.card, binary_sha256=sha(binary), environment=environment,
                    build_receipt_sha256=sha(HERE/"build-receipt.json"))
    if a.window == "G1":
        k0_gate(a.k0, identity)
        bindings[a.k0.resolve()] = sha(a.k0)
    latch = HERE/"build/device-fault-latch.json"
    require(not latch.exists(), "fault latch present; coordinator must assess recovery")
    pre, cursor = journal()
    out.mkdir(parents=True)
    (out/"preflight-kernel.txt").write_text(pre)
    record = dict(schema="packet25.window.v1", **identity, window=a.window, passed=False,
                  device_executed=False, owners=[], deadlines=limits, ldd_preflight=loader,
                  k0=str(a.k0.resolve()) if a.k0 else None,
                  bindings={str(k):v for k,v in bindings.items()})
    reasons = []
    def persist():
        save(out/"window.json", record)
    def failure(reason):
        record.update(passed=False, stop_reason=reason)
        persist()
        save(latch, dict(boot_id=boot, window=str(out), reason=reason,
                        units=[r.get("unit") for r in record["owners"]]))
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda s,f: reasons.append("watcher signal "+str(s)))
    persist()
    started = time.monotonic()
    try:
        for index in range(OWNERS[a.window]):
            unchanged(bindings)
            remaining = limits["watchdog_seconds"]-(time.monotonic()-started)
            require(not reasons and remaining > 0, "window stopped before next owner")
            native = out/"run"/("owner"+str(index+1))
            command = [str(binary), "--mode", a.window, "--card", str(a.card), "--output", str(native)]
            with (out/("owner%d.log"%(index+1))).open("w") as log, (out/("owner%d-kernel.log"%(index+1))).open("w") as kernel:
                child = NativeChild(command, stdout=log, environment=environment)
                owner = dict(unit=child.unit, pid=child.pid, command=command, passed=False)
                record["owners"].append(owner); record["device_executed"] = True; persist()
                owner.update(supervise(child, remaining, cursor, kernel, failure, reasons))
                require(owner["returncode"] in ((0, 2) if a.window == "G1" else (0,)) and not reasons, "native owner failed/stopped")
            unchanged(bindings)
            native_receipt = native_gate(native, a.window, allow_completed_failure=True)
            require(owner["returncode"] == (2 if native_receipt.get("finite_element_gate_failures", 0) else 0), "native exit/receipt mismatch")
            owner.update(passed=native_receipt["passed"], completed=True, finite_element_gate_failures=native_receipt.get("finite_element_gate_failures", 0), native_receipt_sha256=sha(native/"receipt.json"))
            if a.window == "G1":
                owner["exactness_sha256"] = sha(native/"exactness.jsonl")
                owner["gate_summary"] = read(native/"gate-summary.json")
                owner["timing_sha256"] = sha(native/"timing.jsonl")
                owner["sequence_wall_sha256"] = sha(native/"sequence-wall.jsonl")
                if not owner["gate_summary"]["full_sequence_skipped"]:
                    owner["full_sequence_wall_sha256"] = sha(native/"full-sequence-wall.jsonl")
                    owner["full_sequence_plan_sha256"] = sha(native/"full-sequence-plan.jsonl")
            persist()
            cursor = owner["journal_cursor"]
        distinct_owners(record["owners"], OWNERS[a.window])
        if a.window == "G1":
            require(len({r["exactness_sha256"] for r in record["owners"]}) == 1,
                    "fresh owners disagree on fixture exactness/exclusions")
        record["completed"] = True
        record["passed"] = all(r["passed"] for r in record["owners"])
        record["finite_element_gate_failures"] = sum(r["finite_element_gate_failures"] for r in record["owners"])
        record["fresh_owners"] = OWNERS[a.window]
    except Exception as error:
        failure(str(error))
    persist()
    if record.get("completed") and a.window == "G1":
        try:
            from summary import write_summary
            write_summary(out)
        except Exception as error:
            failure("timing summary failed: "+str(error))
    return 0 if record["passed"] else 1

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print("packet25 admission failed: "+str(error), flush=True)
        raise SystemExit(1)
