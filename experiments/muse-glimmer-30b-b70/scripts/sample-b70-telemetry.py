#!/usr/bin/env python3
"""Sample read-only B70 frequency, energy, and temperature sysfs counters."""

import argparse
import json
import os
from pathlib import Path
import signal
import time


MUSE_BDFS = {"0000:23:00.0", "0000:27:00.0", "0000:43:00.0", "0000:47:00.0"}
running = True


def stop(_signum, _frame):
    global running
    running = False


def read_int(path):
    try:
        return int(path.read_text().strip())
    except (FileNotFoundError, OSError, ValueError):
        return None


def discover_cards():
    cards = []
    for card in sorted(Path("/sys/class/drm").glob("card[0-9]*")):
        try:
            bdf = card.joinpath("device").resolve().name
        except OSError:
            continue
        if bdf not in MUSE_BDFS:
            continue
        hwmons = list(card.glob("device/hwmon/hwmon*"))
        cards.append({"card": card.name, "bdf": bdf, "root": card, "hwmon": hwmons[0] if hwmons else None})
    if {card["bdf"] for card in cards} != MUSE_BDFS:
        raise RuntimeError(f"expected BDFs {sorted(MUSE_BDFS)}, found {[card['bdf'] for card in cards]}")
    return cards


def temp_by_label(hwmon, wanted):
    if hwmon is None:
        return None
    for label_path in hwmon.glob("temp*_label"):
        try:
            if label_path.read_text().strip() == wanted:
                return read_int(label_path.with_name(label_path.name.replace("_label", "_input")))
        except OSError:
            continue
    return None


def snapshot(card):
    root = card["root"]
    hwmon = card["hwmon"]
    return {
        "card": card["card"],
        "bdf": card["bdf"],
        "gt0_act_mhz": read_int(root / "device/tile0/gt0/freq0/act_freq"),
        "gt0_cur_mhz": read_int(root / "device/tile0/gt0/freq0/cur_freq"),
        "gt1_act_mhz": read_int(root / "device/tile0/gt1/freq0/act_freq"),
        "gt1_cur_mhz": read_int(root / "device/tile0/gt1/freq0/cur_freq"),
        "energy_card_uj": read_int(hwmon / "energy1_input") if hwmon else None,
        "energy_pkg_uj": read_int(hwmon / "energy2_input") if hwmon else None,
        "power_cap_uw": read_int(hwmon / "power1_cap") if hwmon else None,
        "temp_pkg_mc": temp_by_label(hwmon, "pkg"),
        "temp_vram_mc": temp_by_label(hwmon, "vram"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--interval-ms", type=float, default=100.0)
    parser.add_argument("--duration-s", type=float, default=0.0, help="zero samples until SIGTERM/SIGINT")
    args = parser.parse_args()
    if args.interval_ms < 20:
        parser.error("--interval-ms must be at least 20")

    cards = discover_cards()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    start_ns = time.monotonic_ns()
    deadline_ns = start_ns + int(args.duration_s * 1e9) if args.duration_s > 0 else None
    next_ns = start_ns
    with output.open("x") as stream:
        stream.write(json.dumps({
            "kind": "metadata",
            "pid": os.getpid(),
            "interval_ms": args.interval_ms,
            "cards": [{"card": card["card"], "bdf": card["bdf"]} for card in cards],
        }) + "\n")
        while running and (deadline_ns is None or time.monotonic_ns() < deadline_ns):
            now_ns = time.monotonic_ns()
            stream.write(json.dumps({
                "kind": "sample",
                "elapsed_ms": round((now_ns - start_ns) / 1e6, 3),
                "cards": [snapshot(card) for card in cards],
            }) + "\n")
            stream.flush()
            next_ns += int(args.interval_ms * 1e6)
            time.sleep(max(0.0, (next_ns - time.monotonic_ns()) / 1e9))


if __name__ == "__main__":
    main()
