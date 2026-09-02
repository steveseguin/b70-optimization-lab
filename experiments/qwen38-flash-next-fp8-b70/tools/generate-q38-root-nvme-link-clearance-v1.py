#!/usr/bin/env python3
"""Generate the fixed `q38_root_nvme_link_clearance_v1` receipt from live state.

This is the producer for the receipt that
`validate-q38-root-nvme-link-clearance-v1.py` consumes. It never invents a
value: every field is sampled from sysfs, `/proc`, `nvme smart-log`, and
`xpu-smi discovery`, and the assembled receipt is passed through the tracked
validator against the live boot and controller identity before it is written
to the fixed clearance path. A receipt that the validator rejects is written
beside that path with a `.rejected-<stamp>.json` suffix instead, so a failed
clearance leaves evidence but never a consumable receipt.

Phases:

1. admission: no render-node users, no runtime conflicts, clean SMART;
2. idle: at least `--idle-seconds` (default 1800) with zero endpoint and
   root-port corrected-event delta, polled every `--poll-seconds`; the first
   increment ends the run immediately with a failure record;
3. bounded read: `--read-gib` GiB of O_DIRECT sequential reads from the local
   checkpoint shards with zero corrected-event delta;
4. receipt assembly, validation, and atomic write.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


TOOLS_DIR = Path(__file__).resolve().parent
VALIDATOR_PATH = TOOLS_DIR / "validate-q38-root-nvme-link-clearance-v1.py"
ENDPOINT_BDF = "0000:01:00.0"
ROOT_PORT_BDF = "0000:00:03.1"
PCI_ROOT = Path("/sys/bus/pci/devices")
BLOCK_STAT = Path("/sys/block/nvme0n1/stat")
DEFAULT_READ_SOURCE = Path("/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8")
DEFAULT_SUDO_PASSWORD_FILE = Path("/home/steve/SUDOPASSWORD.txt")


def load_validator() -> Any:
    spec = importlib.util.spec_from_file_location("q38_link_clearance", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class LinkSample:
    monotonic: float
    endpoint_corrected: int
    endpoint_nonfatal: int
    endpoint_fatal: int
    root_corrected: int
    sectors_read: int


def read_aer_total(bdf: str, kind: str) -> int:
    path = PCI_ROOT / bdf / f"aer_dev_{kind}"
    key = {
        "correctable": "TOTAL_ERR_COR",
        "nonfatal": "TOTAL_ERR_NONFATAL",
        "fatal": "TOTAL_ERR_FATAL",
    }[kind]
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == key:
            return int(parts[1])
    raise ValueError(f"{key} missing in {path}")


def read_sectors_read() -> int:
    return int(BLOCK_STAT.read_text(encoding="utf-8").split()[2])


def sample_link() -> LinkSample:
    return LinkSample(
        monotonic=time.monotonic(),
        endpoint_corrected=read_aer_total(ENDPOINT_BDF, "correctable"),
        endpoint_nonfatal=read_aer_total(ENDPOINT_BDF, "nonfatal"),
        endpoint_fatal=read_aer_total(ENDPOINT_BDF, "fatal"),
        root_corrected=read_aer_total(ROOT_PORT_BDF, "correctable"),
        sectors_read=read_sectors_read(),
    )


def delta(before: LinkSample, after: LinkSample) -> dict[str, int]:
    return {
        "local_nvme_corrected_delta": after.endpoint_corrected
        - before.endpoint_corrected,
        "local_nvme_nonfatal_delta": after.endpoint_nonfatal - before.endpoint_nonfatal,
        "local_nvme_fatal_delta": after.endpoint_fatal - before.endpoint_fatal,
        "root_port_corrected_delta": after.root_corrected - before.root_corrected,
        "sectors_read_delta": after.sectors_read - before.sectors_read,
    }


def link_dirty(d: dict[str, int]) -> bool:
    return any(
        d[k] != 0
        for k in (
            "local_nvme_corrected_delta",
            "local_nvme_nonfatal_delta",
            "local_nvme_fatal_delta",
            "root_port_corrected_delta",
        )
    )


def run_idle_window(
    *,
    seconds: int,
    poll_seconds: float,
    sampler: Callable[[], LinkSample],
    sleeper: Callable[[float], None] = time.sleep,
    progress: Callable[[str], None] | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Poll the link until `seconds` elapse; stop on the first new event."""
    start = sampler()
    polls = 0
    while True:
        now = sampler()
        polls += 1
        d = delta(start, now)
        elapsed = now.monotonic - start.monotonic
        if link_dirty(d):
            return False, {
                "seconds": int(elapsed),
                "polls": polls,
                **d,
                "reason": "link-event",
            }
        if elapsed >= seconds:
            return True, {"seconds": int(elapsed), "polls": polls, **d}
        if progress is not None and polls % 60 == 0:
            progress(
                f"idle {int(elapsed)}/{seconds}s clean ({d['sectors_read_delta']} sectors read)"
            )
        sleeper(poll_seconds)


