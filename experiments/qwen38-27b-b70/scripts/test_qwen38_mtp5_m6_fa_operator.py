#!/usr/bin/env python3
"""CPU-only contract tests for the MTP5/M6 FlashAttention qualifier."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("qwen38_mtp5_m6_fa_operator.py")
DRIVER_PATH = Path(__file__).with_name(
    "run-20260820-qwen38-mtp5-m6-fa-operator-abba.sh"
)
HELPER_PATH = Path(__file__).with_name(
    "build-qwen38-m6-head256-q8k64-attn-override-20260820.sh"
)
SPEC = importlib.util.spec_from_file_location("qwen38_mtp5_m6_fa_operator", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
QUALIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUALIFIER)


def _digest(character: str) -> str:
    return character * 64


def make_packet(device: int, slot: int, role: str, latency: float) -> dict:
    suffix = ("a1", "b1", "b2", "a2")[slot - 1]
    hashes = dict(QUALIFIER.CONTROL_HASHES)
    if role == "candidate":
        hashes["device_library"] = _digest("c")
    stage_root = (
        str(QUALIFIER.CONTROL_STAGE)
        if role == "control"
        else "/tmp/qwen38-fa-candidate-stage"
    )
    files = {
        name: {
            "path": f"{stage_root}/{relative}",
            "relative_path": relative,
            "sha256": hashes[name],
        }
        for name, relative in QUALIFIER.RELATIVE_FILES.items()
    }
    cases = []
    for kv_len in QUALIFIER.KV_LENGTHS:
        token = hex(kv_len % 16)[2:]
        mutations = []
        for index, (name, target, scale, mutation_kv) in enumerate(
            (
                ("q_scale_0p875", "q", 0.875, kv_len),
                ("k_cache_scale_0p875", "k_cache", 0.875, kv_len),
                ("v_cache_scale_0p875", "v_cache", 0.875, kv_len),
                ("seqused_k_minus_64", "seqused_k", None, kv_len - 64),
            )
        ):
            mutations.append(
                {
                    "name": name,
                    "target": target,
                    "scale": scale,
                    "seqused_k": mutation_kv,
                    "input_sha256": _digest(hex(index + 5)[2:]),
                    "oracle_sha256": _digest(hex(index + 9)[2:]),
                    "eager_output_sha256": _digest(hex(index + 10)[2:]),
                    "graph_output_sha256": _digest(hex(index + 10)[2:]),
                    "eager_max_abs_diff": 0.001,
                    "graph_max_abs_diff": 0.001,
                    "repetitions_per_mode": 2,
                    "output_changed_from_baseline": True,
                    "eager_graph_exact": True,
                    "restored_before_next": True,
                    "passed": True,
                }
            )
        cases.append(
            {
                "kv_length": kv_len,
                "fixture_seed": 380000 + kv_len,
                "fixture_sha256": _digest(token),
                "oracle_sha256": _digest("d"),
                "eager_output_sha256": _digest("e"),
                "graph_output_sha256": _digest("e"),
                "eager_bit_stable": True,
                "graph_bit_stable": True,
                "eager_graph_exact": True,
                "eager_static_out_honored": True,
                "graph_static_out_honored": True,
                "poison_checked_replays_per_mode": 16,
                "eager_max_abs_diff": 0.001,
                "graph_max_abs_diff": 0.001,
                "mutations": mutations,
                "eager_samples_us_per_call": [latency + 2.0] * 30,
                "graph_samples_us_per_call": [latency] * 30,
                "eager_median_us_per_call": latency + 2.0,
                "graph_median_us_per_call": latency,
                "passed": True,
            }
        )
    started = device * 10_000_000 + slot * 1_000_000
    return {
        "schema": QUALIFIER.SCHEMA_RUN,
        "passed": True,
        "role": role,
        "arm_id": f"gpu{device}-{suffix}",
        "campaign_slot": slot,
        "process": {
            "pid": device * 10 + slot,
            "start_ticks": device * 100 + slot,
            "boot_id": "test-boot",
            "started_time_ns": started,
            "finished_time_ns": started + 100,
        },
        "operator_identity": {
            "dtype": "float16",
            "rows": 6,
            "mtp_depth": 5,
            "q_heads_tp2_local": 12,
            "kv_heads_tp2_local": 2,
            "head_dim": 256,
            "block_size": 64,
            "kv_lengths": [128, 1024, 1300, 2048],
            "causal": True,
            "paged_kv": True,
            "is_mix_batch": True,
            "vllm_xpu_fa2_force_chunk_decode": "1",
            "m6_head256_q8k64_policy": "0" if role == "control" else "1",
        },
        "stage_identity": {
            "role": role,
            "stage": stage_root,
            "hashes": hashes,
            "manifest_path": None if role == "control" else "/tmp/candidate.json",
            "manifest_sha256": None if role == "control" else _digest("f"),
            "artifact_path": (
                None
                if role == "control"
                else "/tmp/qwen38-m6-head256-q8k64-build-inputs.sha256"
            ),
            "artifact_sha256": None if role == "control" else _digest("a"),
            "graph_manifest_path": (
                None
                if role == "control"
                else "/tmp/qwen38-m6-head256-q8k64-candidate.graph.sha256"
            ),
            "graph_manifest_sha256": None if role == "control" else _digest("6"),
            "files": files,
        },
        "mapped_libraries": {
            name: {"path": files[name]["path"], "sha256": files[name]["sha256"]}
            for name in ("extension", "device_library", "stock_library")
        },
        "engagement": {
            "policy_env": QUALIFIER.POLICY_ENV,
            "policy_value": "0" if role == "control" else "1",
            "expected_marker_count": 0 if role == "control" else 1,
            "marker_count": 0 if role == "control" else 1,
            "marker": None if role == "control" else QUALIFIER.POLICY_MARKER,
            "stderr_log_path": f"/tmp/gpu{device}-{slot}.stderr.log",
            "stderr_log_sha256": _digest("4"),
            "stderr_line_count": 0 if role == "control" else 1,
        },
        "runtime_identity": {
            "script_path": str(MODULE_PATH),
            "script_sha256": _digest("1"),
            "campaign_driver_path": "/tmp/driver.sh",
            "campaign_driver_sha256": _digest("2"),
            "lab_repo_head": "3" * 40,
            "python": "test",
            "python_dont_write_bytecode": True,
            "torch_version": "test",
            "xpu_device_count": 1,
            "hostname": "steve-b70s",
            "physical_gpu": device,
            "logical_device": "xpu:0",
            "ze_affinity_mask": str(device),
            "device_name": QUALIFIER.EXPECTED_DEVICE_NAME,
            "device_properties": {"name": "B70"},
            "pythonpath_first": stage_root,
            "ld_library_path_first": f"{stage_root}/vllm_xpu_kernels",
        },
        "timing_contract": {
            "clock": "torch.xpu.Event device elapsed time",
            "samples_per_shape_mode": 30,
            "launches_per_sample": 50,
            "stability_replays_per_shape_mode": 16,
            "gated_mode": "xpu_graph_replay",
        },
        "cases": cases,
    }


def campaign(
    control_latency: float = 100.0, candidate_latency: float = 70.0
) -> list[dict]:
    packets = []
    for device in (2, 3):
        packets.extend(
            (
                make_packet(device, 1, "control", control_latency),
                make_packet(device, 2, "candidate", candidate_latency),
                make_packet(device, 3, "candidate", candidate_latency),
                make_packet(device, 4, "control", control_latency),
            )
        )
    return packets


class QualifierContractTests(unittest.TestCase):
    def validate(self, packets: list[dict]) -> list[dict]:
        return [
            QUALIFIER._validate_run_packet(packet, Path(f"packet-{index}.json"))
            for index, packet in enumerate(packets)
        ]

    def test_passing_two_gpu_abba(self) -> None:
        result = QUALIFIER.compare_packets(self.validate(campaign()), 5000)
        self.assertTrue(result["passed"])
        self.assertEqual(
            [
                item["kv1300_central_saving_us_per_call"]
                for item in result["device_results"]
            ],
            [30.0, 30.0],
        )

    def test_below_absolute_saving_threshold_rejects(self) -> None:
        result = QUALIFIER.compare_packets(
            self.validate(campaign(control_latency=100.0, candidate_latency=90.0)),
            5000,
        )
        self.assertFalse(result["passed"])

    def test_kv128_regression_bootstrap_upper_is_bounded(self) -> None:
        packets = campaign()
        for packet in packets:
            if packet["role"] == "candidate":
                packet["cases"][0]["graph_samples_us_per_call"] = [103.0] * 30
                packet["cases"][0]["graph_median_us_per_call"] = 103.0
        result = QUALIFIER.compare_packets(self.validate(packets), 5000)
        self.assertFalse(result["passed"])
        self.assertEqual(
            [
                item["kv128_regression_ci_upper_us_per_call"]
                for item in result["device_results"]
            ],
            [3.0, 3.0],
        )

    def test_long_kv_positive_ci_is_required(self) -> None:
        packets = campaign()
        for packet in packets:
            if packet["role"] == "candidate":
                packet["cases"][1]["graph_samples_us_per_call"] = [100.0] * 30
                packet["cases"][1]["graph_median_us_per_call"] = 100.0
        result = QUALIFIER.compare_packets(self.validate(packets), 5000)
        self.assertFalse(result["passed"])

    def test_exact_control_candidate_parity_is_required(self) -> None:
        packets = campaign()
        packets[1]["cases"][0]["graph_output_sha256"] = _digest("9")
        with self.assertRaisesRegex(QUALIFIER.ContractError, "exact output parity"):
            QUALIFIER.compare_packets(self.validate(packets), 5000)

    def test_wrong_abba_order_is_rejected(self) -> None:
        packets = campaign()
        packets[1]["role"] = "control"
        packets[1]["operator_identity"]["m6_head256_q8k64_policy"] = "0"
        packets[1]["stage_identity"] = copy.deepcopy(packets[0]["stage_identity"])
        packets[1]["mapped_libraries"] = copy.deepcopy(packets[0]["mapped_libraries"])
        packets[1]["engagement"] = copy.deepcopy(packets[0]["engagement"])
        packets[1]["runtime_identity"]["pythonpath_first"] = packets[0][
            "runtime_identity"
        ]["pythonpath_first"]
        packets[1]["runtime_identity"]["ld_library_path_first"] = packets[0][
            "runtime_identity"
        ]["ld_library_path_first"]
        with self.assertRaisesRegex(QUALIFIER.ContractError, "order is not ABBA"):
            QUALIFIER.compare_packets(self.validate(packets), 5000)

    def test_cross_device_process_overlap_is_rejected(self) -> None:
        packets = campaign()
        gpu2_a2 = packets[3]["process"]
        gpu3_a1 = packets[4]["process"]
        gpu3_a1["started_time_ns"] = gpu2_a2["started_time_ns"] + 50
        gpu3_a1["finished_time_ns"] = gpu3_a1["started_time_ns"] + 100
        with self.assertRaisesRegex(QUALIFIER.ContractError, "processes overlap"):
            QUALIFIER.compare_packets(self.validate(packets), 5000)

    def test_driver_compare_binds_packets_to_current_frozen_identity(self) -> None:
        source = DRIVER_PATH.read_text(encoding="utf-8")
        self.assertIn(".runtime_identity.script_sha256 == $operator_sha", source)
        self.assertIn(".runtime_identity.campaign_driver_sha256 == $driver_sha", source)
        self.assertIn(".runtime_identity.lab_repo_head == $repo_head", source)
        self.assertLess(source.index("jq -e"), source.index('exec "$python"'))

    def test_build_uses_only_process_local_git_safety_override(self) -> None:
        source = HELPER_PATH.read_text(encoding="utf-8")
        self.assertIn("export GIT_CONFIG_COUNT=1", source)
        self.assertIn("export GIT_CONFIG_KEY_0=safe.directory", source)
        self.assertIn('export GIT_CONFIG_VALUE_0="$stage/.deps/onednn-src"', source)
        self.assertNotIn("git config --global", source)

    def test_build_reseals_only_the_private_runtime_copy(self) -> None:
        source = HELPER_PATH.read_text(encoding="utf-8")
        stages = (
            'rsync -a "$base_stage/" "$runtime/"',
            'chmod u+w "$runtime" "$runtime/vllm_xpu_kernels"',
            "install -m 0555",
            'chmod 0555 "$runtime/vllm_xpu_kernels" "$runtime"',
        )
        offsets = [source.index(stage) for stage in stages]
        self.assertEqual(offsets, sorted(offsets))

    def test_graph_correctness_is_checked_only_after_replay(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        capture = source.index("with torch.xpu.graph(graph):")
        replay = source.index("graph.replay()", capture)
        graph_assert = source.index("_assert_close(", capture)
        self.assertLess(replay, graph_assert)

    def test_strict_json_rejects_duplicate_keys_and_nan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            duplicate = Path(directory) / "duplicate.json"
            duplicate.write_text('{"a":1,"a":2}\n', encoding="utf-8")
            with self.assertRaisesRegex(QUALIFIER.ContractError, "duplicate JSON key"):
                QUALIFIER.load_json(duplicate)
            nonstandard = Path(directory) / "nan.json"
            nonstandard.write_text('{"a":NaN}\n', encoding="utf-8")
            with self.assertRaisesRegex(QUALIFIER.ContractError, "non-standard JSON"):
                QUALIFIER.load_json(nonstandard)

    def test_bool_is_not_an_integer(self) -> None:
        packet = campaign()[0]
        packet["campaign_slot"] = True
        with self.assertRaisesRegex(QUALIFIER.ContractError, "must be an integer"):
            QUALIFIER._validate_run_packet(packet, Path("bad.json"))

    def test_exact_b70_device_name_is_required(self) -> None:
        packet = campaign()[0]
        packet["runtime_identity"]["device_name"] = "Intel(R) Arc(TM) Graphics"
        with self.assertRaisesRegex(QUALIFIER.ContractError, "device identity"):
            QUALIFIER._validate_run_packet(packet, Path("wrong-device.json"))

    def test_candidate_may_change_only_device_library(self) -> None:
        packet = campaign()[1]
        packet["stage_identity"]["hashes"]["extension"] = _digest("b")
        packet["stage_identity"]["files"]["extension"]["sha256"] = _digest("b")
        packet["mapped_libraries"]["extension"]["sha256"] = _digest("b")
        with self.assertRaisesRegex(QUALIFIER.ContractError, "fixed extension"):
            QUALIFIER._validate_run_packet(packet, Path("bad-boundary.json"))

    def test_candidate_marker_is_required(self) -> None:
        packet = campaign()[1]
        packet["engagement"]["marker_count"] = 0
        with self.assertRaisesRegex(QUALIFIER.ContractError, "engagement marker"):
            QUALIFIER._validate_run_packet(packet, Path("bad-marker.json"))

    def test_stock_mapping_is_required(self) -> None:
        packet = campaign()[0]
        del packet["mapped_libraries"]["stock_library"]
        with self.assertRaisesRegex(
            QUALIFIER.ContractError, "mapped library inventory"
        ):
            QUALIFIER._validate_run_packet(packet, Path("bad-mapping.json"))

    def test_all_four_mutations_are_required(self) -> None:
        packet = campaign()[0]
        packet["cases"][0]["mutations"].pop()
        with self.assertRaisesRegex(QUALIFIER.ContractError, "mutation inventory"):
            QUALIFIER._validate_run_packet(packet, Path("bad-mutation.json"))

    def test_checksum_manifest_parser_rejects_duplicate_and_malformed_line(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.sha256"
            target = Path(directory) / "target"
            manifest.write_text(
                f"{'a' * 64}  {target}\n{'b' * 64}  {target}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(QUALIFIER.ContractError, "duplicate checksum"):
                QUALIFIER.parse_sha256_manifest(manifest)
            # The path itself is allowed to contain spaces/tabs, so prove malformed
            # digest/prefix syntax fails instead of inventing a filename policy.
            manifest.write_text(f"{'a' * 63}Z  {target}\n", encoding="utf-8")
            with self.assertRaisesRegex(QUALIFIER.ContractError, "malformed checksum"):
                QUALIFIER.parse_sha256_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
