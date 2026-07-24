#!/usr/bin/env python3
"""CPU-only corruption tests for the v3 Phase-A shared validator."""
from __future__ import annotations

import ast
import base64
import copy
import fcntl
import hashlib
import os
import socket
import subprocess
import tempfile
import unittest
import uuid
from unittest import mock
from pathlib import Path

import run_laguna_m8_gather_sharded_phase_a as validator
import orchestrate_laguna_m8_gather_sharded_phase_a as coordinator
import preflight_laguna_m8_gather_sharded_operational as operational

coordinator.operational = operational
coordinator.phase_a = validator


ROOT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
A_PATH = ROOT / "packets/unit-a.json"
B_PATH = ROOT / "packets/unit-b.json"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def file_identity(name: str) -> dict[str, str]:
    return {"path": str(ROOT / "tools" / name), "sha256": digest(name)}


def a_tool_identity(role: str) -> dict[str, str]:
    path = validator.REPOSITORY_ROOT / "experiments/laguna-s-2.1-xpu-b70/tools" / validator.A_TOOL_FILENAMES[role]
    return {"path": str(path), "sha256": validator.sha256_file(path)}


def runtime_file(name: str) -> dict[str, str]:
    path = f"/home/steve/.venvs/deepseek-v4-xpu/{name}"
    return {"path": path, "resolved_path": path, "sha256": digest(name)}


def common() -> dict:
    records = {
        name: {"path": str(ROOT / "fixture" / f"{name}.bin"), "sha256": digest(name), "dtype": "<u2", "shape": [288, 1], "per_epoch_sha256": [digest(f"{name}-{index}") for index in range(validator.EPOCHS)]}
        for name in validator.FIXTURE_RECORDS
    }
    return {
        "format": validator.COMMON_FORMAT,
        "source": {"approved_record_vllm_commit": "8936aac144929190c1e53f8b8624ca397ce16f5b", "approved_record_kernel_commit": "b6076ce1249ffee0e30bee528f4cd15c3bffb234", "candidate_kernel_commit": "7e6a74026a2a4370abcb7973d28bbc9d1ddd1be6"},
        "source_ir": copy.deepcopy(validator.SOURCE_IR_IDENTITY),
        "stage0_completion": {"path": str(ROOT / "evidence/stage0.json"), "sha256": digest("stage0"), "status": "stage0_host_only_complete_pending_packet_commit", "input": {"path": str(ROOT / "evidence/stage0-input.json"), "sha256": digest("stage0-input")}},
        "native_bundle": {"root": str(ROOT / "binaries/unit"), "manifest": str(ROOT / "binaries/unit/manifest.json"), "manifest_sha256": digest("manifest"), "prepared": str(ROOT / "binaries/unit/bundle-prepared.json"), "prepared_sha256": digest("prepared"), "library_sha256": {name: digest(name) for name in validator.LIBRARIES}, "libraries": {name: {"role": "test", "source": str(ROOT / "source" / name), "path": str(ROOT / "binaries/unit" / name), "sha256": digest(name), "bytes": 1, "mode": 0o444} for name in validator.LIBRARIES}, "status": "validated_host_only_not_imported", "validation_protocol": "separate_successful_validate_existing_invocation_required", "storage": {"mount_point": "/mnt/fast-ai", "filesystem": "ext4", "source": "/dev/nvme0n1p2", "major_minor": "259:2", "sysfs_device": "/sys/devices/pci0000:00/nvme0/nvme0n1"}},
        "fixture": {"root": str(ROOT / "fixture"), "manifest": str(ROOT / "fixture/manifest.json"), "manifest_sha256": digest("fixture-manifest"), "analysis": str(ROOT / "fixture/analysis.json"), "analysis_sha256": digest("fixture-analysis"), "canonical_route_map": {"path": str(ROOT / "fixture/canonical_route_map.int32.le.bin"), "sha256": digest("map")}, "records": records},
        "cards": copy.deepcopy(list(validator.PHYSICAL_CARDS)),
        "treatments": {"A": "generic_moe_gather", "B": "laguna_m8_moe_gather_sharded", "same_candidate_moe_library": True},
        "logical_cycle": {"layers": 47, "warm_cycles_per_arm": 20, "blocks": 31, "cycles_per_arm": 64, "arm_order": "A-B-B-A", "rotation": "(block*47)%256", "pre_epochs": 256, "post_epochs": 32, "minimum_wins": 28, "minimum_median_saving_ms": 0.08},
        "operational_preflight": copy.deepcopy(validator.OPERATIONAL_PREFLIGHT_IDENTITY),
        "runtime_identity": copy.deepcopy(validator.RUNTIME_IDENTITY),
    }


