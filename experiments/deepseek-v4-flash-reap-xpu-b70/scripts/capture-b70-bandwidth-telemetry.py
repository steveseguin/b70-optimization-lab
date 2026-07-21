#!/usr/bin/env python3
"""Capture read-only B70 sysfs telemetry during a sustained load."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def read_number(path: Path) -> int | None:
    try:
        return int(path.read_text().strip(), 0)
    except (FileNotFoundError, PermissionError, ValueError):
        return None


def discover() -> list[tuple[str, Path]]:
    cards: list[tuple[str, Path]] = []
    for card in Path("/sys/class/drm").glob("card[0-9]*"):
        if read_number(card / "device/vendor") != 0x8086:
            continue
        if read_number(card / "device/device") != 0xE223:
            continue
        bdf = (card / "device").resolve().name
        cards.append((bdf, card))
    return sorted(cards)


def snapshot(cards: list[tuple[str, Path]]) -> list[dict[str, int | str | None]]:
    rows = []
    for ordinal, (bdf, card) in enumerate(cards):
        hwmons = list((card / "device/hwmon").glob("hwmon*"))
        hw = hwmons[0] if hwmons else Path("/nonexistent")
        gt = card / "device/tile0/gt0/freq0"
        rows.append(
            {
                "ordinal": ordinal,
                "bdf": bdf,
                "drm": card.name,
                "energy_card_uJ": read_number(hw / "energy1_input"),
                "energy_pkg_uJ": read_number(hw / "energy2_input"),
                "power_cap_uW": read_number(hw / "power1_cap"),
                "power_crit_uW": read_number(hw / "power1_crit"),
                "temp_pkg_mC": read_number(hw / "temp2_input"),
                "temp_vram_mC": read_number(hw / "temp3_input"),
                "fan_rpm": read_number(hw / "fan1_input"),
                "gpu_act_MHz": read_number(gt / "act_freq"),
                "gpu_cur_MHz": read_number(gt / "cur_freq"),
                "gpu_max_MHz": read_number(gt / "max_freq"),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=65.0)
    parser.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args()
    cards = discover()
    if len(cards) != 4:
        raise SystemExit(f"expected four B70s, found {cards}")
    start = time.monotonic()
    samples = []
    while True:
        now = time.monotonic()
        samples.append({"elapsed_s": now - start, "cards": snapshot(cards)})
        remaining = args.seconds - (time.monotonic() - start)
        if remaining <= 0:
            break
        time.sleep(min(args.interval, remaining))
    print(json.dumps({"duration_s": time.monotonic() - start, "samples": samples}, indent=2))


if __name__ == "__main__":
    main()
