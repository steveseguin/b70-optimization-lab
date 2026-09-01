#!/usr/bin/env python3
"""A43 trace verifier allowing the EngineCore's consumed trace selector."""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys


BASE_PATH = pathlib.Path(__file__).with_name("verify-q38-a37-fullgraph-runtime.py")
EXPECTED_BASE_SHA256 = (
    "be7aef4a7d0c533ae4dde7eef4d89f19af9c7d807782cf50a12e08367490b92a"
)


def verify_base_hash(path: pathlib.Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise RuntimeError(
            f"A43 base verifier hash changed: expected {expected}, found {digest}"
        )


verify_base_hash(BASE_PATH, EXPECTED_BASE_SHA256)
SPEC = importlib.util.spec_from_file_location("q38_a37_runtime_verifier", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
ORIGINAL_NORMALIZED_ENVIRONMENT = BASE.BASE.normalized_environment
EXPECTED_TRACE = ""
# Linux TASK_COMM_LEN includes the trailing NUL, so /proc/<pid>/comm exposes
# the first 15 characters of the EngineCore display name.
ENGINE_CORE_COMM = "VLLM::EngineCor"


def normalize_trace_identity(
    environment: dict[str, str], command: str, expected_trace: str
) -> dict[str, str]:
    environment = dict(environment)
    declared = environment.get("TORCH_TRACE")
    if command == ENGINE_CORE_COMM:
        if declared is not None and declared != expected_trace:
            raise BASE.CORE.VerificationError(
                f"EngineCore declares unexpected Torch trace path: {declared}"
            )
        # Torch structured logging consumes the selector in EngineCore before
        # worker startup. Four rank-specific logs under the exact requested
        # directory remain authoritative; workers must still retain the value.
        environment["TORCH_TRACE"] = expected_trace
    return environment


def normalized_environment(pid: int) -> dict[str, str]:
    environment = ORIGINAL_NORMALIZED_ENVIRONMENT(pid)
    command = pathlib.Path(f"/proc/{pid}/comm").read_text(encoding="utf-8").strip()
    return normalize_trace_identity(environment, command, EXPECTED_TRACE)


def trace_argument(argv: list[str]) -> str:
    if argv.count("--torch-trace") != 1:
        raise RuntimeError("A43 requires exactly one --torch-trace argument")
    index = argv.index("--torch-trace")
    if index + 1 >= len(argv) or not argv[index + 1]:
        raise RuntimeError("A43 --torch-trace argument is empty")
    return argv[index + 1]


def main() -> None:
    global EXPECTED_TRACE
    EXPECTED_TRACE = trace_argument(sys.argv[1:])
    BASE.BASE.normalized_environment = normalized_environment
    BASE.main()


if __name__ == "__main__":
    main()
