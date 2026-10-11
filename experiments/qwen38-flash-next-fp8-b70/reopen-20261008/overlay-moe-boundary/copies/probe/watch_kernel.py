#!/usr/bin/env python3
"""Independent CPU watcher for the bounded production-path diagnostic.

Retains the original probe watcher's precise fault classification and latching
contract, with a full-load deadline and a 305-second post-exit observation gap.
Never signals, restarts, or initializes a device.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import screen


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def latch(directory, name, reason):
    try:
        with (directory / name).open("x") as stream:
            stream.write(reason + "\n")
    except FileExistsError:
        pass


def terminal_time(path, boot):
    if not path.exists():
        return None
    marker = json.loads(path.read_text())
    screen.require(marker.get("schema") == "screen1b.moe-boundary-controller-exit.v1"
                   and marker.get("boot_id") == boot and marker.get("server_exited") is True,
                   "invalid controller exit marker")
    value = marker.get("exit_unix")
    screen.require(isinstance(value, (int, float)) and 0 < value <= time.time(),
                   "invalid controller exit time")
    return value


def watch(run, cutoff):
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    admission = json.loads((run / "journal-admission.json").read_text())
    screen.require(admission.get("passed") is True and
                   admission.get("monitoring_cutoff_unix") == cutoff,
                   "watcher admission must match the controller receipt")
    screen.require(not (run / "watcher.json").exists(), "watcher exists; no retry")
    deadline = time.monotonic() + 2700
    failure = None
    retained_faults = []

    def failed(reason):
        nonlocal failure
        failure = failure or reason
        latch(run, "STOP", failure)
        latch(run, "FAULT", failure)

    try:
        while True:
            screen.require(time.monotonic() < deadline, "2700-second watcher bound exceeded")
            screen.require(Path("/proc/sys/kernel/random/boot_id").read_text().strip() == boot,
                           "watcher boot changed")
            read_started = time.time()
            readable = False
            try:
                text = screen.journal()
                (run / "kernel-watcher.log").write_text(text)
                faults = screen.new_fault_lines(text, cutoff)
                readable = True
                for line in faults:
                    if line not in retained_faults:
                        retained_faults.append(line)
                if faults:
                    failed("kernel fault: " + str(faults[:1]))
            except Exception as exc:
                failed(f"{type(exc).__name__}: {exc}")
            row = dict(passed=failure is None, boot_id=boot, updated_unix=time.time(),
                       read_started_unix=read_started, new_fault_lines=retained_faults,
                       monitoring_cutoff_unix=cutoff, journal_readable=readable)
            if failure is not None:
                row["exception"] = failure
            exited = terminal_time(run / "controller-exit.json", boot)
            if readable and exited is not None and read_started >= exited + 305:
                row.update(status="post-exit gap complete", post_exit_gap_seconds=305)
                atomic_json(run / "watcher.json", row)
                return 0 if failure is None else 2
            atomic_json(run / "watcher.json", row)
            time.sleep(.5)
    except BaseException as exc:
        reason = f"{type(exc).__name__}: {exc}"
        failed(reason)
        atomic_json(run / "watcher.json", dict(passed=False, boot_id=boot,
                    updated_unix=time.time(), exception=failure, terminal_exception=reason,
                    new_fault_lines=retained_faults))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt-dir", required=True, type=Path)
    parser.add_argument("--cutoff", required=True, type=float)
    args = parser.parse_args()
    return watch(args.receipt_dir, args.cutoff)


if __name__ == "__main__":
    sys.exit(main())
