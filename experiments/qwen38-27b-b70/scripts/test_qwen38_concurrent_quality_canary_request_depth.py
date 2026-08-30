#!/usr/bin/env python3
"""Unit checks for the fail-closed per-request speculative-depth canary path."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / "scripts" / "qwen38-text-quality-suite.py"


def load_module():
    spec = importlib.util.spec_from_file_location("qwen38_quality_for_test", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_request_extra_adds_only_speculative_depth() -> None:
    quality = load_module()
    response = {
        "choices": [{"message": {"content": "OK"}}],
        "usage": {"prompt_tokens_details": {"cached_tokens": 0}},
    }
    with mock.patch.object(quality, "post_json", return_value=response) as post:
        result = quality.chat_completion(
            "http://127.0.0.1:1",
            "model",
            [{"role": "user", "content": "Reply OK"}],
            8,
            1,
            seed=42,
            chat_template_kwargs={"enable_thinking": False},
            request_extra={"speculative.n_max": 0},
        )
    payload = post.call_args.args[1]
    assert payload["speculative.n_max"] == 0
    assert payload["temperature"] == 0
    assert result["normalized"] == "OK"


def test_request_extra_cannot_override_quality_contract() -> None:
    quality = load_module()
    try:
        quality.chat_completion(
            "http://127.0.0.1:1",
            "model",
            [{"role": "user", "content": "Reply OK"}],
            8,
            1,
            seed=42,
            chat_template_kwargs=None,
            request_extra={"temperature": 1},
        )
    except ValueError as exc:
        assert "temperature" in str(exc)
    else:
        raise AssertionError("quality-contract override was accepted")


if __name__ == "__main__":
    test_request_extra_adds_only_speculative_depth()
    test_request_extra_cannot_override_quality_contract()
    print("PASS")
