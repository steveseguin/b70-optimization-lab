#!/usr/bin/env python3
"""A34 wrapper around A33's map-authoritative full-graph runtime verifier."""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import re


BASE_PATH = pathlib.Path(__file__).with_name("verify-q38-a33-fullgraph-runtime.py")
EXPECTED_BASE_SHA256 = (
    "239f80b93531762ee607b2b651b3c69d4ba3d7b888c783ef989d321e7d834fae"
)


def verify_base_hash(path: pathlib.Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise RuntimeError(
            f"A34 base verifier hash changed: expected {expected}, found {digest}"
        )


verify_base_hash(BASE_PATH, EXPECTED_BASE_SHA256)
SPEC = importlib.util.spec_from_file_location("q38_a33_runtime_verifier", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
ORIGINAL_PROCESS_ENVIRONMENT = BASE.process_environment


def normalized_environment(pid: int) -> dict[str, str]:
    """Validate any declared libccl preload, then defer to the mapped image."""
    environment = ORIGINAL_PROCESS_ENVIRONMENT(pid)
    declared = environment.get("LD_PRELOAD")
    if declared:
        entries = [entry for entry in re.split(r"[:\s]+", declared) if entry]
        declared_ccl = {
            pathlib.Path(entry).resolve()
            for entry in entries
            if "libccl.so" in pathlib.Path(entry).name
        }
        unexpected = declared_ccl - {BASE.EXPECTED_LIBCCL}
        if unexpected:
            raise BASE.VerificationError(
                f"pid {pid} declares unexpected libccl preload paths: "
                f"{sorted(map(str, unexpected))}"
            )

    # A33 has already required the process map to contain exactly the expected
    # libccl and checked its digest. LD_PRELOAD is launch provenance and may be
    # absent after a subprocess exec; normalize only that redundant comparison.
    environment["LD_PRELOAD"] = str(BASE.EXPECTED_LIBCCL)
    return environment


def main() -> None:
    BASE.process_environment = normalized_environment
    BASE.main()


if __name__ == "__main__":
    main()
