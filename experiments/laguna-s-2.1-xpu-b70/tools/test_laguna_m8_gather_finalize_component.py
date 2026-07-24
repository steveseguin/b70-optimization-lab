#!/usr/bin/env python3
"""CPU-only contract and anti-forgery tests for gather/finalize Phase A."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

import analyze_laguna_m8_gather_finalize_component as analyzer
import gate_laguna_m8_gather_finalize_component as contract
import orchestrate_laguna_m8_gather_finalize_component as coordinator
import run_laguna_m8_gather_finalize_component as runner


ROOT = Path(__file__).parent
FIXTURE = Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations/"
    "gather-finalize-fixture-v2-4772f72-d338610.json"
)
BINARY_MANIFEST = Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations/"
    "gather-finalize-4772f72-binary-manifest-v1.json"
)
FIXTURE_SHA256 = "0b1ea43d0a724cc64eaf6636b99076afd852846f79c06b4db264f2a511689259"
BINARY_MANIFEST_SHA256 = (
    "9c026221bb1a76ab0b35b26bf37b1521ad4d728569a09ee7cc9f24cf36319ac9"
)
TOOLS = (
    "gate_laguna_m8_gather_finalize_component.py",
    "generate_laguna_m8_gather_finalize_fixture.py",
    "run_laguna_m8_gather_finalize_component.py",
    "orchestrate_laguna_m8_gather_finalize_component.py",
    "analyze_laguna_m8_gather_finalize_component.py",
    "test_laguna_m8_gather_finalize_component.py",
)


def digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def classification() -> dict[str, object]:
    return {
        "positive_zero": analyzer.BF16_NUMEL,
        "negative_zero": 0,
        "subnormal": 0,
        "negative_subnormal": 0,
        "finite_normal": 0,
        "infinity": 0,
        "positive_infinity": 0,
        "negative_infinity": 0,
        "nan": 0,
        "positive_nan": 0,
        "negative_nan": 0,
        "sign_bit_set": 0,
        "nan_payloads_sha256": digest("no-nan-payloads"),
    }


def comparison(raw_digest: str) -> dict[str, object]:
    classes = classification()
    return {
        "left_raw_bf16_le_sha256": raw_digest,
        "right_raw_bf16_le_sha256": raw_digest,
        "raw_uint16_equal": True,
        "left_classification": copy.deepcopy(classes),
        "right_classification": copy.deepcopy(classes),
        "contains_nan": False,
        "torch_equal": True,
        "torch_equal_policy": analyzer.FINITE_COMPARISON_POLICY,
        "classification_equal": True,
        "passed": True,
    }


def tensor_record(
    pointer: int,
    shape: list[int],
    dtype: str,
    stride: list[int],
    element_size: int,
    raw_digest: str,
) -> dict[str, object]:
    numel = 1
    for dimension in shape:
        numel *= dimension
    return {
        "metadata": {
            "data_ptr": pointer,
            "shape": shape,
            "stride": stride,
            "dtype": dtype,
            "device": "xpu:0",
            "numel": numel,
            "element_size": element_size,
        },
        "raw_le_sha256": raw_digest,
    }


class GatherFinalizeCpuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = contract.validate_fixture_manifest(FIXTURE)
        cls.specs = analyzer._expected_specs(cls.manifest)
        cls.expected_final_hashes = {
            spec["id"]: digest(f"literal-final-{spec['id']}") for spec in cls.specs
        }

    def _timing(self) -> dict[str, object]:
        before_inputs = []
        after_inputs = []
        names = (
            (
                "routes",
                [80, analyzer.HIDDEN],
                "torch.bfloat16",
                [analyzer.HIDDEN, 1],
                2,
                "routes_bf16_le_sha256",
            ),
            (
                "weights",
                [analyzer.TOKENS, analyzer.TOPK],
                "torch.float32",
                [analyzer.TOPK, 1],
                4,
                "weights_fp32_le_sha256",
            ),
            (
                "shared",
                [analyzer.TOKENS, analyzer.HIDDEN],
                "torch.bfloat16",
                [analyzer.HIDDEN, 1],
                2,
                "shared_bf16_le_sha256",
            ),
            (
                "route_map",
                [analyzer.TOKENS, analyzer.TOPK],
                "torch.int32",
                [analyzer.TOPK, 1],
                4,
                "route_map_uint32_le_sha256",
            ),
        )
        for index, spec in enumerate(self.specs):
            item: dict[str, object] = {"fixture_id": spec["id"]}
            expected = self.manifest["expected_cpu_input_hashes"][spec["id"]]
            for offset, (name, shape, dtype, stride, size, hash_name) in enumerate(
                names
            ):
                item[name] = tensor_record(
                    1_000_000 + index * 10 + offset,
                    shape,
                    dtype,
                    stride,
                    size,
                    expected[hash_name],
                )
            before_inputs.append(item)
            after_inputs.append(copy.deepcopy(item))

        before_outputs = []
        after_outputs = []
        output_names = (
            "control_routed",
            "control_final",
            "candidate_final",
            "candidate_repeat",
        )
        for slot in range(analyzer.LAYERS):
            final_digest = self.expected_final_hashes[self.specs[slot]["id"]]
            item = {"slot": slot}
            for offset, name in enumerate(output_names):
                raw = (
                    digest(f"timing-routed-{slot}")
                    if name == "control_routed"
                    else final_digest
                )
                item[name] = tensor_record(
                    10_000_000 + slot * 10 + offset,
                    [analyzer.TOKENS, analyzer.HIDDEN],
                    "torch.bfloat16",
                    [analyzer.HIDDEN, 1],
                    2,
                    raw,
                )
            before_outputs.append(item)
            after_item = copy.deepcopy(item)
            final_fixture_index = (
                (analyzer.ABBA_BLOCKS - 1) * analyzer.LAYERS + slot
            ) % len(self.specs)
            after_digest = self.expected_final_hashes[
                self.specs[final_fixture_index]["id"]
            ]
            after_item["control_final"]["raw_le_sha256"] = after_digest
            after_item["candidate_final"]["raw_le_sha256"] = after_digest
            after_outputs.append(after_item)

        blocks = []
        control_ns = 128_000_000
        candidate_ns = 115_200_000
        control_ms = (
            (control_ns + control_ns) / (2 * analyzer.CYCLES_PER_ARM) / 1_000_000
        )
        candidate_ms = (
            (candidate_ns + candidate_ns) / (2 * analyzer.CYCLES_PER_ARM) / 1_000_000
        )
        for block in range(analyzer.ABBA_BLOCKS):
            fixture_indices = [
                (block * analyzer.LAYERS + slot) % len(self.specs)
                for slot in range(analyzer.LAYERS)
            ]
            blocks.append(
                {
                    "block": block,
                    "fixture_indices": fixture_indices,
                    "A1_control_elapsed_ns": control_ns,
                    "B1_candidate_elapsed_ns": candidate_ns,
                    "B2_candidate_elapsed_ns": candidate_ns,
                    "A2_control_elapsed_ns": control_ns,
                    "paired_control_ms_per_47_layer_cycle": control_ms,
                    "paired_candidate_ms_per_47_layer_cycle": candidate_ms,
                    "saving_ms_per_47_layer_cycle": control_ms - candidate_ms,
                }
            )
        timed_block_outputs = []
        for block in blocks:
            outputs = []
            for slot, fixture_index in enumerate(block["fixture_indices"]):
                fixture_id = self.specs[fixture_index]["id"]
                raw = self.expected_final_hashes[fixture_id]
                outputs.append(
                    {
                        "slot": slot,
                        "fixture_index": fixture_index,
                        "fixture_id": fixture_id,
                        "literal_oracle_raw_bf16_le_sha256": raw,
                        "control_final_vs_candidate_final": comparison(raw),
                    }
                )
            timed_block_outputs.append({"block": block["block"], "outputs": outputs})
        return {
            "timing_label": "preallocated_incumbent_moe_gather_then_laguna_m8_scale_add_vs_candidate_only",
            "clock": "torch.xpu.Event device elapsed time",
            "warm_cycles_per_arm": analyzer.WARM_CYCLES,
            "blocks": analyzer.ABBA_BLOCKS,
            "arm_order": "A-B-B-A",
            "cycles_per_arm": analyzer.CYCLES_PER_ARM,
            "layers_per_cycle": analyzer.LAYERS,
            "control_calls_per_primitive_per_arm": (
                analyzer.CYCLES_PER_ARM * analyzer.LAYERS
            ),
            "candidate_calls_per_arm": (analyzer.CYCLES_PER_ARM * analyzer.LAYERS),
            "scheduled_control_selected_launches_per_cycle": 94,
            "scheduled_candidate_selected_launches_per_cycle": 47,
            "scheduled_fixture_rotation": "prebuilt_outside_timed_arms",
            "synchronization": "arm_boundaries_only",
            "cpu_work_inside_event_interval": "native dispatch calls only",
            "storage_proof": {
                "input_storage_count": len(self.specs) * 4,
                "output_storage_count": analyzer.LAYERS * 4,
                "all_storage_unique_and_nonaliasing": True,
                "input_metadata_and_hashes_unchanged": True,
                "output_metadata_unchanged": True,
            },
            "buffer_metadata_and_hash_before": {
                "inputs": before_inputs,
                "outputs": before_outputs,
            },
            "buffer_metadata_and_hash_after": {
                "inputs": after_inputs,
                "outputs": after_outputs,
            },
            "timed_block_output_comparisons": timed_block_outputs,
            "blocks_detail": blocks,
            "candidate_block_wins": analyzer.ABBA_BLOCKS,
            "median_saving_ms_per_47_layer_cycle": control_ms - candidate_ms,
            "passed_timing_threshold": True,
            "counter_evidence": "pending_counter_evidence",
        }

    def test_frozen_fixture_and_binary_manifest_are_canonical_and_complete(
        self,
    ) -> None:
        self.assertEqual(contract.sha(FIXTURE), FIXTURE_SHA256)
        self.assertEqual(contract.sha(BINARY_MANIFEST), BINARY_MANIFEST_SHA256)
        self.assertEqual(len(contract.fixture_spec_ids()), 305)
        self.assertEqual(
            [spec["id"] for spec in runner._corpus_specs(self.manifest)],
            contract.fixture_spec_ids(),
        )
        self.assertEqual(
            [spec["id"] for spec in self.specs], contract.fixture_spec_ids()
        )
        binaries = contract._binary_manifest(BINARY_MANIFEST)
        self.assertEqual(set(binaries), {"installed", "candidate", "incumbent"})
        self.assertEqual(
            binaries["candidate"]["_moe_C.abi3.so"]["sha256"],
            contract.CANDIDATE_MOE_SHA256,
        )

    def test_fixture_manifest_rejects_schema_seed_hash_and_canonical_tampering(
        self,
    ) -> None:
        mutations = []
        extra = copy.deepcopy(self.manifest)
        extra["extra"] = True
        mutations.append((extra, True))
        seed = copy.deepcopy(self.manifest)
        seed["random_full"]["seeds"][1] = seed["random_full"]["seeds"][0]
        mutations.append((seed, True))
        missing = copy.deepcopy(self.manifest)
        missing["expected_cpu_input_hashes"].pop(
            next(iter(missing["expected_cpu_input_hashes"]))
        )
        mutations.append((missing, True))
        malformed = copy.deepcopy(self.manifest)
        first = next(iter(malformed["expected_cpu_input_hashes"].values()))
        first["routes_bf16_le_sha256"] = "bad"
        mutations.append((malformed, True))
        mutations.append((copy.deepcopy(self.manifest), False))
        with tempfile.TemporaryDirectory() as temporary:
            for index, (value, canonical) in enumerate(mutations):
                path = Path(temporary) / f"fixture-{index}.json"
                payload = contract.canonical(value) + b"\n"
                if not canonical:
                    payload = json.dumps(value, indent=2).encode() + b"\n"
                path.write_bytes(payload)
                with (
                    mock.patch.object(contract, "_nvme"),
                    self.assertRaises(RuntimeError),
                ):
                    contract.validate_fixture_manifest(path)

    def test_corpus_zero_row_grammar(self) -> None:
        by_id = {spec["id"]: spec for spec in self.specs}
        self.assertEqual(
            analyzer._expected_zero_rows(by_id["routed-finite-slot-9-chunk-2"]),
            [
                row
                for row in range(80)
                if row not in {9 + token * 10 for token in range(6)}
            ],
        )
        self.assertEqual(analyzer._expected_zero_rows(by_id["all-local"]), [])
        self.assertEqual(
            analyzer._expected_zero_rows(by_id["all-remote"]), list(range(80))
        )
        self.assertEqual(
            analyzer._expected_zero_rows(by_id["mixed-remote-zero"]),
            [0, 9, 10, 19, 23, 31, 40, 47, 58, 70, 79],
        )

    def test_w2_source_and_call_are_identical_to_record(self) -> None:
        proof = contract._w2_source_block_hashes()
        self.assertTrue(proof["native"]["identical"])
        self.assertEqual(proof["native"]["sha256"], contract.NATIVE_W2_SHA256)
        self.assertTrue(proof["python"]["identical"])
        self.assertEqual(proof["native"]["policy"], "w4a16_policy_m_8 (N64)")

    def test_tools_have_no_top_level_torch_or_native_runtime_import(self) -> None:
        for name in TOOLS:
            tree = ast.parse((ROOT / name).read_text())
            top_imports = []
            for node in tree.body:
                if isinstance(node, ast.Import):
                    top_imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    top_imports.append(node.module)
            self.assertNotIn("torch", top_imports, name)
            self.assertFalse(
                any(
                    item == "vllm"
                    or item.startswith("vllm.")
                    or item.startswith("vllm_xpu_kernels")
                    for item in top_imports
                ),
                name,
            )
        self.assertNotIn("import torch", (ROOT / TOOLS[0]).read_text())
        self.assertNotIn("import torch", (ROOT / TOOLS[3]).read_text())
        self.assertNotIn("import torch", (ROOT / TOOLS[4]).read_text())

    def test_runner_runtime_root_and_checkpoint_creation_are_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "card"
            created = runner.seal_runtime_root(root)
            self.assertEqual(
                created,
                [
                    ".",
                    "home",
                    "tmp",
                    analyzer.PRE_EPOCHS,
                    analyzer.POST_EPOCHS,
                    "cache",
                    "cache/pycache",
                    "cache/sycl",
                    "cache/torchinductor",
                ],
            )
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            with self.assertRaises((FileExistsError, RuntimeError)):
                runner.seal_runtime_root(root)
            checkpoint = root / "checkpoint.json"
            runner.write_canonical(checkpoint, {"ok": True})
            self.assertEqual(checkpoint.read_bytes(), b'{"ok":true}\n')
            with self.assertRaises(FileExistsError):
                runner.write_canonical(checkpoint, {"ok": False})

    def test_gate_writes_one_canonical_authorization_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "authorization.json"
            contract.write_authorization(path, {"z": 1, "a": 2})
            self.assertEqual(path.read_bytes(), b'{"a":2,"z":1}\n')
            with self.assertRaises(RuntimeError):
                contract.write_authorization(path, {"z": 3})
            alias = Path(temporary) / "alias.json"
            alias.symlink_to(path)
            with self.assertRaises(RuntimeError):
                contract.write_authorization(alias, {"z": 3})

    def test_one_shot_tools_parent_and_fixed_packet_path_are_enforced(self) -> None:
        commit = "a" * 40

        def good_git(repo: Path, *args: str) -> str:
            self.assertEqual(repo, contract.MAIN)
            if args == ("rev-parse", commit + "^"):
                return contract.TOOLING_PARENT_COMMIT
            if args == (
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                commit,
            ):
                return "\n".join(contract.TOOLS.values())
            raise AssertionError(args)

        with mock.patch.object(contract, "git", side_effect=good_git):
            contract._validate_tools_commit(commit)

        def bad_parent(repo: Path, *args: str) -> str:
            if args == ("rev-parse", commit + "^"):
                return "b" * 40
            return "\n".join(contract.TOOLS.values())

        with (
            mock.patch.object(contract, "git", side_effect=bad_parent),
            self.assertRaises(RuntimeError),
        ):
            contract._validate_tools_commit(commit)
        self.assertEqual(
            contract.MAIN / contract.PACKET_REPO_PATH,
            contract.MAIN
            / "data/laguna-s-2.1-gather-finalize-phase-a-authorization-20260724.json",
        )

    def test_packet_template_and_runner_schema_agree_cpu_only(self) -> None:
        suffix = uuid.uuid4().hex
        packet_path = contract.MAIN / contract.PACKET_REPO_PATH
        output_root = contract.ARTIFACT / "runs" / f"test-gather-finalize-{suffix}"
        if packet_path.exists():
            packet = json.loads(packet_path.read_bytes())
        else:
            hashes = {
                **{
                    name: contract.sha(contract.MAIN / path)
                    for name, path in contract.TOOLS.items()
                },
                "fixture": contract.sha(FIXTURE),
                "binary_manifest": contract.sha(BINARY_MANIFEST),
                "main_tools_commit": subprocess.run(
                    ["git", "-C", str(contract.MAIN), "rev-parse", "HEAD"],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip(),
            }
            packet = contract.template(
                fixture=FIXTURE,
                binary_manifest=BINARY_MANIFEST,
                output_root=output_root,
                packet_path=packet_path,
                hashes=hashes,
            )
        card, manifest, fixture_sha, binaries = runner._validate_packet(
            packet, packet_path, FIXTURE, 0
        )
        self.assertEqual(card, packet["cards"][0])
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(fixture_sha, FIXTURE_SHA256)
        self.assertEqual(binaries, packet["binary_manifest"])
        bad = copy.deepcopy(packet)
        bad["selectors"]["VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE"] = "0"
        with self.assertRaises(RuntimeError):
            runner._validate_packet(bad, packet_path, FIXTURE, 0)

    def test_analyzer_epoch_requires_all_literal_and_direct_comparisons(self) -> None:
        names = {
            "control_routed_vs_literal_oracle",
            "candidate_diagnostic_routed_vs_literal_oracle",
            "candidate_diagnostic_routed_vs_control",
            "candidate_diagnostic_scaled_vs_literal_oracle",
            "control_scaled_literal_vs_literal_oracle",
            "candidate_diagnostic_scaled_vs_control_literal",
            "control_final_vs_literal_oracle",
            "candidate_production_final_vs_literal_oracle",
            "candidate_diagnostic_final_vs_literal_oracle",
            "candidate_diagnostic_final_vs_control",
            "control_final_vs_candidate_production",
            "candidate_production_vs_diagnostic_final",
            "candidate_repeat",
            "rank_order_bf16_sum",
            "fused_add_rms_norm_hidden",
            "fused_add_rms_norm_residual",
        }
        spec = self.specs[0]
        expected = self.manifest["expected_cpu_input_hashes"][spec["id"]]
        epoch = {
            "fixture_id": spec["id"],
            "spec": spec,
            "zero_rows": analyzer._expected_zero_rows(spec),
            "input_hashes_before": expected,
            "input_hashes_after": expected,
            "comparisons": {name: comparison(digest(name)) for name in names},
            "all_equal": True,
            "nan_equality_policy": analyzer.NAN_POLICY,
        }
        analyzer._epoch(epoch, 0, spec, expected)
        for name in (
            "candidate_diagnostic_routed_vs_control",
            "control_scaled_literal_vs_literal_oracle",
            "candidate_diagnostic_scaled_vs_control_literal",
            "candidate_diagnostic_final_vs_control",
        ):
            bad = copy.deepcopy(epoch)
            bad["comparisons"].pop(name)
            with self.assertRaises(RuntimeError):
                analyzer._epoch(bad, 0, spec, expected)

    def test_runtime_environment_summary_matches_runner_contract(self) -> None:
        environment = contract.environment(
            contract.ARTIFACT / "runs/test-runtime/card0", 0
        )
        card = {
            "runtime_root": str(contract.ARTIFACT / "runs/test-runtime/card0-runtime"),
            "environment": environment,
        }
        expected = analyzer._expected_runtime_environment(card)
        self.assertEqual(expected["runtime_root"], card["runtime_root"])
        self.assertEqual(len(expected["environment_paths"]), 16)
        self.assertEqual(
            set(expected["environment_paths"]),
            {
                "HOME",
                "TMPDIR",
                "TMP",
                "TEMP",
                "XDG_CACHE_HOME",
                "XDG_CONFIG_HOME",
                "XDG_DATA_HOME",
                "XDG_STATE_HOME",
                "HF_HOME",
                "TRANSFORMERS_CACHE",
                "VLLM_CACHE_ROOT",
                "TRITON_CACHE_DIR",
                "NUMBA_CACHE_DIR",
                "PYTHONPYCACHEPREFIX",
                "SYCL_CACHE_DIR",
                "TORCHINDUCTOR_CACHE_DIR",
            },
        )

    def test_analyzer_recomputes_timing_and_binds_retained_outputs(self) -> None:
        value = self._timing()
        summary = analyzer._timing(
            value,
            {"protocol": contract.PROTOCOL},
            self.specs,
            self.manifest["expected_cpu_input_hashes"],
            self.expected_final_hashes,
        )
        self.assertEqual(summary["candidate_block_wins"], 31)
        self.assertAlmostEqual(summary["median_saving_ms_per_47_layer_cycle"], 0.2)
        bad = copy.deepcopy(value)
        bad["blocks_detail"][0]["saving_ms_per_47_layer_cycle"] = 0.3
        with self.assertRaises(RuntimeError):
            analyzer._timing(
                bad,
                {"protocol": contract.PROTOCOL},
                self.specs,
                self.manifest["expected_cpu_input_hashes"],
                self.expected_final_hashes,
            )
        bad = copy.deepcopy(value)
        bad["timed_block_output_comparisons"][0]["outputs"][0][
            "control_final_vs_candidate_final"
        ]["left_raw_bf16_le_sha256"] = digest("forged")
        with self.assertRaises(RuntimeError):
            analyzer._timing(
                bad,
                {"protocol": contract.PROTOCOL},
                self.specs,
                self.manifest["expected_cpu_input_hashes"],
                self.expected_final_hashes,
            )

    def test_discovery_preflight_is_exactly_five_bound_probes(self) -> None:
        packet = {
            "coordinator_environment": contract.coordinator_environment(
                contract.ARTIFACT / "runs/test-discovery"
            ),
            "cards": contract._paths(
                contract.MAIN / "data/test-discovery.json",
                contract.ARTIFACT / "runs/test-discovery",
                FIXTURE,
            )["cards"],
        }
        unfiltered = [
            {
                "logical_device_id": rank,
                **{
                    key: contract.CARDS[rank][key]
                    for key in ("uuid", "pci_bdf_address", "drm_device")
                },
            }
            for rank in range(4)
        ]
        filtered = [
            {
                "logical_device_id": 0,
                **{
                    key: contract.CARDS[rank][key]
                    for key in ("uuid", "pci_bdf_address", "drm_device")
                },
            }
            for rank in range(4)
        ]
        responses = [("unfiltered", unfiltered)] + [
            (f"filtered-{rank}", [filtered[rank]]) for rank in range(4)
        ]
        with mock.patch.object(
            coordinator, "_discovery", side_effect=responses
        ) as discovery:
            result = coordinator.device_preflight(packet)
        self.assertEqual(discovery.call_count, 5)
        self.assertEqual(result["discovery_count"], 5)
        self.assertEqual(len(result["filtered"]), 4)
        broken = copy.deepcopy(responses)
        broken[2][1][0]["uuid"] = "wrong"
        with (
            mock.patch.object(coordinator, "_discovery", side_effect=broken),
            self.assertRaises(RuntimeError),
        ):
            coordinator.device_preflight(packet)

    def test_coordinator_runtime_dirs_are_fd_anchored_and_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "runtime"
            coordinator._runtime_dirs(root)
            expected = {
                "home",
                "tmp",
                "cache",
                "cache/xdg",
                "cache/xdg-config",
                "cache/xdg-data",
                "cache/xdg-state",
                "cache/huggingface",
                "cache/transformers",
                "cache/vllm",
                "cache/triton",
                "cache/numba",
                "cache/pycache",
                "cache/sycl",
                "cache/torchinductor",
            }
            observed = {
                str(path.relative_to(root)) for path in root.rglob("*") if path.is_dir()
            }
            self.assertEqual(observed, expected)
            with self.assertRaises((FileExistsError, RuntimeError)):
                coordinator._runtime_dirs(root)

    def test_process_capture_reaps_group_on_interrupt(self) -> None:
        process = mock.Mock()
        process.pid = 424242
        process.communicate.side_effect = [KeyboardInterrupt(), (b"out", b"err")]
        with (
            mock.patch.object(coordinator.subprocess, "Popen", return_value=process),
            mock.patch.object(coordinator.os, "killpg") as killpg,
            self.assertRaises(KeyboardInterrupt),
        ):
            coordinator._capture_process(["stub"], {}, 1)
        killpg.assert_called_once_with(process.pid, coordinator.signal.SIGTERM)
        self.assertEqual(process.communicate.call_count, 2)

    def test_evidence_writer_handles_short_writes_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "evidence.json"
            real_write = os.write

            def short_write(descriptor: int, payload: object) -> int:
                view = memoryview(payload)  # type: ignore[arg-type]
                return real_write(descriptor, view[: max(1, len(view) // 2)])

            with mock.patch.object(coordinator.os, "write", side_effect=short_write):
                coordinator.exclusive_json(path, {"payload": "x" * 4096})
            value = json.loads(path.read_bytes())
            self.assertEqual(value, {"payload": "x" * 4096})
            self.assertEqual(path.read_bytes(), contract.canonical(value) + b"\n")
            with self.assertRaises(FileExistsError):
                coordinator.exclusive_json(path, {"payload": "changed"})

    def test_phase_a_status_cannot_escalate_to_counter_or_endpoint_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packet_path = root / "authorization.json"
            packet_path.write_bytes(b'{"packet":"fixture"}\n')
            cards = []
            summaries = []
            for rank in range(4):
                result = root / f"card-{rank}-result.json"
                result.write_bytes(
                    contract.canonical({"rank": rank, "passed": True}) + b"\n"
                )
                physical = copy.deepcopy(contract.CARDS[rank])
                cards.append(
                    {"rank": rank, "physical": physical, "result": str(result)}
                )
                summaries.append(
                    {
                        "rank": rank,
                        "physical": physical,
                        "result_path": str(result),
                        "result_sha256": contract.sha(result),
                        "fixture_manifest_sha256": FIXTURE_SHA256,
                        "fixture_count": 305,
                        "pre_epoch_sequence_sha256": digest(
                            f"pre-epoch-sequence-{rank}"
                        ),
                        "timing": {
                            "candidate_block_wins": 31,
                            "median_saving_ms_per_47_layer_cycle": 0.2,
                        },
                    }
                )
            packet = {
                "packet_path": str(packet_path),
                "fixture": {"path": str(FIXTURE), "sha256": FIXTURE_SHA256},
                "protocol": contract.PROTOCOL,
                "cards": cards,
            }
            value = {
                "format": "laguna-m8-gather-finalize-four-card-timing-exactness-aggregate-v2",
                "status": "component_timing_pass_pending_mandatory_counters",
                "timing_exactness_passed": True,
                "counter_phase_required": True,
                "counter_phase_complete": False,
                "full_component_pass": False,
                "endpoint_authorized": False,
                "packet_sha256": contract.sha(packet_path),
                "fixture_manifest": {
                    "path": str(FIXTURE),
                    "sha256": FIXTURE_SHA256,
                    "corpus_version": contract.FIXTURE_CORPUS_VERSION,
                },
                "cards": summaries,
                "downstream": contract.FALSE_ACTIONS,
            }
            path = root / "aggregate.json"
            path.write_bytes(contract.canonical(value) + b"\n")
            self.assertTrue(coordinator._phase_a_aggregate_valid(packet, path))
            for name in (
                "counter_phase_complete",
                "full_component_pass",
                "endpoint_authorized",
            ):
                bad = copy.deepcopy(value)
                bad[name] = True
                path.unlink()
                path.write_bytes(contract.canonical(bad) + b"\n")
                self.assertFalse(coordinator._phase_a_aggregate_valid(packet, path))
            bad = copy.deepcopy(value)
            bad["cards"][0]["result_sha256"] = digest("forged-result")
            path.unlink()
            path.write_bytes(contract.canonical(bad) + b"\n")
            self.assertFalse(coordinator._phase_a_aggregate_valid(packet, path))
        self.assertEqual(contract.PROTOCOL["campaigns_authorized"], 1)
        self.assertFalse(contract.PROTOCOL["retry_authorized"])
        self.assertFalse(contract.PROTOCOL["endpoint_authorized"])
        self.assertFalse(contract.PROTOCOL["full_component_pass_authorized"])


if __name__ == "__main__":
    unittest.main()
