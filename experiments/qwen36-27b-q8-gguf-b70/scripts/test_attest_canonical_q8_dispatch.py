#!/usr/bin/env python3
"""Offline tests for canonical Q8 c2 dispatch-log attestation."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("attest-canonical-q8-dispatch.py")
SPEC = importlib.util.spec_from_file_location("attest_canonical_q8_dispatch", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"could not load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


MANIFEST_PATH = "/evidence/runtime-manifest.json"
REFERENCE_REPORT_PATH = "/evidence/runtime-reference.json"
FINAL_REPORT_PATH = "/evidence/runtime-final.json"
SERVER_PATH = "/runtime/canonical-hybrid/llama-server"
SERVER_SHA256 = "1" * 64
SERVER_PID = "111"
SERVER_LOG_PATH = "/evidence/server.log"


def runtime_fixture(
    manifest_path: str = MANIFEST_PATH,
    reference_report_path: str = REFERENCE_REPORT_PATH,
    final_report_path: str = FINAL_REPORT_PATH,
) -> dict:
    origin = str(Path(SERVER_PATH).parent)
    origin_objects = [
        {
            "soname": "libalpha.so.1",
            "loader_path": "$ORIGIN/libalpha.so.1",
            "resolved_path": "$ORIGIN/libalpha.so.1.2.3",
            "size_bytes": 101,
            "sha256": "a" * 64,
        },
        {
            "soname": "libbeta.so.2",
            "loader_path": "$ORIGIN/libbeta.so.2",
            "resolved_path": "$ORIGIN/libbeta.so.2.3.4",
            "size_bytes": 202,
            "sha256": "b" * 64,
        },
    ]
    manifest = {
        "runtime_bundle_schema_version": 1,
        "runtime_loader_policy": {
            "mode": "origin-first",
            "variable": "LD_LIBRARY_PATH",
        },
        "llama_server_path": SERVER_PATH,
        "llama_server_sha256": SERVER_SHA256,
        "origin_shared_objects": origin_objects,
        "experimental_controls": {
            MODULE.CONTROL: {
                "supported": True,
                "default": "0",
                "values": ["0", "1"],
            }
        },
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
    manifest_sha256 = MODULE.sha256_bytes(manifest_bytes)
    dependencies = [
        {
            "soname": "libalpha.so.1",
            "loader_path": f"{origin}/libalpha.so.1",
            "resolved_path": f"{origin}/libalpha.so.1.2.3",
            "size_bytes": 101,
            "sha256": "a" * 64,
        },
        {
            "soname": "libbeta.so.2",
            "loader_path": f"{origin}/libbeta.so.2",
            "resolved_path": f"{origin}/libbeta.so.2.3.4",
            "size_bytes": 202,
            "sha256": "b" * 64,
        },
        {
            "soname": "libc.so.6",
            "loader_path": "/usr/lib/libc.so.6",
            "resolved_path": "/usr/lib/libc.so.6",
            "size_bytes": 303,
            "sha256": "c" * 64,
        },
    ]
    reference_report = {
        "passed": True,
        "runtime_bundle_schema_version": 1,
        "runtime_manifest": manifest_path,
        "runtime_manifest_sha256": manifest_sha256,
        "binary": {
            "loader_path": SERVER_PATH,
            "resolved_path": SERVER_PATH,
            "size_bytes": 404,
            "sha256": SERVER_SHA256,
        },
        "loader_policy": {
            "mode": "origin-first",
            "variable": "LD_LIBRARY_PATH",
            "binary_origin": origin,
            "ld_library_path_first": origin,
            "origin_precedence_attested": True,
        },
        "dependency_count": len(dependencies),
        "origin_shared_object_count": len(origin_objects),
        "origin_shared_object_sonames": sorted(
            item["soname"] for item in origin_objects
        ),
        "dependencies": dependencies,
    }
    final_report = copy.deepcopy(reference_report)
    final_report["reference_report"] = reference_report_path
    final_report["reference_match"] = True
    return {
        "manifest_path": manifest_path,
        "reference_report_path": reference_report_path,
        "final_report_path": final_report_path,
        "manifest": manifest,
        "reference_report": reference_report,
        "final_report": final_report,
    }


def encode_json(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True).encode()


def identity_for(
    runtime: dict,
    manifest_bytes: bytes,
    server_pid: str = SERVER_PID,
    server_output_log: str = SERVER_LOG_PATH,
) -> str:
    manifest = runtime["manifest"]
    server_path = manifest["llama_server_path"]
    lines = (
        "GGML_SYCL_ENABLE_GRAPH=0",
        "GGML_SYCL_ENABLE_OPT=1",
        "GGML_SYCL_PRIORITIZE_DMMV=0",
        "GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ=1",
        f"server_pid={server_pid}",
        f"server_output_log={server_output_log}",
        "runtime_bundle_verified=1",
        f"runtime_manifest={runtime['manifest_path']}",
        f"runtime_manifest_sha256={MODULE.sha256_bytes(manifest_bytes)}",
        f"llama_server={server_path}",
        f"llama_server_sha256={manifest['llama_server_sha256']}",
        "runtime_loader_policy=origin-first",
        f"runtime_loader_origin={Path(server_path).parent}",
        "runtime_loader_origin_precedence=1",
        "--- server ---",
    )
    return "\n".join(lines) + "\n"


DEFAULT_RUNTIME = runtime_fixture()
DEFAULT_MANIFEST_BYTES = encode_json(DEFAULT_RUNTIME["manifest"])
IDENTITY = identity_for(DEFAULT_RUNTIME, DEFAULT_MANIFEST_BYTES)
STARTUP = "  GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ: 1"
BINDING = f"QWEN36_SERVER_PROCESS_BINDING pid={SERVER_PID}"
FLAT = (
    "SYCL_Q8_0_C2_CANONICAL_MMVQ first-hit: layout=flat "
    "path=reordered_single_col_mmvq reorder_ready=1 calls_per_dispatch=2 "
    "src0=blk.0.weight src0_ne=[6144,5120,1,1] "
    "src1_ne=[6144,2,1,1] dst_ne=[5120,2,1,1]"
)
RECURRENT = (
    "SYCL_Q8_0_C2_CANONICAL_MMVQ first-hit: layout=recurrent "
    "path=reordered_single_col_mmvq reorder_ready=1 calls_per_dispatch=2 "
    "src0=blk.1.weight src0_ne=[6144,5120,1,1] "
    "src1_ne=[6144,1,2,1] dst_ne=[5120,1,2,1]"
)


def summary(**changes: int) -> str:
    values = {
        "flat_dispatches": 41,
        "recurrent_dispatches": 59,
        "flat_multicol_suppressed": 41,
        "recurrent_dmmv_suppressed": 59,
        "reorder_ready_dispatches": 100,
        "single_col_mmvq_calls": 200,
        "violations": 0,
    }
    values.update(changes)
    return "SYCL_Q8_0_C2_CANONICAL_MMVQ summary: " + " ".join(
        f"{name}={values[name]}" for name in MODULE.SUMMARY_FIELDS
    )


def common_log(message: str, sequence: int, level: str = "I") -> str:
    return f"0.12.{sequence:03d}.678 {level} {message}"


def log_text(
    *,
    binding: str = BINDING,
    startup: str | None = None,
    flat: str = FLAT,
    recurrent: str = RECURRENT,
    final: str | None = None,
    extra: tuple[str, ...] = (),
    prefixed: bool = True,
) -> str:
    messages = [message for message in (startup, flat, recurrent, *extra) if message]
    if final is None:
        messages.append(summary())
    elif final:
        messages.append(final)
    if prefixed:
        runtime_rows = [
            common_log(message, index + 1) for index, message in enumerate(messages)
        ]
    else:
        runtime_rows = messages
    rows = ([binding] if binding else []) + runtime_rows
    return "unrelated preface\n" + "\n".join(rows) + "\nunrelated epilogue\n"


class DispatchAttestationTests(unittest.TestCase):
    def attest(
        self,
        text: str,
        identity: str | None = None,
        runtime: dict | None = None,
        expected_hashes: dict[str, str] | None = None,
        raw_inputs: dict[str, bytes] | None = None,
        server_pid: str = SERVER_PID,
        log_path: str = SERVER_LOG_PATH,
    ) -> dict:
        runtime = copy.deepcopy(DEFAULT_RUNTIME if runtime is None else runtime)
        raw_inputs = {} if raw_inputs is None else raw_inputs
        manifest_bytes = raw_inputs.get("manifest", encode_json(runtime["manifest"]))
        reference_bytes = raw_inputs.get(
            "reference_report", encode_json(runtime["reference_report"])
        )
        final_bytes = raw_inputs.get(
            "final_report", encode_json(runtime["final_report"])
        )
        if identity is None:
            identity = identity_for(
                runtime,
                encode_json(runtime["manifest"]),
                server_pid,
                log_path,
            )
        expected = {
            "manifest": MODULE.sha256_bytes(manifest_bytes),
            "reference_report": MODULE.sha256_bytes(reference_bytes),
            "final_report": MODULE.sha256_bytes(final_bytes),
        }
        if expected_hashes is not None:
            expected.update(expected_hashes)
        return MODULE.build_attestation(
            text.encode(),
            identity.encode(),
            server_pid,
            manifest_bytes,
            expected["manifest"],
            reference_bytes,
            expected["reference_report"],
            final_bytes,
            expected["final_report"],
            log_path=log_path,
            identity_path="/evidence/identity.log",
            runtime_manifest_path=runtime["manifest_path"],
            runtime_reference_report_path=runtime["reference_report_path"],
            runtime_final_report_path=runtime["final_report_path"],
        )

    def test_real_common_log_prefix_and_absent_runtime_startup_pass(self) -> None:
        result = self.attest(log_text())
        self.assertTrue(result["passed"])
        self.assertTrue(all(result["fields"].values()))
        self.assertEqual(
            [row["layout"] for row in result["observed"]["first_hits"]],
            ["flat", "recurrent"],
        )
        self.assertEqual(result["observed"]["runtime_startup_candidate_count"], 0)

    def test_exact_optional_runtime_startup_and_unprefixed_markers_pass(self) -> None:
        result = self.attest(log_text(startup=STARTUP, prefixed=False))
        self.assertTrue(result["passed"])
        self.assertEqual(result["observed"]["runtime_startup_exact_count"], 1)

    def test_launcher_identity_is_mandatory_and_exact(self) -> None:
        for label, identity in (
            ("missing-selector", IDENTITY.replace(f"{MODULE.CONTROL}=1\n", "")),
            (
                "disabled-selector",
                IDENTITY.replace(f"{MODULE.CONTROL}=1", f"{MODULE.CONTROL}=0"),
            ),
            (
                "wrong-opt",
                IDENTITY.replace("GGML_SYCL_ENABLE_OPT=1", "GGML_SYCL_ENABLE_OPT=0"),
            ),
            (
                "wrong-graph",
                IDENTITY.replace(
                    "GGML_SYCL_ENABLE_GRAPH=0", "GGML_SYCL_ENABLE_GRAPH=1"
                ),
            ),
            (
                "wrong-priority",
                IDENTITY.replace(
                    "GGML_SYCL_PRIORITIZE_DMMV=0", "GGML_SYCL_PRIORITIZE_DMMV=1"
                ),
            ),
            (
                "duplicate-selector",
                IDENTITY.replace(
                    "--- server ---", f"{MODULE.CONTROL}=1\n--- server ---"
                ),
            ),
        ):
            with self.subTest(label=label):
                self.assertFalse(self.attest(log_text(), identity)["passed"])

    def test_identity_delimiter_is_required_exactly_once(self) -> None:
        for label, identity in (
            ("missing", IDENTITY.replace("--- server ---\n", "")),
            ("duplicate", IDENTITY + "--- server ---\n"),
            ("not-exact", IDENTITY.replace("--- server ---", " --- server ---")),
        ):
            with self.subTest(label=label):
                result = self.attest(log_text(), identity)
                self.assertFalse(result["passed"])
                self.assertFalse(result["fields"]["identity_delimiter_exactly_once"])

    def test_valid_separate_identity_and_stdout_process_binding_passes(self) -> None:
        result = self.attest(log_text())
        self.assertTrue(result["passed"])
        binding = result["observed"]["server_process_binding"]
        self.assertEqual(binding["expected_pid"], SERVER_PID)
        self.assertEqual(binding["identity_pids"], [SERVER_PID])
        self.assertEqual(binding["stdout_sentinel_pids"], [SERVER_PID])
        self.assertEqual(
            binding["server_output_log_observed_resolved"], SERVER_LOG_PATH
        )
        self.assertNotEqual(
            result["input"]["identity_log"]["path"],
            result["input"]["server_log"]["path"],
        )

    def test_server_pid_argument_must_be_positive_decimal(self) -> None:
        for server_pid in ("", "0", "01", "+1", "-1", "1x"):
            with self.subTest(server_pid=server_pid):
                result = self.attest(log_text(), server_pid=server_pid)
                self.assertFalse(result["passed"])
                self.assertFalse(
                    result["fields"]["server_pid_argument_positive_decimal"]
                )

    def test_identity_server_pid_is_required_exactly_once_and_matches_runner(
        self,
    ) -> None:
        for label, identity in (
            ("missing", IDENTITY.replace(f"server_pid={SERVER_PID}\n", "")),
            (
                "malformed",
                IDENTITY.replace(f"server_pid={SERVER_PID}", "server_pid=+111"),
            ),
            (
                "wrong",
                IDENTITY.replace(f"server_pid={SERVER_PID}", "server_pid=222"),
            ),
            (
                "duplicate",
                IDENTITY.replace(
                    "--- server ---", f"server_pid={SERVER_PID}\n--- server ---"
                ),
            ),
        ):
            with self.subTest(label=label):
                result = self.attest(log_text(), identity)
                self.assertFalse(result["passed"])
                self.assertFalse(result["fields"]["server_pid_identity_exactly_once"])

    def test_stdout_pid_sentinel_is_required_unprefixed_exactly_once(self) -> None:
        for label, binding in (
            ("missing", ""),
            ("zero", "QWEN36_SERVER_PROCESS_BINDING pid=0"),
            ("signed", "QWEN36_SERVER_PROCESS_BINDING pid=+111"),
            ("suffix", "QWEN36_SERVER_PROCESS_BINDING pid=111x"),
            ("common-prefix", common_log(BINDING, 0)),
            ("duplicate", f"{BINDING}\n{BINDING}"),
        ):
            with self.subTest(label=label):
                result = self.attest(log_text(binding=binding))
                self.assertFalse(result["passed"])
                self.assertFalse(
                    result["fields"]["server_process_binding_sentinel_exactly_once"]
                )

    def test_mixed_runner_identity_and_stdout_pids_cannot_false_pass(self) -> None:
        result = self.attest(log_text(binding="QWEN36_SERVER_PROCESS_BINDING pid=222"))
        self.assertFalse(result["passed"])
        self.assertTrue(
            result["fields"]["server_process_binding_sentinel_exactly_once"]
        )
        self.assertFalse(result["fields"]["server_process_binding_all_pids_equal"])
        self.assertTrue(result["fields"]["runtime_report_signature_exact"])
        self.assertTrue(result["fields"]["summary_marker_well_formed"])

    def test_identity_server_output_log_is_absolute_unique_and_resolved(self) -> None:
        exact = f"server_output_log={SERVER_LOG_PATH}"
        for label, identity in (
            ("missing", IDENTITY.replace(f"{exact}\n", "")),
            ("relative", IDENTITY.replace(exact, "server_output_log=server.log")),
            (
                "nul",
                IDENTITY.replace(exact, "server_output_log=/evidence/\x00server.log"),
            ),
            (
                "wrong",
                IDENTITY.replace(exact, "server_output_log=/evidence/wrong.log"),
            ),
            (
                "duplicate",
                IDENTITY.replace("--- server ---", f"{exact}\n--- server ---"),
            ),
        ):
            with self.subTest(label=label):
                result = self.attest(log_text(), identity)
                self.assertFalse(result["passed"])
                self.assertFalse(
                    result["fields"][
                        "server_output_log_identity_exactly_once_and_resolved"
                    ]
                )

    def test_stdout_sentinel_must_precede_startup_hits_and_summary(self) -> None:
        valid = "\n".join(
            (
                BINDING,
                common_log(STARTUP, 1),
                common_log(FLAT, 2),
                common_log(RECURRENT, 3),
                common_log(summary(), 4),
            )
        )
        self.assertTrue(self.attest(valid)["passed"])
        for label, text in (
            (
                "after-startup",
                "\n".join(
                    (
                        common_log(STARTUP, 1),
                        BINDING,
                        common_log(FLAT, 2),
                        common_log(RECURRENT, 3),
                        common_log(summary(), 4),
                    )
                ),
            ),
            (
                "after-first-hit",
                "\n".join(
                    (
                        common_log(FLAT, 1),
                        BINDING,
                        common_log(RECURRENT, 2),
                        common_log(summary(), 3),
                    )
                ),
            ),
            (
                "after-summary",
                "\n".join(
                    (
                        common_log(FLAT, 1),
                        common_log(RECURRENT, 2),
                        common_log(summary(), 3),
                        BINDING,
                    )
                ),
            ),
        ):
            with self.subTest(label=label):
                result = self.attest(text)
                self.assertFalse(result["passed"])
                self.assertFalse(result["fields"]["server_process_binding_order_valid"])

    def test_every_runtime_identity_header_is_exactly_once(self) -> None:
        runtime_lines = (
            "runtime_bundle_verified=1",
            f"runtime_manifest={MANIFEST_PATH}",
            f"runtime_manifest_sha256={MODULE.sha256_bytes(DEFAULT_MANIFEST_BYTES)}",
            f"llama_server={SERVER_PATH}",
            f"llama_server_sha256={SERVER_SHA256}",
            "runtime_loader_policy=origin-first",
            f"runtime_loader_origin={Path(SERVER_PATH).parent}",
            "runtime_loader_origin_precedence=1",
        )
        for line in runtime_lines:
            name = line.split("=", 1)[0]
            for mutation, identity in (
                ("missing", IDENTITY.replace(f"{line}\n", "")),
                ("wrong", IDENTITY.replace(line, f"{name}=wrong")),
                (
                    "duplicate",
                    IDENTITY.replace("--- server ---", f"{line}\n--- server ---"),
                ),
            ):
                with self.subTest(name=name, mutation=mutation):
                    self.assertFalse(self.attest(log_text(), identity)["passed"])

    def test_all_runtime_inputs_are_bound_to_explicit_sha256(self) -> None:
        field_names = {
            "manifest": "runtime_manifest_sha256_matches_expected",
            "reference_report": "runtime_reference_report_sha256_matches_expected",
            "final_report": "runtime_final_report_sha256_matches_expected",
        }
        for name, field in field_names.items():
            for expected in ("0" * 64, "malformed"):
                with self.subTest(name=name, expected=expected):
                    result = self.attest(log_text(), expected_hashes={name: expected})
                    self.assertFalse(result["passed"])
                    self.assertFalse(result["fields"][field])

    def test_reference_to_final_signature_is_exact(self) -> None:
        mutations = {
            "runtime_bundle_schema_version": lambda report: report.__setitem__(
                "runtime_bundle_schema_version", 2
            ),
            "runtime_manifest_sha256": lambda report: report.__setitem__(
                "runtime_manifest_sha256", "0" * 64
            ),
            "binary": lambda report: report["binary"].__setitem__("size_bytes", 405),
            "loader_policy": lambda report: report["loader_policy"].__setitem__(
                "ld_library_path_first", "/wrong"
            ),
            "dependency_count": lambda report: report.__setitem__(
                "dependency_count", 4
            ),
            "origin_shared_object_count": lambda report: report.__setitem__(
                "origin_shared_object_count", 3
            ),
            "origin_shared_object_sonames": lambda report: report.__setitem__(
                "origin_shared_object_sonames",
                list(reversed(report["origin_shared_object_sonames"])),
            ),
            "dependencies": lambda report: report["dependencies"][-1].__setitem__(
                "sha256", "d" * 64
            ),
        }
        for field, mutate in mutations.items():
            with self.subTest(field=field):
                runtime = runtime_fixture()
                mutate(runtime["final_report"])
                result = self.attest(log_text(), runtime=runtime)
                self.assertFalse(result["passed"])
                self.assertFalse(result["fields"]["runtime_report_signature_exact"])

    def test_report_origin_objects_must_match_manifest_even_when_reports_match(
        self,
    ) -> None:
        runtime = runtime_fixture()
        for report_name in ("reference_report", "final_report"):
            runtime[report_name]["dependencies"][0]["sha256"] = "d" * 64
        result = self.attest(log_text(), runtime=runtime)
        self.assertFalse(result["passed"])
        self.assertTrue(result["fields"]["runtime_report_signature_exact"])
        self.assertFalse(result["fields"]["runtime_reference_report_valid"])
        self.assertFalse(result["fields"]["runtime_final_report_valid"])

    def test_each_runtime_report_identity_gate_is_required(self) -> None:
        mutations = {
            "passed": lambda report: report.__setitem__("passed", False),
            "manifest-path": lambda report: report.__setitem__(
                "runtime_manifest", "/wrong/manifest.json"
            ),
            "manifest-sha": lambda report: report.__setitem__(
                "runtime_manifest_sha256", "0" * 64
            ),
            "binary": lambda report: report["binary"].__setitem__("sha256", "0" * 64),
            "policy": lambda report: report["loader_policy"].__setitem__(
                "origin_precedence_attested", False
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                runtime = runtime_fixture()
                mutate(runtime["reference_report"])
                mutate(runtime["final_report"])
                result = self.attest(log_text(), runtime=runtime)
                self.assertFalse(result["passed"])
                self.assertTrue(result["fields"]["runtime_report_signature_exact"])
                self.assertFalse(result["fields"]["runtime_reference_report_valid"])
                self.assertFalse(result["fields"]["runtime_final_report_valid"])

    def test_final_report_must_name_reference_and_attest_match(self) -> None:
        for label, changes in (
            ("wrong-path", {"reference_report": "/wrong/reference.json"}),
            ("missing-path", {"reference_report": None}),
            ("match-false", {"reference_match": False}),
            ("match-nonboolean", {"reference_match": 1}),
        ):
            with self.subTest(label=label):
                runtime = runtime_fixture()
                runtime["final_report"].update(changes)
                result = self.attest(log_text(), runtime=runtime)
                self.assertFalse(result["passed"])

    def test_runtime_manifest_candidate_contract_is_required(self) -> None:
        for label, mutate in (
            (
                "control",
                lambda manifest: manifest["experimental_controls"].clear(),
            ),
            (
                "policy",
                lambda manifest: manifest["runtime_loader_policy"].__setitem__(
                    "mode", "runpath-default"
                ),
            ),
            (
                "origin",
                lambda manifest: manifest["origin_shared_objects"][0].__setitem__(
                    "sha256", "malformed"
                ),
            ),
        ):
            with self.subTest(label=label):
                runtime = runtime_fixture()
                mutate(runtime["manifest"])
                result = self.attest(log_text(), runtime=runtime)
                self.assertFalse(result["passed"])
                self.assertFalse(result["fields"]["runtime_manifest_contract_valid"])

    def test_malformed_runtime_json_is_retained_as_failed_evidence(self) -> None:
        expected_fields = {
            "manifest": "runtime_manifest_contract_valid",
            "reference_report": "runtime_reference_report_valid",
            "final_report": "runtime_final_report_valid",
        }
        for name, field in expected_fields.items():
            with self.subTest(name=name):
                result = self.attest(log_text(), raw_inputs={name: b'{"truncated":'})
                self.assertFalse(result["passed"])
                self.assertFalse(result["fields"][field])

    def test_malformed_runtime_startup_fails_when_present(self) -> None:
        for value in ("0", "2", "1x"):
            with self.subTest(value=value):
                result = self.attest(
                    log_text(startup=f"  GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ: {value}")
                )
                self.assertFalse(result["passed"])
                self.assertFalse(
                    result["fields"]["runtime_startup_marker_if_present_well_formed"]
                )

    def test_missing_duplicate_or_malformed_first_hit_fails(self) -> None:
        candidates = {
            "missing-flat": log_text(flat=""),
            "missing-recurrent": log_text(recurrent=""),
            "duplicate-flat": log_text(extra=(FLAT,)),
            "wrong-path": log_text(
                flat=FLAT.replace(
                    "path=reordered_single_col_mmvq",
                    "path=reordered_multi_col_mmvq",
                )
            ),
            "wrong-call-count": log_text(
                recurrent=RECURRENT.replace(
                    "calls_per_dispatch=2", "calls_per_dispatch=1"
                )
            ),
        }
        for label, text in candidates.items():
            with self.subTest(label=label):
                result = self.attest(text)
                self.assertFalse(result["passed"])
                self.assertFalse(result["fields"]["first_hit_markers_well_formed"])

    def test_first_hit_shape_contract_is_checked(self) -> None:
        result = self.attest(
            log_text(flat=FLAT.replace("src1_ne=[6144,2,1,1]", "src1_ne=[6144,1,2,1]"))
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["fields"]["flat_first_hit_shape_valid"])
        self.assertTrue(result["fields"]["first_hit_markers_well_formed"])

    def test_every_summary_invariant_is_mandatory(self) -> None:
        mutations = {
            "flat-positive": {
                "flat_dispatches": 0,
                "flat_multicol_suppressed": 0,
                "reorder_ready_dispatches": 59,
                "single_col_mmvq_calls": 118,
            },
            "recurrent-positive": {
                "recurrent_dispatches": 0,
                "recurrent_dmmv_suppressed": 0,
                "reorder_ready_dispatches": 41,
                "single_col_mmvq_calls": 82,
            },
            "flat-suppression": {"flat_multicol_suppressed": 40},
            "recurrent-suppression": {"recurrent_dmmv_suppressed": 58},
            "reorder-ready": {"reorder_ready_dispatches": 99},
            "single-column-calls": {"single_col_mmvq_calls": 199},
            "summary-violation": {"violations": 1},
        }
        for label, changes in mutations.items():
            with self.subTest(label=label):
                self.assertFalse(
                    self.attest(log_text(final=summary(**changes)))["passed"]
                )

    def test_missing_malformed_or_duplicate_summary_fails(self) -> None:
        for label, text in (
            ("missing", log_text(final="")),
            (
                "malformed",
                log_text(
                    final=summary().replace("flat_dispatches=41", "flat_dispatches=-1")
                ),
            ),
            ("duplicate", log_text(extra=(summary(),))),
        ):
            with self.subTest(label=label):
                result = self.attest(text)
                self.assertFalse(result["passed"])
                self.assertFalse(result["fields"]["summary_marker_well_formed"])

    def test_fatal_violation_with_common_error_prefix_fails(self) -> None:
        violation = common_log(
            "SYCL_Q8_0_C2_CANONICAL_MMVQ violation: selected src0 is not contiguous",
            4,
            "E",
        )
        result = self.attest(log_text(extra=(violation,), prefixed=False))
        self.assertFalse(result["passed"])
        self.assertFalse(result["fields"]["no_violation_markers"])

    def test_summary_before_first_hits_fails_order_gate(self) -> None:
        text = "\n".join(
            (
                BINDING,
                common_log(summary(), 1),
                common_log(FLAT, 2),
                common_log(RECURRENT, 3),
            )
        )
        result = self.attest(text)
        self.assertFalse(result["passed"])
        self.assertFalse(result["fields"]["runtime_marker_order_valid"])

    def test_cli_retains_failed_attestation_and_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server_log = root / "server.log"
            identity_log = root / "identity.log"
            manifest_path = root / "runtime-manifest.json"
            reference_report_path = root / "runtime-reference.json"
            final_report_path = root / "runtime-final.json"
            output = root / "attestation.json"
            runtime = runtime_fixture(
                str(manifest_path),
                str(reference_report_path),
                str(final_report_path),
            )
            manifest_bytes = encode_json(runtime["manifest"])
            reference_bytes = encode_json(runtime["reference_report"])
            final_bytes = encode_json(runtime["final_report"])
            server_log.write_text(log_text(recurrent=""))
            identity_log.write_text(
                identity_for(runtime, manifest_bytes, SERVER_PID, str(server_log))
            )
            manifest_path.write_bytes(manifest_bytes)
            reference_report_path.write_bytes(reference_bytes)
            final_report_path.write_bytes(final_bytes)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--server-log",
                    str(server_log),
                    "--identity-log",
                    str(identity_log),
                    "--server-pid",
                    SERVER_PID,
                    "--runtime-manifest",
                    str(manifest_path),
                    "--runtime-manifest-sha256",
                    MODULE.sha256_bytes(manifest_bytes),
                    "--runtime-reference-report",
                    str(reference_report_path),
                    "--runtime-reference-report-sha256",
                    MODULE.sha256_bytes(reference_bytes),
                    "--runtime-final-report",
                    str(final_report_path),
                    "--runtime-final-report-sha256",
                    MODULE.sha256_bytes(final_bytes),
                    "--out",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 1)
            retained = json.loads(output.read_text())
            self.assertFalse(retained["passed"])
            self.assertEqual(
                retained["input"]["server_log"]["path"],
                str(server_log.resolve()),
            )
            self.assertEqual(
                retained["input"]["runtime_manifest"],
                {
                    "path": str(manifest_path),
                    "size_bytes": len(manifest_bytes),
                    "expected_sha256": MODULE.sha256_bytes(manifest_bytes),
                    "sha256": MODULE.sha256_bytes(manifest_bytes),
                },
            )
            for name, path, contents in (
                ("runtime_reference_report", reference_report_path, reference_bytes),
                ("runtime_final_report", final_report_path, final_bytes),
            ):
                with self.subTest(name=name):
                    self.assertEqual(retained["input"][name]["path"], str(path))
                    self.assertEqual(
                        retained["input"][name]["expected_sha256"],
                        MODULE.sha256_bytes(contents),
                    )
                    self.assertEqual(
                        retained["input"][name]["sha256"],
                        MODULE.sha256_bytes(contents),
                    )

    def test_atomic_publish_never_overwrites_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "attestation.json"
            output.write_text("sentinel\n")
            with self.assertRaises(SystemExit):
                MODULE.write_json_exclusive(output, {"passed": True})
            self.assertEqual(output.read_text(), "sentinel\n")


if __name__ == "__main__":
    unittest.main()
