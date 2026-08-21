#!/usr/bin/env python3
"""CPU/static tests for the distinct Q64xK32 operator campaign."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("qwen38_mtp5_m6_fa_q64k32_operator.py")
DRIVER = Path(__file__).with_name(
    "run-20260821-qwen38-mtp5-m6-fa-q64k32-operator-abba.sh"
)
BASE_TEST_PATH = Path(__file__).with_name("test_qwen38_mtp5_m6_fa_operator.py")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


QUALIFIER = _load("q64k32_operator", SCRIPT)
BASE_TEST = _load("q64k32_base_test", BASE_TEST_PATH)


def q64_packet(device: int, slot: int, role: str, latency: float) -> dict:
    packet = BASE_TEST.make_packet(device, slot, role, latency)
    packet["schema"] = QUALIFIER.SCHEMA_RUN
    operator = packet["operator_identity"]
    operator[QUALIFIER.POLICY_IDENTITY_KEY] = operator.pop("m6_head256_q8k64_policy")
    packet["engagement"]["policy_env"] = QUALIFIER.POLICY_ENV
    packet["engagement"]["marker"] = (
        None if role == "control" else QUALIFIER.POLICY_MARKER
    )
    stage = packet["stage_identity"]
    if role == "candidate":
        stage["artifact_path"] = f"/tmp/{QUALIFIER.BUILD_INPUTS_BASENAME}"
        stage["graph_manifest_path"] = f"/tmp/{QUALIFIER.GRAPH_MANIFEST_BASENAME}"
    runtime = packet["runtime_identity"]
    runtime["script_path"] = str(SCRIPT.resolve())
    runtime["script_sha256"] = QUALIFIER.sha256_file(SCRIPT.resolve())
    runtime["base_qualifier_path"] = str(QUALIFIER.BASE_QUALIFIER.resolve())
    runtime["base_qualifier_sha256"] = QUALIFIER.BASE_QUALIFIER_SHA256
    runtime["campaign_driver_path"] = str(DRIVER.resolve())
    runtime["campaign_driver_sha256"] = QUALIFIER.sha256_file(DRIVER.resolve())
    return packet


def campaign(control: float = 160.0, candidate: float = 120.0) -> list[dict]:
    result: list[dict] = []
    for device in (2, 3):
        result.extend(
            (
                q64_packet(device, 1, "control", control),
                q64_packet(device, 2, "candidate", candidate),
                q64_packet(device, 3, "candidate", candidate),
                q64_packet(device, 4, "control", control),
            )
        )
    return result


def validated(packets: list[dict]) -> list[dict]:
    return [
        QUALIFIER._validate_run_packet(packet, Path(f"packet-{index}.json"))
        for index, packet in enumerate(packets)
    ]


def cpu_oracle_message() -> str:
    return (
        "KV 128 eager 0 differs from CPU oracle: Tensor-likes are not close!\n"
        "Mismatched elements: 3297 / 18432 (17.9%)\n"
        "Greatest absolute difference: 0.1544189453125 at index (0, 5, 116) "
        "(up to 0.02 allowed)\n"
        "Greatest relative difference: 1485.0 at index (0, 9, 89) "
        "(up to 0.01 allowed)"
    )


class Q64K32ContractTests(unittest.TestCase):
    def test_policy_namespace_and_success_contract(self) -> None:
        packet = q64_packet(2, 2, "candidate", 120.0)
        QUALIFIER._validate_run_packet(packet, Path("candidate.json"))
        self.assertIn("q64k32", packet["schema"])
        self.assertEqual(packet["engagement"]["policy_env"], QUALIFIER.POLICY_ENV)
        self.assertNotIn("m6_head256_q8k64_policy", packet["operator_identity"])

    def test_paired_hurdles_pass_without_historical_absolute_gate(self) -> None:
        # 135 us exceeds the discarded historical 129.62186 cap, but the
        # within-campaign paired saving is 25 us on each GPU and must pass.
        result = QUALIFIER.compare_packets(validated(campaign(160.0, 135.0)), 5000)
        self.assertTrue(result["passed"])
        self.assertNotIn("maximum_kv1300_candidate_us_per_call_each_gpu", result)

    def test_saving_below_21_844_rejects(self) -> None:
        result = QUALIFIER.compare_packets(validated(campaign(160.0, 140.0)), 5000)
        self.assertFalse(result["passed"])

    def test_success_validator_rejects_wrong_marker_and_mapping(self) -> None:
        marker = q64_packet(2, 2, "candidate", 120.0)
        marker["engagement"]["marker_count"] = 0
        with self.assertRaisesRegex(QUALIFIER.ContractError, "engagement marker"):
            QUALIFIER._validate_run_packet(marker, Path("marker.json"))
        mapping = q64_packet(2, 2, "candidate", 120.0)
        mapping["mapped_libraries"]["device_library"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(QUALIFIER.ContractError, "mapped device_library"):
            QUALIFIER._validate_run_packet(mapping, Path("mapping.json"))

    def test_exact_cpu_oracle_error_metadata(self) -> None:
        metadata = QUALIFIER.failure_error_metadata(
            QUALIFIER.ContractError(cpu_oracle_message()), 128
        )
        self.assertEqual(metadata["phase"], "checked-cpu-oracle-replay")
        self.assertEqual(metadata["correctness_kind"], "cpu-oracle-mismatch")
        self.assertEqual(metadata["mismatched_elements"], 3297)
        self.assertEqual(metadata["element_count"], 18432)
        self.assertEqual(metadata["greatest_absolute_difference"], 0.1544189453125)
        self.assertEqual(metadata["greatest_absolute_difference_index"], [0, 5, 116])
        self.assertEqual(metadata["greatest_relative_difference"], 1485.0)
        self.assertEqual(metadata["greatest_relative_difference_index"], [0, 9, 89])

    def test_mutation_and_post_mutation_oracle_metadata(self) -> None:
        for label, replay in (
            ("q_scale_0p875 eager 0", 0),
            ("post-mutation eager", None),
        ):
            with self.subTest(label=label):
                message = cpu_oracle_message().replace("eager 0", label, 1)
                metadata = QUALIFIER.failure_error_metadata(
                    QUALIFIER.ContractError(message), 128
                )
                self.assertEqual(metadata["correctness_kind"], "cpu-oracle-mismatch")
                self.assertEqual(metadata["replay_index"], replay)

    def test_other_checked_correctness_failures_are_classified(self) -> None:
        examples = {
            "KV 128 eager 0 left poisoned NaNs": "poison-not-overwritten",
            "KV 128 eager call ignored static out": "caller-output-not-honored",
            "KV 128 graph capture ignored static out": "caller-output-not-honored",
            "KV 128 post-mutation eager call ignored out": (
                "caller-output-not-honored"
            ),
            "KV 128 mutation q_scale_0p875 ignored eager out": (
                "caller-output-not-honored"
            ),
            "KV 128 eager output is not bit-stable": "bit-instability",
            "KV 128 eager and graph outputs differ bitwise": (
                "eager-graph-bit-mismatch"
            ),
            "KV 128 mutation q_scale_0p875 was output-inert": ("mutation-output-inert"),
        }
        for message, expected in examples.items():
            with self.subTest(message=message):
                metadata = QUALIFIER.failure_error_metadata(
                    QUALIFIER.ContractError(message), 128
                )
                self.assertEqual(metadata["correctness_kind"], expected)
        unknown = QUALIFIER.failure_error_metadata(RuntimeError("driver lost"), 128)
        self.assertIsNone(unknown["correctness_kind"])

    def _failure_receipt(self, directory: Path) -> tuple[Path, dict]:
        source = q64_packet(2, 1, "control", 160.0)
        stderr = directory / "gpu2-control.json.stderr.log"
        stderr.write_bytes(b"")
        stderr.chmod(0o444)
        failure_path = directory / "gpu2-control.json.failure.json"
        success_path = directory / "gpu2-control.json"
        files = source["stage_identity"]["files"]
        required = {
            name: {"path": files[name]["path"], "sha256": files[name]["sha256"]}
            for name in ("extension", "device_library", "stock_library")
        }
        failure = QUALIFIER.failure_error_metadata(
            QUALIFIER.ContractError(cpu_oracle_message()), 128
        )
        packet = {
            "schema": QUALIFIER.SCHEMA_FAILURE,
            "passed": False,
            "classification": "control-correctness-failure",
            "role": "control",
            "arm_id": "gpu2-a1",
            "campaign_slot": 1,
            "process": source["process"],
            "operator_identity": source["operator_identity"],
            "stage_identity": source["stage_identity"],
            "engagement": {
                "policy_env": QUALIFIER.POLICY_ENV,
                "policy_value": "0",
                "expected_marker_lines": [],
                "observed_marker_lines": [],
                "marker_gate_passed": True,
                "stderr_decode_error": None,
                "stderr_line_count": 0,
                "stderr_log_path": str(stderr),
                "stderr_log_sha256": QUALIFIER.sha256_file(stderr),
            },
            "mapping_evidence": {
                "required": required,
                "matched": copy.deepcopy(required),
                "same_basename_paths": {
                    name: [entry["path"]] for name, entry in required.items()
                },
                "mapping_gate_passed": True,
                "mapping_error": None,
            },
            "runtime_identity": source["runtime_identity"],
            "timing_contract": source["timing_contract"],
            "completed_cases": [],
            "failure": failure,
            "output_contract": {
                "success_packet_path": str(success_path),
                "success_packet_persisted": False,
                "failure_packet_path": str(failure_path),
                "stderr_persisted": True,
            },
        }
        QUALIFIER.write_json_atomic(failure_path, Path(f"{failure_path}.tmp"), packet)
        return failure_path, packet

    def test_failure_receipt_rederives_error_marker_mapping_and_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path, _ = self._failure_receipt(Path(temporary))
            QUALIFIER.validate_failure_packet(QUALIFIER.load_json(path), path)

    def test_failure_receipt_rejects_false_mapping_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path, packet = self._failure_receipt(Path(temporary))
            path.chmod(0o600)
            packet["mapping_evidence"]["matched"]["device_library"] = None
            QUALIFIER.write_json_atomic(path, Path(f"{path}.tmp"), packet)
            with self.assertRaisesRegex(
                QUALIFIER.ContractError, "false matched mapping corroboration"
            ):
                QUALIFIER.validate_failure_packet(QUALIFIER.load_json(path), path)

    def test_failure_receipt_rejects_uncorroborated_mapping_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path, packet = self._failure_receipt(Path(temporary))
            path.chmod(0o600)
            packet["mapping_evidence"]["same_basename_paths"]["device_library"] = []
            QUALIFIER.write_json_atomic(path, Path(f"{path}.tmp"), packet)
            with self.assertRaisesRegex(
                QUALIFIER.ContractError, "false matched mapping corroboration"
            ):
                QUALIFIER.validate_failure_packet(QUALIFIER.load_json(path), path)

    def test_failure_receipt_rejects_false_eager_graph_digest_exactness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path, packet = self._failure_receipt(Path(temporary))
            path.chmod(0o600)
            source = q64_packet(2, 1, "control", 160.0)
            completed = copy.deepcopy(source["cases"][0])
            completed["graph_output_sha256"] = "7" * 64
            packet["completed_cases"] = [completed]
            QUALIFIER.write_json_atomic(path, Path(f"{path}.tmp"), packet)
            with self.assertRaisesRegex(
                QUALIFIER.ContractError, "eager/graph digest mismatch"
            ):
                QUALIFIER.validate_failure_packet(QUALIFIER.load_json(path), path)

    def test_valid_engagement_unclassified_failure_is_not_mislabeled(self) -> None:
        self.assertEqual(
            QUALIFIER.failure_classification("candidate", None, True, True),
            "arm-valid-engagement-unclassified-operator-or-runtime-failure",
        )
        self.assertEqual(
            QUALIFIER.failure_classification("candidate", None, False, True),
            "arm-failure-with-incomplete-or-invalid-engagement",
        )

    def test_failure_receipt_rejects_tampered_numeric_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path, packet = self._failure_receipt(Path(temporary))
            path.chmod(0o600)
            packet["failure"]["mismatched_elements"] = 1
            QUALIFIER.write_json_atomic(path, Path(f"{path}.tmp"), packet)
            with self.assertRaisesRegex(
                QUALIFIER.ContractError, "error metadata does not rederive"
            ):
                QUALIFIER.validate_failure_packet(QUALIFIER.load_json(path), path)

    def test_failure_receipt_rejects_wrong_device_before_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path, packet = self._failure_receipt(Path(temporary))
            path.chmod(0o600)
            packet["runtime_identity"]["device_name"] = "Intel(R) Arc(TM) Graphics"
            packet["completed_cases"] = ["untrusted-case"]
            QUALIFIER.write_json_atomic(path, Path(f"{path}.tmp"), packet)
            with self.assertRaisesRegex(
                QUALIFIER.ContractError, "runtime/device identity"
            ):
                QUALIFIER.validate_failure_packet(QUALIFIER.load_json(path), path)

    def test_failure_receipt_rejects_role_slot_arm_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path, packet = self._failure_receipt(Path(temporary))
            path.chmod(0o600)
            packet["campaign_slot"] = 2
            QUALIFIER.write_json_atomic(path, Path(f"{path}.tmp"), packet)
            with self.assertRaisesRegex(
                QUALIFIER.ContractError, "arm/slot/device ordering mismatch"
            ):
                QUALIFIER.validate_failure_packet(QUALIFIER.load_json(path), path)

    def test_failure_output_collisions_precede_stage_and_torch(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        collision = source.index("if any(path.exists() for path in collision_paths)")
        stage = source.index("identity = stage_identity(args)", collision)
        torch_import = source.index("import torch", stage)
        self.assertLess(collision, stage)
        self.assertLess(stage, torch_import)

    def test_driver_is_candidate_first_and_validates_failure_receipt(self) -> None:
        source = DRIVER.read_text(encoding="utf-8")
        offsets = [
            source.index('run_one "$device" 1 control a1'),
            source.index('run_one "$device" 2 candidate b1'),
            source.index('run_one "$device" 3 candidate b2'),
            source.index('run_one "$device" 4 control a2'),
        ]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn('validate-failure "$failure"', source)
        self.assertIn("VLLM_XPU_FA2_M6_HEAD256_Q64K32_POLICY", source)
        self.assertNotIn("VLLM_XPU_FA2_M6_HEAD256_Q8K64_POLICY", source)


if __name__ == "__main__":
    unittest.main()
