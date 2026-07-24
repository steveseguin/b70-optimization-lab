#!/usr/bin/env python3
"""CPU-only tamper/static tests for the component campaign coordinator."""

from __future__ import annotations

import ast
import copy
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

import analyze_laguna_shared_gate_mm_component as analyzer
import gate_laguna_shared_gate_mm_component as contract
import orchestrate_laguna_shared_gate_mm_component as coordinator


ROOT = pathlib.Path(__file__).parent
STAGE0_ROOT = pathlib.Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-m8-stage0-card0-155d647e4-20260724T005343Z"
)
FIXTURE = pathlib.Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations/shared-gate-m8-stage0-fixture-v5-155d647e4.json"
)


class ComponentCoordinatorTests(unittest.TestCase):
    @staticmethod
    def _packet(root: pathlib.Path) -> dict[str, object]:
        authorization = root.parent / "authorization.json"
        authorization.write_text("{}\n")
        cards = []
        for rank in range(4):
            card_root = root / f"card{rank}"
            cards.append(
                {
                    "rank": rank,
                    "physical": dict(contract.CARDS[rank]),
                    "output_root": str(card_root),
                    "environment": contract.environment(str(card_root), rank),
                }
            )
        return {
            "packet_path": str(authorization),
            "preflight_failure_path": str(
                root.parent / f"{root.name}-preflight-failure.json"
            ),
            "coordinator_environment": contract.coordinator_environment(str(root)),
            "cards": cards,
        }

    @staticmethod
    def _device(
        rank: int, *, logical_device_id: int | None = None
    ) -> dict[str, object]:
        physical = contract.CARDS[rank]
        return {
            "device_id": rank if logical_device_id is None else logical_device_id,
            "uuid": physical["uuid"],
            "pci_bdf_address": physical["pci_bdf_address"],
            "drm_device": physical["drm_device"],
        }

    @classmethod
    def _discovery_responses(cls) -> list[subprocess.CompletedProcess[str]]:
        responses = [
            subprocess.CompletedProcess(
                coordinator.DISCOVERY_ARGV,
                0,
                stdout=json.dumps(
                    {"device_list": [cls._device(rank) for rank in range(4)]}
                ),
                stderr="",
            )
        ]
        responses.extend(
            subprocess.CompletedProcess(
                coordinator.DISCOVERY_ARGV,
                0,
                stdout=json.dumps(
                    {"device_list": [cls._device(rank, logical_device_id=0)]}
                ),
                stderr="",
            )
            for rank in range(4)
        )
        return responses

    def test_full_stage0_evidence_manifest_and_schema_are_rechecked_cpu_only(
        self,
    ) -> None:
        result = contract.validate_stage0_evidence(
            STAGE0_ROOT / "stage0-result.json", FIXTURE
        )
        self.assertEqual(result["status"], "stage0_exactness_pass")
        self.assertEqual(len(result["epochs"]), 128)

    def test_stage0_evidence_tamper_has_no_permissive_hash_path(self) -> None:
        tree = ast.parse((ROOT / "gate_laguna_shared_gate_mm_component.py").read_text())
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "validate_stage0_evidence"
        )
        text = ast.unparse(function)
        self.assertIn("_validate_evidence_files", text)
        self.assertIn("found_map == expected_map", text)
        self.assertIn("validate_schema_for_cpu_tests", text)

    def test_runtime_import_dependencies_are_explicit_and_immutable(self) -> None:
        self.assertEqual(
            set(contract.RUNTIME_DEPENDENCIES),
            {"runner", "analyzer", "coordinator", "launcher"},
        )
        for names in contract.RUNTIME_DEPENDENCIES.values():
            self.assertTrue(names)
            self.assertTrue(set(names).issubset(contract.TOOLS))
        self.assertIn("stage0_runtime_adapter", contract.RUNTIME_DEPENDENCIES["runner"])
        self.assertIn("coordinator", contract.RUNTIME_DEPENDENCIES["runner"])
        self.assertIn(
            "stage0_result_analyzer", contract.RUNTIME_DEPENDENCIES["analyzer"]
        )
        self.assertIn("coordinator", contract.RUNTIME_DEPENDENCIES["analyzer"])

    def test_final_seal_is_analyzer_owned_and_requires_verifier(self) -> None:
        contract_source = (ROOT / "gate_laguna_shared_gate_mm_component.py").read_text()
        analyzer_source = (
            ROOT / "analyze_laguna_shared_gate_mm_component.py"
        ).read_text()
        coordinator_source = (
            ROOT / "orchestrate_laguna_shared_gate_mm_component.py"
        ).read_text()
        self.assertIn('"finalizer_argv"', contract_source)
        self.assertIn('"final_verifier_argv"', contract_source)
        self.assertIn("def finalize_production", analyzer_source)
        self.assertIn("def verify_final_production", analyzer_source)
        self.assertIn("counter_tooling_construction_authorized", analyzer_source)
        self.assertIn('"finalizer_argv"', coordinator_source)
        self.assertIn('"final_verifier_argv"', coordinator_source)

    def test_analyzer_output_writer_never_creates_parents(self) -> None:
        tree = ast.parse(
            (ROOT / "analyze_laguna_shared_gate_mm_component.py").read_text()
        )
        writer = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_exclusive_json"
        )
        self.assertNotIn("mkdir", ast.unparse(writer))
        self.assertIn("os.O_NOFOLLOW", ast.unparse(writer))

    def test_initial_and_final_seals_repeat_semantic_validation(self) -> None:
        tree = ast.parse(
            (ROOT / "analyze_laguna_shared_gate_mm_component.py").read_text()
        )
        functions = {
            node.name: ast.unparse(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        self.assertGreaterEqual(
            functions["validate_production"].count("_runtime_and_sources(packet)"),
            2,
        )
        self.assertGreaterEqual(
            functions["validate_production"].count("validate_card("), 2
        )
        self.assertEqual(functions["finalize_production"].count("_final_cards("), 2)
        self.assertIn("_pre_manifest_hashes", functions["finalize_production"])

    def test_pending_aggregate_cannot_authorize_counter_tooling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            authorization = root / "authorization.json"
            authorization.write_text("{}\n")
            packet = {"packet_path": str(authorization)}
            cards = [{"rank": 0, "result_sha256": "1" * 64}]
            aggregate = {
                "format": "laguna-shared-gate-m8-four-card-component-aggregate-v2",
                "status": "component_aggregate_pending_final_seal",
                "passed": True,
                "authorization_head": "a" * 40,
                "packet_sha256": analyzer.sha(authorization),
                "cards": cards,
                "downstream": dict(contract.FALSE_ACTIONS),
            }
            path = root / "component-aggregate.json"
            path.write_bytes(contract.canonical(aggregate) + b"\n")
            analyzer._validate_aggregate(packet, "a" * 40, cards, path)
            forged = copy.deepcopy(aggregate)
            forged["downstream"]["counter_tooling_construction_authorized"] = True
            forged_path = root / "forged-aggregate.json"
            forged_path.write_bytes(contract.canonical(forged) + b"\n")
            with self.assertRaisesRegex(RuntimeError, "pending-final-seal"):
                analyzer._validate_aggregate(packet, "a" * 40, cards, forged_path)

    def test_schema_tamper_stops_before_evidence_or_root_work(self) -> None:
        bad = {"format": contract.FORMAT}
        with self.assertRaisesRegex(RuntimeError, "schema"):
            contract.validate(copy.deepcopy(bad))

    def test_coordinator_and_launcher_never_shell_eval_or_import_torch(self) -> None:
        coordinator = (
            ROOT / "orchestrate_laguna_shared_gate_mm_component.py"
        ).read_text()
        launcher = (ROOT / "run_laguna_shared_gate_mm_component.sh").read_text()
        self.assertNotIn("import torch", coordinator)
        self.assertNotIn("bash -c", launcher)
        self.assertNotIn("eval ", launcher)
        self.assertIn('exec "$ENV" -i', launcher)
        self.assertIn('card["runner_argv"]', coordinator)

    def test_preflight_binds_all_json_views_and_campaign_start_is_canonical(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary) / "campaign"
            packet = self._packet(root)
            with mock.patch.object(
                coordinator.subprocess, "run", side_effect=self._discovery_responses()
            ) as run:
                preflight = coordinator.device_preflight(packet)
            self.assertEqual(run.call_count, 5)
            for call in run.call_args_list:
                self.assertEqual(call.args[0], coordinator.DISCOVERY_ARGV)
                self.assertEqual(call.kwargs["timeout"], 20)
                self.assertTrue(call.kwargs["capture_output"])
                self.assertTrue(call.kwargs["text"])
            coordinator.validate_device_preflight(preflight, packet)
            self.assertEqual(
                preflight["command"],
                {
                    "argv": ["/usr/bin/xpu-smi", "discovery", "-j"],
                    "timeout_seconds": 20,
                },
            )
            self.assertEqual(
                [probe["rank"] for probe in preflight["filtered"]], [0, 1, 2, 3]
            )
            with mock.patch.object(contract, "sha", return_value="0" * 64):
                coordinator.acquire_campaign_root(root, packet, preflight)
            checkpoint_path = root / "campaign-start-checkpoint.json"
            raw = checkpoint_path.read_bytes()
            checkpoint = json.loads(raw)
            self.assertEqual(raw, contract.canonical(checkpoint) + b"\n")
            self.assertEqual(checkpoint["device_preflight"], preflight)
            self.assertEqual(
                checkpoint["device_preflight"]["packet_mapping"],
                [{"rank": rank, **contract.CARDS[rank]} for rank in range(4)],
            )

    def test_timeout_prevents_campaign_root_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary) / "campaign"
            packet = self._packet(root)
            timeout = subprocess.TimeoutExpired(coordinator.DISCOVERY_ARGV, 20)
            with mock.patch.object(coordinator.subprocess, "run", side_effect=timeout):
                with self.assertRaisesRegex(RuntimeError, "timed out after 20s"):
                    coordinator.preflight_and_acquire_campaign_root(root, packet)
            self.assertFalse(root.exists())
            failure_path = pathlib.Path(packet["preflight_failure_path"])
            failure = json.loads(failure_path.read_text())
            self.assertEqual(failure["tensor_work_started"], False)
            self.assertEqual(failure["status"], "component_failed_stop_before_counters")
            self.assertEqual(
                failure_path.read_bytes(), contract.canonical(failure) + b"\n"
            )

    def test_absent_parent_is_rejected_before_any_device_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = pathlib.Path(temporary)
            packet = self._packet(base / "safe-campaign")
            root = base / "absent-parent" / "campaign"
            packet["preflight_failure_path"] = str(
                root.parent / f"{root.name}-preflight-failure.json"
            )
            with mock.patch.object(coordinator.subprocess, "run") as run:
                with self.assertRaisesRegex(RuntimeError, "parent is absent"):
                    coordinator.preflight_and_acquire_campaign_root(root, packet)
            run.assert_not_called()
            self.assertFalse(root.exists())

    def test_mapping_mismatch_prevents_campaign_root_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary) / "campaign"
            packet = self._packet(root)
            wrong = self._device(2, logical_device_id=0)
            wrong["pci_bdf_address"] = "0000:00:00.0"
            wrong_response = subprocess.CompletedProcess(
                coordinator.DISCOVERY_ARGV,
                0,
                stdout=json.dumps({"device_list": [wrong]}),
                stderr="",
            )
            responses = self._discovery_responses()
            responses[3] = wrong_response  # full, rank 0, rank 1, then rank 2.
            with mock.patch.object(
                coordinator.subprocess, "run", side_effect=responses
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "rank 2 filtered xpu-smi mapping drift"
                ):
                    coordinator.preflight_and_acquire_campaign_root(root, packet)
            self.assertFalse(root.exists())
            self.assertTrue(pathlib.Path(packet["preflight_failure_path"]).is_file())

    def test_preflight_validator_reparses_stdout_instead_of_trusting_mapping(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary) / "campaign"
            packet = self._packet(root)
            with mock.patch.object(
                coordinator.subprocess, "run", side_effect=self._discovery_responses()
            ):
                preflight = coordinator.device_preflight(packet)
            tampered = copy.deepcopy(preflight)
            tampered["filtered"][0]["parsed_mapping"][0]["uuid"] = (
                "not-the-observed-uuid"
            )
            with self.assertRaisesRegex(
                RuntimeError, "parsed mapping does not match stdout"
            ):
                coordinator.validate_device_preflight(tampered, packet)


if __name__ == "__main__":
    unittest.main()
