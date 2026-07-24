"""CPU-only corruption tests for the sharded-gather Phase-B counter tooling."""
from __future__ import annotations

import ast
import csv
import fcntl
import hashlib
import json
import os
import stat
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

import laguna_m8_gather_sharded_counter_parser as parser
import run_laguna_m8_gather_sharded_phase_a as phase_a
import analyze_laguna_m8_gather_sharded_phase_a as phase_a_analysis
import preflight_laguna_m8_gather_sharded_operational as operational
import run_laguna_m8_gather_sharded_phase_b as runner
import profile_laguna_m8_gather_sharded_phase_b_fixture as fixture

_TOOLS = Path(__file__).resolve().parent
fixture.counters = parser
fixture.phase_a = phase_a
fixture.phase_a_analysis = phase_a_analysis
fixture.SOURCE_TOOL_IDENTITIES = {
    "phase_b": {
        role: {"path": str(_TOOLS / filename), "sha256": fixture.sha(_TOOLS / filename)}
        for role, filename in fixture.TOOL_FILENAMES.items()
    },
    "phase_a": {
        "runner": {"path": str(_TOOLS / "run_laguna_m8_gather_sharded_phase_a.py"), "sha256": fixture.sha(_TOOLS / "run_laguna_m8_gather_sharded_phase_a.py")},
        "analyzer": {"path": str(_TOOLS / "analyze_laguna_m8_gather_sharded_phase_a.py"), "sha256": fixture.sha(_TOOLS / "analyze_laguna_m8_gather_sharded_phase_a.py")},
    },
}
runner.counters = parser
runner.operational = operational
runner.fixture = fixture
runner.phase_a = phase_a
runner.phase_a_analysis = phase_a_analysis
runner.SOURCE_TOOL_IDENTITIES = fixture.SOURCE_TOOL_IDENTITIES

import analyze_laguna_m8_gather_sharded_phase_b as analyzer  # noqa: E402

runner.analyzer = analyzer

def metric_row(arm: str, gid: int) -> dict[str, str]:
    row = {field: "1" for field in parser.METRIC_FIELDS}
    geometry = parser.GEOMETRY[parser.ARMS[arm]]
    row.update({"Kernel": parser.KERNELS[parser.ARMS[arm]], "GlobalInstanceId": str(gid), "SubDeviceId": "0", "ReportsCount": "1", "GpuTime[ns]": "10", "ASYNC_GPGPU_THREADGROUP_COUNT[events]": str(geometry["workgroups"]), "ASYNC_GPGPU_THREAD_EXIT_COUNT[messages]": str(geometry["simd32_subgroups"])})
    for field in parser.ZERO_INVALIDITY_FIELDS:
        row[field] = "0"
    row.update({"GPU_MEMORY_BYTE_READ[bytes]": "100", "GPU_MEMORY_BYTE_WRITE[bytes]": "20", "LOAD_STORE_CACHE_BYTE_READ[bytes]": "30", "LOAD_STORE_CACHE_BYTE_WRITE[bytes]": "10", "XVE_ACTIVE[%]": "70", "XVE_THREADS_OCCUPANCY_ALL[%]": "60", "XVE_STALL[%]": "10"})
    return row

def write_metrics(path: Path, arm: str) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=parser.METRIC_FIELDS)
        writer.writeheader()
        # Deliberately write valid 47-dispatch epochs out of order.  A single
        # eviction instance separates every adjacent epoch.
        gids = list(range(parser.RAW_ROWS))
        for gid in list(reversed(gids)):
            writer.writerow(metric_row(arm, gid))

