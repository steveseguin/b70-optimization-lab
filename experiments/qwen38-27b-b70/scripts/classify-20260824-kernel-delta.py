#!/usr/bin/env python3
"""Classify a frozen kernel-journal delta without hiding known raw events.

The only non-reject hardware block is the exact corrected physical-layer
receiver event emitted by this host's healthy Samsung root NVMe. Everything
else continues through the caller's broad reject expression.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path


SCHEMA = "neural-download-kernel-delta-classification-v1"
KNOWN_NVME_BDF = "0000:01:00.0"
KNOWN_NVME_VENDOR_DEVICE = "144d:a80a"

# Full-match expressions for the one established benign block. Keeping the
# complete ordered block fail-closed prevents a similar-looking GPU, fatal,
# nonfatal, uncorrected, reset, timeout, or alternate AER event from passing.
KNOWN_NVME_BLOCK = (
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]: Hardware error from APEI Generic Hardware Error Source: 514",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]: It has been corrected by h/w and requires no further action",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]: event severity: corrected",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:  Error 0, type: corrected",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:   section_type: PCIe error",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:   port_type: 0, PCIe end point",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:   version: 0\.2",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:   command: 0x0406, status: 0x0010",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:   device_id: 0000:01:00\.0",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:   slot: 0",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:   secondary_bus: 0x00",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:   vendor_id: 0x144d, device_id: 0xa80a",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:   class_code: 010802",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:   bridge: secondary_status: 0x0000, control: 0x0000",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:   aer_cor_status: 0x00000001, aer_cor_mask: 0x00000000",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:   aer_uncor_status: 0x00000000, aer_uncor_mask: 0x00100000",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:   aer_uncor_severity: 0x004f6030",
    r"\{(?P<event_id>\d+)\}\[Hardware Error\]:   TLP Header: 00000000 00000000 00000000 00000000",
    r"nvme 0000:01:00\.0: aer_status: 0x00000001, aer_mask: 0x00000000",
    r"nvme 0000:01:00\.0:    \[ 0\] RxErr                  \(First\)",
    r"nvme 0000:01:00\.0: aer_layer=Physical Layer, aer_agent=Receiver ID",
)
KNOWN_NVME_BLOCK_RE = tuple(re.compile(pattern) for pattern in KNOWN_NVME_BLOCK)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delta", required=True, type=Path)
    parser.add_argument("--reject-pattern", required=True)
    parser.add_argument("--reject-output", required=True, type=Path)
    parser.add_argument("--accepted-output", required=True, type=Path)
    parser.add_argument("--summary-output", required=True, type=Path)
    parser.add_argument("--max-known-nvme-events", type=int, default=1)
    return parser.parse_args()


def kernel_message(line: str) -> str | None:
    marker = " kernel: "
    if marker not in line:
        return None
    return line.split(marker, 1)[1].rstrip("\n")


def exact_known_block_at(lines: list[str], start: int) -> tuple[int, str] | None:
    stop = start + len(KNOWN_NVME_BLOCK_RE)
    if stop > len(lines):
        return None
    event_id: str | None = None
    timestamp: str | None = None
    for offset, matcher in enumerate(KNOWN_NVME_BLOCK_RE):
        line = lines[start + offset]
        message = kernel_message(line)
        if message is None:
            return None
        match = matcher.fullmatch(message)
        if match is None:
            return None
        fields = match.groupdict()
        current_event_id = fields.get("event_id")
        if current_event_id is not None:
            if event_id is None:
                event_id = current_event_id
            elif current_event_id != event_id:
                return None
        current_timestamp = line.split(maxsplit=1)[0]
        if timestamp is None:
            timestamp = current_timestamp
        elif current_timestamp != timestamp:
            return None
    assert timestamp is not None
    return stop, timestamp


def is_known_nvme_fragment(line: str) -> bool:
    """Return true for any exact line from the narrowly accepted signature.

    A journal cursor can begin or end inside the 21-line event. Such a partial
    block must reject even when its surviving line is not covered by the
    caller's historical broad expression (notably the final ``aer_layer``
    line).
    """

    message = kernel_message(line)
    if message is None:
        return False
    return any(matcher.fullmatch(message) for matcher in KNOWN_NVME_BLOCK_RE)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    args = parse_args()
    if args.max_known_nvme_events < 0:
        raise ValueError("--max-known-nvme-events must be nonnegative")
    raw = args.delta.read_bytes()
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    reject_re = re.compile(args.reject_pattern, re.IGNORECASE)

    candidates: list[tuple[int, int, str]] = []
    index = 0
    while index < len(lines):
        match = exact_known_block_at(lines, index)
        if match is None:
            index += 1
            continue
        stop, timestamp = match
        candidates.append((index, stop, timestamp))
        index = stop

    accepted: list[tuple[int, int, str]] = []
    if len(candidates) <= args.max_known_nvme_events:
        accepted = candidates
    accepted_indexes = {
        line_index
        for start, stop, _ in accepted
        for line_index in range(start, stop)
    }
    rejected_fragment_indexes = {
        line_index
        for line_index, line in enumerate(lines)
        if line_index not in accepted_indexes and is_known_nvme_fragment(line)
    }
    rejected_indexes = {
        line_index
        for line_index, line in enumerate(lines)
        if line_index not in accepted_indexes
        and (line_index in rejected_fragment_indexes or reject_re.search(line))
    }
    rejected_lines = [
        line for line_index, line in enumerate(lines) if line_index in rejected_indexes
    ]
    accepted_lines = [
        line
        for line_index, line in enumerate(lines)
        if line_index in accepted_indexes
    ]

    atomic_write(args.reject_output, "".join(rejected_lines))
    atomic_write(args.accepted_output, "".join(accepted_lines))
    summary = {
        "schema": SCHEMA,
        "delta_sha256": hashlib.sha256(raw).hexdigest(),
        "reject_pattern": args.reject_pattern,
        "known_nvme_signature": {
            "bdf": KNOWN_NVME_BDF,
            "vendor_device": KNOWN_NVME_VENDOR_DEVICE,
            "block_lines": len(KNOWN_NVME_BLOCK),
            "maximum_events": args.max_known_nvme_events,
        },
        "known_nvme_candidate_count": len(candidates),
        "known_nvme_accepted_count": len(accepted),
        "known_nvme_accepted_timestamps": [item[2] for item in accepted],
        "accepted_line_count": len(accepted_lines),
        "rejected_known_nvme_fragment_count": len(rejected_fragment_indexes),
        "reject_line_count": len(rejected_lines),
        "decision": "pass" if not rejected_lines else "reject",
    }
    atomic_write(
        args.summary_output,
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
    )
    return 0 if not rejected_lines else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, ValueError, re.error) as error:
        print(f"kernel-delta classifier error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
