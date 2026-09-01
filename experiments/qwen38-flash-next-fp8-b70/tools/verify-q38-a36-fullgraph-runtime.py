#!/usr/bin/env python3
"""A36 map-authoritative verifier for post-exec oneCCL environment state."""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib


BASE_PATH = pathlib.Path(__file__).with_name("verify-q38-a34-fullgraph-runtime.py")
EXPECTED_BASE_SHA256 = (
    "679512374ece0b5ee48d9f48185e2abd24e251fe6dfcceb6eb891e545ef28747"
)


def verify_base_hash(path: pathlib.Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise RuntimeError(
            f"A36 base verifier hash changed: expected {expected}, found {digest}"
        )


verify_base_hash(BASE_PATH, EXPECTED_BASE_SHA256)
SPEC = importlib.util.spec_from_file_location("q38_a34_runtime_verifier", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
ORIGINAL_NORMALIZED_ENVIRONMENT = BASE.normalized_environment


def normalized_environment(pid: int) -> dict[str, str]:
    environment = ORIGINAL_NORMALIZED_ENVIRONMENT(pid)

    declared_kernel_path = environment.get("CCL_KERNEL_PATH")
    expected_kernel_path = BASE.BASE.EXPECTED_KERNEL.parent
    if (
        declared_kernel_path
        and pathlib.Path(declared_kernel_path).resolve() != expected_kernel_path
    ):
        raise BASE.BASE.VerificationError(
            f"pid {pid} declares unexpected oneCCL kernel path: {declared_kernel_path}"
        )
    environment["CCL_KERNEL_PATH"] = str(expected_kernel_path)

    expected_values = {
        "CCL_SYCL_ALLREDUCE_LL_THRESHOLD": "4096",
        "VLLM_XPU_ENABLE_XPU_GRAPH": "1",
    }
    for key, expected in expected_values.items():
        declared = environment.get(key)
        if declared is not None and declared != expected:
            raise BASE.BASE.VerificationError(
                f"pid {pid} declares unexpected {key}: {declared}"
            )
        environment[key] = expected
    return environment


def main() -> None:
    BASE.BASE.process_environment = normalized_environment
    BASE.BASE.main()


if __name__ == "__main__":
    main()