def write_timing(path: Path, arm: str, *, extra: bool = False) -> None:
    kernel = parser.KERNELS[parser.ARMS[arm]]
    timing = {"Kernel": kernel, "Calls": str(parser.RAW_ROWS), "Time (ns)": str(parser.RAW_ROWS * 10), "Time (%)": "100", "Average (ns)": "10", "Min (ns)": "10", "Max (ns)": "10"}
    prop = {"Kernel": kernel, "Compiled": "AOT", "SIMD": "32", "Number of Arguments": str(parser.GEOMETRY[parser.ARMS[arm]]["kernel_arguments"]), "SLM Per Work Group": "0", "Private Memory Per Thread": "0", "Spill Memory Per Thread": "0", "Register File Size Per Thread": "128"}
    with path.open("w", newline="") as handle:
        handle.write("=== Device Timing Summary ===\n")
        handle.write(f"Total Device Time for L0 backend (ns): {parser.RAW_ROWS * 10}\n")
        writer = csv.DictWriter(handle, fieldnames=parser.TIMING_FIELDS)
        writer.writeheader()
        writer.writerow(timing)
        if extra:
            writer.writerow({**timing, "Kernel": "unexpected"})
        handle.write("=== Kernel Properties ===\n")
        writer = csv.DictWriter(handle, fieldnames=parser.PROPERTY_FIELDS)
        writer.writeheader()
        writer.writerow(prop)

