#!/usr/bin/env python3
"""Guarded packet165 lab replay; does not adapt or bypass its sealed admission."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
PACKET = ROOT / "experiments/own-xpu-runtime/stage2/packet165-warm-prefill"


def check_files(packet):
    seal = json.loads((packet / "seal.json").read_text())
    for relative, expected in seal["files"].items():
        path = (packet / relative).resolve()
        if not path.is_relative_to(packet):
            raise ValueError("seal path escapes packet")
        with path.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != expected:
            raise ValueError(f"sealed source mismatch: {relative}")
    ready = json.loads((packet / "READY-FOR-DEVICE.json").read_text())
    if ready.get("ready") is not True or ready["seal_sha256"] != hashlib.sha256((packet / "seal.json").read_bytes()).hexdigest():
        raise ValueError("packet readiness is stale")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("health", "preflight", "launch", "benchmark", "stop"))
    ap.add_argument("--cards", type=int, choices=(1, 2), required=True)
    ap.add_argument("--lane", choices=("A", "B"), default="A")
    ap.add_argument("--name", help="unique new output name under packet evidence/")
    ap.add_argument("--unit", help="screen-ownrt-replay-... systemd user unit")
    ap.add_argument("--fault-review", type=Path)
    ap.add_argument("--reference", type=Path, help="completed first fresh replay in the same packet")
    ap.add_argument("--authorized-device-window", action="store_true")
    args = ap.parse_args()
    packet = PACKET / ("one-card" if args.cards == 1 else "two-card")
    if args.cards == 1 and args.lane != "A":
        ap.error("the frozen one-card profile requires lane A")
    if args.mode == "stop":
        if not args.unit or not re.fullmatch(r"screen-ownrt-replay-[A-Za-z0-9_-]+", args.unit):
            ap.error("set the exact screen-ownrt-replay-... unit started by this helper")
        return subprocess.call(["systemctl", "--user", "kill", "--kill-who=main", "--signal=SIGTERM", args.unit + ".service"])
    check_files(packet)
    if args.mode == "health":
        subprocess.run([sys.executable, "-B", str(ROOT / "results/qwen38-flash-next-ud-iq3xxs-b70/extract-ownrt-measurements.py")], check=True)
        print("PASS: sealed packet files and retained measurements; CPU evidence check, not GPU health")
        return 0
    if not args.name or not re.fullmatch(r"[A-Za-z0-9_-]+", args.name):
        ap.error("set a unique --name; old outputs are never reused")
    output = packet / "evidence" / args.name
    if output.exists():
        ap.error("output already exists; preserve it and choose a new name")
    command = ["/usr/bin/python3", "-B", str(packet / "entry.py"), "--lane", args.lane,
               "--kind", "full512", "--output", str(output)]
    if args.reference:
        command += ["--reference", str(args.reference.resolve())]
    if args.mode == "preflight":
        return subprocess.call(["nice", "-n", "19", "taskset", "-c", "8-15,24-31", *command, "--plan"], cwd=ROOT)
    if not args.authorized_device_window or not args.fault_review:
        ap.error("device replay requires coordinator authorization and a genuine current-boot fault review")
    if not args.unit or not re.fullmatch(r"screen-ownrt-replay-[A-Za-z0-9_-]+", args.unit):
        ap.error("set a unique screen-ownrt-replay-... --unit")
    if os.getpriority(os.PRIO_PROCESS, 0) != 0:
        ap.error("timing requires a nice-0 coordinator; this helper never raises priority")
    budget = json.loads((packet / "budget.json").read_text())
    available = next(int(line.split()[1]) * 1024 for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemAvailable:"))
    if available < budget["host_required_available_bytes"]:
        ap.error("insufficient host memory for the sealed profile")
    if shutil.disk_usage(packet).free - budget["planned_write_bytes"] < budget["device_floor_bytes"]:
        ap.error("packet filesystem must retain the unchanged 25 GB device floor after planned writes")
    command += ["--fault-review", str(args.fault_review.resolve()), "--authorized-device-window"]
    cores = "0 1 2 3 16 17 18 19" if args.lane == "A" else "4 5 6 7 20 21 22 23"
    return subprocess.call([
        "systemd-run", "--user", "--collect", "--wait", "--unit=" + args.unit,
        "--property=WorkingDirectory=" + str(ROOT), "--property=Restart=no",
        "--property=KillMode=process", "--property=ExitType=cgroup",
        "--property=SendSIGKILL=no", "--property=TimeoutStopSec=infinity",
        "--property=CPUAffinity=" + cores, *command,
    ], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
