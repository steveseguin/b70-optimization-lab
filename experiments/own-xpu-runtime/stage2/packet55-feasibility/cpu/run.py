#!/usr/bin/env python3
"""CPU-only packet55 build, light exactness, or coordinator-owned quiet benchmark."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
ALLOWED = set(range(4, 16)) | set(range(20, 32))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def run(command, prefix, timeout=300):
    started = now()
    env = {key: val for key, val in os.environ.items()
           if not key.startswith(("OMP_", "GOMP_", "KMP_"))}
    result = subprocess.run(list(map(str, command)), cwd=HERE, env=env,
                            text=True, capture_output=True, timeout=timeout)
    prefix.with_suffix(".stdout").write_text(result.stdout)
    prefix.with_suffix(".stderr").write_text(result.stderr)
    write(prefix.with_suffix(".command.json"), dict(command=list(map(str, command)),
          started_utc=started, finished_utc=now(), returncode=result.returncode))
    if result.returncode:
        raise RuntimeError(f"{prefix.name} failed: {result.stderr[-2000:]}")
    return result.stdout


def dependencies(depfile):
    text = depfile.read_text().replace("\\\n", " ").split(":", 1)[1]
    return {(HERE / name).resolve() for name in shlex.split(text)}


def verify_build():
    record = json.loads((BUILD / "identity.json").read_text())
    for relative, expected in record["sources"].items():
        if sha(HERE / relative) != expected:
            raise RuntimeError(f"CPU source changed: {relative}; rebuild required")
    for name, expected in record["binaries"].items():
        if sha(BUILD / name) != expected:
            raise RuntimeError(f"CPU binary changed: {name}")
    return record


@contextmanager
def quiet_lock():
    # The same lock is held by packet55 route/H2D windows. It cannot see other
    # packets: coordinator acknowledgment must also cover packet49d and all GPUs.
    with (HERE.parent / "window.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another packet55 CPU/GPU window holds window.lock") from exc
        yield


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("build", "test", "bench"))
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--coordinator-quiet-window", action="store_true")
    ap.add_argument("--seconds", type=float, default=1)
    ap.add_argument("--samples", type=int, default=3)
    args = ap.parse_args()
    if os.getpriority(os.PRIO_PROCESS, 0) < 19 or not os.sched_getaffinity(0) <= ALLOWED:
        ap.error("run with nice -n 19 taskset -c 4-15,20-31 python3 -B")
    if not (1 <= args.seconds <= 5 and 3 <= args.samples <= 7):
        ap.error("seconds 1..5 and samples 3..7 required")
    if args.action == "bench" and not args.coordinator_quiet_window:
        ap.error("benchmark requires coordinator acknowledgment that ALL GPU windows are stopped")
    if args.output.exists():
        ap.error("output must be a new directory")
    args.output = args.output.resolve()
    args.output.mkdir(parents=True)
    BUILD.mkdir(exist_ok=True)
    report = dict(schema="p55.cpu-receipt.v1", action=args.action, started_utc=now(),
                  host=platform.node(), device_executed=False, model_weights_read=False,
                  pinned_host_bytes=0, expected_peak_rss_bytes=268435456,
                  affinity=sorted(os.sched_getaffinity(0)), nice=os.getpriority(os.PRIO_PROCESS, 0))
    if args.action == "build":
        flags = ["g++", "-std=c++20", "-O3", "-mavx2", "-mfma", "-fno-fast-math",
                 "-ffp-contract=off", "-frounding-math", "-fopenmp", "-Wall", "-Wextra",
                 "-Wno-unknown-pragmas", "-Wno-misleading-indentation"]
        closure = {Path(__file__).resolve()}
        for source in ("exactness", "benchmark"):
            run(flags + ["-MM", "-MF", BUILD / f"{source}.d", f"{source}.cpp"],
                args.output / f"deps-{source}")
            closure |= dependencies(BUILD / f"{source}.d")
        before = {os.path.relpath(p, HERE): sha(p) for p in sorted(closure)}
        for source in ("exactness", "benchmark"):
            run(flags + [f"{source}.cpp", "-o", BUILD / source], args.output / f"compile-{source}")
        after = {os.path.relpath(p, HERE): sha(p) for p in sorted(closure)}
        if before != after:
            raise RuntimeError("source closure changed during serial compilation")
        identity = dict(sources=after, binaries={n: sha(BUILD / n) for n in ("exactness", "benchmark")},
                        flags=flags, compiler=subprocess.check_output(["g++", "--version"], text=True).splitlines()[0])
        write(BUILD / "identity.json", identity)
        report["build"] = identity
    elif args.action == "test":
        report["build"] = verify_build()
        results = [json.loads(run([BUILD / "exactness"], args.output / f"exactness-{i}")) for i in range(2)]
        if results[0] != results[1] or not all(r["passed"] for r in results):
            raise RuntimeError("fresh process exactness differs")
        report.update(results=results, fresh_process_repeats_equal=True)
        write(BUILD / "exactness.json", report)
    else:
        with quiet_lock():
            report["build"] = verify_build()
            gate = json.loads((BUILD / "exactness.json").read_text())
            if gate["build"] != report["build"] or not gate["fresh_process_repeats_equal"]:
                raise RuntimeError("matching exactness gate required")
            report["exactness_sha256"] = sha(BUILD / "exactness.json")
            report["coordinator_acknowledged_all_gpu_windows_stopped"] = True
            report["results"] = []
            for repeat in range(2):
                for threads in (1, 4, 8, 12, 16):
                    row = json.loads(run([BUILD / "benchmark", threads, args.seconds, args.samples],
                         args.output / f"bench-r{repeat}-t{threads}", timeout=1200))
                    row["fresh_process_repeat"] = repeat
                    report["results"].append(row)
                    write(args.output / "progress.json", report)
            report["throughput_is_model_speed"] = False
    if verify_build() != report["build"]:
        raise RuntimeError("CPU identity changed during action")
    report.update(passed=True, finished_utc=now())
    write(args.output / "receipt.json", report)
    print(json.dumps(dict(passed=True, receipt=str(args.output / "receipt.json"))))


if __name__ == "__main__":
    main()
