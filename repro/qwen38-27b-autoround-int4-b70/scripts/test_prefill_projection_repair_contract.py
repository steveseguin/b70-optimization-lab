#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
HOOK = REPO / (
    "repro/qwen38-27b-autoround-int4-b70/patches/"
    "qwen38-prefill-projection-repair-sitecustomize.py"
)
STRICT_RUNNER = REPO / (
    "experiments/qwen38-27b-b70/scripts/"
    "run-20260831-qwen38-prefill-projection-repair-strict-d54.sh"
)
D62 = REPO / (
    "experiments/qwen38-27b-b70/scripts/"
    "run-20260831-qwen38-prefill-projection-repair-tp2-mtp1-sync-d62.sh"
)


class PrefillProjectionRepairContractTest(unittest.TestCase):
    def test_production_hook_defaults_to_qualified_shape_without_barriers(self) -> None:
        source = HOOK.read_text()
        self.assertIn(
            'os.environ.get("VLLM_XPU_QWEN38_PREFILL_SMALL_PAD_TOKENS", "512")',
            source,
        )
        self.assertIn(
            'os.environ.get("VLLM_XPU_QWEN38_PREFILL_PROJECTION_SYNCHRONIZE", "0")',
            source,
        )
        self.assertIn(
            'os.environ.get("VLLM_XPU_QWEN38_PREFILL_PROJECTION_REPAIR") == "1"',
            source,
        )

    def test_strict_runner_keeps_realistic_cache_zero_quality_contract(self) -> None:
        source = STRICT_RUNNER.read_text()
        for required in (
            "realistic-suite-v1.json",
            "--max-tokens 512",
            "--metric-tokens 100",
            "--return-token-ids",
            "--require-natural-eos",
            "--no-enable-prefix-caching",
            'g["cached_tokens_all_zero"]',
            'len(p["rows"]) == 12',
            'len(set(p["prompt_sha256s"])) == 12',
            "current == expected",
            "c[\"pass_all\"]",
        ):
            self.assertIn(required, source)

    def test_d62_is_post_reboot_synchronized_mtp1_only(self) -> None:
        source = D62.read_text()
        for required in (
            "disallowed_boot_id=4136985e-4d03-45f1-8ecd-5b465b32e8d1",
            'VLLM_XPU_QWEN38_PREFILL_PROJECTION_SYNCHRONIZE=1',
            'VLLM_XPU_QWEN38_PREFILL_SMALL_PAD_TOKENS=512',
            'REQUIRE_DUMMY_SAMPLER_STAGE_SYNC=1',
            'qwen38-autoround-dummy-sampler-stage-sync-r1',
            'TRACE_IMAGE_ID=sha256:66bcfff69c6bf49500ce564132b303b26e26793c2c7c1b75a03c47681cab7261',
            'TENSOR_PARALLEL_SIZE=2',
            'MAX_NUM_BATCHED_TOKENS=256',
            '"num_speculative_tokens":1',
            "qwen38-prefill-projection-repair-tp2-strict-20260831-d59r/performance.json",
        ):
            self.assertIn(required, source)
        self.assertNotIn('"num_speculative_tokens":2', source)

    def test_strict_runner_fails_closed_on_stage_receipts(self) -> None:
        source = STRICT_RUNNER.read_text()
        for required in (
            'REQUIRE_DUMMY_SAMPLER_STAGE_SYNC',
            'QWEN38_DUMMY_SAMPLER_STAGE_SYNC pass=$stage',
            '"$tensor_parallel_size"',
            'dummy-sampler stage receipt missing or duplicated',
        ):
            self.assertIn(required, source)


if __name__ == "__main__":
    unittest.main()
