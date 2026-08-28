#!/usr/bin/env python3
"""Fail closed unless every hardware-error block is the allowed root-NVMe RxErr."""

from __future__ import annotations

import pathlib
import re
import sys

ROOT_NVME = "0000:01:00.0"
B70_ENDPOINTS = re.compile(r"0000:(?:23|27|43|47):00\.0", re.I)
TIMESTAMP = re.compile(r"^(\w{3}\s+\d+\s+\d\d:\d\d:\d\d)\s+")
APEI_START = re.compile(r"Hardware error from APEI Generic Hardware Error Source", re.I)
AER_START = re.compile(
    r"AER:.*error message received from|PCIe Bus Error:\s*severity", re.I
)
EVENT_ID = re.compile(r"(\{[^}]+\})\[Hardware Error\]")
RELATED = re.compile(
    r"\[Hardware Error\]|\bAER:|PCIe Bus Error|\baer_(?:cor|uncor|status|mask|layer|agent)"
    r"|\bRxErr\b|event severity|\bError \d+, type:|Hardware error from APEI",
    re.I,
)
ADVERSE = re.compile(
    r"invoked oom-killer|Out of memory: Killed process|oom-kill:|"
    r"severity\s*[=: ]+\s*(?:Uncorrected|Fatal)(?:\b|\s)|"
    r"event severity\s*[=: ]+\s*(?:Uncorrected|Fatal)(?:\b|\s)|"
    r"\buncorrectable\b|Surprise Down|Completion Timeout|Poisoned TLP|Malformed TLP|"
    r"I/O error|blk_update_request|Buffer I/O|end_request:.*error|critical medium error|"
    r"lost page write|read-only file system|Remounting filesystem read-only|"
    r"EXT4-fs (?:error|warning)|"
    r"nvme.*(?:error|timeout|reset|controller.*down|device.*not ready|abort|failed|offline)",
    re.I,
)
EXPLICIT_CORRECTED = re.compile(
    r"event severity\s*[=: ]+\s*corrected\b|"
    r"severity\s*[=: ]+\s*corrected\b|"
    r"\bError \d+, type:\s*corrected\b|"
    r"has been corrected by h/w",
    re.I,
)
ENDPOINT_PATTERNS = (
    re.compile(r"device_id:\s*(0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7])", re.I),
    re.compile(r"received from\s+(0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7])", re.I),
    re.compile(r"\bnvme\s+(0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]):", re.I),
)


def die(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(70)


def timestamp(line: str) -> str | None:
    match = TIMESTAMP.search(line)
    return match.group(1) if match else None


def event_start(line: str) -> bool:
    return bool(APEI_START.search(line) or AER_START.search(line))


def primary_event_start(line: str) -> bool:
    return bool(
        APEI_START.search(line)
        or re.search(r"AER:.*error message received from", line, re.I)
    )


def collect_blocks(lines: list[str]) -> tuple[list[list[str]], set[int]]:
    blocks: list[list[str]] = []
    consumed: set[int] = set()
    i = 0
    while i < len(lines):
        if not event_start(lines[i]):
            i += 1
            continue
        start = i
        block_ts = timestamp(lines[i])
        id_match = EVENT_ID.search(lines[i])
        event_id = id_match.group(1) if id_match else None
        i += 1
        while i < len(lines) and not primary_event_start(lines[i]):
            line = lines[i]
            line_id_match = EVENT_ID.search(line)
            line_id = line_id_match.group(1) if line_id_match else None
            same_id = event_id is not None and line_id == event_id
            same_time_related = (
                block_ts is not None
                and timestamp(line) == block_ts
                and (
                    RELATED.search(line)
                    or re.search(r"\b(?:nvme|pcieport)\s+0000:[0-9a-f:.]+:", line, re.I)
                )
            )
            if not (same_id or same_time_related):
                break
            i += 1
        block = lines[start:i]
        blocks.append(block)
        consumed.update(range(start, i))
    return blocks, consumed


def endpoints(block_text: str) -> set[str]:
    found: set[str] = set()
    for pattern in ENDPOINT_PATTERNS:
        found.update(match.lower() for match in pattern.findall(block_text))
    return found


def main() -> None:
    if len(sys.argv) != 3:
        die("usage: classifier JOURNAL ALLOWED_BLOCKS_OUTPUT")
    journal = pathlib.Path(sys.argv[1])
    output = pathlib.Path(sys.argv[2])
    if not journal.is_file() or journal.is_symlink():
        die("journal is not a regular non-symlink file")
    if output.exists():
        die("allowed-block output already exists")

    lines = journal.read_text(errors="strict").splitlines(keepends=True)
    whole = "".join(lines)
    if B70_ENDPOINTS.search(whole):
        die("journal names a frozen B70 endpoint")
    if ADVERSE.search(whole):
        die("journal contains an OOM, fatal PCIe, or adverse storage signature")

    blocks, consumed = collect_blocks(lines)
    orphan_indexes = [
        index for index, line in enumerate(lines) if RELATED.search(line) and index not in consumed
    ]
    if orphan_indexes:
        die(f"unbound hardware/AER detail at journal line {orphan_indexes[0] + 1}")

    allowed: list[str] = []
    for number, block in enumerate(blocks, start=1):
        text = "".join(block)
        if not re.search(r"\bRxErr\b", text, re.I):
            die(f"event block {number} is not the narrowly allowed RxErr class")
        if not EXPLICIT_CORRECTED.search(text):
            die(f"event block {number} lacks explicit corrected severity")
        found = endpoints(text)
        if found != {ROOT_NVME}:
            die(f"event block {number} endpoint set is {sorted(found)!r}, not root NVMe only")
        allowed.append(f"----- allowed event block {number} -----\n{text}")

    output.write_text("".join(allowed))


if __name__ == "__main__":
    main()