def cards() -> list[dict]:
    return [{"rank": rank, "physical_rank": rank, "environment": validator.expected_environment(rank, ROOT / f"runs/card{rank}"), "output_root": str(ROOT / f"runs/card{rank}")} for rank in range(4)]


def b_cards() -> list[dict]:
    return [{"rank": rank, "output_root": str(ROOT / f"runs/b/card{rank}"), "environments": {arm: {"ZE_AFFINITY_MASK": str(rank)} for arm in ("A1", "B1", "B2", "A2")}, "sessions": {arm: f"Laguna{arm}Card{rank}{rank:032x}" for arm in ("A1", "B1", "B2", "A2")}} for rank in range(4)]


def pair() -> tuple[dict, dict]:
    shared = common()
    a_body = {"format": validator.PHASE_A_BODY_FORMAT, "common": shared, "common_binding_sha256": validator.common_hash(shared), "phase_b_reference": {"authorization_path": str(B_PATH), "runner_path": str(ROOT / "tools/phase-b-runner.py"), "runner_sha256": digest("phase-b-runner.py"), "common_binding_sha256": validator.common_hash(shared)}, **{role: a_tool_identity(role) for role in validator.A_TOOL_FILENAMES}, "protocol": {"phase": "A", "authorization": "component_exactness_and_timing_only"}, "cards": cards(), "aggregate_path": str(ROOT / "runs/aggregate.json"), "capability": {"phase": "A", "phase_b_counters_authorized": False, "endpoint_authorized": False, "model_generation_authorized": False, "submission_authorized": False}}
    b_tools = {name: {"path": str(validator.REPOSITORY_ROOT / "experiments/laguna-s-2.1-xpu-b70/tools" / filename), "sha256": validator.sha256_file(validator.REPOSITORY_ROOT / "experiments/laguna-s-2.1-xpu-b70/tools" / filename)} for name, filename in validator.B_TOOL_FILENAMES.items()}
    a_body["phase_b_reference"].update(runner_path=b_tools["runner"]["path"], runner_sha256=b_tools["runner"]["sha256"])
    b_body = {"phase": "B", "common": copy.deepcopy(shared), "common_binding_sha256": validator.common_hash(shared), "phase_a_binding": {"authorization_path": str(A_PATH), "phase_a_body_sha256": validator.sha_bytes(validator.canonical_json(a_body)), "phase_a_runner_path": a_body["runner"]["path"], "phase_a_runner_sha256": a_body["runner"]["sha256"], "aggregate_path": a_body["aggregate_path"], "aggregate_format": "laguna-m8-gather-sharded-phase-a-aggregate-v3", "required_status": "component_timing_pass_pending_mandatory_counters", "required_passed": True, "common_binding_sha256": validator.common_hash(shared)}, "output_root": str(ROOT / "runs/b"), "cards": b_cards(), "protocol": {}, "counter_gates": {}, "counter_header": {}, "tools": b_tools, "counter_tools": {}, "temporal_control": {}}
    b_packet = {"format": validator.PHASE_B_FORMAT, "packet_path": str(B_PATH), "body": b_body}
    a_packet = {"format": validator.PHASE_A_FORMAT, "packet_path": str(A_PATH), "body": a_body, "paired_phase_b_packet_sha256": validator.sha_bytes(validator.canonical_json(b_packet))}
    return a_packet, b_packet


