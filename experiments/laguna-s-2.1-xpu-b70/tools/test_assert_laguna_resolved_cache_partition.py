#!/usr/bin/env python3
"""CPU-only tests for the resolved cache and partition evidence extractor."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assert_laguna_resolved_cache_partition as prover


ENGINE_LINE = (
    "INFO 08-03 00:00:00 [core.py:115] Initializing a V1 LLM engine (v0.1) with "
    "config: model='/int4', speculative_config=SpeculativeConfig(dflash, 11), "
    "dtype=torch.bfloat16, max_seq_len=32768, kv_cache_dtype=bfloat16, "
    "enable_prefix_caching=False, enable_chunked_prefill=True, "
    "compilation_config={'mode': 0}"
)
NON_DEFAULT_LINE = (
    "INFO 08-03 00:00:00 [api_utils.py:273] non-default args: "
    "{'model': '/int4', 'max_num_batched_tokens': 8192, 'max_num_seqs': 1, "
    "'enable_prefix_caching': False, 'block_size': 64}"
)
CHUNKED_LINE = (
    "INFO 08-03 00:00:00 [scheduler.py:257] Chunked prefill is enabled with "
    "max_num_batched_tokens=8192."
)
SCHEDULED_LINE = (
    "WARNING 08-03 00:00:00 [vllm.py:1697] max_num_scheduled_tokens is set to "
    "8182 based on the speculative decoding settings. This may lead to "
    "suboptimal performance."
)


def log(*, extra: list[str] | None = None, drop: str | None = None) -> str:
    lines = [ENGINE_LINE, NON_DEFAULT_LINE, CHUNKED_LINE, SCHEDULED_LINE]
    if drop is not None:
        lines = [line for line in lines if drop not in line]
    return "\n".join(lines + (extra or [])) + "\n"


def analyze(text: str) -> dict:
    return prover.analyze(
        text, expected_batched_tokens=8192, expected_scheduled_tokens=8182
    )


def test_incumbent_log_proves_every_resolved_setting() -> None:
    result = analyze(log())

    assert result["status"] == "PASS_RESOLVED_SETTINGS_PROVED"
    assert result["resolved"] == {
        "enable_prefix_caching": False,
        "max_num_partial_prefills": 1,
        "max_num_batched_tokens": 8192,
        "max_num_scheduled_tokens": 8182,
    }


def test_resolved_prefix_caching_on_fails_closed() -> None:
    with pytest.raises(ValueError, match="enable_prefix_caching is True"):
        analyze(
            log().replace("enable_prefix_caching=False", "enable_prefix_caching=True")
        )


def test_concurrent_partial_prefills_notice_fails_closed() -> None:
    notice = (
        "INFO 08-03 00:00:00 [scheduler.py:265] Concurrent partial prefills "
        "enabled with max_num_partial_prefills=4, max_long_partial_prefills=1, "
        "long_prefill_token_threshold=1310"
    )
    with pytest.raises(ValueError, match="max_num_partial_prefills is above one"):
        analyze(log(extra=[notice]))


def test_command_line_partial_prefill_override_fails_closed() -> None:
    overridden = log().replace(
        "'block_size': 64", "'block_size': 64, 'max_num_partial_prefills': 2"
    )
    with pytest.raises(ValueError, match="overridden on the command line"):
        analyze(overridden)


@pytest.mark.parametrize(
    ("drop", "message"),
    [
        ("Initializing a V1 LLM engine", "no resolved engine configuration line"),
        ("non-default args", "no non-default args record"),
        ("Chunked prefill is enabled", "resolved batched-token budget was never"),
        ("max_num_scheduled_tokens is set to", "budget was never logged"),
    ],
)
def test_missing_evidence_fails_closed(drop: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        analyze(log(drop=drop))


def test_wrong_derived_budget_fails_closed() -> None:
    with pytest.raises(ValueError, match="derived max_num_scheduled_tokens is 8192"):
        analyze(log().replace("set to 8182 based", "set to 8192 based"))


def test_wrong_batched_budget_fails_closed() -> None:
    with pytest.raises(ValueError, match="resolved max_num_batched_tokens is 8202"):
        analyze(
            log().replace(
                "max_num_batched_tokens=8192.", "max_num_batched_tokens=8202."
            )
        )


def test_conflicting_worker_values_fail_closed() -> None:
    conflicting = log() + ENGINE_LINE.replace(
        "enable_prefix_caching=False", "enable_prefix_caching=True"
    )
    with pytest.raises(ValueError, match="conflicting values"):
        analyze(conflicting)


def test_repeated_consistent_worker_lines_are_accepted() -> None:
    # Four tensor-parallel workers each log the resolved configuration.
    assert (
        analyze(log() + "\n".join([ENGINE_LINE] * 3))["resolved"][
            "max_num_partial_prefills"
        ]
        == 1
    )
