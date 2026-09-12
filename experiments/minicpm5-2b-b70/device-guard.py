#!/usr/bin/env python3
"""Bounded isolated operator run with exclusive locks and health evidence."""

import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
FAULT = re.compile(r"Fault response|CAT error|engine reset|GPU HANG|GuC.*reset|coredump", re.I)


def journal(since):
    return subprocess.check_output(
        ["journalctl", "-k", "-b", "--since", since, "--no-pager"],
        text=True, timeout=10,
    )


def run(command, log, timeout, since):
    if FAULT.search(journal(since)):
        raise RuntimeError("device fault before subprocess launch")
    with log.open("w") as output:
        child = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        deadline = time.monotonic() + timeout
        try:
            while child.poll() is None:
                if time.monotonic() > deadline:
                    raise RuntimeError("subprocess timeout")
                if FAULT.search(journal(since)):
                    raise RuntimeError("new kernel device fault")
                time.sleep(2)
            if child.returncode:
                raise RuntimeError(f"subprocess exit {child.returncode}; see {log}")
            if FAULT.search(journal(since)):
                raise RuntimeError("new kernel device fault after subprocess exit")
        finally:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            if child.poll() is None:
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=10)
            # Terminate descendants even if their original parent exited early.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    for key in ("ZE_AFFINITY_MASK", "ONEAPI_DEVICE_SELECTOR", "SYCL_DEVICE_FILTER"):
        os.environ.pop(key, None)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("explicit test command required")
    args.out.mkdir(parents=True, exist_ok=False)
    locks = []
    for name in ["/run/lock/muse-glimmer-gpu-exclusive.lock", "/tmp/b70-benchmark.lock"] + [
        f"/tmp/b70-gpu{i}.lock" for i in range(4)
    ]:
        handle = open(name, "a")
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locks.append(handle)
    containers = subprocess.check_output(["docker", "ps", "-q"], text=True, timeout=10)
    if containers.strip():
        raise RuntimeError("a Docker workload is running")
    nodes = list(Path("/dev/dri").glob("renderD*"))
    if len(nodes) != 4:
        raise RuntimeError("expected four render nodes")
    owners = subprocess.run(["fuser", *map(str, nodes)], capture_output=True, text=True, timeout=10)
    if owners.returncode != 1 or owners.stdout.strip() or owners.stderr.strip():
        raise RuntimeError("render nodes held or ownership check failed")
    baseline = journal("10 minutes ago")
    (args.out / "journal-before.txt").write_text(baseline)
    if FAULT.search(baseline):
        raise RuntimeError("recent device fault requires assessment before testing")
    since = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    identity = {"start_utc": since, "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                "command": command, "timeout_s": args.timeout, "host": os.uname().nodename,
                "free_bytes": os.statvfs(args.out).f_bavail * os.statvfs(args.out).f_frsize}
    if identity["free_bytes"] < 5 * 1024**3:
        raise RuntimeError("less than 5GiB free")
    mem = Path("/proc/meminfo").read_text()
    available = int(re.search(r"MemAvailable:\s+(\d+)", mem).group(1)) * 1024
    identity["available_memory_bytes"] = available
    if available < 8 * 1024**3:
        raise RuntimeError("less than 8GiB available RAM")
    (args.out / "identity.json").write_text(json.dumps(identity, indent=2) + "\n")
    health = ["/home/steve/.venvs/minicpm5-baseline-20260912/bin/python",
              str(Path(__file__).with_name("device-health.py"))]
    results = {}
    try:
        run(health, args.out / "preflight.log", 100, since)
        results["preflight"] = "passed"
        run(command, args.out / "test.log", args.timeout, since)
        results["test"] = "passed"
    except Exception as error:
        results["error"] = str(error)
    finally:
        try:
            if results.get("preflight") != "passed":
                raise RuntimeError("preflight failed: passive postflight only")
            if FAULT.search(journal(since)):
                raise RuntimeError("device fault: active postflight skipped; passive evidence retained")
            owners = subprocess.run(["fuser", *map(str, nodes)], capture_output=True,
                                    text=True, timeout=10)
            if owners.returncode != 1 or owners.stdout.strip() or owners.stderr.strip():
                raise RuntimeError("render nodes still held: passive postflight only")
            run(health, args.out / "postflight.log", 100, since)
            results["postflight"] = "passed"
        except Exception as error:
            results["postflight"] = str(error)
        (args.out / "journal-after.txt").write_text(journal(since))
        (args.out / "result.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results), flush=True)
    return 0 if results == {"preflight": "passed", "test": "passed", "postflight": "passed"} else 1


if __name__ == "__main__":
    def terminate(signum, frame):
        raise RuntimeError(f"runner interrupted by signal {signum}")
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    raise SystemExit(main())
