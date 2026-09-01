#!/usr/bin/env python3
"""A46 verifier for trace selectors consumed by EngineCore and workers."""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import re
import sys


BASE_PATH = pathlib.Path(__file__).with_name("verify-q38-a43-fullgraph-runtime.py")
EXPECTED_BASE_SHA256 = (
    "c7748c0316de5cddf3366c28bea419294d51cad92ad14bad893d4c8234099888"
)


def verify_base_hash(path: pathlib.Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise RuntimeError(
            f"A46 base verifier hash changed: expected {expected}, found {digest}"
        )


verify_base_hash(BASE_PATH, EXPECTED_BASE_SHA256)
SPEC = importlib.util.spec_from_file_location("q38_a43_runtime_verifier", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
ORIGINAL_NORMALIZED_ENVIRONMENT = BASE.ORIGINAL_NORMALIZED_ENVIRONMENT
EXPECTED_TRACE = ""
TRACE_FILES_VALIDATED = False
ENGINE_CORE_COMM = "VLLM::EngineCor"
WORKER_COMM = "VLLM::Worker_TP"
TRACE_NAME = re.compile(r"^dedicated_log_torch_trace_rank_(\d+)_.+\.log$")


def validate_rank_trace_files(root: pathlib.Path) -> list[pathlib.Path]:
    all_logs = sorted(root.glob("dedicated_log_torch_trace*.log"))
    logs = sorted(root.glob("dedicated_log_torch_trace_rank_*_*.log"))
    if all_logs != logs:
        unexpected = sorted(path.name for path in set(all_logs) - set(logs))
        raise BASE.BASE.CORE.VerificationError(
            f"unexpected non-rank trace logs: {unexpected}"
        )
    ranks: list[int] = []
    for log in logs:
        match = TRACE_NAME.fullmatch(log.name)
        if match is None:
            raise BASE.BASE.CORE.VerificationError(
                f"unexpected rank trace filename: {log.name}"
            )
        if log.stat().st_size <= 0:
            raise BASE.BASE.CORE.VerificationError(f"empty rank trace log: {log}")
        ranks.append(int(match.group(1)))
    if ranks != [0, 1, 2, 3]:
        raise BASE.BASE.CORE.VerificationError(
            f"expected exactly one trace log for ranks 0-3, found {ranks}"
        )
    return logs


def normalize_trace_identity(
    environment: dict[str, str],
    command: str,
    expected_trace: str,
    trace_files_validated: bool,
) -> dict[str, str]:
    environment = dict(environment)
    declared = environment.get("TORCH_TRACE")
    if command in {ENGINE_CORE_COMM, WORKER_COMM}:
        if declared is not None and declared != expected_trace:
            raise BASE.BASE.CORE.VerificationError(
                f"{command} declares unexpected Torch trace path: {declared}"
            )
        if declared is None:
            if not trace_files_validated:
                raise BASE.BASE.CORE.VerificationError(
                    f"{command} consumed selector without complete rank trace evidence"
                )
            environment["TORCH_TRACE"] = expected_trace
    return environment


def normalized_environment(pid: int) -> dict[str, str]:
    environment = ORIGINAL_NORMALIZED_ENVIRONMENT(pid)
    command = pathlib.Path(f"/proc/{pid}/comm").read_text(encoding="utf-8").strip()
    return normalize_trace_identity(
        environment, command, EXPECTED_TRACE, TRACE_FILES_VALIDATED
    )


def trace_argument(argv: list[str]) -> pathlib.Path:
    if argv.count("--torch-trace") != 1:
        raise RuntimeError("A46 requires exactly one --torch-trace argument")
    index = argv.index("--torch-trace")
    if index + 1 >= len(argv) or not argv[index + 1]:
        raise RuntimeError("A46 --torch-trace argument is empty")
    return pathlib.Path(argv[index + 1])


def main() -> None:
    global EXPECTED_TRACE, TRACE_FILES_VALIDATED
    trace = trace_argument(sys.argv[1:])
    validate_rank_trace_files(trace)
    EXPECTED_TRACE = str(trace)
    TRACE_FILES_VALIDATED = True
    # A43 installs its module-level normalizer into the A37 verifier at main
    # entry. Replace that module-level function so A43 installs this stricter
    # rank-evidence-aware implementation.
    BASE.normalized_environment = normalized_environment
    BASE.main()


if __name__ == "__main__":
    main()
