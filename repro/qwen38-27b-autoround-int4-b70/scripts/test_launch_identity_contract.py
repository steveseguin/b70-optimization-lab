#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
RUNNER = REPO / (
    "experiments/qwen36-27b-autoround-int4-b70/scripts/"
    "run-vllm-candidate.sh"
)
ARM = REPO / (
    "experiments/qwen36-27b-autoround-int4-b70/validation-20260815/"
    "run-arm.sh"
)


class LaunchIdentityContractTest(unittest.TestCase):
    def test_arm_propagates_exact_model_gate_inputs(self) -> None:
        source = ARM.read_text()
        self.assertIn('export MODEL_MANIFEST="$model_manifest"', source)
        self.assertIn('export VERIFY_MODEL_SCRIPT="${VALIDATION_MODEL_VERIFY_SCRIPT:', source)

    def test_tp1_control_keeps_strict_runner_without_tp2_wrapper(self) -> None:
        source = ARM.read_text()
        self.assertIn(
            'tensor_parallel_size=${VALIDATION_TENSOR_PARALLEL_SIZE:-2}',
            source,
        )
        self.assertIn('export TENSOR_PARALLEL_SIZE="$tensor_parallel_size"', source)
        tp1 = source.index('if [[ "$tensor_parallel_size" == "1" ]]; then', 1000)
        direct = source.index('candidate="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh"', tp1)
        stage = source.index('export PYTHONPATH="$STAGE${PYTHONPATH:+:$PYTHONPATH}"', direct)
        arm_env = source.index("printf 'mode=%s\\ngpu_pair=%s\\ntensor_parallel_size=%s", direct)
        self.assertLess(tp1, direct)
        self.assertLess(direct, stage)
        self.assertLess(stage, arm_env)

    def test_runner_is_fail_closed_and_verifies_immediately_before_launch(self) -> None:
        source = RUNNER.read_text()
        self.assertIn("A readable MODEL_MANIFEST is required", source)
        self.assertIn("A readable, explicit VERIFY_MODEL_SCRIPT is required", source)
        self.assertNotIn("VERIFY_MODEL_DIRECT", source)
        verify = source.index('if ! "$PYTHON" "$verify_script"')
        identity = source.index("write_identity\n", verify)
        launch = source.index('if ! supp_start_group', identity)
        self.assertLess(verify, identity)
        self.assertLess(identity, launch)

    def test_effective_identity_records_previously_missing_axes(self) -> None:
        source = RUNNER.read_text()
        for field in (
            "model_manifest_sha256=",
            "model_verification_policy=direct-and-ordinary-fail-closed",
            "verify_model_script_sha256=",
            "model_verify_json_sha256=",
            "model_verify_read_modes=",
            "xpu_python_package_path=",
            "xpu_native_extension_path=",
            "xpu_native_extension_sha256=",
            "xpu_core_extension_path=",
            "xpu_core_extension_sha256=",
            "xpu_moe_extension_path=",
            "xpu_moe_extension_sha256=",
            "xpu_fa_extension_path=",
            "xpu_fa_extension_sha256=",
            "require_xpu_modules_under_stage=",
            "draft_lm_head_int4_fallback_margin=",
            "gdn_spec_persistent_scratch=",
            "onednn_int4_determinism_pad=",
        ):
            self.assertIn(field, source)

    def test_arm_forwards_determinism_pad_explicitly(self) -> None:
        source = ARM.read_text()
        self.assertIn(
            'export VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD='
            '"$VALIDATION_ONEDNN_INT4_DETERMINISM_PAD"',
            source,
        )

    def test_runner_can_fail_closed_on_stage_module_resolution(self) -> None:
        source = RUNNER.read_text()
        self.assertIn('VALIDATION_REQUIRE_XPU_MODULES_UNDER_STAGE', source)
        self.assertIn('resolved XPU module escapes required stage', source)


if __name__ == "__main__":
    unittest.main()
