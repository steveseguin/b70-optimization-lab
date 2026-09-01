#!/usr/bin/env python3
"""A48 verifier for the exact twoshots collective selector."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import sys


BASE_PATH = pathlib.Path(__file__).with_name("verify-q38-a46-fullgraph-runtime.py")
EXPECTED_BASE_SHA256 = (
    "724528810e5316e1a32c013ecc6a2d0419f7063a7cedf6c5cb7d05d4ea672310"
)
EXPECTED_ALGORITHM = "twoshots"
ALGORITHM_LOG_RECEIPT = (
    "value of CCL_SYCL_ALLREDUCE_LL changed to be twoshots (default:ring)"
)


def verify_base_hash(path: pathlib.Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise RuntimeError(
            f"A48 base verifier hash changed: expected {expected}, found {digest}"
        )


verify_base_hash(BASE_PATH, EXPECTED_BASE_SHA256)
SPEC = importlib.util.spec_from_file_location("q38_a46_runtime_verifier", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
ORIGINAL_NORMALIZED_ENVIRONMENT = BASE.normalized_environment


def normalize_algorithm_identity(environment: dict[str, str]) -> dict[str, str]:
    environment = dict(environment)
    declared = environment.get("CCL_SYCL_ALLREDUCE_LL")
    if declared is not None and declared != EXPECTED_ALGORITHM:
        raise BASE.BASE.BASE.CORE.VerificationError(
            f"process declares unexpected CCL_SYCL_ALLREDUCE_LL: {declared}"
        )
    environment["CCL_SYCL_ALLREDUCE_LL"] = EXPECTED_ALGORITHM
    return environment


def normalized_environment(pid: int) -> dict[str, str]:
    return normalize_algorithm_identity(ORIGINAL_NORMALIZED_ENVIRONMENT(pid))


def argument_path(argv: list[str], name: str) -> pathlib.Path:
    if argv.count(name) != 1:
        raise RuntimeError(f"A48 requires exactly one {name} argument")
    index = argv.index(name)
    if index + 1 >= len(argv) or not argv[index + 1]:
        raise RuntimeError(f"A48 {name} argument is empty")
    return pathlib.Path(argv[index + 1])


def validate_algorithm_log(path: pathlib.Path) -> None:
    log = path.read_text(encoding="utf-8", errors="replace")
    if ALGORITHM_LOG_RECEIPT not in log:
        raise BASE.BASE.BASE.CORE.VerificationError(
            "server log lacks the exact twoshots selector receipt"
        )
    if "|CCL_ERROR|" in log:
        raise BASE.BASE.BASE.CORE.VerificationError(
            "server log contains a oneCCL error"
        )


def annotate_output(path: pathlib.Path) -> None:
    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("status") != "passed":
        raise BASE.BASE.BASE.CORE.VerificationError(
            "base runtime verifier did not pass"
        )
    result["ccl_sycl_allreduce_ll"] = EXPECTED_ALGORITHM
    temporary = path.with_name(path.name + f".tmp.{os.getpid()}")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> None:
    server_log = argument_path(sys.argv[1:], "--server-log")
    output = argument_path(sys.argv[1:], "--output")
    validate_algorithm_log(server_log)
    BASE.normalized_environment = normalized_environment
    BASE.main()
    annotate_output(output)


if __name__ == "__main__":
    main()
