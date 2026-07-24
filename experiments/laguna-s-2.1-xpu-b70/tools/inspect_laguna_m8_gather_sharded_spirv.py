#!/usr/bin/env python3
"""Fail-closed inspector for final-linked ``spirv-dis --raw-id`` assembly.

The input is standard textual SPIR-V emitted from the final linked device
module.  This is intentionally a small, standard-library-only parser: it
neither imports torch nor attempts to load a native extension.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


CANDIDATE = "_ZTSN4vllm3moe24LagunaM8MoeGatherShardedE"
INCUMBENT = "_ZTSN4vllm3moe9MoeGatherIN4sycl3_V13ext6oneapi8bfloat16ELi10ELi8EEE"
ENTRY_RE = re.compile(r'^\s*OpEntryPoint\s+\S+\s+(%\S+)\s+"([^"]+)"')
MODE_RE = re.compile(r"^\s*OpExecutionMode(?:Id)?\s+(%\S+)\s+(.+?)\s*$")
FUNCTION_RE = re.compile(r"^\s*(%\S+)\s*=\s*OpFunction\b")
NAME_RE = re.compile(r'^\s*OpName\s+(%\S+)\s+"([^"]+)"')
CALL_RE = re.compile(r"^\s*(%\S+)\s*=\s*OpFunctionCall\s+(%\S+)\s+(%\S+)")
MUL_RE = re.compile(r"^\s*(%\S+)\s*=\s*OpFMul\s+\S+\s+(%\S+)\s+(%\S+)")
ADD_RE = re.compile(r"^\s*(%\S+)\s*=\s*OpFAdd\s+\S+\s+(%\S+)\s+(%\S+)")
LOAD_RE = re.compile(r"^\s*(%\S+)\s*=\s*OpLoad\s+\S+\s+(%\S+)")
STORE_RE = re.compile(r"^\s*OpStore\s+(%\S+)\s+(%\S+)")
DECORATE_RE = re.compile(r"^\s*OpDecorate\s+(%\S+)\s+FPFastMathMode\s+(.+?)\s*$")
CONSTANT_RE = re.compile(r"^\s*(%\S+)\s*=\s*OpConstant\s+%\S+\s+(-?\d+)\s*$")
COMPARE_RE = re.compile(r"\bOp[SU]LessThan\s+%\S+\s+%\S+\s+(%\S+)\s*$")


class EvidenceError(ValueError):
    """Raised for malformed or nonconforming evidence."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _names(lines: list[str]) -> dict[str, str]:
    return {match.group(1): match.group(2) for line in lines if (match := NAME_RE.match(line))}


