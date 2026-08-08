#!/usr/bin/env python3
"""Host-only guards for the dynamic long-context cutoff runner."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
RUNNER = TOOLS / "run_laguna_long_context_baseline.sh"
SUITE = TOOLS.parent / "long-context-suite-v1.json"


def test_positive_cutoff_rejects_missing_oracle_before_preflight(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "LAGUNA_DFLASH_CONTEXT_CUTOFF": "4160",
            "LAGUNA_LONG_CANDIDATE_PROFILE": "q12",
            "LAGUNA_REQUIRE_ORACLE": "0",
        }
    )

    result = subprocess.run(
        [str(RUNNER), "candidate", str(tmp_path / "run")],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "context cutoff requires an exact oracle" in result.stderr


def test_preregistered_correctness_case_crosses_within_one_request():
    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    case = next(
        case
        for case in suite["cases"]
        if case["id"] == "laguna-lc-04096-middle"
    )

    prompt = int(case["target_prompt_tokens"])
    cutoff = 4160
    assert prompt < cutoff <= prompt + int(suite["max_output_tokens"])


def test_runner_requires_exact_status_and_committed_boundary():
    source = RUNNER.read_text(encoding="utf-8")

    assert "PASS_ORACLE_EXACT" in source
    assert "committed_context=" in source
    assert "value[2] + 0 < cutoff || value[2] + 0 > cutoff + 11" in source
    assert "b0e41df6b7e5b798749c97221dbae4c41e345a41785e9c6793d5f76b5b9b11b8" in source