def valid_card_result(packet: dict, rank: int = 0) -> dict:
    common_value = packet["body"]["common"]
    output = digest("exact-output")
    classification = {"positive_zero": 0, "negative_zero": 0, "subnormal": 0,
                      "finite_normal": 8 * 3072, "infinity": 0, "nan": 0,
                      "nan_payloads_sha256": hashlib.sha256(b"").hexdigest()}
    comparison = {"left_raw_bf16_le_sha256": output, "right_raw_bf16_le_sha256": output,
                  "raw_uint16_equal": True, "left_classification": classification,
                  "right_classification": copy.deepcopy(classification), "torch_equal": True,
                  "nan_policy": "torch_equal_and_raw_bits", "passed": True}
    output_names = {"control_gather", "candidate_gather", "candidate_repeat", "scale_add",
                    "rank_order_bf16_sum", "fused_add_rms_norm_hidden", "fused_add_rms_norm_residual",
                    "candidate_scale_add", "candidate_rank_order_bf16_sum",
                    "candidate_fused_add_rms_norm_hidden", "candidate_fused_add_rms_norm_residual"}
    comparison_names = {"gather", "candidate_repeat", "scale_add", "rank_order_bf16_sum",
                        "fused_add_rms_norm_hidden", "fused_add_rms_norm_residual"}
    def epoch(index: int) -> dict:
        inputs = {name: common_value["fixture"]["records"][name]["per_epoch_sha256"][index]
                  for name in validator.FIXTURE_RECORDS}
        inputs["canonical_route_map"] = common_value["fixture"]["canonical_route_map"]["sha256"]
        return {"epoch": index, "input_before": inputs, "input_after": copy.deepcopy(inputs),
                "outputs": {name: output for name in output_names},
                "raw_bf16_classification": copy.deepcopy(classification),
                "comparisons": {name: copy.deepcopy(comparison) for name in comparison_names}, "passed": True}
    exact = [copy.deepcopy(comparison) for _ in range(47)]
    blocks = []
    for block in range(31):
        control_ns, candidate_ns = 64_000_000, 57_600_000
        control_ms = (control_ns + control_ns) / (2 * 64) / 1_000_000
        candidate_ms = (candidate_ns + candidate_ns) / (2 * 64) / 1_000_000
        blocks.append({"block": block, "fixture_indices": [(block * 47 + slot) % 256 for slot in range(47)],
                       "A1_control_elapsed_ns": control_ns, "B1_candidate_elapsed_ns": candidate_ns,
                       "B2_candidate_elapsed_ns": candidate_ns, "A2_control_elapsed_ns": control_ns,
                       "paired_control_ms_per_47_layer_cycle": control_ms,
                       "paired_candidate_ms_per_47_layer_cycle": candidate_ms,
                       "saving_ms_per_47_layer_cycle": control_ms - candidate_ms,
                       "selected_gather_launches": {"control": 47, "candidate": 47},
                       "post_block_raw_exactness": copy.deepcopy(exact)})
    root = Path(packet["body"]["cards"][rank]["output_root"])
    expected_dirs: set[str] = set()
    for path_value in validator.expected_environment(rank, root).values():
        path = Path(path_value)
        if path.is_absolute() and path.is_relative_to(root):
            relative = path.relative_to(root)
            expected_dirs.update(str(Path(*relative.parts[:offset])) for offset in range(1, len(relative.parts) + 1))
    retained = {}
    for name in validator.LIBRARIES:
        record = common_value["native_bundle"]["libraries"][name]
        retained[f"library:{name}"] = {"sha256": record["sha256"], "dev": 1, "inode": 2, "bytes": record["bytes"]}
    for name in validator.FIXTURE_RECORDS:
        record = common_value["fixture"]["records"][name]
        width = {"<u2": 2, "<u4": 4}[record["dtype"]]
        size = width
        for dimension in record["shape"]:
            size *= dimension
        retained[name] = {"sha256": record["sha256"], "dev": 1, "inode": 2, "bytes": size}
    retained["canonical_route_map"] = {"sha256": common_value["fixture"]["canonical_route_map"]["sha256"],
                                       "dev": 1, "inode": 2, "bytes": 320}
    dependencies = set(validator.LIBRARIES[3:])
    native = {name: {"sha256": common_value["native_bundle"]["libraries"][name]["sha256"],
                     "bytes": common_value["native_bundle"]["libraries"][name]["bytes"], "dev": 1, "inode": 2,
                     "loaded_via": f"/proc/self/fd/{20 + index}", "rtld_global": name in dependencies,
                     "mapping_verified": True} for index, name in enumerate(validator.LIBRARIES)}
    physical = common_value["cards"][rank]
    runtime = {"physical_rank": rank, "bdf": physical["bdf"], "drm_card": physical["drm_card"],
               "vendor": "0x8086", "device": "0xe223", "torch_version": "2.12.0+xpu",
               "device_name": "Intel(R) Arc(TM) Pro B70 Graphics", "oneapi_device_selector": "level_zero:0",
               "ze_affinity_mask": str(rank), "logical_probe": "xpu:0",
               "torch_uuid_bytes_hex": uuid.UUID(physical["xpu_smi_uuid"]).bytes[::-1].hex(),
               "xpu_smi_uuid": physical["xpu_smi_uuid"],
               "uuid_mapping": "xpu_smi_uuid_is_reverse_of_torch_level_zero_bytes"}
    timing = {"clock": "torch.xpu.Event device elapsed time", "warm_cycles_per_arm": 20,
              "cpu_work_inside_event_interval": False, "control_geometry": {"workgroups": 8, "simd32_subgroups": 64},
              "candidate_geometry": {"workgroups": 48, "simd32_subgroups": 96},
              "passed": True, "candidate_block_wins": 31,
              "median_saving_ms_per_cycle": blocks[0]["saving_ms_per_47_layer_cycle"], "blocks": 31,
              "cycles_per_arm": 64, "layers_per_cycle": 47, "arm_order": "A-B-B-A",
              "rotation": "(block*47)%256", "selected_gather_launches_per_cycle": {"control": 47, "candidate": 47},
              "blocks_detail": blocks}
    return {"format": validator.CARD_RESULT_FORMAT, "status": "component_timing_pass_pending_mandatory_counters",
            "passed": True, "rank": rank, "physical": physical,
            "authorization": {"path": packet["packet_path"], "sha256": validator.sha_bytes(validator.canonical_json(packet))},
            "runtime_binding": runtime, "native_modules": native, "retained_fixture_before": retained,
            "retained_fixture_after": copy.deepcopy(retained), "runtime_directories": sorted(expected_dirs),
            "pre_epochs": [epoch(index) for index in range(256)],
            "post_epochs": [epoch(index) for index in range(256, 288)], "timing": timing,
            "terminal": {"status": "component_timing_pass_pending_mandatory_counters", "passed": True,
                         "endpoint_authorized": False, "phase_b_required": True}}