def select_read_files(source: Path, budget_bytes: int) -> list[tuple[Path, int]]:
    files = sorted(
        p for p in source.iterdir() if p.suffix == ".safetensors" and p.is_file()
    )
    if not files:
        raise ValueError(f"no safetensors shards under {source}")
    plan: list[tuple[Path, int]] = []
    remaining = budget_bytes
    for path in files:
        if remaining <= 0:
            break
        size = path.stat().st_size
        take = min(size, remaining)
        # dd reads whole 16 MiB blocks; round down so we never exceed the budget.
        take -= take % (16 << 20)
        if take <= 0:
            continue
        plan.append((path, take))
        remaining -= take
    return plan


def run_bounded_read(
    *,
    source: Path,
    read_gib: int,
    sampler: Callable[[], LinkSample],
    runner: Callable[[list[str]], None] = lambda cmd: subprocess.run(
        cmd, check=True, capture_output=True
    ),
    budget_bytes: int | None = None,
) -> tuple[bool, dict[str, Any]]:
    budget = (read_gib << 30) if budget_bytes is None else budget_bytes
    plan = select_read_files(source, budget)
    before = sampler()
    started = time.monotonic()
    total = 0
    for path, take in plan:
        blocks = take // (16 << 20)
        runner(
            [
                "dd",
                f"if={path}",
                "of=/dev/null",
                "bs=16M",
                f"count={blocks}",
                "iflag=direct",
                "status=none",
            ]
        )
        total += take
    elapsed = time.monotonic() - started
    after = sampler()
    d = delta(before, after)
    record = {
        **d,
        "bytes_read": total,
        "files": [str(p) for p, _ in plan],
        "seconds": round(elapsed, 3),
        "mib_per_s": round(total / (1 << 20) / elapsed, 1) if elapsed > 0 else None,
    }
    return (not link_dirty(d)) and total >= budget - (16 << 20), record


def read_smart(sudo_password_file: Path) -> dict[str, Any]:
    with sudo_password_file.open("rb") as handle:
        proc = subprocess.run(
            ["sudo", "-S", "-p", "", "nvme", "smart-log", "/dev/nvme0", "-o", "json"],
            stdin=handle,
            capture_output=True,
            check=True,
        )
    smart = json.loads(proc.stdout.decode("utf-8"))
    return {
        "critical_warning": int(smart["critical_warning"]),
        "media_errors": int(smart["media_errors"]),
        "num_err_log_entries": int(smart["num_err_log_entries"]),
        "temperature_c": int(smart["temperature"]) - 273,
    }


def read_b70_devices() -> list[dict[str, Any]]:
    proc = subprocess.run(
        ["xpu-smi", "discovery", "-j"], capture_output=True, check=True, timeout=60
    )
    devices = json.loads(proc.stdout.decode("utf-8"))["device_list"]
    return [
        {
            "device_id": int(d["device_id"]),
            "device_name": str(d["device_name"]),
            "pci_bdf_address": str(d["pci_bdf_address"]),
        }
        for d in devices
    ]


def render_node_users() -> list[str]:
    proc = subprocess.run(
        [
            "fuser",
            "-v",
            "/dev/dri/renderD128",
            "/dev/dri/renderD129",
            "/dev/dri/renderD130",
            "/dev/dri/renderD131",
        ],
        capture_output=True,
    )
    text = (proc.stdout + proc.stderr).decode("utf-8", "replace")
    return [
        line
        for line in text.splitlines()
        if line.strip() and "USER" not in line and not line.strip().endswith(":")
    ]


def runtime_clear() -> dict[str, Any]:
    proc = subprocess.run(
        [str(TOOLS_DIR / "check-q38-recovery-runtime-clear.sh")],
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout.decode("utf-8"))


