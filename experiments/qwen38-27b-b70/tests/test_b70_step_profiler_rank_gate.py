#!/usr/bin/env python3
"""The b70-step-profiler rank gate: resolved lazily, inside execute_model, not at register() time.

No torch and no XPU: torch, vllm.logger, vllm.v1.worker.gpu_model_runner and vllm.distributed.parallel_state are
stubbed in sys.modules, so this runs anywhere. Before 2026-09-18 the gate ran in register(), before the
tensor-parallel group existed, and both workers profiled as rank 0.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

OVERLAY = (
    Path(__file__).resolve().parents[1]
    / "overlays"
    / "b70-step-profiler"
    / "b70_step_profiler.py"
)


def load_overlay():
    spec = importlib.util.spec_from_file_location("b70_step_profiler_under_test", OVERLAY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeProfile:
    def __init__(self, **kwargs):
        self.exported: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def export_chrome_trace(self, path):
        self.exported.append(path)
        with open(path, "w") as handle:
            handle.write("{}\n")


def fake_torch():
    torch = types.ModuleType("torch")
    profiler = types.ModuleType("torch.profiler")
    activity = types.SimpleNamespace(CPU="cpu", XPU="xpu")
    profiler.ProfilerActivity = activity
    profiler.profile = FakeProfile
    torch.profiler = profiler
    torch.xpu = types.SimpleNamespace(synchronize=lambda: None)
    return torch


class FakeRunner:
    """Stand-in for GPUModelRunner; `calls` counts the unwrapped body."""

    calls = 0

    def execute_model(self, *args, **kwargs):
        type(self).calls += 1
        return "step"


class SchedulerOutput:
    def __init__(self, total_num_scheduled_tokens):
        self.total_num_scheduled_tokens = total_num_scheduled_tokens


class RankGateTest(unittest.TestCase):
    def setUp(self):
        self.module = load_overlay()
        self.tp_rank = 0
        self.tp_available = True
        self.tp_queries = 0
        self.logs: list[str] = []

    def install_modules(self):
        """Put stub torch/vllm modules in sys.modules for the duration of one test."""
        runner_module = types.ModuleType("vllm.v1.worker.gpu_model_runner")
        runner_module.GPUModelRunner = type("GPUModelRunner", (FakeRunner,), {})

        def get_tensor_model_parallel_rank():
            self.tp_queries += 1
            if not self.tp_available:
                raise AssertionError("tensor model parallel group is not initialized")
            return self.tp_rank

        parallel_state = types.ModuleType("vllm.distributed.parallel_state")
        parallel_state.get_tensor_model_parallel_rank = get_tensor_model_parallel_rank

        logger_module = types.ModuleType("vllm.logger")
        logger_module.init_logger = lambda name: types.SimpleNamespace(
            warning=lambda message, *args: self.logs.append(message % args if args else message)
        )

        vllm = types.ModuleType("vllm")
        vllm_v1 = types.ModuleType("vllm.v1")
        vllm_worker = types.ModuleType("vllm.v1.worker")
        vllm_distributed = types.ModuleType("vllm.distributed")
        vllm.v1 = vllm_v1
        vllm.distributed = vllm_distributed
        vllm.logger = logger_module
        vllm_v1.worker = vllm_worker
        vllm_worker.gpu_model_runner = runner_module
        vllm_distributed.parallel_state = parallel_state

        modules = {
            "torch": fake_torch(),
            "vllm": vllm,
            "vllm.v1": vllm_v1,
            "vllm.v1.worker": vllm_worker,
            "vllm.v1.worker.gpu_model_runner": runner_module,
            "vllm.distributed": vllm_distributed,
            "vllm.distributed.parallel_state": parallel_state,
            "vllm.logger": logger_module,
        }
        patcher = mock.patch.dict(sys.modules, modules)
        patcher.start()
        self.addCleanup(patcher.stop)
        return runner_module.GPUModelRunner

    def register(self, directory, **env):
        """register() with a clean environment plus `env`; RANK/LOCAL_RANK stay unset as in a spawned XPU worker."""
        environment = {"B70_PROFILE_DIR": directory, "B70_PROFILE_SKIP": "1", "B70_PROFILE_STEPS": "2"}
        environment.update(env)
        cls = self.install_modules()
        patcher = mock.patch.dict(os.environ, environment, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.module.register()
        return cls

    def drive(self, cls, calls=4, scheduled=1):
        runner = cls()
        for _ in range(calls):
            runner.execute_model(SchedulerOutput(scheduled))
        return runner

    def traces(self, directory):
        return sorted(path.name for path in Path(directory).iterdir())

    # --- the gate itself -------------------------------------------------

    def test_register_does_not_query_the_rank(self):
        """register() runs before the TP group exists, so it must not resolve the rank there."""
        with tempfile.TemporaryDirectory() as directory:
            self.tp_available = False
            self.register(directory, B70_PROFILE_RANKS="0")
            self.assertEqual(self.tp_queries, 0)

    def test_non_selected_rank_does_not_profile(self):
        """The regression: TP unavailable at register(), rank 1 at the first call -> rank 1 stays out."""
        with tempfile.TemporaryDirectory() as directory:
            self.tp_available = False
            cls = self.register(directory, B70_PROFILE_RANKS="0")
            self.tp_available, self.tp_rank = True, 1
            self.drive(cls)
            self.assertEqual(self.traces(directory), [])
            self.assertEqual(cls.calls, 4)
            self.assertTrue(any("rank 1" in line and "not selected" in line for line in self.logs))

    def test_selected_rank_profiles_and_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            self.tp_available = False
            cls = self.register(directory, B70_PROFILE_RANKS="0")
            self.tp_available, self.tp_rank = True, 0
            self.drive(cls)
            self.assertEqual(
                self.traces(directory),
                [f"worker-rank0-pid{os.getpid()}.json", f"worker-rank0-pid{os.getpid()}.meta.json"],
            )
            self.assertTrue(any("rank 0" in line and "is profiling" in line for line in self.logs))

    def test_rank_is_logged_once(self):
        with tempfile.TemporaryDirectory() as directory:
            cls = self.register(directory, B70_PROFILE_RANKS="0")
            self.drive(cls, calls=6)
            gate_lines = [line for line in self.logs if "is profiling" in line or "not selected" in line]
            self.assertEqual(len(gate_lines), 1, gate_lines)
            self.assertEqual(self.tp_queries, 1)

    def test_rank_list_is_honoured(self):
        with tempfile.TemporaryDirectory() as directory:
            cls = self.register(directory, B70_PROFILE_RANKS="0,1")
            self.tp_rank = 1
            self.drive(cls)
            self.assertIn(f"worker-rank1-pid{os.getpid()}.json", self.traces(directory))

    def test_unset_ranks_profiles_every_rank(self):
        """B70_PROFILE_RANKS unset keeps the old behaviour: every worker profiles, under its true rank."""
        with tempfile.TemporaryDirectory() as directory:
            cls = self.register(directory)
            self.tp_rank = 1
            self.drive(cls)
            self.assertIn(f"worker-rank1-pid{os.getpid()}.json", self.traces(directory))

    # --- fallbacks -------------------------------------------------------

    def test_falls_back_to_the_runner_rank_attribute(self):
        """No TP group at all: the worker's own rank attribute decides, not a RANK/LOCAL_RANK default of 0."""
        with tempfile.TemporaryDirectory() as directory:
            cls = self.register(directory, B70_PROFILE_RANKS="0")
            self.tp_available = False
            runner = cls()
            runner.rank = 1
            runner.execute_model(SchedulerOutput(1))
            runner.execute_model(SchedulerOutput(1))
            self.assertEqual(self.traces(directory), [])
            self.assertTrue(any("runner.rank" in line for line in self.logs))

    def test_falls_back_to_the_rank_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            cls = self.register(directory, B70_PROFILE_RANKS="0", RANK="1")
            self.tp_available = False
            self.drive(cls)
            self.assertEqual(self.traces(directory), [])
            self.assertTrue(any("$RANK" in line for line in self.logs))

    def test_resolve_rank_prefers_the_tensor_parallel_group(self):
        with tempfile.TemporaryDirectory() as directory:
            self.register(directory)
            self.tp_rank = 3
            runner = types.SimpleNamespace(rank=1, local_rank=1)
            self.assertEqual(self.module._resolve_rank(runner), (3, "tp-group"))

    # --- the other env flags still work ---------------------------------

    def test_by_prefill_windows_respect_the_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            cls = self.register(
                directory, B70_PROFILE_RANKS="0", B70_PROFILE_BY_PREFILL="1", B70_PROFILE_MIN_PREFILL="2048"
            )
            self.tp_rank = 1
            runner = cls()
            runner.execute_model(SchedulerOutput(4096))
            for _ in range(4):
                runner.execute_model(SchedulerOutput(1))
            self.assertEqual(self.traces(directory), [])

    def test_by_prefill_window_exports_on_the_selected_rank(self):
        with tempfile.TemporaryDirectory() as directory:
            cls = self.register(
                directory, B70_PROFILE_RANKS="0", B70_PROFILE_BY_PREFILL="1", B70_PROFILE_MIN_PREFILL="2048"
            )
            runner = cls()
            runner.execute_model(SchedulerOutput(4096))
            for _ in range(2):
                runner.execute_model(SchedulerOutput(1))
            self.assertEqual(self.traces(directory), ["worker-rank0-ctx4096.json", "worker-rank0-ctx4096.meta.json"])

    def test_profile_dir_unset_is_a_no_op(self):
        cls = self.install_modules()
        original = cls.execute_model
        with mock.patch.dict(os.environ, {}, clear=True):
            self.module.register()
        self.assertIs(cls.execute_model, original)
        self.assertFalse(getattr(cls, "_b70_step_profiler", False))


if __name__ == "__main__":
    unittest.main()
