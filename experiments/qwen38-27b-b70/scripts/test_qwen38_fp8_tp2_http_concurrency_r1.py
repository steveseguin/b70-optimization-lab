import json
import hashlib
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]


class Fp8ConcurrencyPilotContractTest(unittest.TestCase):
    def test_pilot_contract_is_frozen_and_nonpublishable(self) -> None:
        path = ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-tp2-http-concurrency-oracle-pilot-r1-prereg.json"
        data = json.loads(path.read_text())
        self.assertEqual(data["state"], "preregistered-not-launched")
        self.assertEqual(data["identity"]["generation"], "target-only / MTP0")
        self.assertEqual(data["identity"]["cards"], 2)
        self.assertEqual(data["server_profile"]["max_num_seqs"], 4)
        self.assertEqual(data["pilot"]["concurrency_points"], [1, 2, 4, 8, 16, 32, 64])
        self.assertEqual(data["pilot"]["sequential_oracle_rows"], 64)
        self.assertIn("may not be published", data["pilot"]["publication_status"])
        self.assertIn("two new fresh-server", data["next_step_if_passed"])
        for key, field in (
            ("suite", "suite_sha256"),
            ("harness", "harness_sha256"),
            ("request_client", "request_client_sha256"),
        ):
            source = ROOT / data["frozen_inputs"][key]
            self.assertEqual(
                hashlib.sha256(source.read_bytes()).hexdigest(),
                data["frozen_inputs"][field],
            )

    def test_r2_freezes_oracle_runner_and_queue_boundary(self) -> None:
        path = ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-tp2-http-concurrency-r2-prereg.json"
        data = json.loads(path.read_text())
        self.assertEqual(data["state"], "preregistered-not-launched")
        self.assertEqual(data["measurement"]["fresh_server_attempts"], 2)
        self.assertIn("c8-c64", data["measurement"]["queue_boundary"])
        self.assertIn("<=10%", data["measurement"]["required_throughput_stability_gate"])
        self.assertIn("<=15%", data["measurement"]["required_latency_stability_gate"])
        for key, field in (
            ("oracle", "oracle_sha256"),
            ("suite", "suite_sha256"),
            ("runner", "runner_sha256"),
            ("summarizer", "summarizer_sha256"),
            ("excluded_warmup_client", "excluded_warmup_client_sha256"),
        ):
            source = ROOT / data["frozen_inputs"][key]
            self.assertEqual(
                hashlib.sha256(source.read_bytes()).hexdigest(),
                data["frozen_inputs"][field],
            )


if __name__ == "__main__":
    unittest.main()