class SchemaTests(unittest.TestCase):
    def test_accepts_complete_nonrecursive_pair(self) -> None:
        phase_a, phase_b = pair()
        self.assertIs(validator.validate_common(phase_a["body"]["common"]), phase_a["body"]["common"])
        self.assertEqual(validator.validate_phase_a_packet(phase_a, A_PATH), phase_a)
        validator.verify_mutual_packets(phase_a, phase_b)

    def test_rejects_each_common_top_level_key_change(self) -> None:
        for key in validator.COMMON_KEYS:
            value = common()
            value["unexpected"] = True
            with self.assertRaises(RuntimeError, msg=f"extra key near {key}"):
                validator.validate_common(value)
            value = common()
            del value[key]
            with self.assertRaises(RuntimeError, msg=f"missing {key}"):
                validator.validate_common(value)

    def test_rejects_fixture_and_bundle_corruption(self) -> None:
        mutations = (
            lambda value: value["native_bundle"]["library_sha256"].pop(validator.LIBRARIES[0]),
            lambda value: value["native_bundle"].update(storage={"mount_source": "/dev/sda1", "fstype": "ext4", "major_minor": "8:1"}),
            lambda value: value["fixture"]["records"]["weights"]["per_epoch_sha256"].pop(),
            lambda value: value["fixture"]["records"].pop("norm_weight"),
            lambda value: value["fixture"]["canonical_route_map"].update(path="/media/usb/map"),
            lambda value: value["cards"][0].update(drm_card="/dev/dri/card1"),
            lambda value: value["runtime_identity"]["observed_identity"]["files"].pop("torch_init"),
        )
        for mutate in mutations:
            value = common()
            mutate(value)
            with self.assertRaises(RuntimeError):
                validator.validate_common(value)

    def test_rejects_packet_recursion_and_binding_corruption(self) -> None:
        mutations = (
            lambda a, b: a["body"].update(paired_phase_b_packet_sha256=digest("bad")),
            lambda a, b: a["body"]["phase_b_reference"].update(full_packet_sha256=digest("forbidden")),
            lambda a, b: b["body"]["phase_a_binding"].update(phase_a_body_sha256=digest("wrong")),
            lambda a, b: b["body"]["common"].update(format="wrong"),
            lambda a, b: a.update(packet_path=str(ROOT / "packets/other-a.json")),
        )
        for mutate in mutations:
            phase_a, phase_b = pair()
            mutate(phase_a, phase_b)
            with self.assertRaises(RuntimeError):
                validator.verify_mutual_packets(phase_a, phase_b)

    def test_rejects_wrong_full_b_wrapper_hash_and_nonbyte_identical_common(self) -> None:
        phase_a, phase_b = pair()
        phase_a["paired_phase_b_packet_sha256"] = digest("incorrect")
        with self.assertRaises(RuntimeError):
            validator.verify_mutual_packets(phase_a, phase_b)
        phase_a, phase_b = pair()
        phase_b["body"]["common"] = copy.deepcopy(phase_a["body"]["common"])
        phase_b["body"]["common"]["logical_cycle"]["minimum_wins"] = 29
        phase_b["body"]["common_binding_sha256"] = validator.common_hash(phase_b["body"]["common"])
        phase_b["body"]["phase_a_binding"]["common_binding_sha256"] = phase_b["body"]["common_binding_sha256"]
        phase_a["paired_phase_b_packet_sha256"] = validator.sha_bytes(validator.canonical_json(phase_b))
        with self.assertRaises(RuntimeError):
            validator.verify_mutual_packets(phase_a, phase_b)

    def test_canonical_read_rejects_duplicate_noncanonical_and_symlink(self) -> None:
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"a":1,"a":2}\n', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                validator.read_canonical_json(duplicate, "duplicate")
            noncanonical = root / "noncanonical.json"
            noncanonical.write_text('{"b":2, "a":1}\n', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                validator.read_canonical_json(noncanonical, "noncanonical")
            target = root / "target.json"
            target.write_text('{"a":1}\n', encoding="utf-8")
            link = root / "link.json"
            link.symlink_to(target)
            with self.assertRaises(RuntimeError):
                validator.read_canonical_json(link, "link")

    def test_artifact_helper_fails_before_any_usb_read(self) -> None:
        with self.assertRaises(RuntimeError):
            validator._assert_internal_nvme(Path("/media/usb/packet.json"), "USB test")

    def test_module_has_no_accelerator_or_runtime_import(self) -> None:
        tree = ast.parse(Path(validator.__file__).read_text(encoding="utf-8"))
        forbidden = {"torch", "vllm", "sycl", "intel_extension_for_pytorch", "subprocess", "importlib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse({alias.name.split(".")[0] for alias in node.names} & forbidden)
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or "").split(".")[0], forbidden)