class PhaseBCounterTests(unittest.TestCase):
    def test_frozen_86_field_header(self) -> None:
        self.assertEqual(len(parser.METRIC_FIELDS), 86)
        self.assertEqual(parser.METRIC_HEADER_SHA256, "2f1add0fd583d68e3f9dfe9cd34577f25de4aff28e0a2c203ccaab1c567ce438")

    def test_unordered_611_metrics_retains_exactly_517(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "metrics.csv"
            write_metrics(path, "A1")
            report = parser.parse_metrics(path, "A1")
            self.assertEqual(report["raw_rows"], 611)
            self.assertEqual(report["retained_rows"], 517)
            self.assertEqual(report["global_instance_ids_sorted"], list(range(611)))

    def test_extra_timing_and_invalid_report_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            timing, metrics = root / "timing", root / "metrics"
            write_timing(timing, "B1", extra=True)
            with self.assertRaisesRegex(RuntimeError, "exactly one"):
                parser.parse_timing(timing, "B1")
            write_metrics(metrics, "B1")
            text = metrics.read_text().replace(",0,1,", ",1,1,", 1)
            metrics.write_text(text)
            with self.assertRaises(RuntimeError):
                parser.parse_metrics(metrics, "B1")

    def test_temporal_capture_rejects_auxiliaries_and_nonconsecutive_gids(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            timing, metrics = root / "timing", root / "metrics"
            write_timing(timing, "A1", extra=True)
            with self.assertRaises(RuntimeError):
                parser.parse_timing(timing, "A1")
            write_metrics(metrics, "A1")
            # Keep 611 rows but create a one-ID gap.
            with metrics.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["GlobalInstanceId"] = str(parser.RAW_ROWS)
            with metrics.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=parser.METRIC_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(RuntimeError, "consecutive"):
                parser.parse_metrics(metrics, "A1")

    def test_all_memory_lsc_and_xve_gates_are_per_field_and_zero_safe(self) -> None:
        control = {"means": {"GPU_MEMORY_BYTE_READ[bytes]": 10.0, "GPU_MEMORY_BYTE_WRITE[bytes]": 0.0, "LOAD_STORE_CACHE_BYTE_READ[bytes]": 10.0, "LOAD_STORE_CACHE_BYTE_WRITE[bytes]": 0.0, "XVE_ACTIVE[%]": 70.0, "XVE_THREADS_OCCUPANCY_ALL[%]": 60.0, "XVE_STALL[%]": 10.0}}
        candidate = {"means": {**control["means"], "GPU_MEMORY_BYTE_READ[bytes]": 10.2, "GPU_MEMORY_BYTE_WRITE[bytes]": 1.0}}
        decision = parser.compare(control, candidate)
        self.assertFalse(decision["gpu_memory_write_within_102pct"])
        self.assertFalse(decision["passed"])
        candidate["means"]["GPU_MEMORY_BYTE_WRITE[bytes]"] = 0.0
        candidate["means"]["XVE_STALL[%]"] = 10.51
        self.assertFalse(parser.compare(control, candidate)["xve_stall_within_0_5pp"])

    def test_unitrace_command_is_exact_compute_basic_pid_one_visible_device(self) -> None:
        session = "LagunaB2Card2a9f84c30e21376b45ddc9172c086f4e1"
        command = runner.argv(
            Path("/mnt/fast-ai/packet.json"), "a" * 64,
            Path("/mnt/fast-ai/aggregate.json"), "b" * 64, 2, "B2",
            Path("/mnt/fast-ai/fixture.json"),
            {"ONEAPI_DEVICE_SELECTOR": "level_zero:0", "ZE_AFFINITY_MASK": "2"},
            session,
        )
        self.assertEqual(command[:9], ["/usr/bin/sudo", "-S", "-p", "", "-E", "--", "/usr/bin/env", "-i", "ONEAPI_DEVICE_SELECTOR=level_zero:0"])
        self.assertIn("ZE_AFFINITY_MASK=2", command)
        self.assertEqual(command[command.index("--group") + 1], "ComputeBasic")
        self.assertEqual(command[command.index("--include-kernels") + 1], "MoeGather")
        self.assertEqual(command[command.index("--devices-to-sample") + 1], "0")
        self.assertEqual(command[command.index("--follow-child-process") + 1], "0")
        self.assertIn("--start-paused", command)
        self.assertEqual(command[command.index("--session") + 1], session)
        self.assertIn("--kill-after=5s", command)
        python_index = command.index(str(runner.PYTHON))
        self.assertEqual(command[python_index + 1], "-I")
        self.assertEqual(Path(command[python_index + 2]).name, fixture.TOOL_FILENAMES["fixture"])
        self.assertEqual(command[-2:], ["--tool-stage", "/mnt/fast-ai/tool-stage"])

    def test_execution_bootstrap_imports_no_project_module_before_validation(self) -> None:
        base = Path(__file__).parent
        project_modules = {
            "laguna_m8_gather_sharded_counter_parser",
            "preflight_laguna_m8_gather_sharded_operational",
            "profile_laguna_m8_gather_sharded_phase_b_fixture",
            "run_laguna_m8_gather_sharded_phase_a",
            "analyze_laguna_m8_gather_sharded_phase_a",
            "analyze_laguna_m8_gather_sharded_phase_b",
        }
        for filename in ("run_laguna_m8_gather_sharded_phase_b.py", "profile_laguna_m8_gather_sharded_phase_b_fixture.py"):
            tree = ast.parse((base / filename).read_bytes())
            imported = {
                alias.name
                for node in tree.body
                if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names
            }
            self.assertTrue(project_modules.isdisjoint(imported), imported & project_modules)

    def test_runner_source_memfd_is_write_sealed(self) -> None:
        payload = b"print('sealed')\n"
        descriptor = runner._sealed_source(payload, "phase-b-test")
        try:
            required = runner.REQUIRED_SEALS
            self.assertEqual(os.pread(descriptor, len(payload), 0), payload)
            self.assertEqual(fcntl.fcntl(descriptor, runner.F_GET_SEALS) & required, required)
            with self.assertRaises(OSError):
                os.write(descriptor, b"x")
        finally:
            os.close(descriptor)

    def test_temporal_control_requires_exact_ack_not_only_zero_exit(self) -> None:
        session = "LagunaA1Card0c8f73d21a091b6e45f2c877e302ad0b4"
        descriptor = os.open(fixture.UNITRACE, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            fake = mock.Mock(returncode=0)
            fake.communicate.return_value = (b"", b"")
            with mock.patch.object(fixture.subprocess, "Popen", return_value=fake):
                with self.assertRaisesRegex(RuntimeError, "acknowledgement"):
                    fixture._control(fixture.UNITRACE, descriptor, "resume", session)
            resumed = f"[INFO] Session {session} is resumed\n".encode()
            fake.communicate.return_value = (b"", resumed)
            with mock.patch.object(fixture.subprocess, "Popen", return_value=fake):
                evidence = fixture._control(fixture.UNITRACE, descriptor, "resume", session)
            self.assertEqual(evidence["returncode"], 0)
            self.assertEqual(evidence["expected_stderr_utf8"], resumed.decode())
            stopped_ack = f"[INFO] Session {session} is stopped and can no longer be paused or resumed\n".encode()
            fake.communicate.return_value = (b"", stopped_ack)
            with mock.patch.object(fixture.subprocess, "Popen", return_value=fake):
                stopped = fixture._control(fixture.UNITRACE, descriptor, "stop", session)
            self.assertEqual(stopped["expected_stderr_utf8"], stopped_ack.decode())
        finally:
            os.close(descriptor)

    def test_phase_b_modules_have_no_module_scope_torch_import(self) -> None:
        base = Path(__file__).parent
        for name in ("laguna_m8_gather_sharded_counter_parser.py", "profile_laguna_m8_gather_sharded_phase_b_fixture.py", "run_laguna_m8_gather_sharded_phase_b.py", "analyze_laguna_m8_gather_sharded_phase_b.py"):
            tree = ast.parse((base / name).read_text())
            imports = [alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names]
            self.assertNotIn("torch", imports)

    def test_fixture_has_no_graph_or_compile_api_calls(self) -> None:
        tree = ast.parse((Path(__file__).with_name("profile_laguna_m8_gather_sharded_phase_b_fixture.py")).read_text())
        def dotted(node: ast.AST) -> str:
            if isinstance(node, ast.Name):
                return node.id
            if isinstance(node, ast.Attribute):
                base = dotted(node.value)
                return f"{base}.{node.attr}" if base else node.attr
            return ""
        calls = {dotted(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
        forbidden = {"torch.compile", "torch.xpu.graph", "torch.xpu.make_graphed_callables", "torch._dynamo.optimize", "torch.jit.trace", "torch.jit.script"}
        self.assertTrue(calls.isdisjoint(forbidden), calls & forbidden)

    def test_runner_and_fixture_independently_freeze_same_full_environment(self) -> None:
        required_candidate = {
            "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED": "1", "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE": "0",
            "VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM": "0", "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM": "0",
            "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0", "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64",
            "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0", "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0",
            "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1", "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1",
            "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1", "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1",
            "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1", "VLLM_XPU_EXACT_SPEC_ATTN": "1",
        }
        for rank in range(4):
            arm_root = Path(f"/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/test/card{rank}/A1")
            environment = runner.expected_environment(rank, arm_root)
            self.assertEqual(environment, fixture.expected_environment(rank, arm_root))
            self.assertEqual({key: environment[key] for key in required_candidate}, required_candidate)
            self.assertEqual(environment["ZE_AFFINITY_MASK"], str(rank))
            self.assertEqual(environment["XPU_GRAPH"], "0")
            self.assertEqual(environment["VLLM_XPU_ENABLE_XPU_GRAPH"], "0")
            self.assertEqual(environment["TORCH_COMPILE_DISABLE"], "1")
            self.assertEqual(environment["PYTHONPATH"], str(phase_a.TOOLS_ROOT))
            self.assertEqual(environment["PYTHONSAFEPATH"], "1")
            self.assertEqual(environment["LD_PRELOAD"], "")
            self.assertEqual(environment["HOME"], str(arm_root / "scratch/runtime/home"))
            self.assertNotIn("DRAFT_FLASH_DEPTH", environment)
        source = Path("/home/steve/src/laguna-xpu-kernels-gather-sharded-20260724/vllm_xpu_kernels/fused_moe_interface.py")
        tree = ast.parse(source.read_text())
        assignments = [
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "LAGUNA_M8_GATHER_SHARDED_REQUIRED_ENV" for target in node.targets)
        ]
        self.assertEqual(len(assignments), 1)
        environment = runner.expected_environment(0, Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/test/card0/A1"))
        self.assertEqual({key: environment[key] for key in assignments[0]}, assignments[0])

    def test_runner_and_fixture_independently_freeze_tools_and_temporal_control(self) -> None:
        self.assertEqual(runner.expected_tools(), fixture.expected_tools())
        self.assertEqual(runner.tool_identity(), fixture.counter_tool_identity())
        self.assertEqual(runner.temporal_control_identity(), fixture.temporal_control_identity())

    def test_post_constructor_environment_has_no_ld_preload_and_rejects_extra_graph_flag(self) -> None:
        session = "LagunaA1Card0c8f73d21a091b6e45f2c877e302ad0b4"
        commit = "a5bab309f4ffdd78bd127035c46f5f75371160f8"
        arm_root = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/test/card0/A1")
        environment = fixture.application_environment_contract(0, arm_root, session, "/sealed/libunitrace_tool.so", f"1.0 ({commit})")
        self.assertNotIn("LD_PRELOAD", environment)
        self.assertEqual(environment["UNITRACE_LD_PRELOAD_OLD"], "")
        self.assertEqual(fixture.validate_recorded_application_environment(environment, 0, arm_root, session, "/sealed/libunitrace_tool.so", commit), dict(sorted(environment.items())))
        environment["UNPACKETED_GRAPH_CAPTURE"] = "0"
        with self.assertRaisesRegex(RuntimeError, "known unitrace internals|unallowlisted"):
            fixture.validate_recorded_application_environment(environment, 0, arm_root, session, "/sealed/libunitrace_tool.so", commit)

    def test_torch_xpuuuid_parser_accepts_only_exact_torch_shape_and_reverse_bytes(self) -> None:
        raw = bytes.fromhex("868023e2000000002300000000000000")
        runtime_uuid = uuid.UUID(bytes=raw)
        fake_type = type("_XPUuuid", (), {
            "__module__": "torch._C",
            "__str__": lambda self: str(runtime_uuid),
        })
        value = fake_type()
        value.bytes = list(raw)
        parsed, parsed_raw = fixture._parse_runtime_uuid(value)
        self.assertEqual(parsed, runtime_uuid)
        self.assertEqual(parsed_raw[::-1].hex(), "000000000000002300000000e2238086")
        value.bytes[0] = 256
        with self.assertRaisesRegex(RuntimeError, "malformed|octets"):
            fixture._parse_runtime_uuid(value)

    def test_fixture_retained_fd_detects_path_substitution_and_inplace_race(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest = root / "manifest.json"
            manifest.write_bytes(fixture.canonical({"fixture": "test"}) + b"\n")
            route_epochs = [bytes([index % 251, (index + 1) % 251]) for index in range(288)]
            weight_epochs = [bytes([index % 251, 1, 2, 3]) for index in range(288)]
            routes, weights, route_map = root / "routes.bin", root / "weights.bin", root / "map.bin"
            routes.write_bytes(b"".join(route_epochs))
            weights.write_bytes(b"".join(weight_epochs))
            route_map.write_bytes(bytes(320))
            binding = {
                "root": str(root),
                "manifest": str(manifest),
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "canonical_route_map": {"path": str(route_map), "sha256": hashlib.sha256(route_map.read_bytes()).hexdigest()},
                "records": {
                    "route_rows": {"path": str(routes), "sha256": hashlib.sha256(routes.read_bytes()).hexdigest(), "dtype": "<u2", "shape": [288, 1], "per_epoch_sha256": [hashlib.sha256(value).hexdigest() for value in route_epochs]},
                    "weights": {"path": str(weights), "sha256": hashlib.sha256(weights.read_bytes()).hexdigest(), "dtype": "<u4", "shape": [288, 1], "per_epoch_sha256": [hashlib.sha256(value).hexdigest() for value in weight_epochs]},
                },
            }
            state = fixture._open_fixture_fds(binding)
            try:
                replacement = root / "replacement.bin"
                replacement.write_bytes(routes.read_bytes())
                os.replace(replacement, routes)
                with self.assertRaisesRegex(RuntimeError, "root descriptor changed|identity changed"):
                    fixture._validate_fixture_fds(state, binding)
            finally:
                fixture._close_fixture_fds(state)
            # Reopen cleanly, then mutate the retained inode itself.
            binding["records"]["route_rows"]["sha256"] = hashlib.sha256(routes.read_bytes()).hexdigest()
            state = fixture._open_fixture_fds(binding)
            try:
                writer = os.open(routes, os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
                try:
                    os.pwrite(writer, b"\xff\xff", 0)
                finally:
                    os.close(writer)
                with self.assertRaises(RuntimeError):
                    fixture._validate_fixture_fds(state, binding)
            finally:
                fixture._close_fixture_fds(state)

    def test_forged_output_and_input_exactness_evidence_is_rejected(self) -> None:
        classification = {"positive_zero": 1, "negative_zero": 0, "subnormal": 0, "finite_normal": 24575, "infinity": 0, "nan": 0, "nan_payloads_sha256": hashlib.sha256(b"").hexdigest()}
        phase_rows = [{"outputs": {"control_gather": f"{layer:064x}", "candidate_gather": f"{layer:064x}"}, "raw_bf16_classification": classification} for layer in range(parser.LAYERS)]
        evidence = [{"cycle": cycle, "layer": layer, "raw_bf16_le_sha256": f"{layer:064x}", "classification": classification} for cycle in range(parser.RAW_CYCLES) for layer in range(parser.LAYERS)]
        self.assertEqual(analyzer.validate_output_evidence(evidence, phase_rows, "candidate"), evidence)
        forged = [dict(row) for row in evidence]
        forged[-1]["raw_bf16_le_sha256"] = "f" * 64
        with self.assertRaisesRegex(RuntimeError, "canonical Phase-A"):
            analyzer.validate_output_evidence(forged, phase_rows, "candidate")
        fixture_binding = {"records": {"route_rows": {"per_epoch_sha256": [f"{index:064x}" for index in range(288)]}, "weights": {"per_epoch_sha256": [f"{index + 1:064x}" for index in range(288)]}}, "canonical_route_map": {"sha256": "a" * 64}}
        expected = {"route_rows": fixture_binding["records"]["route_rows"]["per_epoch_sha256"][:47], "weights": fixture_binding["records"]["weights"]["per_epoch_sha256"][:47], "canonical_route_map": "a" * 64}
        integrity = {"before": expected, "after": expected, "passed": True}
        analyzer.validate_input_integrity(integrity, fixture_binding)
        integrity = {"before": expected, "after": {**expected, "canonical_route_map": "b" * 64}, "passed": True}
        with self.assertRaisesRegex(RuntimeError, "immutability"):
            analyzer.validate_input_integrity(integrity, fixture_binding)

    def test_bad_matched_pair_cannot_be_rescued_by_card_aggregate(self) -> None:
        def means(memory_read: float) -> dict[str, float]:
            return {"GPU_MEMORY_BYTE_READ[bytes]": memory_read, "GPU_MEMORY_BYTE_WRITE[bytes]": 10.0, "LOAD_STORE_CACHE_BYTE_READ[bytes]": 10.0, "LOAD_STORE_CACHE_BYTE_WRITE[bytes]": 10.0, "XVE_ACTIVE[%]": 70.0, "XVE_THREADS_OCCUPANCY_ALL[%]": 60.0, "XVE_STALL[%]": 10.0}
        decision = analyzer.decide_card_counters({"A1": means(10.0), "B1": means(20.0), "B2": means(1.0), "A2": means(100.0)})
        self.assertFalse(decision["matched_pairs"][0]["decision"]["passed"])
        self.assertTrue(decision["aggregate"]["decision"]["passed"])
        self.assertFalse(decision["passed"])

    def test_finalizer_excludes_untrusted_runtime_scratch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "campaign"
            arm = root / "card0" / "A1"
            scratch = arm / "scratch"
            scratch.mkdir(parents=True, mode=0o700)
            (scratch / "cache").mkdir(mode=0o700)
            (scratch / "cache" / "runtime.bin").write_bytes(b"mutable-cache")
            os.symlink("/definitely-not-evidence", scratch / "cache" / "untrusted-link")
            campaign_evidence = root / "capture.json"
            arm_evidence = arm / "process-terminal.json"
            campaign_evidence.write_bytes(b'{"capture":"exact"}\n')
            arm_evidence.write_bytes(b'{"terminal":"exact"}\n')
            try:
                before = runner._tree_inventory(root)
                self.assertEqual({entry["path"] for entry in before}, {"capture.json", "card0/A1/process-terminal.json"})
                runner._finalize_campaign(root, {"format": "test-terminal", "status": "failed", "passed": False})
                final_inventory = runner._tree_inventory(root)
                self.assertTrue(all("/scratch/" not in f"/{entry['path']}/" for entry in final_inventory))
                self.assertTrue((scratch / "cache" / "untrusted-link").is_symlink())
                self.assertEqual(stat.S_IMODE(os.stat(scratch, follow_symlinks=False).st_mode), 0o700)
                for evidence in (campaign_evidence, arm_evidence, root / "freeze-manifest.json", root / "campaign-terminal.json"):
                    self.assertEqual(stat.S_IMODE(os.stat(evidence, follow_symlinks=False).st_mode), 0o444)
                for evidence_directory in (root, root / "card0", arm):
                    self.assertEqual(stat.S_IMODE(os.stat(evidence_directory, follow_symlinks=False).st_mode), 0o555)
                freeze = json.loads((root / "freeze-manifest.json").read_bytes())
                self.assertEqual(freeze["scratch_policy"], "excluded_non_evidence_never_traversed_or_chmodded")
                self.assertEqual([entry["path"] for entry in freeze["excluded_scratch_roots"]], ["card0/A1/scratch"])
                self.assertTrue(all("scratch" not in entry["path"] for entry in freeze["prior_files"]))
            finally:
                for directory in (root, root / "card0", arm, scratch, scratch / "cache"):
                    if directory.exists():
                        os.chmod(directory, 0o700)
                for evidence in (campaign_evidence, arm_evidence, root / "freeze-manifest.json", root / "campaign-terminal.json"):
                    if evidence.exists():
                        os.chmod(evidence, 0o600)

    def test_idle_analyzer_recomputes_raw_nested_evidence(self) -> None:
        operational = runner.operational
        resolved, metadata, digest = operational.resolve_executable(operational.DEFAULT_XPU_SMI, expected_sha256=operational.EXPECTED_XPU_SMI_SHA256)
        stdout, stderr = b'{"device_util_by_proc_list":[]}\n', b""
        child = {"process_id": 424242, "proc_dir_fd_acquired": True, "pidfd_acquired": True, "proc_exe_resolved": str(resolved), "executable_device": metadata.st_dev, "executable_inode": metadata.st_ino}
        sample = {
            "format": operational.FORMAT, "status": "passed", "observed_utc": "2026-07-24T00:00:00+00:00",
            "argv": [str(resolved), *operational.PS_ARGUMENTS], "environment": operational.OBSERVER_ENVIRONMENT,
            "timeout_seconds": operational.DEFAULT_TIMEOUT_SECONDS,
            "xpu_smi": {"configured_path": str(operational.DEFAULT_XPU_SMI), "resolved_path": str(resolved), "sha256": digest, "device": metadata.st_dev, "inode": metadata.st_ino},
            "child_identity": child, "raw_capture": operational.encode_capture(stdout, stderr),
            "idle": {"accepted_mode": "empty", "row_count": 0, "device_ids": [], "sanitized_payload": {"device_util_by_proc_list": []}},
        }
        self.assertEqual(analyzer.validate_operational_sample(sample), sample)
        forged = {**sample, "raw_capture": {key: value for key, value in sample["raw_capture"].items() if key != "stdout_base64"}}
        with self.assertRaisesRegex(RuntimeError, "raw capture schema"):
            analyzer.validate_operational_sample(forged)
        with self.assertRaisesRegex(RuntimeError, "schema/status"):
            analyzer.validate_operational_sample({"status": "passed"})

if __name__ == "__main__":
    unittest.main()
