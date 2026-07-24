#!/usr/bin/env python3
"""CPU-only anti-forgery tests for the component analyzer and timed loop."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

import analyze_laguna_shared_gate_up_mm_component as analyzer
import gate_laguna_shared_gate_up_mm_component as c
import run_laguna_shared_gate_up_mm_component as runner
import run_laguna_shared_gate_up_mm_stage0 as stage0_runner


ROOT = pathlib.Path(__file__).parent
FIXTURE = pathlib.Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations/"
    "shared-gate-up-m8-stage0-fixture-v1-79577851f.json"
)
STAGE0_RESULT = pathlib.Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/"
    "shared-gate-up-m8-stage0-card0-79577851f-v1/stage0-result.json"
)


def _metadata(pointer: int, shape: list[int], stride: list[int]) -> dict:
    size = 1
    for dimension in shape:
        size *= dimension
    return {
        "data_ptr": pointer,
        "shape": shape,
        "stride": stride,
        "dtype": "torch.bfloat16",
        "numel": size,
        "element_size": 2,
    }


def _timing_slot(fixture: dict, slot: int, *, post: bool) -> dict:
    tensors = {tensor["label"]: tensor for tensor in fixture["epochs"][slot]["tensors"]}
    rows_shape = tensors["hidden_input"]["shape"]
    gate_weight_shape = tensors["gate_weight"]["shape"]
    up_weight_shape = tensors["up_weight"]["shape"]
    rows = _metadata(100_000_000 + slot * 100_000, rows_shape, [rows_shape[1], 1])
    gate_weight = _metadata(
        200_000_000 + slot * 100_000,
        gate_weight_shape,
        [gate_weight_shape[1], 1],
    )
    up_weight = _metadata(
        300_000_000 + slot * 100_000,
        up_weight_shape,
        [up_weight_shape[1], 1],
    )
    rows["raw_bf16_le_sha256"] = tensors["hidden_input"]["raw_bf16_le_sha256"]
    gate_weight["raw_bf16_le_sha256"] = tensors["gate_weight"][
        "raw_bf16_le_sha256"
    ]
    up_weight["raw_bf16_le_sha256"] = tensors["up_weight"]["raw_bf16_le_sha256"]
    gate_output_raw = hashlib.sha256(f"timing-gate-output-{slot}".encode()).hexdigest()
    up_output_raw = hashlib.sha256(f"timing-up-output-{slot}".encode()).hexdigest()
    gate_control = _metadata(
        400_000_000 + slot * 100_000,
        [rows_shape[0], 1, gate_weight_shape[0]],
        [gate_weight_shape[0], gate_weight_shape[0], 1],
    )
    up_control = _metadata(
        500_000_000 + slot * 100_000,
        [rows_shape[0], 1, up_weight_shape[0]],
        [up_weight_shape[0], up_weight_shape[0], 1],
    )
    gate_candidate = _metadata(
        600_000_000 + slot * 100_000,
        [rows_shape[0], gate_weight_shape[0]],
        [gate_weight_shape[0], 1],
    )
    up_candidate = _metadata(
        700_000_000 + slot * 100_000,
        [rows_shape[0], up_weight_shape[0]],
        [up_weight_shape[0], 1],
    )
    gate_control["raw_bf16_le_sha256"] = gate_output_raw
    gate_candidate["raw_bf16_le_sha256"] = gate_output_raw
    up_control["raw_bf16_le_sha256"] = up_output_raw
    up_candidate["raw_bf16_le_sha256"] = up_output_raw
    return {
        "slot": slot,
        "rows": rows,
        "gate_weight": gate_weight,
        "up_weight": up_weight,
        "rows_bmm": _metadata(
            rows["data_ptr"],
            [rows_shape[0], 1, rows_shape[1]],
            [rows_shape[1], rows_shape[1], 1],
        ),
        "gate_weight_t": _metadata(
            gate_weight["data_ptr"],
            [gate_weight_shape[1], gate_weight_shape[0]],
            [1, gate_weight_shape[1]],
        ),
        "up_weight_t": _metadata(
            up_weight["data_ptr"],
            [up_weight_shape[1], up_weight_shape[0]],
            [1, up_weight_shape[1]],
        ),
        "gate_expanded": _metadata(
            gate_weight["data_ptr"],
            [rows_shape[0], gate_weight_shape[1], gate_weight_shape[0]],
            [0, 1, gate_weight_shape[1]],
        ),
        "up_expanded": _metadata(
            up_weight["data_ptr"],
            [rows_shape[0], up_weight_shape[1], up_weight_shape[0]],
            [0, 1, up_weight_shape[1]],
        ),
        "gate_control": gate_control,
        "up_control": up_control,
        "gate_candidate": gate_candidate,
        "up_candidate": up_candidate,
    }


def _timing(fixture: dict) -> dict:
    blocks = []
    for index in range(31):
        a1_ns, a2_ns, b1_ns, b2_ns = 128_000_000, 140_800_000, 108_800_000, 115_200_000
        a1, a2, b1, b2 = (
            a1_ns / 64 / 1_000_000,
            a2_ns / 64 / 1_000_000,
            b1_ns / 64 / 1_000_000,
            b2_ns / 64 / 1_000_000,
        )
        control, candidate = (a1 + a2) / 2, (b1 + b2) / 2
        blocks.append(
            {
                "block": index,
                "rotation": (index * 11) % 47,
                "slot_order": [((index * 11) % 47 + slot) % 47 for slot in range(47)],
                "A1_control_elapsed_ns": a1_ns,
                "A1_control_ms": a1,
                "B1_candidate_elapsed_ns": b1_ns,
                "B1_candidate_ms": b1,
                "B2_candidate_elapsed_ns": b2_ns,
                "B2_candidate_ms": b2,
                "A2_control_elapsed_ns": a2_ns,
                "A2_control_ms": a2,
                "paired_control_ms": control,
                "paired_candidate_ms": candidate,
                "saving_ms": control - candidate,
            }
        )
    pre_slots = [_timing_slot(fixture, index, post=False) for index in range(47)]
    post_slots = [_timing_slot(fixture, index, post=True) for index in range(47)]
    metadata_keys = (
        "data_ptr",
        "shape",
        "stride",
        "dtype",
        "numel",
        "element_size",
    )
    return {
        "passed": True,
        "timing_label": "allocation_free_isolated_gate_up_GEMM_pair",
        "target_layers_per_cycle": 47,
        "projections_per_layer": 2,
        "projection_calls_per_cycle": 94,
        "weight_bytes_each": 1572864,
        "distinct_inputs": 47,
        "distinct_weights": 94,
        "preallocated_unique_inputs": True,
        "output_ring_slots_per_projection": 47,
        "output_ring_count": 4,
        "distinct_preallocated_output_buffers": True,
        "warm_cycles_per_arm": 20,
        "blocks": 31,
        "cycles_per_arm_per_block": 64,
        "calls_per_arm": 6016,
        "eviction_bytes_once_per_arm": 134217728,
        "synchronization": "arm_boundaries_only",
        "arm_order": "A-B-B-A",
        "candidate_block_wins": 31,
        "median_saving_ms_per_cycle": 0.35,
        "buffer_proof": {
            "input_slots": [proof["rows"]["data_ptr"] for proof in pre_slots],
            "gate_weight_slots": [
                proof["gate_weight"]["data_ptr"] for proof in pre_slots
            ],
            "up_weight_slots": [
                proof["up_weight"]["data_ptr"] for proof in pre_slots
            ],
            "gate_control_output_slots": [
                proof["gate_control"]["data_ptr"] for proof in pre_slots
            ],
            "up_control_output_slots": [
                proof["up_control"]["data_ptr"] for proof in pre_slots
            ],
            "gate_candidate_output_slots": [
                proof["gate_candidate"]["data_ptr"] for proof in pre_slots
            ],
            "up_candidate_output_slots": [
                proof["up_candidate"]["data_ptr"] for proof in pre_slots
            ],
            "gate_control_layout": {
                key: pre_slots[0]["gate_control"][key] for key in metadata_keys
            },
            "up_control_layout": {
                key: pre_slots[0]["up_control"][key] for key in metadata_keys
            },
            "gate_candidate_layout": {
                key: pre_slots[0]["gate_candidate"][key] for key in metadata_keys
            },
            "up_candidate_layout": {
                key: pre_slots[0]["up_candidate"][key] for key in metadata_keys
            },
            "pre_timing_slots": pre_slots,
            "post_timing_slots": post_slots,
            "nonalias": True,
        },
        "preflight_proof": [
            {
                "slot": index,
                "gate_control_out_supplied_ptr": pre_slots[index]["gate_control"][
                    "data_ptr"
                ],
                "gate_control_out_returned_ptr": pre_slots[index]["gate_control"][
                    "data_ptr"
                ],
                "up_control_out_supplied_ptr": pre_slots[index]["up_control"][
                    "data_ptr"
                ],
                "up_control_out_returned_ptr": pre_slots[index]["up_control"][
                    "data_ptr"
                ],
                "gate_candidate_out_supplied_ptr": pre_slots[index]["gate_candidate"][
                    "data_ptr"
                ],
                "gate_candidate_out_returned_ptr": pre_slots[index]["gate_candidate"][
                    "data_ptr"
                ],
                "up_candidate_out_supplied_ptr": pre_slots[index]["up_candidate"][
                    "data_ptr"
                ],
                "up_candidate_out_returned_ptr": pre_slots[index]["up_candidate"][
                    "data_ptr"
                ],
                "gate_literal_raw_uint16_equal": True,
                "up_literal_raw_uint16_equal": True,
                "gate_control_out_raw_uint16_equal": True,
                "up_control_out_raw_uint16_equal": True,
                "gate_candidate_out_raw_uint16_equal": True,
                "up_candidate_out_raw_uint16_equal": True,
                "input_metadata_unchanged": True,
                "weight_metadata_unchanged": True,
                "output_metadata_unchanged": True,
            }
            for index in range(47)
        ],
        "blocks_detail": blocks,
    }


class SchemaOnlyComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (FIXTURE.is_file() and STAGE0_RESULT.is_file()):
            raise unittest.SkipTest("sealed CPU fixture/result not present")
        cls.fixture = json.loads(FIXTURE.read_text())
        stage0 = json.loads(STAGE0_RESULT.read_text())
        cls.entries = stage0["epochs"]
        if len(cls.entries) != 128:
            raise unittest.SkipTest("sealed stage-zero exact epochs unavailable")

    def packet(self) -> dict:
        cards = []
        for rank, physical in c.CARDS.items():
            root = f"/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/unit/card{rank}"
            cards.append(
                {
                    "rank": rank,
                    "physical": physical,
                    "result": f"{root}/component-result.json",
                    "output_root": root,
                    "environment": c.environment(root, rank),
                }
            )
        return {
            "packet_path": "/home/steve/llm-optimizations/data/unit.json",
            "cards": cards,
        }

    def result(self) -> tuple[dict, dict]:
        packet = self.packet()
        digest = hashlib.sha256(c.canonical(packet) + b"\n").hexdigest()
        pre = [
            {"packet_sha256": digest, "rank": 0, "entry": copy.deepcopy(value)}
            for value in self.entries
        ]
        post = copy.deepcopy(pre[:32])
        timing = _timing(self.fixture)
        timing.update({"packet_sha256": digest, "rank": 0})
        checkpoints = (
            [
                "pre-tensor-identity-checkpoint.json",
                "tensor-work-started-checkpoint.json",
                "runtime-card-binding-checkpoint.json",
                "constructor-scope-proof.json",
                "dispatch-proof.json",
            ]
            + [f"pre-epochs/epoch-{i:03d}.json" for i in range(128)]
            + ["timing.json"]
            + [f"post-epochs/epoch-{i:03d}.json" for i in range(32)]
        )
        return {
            "format": "laguna-shared-gate-up-m8-four-card-component-result-v1",
            "status": "component-card-pass",
            "passed": True,
            "rank": 0,
            "physical": packet["cards"][0]["physical"],
            "packet_path": packet["packet_path"],
            "packet_sha256": digest,
            "downstream": dict(c.FALSE_ACTIONS),
            "tensor_work_started": True,
            "checkpoints": checkpoints,
            "checkpoint_sha256": {name: "0" * 64 for name in checkpoints},
            "constructor_scope_proof": {},
            "dispatch_proof": {},
            "actual_forward_proof": {},
            "runtime_card_binding": {},
            "observed": {},
            "pre_exactness": pre,
            "timing": timing,
            "post_exactness": post,
            "failure": None,
        }, packet

    def valid(self, result: dict, packet: dict) -> None:
        with (
            patch.object(analyzer.contract, "validate"),
            patch.object(analyzer.stage0, "validate_fixture_manifest"),
        ):
            analyzer.validate_schema_for_cpu_tests(result, self.fixture, packet)

    def rejects(self, edit) -> None:
        result, packet = self.result()
        edit(result, packet)
        with self.assertRaises(RuntimeError):
            self.valid(result, packet)

    def test_schema_fixture_is_explicitly_not_production_acceptance(self):
        result, packet = self.result()
        self.valid(result, packet)
        tree = ast.parse(
            (ROOT / "analyze_laguna_shared_gate_up_mm_component.py").read_text()
        )
        prod = next(
            x
            for x in ast.walk(tree)
            if isinstance(x, ast.FunctionDef) and x.name == "validate_production"
        )
        calls = {ast.unparse(x.func) for x in ast.walk(prod) if isinstance(x, ast.Call)}
        self.assertTrue(
            {
                "_packet_lineage",
                "_runtime_and_sources",
                "_stage0",
                "_strict_tree",
            }.issubset(calls)
        )

    def test_tampers_result_schema_and_action_escalation(self):
        self.rejects(lambda r, p: r.__setitem__("forgery", True))
        self.rejects(
            lambda r, p: r["downstream"].__setitem__("endpoint_authorized", True)
        )
        self.rejects(
            lambda r, p: r.__setitem__(
                "status", "component_failed_stop_before_counters"
            )
        )
        self.rejects(lambda r, p: r["checkpoints"].pop())

    def test_tampers_raw_exactness_uniqueness_and_replay(self):
        self.rejects(
            lambda r, p: r["pre_exactness"][0]["entry"]["comparisons"].__setitem__(
                "gate", {"raw_uint16_equal": False, "torch_equal": False}
            )
        )
        self.rejects(
            lambda r, p: r["pre_exactness"][1].__setitem__(
                "entry", copy.deepcopy(r["pre_exactness"][0]["entry"])
            )
        )
        self.rejects(
            lambda r, p: r["post_exactness"][0]["entry"]["comparisons"].__setitem__(
                "gate", {"raw_uint16_equal": False, "torch_equal": False}
            )
        )
        self.rejects(
            lambda r, p: r["pre_exactness"][0].__setitem__("packet_sha256", "f" * 64)
        )

    def test_tampers_timing_protocol_buffers_preflight_and_abba(self):
        self.rejects(
            lambda r, p: r["timing"]["buffer_proof"][
                "up_candidate_output_slots"
            ].__setitem__(0, 300)
        )
        self.rejects(
            lambda r, p: r["timing"]["preflight_proof"][0].__setitem__(
                "up_control_out_raw_uint16_equal", False
            )
        )
        self.rejects(
            lambda r, p: r["timing"]["blocks_detail"][0].__setitem__(
                "A1_control_ms", 0.0
            )
        )
        self.rejects(lambda r, p: r["timing"].__setitem__("candidate_block_wins", 28))
        self.rejects(lambda r, p: r["timing"].__setitem__("arm_order", "A-B-A-B"))
        self.rejects(
            lambda r, p: r["timing"]["blocks_detail"][0].__setitem__(
                "A1_control_elapsed_ns", 0
            )
        )
        self.rejects(
            lambda r, p: r["timing"]["blocks_detail"][0].__setitem__(
                "B1_candidate_elapsed_ns", True
            )
        )
        self.rejects(
            lambda r, p: r["timing"]["blocks_detail"][0].__setitem__(
                "A2_control_ms", 123.0
            )
        )
        self.rejects(
            lambda r, p: r["timing"]["blocks_detail"][0]["slot_order"].reverse()
        )
        self.rejects(
            lambda r, p: r["timing"]["buffer_proof"]["pre_timing_slots"][0][
                "rows"
            ].__setitem__("raw_bf16_le_sha256", "0" * 64)
        )
        self.rejects(
            lambda r, p: r["timing"]["buffer_proof"]["post_timing_slots"][0][
                "rows"
            ].__setitem__("raw_bf16_le_sha256", "0" * 64)
        )
        self.rejects(
            lambda r, p: r["timing"]["buffer_proof"]["post_timing_slots"][0][
                "up_weight"
            ].__setitem__("data_ptr", 1)
        )
        self.rejects(
            lambda r, p: r["timing"]["buffer_proof"]["post_timing_slots"][0][
                "up_candidate"
            ].__setitem__("raw_bf16_le_sha256", "0" * 64)
        )

    def test_checkpoint_hash_packet_binding_and_exact_inventory_are_not_trusted(self):
        result, _ = self.result()
        digest = result["packet_sha256"]
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            values = {
                "pre-tensor-identity-checkpoint.json": {
                    "format": "laguna-shared-gate-up-m8-component-pre-tensor-v2",
                    "packet_sha256": digest,
                    "rank": 0,
                    "tensor_work_started": False,
                    "observed": result["observed"],
                },
                "tensor-work-started-checkpoint.json": {
                    "format": "laguna-shared-gate-up-m8-component-tensor-start-v2",
                    "packet_sha256": digest,
                    "rank": 0,
                    "tensor_work_started": True,
                },
                "runtime-card-binding-checkpoint.json": {
                    "packet_sha256": digest,
                    "rank": 0,
                },
                "constructor-scope-proof.json": result["constructor_scope_proof"],
                "dispatch-proof.json": result["dispatch_proof"],
                "timing.json": result["timing"],
            }
            for phase, entries in (
                ("pre", result["pre_exactness"]),
                ("post", result["post_exactness"]),
            ):
                for envelope in entries:
                    values[
                        f"{phase}-epochs/epoch-{envelope['entry']['epoch']:03d}.json"
                    ] = envelope
            # Scope/dispatch were deliberately empty in the schema fixture;
            # add only the immutable packet/rank binding demanded by the file
            # verifier, not production scope acceptance.
            values["constructor-scope-proof.json"] = {
                "packet_sha256": digest,
                "rank": 0,
            }
            values["dispatch-proof.json"] = {"packet_sha256": digest, "rank": 0}
            result["runtime_card_binding"] = values[
                "runtime-card-binding-checkpoint.json"
            ]
            result["constructor_scope_proof"] = values["constructor-scope-proof.json"]
            result["dispatch_proof"] = values["dispatch-proof.json"]
            for relative, value in values.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(c.canonical(value) + b"\n")
            result["checkpoint_sha256"] = {
                relative: analyzer.sha(root / relative)
                for relative in result["checkpoints"]
            }
            analyzer._checkpoints(root, result, digest, 0)
            (root / "timing.json").write_bytes(
                c.canonical({"packet_sha256": digest, "rank": 0, "forged": True})
                + b"\n"
            )
            with self.assertRaises(RuntimeError):
                analyzer._checkpoints(root, result, digest, 0)

    def test_tree_rejects_unknown_files_and_empty_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            (root / "card0").mkdir()
            (root / "card0" / "a.json").write_text("{}\n")
            analyzer._strict_tree(root, {"card0/a.json"})
            (root / "unexpected-empty").mkdir()
            with self.assertRaises(RuntimeError):
                analyzer._strict_tree(root, {"card0/a.json"})


class TimedLoopStaticTests(unittest.TestCase):
    def test_timing_exactness_helper_is_bound_to_actual_stage0_runner(self):
        self.assertFalse(hasattr(runner.stage0, "_raw_equal"))
        self.assertTrue(callable(stage0_runner._raw_equal))
        tree = ast.parse((ROOT / "run_laguna_shared_gate_up_mm_component.py").read_text())
        timing = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_timing"
        )
        imports = {
            (alias.name, alias.asname)
            for node in ast.walk(timing)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertIn(("run_laguna_shared_gate_up_mm_stage0", "actual"), imports)
        raw_equal_calls = [
            ast.unparse(node.func)
            for node in ast.walk(timing)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func).endswith("._raw_equal")
        ]
        self.assertEqual(raw_equal_calls, ["actual._raw_equal"] * 6)

    def test_runtime_xpu_uuid_wrapper_is_exactly_bound(self):
        physical_uuid = uuid.UUID(c.CARDS[0]["uuid"])
        torch_uuid = uuid.UUID(bytes=physical_uuid.bytes[::-1])

        class _XPUuuid:
            __module__ = "torch._C"

            def __init__(self, raw: bytes, text: str | None = None):
                self.bytes = list(raw)
                self.text = text

            def __str__(self):
                if self.text is not None:
                    return self.text
                return str(uuid.UUID(bytes=bytes(self.bytes)))

        parsed, raw = runner._parse_runtime_uuid(_XPUuuid(torch_uuid.bytes))
        self.assertEqual(parsed, torch_uuid)
        self.assertEqual(raw, torch_uuid.bytes)
        with self.assertRaisesRegex(RuntimeError, "not 16 bytes"):
            runner._parse_runtime_uuid(_XPUuuid(torch_uuid.bytes[:-1]))
        invalid_octets = _XPUuuid(torch_uuid.bytes)
        invalid_octets.bytes[-1] = True
        with self.assertRaisesRegex(RuntimeError, "invalid octet"):
            runner._parse_runtime_uuid(invalid_octets)
        with self.assertRaisesRegex(RuntimeError, "text/bytes disagree"):
            runner._parse_runtime_uuid(
                _XPUuuid(torch_uuid.bytes, "00000000-0000-0000-0000-000000000000")
            )

        def wrong_module_init(instance, raw: bytes):
            instance.bytes = list(raw)

        _XPUuuidWrongModule = type("_XPUuuid", (), {"__init__": wrong_module_init})
        with self.assertRaisesRegex(RuntimeError, "malformed"):
            runner._parse_runtime_uuid(_XPUuuidWrongModule(torch_uuid.bytes))

        class Probe:
            device = "xpu:0"

        class Properties:
            uuid = _XPUuuid(torch_uuid.bytes)

        class XPU:
            @staticmethod
            def is_available():
                return True

            @staticmethod
            def device_count():
                return 1

            @staticmethod
            def current_device():
                return 0

            @staticmethod
            def get_device_name(_index):
                return c.stage0.EXPECTED_DEVICE_NAME

            @staticmethod
            def get_device_properties(_index):
                return Properties()

        class Torch:
            xpu = XPU()
            __version__ = c.stage0.EXPECTED_RUNTIME_OBSERVED_IDENTITY["torch_version"]

            @staticmethod
            def empty(_shape, *, device):
                self.assertEqual(device, "xpu")
                return Probe()

        card = {"rank": 0, "physical": dict(c.CARDS[0])}
        observed = {"card_binding": {"sealed_preflight": True}}
        with patch.dict(
            runner.os.environ,
            {"ONEAPI_DEVICE_SELECTOR": "level_zero:0", "ZE_AFFINITY_MASK": "0"},
        ):
            binding = runner._runtime_binding(Torch(), card, observed)
        self.assertEqual(binding["runtime_uuid"], str(physical_uuid))
        self.assertEqual(binding["runtime_uuid_bytes_hex"], physical_uuid.hex)
        self.assertEqual(binding["torch_runtime_uuid"], str(torch_uuid))
        self.assertEqual(binding["torch_runtime_uuid_bytes_hex"], torch_uuid.hex)
        self.assertEqual(
            binding["runtime_uuid_mapping"],
            "xpu_smi_uuid_is_reverse_of_torch_level_zero_bytes",
        )

        Properties.uuid = _XPUuuid(
            bytes([torch_uuid.bytes[0] ^ 1]) + torch_uuid.bytes[1:]
        )
        with (
            patch.dict(
                runner.os.environ,
                {
                    "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
                    "ZE_AFFINITY_MASK": "0",
                },
            ),
            self.assertRaisesRegex(
                RuntimeError, "does not bind to preflight physical card"
            ),
        ):
            runner._runtime_binding(Torch(), card, observed)

    def test_runtime_identity_accepts_only_the_frozen_symlink_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            target = root / "runtime-v1.so"
            target.write_bytes(b"frozen-runtime-v1")
            link = root / "runtime.so.1"
            link.symlink_to(target.name)
            record = {
                "path": str(link),
                "resolved_path": str(target.resolve(strict=True)),
                "sha256": runner.sha(target),
            }
            packet = {
                "runtime": {
                    "python_executable": sys.executable,
                    "python_version": sys.version,
                    "files": {"level_zero_driver": record},
                }
            }
            self.assertEqual(
                runner._runtime_files(packet)["files"]["level_zero_driver"],
                record,
            )
            with self.assertRaisesRegex(RuntimeError, "required regular file missing"):
                runner._regular(link, "sealed evidence")

            replacement = root / "runtime-v2.so"
            replacement.write_bytes(b"changed-runtime-v2")
            link.unlink()
            link.symlink_to(replacement.name)
            with self.assertRaisesRegex(RuntimeError, "runtime file identity drift"):
                runner._runtime_files(packet)

    def test_analyzer_runtime_binding_and_forward_proofs_are_schema_exact(self):
        tree = ast.parse(
            (ROOT / "analyze_laguna_shared_gate_up_mm_component.py").read_text()
        )
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        binding = functions["_binding"]
        compared_sets = []
        for comparison in (
            node for node in ast.walk(binding) if isinstance(node, ast.Compare)
        ):
            if (
                isinstance(comparison.left, ast.Call)
                and ast.unparse(comparison.left) == "set(binding)"
                and len(comparison.comparators) == 1
                and isinstance(comparison.comparators[0], ast.Set)
            ):
                compared_sets.append(
                    {ast.literal_eval(item) for item in comparison.comparators[0].elts}
                )
        self.assertIn(
            {"format", "packet_sha256", "rank", "binding"}, compared_sets
        )
        binding_source = ast.unparse(binding)
        self.assertIn(
            "laguna-shared-gate-up-m8-component-runtime-card-binding-v1",
            binding_source,
        )
        self.assertIn("body == expected_body", binding_source)

        card_source = ast.unparse(functions["_card"])
        self.assertIn("'scope': scope['scope']", card_source)
        self.assertNotIn("actual_checkpoint_selected_LagunaMLP.forward", card_source)

    def test_inner_loop_and_its_callees_are_allocation_and_sync_free(self):
        tree = ast.parse((ROOT / "run_laguna_shared_gate_up_mm_component.py").read_text())
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        reachable, todo = set(), ["_cycles"]
        while todo:
            name = todo.pop()
            if name in reachable:
                continue
            reachable.add(name)
            for call in (
                x for x in ast.walk(functions[name]) if isinstance(x, ast.Call)
            ):
                called = ast.unparse(call.func).rsplit(".", 1)[-1]
                if called in functions:
                    todo.append(called)
        calls = [
            ast.unparse(call.func)
            for name in reachable
            for call in ast.walk(functions[name])
            if isinstance(call, ast.Call)
        ]
        banned = (
            "empty",
            "zeros",
            "clone",
            "copy",
            "sha",
            "hash",
            "fixture",
            "unsqueeze",
            "expand",
            "contiguous",
            "synchronize",
            "to",
        )
        self.assertFalse(
            [
                call
                for call in calls
                if any(word in call.rsplit(".", 1)[-1] for word in banned)
            ],
            calls,
        )
        arm = functions["_arm"]
        arm_calls = [
            ast.unparse(call.func)
            for call in ast.walk(arm)
            if isinstance(call, ast.Call)
        ]
        self.assertEqual(sum("synchronize" in call for call in arm_calls), 2, arm_calls)

    def test_runner_consumes_sealed_discovery_and_binds_torch_uuid(self):
        source = (ROOT / "run_laguna_shared_gate_up_mm_component.py").read_text()
        analyzer_source = (
            ROOT / "analyze_laguna_shared_gate_up_mm_component.py"
        ).read_text()
        self.assertNotIn('"xpu-smi"', source)
        self.assertNotIn("'xpu-smi'", source)
        self.assertIn("coordinator.validate_device_preflight", source)
        self.assertIn("torch.xpu.get_device_properties(0)", source)
        self.assertIn("runtime_uuid_bytes = torch_raw_uuid[::-1]", source)
        self.assertIn('runtime_uuid_text == card["physical"]["uuid"]', source)
        self.assertIn(
            "xpu_smi_uuid_is_reverse_of_torch_level_zero_bytes", analyzer_source
        )
        self.assertIn("runtime-card-binding-checkpoint.json", source)
        for checkpoint_format in (
            "laguna-shared-gate-up-m8-component-pre-tensor-v2",
            "laguna-shared-gate-up-m8-component-tensor-start-v2",
        ):
            self.assertIn(checkpoint_format, source)
            self.assertIn(checkpoint_format, analyzer_source)

    def test_warm_abba_raw_ns_and_eviction_boundaries_are_pinned(self):
        tree = ast.parse((ROOT / "run_laguna_shared_gate_up_mm_component.py").read_text())
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        arm_source = ast.unparse(functions["_arm"]).replace("'", '"')
        warm = (
            '_cycles(corpus, candidate, contract.PROTOCOL["warm_cycles_per_arm"], '
            "order, torch)"
        )
        self.assertLess(arm_source.index("evict.add_(1)"), arm_source.index(warm))
        self.assertLess(arm_source.index(warm), arm_source.index("start ="))
        self.assertEqual(arm_source.count("torch.xpu.synchronize()"), 2)
        self.assertEqual(arm_source.count("time.perf_counter_ns()"), 2)
        self.assertIn("cycles_per_arm_per_block", arm_source)
        self.assertIn('"elapsed_ns": elapsed', arm_source)

        timing_source = ast.unparse(functions["_timing"]).replace("'", '"')
        # The frozen protocol warms each individual A/B arm after its own
        # 128 MiB touch; there is no shared warm-up that could privilege the
        # arm that runs second.
        timing_cycle_calls = [
            ast.unparse(call)
            for call in ast.walk(functions["_timing"])
            if isinstance(call, ast.Call) and ast.unparse(call.func) == "_cycles"
        ]
        self.assertEqual(timing_cycle_calls, [])
        self.assertEqual(timing_source.count("torch.xpu.synchronize()"), 1)
        arm_calls = [
            ast.unparse(call)
            for call in ast.walk(functions["_timing"])
            if isinstance(call, ast.Call) and ast.unparse(call.func) == "_arm"
        ]
        self.assertEqual(
            arm_calls,
            [
                "_arm(corpus, evict, False, order, torch)",
                "_arm(corpus, evict, True, order, torch)",
                "_arm(corpus, evict, True, order, torch)",
                "_arm(corpus, evict, False, order, torch)",
            ],
        )
        self.assertIn("for block in range(31):", timing_source)
        self.assertIn("order = tuple", timing_source)
        self.assertIn("(rotation + index) % 47 for index in range(47)", timing_source)
        self.assertEqual(timing_source.count("_timing_slot_proof(corpus)"), 2)

        fixture_source = ast.unparse(functions["_timing_fixture"]).replace("'", '"')
        self.assertIn("len(set(all_slots)) == len(all_slots)", fixture_source)
        self.assertIn(
            'contract.PROTOCOL["eviction_bytes_per_arm"] // 4', fixture_source
        )
        self.assertIn("dtype=torch.float32", fixture_source)

    def test_aggregate_writer_is_exclusive_durable_and_no_overwrite(self):
        source = (ROOT / "analyze_laguna_shared_gate_up_mm_component.py").read_text()
        self.assertIn("os.O_EXCL", source)
        self.assertIn("os.O_NOFOLLOW", source)
        self.assertGreaterEqual(source.count("os.fsync"), 2)

    def test_production_path_binds_stage0_packet_lineage_and_runtime_dependencies(self):
        tree = ast.parse(
            (ROOT / "analyze_laguna_shared_gate_up_mm_component.py").read_text()
        )
        production = next(
            x
            for x in ast.walk(tree)
            if isinstance(x, ast.FunctionDef) and x.name == "validate_production"
        )
        calls = {
            ast.unparse(x.func) for x in ast.walk(production) if isinstance(x, ast.Call)
        }
        self.assertTrue(
            {
                "_packet_lineage",
                "_runtime_and_sources",
                "_stage0",
                "_strict_tree",
            }.issubset(calls)
        )
        stage0 = next(
            x
            for x in ast.walk(tree)
            if isinstance(x, ast.FunctionDef) and x.name == "_stage0"
        )
        stage0_calls = {
            ast.unparse(x.func) for x in ast.walk(stage0) if isinstance(x, ast.Call)
        }
        self.assertIn("contract.validate_stage0_evidence", stage0_calls)
        contract_tree = ast.parse(
            (ROOT / "gate_laguna_shared_gate_up_mm_component.py").read_text()
        )
        sealed_evidence = next(
            x
            for x in ast.walk(contract_tree)
            if isinstance(x, ast.FunctionDef)
            and x.name == "validate_stage0_evidence"
        )
        sealed_calls = {
            ast.unparse(x.func)
            for x in ast.walk(sealed_evidence)
            if isinstance(x, ast.Call)
        }
        self.assertIn("stage0.validate_authorization", sealed_calls)


if __name__ == "__main__":
    unittest.main()
