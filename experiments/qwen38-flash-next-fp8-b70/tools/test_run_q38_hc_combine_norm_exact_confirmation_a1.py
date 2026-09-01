#!/usr/bin/env python3
"""CPU-only launch-contract checks for the HC exact-confirmation runner."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess


RUNNER = Path(__file__).with_name("run-q38-hc-combine-norm-exact-confirmation-a1.sh")
RESULT = Path(
    "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/"
    "20260901-hc-combine-norm-exact-confirmation-a1"
)
CACHE = Path("/dev/shm/q38-hc-combine-norm-exact-confirmation-a1")


def test_runner_has_one_selector_and_continuous_owned_group_guard() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "setsid env -u ZE_AFFINITY_MASK" in source
    assert "ONEAPI_DEVICE_SELECTOR=level_zero:0" in source
    assert "ZE_AFFINITY_MASK=0" not in source
    assert 'while kill -0 "$leader"' in source
    assert "sleep 1" in source
    assert 'kill -TERM -- "-${owned_pgid}"' in source
    assert 'kill -KILL -- "-${owned_pgid}"' in source
    assert "trap 'finalize \"$?\"' EXIT" in source


def test_runner_has_no_clobber_final_receipt_and_manifest() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert '[[ ! -e "$result_dir" && ! -L "$result_dir" ]]' in source
    assert '[[ ! -e "$cache_root" && ! -L "$cache_root" ]]' in source
    assert '"${result_dir}/final-health.txt"' in source
    assert '"${result_dir}/SHA256SUMS"' in source
    assert "! -name SHA256SUMS" in source


def test_validate_only_has_no_result_or_cache_side_effect() -> None:
    assert not RESULT.exists() and not RESULT.is_symlink()
    assert not CACHE.exists() and not CACHE.is_symlink()
    environment = dict(os.environ)
    environment["Q38_HC_EXACT_VALIDATE_ONLY"] = "1"
    completed = subprocess.run(
        [str(RUNNER)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "PASS: HC exact-confirmation A1 static validation\n"
    assert not RESULT.exists() and not RESULT.is_symlink()
    assert not CACHE.exists() and not CACHE.is_symlink()
