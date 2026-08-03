#!/usr/bin/env python3
"""Apply the frozen offline ISA gate to the matched INT4 tile-record probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path


KERNEL_RE = re.compile(r"^//\.kernel (.*LagunaInt4TileRecordProbeILb([01])EE)$")
METRIC_RES = {
    "instructions": re.compile(r"^//\.instCount\s+(\d+)$", re.MULTILINE),
    "alu_instructions": re.compile(r"^//\.numALUInst:\s*(\d+)$", re.MULTILINE),
    "sync_instructions": re.compile(r"^//\.syncInstCount:\s*(\d+)$", re.MULTILINE),
    "grf": re.compile(r"^//\.thread_config\s+numGRF=(\d+),", re.MULTILINE),
}
INSTRUCTION_RE = re.compile(r"^\s*(?:\([^)]*\)\s*)*([a-z][a-z0-9_.]*)\s")
MEMORY_PREFIXES = ("load", "store", "send", "sync", "barrier", "fence")


@dataclass(frozen=True)
class KernelMetrics:
    path: str
    sha256: str
    kernel: str
    instructions: int
    alu_instructions: int
    sync_instructions: int
    grf: int
    dpas: int
    mul: int
    memory_opcodes: dict[str, int]
    executable_spill_or_scratch: list[str]


def _required_metric(text: str, name: str) -> int:
    match = METRIC_RES[name].search(text)
    if match is None:
        raise ValueError(f"missing {name} metric")
    return int(match.group(1))


def _instruction_opcodes(text: str) -> list[tuple[str, str, bool]]:
    instructions = []
    for raw_line in text.splitlines():
        code = raw_line.split("//", 1)[0]
        match = INSTRUCTION_RE.match(code)
        if match is not None:
            instructions.append(
                (
                    match.group(1),
                    raw_line.strip(),
                    not code.lstrip().startswith("("),
                )
            )
    return instructions


def parse_assembly(path: Path) -> tuple[bool, KernelMetrics] | None:
    text = path.read_text()
    first_line = text.splitlines()[0] if text else ""
    kernel_match = KERNEL_RE.fullmatch(first_line)
    if kernel_match is None:
        return None

    instructions = _instruction_opcodes(text)
    opcodes = [opcode for opcode, _, _ in instructions]
    memory_opcodes = Counter(
        opcode for opcode in opcodes if opcode.startswith(MEMORY_PREFIXES)
    )
    executable_spill_or_scratch = [
        line
        for _, line, _ in instructions
        if re.search(r"\b(?:spill|scratch)\b", line, re.IGNORECASE)
    ]
    metrics = KernelMetrics(
        path=str(path),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        kernel=kernel_match.group(1),
        instructions=_required_metric(text, "instructions"),
        alu_instructions=_required_metric(text, "alu_instructions"),
        sync_instructions=_required_metric(text, "sync_instructions"),
        grf=_required_metric(text, "grf"),
        dpas=sum(opcode.startswith("dpas") for opcode in opcodes),
        mul=sum(
            opcode.split(".", 1)[0] == "mul" and unpredicated
            for opcode, _, unpredicated in instructions
        ),
        memory_opcodes=dict(sorted(memory_opcodes.items())),
        executable_spill_or_scratch=executable_spill_or_scratch,
    )
    return kernel_match.group(2) == "1", metrics


def analyze(output_dir: Path, max_candidate_instructions: int = 378) -> dict:
    selected: dict[bool, list[KernelMetrics]] = {False: [], True: []}
    errors = []
    for path in sorted(output_dir.glob("*.asm")):
        try:
            parsed = parse_assembly(path)
        except ValueError as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        if parsed is not None:
            candidate, metrics = parsed
            selected[candidate].append(metrics)

    for candidate, label in ((False, "control"), (True, "candidate")):
        if len(selected[candidate]) != 1:
            errors.append(
                f"expected exactly one {label} assembly, found "
                f"{len(selected[candidate])}"
            )

    if errors:
        return {"status": "fail", "errors": errors}

    control = selected[False][0]
    candidate = selected[True][0]
    checks = {
        "control_archived_identity": (
            control.instructions == 370
            and control.alu_instructions == 320
            and control.sync_instructions == 9
            and control.dpas == 2
            and control.mul == 33
            and control.grf == 128
        ),
        "candidate_instruction_ceiling": (
            candidate.instructions <= max_candidate_instructions
        ),
        "candidate_arithmetic_identity": (
            candidate.dpas == control.dpas == 2 and candidate.mul == control.mul == 33
        ),
        "candidate_sync_identity": (
            candidate.sync_instructions == control.sync_instructions == 9
        ),
        "candidate_memory_opcode_identity": (
            candidate.memory_opcodes == control.memory_opcodes
        ),
        "grf128_identity": candidate.grf == control.grf == 128,
        "no_executable_spill_or_scratch": not (
            control.executable_spill_or_scratch or candidate.executable_spill_or_scratch
        ),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "thresholds": {
            "max_candidate_instructions": max_candidate_instructions,
            "archived_control_instructions": 370,
            "expected_dpas": 2,
            "expected_mul": 33,
            "expected_grf": 128,
        },
        "checks": checks,
        "control": asdict(control),
        "candidate": asdict(candidate),
        "delta": {
            "instructions": candidate.instructions - control.instructions,
            "alu_instructions": (candidate.alu_instructions - control.alu_instructions),
            "sync_instructions": (
                candidate.sync_instructions - control.sync_instructions
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--max-candidate-instructions", type=int, default=378)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    report = analyze(args.output_dir, args.max_candidate_instructions)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_output is not None:
        args.json_output.write_text(encoded)
    print(encoded, end="")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
