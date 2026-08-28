#!/usr/bin/env python3

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("verify-0731-endpoint-binding.py")
SPEC = importlib.util.spec_from_file_location("verify_0731_endpoint_binding", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stat_row(pid: int, parent: int, start: int) -> str:
    tail = ["S", str(parent), *(["0"] * 17), str(start)]
    return f"{pid} (vllm worker) {' '.join(tail)}\n"


class BindingFixture:
    def __init__(self, root: Path, mode: str = "smoke") -> None:
        self.root = root
        self.mode = mode
        self.port = 18080
        self.pid = 4321
        self.start = 987654
        self.boot = "11111111-2222-3333-4444-555555555555"
        label = "canary" if mode == "smoke" else "full"
        self.run = root / f"target-eager-{label}-20260828T210000Z"
        self.run.mkdir()
        self.model = root / "model"
        self.model.mkdir()
        self.receipt = root / "summary.json"
        (self.model / "SHA256SUMS").write_text("pinned manifest\n", encoding="utf-8")
        self.receipt.write_text('{"status":"pass"}\n', encoding="utf-8")
        self.original_manifest = MODULE.MANIFEST_SHA256
        self.original_validation = MODULE.VALIDATION_SHA256
        self.original_runtime_verifier = MODULE.verify_live_runtime_files
        MODULE.MANIFEST_SHA256 = digest(self.model / "SHA256SUMS")
        MODULE.VALIDATION_SHA256 = digest(self.receipt)
        MODULE.verify_live_runtime_files = lambda: None
        (self.run / "preflight.log").write_text("four-rank pass\n", encoding="utf-8")

        self.proc = root / "proc"
        (self.proc / "sys/kernel/random").mkdir(parents=True)
        (self.proc / "sys/kernel/random/boot_id").write_text(self.boot, encoding="ascii")
        (self.proc / "net").mkdir()
        self.set_listeners([12345])
        self.add_process(self.pid, 1, self.start, [12345])

        context = "256" if mode == "smoke" else "2048"
        stamp = "20260828T210000Z"
        cache = (
            "/mnt/fast-ai/vllm-cache-exp/deepseek-v4-flash-0731-reap-"
            f"{MODULE.REVISION}/target-eager-{stamp}"
        )
        self.identity = dict(MODULE.STATIC_IDENTITY)
        self.identity.update(
            {
                "launcher_pid": str(self.pid),
                "host_boot_id": self.boot,
                "process_start_ticks": str(self.start),
                "host": "127.0.0.1",
                "port": str(self.port),
                "preflight_log_sha256": digest(self.run / "preflight.log"),
                "model": str(self.model),
                "artifact_manifest_sha256": MODULE.MANIFEST_SHA256,
                "full_validation_summary": str(self.receipt),
                "full_validation_summary_sha256": MODULE.VALIDATION_SHA256,
                "max_model_len": context,
                "max_num_batched_tokens": context,
                "vllm_xpu_v4_capture_cycle_arm_file": str(
                    self.run / "disabled-cycle-capture.arm"
                ),
                "vllm_xpu_v4_divergence_arm_file": str(
                    self.run / "disabled-divergence.arm"
                ),
                "ld_library_path": (
                    "/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib:"
                    "/home/steve/.venvs/deepseek-v4-xpu/lib:/opt/runtime"
                ),
                "vllm_cache_root": f"{cache}/vllm",
                "torchinductor_cache_dir": f"{cache}/torchinductor",
                "deepseek_0731_target_profile": mode,
                "argv": shlex_join(MODULE.expected_argv(self.port, mode, self.model)),
            }
        )
        self.identity_path = self.run / "identity.txt"
        self.write_identity()
        self.write_cmdline(MODULE.expected_argv(self.port, mode, self.model))
        self.write_environ(context)

    def close(self) -> None:
        MODULE.MANIFEST_SHA256 = self.original_manifest
        MODULE.VALIDATION_SHA256 = self.original_validation
        MODULE.verify_live_runtime_files = self.original_runtime_verifier

    def write_identity(self) -> None:
        self.identity_path.write_text(
            "".join(f"{key}={value}\n" for key, value in self.identity.items()),
            encoding="utf-8",
        )

    def add_process(self, pid: int, parent: int, start: int, inodes: list[int]) -> None:
        process = self.proc / str(pid)
        (process / "fd").mkdir(parents=True, exist_ok=True)
        (process / "stat").write_text(stat_row(pid, parent, start), encoding="ascii")
        for index, inode in enumerate(inodes):
            os.symlink(f"socket:[{inode}]", process / "fd" / str(index + 3))

    def write_cmdline(self, argv: list[str]) -> None:
        raw = b"\0".join(part.encode("utf-8") for part in [MODULE.PYTHON, *argv]) + b"\0"
        (self.proc / str(self.pid) / "cmdline").write_bytes(raw)

    def write_environ(self, context: str) -> None:
        environment = {key.upper(): "0" for key in MODULE.ZERO_IDENTITY_KEYS}
        environment.update(
            {
                "MODEL_PATH": str(self.model),
                "MODEL_REVISION": MODULE.REVISION,
                "SERVED_MODEL_NAME": MODULE.MODEL,
                "DEEPSEEK_0731_VALIDATION_SUMMARY": str(self.receipt),
                "DEEPSEEK_0731_TARGET_PROFILE": self.mode,
                "VLLM_TARGET_DEVICE": "xpu",
                "ONEAPI_DEVICE_SELECTOR": "level_zero:*",
                "ZE_AFFINITY_MASK": "0,1,2,3",
                "XPU_GRAPH": "0",
                "VLLM_XPU_ENABLE_XPU_GRAPH": "0",
                "VLLM_XPU_FORCE_GRAPH_WITH_COMM": "0",
                "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE": "0",
                "COMPILATION_CONFIG": '{"cudagraph_mode":"NONE"}',
                "ENFORCE_EAGER": "1",
                "TP_SIZE": "4",
                "PP_SIZE": "1",
                "DP_SIZE": "1",
                "DP_SIZE_LOCAL": "1",
                "MAX_MODEL_LEN": context,
                "MAX_NUM_BATCHED_TOKENS": context,
                "GPU_MEMORY_UTILIZATION": "0.95",
                "VLLM_XPU_FUSED_MOE_USE_REF": "0",
                "VLLM_XPU_FUSED_MOE_USE_MXFP4_FP8": "0",
                "VLLM_XPU_USE_SAMPLER_KERNEL": "1",
                "VLLM_XPU_LOG_FP8_LINEAR_SHAPES": "0",
                "VLLM_XPU_V4_BLOCK_FP8_W8A16_SHAPES": "",
                "VLLM_XPU_MXFP4_SMALL_M_N": "64",
                "VLLM_XPU_V4_DIRECT_FP8_BLOCK_H": "16",
                "VLLM_XPU_V4_DIRECT_FP8_NUM_WARPS": "8",
                "VLLM_XPU_V4_SPLIT_FP8_BLOCK_H": "16",
                "VLLM_XPU_V4_SPLIT_FP8_QK_NUM_WARPS": "8",
                "VLLM_XPU_V4_SPLIT_FP8_PV_NUM_WARPS": "4",
                "VLLM_CUSTOM_SCOPES_FOR_PROFILING": "0",
                "VLLM_XPU_V4_CAPTURE_CYCLE_WIDTH": "2",
                "VLLM_XPU_V4_CAPTURE_CYCLE_DIR": "",
                "VLLM_XPU_V4_CAPTURE_CYCLE_ARM_FILE": self.identity[
                    "vllm_xpu_v4_capture_cycle_arm_file"
                ],
                "VLLM_XPU_V4_DIVERGENCE_CAPTURE_DIR": "",
                "VLLM_XPU_V4_DIVERGENCE_ARM_FILE": self.identity[
                    "vllm_xpu_v4_divergence_arm_file"
                ],
                "VLLM_XPU_V4_DIVERGENCE_STAGES": "layer_out",
                "VLLM_XPU_V4_DIVERGENCE_LAYERS": "all",
                "VLLM_XPU_V4_DIVERGENCE_MODE": "hash",
                "VLLM_XPU_V4_DIVERGENCE_MAX_RECORDS": "2048",
                "VLLM_XPU_DSPARK_CONFIDENCE_GATE_THRESHOLD": "",
                "VLLM_XPU_DSPARK_DRAFT_PREFIX_CAP": "0",
                "DSPARK_KV_CACHE_MEMORY_BYTES": "125829120",
                "VLLM_EXTRA_ARGS": "--enable-prompt-tokens-details --kv-cache-memory 125829120",
                "VLLM_MULTI_STREAM_GEMM_TOKEN_THRESHOLD": "1024",
                "TRITON_CACHE_AUTOTUNING": "1",
                "VLLM_TRITON_FORCE_FIRST_CONFIG": "0",
                "VLLM_CACHE_ROOT": self.identity["vllm_cache_root"],
                "TORCHINDUCTOR_CACHE_DIR": self.identity["torchinductor_cache_dir"],
                "ONECCL_INSTALL_DIR": "/home/steve/.venvs/deepseek-v4-xpu",
                "ONECCL_LIB_DIR": MODULE.STATIC_IDENTITY["oneccl_lib"],
                "ONECCL_SOURCE_TREE": MODULE.STATIC_IDENTITY["oneccl_source_tree"],
                "ONECCL_FORCE_PRELOAD": "1",
                "CCL_ROOT": "/home/steve/.venvs/deepseek-v4-xpu",
                "CCL_ATL_TRANSPORT": "ofi",
                "CCL_TOPO_P2P_ACCESS": "1",
                "CCL_SYCL_ALLREDUCE_LL": "ring",
                "CCL_SYCL_ALLREDUCE_LL_THRESHOLD": "4096",
                "CCL_SYCL_ALLREDUCE_ARC": "0",
                "B70_ONECCL_SYCL_MAX_BYTES": "",
                "B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES": "131072",
                "B70_ONECCL_SYCL_ALLGATHER_MAX_BYTES": "",
                "B70_ONECCL_SYCL_REDUCE_SCATTER_MAX_BYTES": "",
                "CCL_KERNEL_PATH": MODULE.STATIC_IDENTITY["ccl_kernel_path"],
                "FI_TCP_IFACE": "eno1",
                "CCL_KVS_IFACE": "eno1",
                "LD_PRELOAD": MODULE.STATIC_IDENTITY["ld_preload"],
                "LD_LIBRARY_PATH": self.identity["ld_library_path"],
                "PYTHONPATH": MODULE.STATIC_IDENTITY["pythonpath"],
                "RUN_PREFLIGHT": "1",
                "VERIFY_MANIFEST": "0",
            }
        )
        raw = b"\0".join(
            f"{key}={value}".encode("utf-8") for key, value in environment.items()
        ) + b"\0"
        (self.proc / str(self.pid) / "environ").write_bytes(raw)

    def set_listeners(self, inodes: list[int], address: str = "0100007F") -> None:
        rows = ["  sl  local_address rem_address   st tx_queue tr tm->when retrnsmt uid timeout inode"]
        for index, inode in enumerate(inodes):
            rows.append(
                f"{index}: {address}:{self.port:04X} 00000000:0000 0A "
                f"00000000:00000000 00:00000000 00000000 1000 0 {inode}"
            )
        (self.proc / "net" / "tcp").write_text("\n".join(rows) + "\n", encoding="ascii")

    def validate(self, baseline: Path | None = None):
        return MODULE.validate(
            self.identity_path,
            f"http://127.0.0.1:{self.port}",
            self.receipt,
            self.mode,
            self.proc,
            self.model,
            baseline,
        )


def shlex_join(argv: list[str]) -> str:
    import shlex

    return shlex.join(argv)


class EndpointBindingTests(unittest.TestCase):
    def fixture(self, root: Path, mode: str = "smoke") -> BindingFixture:
        fixture = BindingFixture(root, mode)
        self.addCleanup(fixture.close)
        return fixture

    def test_valid_direct_listener_and_baseline(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self.fixture(Path(temporary))
            first = fixture.validate()
            self.assertEqual(first["listener_socket_inodes"], ["12345"])
            baseline = Path(temporary) / "binding.json"
            baseline.write_text(json.dumps(first), encoding="utf-8")
            second = fixture.validate(baseline)
            self.assertEqual(second["baseline_sha256"], digest(baseline))

    def test_exact_url_and_exact_full_context_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self.fixture(Path(temporary), "full")
            fixture.validate()
            with self.assertRaises(MODULE.BindingError):
                MODULE.validate(
                    fixture.identity_path,
                    f"http://localhost:{fixture.port}",
                    fixture.receipt,
                    "full",
                    fixture.proc,
                    fixture.model,
                )
            fixture.identity["max_model_len"] = "4096"
            fixture.write_identity()
            with self.assertRaises(MODULE.BindingError):
                fixture.validate()

    def test_wrong_address_ambiguous_and_external_listeners_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self.fixture(Path(temporary))
            fixture.set_listeners([12345], "00000000")
            with self.assertRaises(MODULE.BindingError):
                fixture.validate()
            fixture.set_listeners([12345, 12346])
            fixture.add_process(4322, fixture.pid, 10, [12346])
            with self.assertRaises(MODULE.BindingError):
                fixture.validate()
            fixture.set_listeners([99999])
            fixture.add_process(9999, 1, 11, [99999])
            with self.assertRaises(MODULE.BindingError):
                fixture.validate()

    def test_duplicate_identity_and_process_replacement_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self.fixture(Path(temporary))
            with fixture.identity_path.open("a", encoding="utf-8") as handle:
                handle.write("port=18081\n")
            with self.assertRaises(MODULE.BindingError):
                fixture.validate()
            fixture.write_identity()
            (fixture.proc / str(fixture.pid) / "stat").write_text(
                stat_row(fixture.pid, 1, fixture.start + 1), encoding="ascii"
            )
            with self.assertRaises(MODULE.BindingError):
                fixture.validate()

    def test_receipt_pin_and_argv_are_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self.fixture(Path(temporary))
            fixture.identity["vllm_extra_args"] = "--speculative-config {}"
            fixture.write_identity()
            with self.assertRaises(MODULE.BindingError):
                fixture.validate()
            fixture.identity["vllm_extra_args"] = MODULE.STATIC_IDENTITY["vllm_extra_args"]
            fixture.write_identity()
            MODULE.VALIDATION_SHA256 = "0" * 64
            with self.assertRaises(MODULE.BindingError):
                fixture.validate()

    def test_live_environment_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self.fixture(Path(temporary))
            fixture.validate()
            path = fixture.proc / str(fixture.pid) / "environ"
            raw = path.read_bytes().replace(b"XPU_GRAPH=0\0", b"XPU_GRAPH=1\0")
            path.write_bytes(raw)
            with self.assertRaises(MODULE.BindingError):
                fixture.validate()

    def test_live_runtime_file_drift_is_rejected(self):
        original_sha256 = MODULE.sha256
        try:
            MODULE.sha256 = lambda path: (
                "0" * 64 if Path(path) == Path(MODULE.VLLM_CLI) else original_sha256(path)
            )
            with self.assertRaises(MODULE.BindingError):
                MODULE.verify_live_runtime_files()
        finally:
            MODULE.sha256 = original_sha256

    def test_atomic_report_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "binding.json"
            MODULE.atomic_json(output, {"status": "pass"})
            with self.assertRaises(MODULE.BindingError):
                MODULE.atomic_json(output, {"status": "replacement"})
            self.assertEqual(json.loads(output.read_text())["status"], "pass")

    def test_shell_drivers_are_fail_closed_and_full_gate_uses_512(self):
        driver = SCRIPT.with_name("qualify-0731-reap-target-endpoint.sh")
        launcher = SCRIPT.with_name("serve-k160-tp4-smoke.sh")
        subprocess.run(["bash", "-n", str(driver), str(launcher)], check=True)
        driver_text = driver.read_text(encoding="utf-8")
        launcher_text = launcher.read_text(encoding="utf-8")
        self.assertIn("--max-tokens 512", driver_text)
        self.assertIn("--baseline", driver_text)
        self.assertIn("flock --nonblock", driver_text)
        self.assertIn("--noproxy '*'", driver_text)
        self.assertGreaterEqual(driver_text.count('"endpoint-models.json"'), 2)
        self.assertIn('"overall_model_quality"', driver_text)
        self.assertEqual(launcher_text.count("printf 'ld_preload=%s"), 1)
        self.assertIn("vllm_xpu_v4_router_norm_max_m", launcher_text)
        self.assertIn("vllm_xpu_v4_direct_routed_moe_allow_256_expert_fallback", launcher_text)
        self.assertIn('if [[ -f "${kernel_tree}/vllm_xpu_kernels/_xpu_C.abi3.so" ]]', launcher_text)
        emitted = re.findall(r"printf '[^']*?([a-z][a-z0-9_.-]*)=%s", launcher_text)
        emitted.extend(("kv_cache_dtype", "block_size", "prefix_caching", "argv", "expert_parallel"))
        emitted.extend(
            (
                "package_torch",
                "package_triton-xpu",
                "package_vllm",
                "package_vllm-xpu-kernels",
                "package_oneccl",
            )
        )
        dynamic = {
            "launcher_pid", "host_boot_id", "process_start_ticks", "host", "port",
            "preflight_log_sha256", "model", "artifact_manifest_sha256",
            "full_validation_summary", "full_validation_summary_sha256",
            "max_model_len", "max_num_batched_tokens",
            "vllm_xpu_v4_capture_cycle_arm_file", "vllm_xpu_v4_divergence_arm_file",
            "ld_library_path", "vllm_cache_root", "torchinductor_cache_dir", "argv",
            "deepseek_0731_target_profile",
        }
        self.assertEqual(len(emitted), len(set(emitted)))
        self.assertEqual(set(emitted), set(MODULE.STATIC_IDENTITY) | dynamic)


if __name__ == "__main__":
    unittest.main()