def build_receipt(
    *,
    boot_id: str,
    root_nvme: dict[str, str],
    idle: dict[str, Any],
    bounded: dict[str, Any],
    smart: dict[str, Any],
    b70_devices: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "pass",
        "classification": "q38_root_nvme_link_clearance_v1",
        "boot_id": boot_id,
        "root_nvme": dict(root_nvme),
        "idle": {
            "seconds": int(idle["seconds"]),
            "local_nvme_corrected_delta": int(idle["local_nvme_corrected_delta"]),
            "root_port_corrected_delta": int(idle["root_port_corrected_delta"]),
        },
        "bounded_read": {
            "local_nvme_corrected_delta": int(bounded["local_nvme_corrected_delta"]),
            "root_port_corrected_delta": int(bounded["root_port_corrected_delta"]),
        },
        "smart": {
            "critical_warning": int(smart["critical_warning"]),
            "media_errors": int(smart["media_errors"]),
        },
        "b70_devices": [dict(d) for d in b70_devices],
    }


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--idle-seconds", type=int, default=1800)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--read-gib", type=int, default=4)
    parser.add_argument("--read-source", type=Path, default=DEFAULT_READ_SOURCE)
    parser.add_argument(
        "--sudo-password-file", type=Path, default=DEFAULT_SUDO_PASSWORD_FILE
    )
    parser.add_argument(
        "--clearance-json",
        type=Path,
        default=None,
        help="defaults to the validator's fixed path",
    )
    args = parser.parse_args()

    validator = load_validator()
    clearance_path = args.clearance_json or validator.CLEARANCE_PATH
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    evidence_path = clearance_path.with_name(
        clearance_path.stem + f".evidence-{stamp}.json"
    )

    def log(msg: str) -> None:
        print(f"[clearance {time.strftime('%H:%M:%S')}] {msg}", flush=True)

    evidence: dict[str, Any] = {"stamp_utc": stamp, "phases": {}}

    # Live identity first: a wrong controller or stale firmware fails before waiting 30 minutes.
    live = validator.read_live_identity()
    evidence["live_identity"] = live
    for key, expected in validator.EXPECTED_ROOT_NVME.items():
        if live["root_nvme"][key] != expected:
            log(
                f"live root_nvme.{key}={live['root_nvme'][key]!r} != required {expected!r}; refusing to start"
            )
            evidence["status"] = "fail"
            evidence["reason"] = f"live-identity:{key}"
            write_json_atomic(evidence_path, evidence)
            return 2

    users = render_node_users()
    conflicts = runtime_clear()
    smart_before = read_smart(args.sudo_password_file)
    evidence["phases"]["admission"] = {
        "render_node_users": users,
        "runtime_conflict_status": conflicts.get("status"),
        "smart": smart_before,
    }
    if (
        users
        or conflicts.get("status") != "clear"
        or smart_before["critical_warning"]
        or smart_before["media_errors"]
    ):
        log("admission failed: render-node users, runtime conflicts, or dirty SMART")
        evidence["status"] = "fail"
        evidence["reason"] = "admission"
        write_json_atomic(evidence_path, evidence)
        return 3

    log(f"idle window: {args.idle_seconds}s, polling every {args.poll_seconds}s")
    ok, idle = run_idle_window(
        seconds=args.idle_seconds,
        poll_seconds=args.poll_seconds,
        sampler=sample_link,
        progress=log,
    )
    evidence["phases"]["idle"] = idle
    if not ok:
        log(f"idle window failed after {idle['seconds']}s: {idle}")
        evidence["status"] = "fail"
        evidence["reason"] = "idle"
        write_json_atomic(evidence_path, evidence)
        return 4
    log(f"idle window clean: {idle}")

    log(f"bounded read: {args.read_gib} GiB O_DIRECT from {args.read_source}")
    ok, bounded = run_bounded_read(
        source=args.read_source, read_gib=args.read_gib, sampler=sample_link
    )
    evidence["phases"]["bounded_read"] = bounded
    if not ok:
        log(f"bounded read failed: {bounded}")
        evidence["status"] = "fail"
        evidence["reason"] = "bounded_read"
        write_json_atomic(evidence_path, evidence)
        return 5
    log(
        f"bounded read clean: {bounded['mib_per_s']} MiB/s, {bounded['bytes_read']} bytes"
    )

    smart_after = read_smart(args.sudo_password_file)
    b70 = read_b70_devices()
    evidence["phases"]["final"] = {"smart": smart_after, "b70_devices": b70}
    receipt = build_receipt(
        boot_id=live["boot_id"],
        root_nvme=live["root_nvme"],
        idle=idle,
        bounded=bounded,
        smart=smart_after,
        b70_devices=b70,
    )
    try:
        validator.validate(receipt, live_identity=validator.read_live_identity())
    except (ValueError, KeyError) as exc:
        rejected = clearance_path.with_name(
            clearance_path.stem + f".rejected-{stamp}.json"
        )
        write_json_atomic(rejected, receipt)
        evidence["status"] = "fail"
        evidence["reason"] = f"validator:{exc}"
        write_json_atomic(evidence_path, evidence)
        log(f"validator rejected the assembled receipt: {exc}; wrote {rejected}")
        return 6

    write_json_atomic(clearance_path, receipt)
    evidence["status"] = "pass"
    evidence["clearance_path"] = str(clearance_path)
    write_json_atomic(evidence_path, evidence)
    # Final proof: the tracked validator accepts the file at its fixed path.
    subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--clearance-json", str(clearance_path)],
        check=True,
    )
    log(f"clearance receipt written and validated: {clearance_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