def _entry_ids(lines: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in lines:
        match = ENTRY_RE.match(line)
        if match:
            result[match.group(2)] = match.group(1)
    return result


def _function_body(lines: list[str], function_id: str) -> list[str]:
    start = next((index for index, line in enumerate(lines) if (match := FUNCTION_RE.match(line)) and match.group(1) == function_id), None)
    if start is None:
        raise EvidenceError(f"entry point {function_id} has no OpFunction body")
    end = next((index for index in range(start + 1, len(lines)) if lines[index].strip() == "OpFunctionEnd"), None)
    if end is None:
        raise EvidenceError(f"entry point {function_id} has no OpFunctionEnd")
    return lines[start : end + 1]


def _execution_modes(lines: list[str], function_id: str) -> list[str]:
    modes = []
    for line in lines:
        match = MODE_RE.match(line)
        if match and match.group(1) == function_id:
            modes.append(" ".join(match.group(2).split()))
    return modes


def _function_call_count(body: list[str], callee_id: str) -> int:
    return sum(
        1
        for line in body
        if (match := CALL_RE.match(line)) and match.group(3) == callee_id
    )


def _constants(lines: list[str]) -> dict[str, int]:
    return {
        match.group(1): int(match.group(2))
        for line in lines
        if (match := CONSTANT_RE.match(line))
    }


def _loop_bounds(body: list[str], constants: dict[str, int]) -> dict[str, int]:
    """Count only loop-comparison bounds, resolving raw-id constants."""
    result = {"10": 0, "8": 0}
    for line in body:
        match = COMPARE_RE.search(line)
        if match and constants.get(match.group(1)) in (8, 10):
            result[str(constants[match.group(1)])] += 1
    return result


def _conversion_calls(body: list[str], names: dict[str, str]) -> dict[str, int]:
    to_fp32 = 0
    to_bf16 = 0
    for line in body:
        match = CALL_RE.match(line)
        if not match:
            continue
        callee = names.get(match.group(3), "").lower()
        compact = callee.replace("_", "")
        if "bfloat16" in compact or "bf16" in compact:
            if any(token in compact for token in ("tofloat", "tof", "tofp32")):
                to_fp32 += 1
            if any(token in compact for token in ("fromfloat", "fromf", "fromfp32", "tobfloat", "tobf16")):
                to_bf16 += 1
    return {"bf16_to_fp32": to_fp32, "fp32_to_bf16": to_bf16}


def _arithmetic(body: list[str], decorations: dict[str, str]) -> dict[str, Any]:
    loads: dict[str, str] = {}
    stores: list[tuple[str, str]] = []
    muls: dict[str, tuple[str, str]] = {}
    adds: dict[str, tuple[str, str]] = {}
    fused = False
    for line in body:
        lowered = line.lower()
        if "fma" in lowered or "fused" in lowered:
            fused = True
        if match := LOAD_RE.match(line):
            loads[match.group(1)] = match.group(2)
        elif match := STORE_RE.match(line):
            stores.append((match.group(1), match.group(2)))
        elif match := MUL_RE.match(line):
            muls[match.group(1)] = (match.group(2), match.group(3))
        elif match := ADD_RE.match(line):
            adds[match.group(1)] = (match.group(2), match.group(3))

    dependent = []
    pointer_matches = []
    for add_id, operands in adds.items():
        mul_id = next((operand for operand in operands if operand in muls), None)
        if mul_id is None:
            continue
        dependent.append((mul_id, add_id))
        acc = next(operand for operand in operands if operand != mul_id)
        load_pointer = loads.get(acc)
        stored_pointers = [pointer for pointer, value in stores if value == add_id]
        if load_pointer and load_pointer in stored_pointers:
            pointer_matches.append((mul_id, add_id, load_pointer))
    pairs = [
        {"mul": mul, "add": add, "mul_fast_math": decorations.get(mul), "add_fast_math": decorations.get(add)}
        for mul, add in dependent
    ]
    return {
        "fmul_count": len(muls),
        "fadd_count": len(adds),
        "dependent_pairs": pairs,
        "accumulator_pointer_pairs": pointer_matches,
        "no_fma_or_fused_opcode": not fused,
    }


def _inspect_kernel(
    lines: list[str],
    wrapper_id: str,
    implementation_id: str,
    names: dict[str, str],
    decorations: dict[str, str],
    constants: dict[str, int],
) -> dict[str, Any]:
    body = _function_body(lines, implementation_id)
    wrapper_body = _function_body(lines, wrapper_id)
    return {
        "entry_wrapper_id": wrapper_id,
        "implementation_id": implementation_id,
        "wrapper_calls_named_implementation": _function_call_count(
            wrapper_body, implementation_id
        ),
        "execution_modes": _execution_modes(lines, wrapper_id),
        "loop_bounds": _loop_bounds(body, constants),
        "conversions": _conversion_calls(body, names),
        "arithmetic": _arithmetic(body, decorations),
    }


def inspect_text(text: str) -> dict[str, Any]:
    """Inspect a textual module and return a deterministic, JSON-safe report."""
    lines = text.splitlines()
    entries = _entry_ids(lines)
    names = _names(lines)
    named_implementations = {name: value_id for value_id, name in names.items()}
    constants = _constants(lines)
    decorations = {match.group(1): " ".join(match.group(2).split()) for line in lines if (match := DECORATE_RE.match(line))}
    missing = [symbol for symbol in (CANDIDATE, INCUMBENT) if symbol not in entries]
    if missing:
        raise EvidenceError("missing exact entry point(s): " + ", ".join(missing))
    missing_implementations = [
        symbol for symbol in (CANDIDATE, INCUMBENT) if symbol not in named_implementations
    ]
    if missing_implementations:
        raise EvidenceError(
            "missing exact named implementation(s): "
            + ", ".join(missing_implementations)
        )
    candidate = _inspect_kernel(
        lines,
        entries[CANDIDATE],
        named_implementations[CANDIDATE],
        names,
        decorations,
        constants,
    )
    incumbent = _inspect_kernel(
        lines,
        entries[INCUMBENT],
        named_implementations[INCUMBENT],
        names,
        decorations,
        constants,
    )
    candidate_pairs = candidate["arithmetic"]["dependent_pairs"]
    incumbent_pairs = incumbent["arithmetic"]["dependent_pairs"]
    pairs = candidate_pairs + incumbent_pairs
    checks = {
        "entrypoints_present": True,
        "matching_nonempty_execution_modes": bool(candidate["execution_modes"]) and candidate["execution_modes"] == incumbent["execution_modes"],
        "contraction_off_execution_mode": all(
            "ContractionOff" in kernel["execution_modes"]
            for kernel in (candidate, incumbent)
        ),
        # The generic implementation stages both public route-map and weights
        # before its accumulation loop.  The sharded candidate has no route
        # map, so it retains only weight staging plus accumulation.
        "candidate_two_bound_10_loops": candidate["loop_bounds"]["10"] == 2,
        "incumbent_three_bound_10_loops": incumbent["loop_bounds"]["10"] == 3,
        "three_bound_8_loops_per_kernel": all(
            kernel["loop_bounds"]["8"] == 3 for kernel in (candidate, incumbent)
        ),
        "entry_wrapper_calls_named_implementation_once": all(
            kernel["wrapper_calls_named_implementation"] == 1
            for kernel in (candidate, incumbent)
        ),
        "one_bf16_to_fp32_call_per_kernel": all(kernel["conversions"]["bf16_to_fp32"] == 1 for kernel in (candidate, incumbent)),
        "one_fp32_to_bf16_call_per_kernel": all(kernel["conversions"]["fp32_to_bf16"] == 1 for kernel in (candidate, incumbent)),
        "exactly_one_fmul_and_one_fadd_per_implementation": all(
            kernel["arithmetic"]["fmul_count"] == 1
            and kernel["arithmetic"]["fadd_count"] == 1
            for kernel in (candidate, incumbent)
        ),
        "fmul_then_dependent_fadd": bool(candidate_pairs) and bool(incumbent_pairs),
        "same_accumulator_load_store_pointer": bool(candidate["arithmetic"]["accumulator_pointer_pairs"]) and bool(incumbent["arithmetic"]["accumulator_pointer_pairs"]),
        "all_mul_add_fast_math_decorations_present": bool(pairs)
        and all(
            pair["mul_fast_math"] is not None
            and pair["add_fast_math"] is not None
            for pair in pairs
        ),
        "identical_mul_add_fast_math": bool(candidate_pairs)
        and bool(incumbent_pairs)
        and all(pair["mul_fast_math"] == pair["add_fast_math"] for pair in pairs)
        and {pair["mul_fast_math"] for pair in candidate_pairs}
        == {pair["mul_fast_math"] for pair in incumbent_pairs},
        "no_fma_or_fused_opcode": candidate["arithmetic"]["no_fma_or_fused_opcode"] and incumbent["arithmetic"]["no_fma_or_fused_opcode"],
    }
    return {
        "candidate_symbol": CANDIDATE,
        "checks": checks,
        "incumbent_symbol": INCUMBENT,
        "kernels": {"candidate": candidate, "incumbent": incumbent},
        "passed": all(checks.values()),
    }


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise EvidenceError(f"not a regular input file: {path}")
    return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "spirv", type=Path, help="final-linked spirv-dis --raw-id assembly input"
    )
    parser.add_argument("--built-object", type=Path, help="built object/bitcode to bind")
    parser.add_argument("--save-temp-bitcode", type=Path, help="matching saved temporary bitcode")
    parser.add_argument("--output", type=Path, help="write JSON here instead of stdout")
    args = parser.parse_args(argv)
    if bool(args.built_object) != bool(args.save_temp_bitcode):
        parser.error("--built-object and --save-temp-bitcode must be supplied together")
    try:
        report = inspect_text(_read_text(args.spirv))
        report["spirv_sha256"] = _sha256(args.spirv)
        if args.built_object:
            built_sha = _sha256(args.built_object)
            saved_sha = _sha256(args.save_temp_bitcode)
            if built_sha != saved_sha:
                raise EvidenceError("built object and saved temporary bitcode SHA-256 differ")
            report["bound_bitcode_sha256"] = built_sha
    except (EvidenceError, OSError, UnicodeError) as error:
        parser.error(str(error))
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
