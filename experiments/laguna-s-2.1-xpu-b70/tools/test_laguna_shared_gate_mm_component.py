#!/usr/bin/env python3
"""CPU-only anti-forgery tests for the component analyzer and timed loop."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import analyze_laguna_shared_gate_mm_component as analyzer
import gate_laguna_shared_gate_mm_component as c


ROOT = pathlib.Path(__file__).parent
FIXTURE = pathlib.Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations/shared-gate-m8-stage0-fixture-v5-155d647e4.json"
)
STAGE0_RESULT = pathlib.Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-m8-stage0-card0-155d647e4-20260724T005343Z/stage0-result.json"
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
    weight_shape = tensors["gate_weight"]["shape"]
    rows = _metadata(100_000 + slot * 10, rows_shape, [rows_shape[1], 1])
    weight = _metadata(200_000 + slot * 10, weight_shape, [weight_shape[1], 1])
    rows["raw_bf16_le_sha256"] = tensors["hidden_input"]["raw_bf16_le_sha256"]
    weight["raw_bf16_le_sha256"] = tensors["gate_weight"]["raw_bf16_le_sha256"]
    output_raw = hashlib.sha256(f"timing-output-{slot}".encode()).hexdigest()
    control = _metadata(
        300_000 + slot * 10,
        [rows_shape[0], 1, weight_shape[0]],
        [weight_shape[0], weight_shape[0], 1],
    )
    candidate = _metadata(
        400_000 + slot * 10,
        [rows_shape[0], weight_shape[0]],
        [weight_shape[0], 1],
    )
    control["raw_bf16_le_sha256"] = output_raw
    candidate["raw_bf16_le_sha256"] = output_raw
    return {
        "slot": slot,
        "rows": rows,
        "weight": weight,
        "rows_bmm": _metadata(
            rows["data_ptr"],
            [rows_shape[0], 1, rows_shape[1]],
            [rows_shape[1], rows_shape[1], 1],
        ),
        "weight_t": _metadata(
            weight["data_ptr"],
            [weight_shape[1], weight_shape[0]],
            [1, weight_shape[1]],
        ),
        "expanded": _metadata(
            weight["data_ptr"],
            [rows_shape[0], weight_shape[1], weight_shape[0]],
            [0, 1, weight_shape[1]],
        ),
        "control": control,
        "candidate": candidate,
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
        "timing_label": "allocation_free_isolated_gate_GEMM_primitive",
        "target_layers_per_cycle": 47,
        "weight_bytes_each": 1572864,
        "distinct_weights": 47,
        "preallocated_identical_inputs": True,
        "output_ring_slots_per_arm": 47,
        "distinct_preallocated_output_buffers": True,
        "warm_cycles_per_arm": 20,
        "blocks": 31,
        "cycles_per_arm_per_block": 64,
        "calls_per_arm": 3008,
        "eviction_bytes_once_per_arm": 134217728,
        "synchronization": "arm_boundaries_only",
        "arm_order": "A-B-B-A",
        "candidate_block_wins": 31,
        "median_saving_ms_per_cycle": 0.35,
        "buffer_proof": {
            "input_slots": [proof["rows"]["data_ptr"] for proof in pre_slots],
            "weight_slots": [proof["weight"]["data_ptr"] for proof in pre_slots],
            "control_output_slots": [
                proof["control"]["data_ptr"] for proof in pre_slots
            ],
            "candidate_output_slots": [
                proof["candidate"]["data_ptr"] for proof in pre_slots
            ],
            "control_layout": {
                key: pre_slots[0]["control"][key] for key in metadata_keys
            },
            "candidate_layout": {
                key: pre_slots[0]["candidate"][key] for key in metadata_keys
            },
            "pre_timing_slots": pre_slots,
            "post_timing_slots": post_slots,
            "nonalias": True,
        },
        "preflight_proof": [
            {
                "slot": index,
                "control_out_supplied_ptr": pre_slots[index]["control"]["data_ptr"],
                "control_out_returned_ptr": pre_slots[index]["control"]["data_ptr"],
                "candidate_out_supplied_ptr": pre_slots[index]["candidate"]["data_ptr"],
                "candidate_out_returned_ptr": pre_slots[index]["candidate"]["data_ptr"],
                "literal_raw_uint16_equal": True,
                "control_out_raw_uint16_equal": True,
                "candidate_out_raw_uint16_equal": True,
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
            "format": "laguna-shared-gate-m8-four-card-component-result-v1",
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
            patch.object(analyzer.c, "validate"),
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
            (ROOT / "analyze_laguna_shared_gate_mm_component.py").read_text()
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
                "candidate_output_slots"
            ].__setitem__(0, 300)
        )
        self.rejects(
            lambda r, p: r["timing"]["preflight_proof"][0].__setitem__(
                "control_out_raw_uint16_equal", False
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
                "weight"
            ].__setitem__("data_ptr", 1)
        )
        self.rejects(
            lambda r, p: r["timing"]["buffer_proof"]["post_timing_slots"][0][
                "candidate"
            ].__setitem__("raw_bf16_le_sha256", "0" * 64)
        )

    def test_checkpoint_hash_packet_binding_and_exact_inventory_are_not_trusted(self):
        result, _ = self.result()
        digest = result["packet_sha256"]
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            values = {
                "pre-tensor-identity-checkpoint.json": {
                    "packet_sha256": digest,
                    "rank": 0,
                },
                "tensor-work-started-checkpoint.json": {
                    "packet_sha256": digest,
                    "rank": 0,
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
    def test_inner_loop_and_its_callees_are_allocation_and_sync_free(self):
        tree = ast.parse((ROOT / "run_laguna_shared_gate_mm_component.py").read_text())
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
        source = (ROOT / "run_laguna_shared_gate_mm_component.py").read_text()
        analyzer_source = (
            ROOT / "analyze_laguna_shared_gate_mm_component.py"
        ).read_text()
        self.assertNotIn('"xpu-smi"', source)
        self.assertNotIn("'xpu-smi'", source)
        self.assertIn("coordinator.validate_device_preflight", source)
        self.assertIn("torch.xpu.get_device_properties(0)", source)
        self.assertIn('runtime_uuid_text == card["physical"]["uuid"]', source)
        self.assertIn("runtime-card-binding-checkpoint.json", source)
        for checkpoint_format in (
            "laguna-shared-gate-m8-component-pre-tensor-v2",
            "laguna-shared-gate-m8-component-tensor-start-v2",
        ):
            self.assertIn(checkpoint_format, source)
            self.assertIn(checkpoint_format, analyzer_source)

    def test_warm_abba_raw_ns_and_eviction_boundaries_are_pinned(self):
        tree = ast.parse((ROOT / "run_laguna_shared_gate_mm_component.py").read_text())
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        arm_source = ast.unparse(functions["_arm"]).replace("'", '"')
        self.assertLess(arm_source.index("evict.add_(1)"), arm_source.index("start ="))
        self.assertEqual(arm_source.count("torch.xpu.synchronize()"), 2)
        self.assertEqual(arm_source.count("time.perf_counter_ns()"), 2)
        self.assertIn("cycles_per_arm_per_block", arm_source)
        self.assertIn('"elapsed_ns": elapsed', arm_source)

        timing_source = ast.unparse(functions["_timing"]).replace("'", '"')
        warm_control = '_cycles(corpus, False, contract.PROTOCOL["warm_cycles_per_arm"], fixed, torch)'
        warm_candidate = '_cycles(corpus, True, contract.PROTOCOL["warm_cycles_per_arm"], fixed, torch)'
        self.assertIn(warm_control, timing_source)
        self.assertIn(warm_candidate, timing_source)
        self.assertLess(
            timing_source.index(warm_control), timing_source.index(warm_candidate)
        )
        self.assertEqual(timing_source.count("torch.xpu.synchronize()"), 4)
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
        source = (ROOT / "analyze_laguna_shared_gate_mm_component.py").read_text()
        self.assertIn("os.O_EXCL", source)
        self.assertIn("os.O_NOFOLLOW", source)
        self.assertGreaterEqual(source.count("os.fsync"), 2)

    def test_production_path_binds_stage0_packet_lineage_and_runtime_dependencies(self):
        tree = ast.parse(
            (ROOT / "analyze_laguna_shared_gate_mm_component.py").read_text()
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
        self.assertIn("c.validate_stage0_evidence", stage0_calls)
        self.assertIn("stage0.validate_authorization", stage0_calls)


if __name__ == "__main__":
    unittest.main()
