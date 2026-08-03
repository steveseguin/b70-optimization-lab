#!/usr/bin/env python3
"""CPU-only profile contracts for the Laguna paired-attention gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_laguna_paired_attn as gate


TOOLS = Path(__file__).resolve().parent
SCRIPT = TOOLS / "gate_laguna_paired_attn.py"


def test_short_profile_preserves_original_contexts_and_projection() -> None:
    profile = gate.profile_contract("short-record")

    assert profile["contexts"] == gate.SHORT_RECORD_CONTEXTS
    assert profile["attention_modes"] == (False, True)
    assert profile["full_layers"] == 12
    assert profile["sliding_layers"] == 36
    assert profile["minimum_projected_saving_ms"] == 1.5


def test_long_profile_is_full_attention_only_at_real_contexts() -> None:
    profile = gate.profile_contract("long-full")

    assert profile["contexts"] == (8192, 16384, 24576, 32640)
    assert profile["attention_modes"] == (False,)
    assert profile["full_layers"] == 12
    assert profile["sliding_layers"] == 0
    assert profile["minimum_projected_saving_ms"] == 0.25


def test_long_staircase_stays_within_32k_service_limit() -> None:
    checks = gate.host_contract_checks(gate.LONG_FULL_CONTEXTS)

    assert checks["paired_staircase"] is True
    assert checks["maximum_context"] + gate.Q_WIDTH <= 32768


def test_long_metadata_uses_later_row_sequence_lengths() -> None:
    context = gate.LONG_FULL_CONTEXTS[-1]
    _, paired, block_table = gate.metadata(
        context=context,
        blocks=512,
        paired=True,
        device=torch.device("cpu"),
    )

    assert paired.tolist() == [context + value for value in range(2, 13, 2)]
    assert tuple(block_table.shape) == (gate.PACKED_BATCH, 512)


def test_long_host_only_cli_never_requires_xpu(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "/home/steve/.venvs/deepseek-v4-xpu/bin/python",
            str(SCRIPT),
            "--rank",
            "0",
            "--profile",
            "long-full",
            "--host-only",
            "--out",
            str(tmp_path / "unused.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert '"profile": "long-full"' in result.stdout
    assert '"maximum_context": 32640' in result.stdout
