from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build-20260825-qwen38-tp1-context-sentinel-suite.py"
)
SPEC = importlib.util.spec_from_file_location("qwen38_context_suite", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeBatchTokenizer:
    def __init__(self) -> None:
        self.maximum_count = 0

    def apply_chat_template(self, messages, **_kwargs):
        prompt = messages[0]["content"]
        count = 78 + prompt.count(MODULE.FILLER) * 23
        self.maximum_count = max(self.maximum_count, count)
        return {"input_ids": [0] * count, "attention_mask": [1] * count}


class FakeTensorIds:
    shape = (1, 123)


class FakeTensorTokenizer:
    def apply_chat_template(self, _messages, **_kwargs):
        return FakeTensorIds()


class ContextSuiteTests(unittest.TestCase):
    def test_batch_encoding_counts_input_ids_not_mapping_keys(self) -> None:
        tokenizer = FakeBatchTokenizer()
        self.assertEqual(MODULE.token_count(tokenizer, "plain prompt"), 78)

    def test_tensor_like_result_uses_last_dimension(self) -> None:
        self.assertEqual(MODULE.token_count(FakeTensorTokenizer(), "prompt"), 123)

    def test_32k_search_is_bounded_and_within_contract(self) -> None:
        tokenizer = FakeBatchTokenizer()
        prompt, actual, marker = MODULE.make_prompt(
            tokenizer, 32000, "middle", 0.5
        )
        self.assertLessEqual(abs(actual - 32000), 16)
        self.assertEqual(prompt.count(marker), 1)
        self.assertLess(tokenizer.maximum_count, 34000)


if __name__ == "__main__":
    unittest.main()
