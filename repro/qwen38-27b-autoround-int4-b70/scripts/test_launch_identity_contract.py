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
DRIVER = REPO / (
    "experiments/qwen38-27b-b70/scripts/"
    "run-20260820-detpad-tp2-full25.sh"
)
RECURRENCE_DRIVER = REPO / (
    "experiments/qwen38-27b-b70/scripts/"
    "run-20260820-detpad-tp2-recurrence.sh"
)
SYNC_DRIVER = REPO / (
    "experiments/qwen38-27b-b70/scripts/"
    "run-20260820-detpad-tp2-postforward-sync.sh"
)
MICROSCOPE_DRIVER = REPO / (
    "experiments/qwen38-27b-b70/scripts/"
    "run-20260820-detpad-tp2-replay-microscope.sh"
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
            "graph_stage_manifest_sha256=",
            "compile_cache_input_manifest_sha256=",
            "draft_lm_head_int4_fallback_margin=",
            "gdn_spec_persistent_scratch=",
            "onednn_int4_determinism_pad=",
            "xpu_graph=",
            "vllm_xpu_enable_xpu_graph=",
            "vllm_xpu_force_graph_with_comm=",
            "vllm_xpu_graph_noop_comm_capture=",
            "fa2_force_chunk_decode=",
            "lm_head_int8_scope=",
            "quality_baseline_json_sha256=",
            "validation_suite_sha256=",
            "sealed_gate_checker_sha256=",
            "run_arm_script_sha256=",
            "campaign_driver_sha256=",
            "validation_input_env_sha256=",
            "parity_peer_bench_sha256=",
            "target_token_bench_sha256=",
            "expected_parity_peer_bench_sha256=",
            "expected_target_token_bench_sha256=",
            "validation_mode=",
            "sync_after_model_forward=",
            "expected_sync_after_model_forward=",
            "replay_microscope_required=",
            "replay_microscope_file=",
            "replay_microscope_req_regex=",
            "replay_microscope_min_tokens_no_spec=",
            "replay_microscope_max_tokens_no_spec=",
            "expected_parity_peer_checksum_manifest_sha256=",
            "parity_peer_bench_snapshot_sha256=",
            "target_token_bench_snapshot_sha256=",
        ):
            self.assertIn(field, source)

    def test_arm_forwards_determinism_pad_explicitly(self) -> None:
        source = ARM.read_text()
        self.assertIn(
            'export VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD='
            '"$VALIDATION_ONEDNN_INT4_DETERMINISM_PAD"',
            source,
        )

    def test_sealed_arm_binds_sync_after_model_forward(self) -> None:
        source = ARM.read_text()
        self.assertIn("VALIDATION_EXPECT_SYNC_AFTER_MODEL_FORWARD", source)
        self.assertIn("VALIDATION_SYNC_AFTER_MODEL_FORWARD", source)
        self.assertIn(
            "sealed TP2 sync-after-forward identity must be explicit and self-consistent",
            source,
        )
        checker = (
            REPO
            / "repro/qwen38-27b-autoround-int4-b70/scripts/check-tp2-sealed-gates.py"
        ).read_text()
        self.assertIn("--expected-sync-after-model-forward", checker)
        self.assertIn(
            "--expected-parity-peer-checksum-manifest-sha256", checker
        )
        self.assertIn('"sync_after_model_forward": str(', checker)

    def test_runner_can_fail_closed_on_stage_module_resolution(self) -> None:
        source = RUNNER.read_text()
        self.assertIn('VALIDATION_REQUIRE_XPU_MODULES_UNDER_STAGE', source)
        self.assertIn('resolved XPU module escapes required stage', source)

    def test_sealed_tp2_gate_inputs_are_explicit_and_mandatory(self) -> None:
        source = ARM.read_text()
        for variable in (
            "VALIDATION_REQUIRE_TP2_SEALED_GATES",
            "VALIDATION_COMPILE_CACHE_MANIFEST",
            "VALIDATION_EXPECT_ONEDNN_INT4_DETERMINISM_PAD_MARKERS",
            "VALIDATION_EXPECT_COMPILE_CACHE_DIRECT_LOADS",
            "VALIDATION_EXPECT_AOT_DIRECT_LOADS",
            "VALIDATION_EXPECT_COMPILE_CACHE_NAMESPACE",
            "VALIDATION_EXPECT_COMPILE_CACHE_OUTER_ROLES",
            "VALIDATION_EXPECT_AOT_CACHE_KEYS",
            "VALIDATION_EXPECT_SUITE_SHA256",
            "VALIDATION_EXPECT_QUALITY_BASELINE_SHA256",
            "VALIDATION_REQUIRE_COMPILE_CACHE_UNCHANGED",
            "VALIDATION_REQUIRE_NO_COMPILE_CACHE_WRITES",
            "VALIDATION_CAMPAIGN_DRIVER",
            "VALIDATION_CAMPAIGN_DRIVER_SHA256",
            "VALIDATION_EXPECT_MODEL_MANIFEST_SHA256",
            "VALIDATION_EXPECT_CACHE_MANIFEST_SHA256",
            "VALIDATION_EXPECT_NATIVE_SHA256",
            "VALIDATION_EXPECT_REPO_HEAD",
        ):
            self.assertIn(variable, source)
        self.assertIn(
            "sealed TP2 gates require VALIDATION_ONEDNN_INT4_DETERMINISM_PAD=1",
            source,
        )
        self.assertIn(
            "sealed Qwen3.8 TP2 gates require explicit MTP5 and recurrent-serial-exact=0",
            source,
        )

    def test_post_run_gate_order_precedes_authoritative_exit_code(self) -> None:
        source = ARM.read_text()
        candidate = source.index('"$candidate" \\\n  > "$arm_root/runner.stdout.log"')
        manifest = source.index('compile-cache-output-manifest.json', candidate)
        qualifier = source.index('qualify_realistic_window_metrics.py', manifest)
        postflight = source.index('compile-cache-postflight.json', qualifier)
        checker_call = '"$RUN_DIR/check-tp2-sealed-gates.py.snapshot"'
        sealed = source.index(checker_call, postflight)
        parity = source.index(checker_call, sealed + len(checker_call))
        exit_code = source.index(
            'printf \'%s\\n\' "$runner_rc" > "$arm_root/runner.exit-code"',
            parity,
        )
        checksums = source.index('SHA256SUMS.pre-manifest', exit_code)
        self.assertLess(candidate, manifest)
        self.assertLess(manifest, qualifier)
        self.assertLess(qualifier, postflight)
        self.assertLess(postflight, sealed)
        self.assertLess(sealed, parity)
        self.assertLess(parity, exit_code)
        self.assertLess(exit_code, checksums)

    def test_run_arm_and_checker_are_snapshotted_and_hashed(self) -> None:
        source = ARM.read_text()
        self.assertIn('run-arm.sh.snapshot', source)
        self.assertIn('check-tp2-sealed-gates.py.snapshot', source)
        self.assertIn('VALIDATION_RUN_ARM_SCRIPT_SHA256', source)
        self.assertIn('VALIDATION_SEALED_GATE_CHECKER_SHA256', source)

    def test_sealed_mode_rejects_unknown_validation_axes_and_snapshots_inputs(self) -> None:
        source = ARM.read_text()
        self.assertIn("unexpected VALIDATION_* input in sealed mode", source)
        self.assertIn("sealed_validation_allowlist", source)
        self.assertNotIn("env | LC_ALL=C sort | sed -n '/^VALIDATION_/p'", source)
        self.assertIn("parity-peer-bench.input.json", source)
        self.assertIn("target-token-bench.input.json", source)

    def test_campaign_driver_is_clean_exact_and_gates_b_on_a(self) -> None:
        source = DRIVER.read_text()
        for required in (
            "exec env -i",
            "VALIDATION_PYTHONHASHSEED=0",
            "VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0",
            "VALIDATION_ONEDNN_INT4_DETERMINISM_PAD=1",
            "VALIDATION_EXPECT_REPO_HEAD",
            "VALIDATION_EXPECT_CACHE_MANIFEST_SHA256",
            "VALIDATION_REQUIRE_TP2_SEALED_GATES=1",
            "sealed_checker",
            "recorded_checker_sha",
            '"$sealed_checker" arm',
            "--require-quality-pass",
            "VALIDATION_EXPECT_TARGET_TOKEN_BENCH_SHA256",
            "SHA256SUMS.pre-manifest",
            ".benchmark.sha256",
        ):
            self.assertIn(required, source)
        gate_a = source.index("arm A no longer passes the current sealed campaign contract")
        launch = source.index("exec env -i", gate_a)
        self.assertLess(gate_a, launch)

    def test_recurrence_driver_binds_sane_peer_and_corrupt_reference(self) -> None:
        source = RECURRENCE_DRIVER.read_text()
        for required in (
            "exec env -i",
            "VALIDATION_PYTHONHASHSEED=0",
            "VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0",
            "VALIDATION_ONEDNN_INT4_DETERMINISM_PAD=1",
            "VALIDATION_REQUIRE_TP2_SEALED_GATES=1",
            "VALIDATION_REQUIRE_COMPILE_CACHE_UNCHANGED=1",
            "VALIDATION_REQUIRE_NO_COMPILE_CACHE_WRITES=1",
            "VALIDATION_PARITY_PEER_BENCH=\"$peer_bench\"",
            "VALIDATION_TARGET_TOKEN_BENCH=\"$reference_bench\"",
            "VALIDATION_REQUIRE_TARGET_TOKEN_PARITY=0",
            "b2_bench_sha=96933a821186",
            "a2_bench_sha=865ab22ef080",
            "a2_checksum_manifest_sha=a9a162c959256",
            "b2_checksum_manifest_sha=e7726d02dd467",
            "run_arm_sha=e89352d7d71a",
            "checker_sha=23ad35011198",
            "common_runner_sha=b6ad5add4d19",
            "top_wrapper_sha=991e21c1ddea",
            "serve_runner_sha=f1d1503a4a16",
            "SHA256SUMS.pre-manifest",
        ):
            self.assertIn(required, source)
        self.assertLess(
            source.index("prior A2/B2 runner status no longer matches 0/14"),
            source.index("exec env -i"),
        )

    def test_postforward_sync_driver_retains_full_history_and_gates_s2(self) -> None:
        source = SYNC_DRIVER.read_text()
        for required in (
            "env -i",
            "C1 no longer proves the preregistered active recurrence",
            '.schema == "qwen38-token-array-parity-v1"',
            "VALIDATION_SYNC_AFTER_MODEL_FORWARD=1",
            "VALIDATION_EXPECT_SYNC_AFTER_MODEL_FORWARD=1",
            "S1 prompt 24 is not the sane B2 token family; S2 is forbidden",
            "VALIDATION_PARITY_PEER_BENCH=$peer_bench",
            "VALIDATION_TARGET_TOKEN_BENCH=$b2/data/bench.json",
            "s1_checksum_manifest_expected",
            "VALIDATION_EXPECT_PARITY_PEER_CHECKSUM_MANIFEST_SHA256",
            "s1-checksum-manifest",
        ):
            self.assertIn(required, source)

    def test_replay_microscope_is_bounded_recorded_and_fail_closed(self) -> None:
        arm = ARM.read_text()
        runner = RUNNER.read_text()
        checker = (
            REPO
            / "repro/qwen38-27b-autoround-int4-b70/scripts/check-tp2-sealed-gates.py"
        ).read_text()
        driver = MICROSCOPE_DRIVER.read_text()
        for required in (
            "VALIDATION_REQUIRE_REPLAY_MICROSCOPE",
            "VALIDATION_REPLAY_MICROSCOPE_FILE",
            "VALIDATION_REPLAY_MICROSCOPE_MAX_LINES",
            "VALIDATION_REPLAY_MICROSCOPE_REQ_REGEX",
            "VALIDATION_REPLAY_MICROSCOPE_MIN_TOKENS_NO_SPEC",
            "VALIDATION_REPLAY_MICROSCOPE_MAX_TOKENS_NO_SPEC",
            "sealed replay microscope identity does not match",
            "--require-replay-microscope",
        ):
            self.assertIn(required, arm)
        for required in (
            "replay_microscope_required=",
            "replay_microscope_file=",
            "replay_microscope_max_lines=",
            "replay_microscope_rank=",
            "replay_microscope_req_regex=",
            "replay_microscope_tensor_limit=",
            "replay_microscope_topk=",
        ):
            self.assertIn(required, runner)
        for required in (
            "REPLAY_MICROSCOPE_STAGES",
            "validate_replay_microscope",
            "--require-replay-microscope",
            "sampled_token_matches_bench",
        ):
            self.assertIn(required, checker)
        for required in (
            "env -i",
            'if [[ "$action" == "m1" ]]',
            "M1 is permanently closed; preserve the original arm and do not retry",
            "VALIDATION_SYNC_AFTER_MODEL_FORWARD=0",
            "VALIDATION_EXPECT_SYNC_AFTER_MODEL_FORWARD=0",
            "VALIDATION_REQUIRE_REPLAY_MICROSCOPE=1",
            "VALIDATION_REPLAY_MICROSCOPE_MAX_LINES=6",
            "VALIDATION_REPLAY_MICROSCOPE_TOPK=0",
            "VALIDATION_REPLAY_MICROSCOPE_MIN_TOKENS_NO_SPEC=849",
            "VALIDATION_REPLAY_MICROSCOPE_MAX_TOKENS_NO_SPEC=849",
            "C1 no longer proves the preregistered active recurrence",
        ):
            self.assertIn(required, driver)
        self.assertLess(
            driver.index("M1 is permanently closed"), driver.index("env -i")
        )


if __name__ == "__main__":
    unittest.main()
