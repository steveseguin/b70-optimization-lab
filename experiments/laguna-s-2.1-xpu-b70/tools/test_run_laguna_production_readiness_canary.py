#!/usr/bin/env python3
"""CPU-only argument and separation tests for production readiness."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
SCRIPT = TOOLS / "run_laguna_production_readiness_canary.sh"


def run_validate(
    *, armed: bool, require_wide_prefill: str = "0"
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["LAGUNA_PRODUCTION_READINESS_VALIDATE_ONLY"] = "1"
    environment["LAGUNA_PRODUCTION_REQUIRE_WIDE_PREFILL"] = require_wide_prefill
    if armed:
        environment["LAGUNA_PRODUCTION_READINESS_CANARY"] = "1"
    else:
        environment.pop("LAGUNA_PRODUCTION_READINESS_CANARY", None)
    return subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "/absolute/run",
            "/absolute/server.log",
            "/absolute/libgrouped_gemm_xe_2.so",
            "0" * 64,
            "/absolute/teacher.json",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_production_canary_is_default_off() -> None:
    result = run_validate(armed=False)

    assert result.returncode == 2
    assert "LAGUNA_PRODUCTION_READINESS_CANARY=1 is required" in result.stderr


def test_validate_only_stops_before_endpoint_or_artifact_access() -> None:
    result = run_validate(armed=True)

    assert result.returncode == 0
    assert result.stdout == "argument_validation=PASS\n"


def test_validate_only_rejects_malformed_wide_prefill_requirement() -> None:
    result = run_validate(armed=True, require_wide_prefill="true")

    assert result.returncode == 2
    assert "LAGUNA_PRODUCTION_REQUIRE_WIDE_PREFILL must be 0 or 1" in result.stderr


def test_canary_stays_outside_cold_launchers() -> None:
    cold_launchers = (
        "run_laguna_replemb_measurement_leg.sh",
        "run_laguna_worker_proof_measurement_leg.sh",
        "run_laguna_mwide_measurement_leg.sh",
        "run_laguna_long_context_baseline.sh",
    )
    for name in cold_launchers:
        text = (TOOLS / name).read_text(encoding="utf-8")
        assert SCRIPT.name not in text
        assert "LAGUNA_PRODUCTION_READINESS_CANARY" not in text


def test_canary_requires_single_exact_non_scored_request() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "--require-exact-prefill" in text
    assert "--require-wide-prefill" in text
    assert '"wide_prefill_worker_attested": %s' in text
    assert "--request-count 1" in text
    assert "--max-tokens 400" in text
    assert '"scored_measurement": false' in text
    assert '"prefix_caching": false' in text
