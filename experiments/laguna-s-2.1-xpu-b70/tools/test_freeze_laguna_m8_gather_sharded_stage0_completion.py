#!/usr/bin/env python3
"""Host-only tests for the M8 gather-sharded Stage-0 completion freezer."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import runpy
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import freeze_laguna_m8_gather_sharded_stage0_completion as completion


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class Stage0CompletionTests(unittest.TestCase):
    REAL_SOURCE_PACKET = (
        Path(completion.__file__).parents[3]
        / "data/laguna-s-2.1-m8-gather-sharded-source-build-ir-20260724.json"
    )
    STORAGE = {
        "filesystem": "ext4",
        "source": "/dev/nvme0n1p2",
        "major_minor": "259:2",
        "mount_point": "/",
        "sysfs_device": "/sys/devices/pci/nvme0/nvme0n1",
    }

    def _write_json(self, path: Path, value: dict[str, Any]) -> str:
        raw = canonical(value)
        if path.exists():
            path.chmod(0o600)
        path.write_bytes(raw)
        path.chmod(0o444)
        return digest(raw)

    def _source_packet(self, root: Path) -> tuple[Path, str]:
        packet = json.loads(self.REAL_SOURCE_PACKET.read_bytes())
        path = root / "source.json"
        return path, self._write_json(path, packet)

    def _fixture(self, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        fixture_root = root / "fixture"
        fixture_root.mkdir()
        for member in sorted(
            completion.FIXTURE_MEMBER_NAMES - {"manifest.json", "analysis.json"}
        ):
            (fixture_root / member).write_bytes(member.encode())
            (fixture_root / member).chmod(0o444)
        epoch_hashes = [f"{index:064x}" for index in range(288)]
        tensors = {
            name: {
                "file": {
                    "route_rows": "route_rows.uint16.le.bin",
                    "weights": "weights.uint32.le.bin",
                    "scale_add_input": "scale_add_input.uint16.le.bin",
                    "four_rank_tail": "four_rank_tail.uint16.le.bin",
                    "residual_input": "residual_input.uint16.le.bin",
                    "norm_weight": "norm_weight.uint16.le.bin",
                }[name],
                "dtype": "<u4" if name == "weights" else "<u2",
                "shape": {
                    "route_rows": [288, 80, 3072],
                    "weights": [288, 8, 10],
                    "scale_add_input": [288, 8, 3072],
                    "four_rank_tail": [288, 3, 8, 3072],
                    "residual_input": [288, 8, 3072],
                    "norm_weight": [288, 3072],
                }[name],
                "sha256": digest(name.encode()),
                "epoch_sha256": epoch_hashes,
            }
            for name in sorted(completion.TENSOR_NAMES)
        }
        manifest = {
            "format": completion.FIXTURE_FORMAT,
            "production": True,
            "pre_timing_epochs": 256,
            "post_timing_epochs": 32,
            "epochs": 288,
            "geometry": {"tokens": 8, "topk": 10, "hidden": 3072, "ranks": 4},
            "canonical_route_map": {
                "file": "canonical_route_map.int32.le.bin",
                "dtype": "<i4",
                "shape": [8, 10],
                "sha256": "c" * 64,
                "definition": "arange(80).reshape(8,10)",
            },
            "tensors": tensors,
        }
        manifest_path = fixture_root / "manifest.json"
        manifest_digest = self._write_json(manifest_path, manifest)
        analysis = {
            "status": "passed",
            "manifest_sha256": manifest_digest,
            "tensors": {
                name: {
                    "sha256": tensor["sha256"],
                    "epoch_sha256": tensor["epoch_sha256"],
                }
                for name, tensor in tensors.items()
            },
            "coverage": {
                "all_65536": True,
                "all_fp32_edge_classes": True,
                "all_1024_local_zero_masks": True,
                "all_slots_independently_active": True,
                "all_local": True,
                "all_remote_zero": True,
                "zero_rows_literal_uint16_zero": True,
                "local_rows_match_formula": True,
                "canonical_route_map": True,
                "ordered_cancellation_witness": True,
                "bf16_midpoint_witness": True,
                "uint16_patterns_present": 65536,
            },
            "deterministic_bytes_match": True,
            "hashes_match_manifest": True,
        }
        analysis_path = fixture_root / "analysis.json"
        analysis_digest = self._write_json(analysis_path, analysis)
        return (
            {
                "root": str(fixture_root),
                "manifest": str(manifest_path),
                "analysis": str(analysis_path),
                "analysis_sha256": analysis_digest,
            },
            analysis,
        )

    def _operational(self, root: Path) -> tuple[Path, str]:
        report = {
            "format": completion.OPERATIONAL_FORMAT,
            "status": "passed",
            "output": {"storage": dict(self.STORAGE)},
        }
        path = root / "operational.json"
        return path, self._write_json(path, report)

    def _tools(self) -> dict[str, Any]:
        repo = Path(completion.__file__).parents[3]
        return {
            "commit": "d" * 40,
            "bindings": [
                {
                    "role": role,
                    "path": path,
                    "sha256": digest((repo / path).read_bytes()),
                    "test_path": test_path,
                    "test_sha256": digest((repo / test_path).read_bytes()),
                }
                for role, (path, test_path) in completion.ROLE_PATHS.items()
            ],
        }

    def _verified_tools(self) -> dict[str, Any]:
        return completion._verify_tool_bindings(
            self._tools(),
            committed_blob_reader=self._committed_reader,
            commit_verifier=self._commit_verifier,
        )

    def _declaration(self, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        source_path, source_digest = self._source_packet(root)
        fixture, analysis = self._fixture(root)
        operational_path, operational_digest = self._operational(root)
        source = json.loads(source_path.read_bytes())
        completion.SOURCE_PACKET_PATH = source_path
        completion.SOURCE_PACKET_SHA256 = source_digest
        completion.DEVICE_IR_REPORT_SHA256 = source["device_ir"]["report_sha256"]
        completion.CANDIDATE_BINARY_SHA256 = source["build"]["binary"]["sha256"]
        completion.FIXTURE_ROOT = Path(fixture["root"])
        completion.FIXTURE_MANIFEST_SHA256 = digest(
            Path(fixture["manifest"]).read_bytes()
        )
        completion.FIXTURE_ANALYSIS_SHA256 = fixture["analysis_sha256"]
        completion.OPERATIONAL_REPORT_PATH = operational_path
        completion.OPERATIONAL_REPORT_SHA256 = operational_digest
        return (
            {
                "format": completion.INPUT_FORMAT,
                "source_packet": {"path": str(source_path), "sha256": source_digest},
                "fixture": fixture,
                "operational_preflight": {"report": str(operational_path), "sha256": operational_digest},
                "tools": self._tools(),
                "independent_audits": self._audits(root, source_path, source_digest),
            },
            analysis,
        )

    def _bundle(self) -> dict[str, Any]:
        return {
            "root": "/mnt/fast-ai/bundle",
            "manifest": "/mnt/fast-ai/bundle/manifest.json",
            "manifest_sha256": "a" * 64,
            "prepared": "/mnt/fast-ai/bundle/bundle-prepared.json",
            "prepared_sha256": "b" * 64,
            "library_sha256": {
                name: record["sha256"]
                for name, record in completion.BUNDLE_EXPECTED.items()
            },
            "status": "validated_host_only_not_imported",
            "validation_protocol": "separate_successful_validate_existing_invocation_required",
            "storage": dict(self.STORAGE),
        }

    def _committed_reader(self, _commit: str, path: str) -> bytes:
        return (Path(completion.__file__).parents[3] / path).read_bytes()

    @staticmethod
    def _commit_verifier(_commit: str, _paths: set[str]) -> None:
        """Unit tests model a previously committed clean tool closure."""

    def _audits(self, root: Path, source_path: Path, source_digest: str) -> list[dict[str, str]]:
        tools = completion._verify_tool_bindings(
            self._tools(),
            committed_blob_reader=self._committed_reader,
            commit_verifier=self._commit_verifier,
        )
        result: list[dict[str, str]] = []
        for index in range(2):
            path = root / f"audit-{index}.json"
            audit = {
                "format": completion.AUDIT_FORMAT,
                "status": completion.AUDIT_STATUS,
                "read_only": True,
                "audit_id": f"read-only-audit-{index}",
                "reviewer_id": f"reviewer-{index}",
                "reviewer_authority": completion.AUDIT_REVIEWER_AUTHORITY,
                "scopes": sorted(completion.REQUIRED_AUDIT_SCOPES),
                "reviewed_source_packet": {"path": str(source_path), "sha256": source_digest},
                "reviewed_tool_hashes": completion._tool_hashes(tools),
                "blocker_resolution": {
                    key: True for key in completion.REQUIRED_AUDIT_BLOCKER_KEYS
                },
                "open_findings": [],
            }
            result.append({"path": str(path), "sha256": self._write_json(path, audit)})
            path.chmod(0o444)
        return result

    def _freeze(self, root: Path) -> tuple[Path, dict[str, Any]]:
        declaration, analysis = self._declaration(root)
        input_path = root / "input.json"
        self._write_json(input_path, declaration)
        output = root / "certificate.json"
        original_prefix = completion.ROOT_PREFIX
        original_data_root = completion.TRACKED_DATA_ROOT
        completion.ROOT_PREFIX = root
        completion.TRACKED_DATA_ROOT = root
        try:
            certificate = completion.freeze_certificate(
                input_path,
                output,
                fixture_analyzer=lambda _path: analysis,
                bundle_validator=self._bundle,
                storage_attestor=lambda _path: dict(self.STORAGE),
                committed_blob_reader=self._committed_reader,
                commit_verifier=self._commit_verifier,
            )
        finally:
            completion.ROOT_PREFIX = original_prefix
            completion.TRACKED_DATA_ROOT = original_data_root
        return output, certificate

    def test_freezes_canonical_read_only_certificate_and_revalidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, certificate = self._freeze(root)
            self.assertEqual(output.read_bytes(), canonical(certificate))
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o444)
            self.assertEqual(certificate["native_bundle"]["status"], "validated_host_only_not_imported")
            self.assertEqual(certificate["fixture"]["tensors"].keys(), completion.TENSOR_NAMES)
            original_prefix = completion.ROOT_PREFIX
            original_data_root = completion.TRACKED_DATA_ROOT
            completion.ROOT_PREFIX = root
            completion.TRACKED_DATA_ROOT = root
            try:
                with mock.patch.object(
                    completion,
                    "_open_internal_evidence",
                    wraps=completion._open_internal_evidence,
                ) as opened:
                    validated = completion.validate_certificate(
                        output,
                        root / "input.json",
                        fixture_analyzer=lambda _path: json.loads((root / "fixture" / "analysis.json").read_bytes()),
                        bundle_validator=self._bundle,
                        storage_attestor=lambda _path: dict(self.STORAGE),
                        committed_blob_reader=self._committed_reader,
                        commit_verifier=self._commit_verifier,
                    )
                    certificate_only = completion.validate_certificate_only(
                        output,
                        fixture_analyzer=lambda _path: json.loads((root / "fixture" / "analysis.json").read_bytes()),
                        bundle_validator=self._bundle,
                        storage_attestor=lambda _path: dict(self.STORAGE),
                        committed_blob_reader=self._committed_reader,
                        commit_verifier=self._commit_verifier,
                    )
                input_opens = [
                    call
                    for call in opened.call_args_list
                    if call.args[:2]
                    == (root / "input.json", "stage0 completion input")
                ]
                self.assertEqual(len(input_opens), 2)
            finally:
                completion.ROOT_PREFIX = original_prefix
                completion.TRACKED_DATA_ROOT = original_data_root
            self.assertEqual(validated, certificate)
            self.assertEqual(certificate_only, certificate)

    def test_rejects_per_epoch_fixture_drift_before_bundle_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            declaration, analysis = self._declaration(root)
            declaration["fixture"]["analysis_sha256"] = digest(canonical(analysis))
            analysis["tensors"]["weights"]["epoch_sha256"][7] = "f" * 64
            input_path = root / "input.json"
            self._write_json(input_path, declaration)
            original_prefix = completion.ROOT_PREFIX
            original_data_root = completion.TRACKED_DATA_ROOT
            completion.ROOT_PREFIX = root
            completion.TRACKED_DATA_ROOT = root
            try:
                with self.assertRaisesRegex(RuntimeError, "fixture analysis is not"):
                    completion.freeze_certificate(
                        input_path,
                        root / "certificate.json",
                        fixture_analyzer=lambda _path: analysis,
                        bundle_validator=lambda: self.fail("bundle validator must not run"),
                        storage_attestor=lambda _path: dict(self.STORAGE),
                        committed_blob_reader=self._committed_reader,
                        commit_verifier=self._commit_verifier,
                    )
            finally:
                completion.ROOT_PREFIX = original_prefix
                completion.TRACKED_DATA_ROOT = original_data_root

    def test_rejects_uncommitted_tool_content_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, _certificate = self._freeze(root)
            original_prefix = completion.ROOT_PREFIX
            original_data_root = completion.TRACKED_DATA_ROOT
            completion.ROOT_PREFIX = root
            completion.TRACKED_DATA_ROOT = root
            try:
                with self.assertRaises(FileExistsError):
                    completion.freeze_certificate(
                        root / "input.json",
                        output,
                        fixture_analyzer=lambda _path: json.loads((root / "fixture" / "analysis.json").read_bytes()),
                        bundle_validator=self._bundle,
                        storage_attestor=lambda _path: dict(self.STORAGE),
                        committed_blob_reader=self._committed_reader,
                        commit_verifier=self._commit_verifier,
                    )
                with self.assertRaisesRegex(RuntimeError, "committed tool digest drift"):
                    completion.build_certificate(
                        json.loads((root / "input.json").read_bytes()),
                        root / "different.json",
                        input_path=root / "input.json",
                        fixture_analyzer=lambda _path: json.loads((root / "fixture" / "analysis.json").read_bytes()),
                        bundle_validator=lambda: self.fail("bundle validator must not run"),
                        storage_attestor=lambda _path: dict(self.STORAGE),
                        committed_blob_reader=lambda _commit, _path: b"not committed",
                        commit_verifier=self._commit_verifier,
                    )
            finally:
                completion.ROOT_PREFIX = original_prefix
                completion.TRACKED_DATA_ROOT = original_data_root

    def test_bundle_validation_uses_only_fixed_validate_existing_child(self) -> None:
        expected = self._bundle()
        emitted = json.dumps(expected, sort_keys=True) + "\n"
        with mock.patch.object(
            completion.subprocess,
            "run",
            return_value=completion.subprocess.CompletedProcess(
                args=[], returncode=0, stdout=emitted, stderr=""
            ),
        ) as run:
            with self.assertRaisesRegex(RuntimeError, "root identity substitution"):
                completion._validate_bundle_subprocess(tools=self._verified_tools())
        self.assertEqual(
            run.call_args.args[0],
            [
                mock.ANY,
                "-I",
                "-S",
                "-c",
                completion.VALIDATOR_BOOTSTRAP,
                mock.ANY,
                mock.ANY,
            ],
        )
        self.assertRegex(run.call_args.args[0][0], r"^/proc/self/fd/\d+$")
        self.assertEqual(run.call_args.kwargs["cwd"], "/")
        self.assertEqual(run.call_args.kwargs["env"], completion.SUBPROCESS_ENVIRONMENT)
        self.assertEqual(run.call_args.kwargs["timeout"], 30)
        self.assertTrue(run.call_args.kwargs["capture_output"])
        self.assertTrue(run.call_args.kwargs["text"])
        self.assertFalse(run.call_args.kwargs["check"])
        self.assertEqual(len(run.call_args.kwargs["pass_fds"]), 3)
        self.assertFalse(any(key.startswith("GIT_") for key in run.call_args.kwargs["env"]))

    def test_bundle_child_result_is_independently_reopened_and_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "bundle"
            root.mkdir()
            entries = {
                "one.so": {"role": "one", "source": "/source/one.so", "sha256": digest(b"one")},
                "two.so": {"role": "two", "source": "/source/two.so", "sha256": digest(b"two")},
            }
            for name, contents in (("one.so", b"one"), ("two.so", b"two")):
                path = root / name
                path.write_bytes(contents)
                path.chmod(0o444)
            libraries = {
                name: {
                    "role": entry["role"], "source": entry["source"], "path": str(root / name),
                    "sha256": entry["sha256"], "bytes": len(name.split(".")[0]),
                }
                for name, entry in entries.items()
            }
            manifest = {
                "format": completion.BUNDLE_FORMAT,
                "status": "prepared_host_only_not_imported", "root": str(root),
                "storage": self.STORAGE,
                "candidate_kernel_commit": completion.CANDIDATE_KERNELS,
                "approved_record_kernel_commit": completion.RECORD_KERNELS,
                "approved_record_vllm_commit": completion.RECORD_VLLM,
                "libraries": libraries,
                "actions_not_performed": [
                    "Torch import", "native-library import", "XPU enumeration", "XPU allocation",
                    "XPU primitive", "model load", "generation",
                ],
            }
            manifest_raw = canonical(manifest)
            (root / "manifest.json").write_bytes(manifest_raw)
            (root / "manifest.json").chmod(0o444)
            prepared = {
                "format": completion.BUNDLE_PREPARED_FORMAT,
                "status": "prepared_requires_separate_validation", "root": str(root),
                "manifest_sha256": digest(manifest_raw),
                "library_sha256": {name: item["sha256"] for name, item in sorted(entries.items())},
            }
            prepared_raw = canonical(prepared)
            (root / "bundle-prepared.json").write_bytes(prepared_raw)
            (root / "bundle-prepared.json").chmod(0o444)
            root.chmod(0o555)
            child = {
                "root": str(root), "manifest": str(root / "manifest.json"),
                "manifest_sha256": digest(manifest_raw), "prepared": str(root / "bundle-prepared.json"),
                "prepared_sha256": digest(prepared_raw),
                "library_sha256": {name: item["sha256"] for name, item in sorted(entries.items())},
                "status": "validated_host_only_not_imported",
                "validation_protocol": "separate_successful_validate_existing_invocation_required",
                "storage": self.STORAGE,
            }
            with mock.patch.object(completion, "BUNDLE_ROOT", root), \
                 mock.patch.object(completion, "BUNDLE_EXPECTED", entries), \
                 mock.patch.object(completion, "BUNDLE_FILENAMES", frozenset(entries)), \
                 mock.patch.object(
                     completion.subprocess, "run",
                     return_value=completion.subprocess.CompletedProcess(
                         args=[], returncode=0, stdout=json.dumps(child, sort_keys=True) + "\n", stderr=""
                     ),
                 ):
                verified = completion._validate_bundle_subprocess(
                    tools=self._verified_tools(),
                    storage_attestor=lambda _path: dict(self.STORAGE)
                )
                different = dict(self.STORAGE)
                different["mount_point"] = "/mnt/fast-ai"
                with self.assertRaisesRegex(RuntimeError, "differs from independent"):
                    completion._validate_bundle_subprocess(
                        tools=self._verified_tools(),
                        storage_attestor=lambda _path: different
                    )
            self.assertEqual(verified["libraries"]["one.so"]["mode"], 0o444)
            self.assertEqual(verified["libraries"]["two.so"]["bytes"], 3)
            process = verified["validator_process"]
            self.assertEqual(
                process["argv"],
                [
                    "/proc/self/fd/<retained-pinned-python>", "-I", "-S", "-c",
                    f"sha256:{digest(completion.VALIDATOR_BOOTSTRAP.encode())}",
                    "/proc/self/fd/<sealed-helper-closure>",
                    "/proc/self/fd/<sealed-bundle-freezer>",
                ],
            )
            self.assertEqual(
                process["script_argv"],
                ["/proc/self/fd/<sealed-bundle-freezer>", "--validate-existing"],
            )
            self.assertEqual(
                process["execution"],
                "retained-o-nofollow-fd-plus-read-only-anonymous-staging",
            )
            self.assertNotIn(str(completion.FREEZER), process["argv"])

    def test_rejects_output_outside_the_two_internal_nvme_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / "outside-certificate.json"
            original_prefix = completion.ROOT_PREFIX
            original_data_root = completion.TRACKED_DATA_ROOT
            completion.ROOT_PREFIX = root
            completion.TRACKED_DATA_ROOT = root
            try:
                with self.assertRaisesRegex(RuntimeError, "outside approved"):
                    completion._require_nvme_output(
                        outside,
                        lambda _path: dict(self.STORAGE),
                    )
            finally:
                completion.ROOT_PREFIX = original_prefix
                completion.TRACKED_DATA_ROOT = original_data_root

    def test_rejects_external_usb_evidence_and_intermediate_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_prefix, original_data_root = completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT
            completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = root, root
            try:
                evidence = root / "input.json"
                evidence.write_bytes(b"{}\n")
                evidence.chmod(0o444)
                usb = dict(self.STORAGE)
                usb.update({"source": "/dev/sda1", "major_minor": "8:1"})
                with self.assertRaisesRegex(RuntimeError, "not on the frozen internal NVMe"):
                    completion._require_internal_evidence(
                        evidence,
                        "stage0 completion input",
                        lambda _path: usb,
                    )
                outside = root.parent / "outside-input.json"
                with self.assertRaisesRegex(RuntimeError, "outside approved"):
                    completion._require_internal_evidence(
                        outside,
                        "stage0 completion input",
                        lambda _path: dict(self.STORAGE),
                    )
                real = root / "real"
                real.mkdir()
                linked = root / "linked"
                linked.symlink_to(real, target_is_directory=True)
                with self.assertRaisesRegex(RuntimeError, "intermediate symlink"):
                    completion._open_output_parent(
                        linked / "certificate.json",
                        lambda _path: dict(self.STORAGE),
                    )
                parent = root / "parent"
                parent.mkdir()
                replacement = root / "replacement"
                replacement.mkdir()
                moved = root / "moved-parent"

                def swap_parent(_fd_path: Path) -> dict[str, str]:
                    parent.rename(moved)
                    replacement.rename(parent)
                    return dict(self.STORAGE)

                with self.assertRaisesRegex(RuntimeError, "changed during attestation"):
                    completion._open_output_parent(
                        parent / "certificate.json",
                        swap_parent,
                    )
            finally:
                completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = original_prefix, original_data_root

    def test_internal_evidence_rejects_replacement_during_fd_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_prefix, original_data_root = completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT
            completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = root, root
            try:
                evidence = root / "input.json"
                evidence.write_bytes(b"{}\n")
                evidence.chmod(0o444)
                replacement = root / "replacement.json"
                replacement.write_bytes(b'{"replaced":true}\n')
                replacement.chmod(0o444)

                def replace_after_fd_attestation(fd_path: Path) -> dict[str, str]:
                    self.assertRegex(str(fd_path), r"^/proc/self/fd/\d+$")
                    replacement.replace(evidence)
                    return dict(self.STORAGE)

                with self.assertRaisesRegex(
                    RuntimeError, "(metadata changed during FD attestation|namespace changed while retained)"
                ):
                    completion._open_internal_evidence(
                        evidence, "stage0 completion input", replace_after_fd_attestation
                    )
            finally:
                completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = original_prefix, original_data_root

    def test_rejects_role_and_known_evidence_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            declaration, analysis = self._declaration(root)
            altered_tools = json.loads(json.dumps(declaration["tools"]))
            altered_tools["bindings"][0]["path"] = altered_tools["bindings"][1]["path"]
            with self.assertRaisesRegex(RuntimeError, "role path substitution"):
                completion._verify_tool_bindings(
                    altered_tools,
                    committed_blob_reader=self._committed_reader,
                )
            forged_source = dict(declaration["source_packet"])
            forged_source["path"] = str(root / "forged-source.json")
            (root / "forged-source.json").write_bytes((root / "source.json").read_bytes())
            forged_source["sha256"] = digest((root / "forged-source.json").read_bytes())
            with self.assertRaisesRegex(RuntimeError, "source packet identity substitution"):
                completion._verify_source_packet(forged_source)
            forged_fixture = dict(declaration["fixture"])
            forged_fixture["root"] = str(root / "forged-fixture")
            with self.assertRaisesRegex(RuntimeError, "fixture (root identity drift|identity substitution)"):
                completion._verify_fixture(
                    forged_fixture,
                    fixture_analyzer=lambda _path: analysis,
                )
            forged_operational = dict(declaration["operational_preflight"])
            forged_operational["report"] = str(root / "forged-operational.json")
            (root / "forged-operational.json").write_bytes((root / "operational.json").read_bytes())
            forged_operational["sha256"] = digest((root / "forged-operational.json").read_bytes())
            with self.assertRaisesRegex(RuntimeError, "operational report identity substitution"):
                completion._verify_operational(forged_operational)
            coverage_bad = json.loads(json.dumps(analysis))
            coverage_bad["coverage"]["all_65536"] = False
            analysis_path = root / "fixture" / "analysis.json"
            analysis_digest = self._write_json(analysis_path, coverage_bad)
            fixture_bad = dict(declaration["fixture"])
            fixture_bad["analysis_sha256"] = analysis_digest
            completion.FIXTURE_ANALYSIS_SHA256 = analysis_digest
            original_prefix, original_data_root = completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT
            completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = root, root
            try:
                with self.assertRaisesRegex(RuntimeError, "fixture coverage proof drift"):
                    completion._verify_fixture(
                        fixture_bad,
                        fixture_analyzer=lambda _path: coverage_bad,
                        storage_attestor=lambda _path: dict(self.STORAGE),
                    )
            finally:
                completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = original_prefix, original_data_root

    def test_rejects_bundle_name_or_digest_forgery(self) -> None:
        forged = self._bundle()
        name = next(iter(forged["library_sha256"]))
        forged["library_sha256"][name] = "0" * 64
        with mock.patch.object(
            completion.subprocess,
            "run",
            return_value=completion.subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(forged, sort_keys=True) + "\n",
                stderr="",
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "library proof drift"):
                completion._validate_bundle_subprocess(tools=self._verified_tools())

    def test_audits_fail_closed_for_zero_one_mutable_and_unresolved_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_prefix = completion.ROOT_PREFIX
            original_data_root = completion.TRACKED_DATA_ROOT
            completion.ROOT_PREFIX = root
            completion.TRACKED_DATA_ROOT = root
            self.addCleanup(setattr, completion, "ROOT_PREFIX", original_prefix)
            self.addCleanup(setattr, completion, "TRACKED_DATA_ROOT", original_data_root)
            declaration, _analysis = self._declaration(root)
            source = completion._verify_source_packet(
                declaration["source_packet"],
                storage_attestor=lambda _path: dict(self.STORAGE),
            )
            tools = completion._verify_tool_bindings(
                declaration["tools"],
                committed_blob_reader=self._committed_reader,
                commit_verifier=self._commit_verifier,
            )
            with self.assertRaisesRegex(RuntimeError, "at least two"):
                completion._verify_independent_audits(
                    [],
                    source_packet=source,
                    tools=tools,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )
            with self.assertRaisesRegex(RuntimeError, "at least two"):
                completion._verify_independent_audits(
                    declaration["independent_audits"][:1],
                    source_packet=source,
                    tools=tools,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )
            mutable = Path(declaration["independent_audits"][0]["path"])
            mutable.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError, "exact 0444 regular file"):
                completion._verify_independent_audits(
                    declaration["independent_audits"],
                    source_packet=source,
                    tools=tools,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )
            mutable.chmod(0o644)
            bad = json.loads(mutable.read_bytes())
            bad["blocker_resolution"] = {"a_real_blocker": False}
            declaration["independent_audits"][0]["sha256"] = self._write_json(mutable, bad)
            mutable.chmod(0o444)
            with self.assertRaisesRegex(RuntimeError, "unresolved blockers"):
                completion._verify_independent_audits(
                    declaration["independent_audits"],
                    source_packet=source,
                    tools=tools,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )

    def test_audit_identity_scope_hash_and_internal_path_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_prefix, original_data_root = completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT
            completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = root, root
            self.addCleanup(setattr, completion, "ROOT_PREFIX", original_prefix)
            self.addCleanup(setattr, completion, "TRACKED_DATA_ROOT", original_data_root)
            declaration, _analysis = self._declaration(root)
            source = completion._verify_source_packet(
                declaration["source_packet"],
                storage_attestor=lambda _path: dict(self.STORAGE),
            )
            tools = completion._verify_tool_bindings(
                declaration["tools"],
                committed_blob_reader=self._committed_reader,
                commit_verifier=self._commit_verifier,
            )
            second_record = declaration["independent_audits"][1]
            second_path = Path(second_record["path"])
            original = json.loads(second_path.read_bytes())

            def install(value: dict[str, Any]) -> None:
                second_path.chmod(0o644)
                second_record["sha256"] = self._write_json(second_path, value)
                second_path.chmod(0o444)

            def verify() -> None:
                completion._verify_independent_audits(
                    declaration["independent_audits"],
                    source_packet=source,
                    tools=tools,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )

            first = json.loads(Path(declaration["independent_audits"][0]["path"]).read_bytes())
            changed = json.loads(json.dumps(original))
            changed["audit_id"] = first["audit_id"]
            install(changed)
            with self.assertRaisesRegex(RuntimeError, "identity is not distinct"):
                verify()
            changed = json.loads(json.dumps(original))
            changed["reviewer_id"] = first["reviewer_id"]
            install(changed)
            with self.assertRaisesRegex(RuntimeError, "reviewer is not distinct"):
                verify()
            changed = json.loads(json.dumps(original))
            changed["reviewer_authority"] = "self_asserted"
            install(changed)
            with self.assertRaisesRegex(RuntimeError, "reviewer is not distinct"):
                verify()
            changed = json.loads(json.dumps(original))
            changed["scopes"] = changed["scopes"][:-1]
            install(changed)
            with self.assertRaisesRegex(RuntimeError, "scope is incomplete"):
                verify()
            changed = json.loads(json.dumps(original))
            changed["blocker_resolution"].pop(next(iter(completion.REQUIRED_AUDIT_BLOCKER_KEYS)))
            install(changed)
            with self.assertRaisesRegex(RuntimeError, "unresolved blockers"):
                verify()
            changed = json.loads(json.dumps(original))
            changed["open_findings"] = ["still open"]
            install(changed)
            with self.assertRaisesRegex(RuntimeError, "unresolved blockers"):
                verify()
            changed = json.loads(json.dumps(original))
            changed["reviewed_tool_hashes"].pop(next(iter(changed["reviewed_tool_hashes"])))
            install(changed)
            with self.assertRaisesRegex(RuntimeError, "tool identity drift"):
                verify()
            changed = json.loads(json.dumps(original))
            changed["reviewed_source_packet"]["sha256"] = "0" * 64
            install(changed)
            with self.assertRaisesRegex(RuntimeError, "source identity drift"):
                verify()
            install(original)
            outside = root.parent / f"{root.name}-outside-audit.json"
            outside.write_bytes(second_path.read_bytes())
            outside.chmod(0o444)
            second_record["path"] = str(outside)
            second_record["sha256"] = digest(outside.read_bytes())
            try:
                with self.assertRaisesRegex(RuntimeError, "outside approved"):
                    verify()
            finally:
                outside.chmod(0o644)
                outside.unlink()

    def test_certificate_reconciles_declaration_and_parent_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, _certificate = self._freeze(root)
            original_prefix, original_data_root = completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT
            completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = root, root
            try:
                input_path = root / "input.json"
                changed = json.loads(input_path.read_bytes())
                changed["source_packet"] = dict(changed["source_packet"])
                changed["source_packet"]["path"] = str(root / "same-format-substitution.json")
                (root / "same-format-substitution.json").write_bytes((root / "source.json").read_bytes())
                changed["source_packet"]["sha256"] = digest((root / "source.json").read_bytes())
                self._write_json(input_path, changed)
                with self.assertRaisesRegex(
                    RuntimeError,
                    "(input closure drift|source packet identity substitution)",
                ):
                    completion.validate_certificate_only(
                        output,
                        fixture_analyzer=lambda _path: json.loads((root / "fixture" / "analysis.json").read_bytes()),
                        bundle_validator=self._bundle,
                        storage_attestor=lambda _path: dict(self.STORAGE),
                        committed_blob_reader=self._committed_reader,
                        commit_verifier=self._commit_verifier,
                    )
                parent_fd, _storage, identity = completion._open_output_parent(
                    root / "other.json", lambda _path: dict(self.STORAGE)
                )
                try:
                    with self.assertRaisesRegex(RuntimeError, "parent descriptor drift"):
                        completion._write_exclusive(
                            root / "other.json", b"{}\n", parent_fd=parent_fd,
                            parent_identity={"device": identity["device"] + 1, "inode": identity["inode"]},
                        )
                finally:
                    os.close(parent_fd)
            finally:
                completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = original_prefix, original_data_root

    def test_rejects_non_commit_and_uncommitted_declared_paths(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "canonical commit"):
            completion._verify_reachable_clean_commit("d" * 40, set())
        head = subprocess.run(
            ["git", "-C", str(Path(completion.__file__).parents[3]), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        declared = completion.ROLE_PATHS["stage0_completion_generator"][0]
        with self.assertRaisesRegex(RuntimeError, "not clean and precommitted"):
            completion._verify_reachable_clean_commit(head, {declared})
        wrong_name = self._bundle()
        digest_value = next(iter(wrong_name["library_sha256"].values()))
        wrong_name["library_sha256"] = {"forged.so": digest_value}
        with mock.patch.object(
            completion.subprocess,
            "run",
            return_value=completion.subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(wrong_name, sort_keys=True) + "\n",
                stderr="",
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "library proof drift"):
                completion._validate_bundle_subprocess(tools=self._verified_tools())

    def test_git_commands_pin_binary_repo_environment_timeout_and_output(self) -> None:
        commit = "a" * 40
        replies = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout=commit + "\n", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ]
        with mock.patch.object(completion.subprocess, "run", side_effect=replies) as run:
            completion._verify_reachable_clean_commit(commit, set())
        self.assertEqual(run.call_count, 3)
        for call in run.call_args_list:
            argv = call.args[0]
            self.assertRegex(argv[0], r"^/proc/self/fd/\d+$")
            self.assertIn("--no-optional-locks", argv)
            self.assertIn("--literal-pathspecs", argv)
            self.assertIn(f"safe.directory={completion.REPOSITORY_ROOT}", argv)
            self.assertEqual(call.kwargs["cwd"], str(completion.REPOSITORY_ROOT))
            self.assertEqual(call.kwargs["env"], completion.SUBPROCESS_ENVIRONMENT)
            self.assertEqual(call.kwargs["timeout"], 10)
            self.assertEqual(len(call.kwargs["pass_fds"]), 1)
            self.assertFalse(any(key.startswith("GIT_") for key in call.kwargs["env"]))
        noisy = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=commit + "\n", stderr="warning\n"
        )
        with mock.patch.object(completion.subprocess, "run", return_value=noisy):
            with self.assertRaisesRegex(RuntimeError, "canonical commit"):
                completion._verify_reachable_clean_commit(commit, set())
        with mock.patch.object(
            completion.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=10),
        ):
            with self.assertRaisesRegex(RuntimeError, "Git command timed out"):
                completion._verify_reachable_clean_commit(commit, set())

    def test_pinned_executable_runs_retained_inode_after_path_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "tool"
            original = b"#!/bin/sh\necho original\n"
            executable.write_bytes(original)
            executable.chmod(0o500)
            replacement = root / "replacement"
            replacement.write_bytes(b"#!/bin/sh\necho replacement\n")
            replacement.chmod(0o500)
            observed: list[bytes] = []

            def replace_while_exec(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
                replacement.replace(executable)
                observed.append(Path(argv[0]).read_bytes())
                return subprocess.CompletedProcess(argv, 0, "", "")

            with mock.patch.object(completion.subprocess, "run", side_effect=replace_while_exec):
                result = completion._run_pinned_executable(
                    executable, digest(original), "test executable", ["--version"],
                    text=True, timeout=1, cwd=root,
                    environment=completion.SUBPROCESS_ENVIRONMENT,
                )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(observed, [original])
            self.assertEqual(executable.read_bytes(), b"#!/bin/sh\necho replacement\n")

    def test_descriptor_backed_python_bootstrap_imports_only_sealed_helper(self) -> None:
        archive_stream = completion.io.BytesIO()
        with completion.zipfile.ZipFile(
            archive_stream, "w", compression=completion.zipfile.ZIP_STORED
        ) as archive:
            archive.writestr("sealed_helper.py", "VALUE = 'sealed-helper'\n")
        closure_fd = completion._sealed_staging_fd(
            "test-helper-closure", archive_stream.getvalue()
        )
        script_fd = completion._sealed_staging_fd(
            "test-script", "import sealed_helper; print(sealed_helper.VALUE)\n".encode()
        )
        try:
            result = completion._run_pinned_executable(
                completion.PYTHON_EXECUTABLE,
                completion.PYTHON_EXECUTABLE_SHA256,
                "test Python",
                [
                    "-I", "-S", "-c", completion.VALIDATOR_BOOTSTRAP,
                    f"/proc/self/fd/{closure_fd}", f"/proc/self/fd/{script_fd}",
                ],
                text=True,
                timeout=10,
                cwd=Path("/"),
                environment=completion.SUBPROCESS_ENVIRONMENT,
                extra_fds=(closure_fd, script_fd),
            )
        finally:
            os.close(script_fd)
            os.close(closure_fd)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "sealed-helper\n")

    def test_both_certificate_validators_retain_certificate_during_rebuild(self) -> None:
        for certificate_only in (False, True):
            with self.subTest(certificate_only=certificate_only), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output, frozen_certificate = self._freeze(root)
                replacement = root / "replacement-certificate.json"
                replacement.write_bytes(output.read_bytes())
                replacement.chmod(0o444)
                analysis = json.loads((root / "fixture" / "analysis.json").read_bytes())
                swapped = False

                def swap_after_evidence_rebuild() -> dict[str, Any]:
                    nonlocal swapped
                    if not swapped:
                        replacement.replace(output)
                        swapped = True
                    return self._bundle()

                common = {
                    "fixture_analyzer": lambda _path: analysis,
                    "bundle_validator": swap_after_evidence_rebuild,
                    "storage_attestor": lambda _path: dict(self.STORAGE),
                    "committed_blob_reader": self._committed_reader,
                    "commit_verifier": self._commit_verifier,
                }
                original_prefix, original_data_root = completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT
                completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = root, root
                try:
                    with mock.patch.object(
                        completion,
                        "_verify_tool_bindings",
                        return_value=frozen_certificate["tools"],
                    ):
                        with self.assertRaisesRegex(
                            RuntimeError,
                            "(certificate metadata changed during validation|certificate namespace changed while retained)",
                        ):
                            if certificate_only:
                                completion.validate_certificate_only(output, **common)
                            else:
                                completion.validate_certificate(
                                    output, root / "input.json", **common
                                )
                finally:
                    completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = original_prefix, original_data_root
                self.assertTrue(swapped)

    def test_source_and_operational_evidence_reject_fd_attestation_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            declaration, _analysis = self._declaration(root)
            original_prefix, original_data_root = completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT
            completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = root, root
            try:
                cases = [
                    (
                        Path(declaration["source_packet"]["path"]),
                        lambda attestor: completion._verify_source_packet(
                            declaration["source_packet"], storage_attestor=attestor
                        ),
                    ),
                    (
                        Path(declaration["operational_preflight"]["report"]),
                        lambda attestor: completion._verify_operational(
                            declaration["operational_preflight"],
                            storage_attestor=attestor,
                        ),
                    ),
                ]
                for index, (path, verifier) in enumerate(cases):
                    with self.subTest(path=path):
                        replacement = root / f"replacement-evidence-{index}.json"
                        replacement.write_bytes(path.read_bytes())
                        replacement.chmod(0o444)
                        replaced = False

                        def replace_during_attestation(_fd_path: Path) -> dict[str, str]:
                            nonlocal replaced
                            if not replaced:
                                replacement.replace(path)
                                replaced = True
                            return dict(self.STORAGE)

                        with self.assertRaisesRegex(
                            RuntimeError,
                            "(metadata changed during FD attestation|namespace changed while retained)",
                        ):
                            verifier(replace_during_attestation)
                        self.assertTrue(replaced)
            finally:
                completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = original_prefix, original_data_root

    def test_fixture_reanalysis_rejects_member_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            declaration, analysis = self._declaration(root)
            fixture_root = Path(declaration["fixture"]["root"])
            victim = fixture_root / "route_rows.uint16.le.bin"
            replacement = root / "replacement-route-rows.bin"
            replacement.write_bytes(victim.read_bytes())
            replacement.chmod(0o444)
            replaced = False

            def replace_during_reanalysis(_path: Path) -> dict[str, Any]:
                nonlocal replaced
                replacement.replace(victim)
                replaced = True
                return analysis

            original_prefix, original_data_root = completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT
            completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = root, root
            try:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "(fixture root changed during validation|fixture member metadata changed during validation|fixture member route_rows.uint16.le.bin namespace changed while retained)",
                ):
                    completion._verify_fixture(
                        declaration["fixture"],
                        fixture_analyzer=replace_during_reanalysis,
                        storage_attestor=lambda _path: dict(self.STORAGE),
                    )
            finally:
                completion.ROOT_PREFIX, completion.TRACKED_DATA_ROOT = original_prefix, original_data_root
            self.assertTrue(replaced)

    def test_tool_binding_reader_rejects_replacement_during_commit_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "tool.py"
            raw = b"VALUE = 1\n"
            path.write_bytes(raw)
            replacement = root / "replacement.py"
            replacement.write_bytes(raw)

            def replace_during_commit(_commit: str, _relative: str) -> bytes:
                replacement.replace(path)
                return raw

            with self.assertRaisesRegex(
                RuntimeError,
                "(live tool metadata changed|live tool namespace changed while retained)",
            ):
                completion._anchored_live_committed_bytes(
                    path,
                    "tool.py",
                    digest(raw),
                    "d" * 40,
                    replace_during_commit,
                    "tool",
                )

    def test_pinned_python_stderr_and_same_fd_metadata_fail_closed(self) -> None:
        with mock.patch.object(completion, "PYTHON_EXECUTABLE_SHA256", "0" * 64), \
             mock.patch.object(completion.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "Python executable identity drift"):
                completion._validate_bundle_subprocess(tools=self._verified_tools())
            run.assert_not_called()
        emitted = json.dumps(self._bundle(), sort_keys=True) + "\n"
        with mock.patch.object(
            completion.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=emitted, stderr="unexpected stderr\n"
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "validation subprocess failed"):
                completion._validate_bundle_subprocess(tools=self._verified_tools())
        with mock.patch.object(
            completion.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd="python", timeout=30),
        ):
            with self.assertRaisesRegex(RuntimeError, "validation subprocess timed out"):
                completion._validate_bundle_subprocess(tools=self._verified_tools())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stable.txt"
            path.write_bytes(b"stable")
            actual = path.stat()
            before = mock.Mock()
            after = mock.Mock()
            for field in completion.STABLE_STAT_FIELDS:
                setattr(before, field, getattr(actual, field))
                setattr(after, field, getattr(actual, field))
            after.st_mtime_ns += 1
            with mock.patch.object(completion.os, "fstat", side_effect=[before, after]):
                with self.assertRaisesRegex(RuntimeError, "same-FD metadata changed"):
                    completion._regular_bytes(path)

    def test_module_has_no_accelerator_imports(self) -> None:
        forbidden_local = {
            "prepare_laguna_m8_gather_sharded_fixtures",
            "preflight_laguna_m8_gather_sharded_operational",
            "freeze_laguna_m8_gather_sharded_binary_bundle",
        }
        tree = ast.parse(Path(completion.__file__).read_text())
        imports = [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        imports.extend(node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module)
        blocked = {"torch", "vllm", "vllm_xpu_kernels", "intel_extension_for_pytorch", "unitrace"}
        self.assertFalse(any(name.split(".")[0] in blocked for name in imports))
        self.assertTrue(forbidden_local.isdisjoint(set(imports)))
        real_import = __import__

        def reject_mutable_helpers(name: str, *args: Any, **kwargs: Any) -> Any:
            if name.split(".", 1)[0] in forbidden_local:
                self.fail(f"mutable helper executed during import: {name}")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=reject_mutable_helpers):
            runpy.run_path(str(completion.__file__), run_name="stage0_import_probe")


if __name__ == "__main__":
    unittest.main()
