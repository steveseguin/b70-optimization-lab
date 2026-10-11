#!/usr/bin/env python3
"""CPU-only boundary tests. Native alignment/Triton dispatch are CPU doubles.

These execute the real extracted Python wrappers; they are not an XPU arithmetic
qualification. Temporary receipts are deleted even on test failure.
"""
import ast
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import torch

HERE = Path(__file__).resolve().parent
COPY = HERE / "copies/overlay/vllm"
BASE = HERE.parent / "overlay/vllm"
MOE = "model_executor/layers/fused_moe"
spec = importlib.util.spec_from_file_location("boundary_test_module", COPY / "screen1b_moe_boundary.py")
boundary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boundary)


def aligned(shape):
    count = math.prod(shape)
    storage = torch.empty(count * 4 + 1024, dtype=torch.uint8, device="cpu")
    offset = (-storage.data_ptr()) % 1024
    return storage[offset:offset + count * 4].view(torch.float32).view(shape)


def extract(path, name, namespace):
    node = next(x for x in ast.walk(ast.parse(path.read_text()))
                if isinstance(x, ast.FunctionDef) and x.name == name)
    # Deferred annotations avoid importing accelerator/runtime modules.
    tree = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(tree), str(path), "exec"), namespace)
    return namespace[name]


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="moe-boundary-test-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.watcher = self.directory / "watcher.json"
        self.syncs = 0
        # Deterministic test clock: slow host fsync must not stand in for a dead
        # watcher. Stale/future heartbeat refusal is tested explicitly below.
        self.clock = time.time()
        timer = patch.object(boundary, "time", types.SimpleNamespace(time=lambda: self.clock,
                                                                     monotonic=time.monotonic))
        timer.start()
        self.addCleanup(timer.stop)
        self.b = boundary.Boundary(self.directory / "receipts", self.watcher, 0, "cpu", self.sync, cpu_test=True)
        self.refresh()

    def refresh(self, **override):
        value = dict(passed=True, boot_id=self.b.boot, new_fault_lines=[],
                     updated_unix=self.clock, read_started_unix=self.clock)
        value.update(override)
        self.watcher.write_text(json.dumps(value))

    def sync(self):
        self.syncs += 1

    def rows(self):
        return [json.loads(x) for x in self.b.path.read_text().splitlines()]

    def routing(self):
        ids = torch.tensor([[0, 128], [1, 129]], dtype=torch.int32, device="cpu")
        mapping = torch.full((512,), -1, dtype=torch.int32, device="cpu")
        mapping[:128] = torch.arange(128, device="cpu")
        state = self.b.router(ids, mapping, 2, 512)
        ordered = torch.tensor([0, 4, 2, 4, 1, 4, 3, 4], dtype=torch.int32, device="cpu")
        raw = torch.tensor([0, 1, 128, 129, 0], dtype=torch.int32, device="cpu")
        padded = torch.tensor([8], dtype=torch.int32, device="cpu")
        return state, ordered, raw, padded, mapping

    def validated(self):
        state, ordered, raw, padded, mapping = self.routing()
        self.b.raw_alignment(state, ordered, raw, padded)
        local = mapping[raw]
        self.b.remapped(state, local, ordered, padded)
        return ordered, local, padded

    def weight(self):
        weight, host = aligned((127, 16, 16)), aligned((1, 16, 16))
        weight.fill_(0.25)
        host.fill_(0.75)
        weight._q38_num_experts = 128
        weight._screen1b_boundary_owner = (os.getpid(), 0, "cpu")
        weight._q38_host_cpu = host
        weight._q38_host_storage = host
        weight._q38_row_map = {i: ("resident", i) for i in range(127)} | {127: ("host", 0)}
        weight._q38_base_table = torch.tensor(
            [i * 256 for i in range(127)] + [(host.data_ptr() - weight.data_ptr()) // 4],
            dtype=torch.int64, device="cpu")
        return weight

    def gemm_args(self):
        ordered, local, padded = self.validated()
        A = torch.arange(32, dtype=torch.float32, device="cpu").reshape(2, 16)
        B = self.weight()
        return dict(A=A, B=B, C=torch.empty((2, 2, 16), device="cpu"),
                    A_scale=torch.ones((2, 1), device="cpu"), B_scale=torch.ones((128, 1, 1), device="cpu"),
                    routes=None, sorted_ids=ordered, local_ids=local, padded=padded,
                    topk=2, config={"BLOCK_SIZE_M": 2, "BLOCK_SIZE_N": 16, "BLOCK_SIZE_K": 16},
                    block_shape=[128, 128], bias=None, mul_weight=False)

    def bad(self, message, function, *args, **kwargs):
        with self.assertRaisesRegex(boundary.BoundaryError, message):
            function(*args, **kwargs)
        self.assertTrue(self.b.failed)
        self.assertTrue(any(r.get("passed") is False or r["phase"].endswith("failed") for r in self.rows()))

    def test_good_alignment_receipts_and_nonlocal_zero_blocks(self):
        self.validated()
        row = next(x for x in self.rows() if x["phase"] == "alignment.local_pass")
        self.assertEqual(row["values"], [0, 1, -1, -1])
        self.assertEqual(row["nonlocal_zero_blocks"], 2)
        self.assertTrue(all({"rank", "pid", "device", "phase", "sequence"} <= x.keys() for x in self.rows()))
        self.assertTrue(any("sha256" in x for x in self.rows()))

    def test_good_compact_weight_all_rows(self):
        self.b.weights(self.weight())
        self.assertEqual(len(self.rows()[-1]["rows"]), 128)

    def test_good_dense_weight(self):
        self.b.weights(torch.empty((128, 16, 16), device="cpu"))

    def test_good_workspace_aliases(self):
        a, b = torch.empty(64, device="cpu"), torch.empty(64, device="cpu")
        self.b.workspace(a, b, 2, 2, 16, 16, 8, a[:32].view(2, 16))

    def test_good_eleven_pointer_census(self):
        self.b.before_gemm(**self.gemm_args())
        row = self.rows()[-1]
        self.assertEqual(row["phase"], "gemm.launch_ready")
        self.assertEqual(set(row["pointers"]), set(boundary.POINTERS))
        self.assertIsNone(row["pointers"]["b_bias_ptr"])
        self.assertIsNone(row["pointers"]["topk_weights_ptr"])
        self.assertFalse(row["native_usm_context_verified"])
        self.assertEqual(row["pointers"]["b_ptr"]["owner_pid"], os.getpid())

    def test_pointer_wrong_device(self):
        self.b.device = "xpu:3"
        self.bad("pointer device/owner mismatch", self.b.device_tensor, torch.empty(1, device="cpu"), "bad")

    def test_runtime_rejects_cpu(self):
        self.b.cpu_test = False
        self.bad("runtime requires XPU pointer", self.b.device_tensor, torch.empty(1, device="cpu"), "bad")

    def test_span_past_backing_storage(self):
        class BadTensor:
            shape = (16,)
            dtype = torch.float32
            device = torch.device("cpu")
            def untyped_storage(self):
                return types.SimpleNamespace(data_ptr=lambda: 4096, nbytes=lambda: 32)
            def data_ptr(self):
                return 4096
            def element_size(self):
                return 4
            def numel(self):
                return 16
            def stride(self):
                return (1,)
            def storage_offset(self):
                return 0
        self.bad("tensor span within allocation", self.b.register, BadTensor(), "invalid")

    def test_rank_specific_mapping_all_four_ranks(self):
        for rank in range(4):
            self.b.rank = rank
            mapping = torch.full((512,), -1, dtype=torch.int32, device="cpu")
            mapping[rank*128:(rank+1)*128] = torch.arange(128, device="cpu")
            state = self.b.router(torch.tensor([[0, 511]], dtype=torch.int32, device="cpu"), mapping, 2, 512)
            self.assertEqual(state["mapping"][rank*128], 0)

    def test_remapped_positive_invalid(self):
        state, ordered, raw, padded, mapping = self.routing()
        self.b.raw_alignment(state, ordered, raw, padded)
        local = mapping[raw]
        local[0] = 128
        self.bad("local remap differs", self.b.remapped, state, local, ordered, padded)

    def test_remapped_negative_invalid(self):
        state, ordered, raw, padded, mapping = self.routing()
        self.b.raw_alignment(state, ordered, raw, padded)
        local = mapping[raw]
        local[0] = -2
        self.bad("local remap differs", self.b.remapped, state, local, ordered, padded)

    def test_remapped_owned_to_nonlocal_invalid(self):
        state, ordered, raw, padded, mapping = self.routing()
        self.b.raw_alignment(state, ordered, raw, padded)
        local = mapping[raw]
        local[0] = -1
        self.bad("local remap differs", self.b.remapped, state, local, ordered, padded)

    def test_remapped_dtype(self):
        state, ordered, raw, padded, mapping = self.routing()
        self.b.raw_alignment(state, ordered, raw, padded)
        self.bad("remapped ID dtype/layout", self.b.remapped, state, mapping[raw].float(), ordered, padded)

    def test_alignment_dtype(self):
        state, ordered, raw, padded, _ = self.routing()
        self.bad("alignment buffer dtype/layout", self.b.raw_alignment, state, ordered.long(), raw, padded)

    def test_alignment_padded_not_scalar(self):
        state, ordered, raw, padded, _ = self.routing()
        self.bad("padded count scalar capacity", self.b.raw_alignment, state, ordered, raw, padded.repeat(2))

    def test_alignment_raw_block_capacity(self):
        state, ordered, raw, padded, _ = self.routing()
        self.bad("padded layout capacity/divisibility", self.b.raw_alignment, state, ordered, raw[:3], padded)

    def test_workspace_capacity(self):
        self.bad("workspace capacity", self.b.workspace, torch.empty(63, device="cpu"),
                 torch.empty(64, device="cpu"), 2, 2, 16, 16, 8)

    def test_workspace_overlap(self):
        common = torch.empty(128, device="cpu")
        self.bad("workspace13/workspace2 overlap", self.b.workspace,
                 common[:64], common[32:96], 2, 2, 16, 16, 8)

    def test_workspace_same_allocation_disjoint_passes(self):
        common = torch.empty(128, device="cpu")
        self.b.workspace(common[:64], common[64:], 2, 2, 16, 16, 8)

    def test_workspace_layout(self):
        self.bad("workspace layout/dtype", self.b.workspace,
                 torch.empty((8, 8), device="cpu").T, torch.empty(64, device="cpu"), 2, 2, 16, 16, 8)

    def test_workspace_dtype(self):
        self.bad("workspace layout/dtype", self.b.workspace,
                 torch.empty(64, dtype=torch.float32, device="cpu"),
                 torch.empty(64, dtype=torch.bfloat16, device="cpu"), 2, 2, 16, 16, 8)

    def test_output_workspace2_overlap(self):
        a, b = torch.empty(64, device="cpu"), torch.empty(64, device="cpu")
        self.bad("output capacity/workspace2 overlap", self.b.workspace, a, b, 2, 2, 16, 16, 8, b[:32])

    def test_output_insufficient_capacity(self):
        a, b = torch.empty(64, device="cpu"), torch.empty(64, device="cpu")
        self.bad("output capacity/workspace2 overlap", self.b.workspace, a, b, 2, 2, 16, 16, 8, a[:31])

    def test_output_partial_alias(self):
        common, b = torch.empty(128, device="cpu"), torch.empty(64, device="cpu")
        self.bad("output alias exceeds workspace13", self.b.workspace,
                 common[32:96], b, 2, 2, 16, 16, 8, common[:64])

    def test_gemm_output_live_input_overlap(self):
        args = self.gemm_args()
        common = torch.empty(64, device="cpu")
        args.update(A=common[:32].view(2, 16), C=common.view(2, 2, 16))
        self.bad("GEMM output overlaps live input", self.b.before_gemm, **args)

    def test_gemm_missing_alignment(self):
        args = self.gemm_args()
        self.b.alignment = {}
        self.bad("GEMM missing validated alignment", self.b.before_gemm, **args)

    def test_gemm_w2_route_weight_and_dense_table_placeholder(self):
        args = self.gemm_args()
        args.update(A=torch.ones((4, 16), device="cpu"), A_scale=torch.ones((4, 1), device="cpu"),
                    topk=1, routes=torch.ones((2, 2), device="cpu"), mul_weight=True,
                    B=torch.ones((128, 16, 16), device="cpu"))
        self.b.before_gemm(**args)
        row = self.rows()[-1]
        self.assertTrue(row["table_placeholder"])
        self.assertEqual(row["pointers"]["b_ptr"], row["pointers"]["b_table_ptr"])

    def test_missing_watcher_prevents_sync(self):
        self.watcher.unlink()
        self.bad("watcher/fault latch", self.b.stage, "blocked")
        self.assertEqual(self.syncs, 0)

    def test_fault_during_sync_prevents_readback(self):
        def sync():
            (self.directory / "STOP").write_text("fault")
        self.b.synchronize = sync
        class NeverRead:
            def detach(self):
                raise AssertionError("readback happened")
        self.bad("fault/stop latch", self.b.snapshot, NeverRead(), "blocked")

    def test_sync_failure_prevents_readback(self):
        def sync():
            raise RuntimeError("queue failure")
        self.b.synchronize = sync
        self.bad("synchronization failed", self.b.snapshot, object(), "blocked")

    def test_fault_before_readback_prevents_copy(self):
        clear = self.b.clear
        calls = 0
        def racing_clear():
            nonlocal calls
            calls += 1
            if calls == 3:
                (self.directory / "FAULT").write_text("fault")
            clear()
        self.b.clear = racing_clear
        self.bad("fault/stop latch", self.b.snapshot, object(), "blocked")

    def test_fault_during_readback_prevents_value_use(self):
        directory = self.directory
        class Copy:
            def detach(self):
                return self
            def cpu(self):
                (directory / "FAULT.json").write_text("{}")
                return object()
        self.bad("fault/stop latch", self.b.snapshot, Copy(), "blocked")

    def test_readback_exception_latches(self):
        class Copy:
            def detach(self):
                return self
            def cpu(self):
                raise RuntimeError("copy failure")
        self.bad("readback failed", self.b.snapshot, Copy(), "blocked")

    def test_failed_boundary_never_resumes(self):
        self.b.failed = True
        with self.assertRaisesRegex(boundary.BoundaryError, "already failed"):
            self.b.stage("again")
        self.assertEqual(self.syncs, 0)

    def test_boundary_failure_stops_other_rank_before_sync(self):
        self.bad("intentional invalid index", self.b.require, False, "intentional invalid index")
        self.assertTrue((self.directory / "STOP").is_file())
        other = boundary.Boundary(self.directory / "receipts", self.watcher, 1, "cpu", self.sync, cpu_test=True)
        with self.assertRaisesRegex(boundary.BoundaryError, "fault/stop latch"):
            other.stage("other_rank")
        self.assertEqual(self.syncs, 0)
        self.assertTrue(other.failed)

    def test_existing_stop_reason_is_preserved(self):
        stop = self.directory / "STOP"
        stop.write_text("watcher original fault\n")
        self.bad("fault/stop latch", self.b.stage, "blocked")
        self.assertEqual(stop.read_text(), "watcher original fault\n")

    def test_enable_default_off_and_invalid_refusal(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(boundary.enabled())
        with patch.dict(os.environ, {boundary.ENABLE: "yes"}):
            with self.assertRaisesRegex(boundary.BoundaryError, "must be 0 or 1"):
                boundary.enabled()

    def test_actual_alignment_wrapper_on_off_and_original_identical(self):
        topk = torch.tensor([[0, 128], [1, 129]], dtype=torch.int32, device="cpu")
        mapping = torch.full((512,), -1, dtype=torch.int32, device="cpu")
        mapping[:128] = torch.arange(128, device="cpu")
        calls = []
        def native(ids, E, block, ordered, experts, padded, expert_map):
            calls.append(True)
            routes = ids.flatten().tolist()
            order, raw = [], []
            for e in range(E):
                tokens = [i for i, x in enumerate(routes) if x == e]
                if tokens:
                    count = (len(tokens) + block - 1) // block * block
                    order.extend(tokens + [len(routes)] * (count - len(tokens)))
                    raw.extend([e] * (count // block))
            ordered.fill_(len(routes))
            experts.zero_()
            ordered[:len(order)] = torch.tensor(order, dtype=torch.int32, device="cpu")
            experts[:len(raw)] = torch.tensor(raw, dtype=torch.int32, device="cpu")
            padded.fill_(len(order))
        outputs = []
        for source, on in [(HERE / "base-runtime/vllm" / MOE / "moe_align_block_size.py", False),
                           (COPY / MOE / "moe_align_block_size.py", False),
                           (COPY / MOE / "moe_align_block_size.py", True)]:
            namespace = dict(torch=torch, ops=types.SimpleNamespace(moe_align_block_size=native),
                             triton=types.SimpleNamespace(cdiv=lambda a, b: (a+b-1)//b),
                             round_up=lambda a, b: (a+b-1)//b*b, _moe_boundary=boundary)
            fn = extract(source, "moe_align_block_size", namespace)
            with patch.dict(os.environ, {boundary.ENABLE: str(int(on))}), patch.object(boundary, "get", return_value=self.b) as get:
                outputs.append(fn(topk, 2, 512, mapping))
                self.assertEqual(get.call_count, int(on))
        for output in outputs[1:]:
            for actual, reference in zip(output, outputs[0]):
                self.assertTrue(torch.equal(actual.view(torch.uint8), reference.view(torch.uint8)))
        self.assertEqual(len(calls), 3)

    def test_actual_gemm_wrapper_on_off_and_original_bit_identical(self):
        args = self.gemm_args()
        launches = []
        class CPUDispatch:
            def __getitem__(dispatch, grid):
                def launch(*pos, **kw):
                    launches.append(kw)
                    A, B, table, C, bias, AS, BS, routes, ordered, experts, padded = pos[:11]
                    C.fill_(float("nan"))
                    output = C.reshape(-1, B.shape[1])
                    for index in range(padded.item()):
                        token = int(ordered[index])
                        if token >= output.shape[0]:
                            continue
                        expert = int(experts[index // kw["BLOCK_SIZE_M"]])
                        if expert == -1:
                            output[token].zero_()
                        else:
                            kind, physical = B._q38_row_map[expert]
                            row = B[physical] if kind == "resident" else B._q38_host_cpu[physical]
                            output[token] = torch.mv(row, A[token // kw["top_k"]])
                return launch
        outputs = []
        for source, on in [(BASE / MOE / "fused_moe.py", False),
                           (COPY / MOE / "fused_moe.py", False),
                           (COPY / MOE / "fused_moe.py", True)]:
            namespace = dict(torch=torch, _moe_boundary=boundary, enable_swap_ab=lambda *a: False,
                             warn_if_moe_use_td_ineffective=lambda *a, **kw: None, resolve_moe_use_td=lambda: False,
                             triton=types.SimpleNamespace(cdiv=lambda a, b: (a+b-1)//b), fused_moe_kernel=CPUDispatch())
            fn = extract(source, "invoke_fused_moe_triton_kernel", namespace)
            C = torch.empty_like(args["C"], device="cpu")
            with patch.dict(os.environ, {boundary.ENABLE: str(int(on))}), patch.object(boundary, "get", return_value=self.b) as get:
                fn(args["A"], args["B"], C, args["A_scale"], args["B_scale"], None,
                   args["sorted_ids"], args["local_ids"], args["padded"], False, 2, args["config"],
                   None, True, False, False, False, False, [128, 128], None)
                self.assertEqual(get.call_count, int(on))
            outputs.append(C)
        self.assertTrue(torch.equal(outputs[0].view(torch.uint8), outputs[1].view(torch.uint8)))
        self.assertTrue(torch.equal(outputs[0].view(torch.uint8), outputs[2].view(torch.uint8)))
        self.assertTrue(torch.equal(outputs[2][:, 1], torch.zeros_like(outputs[2][:, 1])))
        self.assertFalse(launches[1]["DIAGNOSTIC_BOUNDARY"])
        self.assertTrue(launches[2]["DIAGNOSTIC_BOUNDARY"])
        self.assertIn("gemm.complete.sync_complete", [x["phase"] for x in self.rows()])

    def test_actual_experts_apply_on_off_and_original_identical(self):
        # Exercise the actual TritonExperts.apply hook with CPU operator doubles.
        # Native dispatch and quantization parity are deliberately out of scope.
        ids = torch.tensor([[0, 128], [1, 129]], dtype=torch.int32, device="cpu")
        mapping = torch.full((512,), -1, dtype=torch.int32, device="cpu")
        mapping[:128] = torch.arange(128, device="cpu")
        weights = torch.full((2, 2), 0.5, device="cpu")
        hidden = torch.arange(32, dtype=torch.float32, device="cpu").reshape(2, 16)
        w1, w2 = self.weight(), self.weight()
        quant = types.SimpleNamespace(use_int4_w4a16=False, use_int8_w8a16=False,
            use_fp8_w8a8=True, use_int8_w8a8=False, config_name=lambda dtype: "fixture")
        receiver = types.SimpleNamespace(quant_config=quant, expects_unquantized_inputs=False,
            moe_problem_size=lambda *args: (128, 2, 16, 16, 2),
            block_shape=[128, 128], adjust_N_for_activation=lambda n, a: n,
            _lora_context=None, quantization_emulation=False, a1_scale=None,
            w1_scale=torch.ones((128, 1, 1), device="cpu"),
            w2_scale=torch.ones((128, 1, 1), device="cpu"), w1_bias=None, w2_bias=None,
            per_act_token_quant=False, quant_dtype=torch.float32,
            activation=lambda a, out, src: out.copy_(src),
            moe_sum=lambda src, out: out.copy_(src.sum(dim=1)))
        assignment_calls = []
        def assignment(*args, **kwargs):
            assignment_calls.append(True)
            return (torch.tensor([0, 4, 2, 4, 1, 4, 3, 4], dtype=torch.int32, device="cpu"),
                    torch.tensor([0, 1, -1, -1], dtype=torch.int32, device="cpu"),
                    torch.tensor([8], dtype=torch.int32, device="cpu"))
        def gemm(A, B, C, AS, BS, route_weights, ordered, experts, padded, mul, topk, *args, **kwargs):
            flat = C.reshape(-1, 16)
            for i, global_id in enumerate(ids.flatten().tolist()):
                if global_id >= 128:
                    flat[i].zero_()
                else:
                    flat[i] = torch.mv(B[global_id], A[i // topk])
                    if mul:
                        flat[i] *= route_weights.flatten()[i]
        outputs = []
        for source, on in [(BASE / MOE / "experts/triton_moe.py", False),
                           (COPY / MOE / "experts/triton_moe.py", False),
                           (COPY / MOE / "experts/triton_moe.py", True)]:
            namespace = dict(torch=torch, _moe_boundary=boundary,
                tl=types.SimpleNamespace(float32="float32", float16="float16", bfloat16="bfloat16"),
                try_get_optimal_moe_config=lambda *args, **kw: dict(BLOCK_SIZE_M=2),
                _resize_cache=lambda tensor, shape: tensor.flatten()[:math.prod(shape)].view(shape),
                _prepare_expert_assignment=assignment, invoke_fused_moe_triton_kernel=gemm,
                MoEActivation=types.SimpleNamespace(SILU="silu"),
                moe_kernel_quantize_input=lambda tensor, *args, **kw: (tensor, torch.ones((4, 1), device="cpu")))
            fn = extract(source, "apply", namespace)
            output = torch.empty((2, 16), device="cpu")
            with patch.dict(os.environ, {boundary.ENABLE: str(int(on))}), patch.object(boundary, "get", return_value=self.b) as get:
                fn(receiver, output, hidden, w1, w2, weights, ids, "identity", 512, mapping,
                   torch.ones((2, 1), device="cpu"), None,
                   torch.empty(64, device="cpu"), torch.empty(64, device="cpu"), None, False)
                self.assertEqual(get.call_count, int(on))
            outputs.append(output)
        self.assertEqual(len(assignment_calls), 3)
        for output in outputs[1:]:
            self.assertTrue(torch.equal(output.view(torch.uint8), outputs[0].view(torch.uint8)))
        self.assertIn("experts.entry.sync_complete", [r["phase"] for r in self.rows()])

    def test_actual_modular_allocator_on_off_and_original_identical(self):
        def shapes(M, N, K, topk, *unused):
            return (M, topk, max(N//2, K)), (M, topk, max(N, K)), (M, K)
        experts = types.SimpleNamespace(workspace_dtype=lambda dtype: dtype,
                                        workspace_shapes=shapes,
                                        adjust_N_for_activation=lambda N, activation: N//2)
        receiver = types.SimpleNamespace(fused_experts=experts)
        def simultaneous(*descriptions):
            return tuple(torch.arange(math.prod(shape), dtype=dtype, device="cpu").reshape(shape)
                         for shape, dtype in descriptions)
        outputs = []
        for source, on in [(BASE / MOE / "modular_kernel.py", False),
                           (COPY / MOE / "modular_kernel.py", False),
                           (COPY / MOE / "modular_kernel.py", True)]:
            namespace = dict(torch=torch, prod=math.prod, _moe_boundary=boundary,
                             current_platform=types.SimpleNamespace(is_cpu=lambda: False),
                             current_workspace_manager=lambda: types.SimpleNamespace(get_simultaneous=simultaneous),
                             _resize_cache=lambda tensor, shape: tensor.flatten()[:math.prod(shape)].view(shape))
            fn = extract(source, "_allocate_buffers", namespace)
            with patch.dict(os.environ, {boundary.ENABLE: str(int(on))}), patch.object(boundary, "get", return_value=self.b) as get:
                result = fn(receiver, torch.float32, torch.device("cpu"), 2, 2, 16, 16, 2, 512, 128, None, None)
                self.assertEqual(get.call_count, int(on))
            self.assertEqual(result[0].data_ptr(), result[2].data_ptr())
            self.assertFalse(boundary.overlaps(boundary.span(result[0]), boundary.span(result[1])))
            outputs.append(result)
        for actual in outputs[1:]:
            for tensor, expected in zip(actual, outputs[0]):
                self.assertTrue(torch.equal(tensor.view(torch.uint8), expected.view(torch.uint8)))
        self.assertIn("workspace.pass", [x["phase"] for x in self.rows()])


def install_cases():
    routers = {
        "global_count": (lambda a: a.update(global_experts=128), "unsupported alignment geometry/filter"),
        "block": (lambda a: a.update(block=0), "unsupported alignment geometry/filter"),
        "ignore_nonlocal": (lambda a: a.update(ignore_invalid=True), "unsupported alignment geometry/filter"),
        "negative_id": (lambda a: a["topk"].__setitem__((0, 0), -1), "router IDs outside"),
        "upper_id": (lambda a: a["topk"].__setitem__((0, 0), 512), "router IDs outside"),
        "id_dtype": (lambda a: a.update(topk=a["topk"].float()), "router ID dtype/shape"),
        "id_shape": (lambda a: a.update(topk=a["topk"].reshape(-1)), "router ID dtype/shape"),
        "id_stride": (lambda a: a.update(topk=torch.tensor([[0, 0, 128, 0]], dtype=torch.int32, device="cpu")[:, ::2]), "router ID dtype/shape/layout"),
        "missing_map": (lambda a: a.update(expert_map=None), "TP4 expert map required"),
        "map_dtype": (lambda a: a.update(expert_map=a["expert_map"].float()), "expert map dtype/layout"),
        "map_shape": (lambda a: a.update(expert_map=a["expert_map"][:128]), "expert map dtype/layout"),
        "map_owner": (lambda a: a["expert_map"].__setitem__(128, 0), "rank expert map ownership/coverage"),
    }
    for name, (change, message) in routers.items():
        def test(self, change=change, message=message):
            mapping = torch.full((512,), -1, dtype=torch.int32, device="cpu")
            mapping[:128] = torch.arange(128, device="cpu")
            args = dict(topk=torch.tensor([[0, 128]], dtype=torch.int32, device="cpu"),
                        expert_map=mapping, block=2, global_experts=512)
            change(args)
            self.bad(message, self.b.router, **args)
        setattr(BoundaryTests, "test_router_"+name, test)
    watcher_cases = {
        "failed": {"passed": False}, "wrong_boot": {"boot_id": "other"},
        "fault_lines": {"new_fault_lines": ["fault"]}, "stale": {"updated_unix": 0},
        "stale_read": {"read_started_unix": 0}, "future": {"updated_unix": time.time()+1000},
    }
    for name, change in watcher_cases.items():
        def test(self, change=change):
            self.refresh(**change)
            self.bad("watcher/fault latch", self.b.stage, "blocked")
            self.assertEqual(self.syncs, 0)
        setattr(BoundaryTests, "test_watcher_"+name, test)
    for marker in ("STOP", "FAULT", "FAULT.json"):
        def test(self, marker=marker):
            (self.directory / marker).write_text("fault")
            self.bad("fault/stop latch", self.b.stage, "blocked")
            self.assertEqual(self.syncs, 0)
        setattr(BoundaryTests, "test_latch_"+marker.replace(".", "_"), test)
    cases = {
        "raw_tail": (lambda s,o,r,p: r.__setitem__(-1, 512), "raw alignment IDs outside"),
        "raw_negative": (lambda s,o,r,p: r.__setitem__(0, -1), "raw alignment IDs outside"),
        "padded_negative": (lambda s,o,r,p: p.fill_(-2), "padded layout capacity/divisibility"),
        "padded_too_large": (lambda s,o,r,p: p.fill_(10), "padded layout capacity/divisibility"),
        "padded_unaligned": (lambda s,o,r,p: p.fill_(7), "padded layout capacity/divisibility"),
        "padded_wrong_count": (lambda s,o,r,p: p.fill_(6), "padded counts inconsistent"),
        "sort_negative": (lambda s,o,r,p: o.__setitem__(0, -1), "sorted route index/padding"),
        "sort_too_large": (lambda s,o,r,p: o.__setitem__(0, 5), "sorted route index/padding"),
        "sort_duplicate": (lambda s,o,r,p: o.__setitem__(2, 0), "sorted routes missing/duplicate"),
        "wrong_expert": (lambda s,o,r,p: r.__setitem__(0, 2), "sorted route assigned to wrong expert"),
    }
    for name, (change, message) in cases.items():
        def test(self, change=change, message=message):
            state, ordered, raw, padded, _ = self.routing()
            change(state, ordered, raw, padded)
            self.bad(message, self.b.raw_alignment, state, ordered, raw, padded)
        setattr(BoundaryTests, "test_alignment_"+name, test)
    weights = {
        "table_missing": (lambda w: delattr(w, "_q38_base_table"), "compact weight missing base-table"),
        "logical_count": (lambda w: setattr(w, "_q38_num_experts", 127), "compact logical expert count"),
        "wrong_owner": (lambda w: setattr(w, "_screen1b_boundary_owner", (os.getpid()+1, 0, "cpu")), "allocation owner mismatch"),
        "table_dtype": (lambda w: setattr(w, "_q38_base_table", w._q38_base_table.int()), "base table dtype/length/layout"),
        "table_length": (lambda w: setattr(w, "_q38_base_table", w._q38_base_table[:127]), "base table dtype/length/layout"),
        "owner_missing": (lambda w: delattr(w, "_q38_host_cpu"), "compact retained owners missing"),
        "alias_geometry": (lambda w: setattr(w, "_q38_host_storage", w._q38_host_storage[:, :8]), "host alias geometry mismatch"),
        "alias_address": (lambda w: setattr(w, "_q38_host_storage", w._q38_host_storage.clone()), "host alias address differs"),
        "logical_partition": (lambda w: w._q38_row_map.pop(0), "row-map logical coverage"),
        "physical_partition": (lambda w: w._q38_row_map.__setitem__(1, ("resident", 0)), "row-map physical partition"),
        "row_wrong": (lambda w: w._q38_base_table.__setitem__(1, 0), "weight row outside owned span or wrong row"),
        "row_outside": (lambda w: w._q38_base_table.__setitem__(0, 1 << 40), "weight row outside owned span or wrong row"),
        "row_unaligned": (lambda w: w._q38_base_table.__setitem__(0, 1), "weight row outside owned span or wrong row"),
    }
    for name, (change, message) in weights.items():
        def test(self, change=change, message=message):
            weight = self.weight()
            change(weight)
            self.bad(message, self.b.weights, weight)
        setattr(BoundaryTests, "test_weight_"+name, test)
    gemms = {
        "producer": (lambda a: a.update(local_ids=a["local_ids"].clone()), "alignment producer identity mismatch"),
        "mutated_ids": (lambda a: a["local_ids"].__setitem__(0, 1), "alignment mutated before GEMM"),
        "mutated_count": (lambda a: a["padded"].fill_(6), "alignment mutated before GEMM"),
        "mutated_sort": (lambda a: a["sorted_ids"].__setitem__(0, 1), "alignment mutated before GEMM"),
        "block": (lambda a: a["config"].update(BLOCK_SIZE_M=4), "GEMM config mismatch"),
        "scale_missing": (lambda a: a.update(A_scale=None), "FP8 scale/bias contract"),
        "bias": (lambda a: a.update(bias=torch.zeros(16, device="cpu")), "FP8 scale/bias contract"),
        "scale_capacity": (lambda a: a.update(B_scale=a["B_scale"][:127]), "FP8 scale capacity/layout"),
        "route_weights": (lambda a: a.update(mul_weight=True), "route weight capacity/layout"),
        "C_capacity": (lambda a: a.update(C=a["C"][:1]), "GEMM A/C capacity"),
        "C_same_numel_wrong_geometry": (lambda a: a.update(C=a["C"].view(1, 8, 8)), "GEMM A/C capacity"),
    }
    for name, (change, message) in gemms.items():
        def test(self, change=change, message=message):
            args = self.gemm_args()
            change(args)
            self.bad(message, self.b.before_gemm, **args)
        setattr(BoundaryTests, "test_gemm_"+name, test)


install_cases()

if __name__ == "__main__":
    unittest.main()