class RuntimeStaticSafetyTests(unittest.TestCase):
    """These tests never import the late runtime or execute an XPU operation."""

    TOOLS = Path(validator.__file__).parent

    def _source(self, name: str) -> str:
        return (self.TOOLS / name).read_text(encoding="utf-8")

    def test_late_runtime_has_no_top_level_accelerator_import(self) -> None:
        tree = ast.parse(self._source("laguna_m8_gather_sharded_phase_a_runtime.py"))
        for node in tree.body:
            if isinstance(node, ast.Import):
                self.assertNotIn("torch", {item.name.split(".")[0] for item in node.names})
            if isinstance(node, ast.ImportFrom):
                self.assertNotEqual((node.module or "").split(".")[0], "torch")
        source = self._source("laguna_m8_gather_sharded_phase_a_runtime.py")
        for literal in ("os.pread", "/proc/self/fd/", "laguna_m8_moe_gather_sharded",
                        "moe_gather", "laguna_m8_scale_add", "rank_order_bf16_sum",
                        "fused_add_rms_norm", "A-B-B-A", "CYCLES_PER_ARM = 20, 31, 64"):
            self.assertIn(literal, source)
        self.assertNotIn("importlib", source)
        self.assertLess(source.index('"libgdn_attn_kernels_xe_2.so"'), source.index('"shared-_xpu_C.abi3.so"'))
        self.assertIn("ctypes.RTLD_GLOBAL", source)
        self.assertIn("unsealed or replaced native mapping", source)

    def test_one_shot_capability_is_packet_rank_bound_and_eof_limited(self) -> None:
        read_fd, write_fd = os.pipe()
        os.close(write_fd)
        with self.assertRaises((OSError, RuntimeError)):
            validator._consume_capability(read_fd, "a" * 64, 2, Path("/tmp/no-root"), -1, -1, -1, {}, A_PATH)
        try:
            os.close(read_fd)
        except OSError:
            pass

    def test_direct_same_process_seqpacket_is_rejected_as_wrong_peer(self) -> None:
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        parent.send(b"{}\n")
        parent.close()
        with self.assertRaises(RuntimeError):
            validator._consume_capability(child.detach(), "a" * 64, 0, Path("/tmp/no-root"), -1, -1, -1, {}, A_PATH)

    def test_coordinator_precreates_exact_roots_without_recursion(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
                coordinator.phase_a, "assert_live_internal_nvme", return_value=None):
            campaign = Path(directory) / "campaign"
            campaign_fd, card_fds = coordinator._prepare_campaign_roots(campaign)
            try:
                self.assertEqual(sorted(path.name for path in campaign.iterdir()), [f"card{rank}" for rank in range(4)])
                for rank in range(4):
                    self.assertEqual(sorted(path.name for path in (campaign / f"card{rank}").iterdir()), ["evidence", "scratch"])
            finally:
                for descriptor in card_fds:
                    os.close(descriptor)
                os.close(campaign_fd)

    def test_fd_anchored_evidence_is_immutable_and_symlink_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                digest_value = coordinator._write_at(descriptor, "terminal.json", {"passed": False})
                self.assertEqual(digest_value, hashlib.sha256(validator.canonical_json({"passed": False})).hexdigest())
                self.assertEqual((root / "terminal.json").stat().st_mode & 0o777, 0o444)
                (root / "target").write_text("x", encoding="utf-8")
                (root / "link").symlink_to(root / "target")
                with self.assertRaises(FileExistsError):
                    coordinator._write_at(descriptor, "link", {"passed": False})
            finally:
                os.close(descriptor)

    def test_campaign_seal_rejects_unregistered_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
                coordinator.phase_a, "assert_live_internal_nvme", return_value=None):
            campaign = Path(directory) / "campaign"
            campaign_fd, card_fds = coordinator._prepare_campaign_roots(campaign)
            try:
                coordinator._write_at(campaign_fd, "campaign-start.json", {"passed": False})
                coordinator._write_at(campaign_fd, "campaign-terminal.json", {"passed": False})
                coordinator._write_at(campaign_fd, "unregistered.json", {"forged": True})
                with self.assertRaises(RuntimeError):
                    coordinator._seal_namespace(campaign_fd, card_fds)
            finally:
                for descriptor in card_fds:
                    os.close(descriptor)
                os.close(campaign_fd)

    def test_stage0_helper_closure_rejects_missing_or_wrong_digest(self) -> None:
        with self.assertRaises(RuntimeError):
            validator._load_stage0_validator({"tools": {"local_helper_closure": []}})

    def test_card_result_validator_requires_every_registered_gate(self) -> None:
        source = self._source("run_laguna_m8_gather_sharded_phase_a.py")
        for literal in ("CARD_RESULT_FORMAT", "PRE_EPOCHS, POST_EPOCHS = 256, 32",
                        "candidate_block_wins", "median_saving_ms_per_cycle",
                        "fused_add_rms_norm_hidden", "fused_add_rms_norm_residual",
                        "phase_b_required"):
            self.assertIn(literal, source)

    def test_card_result_deep_corruptions_fail(self) -> None:
        packet, _unused = pair()
        baseline = valid_card_result(packet)
        self.assertIs(validator.validate_card_result(baseline, packet, 0), baseline)
        mutations = (
            lambda value: value["runtime_binding"].update(torch_uuid_bytes_hex="00" * 16),
            lambda value: value["native_modules"][validator.LIBRARIES[0]].update(rtld_global=True),
            lambda value: value["retained_fixture_before"]["weights"].update(sha256=digest("forged")),
            lambda value: value["pre_epochs"][0]["outputs"].update(control_gather=digest("forged")),
            lambda value: value["pre_epochs"][0].update(raw_bf16_classification={**value["pre_epochs"][0]["raw_bf16_classification"], "finite_normal": 0}),
            lambda value: value["timing"].update(median_saving_ms_per_cycle=float("nan")),
        )
        for mutate in mutations:
            forged = copy.deepcopy(baseline)
            mutate(forged)
            with self.assertRaises(RuntimeError):
                validator.validate_card_result(forged, packet, 0)

    def test_exact_environment_rejects_extra_missing_and_mutated_selector(self) -> None:
        env = validator.expected_environment(0, ROOT / "runs/card0")
        self.assertEqual(env["LD_PRELOAD"], "")
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(env["ONEAPI_DEVICE_SELECTOR"], "level_zero:0")
        for mutate in (lambda value: value.pop("PYTHONSAFEPATH"),
                       lambda value: value.update(LD_LIBRARY_PATH="/tmp/evil"),
                       lambda value: value.update(UNREGISTERED="1")):
            value = dict(env)
            mutate(value)
            self.assertNotEqual(value, validator.expected_environment(0, ROOT / "runs/card0"))

    def test_env_i_safe_path_import_closure_is_cpu_only(self) -> None:
        env = validator.expected_environment(0, ROOT / "runs/card0")
        raw = Path(validator.__file__).read_bytes()
        descriptor = coordinator._sealed_source(raw, "phase-a-test-runner")
        try:
            command = [validator.RUNTIME_IDENTITY["observed_identity"]["python_executable"], "-I", "-S",
                       f"/proc/self/fd/{descriptor}", "--help"]
            completed = subprocess.run(command, env=env, cwd="/", stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20,
                                       check=False, pass_fds=(descriptor,))
            self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", errors="replace"))
            self.assertEqual(fcntl.fcntl(descriptor, coordinator.F_GET_SEALS) & coordinator.REQUIRED_SEALS,
                             coordinator.REQUIRED_SEALS)
        finally:
            os.close(descriptor)

    def test_runtime_directory_bootstrap_rejects_reuse_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "card"
            root.mkdir()
            env = validator.expected_environment(0, root)
            created = validator._prepare_runtime_directories(root, env)
            self.assertIn("scratch/runtime/home", created)
            with self.assertRaises(RuntimeError):
                validator._prepare_runtime_directories(root, env)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "card"
            (root / "scratch/runtime").mkdir(parents=True)
            (root / "scratch/runtime/home").symlink_to(Path(directory))
            with self.assertRaises(RuntimeError):
                validator._prepare_runtime_directories(root, validator.expected_environment(0, root))

    def test_live_idle_gate_requires_all_65_mocked_installed_schema_samples(self) -> None:
        calls = []
        def snapshot() -> dict:
            calls.append(1)
            stdout = b'{"device_util_by_proc_list":[]}\n'
            empty = hashlib.sha256(b"").hexdigest()
            return {"format": operational.FORMAT, "status": "passed", "observed_utc": "x", "argv": ["/usr/bin/xpu-smi", "ps", "-j"], "environment": operational.OBSERVER_ENVIRONMENT, "timeout_seconds": 20.0, "xpu_smi": {"configured_path": "/usr/bin/xpu-smi", "resolved_path": "/usr/bin/xpu-smi", "sha256": operational.EXPECTED_XPU_SMI_SHA256, "device": 1, "inode": 2}, "child_identity": {"process_id": 3, "proc_dir_fd_acquired": True, "pidfd_acquired": False, "proc_exe_resolved": "/usr/bin/xpu-smi", "executable_device": 1, "executable_inode": 2}, "raw_capture": {"stdout_bytes": len(stdout), "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stdout_base64": base64.b64encode(stdout).decode(), "stderr_bytes": 0, "stderr_sha256": empty, "stderr_base64": ""}, "idle": {"accepted_mode": "empty", "row_count": 0, "device_ids": [], "sanitized_payload": {"device_util_by_proc_list": []}}}
        ticks = iter(range(1000))
        report = coordinator._live_idle_gate(snapshot=snapshot, sleep=lambda _seconds: None, monotonic=lambda: float(next(ticks)))
        self.assertEqual(len(calls), 66)
        self.assertEqual(report["strict_idle_seconds"], 65)
        with self.assertRaises(RuntimeError):
            coordinator._live_idle_gate(snapshot=lambda: {"format": "wrong", "status": "passed"}, sleep=lambda _seconds: None)
        forged = snapshot()
        forged["raw_capture"]["stdout_sha256"] = digest("forged")
        with self.assertRaises(RuntimeError):
            coordinator._validate_idle_snapshot(forged)
        forged = snapshot()
        forged["idle"]["row_count"] = 1
        with self.assertRaises(RuntimeError):
            coordinator._validate_idle_snapshot(forged)


if __name__ == "__main__":
    unittest.main()
