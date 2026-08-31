import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
RUNNER = ROOT / "experiments/qwen38-27b-b70/scripts/run-20260830-qwen38-q4km-tp2-wdc-http-quality-arm-r1.sh"


class Qwen38Q4kmRunnerTests(unittest.TestCase):
    def test_pilot_generates_its_own_shape_oracle(self) -> None:
        source = RUNNER.read_text()
        self.assertIn(
            'if [[ "${baseline_mode}" == 0 && "${pilot_mode}" == 0 ]]; then',
            source,
        )
        self.assertIn(
            "--pilot-from-batch --oracle-out",
            source,
        )

    def test_oracle_provenance_is_not_mislabeled(self) -> None:
        source = RUNNER.read_text()
        self.assertIn("CONCURRENCY_ORACLE_KIND", source)
        self.assertIn('"oracle_kind": oracle_kind', source)
        self.assertIn('"same_shape_batch_oracle_exact_all"', source)
        self.assertIn('if oracle_kind == "sequential" else None', source)

    def test_ubatch_is_configurable_recorded_and_launch_verified(self) -> None:
        source = RUNNER.read_text()
        self.assertIn('ubatch_size=${UBATCH_SIZE:-256}', source)
        self.assertIn('UBATCH_SIZE="${ubatch_size}" THREADS=8', source)
        self.assertIn('--ubatch-size[[:space:]]+${ubatch_size}', source)
        self.assertIn('"ubatch_size": ubatch_size', source)
        self.assertNotIn('UBATCH_SIZE=256 THREADS=8', source)

    def test_onednn_profile_environment_is_archived(self) -> None:
        source = RUNNER.read_text()
        self.assertIn('DNNL_VERBOSE=|ONEDNN_VERBOSE=', source)

    def test_dual_gemm_is_scoped_recorded_and_must_fire(self) -> None:
        source = RUNNER.read_text()
        self.assertIn('q4k_dual_gemm=${Q4K_DUAL_GEMM:-0}', source)
        self.assertIn('Q4K_DUAL_GEMM="${q4k_dual_gemm}"', source)
        self.assertIn('"q4k_dual_gemm": q4k_dual_gemm', source)
        self.assertIn('candidate Q4_K dual-GEMM liveness failed', source)
        self.assertIn('Q4_K dual-GEMM negative control failed', source)

    def test_f16_activation_dedup_is_scoped_recorded_and_must_fire(self) -> None:
        source = RUNNER.read_text()
        self.assertIn('f16_act_dedup=${F16_ACT_DEDUP:-0}', source)
        self.assertIn('F16_ACT_DEDUP="${f16_act_dedup}"', source)
        self.assertIn('"f16_act_dedup": f16_act_dedup', source)
        self.assertIn('candidate F16 activation-dedup liveness failed', source)
        self.assertIn('F16 activation-dedup negative control failed', source)


if __name__ == "__main__":
    unittest.main()
