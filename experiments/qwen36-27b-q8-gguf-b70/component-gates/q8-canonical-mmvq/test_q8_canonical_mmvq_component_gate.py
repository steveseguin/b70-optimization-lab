#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import os
import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("run-q8-canonical-mmvq-component-gate.py")
SPEC = importlib.util.spec_from_file_location("q8_component_gate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def valid_route_log(*, startup: bool = True) -> str:
    lines = []
    if startup:
        lines.append("2026-08-09T00:00:00Z I   GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ: 1")
    lines.extend(
        [
            "prefix SYCL_Q8_0_C2_CANONICAL_MMVQ first-hit: "
            "layout=flat path=reordered_single_col_mmvq reorder_ready=1 calls_per_dispatch=2 "
            "src0=qwen36-q8-control-weight-6144x5120 src0_ne=[6144,5120,1,1] "
            "src1_ne=[6144,2,1,1] dst_ne=[5120,2,1,1]",
            "prefix SYCL_Q8_0_C2_CANONICAL_MMVQ first-hit: "
            "layout=recurrent path=reordered_single_col_mmvq reorder_ready=1 calls_per_dispatch=2 "
            "src0=qwen36-q8-control-weight-6144x5120 src0_ne=[6144,5120,1,1] "
            "src1_ne=[6144,1,2,1] dst_ne=[5120,1,2,1]",
            "prefix SYCL_Q8_0_C2_CANONICAL_MMVQ summary: "
            "flat_dispatches=1 recurrent_dispatches=1 flat_multicol_suppressed=1 "
            "recurrent_dmmv_suppressed=1 reorder_ready_dispatches=2 "
            "single_col_mmvq_calls=4 violations=0",
        ]
    )
    return "\n".join(lines)


class RouteParserTests(unittest.TestCase):
    def test_accepts_prefixed_markers(self) -> None:
        result = gate.parse_route_log(valid_route_log())
        self.assertTrue(result["startup_echo_observed"])
        self.assertEqual(result["summary"], gate.EXPECTED_ROUTES)
        self.assertEqual(set(result["first_hits"]), {"flat", "recurrent"})

    def test_startup_echo_is_optional(self) -> None:
        result = gate.parse_route_log(valid_route_log(startup=False))
        self.assertFalse(result["startup_echo_observed"])

    def test_rejects_disabled_startup_echo(self) -> None:
        with self.assertRaisesRegex(gate.GateError, "disagrees"):
            gate.parse_route_log(valid_route_log().replace("MMVQ: 1", "MMVQ: 0"))

    def test_rejects_malformed_visible_startup_echo(self) -> None:
        text = valid_route_log().replace("MMVQ: 1", "MMVQ: enabled")
        with self.assertRaisesRegex(gate.GateError, "malformed selector"):
            gate.parse_route_log(text)

    def test_rejects_violation_marker(self) -> None:
        with self.assertRaisesRegex(gate.GateError, "violation"):
            gate.parse_route_log(valid_route_log() + "\nprefix SYCL_Q8_0_C2_CANONICAL_MMVQ violation: reason=test")

    def test_rejects_missing_layout_hit(self) -> None:
        text = "\n".join(line for line in valid_route_log().splitlines() if "layout=recurrent" not in line)
        with self.assertRaisesRegex(gate.GateError, "missing per-layout"):
            gate.parse_route_log(text)

    def test_rejects_counter_mismatch(self) -> None:
        text = valid_route_log().replace("single_col_mmvq_calls=4", "single_col_mmvq_calls=3")
        with self.assertRaisesRegex(gate.GateError, "counter mismatch"):
            gate.parse_route_log(text)

    def test_rejects_duplicate_summary_field(self) -> None:
        text = valid_route_log().replace(
            "flat_dispatches=1 recurrent_dispatches=1",
            "flat_dispatches=1 flat_dispatches=1 recurrent_dispatches=1",
        )
        with self.assertRaisesRegex(gate.GateError, "duplicate field"):
            gate.parse_route_log(text)

    def test_rejects_noncanonical_first_hit_dimensions(self) -> None:
        text = valid_route_log().replace("src1_ne=[6144,2,1,1]", "src1_ne=[6144,1,2,1]", 1)
        with self.assertRaisesRegex(gate.GateError, "not model-exact"):
            gate.parse_route_log(text)

    def test_selector_off_rejects_any_canonical_marker(self) -> None:
        self.assertFalse(
            gate.parse_selector_off_log(f"prefix {gate.SELECTOR}: 0")["canonical_markers_observed"]
        )
        with self.assertRaisesRegex(gate.GateError, "canonical route marker"):
            gate.parse_selector_off_log(valid_route_log(startup=False))


class WorkerRecordTests(unittest.TestCase):
    def test_extracts_result_amid_noise(self) -> None:
        record = {
            "schema_version": 1,
            "pid": 123,
            "bootstrap_order": "m1-first-ab",
            "device_name": "SYCL0",
            "device_description": "Intel Arc Pro B70",
            "weight_type": "Q8_0",
            "weight_shape": [6144, 5120, 1, 1],
            "flat_input_shape": [6144, 2, 1, 1],
            "recurrent_input_shape": [6144, 1, 2, 1],
            "inputs_distinct": True,
            "bitwise_comparisons": 4,
            "bitwise_equal": True,
        }
        parsed = gate.parse_worker_record("backend noise\n" + json.dumps(record) + "\n", "m1-first-ab")
        self.assertEqual(parsed["pid"], 123)


class OutputInspectionTests(unittest.TestCase):
    @staticmethod
    def values(*items: float) -> bytes:
        return struct.pack(f"<{len(items)}f", *items)

    def write_common_inputs(self, root: Path) -> None:
        (root / "input-a.f32").write_bytes(self.values(1.0, 2.0))
        (root / "input-b.f32").write_bytes(self.values(3.0, 4.0))

    def test_forward_and_reverse_exact_outputs(self) -> None:
        m1_a = self.values(10.0, 11.0, 12.0)
        m1_b = self.values(20.0, 21.0, 22.0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            forward = root / "forward"
            reverse = root / "reverse"
            forward.mkdir()
            reverse.mkdir()
            self.write_common_inputs(forward)
            self.write_common_inputs(reverse)
            (forward / "m1-a.f32").write_bytes(m1_a)
            (forward / "m1-b.f32").write_bytes(m1_b)
            (forward / "flat-ab.f32").write_bytes(m1_a + m1_b)
            (forward / "recurrent-ab.f32").write_bytes(m1_a + m1_b)
            (reverse / "m1-a.f32").write_bytes(m1_a)
            (reverse / "m1-b.f32").write_bytes(m1_b)
            (reverse / "flat-ba.f32").write_bytes(m1_b + m1_a)
            (reverse / "recurrent-ba.f32").write_bytes(m1_b + m1_a)

            forward_result = gate.inspect_worker_outputs(forward, "m1-first-ab", k=2, m=3)
            reverse_result = gate.inspect_worker_outputs(reverse, "batched-first-ba", k=2, m=3)
            self.assertEqual(forward_result["raw"]["flat-ab"], m1_a + m1_b)
            self.assertEqual(reverse_result["raw"]["recurrent-ba"], m1_b + m1_a)
            self.assertTrue(all(gate.compare_fresh_processes(forward_result, reverse_result, m=3).values()))
            selector_off = root / "selector-off"
            selector_off.mkdir()
            self.write_common_inputs(selector_off)
            (selector_off / "m1-a.f32").write_bytes(m1_a)
            (selector_off / "m1-b.f32").write_bytes(m1_b)
            selector_off_result = gate.inspect_worker_outputs(
                selector_off, "selector-off-m1-ab", k=2, m=3
            )
            self.assertTrue(
                all(
                    gate.compare_selector_off_oracle(
                        selector_off_result, forward_result, reverse_result
                    ).values()
                )
            )

    def test_rejects_one_bit_difference(self) -> None:
        m1_a = self.values(10.0, 11.0, 12.0)
        m1_b = self.values(20.0, 21.0, 22.0)
        damaged = bytearray(m1_a + m1_b)
        damaged[-1] ^= 1
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_common_inputs(root)
            (root / "m1-a.f32").write_bytes(m1_a)
            (root / "m1-b.f32").write_bytes(m1_b)
            (root / "flat-ab.f32").write_bytes(m1_a + m1_b)
            (root / "recurrent-ab.f32").write_bytes(damaged)
            with self.assertRaisesRegex(gate.GateError, "bitwise mismatch"):
                gate.inspect_worker_outputs(root, "m1-first-ab", k=2, m=3)


class EnvironmentTests(unittest.TestCase):
    def test_only_clean_worker_lifecycle_allows_postflight(self) -> None:
        clean = {
            "returncode": 0,
            "clean_exit_no_survivor": True,
            "timed_out": False,
            "cleanup_required": False,
            "forced_kill": False,
            "survivor_pids": [],
        }
        self.assertTrue(gate.worker_lifecycle_allows_postflight(clean))
        for field, unsafe_value in (
            ("returncode", 1),
            ("clean_exit_no_survivor", False),
            ("timed_out", True),
            ("cleanup_required", True),
            ("forced_kill", True),
            ("survivor_pids", [123]),
        ):
            unsafe = dict(clean)
            unsafe[field] = unsafe_value
            self.assertFalse(gate.worker_lifecycle_allows_postflight(unsafe), field)

    def test_worker_environment_sanitizes_diagnostic_overrides(self) -> None:
        result = gate.worker_environment(
            {
                "PATH": "/bin",
                "LD_LIBRARY_PATH": "/oneapi/lib",
                "LD_PRELOAD": "/tmp/inject.so",
                "GGML_OTHER": "1",
                "SYCL_PI_TRACE": "2",
                "ZE_AFFINITY_MASK": "3",
            },
            Path("/candidate/bin"),
            2,
        )
        self.assertNotIn("LD_PRELOAD", result)
        self.assertNotIn("GGML_OTHER", result)
        self.assertNotIn("SYCL_PI_TRACE", result)
        self.assertEqual(result["ZE_AFFINITY_MASK"], "2")
        self.assertEqual(result[gate.SELECTOR], "1")
        self.assertEqual(result["GGML_SYCL_ENABLE_GRAPH"], "0")
        self.assertEqual(result["GGML_SYCL_PRIORITIZE_DMMV"], "0")
        self.assertEqual(result["LD_LIBRARY_PATH"], "/candidate/bin:/oneapi/lib")

    def test_library_environment_is_origin_first_and_drops_preload(self) -> None:
        result = gate.library_environment(
            {"LD_LIBRARY_PATH": "/oneapi/lib", "LD_PRELOAD": "/tmp/inject.so"},
            Path("/exact/hybrid"),
        )
        self.assertNotIn("LD_PRELOAD", result)
        self.assertEqual(result["LD_LIBRARY_PATH"], "/exact/hybrid:/oneapi/lib")

    def test_parses_xpu_smi_memory_table(self) -> None:
        text = "| GPU Memory Used (MiB)       | 43                                                                 |"
        self.assertEqual(gate.parse_gpu_used_mib(text), 43)

    def test_rejects_malformed_xpu_smi_memory(self) -> None:
        with self.assertRaisesRegex(gate.GateError, "could not parse"):
            gate.parse_gpu_used_mib("| GPU Memory Used (MiB) | unavailable |")

    def test_bounded_process_timeout_has_no_unbounded_wait(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = time.monotonic()
            result = gate.run_bounded_to_files(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                root / "stdout.log",
                root / "stderr.log",
                environment=dict(os.environ),
                timeout_seconds=1,
            )
            elapsed = time.monotonic() - started
            self.assertTrue(result["timed_out"])
            self.assertTrue(result["cleanup_required"])
            self.assertEqual(result["survivor_pids"], [])
            self.assertLess(elapsed, 5)

    def test_bounded_process_interrupt_cleans_private_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real_sleep = time.sleep
            calls = 0

            def interrupt_once(_seconds: float) -> None:
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise KeyboardInterrupt
                real_sleep(0.01)

            with mock.patch.object(gate.time, "sleep", side_effect=interrupt_once):
                with self.assertRaises(KeyboardInterrupt):
                    gate.run_bounded_to_files(
                        [sys.executable, "-c", "import time; time.sleep(30)"],
                        root / "stdout.log",
                        root / "stderr.log",
                        environment=dict(os.environ),
                        timeout_seconds=30,
                    )
            evidence = json.loads((root / "stdout.interruption.json").read_text())
            self.assertEqual(evidence["survivor_pids"], [])
            self.assertTrue(evidence["cleanup_required"])


class RuntimeManifestTests(unittest.TestCase):
    def make_runtime(self, root: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
        mapped: dict[str, object] = {}
        entries = []
        for index, stem in enumerate(gate.GGML_RUNTIME_OBJECTS):
            versioned = root / f"{stem}.0.18.1"
            versioned.write_bytes(f"object-{index}".encode())
            (root / stem).symlink_to(versioned.name)
            digest = gate.sha256_file(versioned)
            mapped[stem] = {
                "soname": f"{stem}.0",
                "link_path": str(root / stem),
                "resolved_path": str(versioned),
                "size_bytes": versioned.stat().st_size,
                "sha256": digest,
            }
            entries.append(
                {
                    "soname": f"{stem}.0",
                    "resolved_path": f"$ORIGIN/{versioned.name}",
                    "size_bytes": versioned.stat().st_size,
                    "sha256": digest,
                }
            )
        return mapped, entries

    def make_source(self, root: Path) -> tuple[Path, dict[str, object]]:
        source_dir = root / "source"
        source_file = source_dir / "ggml" / "src" / "ggml-sycl" / "ggml-sycl.cpp"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("candidate source\n")
        identity: dict[str, object] = {
            "head": "1" * 40,
            "status_line_count": 0,
            "ggml_sycl_cpp_sha256": gate.sha256_file(source_file),
        }
        return source_dir, identity

    def write_manifest(
        self,
        path: Path,
        entries: list[dict[str, object]],
        source: dict[str, object],
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "runtime_bundle_schema_version": 1,
                    "llama_cpp_commit": source["head"],
                    "runtime_loader_policy": {
                        "mode": "origin-first",
                        "variable": "LD_LIBRARY_PATH",
                    },
                    "source_provenance": {
                        "ggml_sycl_cpp_sha256": source["ggml_sycl_cpp_sha256"],
                    },
                    "experimental_controls": {
                        gate.SELECTOR: gate.EXPECTED_SELECTOR_CONTRACT,
                    },
                    "origin_shared_objects": entries,
                }
            )
        )

    def test_manifest_seals_exact_origin_objects_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mapped, entries = self.make_runtime(root)
            source_dir, source = self.make_source(root)
            manifest = root / "manifest.json"
            self.write_manifest(manifest, entries, source)
            result = gate.validate_runtime_manifest(manifest, root, mapped, source_dir, source)
            self.assertEqual(set(result["matched_objects"]), set(gate.GGML_RUNTIME_OBJECTS))
            self.assertEqual(result["source_binding"]["head"], source["head"])
            gate.assert_runtime_identity_unchanged(mapped)

    def test_manifest_rejects_wrong_companion_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mapped, entries = self.make_runtime(root)
            source_dir, source = self.make_source(root)
            entries[1]["sha256"] = "0" * 64
            manifest = root / "manifest.json"
            self.write_manifest(manifest, entries, source)
            with self.assertRaisesRegex(gate.GateError, "disagrees with manifest"):
                gate.validate_runtime_manifest(manifest, root, mapped, source_dir, source)

    def test_manifest_rejects_dirty_or_wrong_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mapped, entries = self.make_runtime(root)
            source_dir, source = self.make_source(root)
            manifest = root / "manifest.json"
            self.write_manifest(manifest, entries, source)
            dirty = dict(source)
            dirty["status_line_count"] = 1
            with self.assertRaisesRegex(gate.GateError, "must be clean"):
                gate.validate_runtime_manifest(manifest, root, mapped, source_dir, dirty)
            wrong = dict(source)
            wrong["head"] = "2" * 40
            with self.assertRaisesRegex(gate.GateError, "does not match"):
                gate.validate_runtime_manifest(manifest, root, mapped, source_dir, wrong)


if __name__ == "__main__":
    unittest.main()
