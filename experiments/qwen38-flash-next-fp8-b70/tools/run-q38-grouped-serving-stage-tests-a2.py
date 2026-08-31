#!/home/steve/.venvs/vllm-xpu/bin/python3
"""Run the exact vLLM focused suites after candidate-stage preload."""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import sys

import pytest


VLLM = Path("/home/steve/src/vllm-current-main")
PACKAGE = Path(
    "/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2/vllm_xpu_kernels"
)
SUITES = {
    "hc": (
        VLLM / "tests/models/qwen4_exp/test_amd_hc_grouped_up.py",
        5,
    ),
    "config": (
        VLLM / "tests/models/qwen4_exp/test_config.py",
        25,
    ),
}


class CountPlugin:
    """Require the exact frozen number of passed tests."""

    def __init__(self, expected: int) -> None:
        self.expected = expected
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when != "call":
            return
        if report.passed:
            self.passed += 1
        elif report.failed:
            self.failed += 1
        elif report.skipped:
            self.skipped += 1

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        if self.passed != self.expected or self.failed or self.skipped:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=tuple(SUITES), required=True)
    args = parser.parse_args()
    test_path, expected = SUITES[args.suite]
    if not PACKAGE.is_dir() or PACKAGE.is_symlink():
        raise RuntimeError(f"candidate package is unavailable: {PACKAGE}")
    if str(PACKAGE.parent) not in sys.path:
        sys.path.insert(0, str(PACKAGE.parent))
    importlib.invalidate_caches()
    package = importlib.import_module("vllm_xpu_kernels")
    native = importlib.import_module("vllm_xpu_kernels._xpu_C")
    if Path(package.__file__).resolve() != (PACKAGE / "__init__.py").resolve():
        raise RuntimeError("focused suite imported the wrong package")
    if Path(native.__file__).resolve() != (PACKAGE / "_xpu_C.abi3.so").resolve():
        raise RuntimeError("focused suite imported the wrong native extension")
    plugin = CountPlugin(expected)
    result = pytest.main(["-q", str(test_path)], plugins=[plugin])
    if result != pytest.ExitCode.OK:
        raise SystemExit(int(result))
    if (plugin.passed, plugin.failed, plugin.skipped) != (expected, 0, 0):
        raise RuntimeError(
            "focused suite count drifted: "
            f"passed={plugin.passed} failed={plugin.failed} "
            f"skipped={plugin.skipped} expected={expected}"
        )


if __name__ == "__main__":
    main()
