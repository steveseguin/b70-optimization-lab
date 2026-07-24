#!/usr/bin/env python3
"""CPU fixtures for the real Laguna M=8 low-level recorder schema."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "laguna_actual_analyzer", HERE / "analyze_laguna_m8_actual_offline_gate.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
DRIVER_SPEC = importlib.util.spec_from_file_location(
    "laguna_actual_driver", HERE / "run_laguna_m8_actual_offline.py"
)
assert DRIVER_SPEC and DRIVER_SPEC.loader
DRIVER = importlib.util.module_from_spec(DRIVER_SPEC)
DRIVER_SPEC.loader.exec_module(DRIVER)


def signature(data: bytes) -> dict[str, object]:
    return {
        "dtype": "torch.bfloat16",
        "shape": [1],
        "stride": [1],
        "device": "xpu:0",
        "nbytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def slot_signature(label: bytes, device: str = "xpu:0") -> dict[str, object]:
    data = hashlib.sha256(label).digest() * 2
    return {
        "dtype": "torch.int64",
        "shape": [8],
        "stride": [1],
        "device": device,
        "nbytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def expected_boundaries() -> list[str]:
    return MODULE._expected_boundaries()


class ActualOfflineAnalyzerTest(unittest.TestCase):
    def test_eager_arms_match_record_and_graph_arm_is_explicit(self) -> None:
        for arm in ("incumbent-eager", "segmented-eager"):
            with self.subTest(arm=arm):
                enforce_eager, compilation = DRIVER.execution_config(arm)
                self.assertTrue(enforce_eager)
                self.assertIsNone(compilation)
        enforce_eager, compilation = DRIVER.execution_config("segmented-graph")
        self.assertFalse(enforce_eager)
        self.assertEqual(
            compilation,
            {
                "mode": "NONE",
                "cudagraph_mode": "PIECEWISE",
                "cudagraph_capture_sizes": [8],
                "max_cudagraph_capture_size": 8,
            },
        )

    def test_frozen_rpc_bases_leave_conservative_socket_headroom(self) -> None:
        self.assertEqual(
            set(DRIVER.RPC_DIRS),
            {"incumbent-eager", "segmented-eager", "segmented-graph"},
        )
        for arm, rpc_dir in DRIVER.RPC_DIRS.items():
            with self.subTest(arm=arm):
                self.assertEqual(
                    DRIVER.rpc_socket_path_bytes(rpc_dir),
                    DRIVER.ZMQ_CONSERVATIVE_PATH_BYTES,
                )
                self.assertEqual(
                    str(rpc_dir),
                    MODULE.RPC_DIRS[arm],
                )
        self.assertLess(
            DRIVER.ZMQ_CONSERVATIVE_PATH_BYTES,
            107,
        )

    @staticmethod
    def mutate_event(
        root: Path,
        rank: int,
        ordinal: int,
        label: str,
        mutate: object,
    ) -> None:
        run_dir = root / f"rank{rank:02d}-pid123-evidence{ordinal + 1:04d}"
        manifest_path = run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        matches = [event for event in manifest["events"] if event["label"] == label]
        if len(matches) != 1:
            raise AssertionError(f"fixture expected one {label}")
        mutate(matches[0])  # type: ignore[operator]
        event = matches[0]
        sidecar = (
            run_dir / "events" / f"{event['event_index']:05d}-{event['label']}.json"
        )
        sidecar.write_text(json.dumps(event))
        manifest_path.write_text(json.dumps(manifest))

    def write_run(
        self,
        root: Path,
        arm: str,
        *,
        content_salt: str = "same",
        event_count: int = 4,
        routing_salt: str = "same-routing",
    ) -> None:
        for rank in range(4):
            for ordinal in range(event_count):
                run_dir = root / f"rank{rank:02d}-pid123-evidence{ordinal + 1:04d}"
                events_dir = run_dir / "events"
                events_dir.mkdir(parents=True)
                events: list[dict[str, object]] = []
                slot_signatures = [
                    slot_signature(
                        f"{routing_salt}:{layer % 3}".encode(),
                        device=f"xpu:{rank}",
                    )
                    for layer in range(48)
                ]
                logical = {
                    "attention_slot_mapping_signatures": slot_signatures,
                    "candidate_ids": list(range(8)),
                    "positions": list(range(8)),
                    "rank": rank,
                    "request_generation_epoch": ordinal + 1,
                    "seq_query_metadata": {
                        "num_reqs": 1,
                        "num_tokens_padded": 8,
                        "num_tokens_unpadded": 8,
                        "query_len": 8,
                    },
                    "target_ordinal": ordinal * 2,
                }

                def metadata(
                    label: str, details: dict[str, object], phase: str
                ) -> None:
                    event = {
                        "event_index": len(events),
                        "label": label,
                        "phase": phase,
                        "rank": rank,
                        "details": details,
                        "logical_event_key": logical,
                    }
                    events.append(event)
                    (
                        events_dir / f"{event['event_index']:05d}-{label}.json"
                    ).write_text(json.dumps(event))

                def tensor(
                    label: str,
                    phase: str,
                    inputs: dict[str, object],
                    metadata_extra: dict[str, object] | None = None,
                ) -> None:
                    data = f"{content_salt}:{rank}:{ordinal}:{label}".encode()
                    raw_name = f"events/{len(events):05d}-{label}.bin"
                    (run_dir / raw_name).write_bytes(data)
                    details = {
                        "output": signature(data),
                        "input_signatures": inputs,
                    }
                    if metadata_extra:
                        details.update(metadata_extra)
                    event = {
                        "event_index": len(events),
                        "label": label,
                        "phase": phase,
                        "rank": rank,
                        "details": details,
                        "logical_event_key": logical,
                        "raw_file": raw_name,
                    }
                    events.append(event)
                    (
                        events_dir / f"{event['event_index']:05d}-{label}.json"
                    ).write_text(json.dumps(event))

                metadata("logical_event_key", logical, "uninitialized")
                base_phase = (
                    "segmented-eager" if arm == "segmented-eager" else "incumbent-eager"
                )
                metadata("phase", {"phase": base_phase}, base_phase)
                metadata(
                    "arm_contract",
                    {
                        "drafter_is_breakable": False,
                        "logits_outside_model_wrapper": True,
                        "target_is_breakable": arm == "segmented-graph",
                    },
                    base_phase,
                )
                phase = base_phase
                if arm == "segmented-graph":
                    phase = "capture" if ordinal == 0 else "replay"
                    metadata("phase", {"phase": phase}, phase)
                if arm != "incumbent-eager":
                    for boundary in expected_boundaries():
                        metadata(
                            "boundary",
                            {
                                "boundary": boundary,
                                "ordinal": len(
                                    [e for e in events if e["label"] == "boundary"]
                                ),
                            },
                            phase,
                        )
                        if boundary == "embedding_reduce":
                            tensor(
                                "embedding_all_reduce",
                                phase,
                                {"local_input": signature(b"local")},
                                {"collective_index": None},
                            )
                            continue
                        if boundary.startswith("attention:"):
                            layer = int(boundary.split(":")[1])
                            slot = {"slot_mapping": slot_signatures[layer]}
                            for suffix in ("query", "key", "value", "output"):
                                tensor(f"attention_{layer:02d}_{suffix}", phase, slot)
                        else:
                            gather = int(boundary.split(":")[1])
                            tensor(
                                "all_gather",
                                phase,
                                {"local_input": signature(b"local")},
                                {"collective_index": gather},
                            )
                    metadata(
                        "full_topology",
                        {"boundary_count": 145, "collective_count": 97},
                        phase,
                    )
                else:
                    for layer in range(48):
                        slot = {"slot_mapping": slot_signatures[layer]}
                        for suffix in ("query", "key", "value", "output"):
                            tensor(f"attention_{layer:02d}_{suffix}", phase, slot)
                if arm == "segmented-graph":
                    label = (
                        "breakable_capture_topology"
                        if ordinal == 0
                        else "breakable_replay_topology"
                    )
                    topology: dict[str, object] = {
                        "graphs": 146,
                        "eager_breaks": 145,
                        "capture_count": 1,
                        "descriptor": "BatchDescriptor(8)",
                    }
                    if ordinal == 0:
                        topology["ordered_boundary_categories"] = {
                            "attention": 48,
                            "collective": 97,
                        }
                    else:
                        topology["replay_count"] = ordinal
                    metadata(label, topology, phase)
                tensor(
                    "target_hidden_before_logits",
                    phase,
                    {
                        "input_ids": signature(b"ids"),
                        "positions": signature(b"positions"),
                    },
                )
                metadata(
                    "kv_capture_status",
                    {
                        "physical_kv_cache_bytes_supported": False,
                        "status": "unsupported",
                        "reason": "backend-owned",
                    },
                    phase,
                )
                metadata("logits_boundary", {"after_target_model_forward": True}, phase)
                tensor("sampled_token_ids_after_logits", phase, {})
                metadata(
                    "spec_acceptance_before_bookkeeping",
                    {
                        "accepted_draft_count": 7,
                        "emitted_ids_before_bookkeeping": list(range(8)),
                        "first_rejected_draft_index": None,
                        "proposed_draft_ids": list(range(7)),
                    },
                    phase,
                )
                metadata(
                    "emitted_ids_after_bookkeeping",
                    {"emitted_ids": [list(range(8))]},
                    phase,
                )
                (run_dir / "manifest.json").write_text(
                    json.dumps(
                        {
                            "format": MODULE.FORMAT,
                            "marker": MODULE.RECORDER_MARKER,
                            "arm": arm,
                            "rank": rank,
                            "event_count": len(events),
                            "events": events,
                        }
                    )
                )

    def test_path_difference_with_equal_bytes_passes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            left, right = root / "left", root / "right"
            left.mkdir()
            right.mkdir()
            self.write_run(left, "segmented-eager")
            self.write_run(right, "segmented-eager")
            MODULE.compare(
                MODULE.aggregate_recorder_root("segmented-eager", left),
                MODULE.aggregate_recorder_root("segmented-eager", right),
                "same-bytes-different-paths",
            )

    def test_content_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            left, right = root / "left", root / "right"
            left.mkdir()
            right.mkdir()
            self.write_run(left, "segmented-eager")
            self.write_run(right, "segmented-eager", content_salt="different")
            with self.assertRaisesRegex(ValueError, "target_hidden"):
                MODULE.compare(
                    MODULE.aggregate_recorder_root("segmented-eager", left),
                    MODULE.aggregate_recorder_root("segmented-eager", right),
                    "mismatch",
                )

    def test_fewer_than_four_eligible_events_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write_run(root, "segmented-graph", event_count=3)
            with self.assertRaisesRegex(ValueError, "fewer than 4"):
                MODULE.aggregate_recorder_root("segmented-graph", root)

    def test_graph_requires_one_capture_then_replays(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write_run(root, "segmented-graph")
            aggregate = MODULE.aggregate_recorder_root("segmented-graph", root)
            self.assertEqual(aggregate["rank_events"]["0"][0]["phase"], "capture")
            self.assertTrue(
                all(
                    event["phase"] == "replay"
                    for event in aggregate["rank_events"]["0"][1:]
                )
            )

    def test_wrong_manifest_marker_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write_run(root, "segmented-eager")
            manifest = root / "rank00-pid123-evidence0001" / "manifest.json"
            value = json.loads(manifest.read_text())
            value["marker"] = "WRONG"
            manifest.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "recorder format"):
                MODULE.aggregate_recorder_root("segmented-eager", root)

    def test_attention_slot_mapping_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write_run(root, "segmented-eager")

            def mutate(event: dict[str, object]) -> None:
                event["details"]["input_signatures"]["slot_mapping"] = slot_signature(  # type: ignore[index]
                    b"different-slot"
                )

            self.mutate_event(root, 0, 0, "attention_07_key", mutate)
            with self.assertRaisesRegex(ValueError, "slot mapping"):
                MODULE.aggregate_recorder_root("segmented-eager", root)

    def test_live_layer_slot_must_match_logical_vector(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write_run(root, "segmented-eager")

            def mutate(event: dict[str, object]) -> None:
                event["details"]["input_signatures"]["slot_mapping"] = slot_signature(  # type: ignore[index]
                    b"internally-consistent-but-logically-wrong"
                )

            for suffix in ("query", "key", "value", "output"):
                self.mutate_event(root, 0, 0, f"attention_07_{suffix}", mutate)
            with self.assertRaisesRegex(
                ValueError, "live attention slot differs at layer 7"
            ):
                MODULE.aggregate_recorder_root("segmented-eager", root)

    def test_distinct_per_layer_slot_mappings_pass(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write_run(root, "segmented-eager")
            aggregate = MODULE.aggregate_recorder_root("segmented-eager", root)
            routing = aggregate["rank_events"]["0"][0]["live_attention_slot_routing"]
            self.assertEqual(
                len({json.dumps(item, sort_keys=True) for item in routing}),
                3,
            )

    def test_cross_arm_slot_routing_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            left, right = root / "left", root / "right"
            left.mkdir()
            right.mkdir()
            self.write_run(left, "segmented-eager")
            self.write_run(
                right,
                "segmented-eager",
                routing_salt="different-routing",
            )
            with self.assertRaisesRegex(ValueError, "live_attention_slot_routing"):
                MODULE.compare(
                    MODULE.aggregate_recorder_root("segmented-eager", left),
                    MODULE.aggregate_recorder_root("segmented-eager", right),
                    "routing-mismatch",
                )

    def test_obsolete_singular_slot_logical_key_fails(self) -> None:
        logical = {
            "attention_slot_mapping_signatures": [
                slot_signature(f"slot:{layer}".encode()) for layer in range(48)
            ],
            "candidate_ids": list(range(8)),
            "positions": list(range(8)),
            "rank": 0,
            "request_generation_epoch": 1,
            "seq_query_metadata": {
                "num_reqs": 1,
                "num_tokens_padded": 8,
                "num_tokens_unpadded": 8,
                "query_len": 8,
            },
            "slot_mapping_sha256": "0" * 64,
            "target_ordinal": 0,
        }
        with self.assertRaisesRegex(ValueError, "fields/rank drift"):
            MODULE._validate_logical_key(logical, 0, "obsolete")

    def test_hidden_spurious_slot_mapping_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write_run(root, "incumbent-eager")

            def mutate(event: dict[str, object]) -> None:
                event["details"]["input_signatures"]["slot_mapping"] = slot_signature(  # type: ignore[index]
                    b"spurious-hidden-slot"
                )

            self.mutate_event(root, 0, 0, "target_hidden_before_logits", mutate)
            with self.assertRaisesRegex(ValueError, "hidden input signature fields"):
                MODULE.aggregate_recorder_root("incumbent-eager", root)

    def test_graph_replay_counter_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write_run(root, "segmented-graph")

            def mutate(event: dict[str, object]) -> None:
                event["details"]["replay_count"] = 99  # type: ignore[index]

            self.mutate_event(root, 0, 1, "breakable_replay_topology", mutate)
            with self.assertRaisesRegex(ValueError, "replay counter"):
                MODULE.aggregate_recorder_root("segmented-graph", root)

    def test_inconsistent_acceptance_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write_run(root, "incumbent-eager")

            def mutate(event: dict[str, object]) -> None:
                event["details"]["accepted_draft_count"] = 6  # type: ignore[index]

            self.mutate_event(root, 0, 0, "spec_acceptance_before_bookkeeping", mutate)
            with self.assertRaisesRegex(ValueError, "accepted-prefix"):
                MODULE.aggregate_recorder_root("incumbent-eager", root)

    def test_stored_aggregate_tamper_fails_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write_run(root, "segmented-eager")
            aggregate = MODULE.aggregate_recorder_root("segmented-eager", root)
            aggregate["rank_events"]["0"][0]["emitted_ids"] = [999]
            stored = root / "evidence.json"
            stored.write_text(json.dumps(aggregate))
            with self.assertRaisesRegex(ValueError, "differs from revalidated"):
                MODULE.normalize_evidence("segmented-eager", stored, root)


if __name__ == "__main__":
    unittest.main()
