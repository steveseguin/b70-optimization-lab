#!/usr/bin/env python3
"""Qualify a warmed oneDNN->Triton M1 cluster for fixed-address graph replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from option4_decoder import (  # noqa: E402
    FixedAddressCommandGraph,
    compare_tensor_bits,
)


M = 1
K = 1024
N = 8192
HEADS = 16
HEAD_DIM = 512
BLOCK_SIZE = 64
NUM_CACHE_BLOCKS = 2
CACHE_ROW_BYTES = BLOCK_SIZE * (576 + 8)
# Production K160 M1 cache is a layer view with shape [2761, 64, 584]
# and stride [1039680, 584, 1], not a compact benchmark allocation.
CACHE_BLOCK_STRIDE = 1_039_680
GUARD_BYTES = 4096
MAX_POSITION = 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def control(unitrace: Path, action: str, session: str) -> dict[str, Any]:
    started_ns = time.monotonic_ns()
    proc = subprocess.run(
        [str(unitrace), f"--{action}", session],
        check=False,
        capture_output=True,
        text=True,
    )
    ended_ns = time.monotonic_ns()
    if proc.returncode != 0:
        raise RuntimeError(
            f"unitrace --{action} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return {
        "action": action,
        "started_monotonic_ns": started_ns,
        "ended_monotonic_ns": ended_ns,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def protected_process(pid: int | None) -> dict[str, Any] | None:
    if pid is None:
        return None
    proc = Path(f"/proc/{pid}")
    render_nodes: list[str] = []
    if proc.exists():
        fd_dir = proc / "fd"
        try:
            for entry in fd_dir.iterdir():
                try:
                    target = str(entry.resolve())
                except FileNotFoundError:
                    continue
                if "/dev/dri/renderD" in target:
                    render_nodes.append(target)
        except PermissionError:
            pass
    return {
        "pid": pid,
        "alive": proc.exists(),
        "render_nodes": sorted(set(render_nodes)),
    }


def make_cache(device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    payload_bytes = (NUM_CACHE_BLOCKS - 1) * CACHE_BLOCK_STRIDE + CACHE_ROW_BYTES
    storage = torch.full(
        (payload_bytes + 2 * GUARD_BYTES,),
        0xA5,
        dtype=torch.uint8,
        device=device,
    )
    payload = storage[GUARD_BYTES : GUARD_BYTES + payload_bytes].as_strided(
        (NUM_CACHE_BLOCKS, BLOCK_SIZE, 584),
        (CACHE_BLOCK_STRIDE, 584, 1),
    )
    payload.zero_()
    return storage, payload


def changed_values(
    seed: int, device: torch.device
) -> tuple[torch.Tensor, torch.Tensor, int, int]:
    torch.manual_seed(seed)
    x = torch.randn((M, K), device=device, dtype=torch.bfloat16) * (
        0.03125 * (1 + seed % 7)
    )
    kv = torch.randn((M, HEAD_DIM), device=device, dtype=torch.bfloat16) * (
        0.0625 * (1 + seed % 5)
    )
    position = 11 + (seed * 37) % (MAX_POSITION - 11)
    slot = (seed * 29 + 7) % (NUM_CACHE_BLOCKS * BLOCK_SIZE)
    return x, kv, position, slot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("eager", "graph", "raw-lz"), required=True
    )
    parser.add_argument("--parity-cases", type=int, default=40)
    parser.add_argument("--warmups", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260720)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--unitrace", type=Path)
    parser.add_argument("--session")
    parser.add_argument("--protected-pid", type=int)
    parser.add_argument("--native-build-dir", type=Path)
    parser.add_argument("--overhead-replays", type=int, default=100)
    parser.add_argument(
        "--nested",
        action="store_true",
        help="Capture an already-built inner mixed graph into a surrounding graph.",
    )
    parser.add_argument(
        "--trace-completion",
        action="store_true",
        help="Keep tracing enabled through synchronize for a supporting device timeline.",
    )
    args = parser.parse_args()

    if (args.unitrace is None) != (args.session is None):
        parser.error("--unitrace and --session must be supplied together")
    if os.environ.get("VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT") != "1":
        raise RuntimeError("the promoted fused Triton selector must be explicitly 1")
    if os.environ.get("ZE_AFFINITY_MASK") is None:
        raise RuntimeError("ZE_AFFINITY_MASK must explicitly select the verified free card")
    if args.mode == "raw-lz" and args.native_build_dir is None:
        raise RuntimeError("--mode raw-lz requires --native-build-dir")
    if args.mode == "raw-lz" and os.environ.get("ZE_ENABLE_TRACING_LAYER") != "1":
        raise RuntimeError("--mode raw-lz requires ZE_ENABLE_TRACING_LAYER=1")
    if args.mode == "raw-lz" and args.nested:
        raise RuntimeError("--nested is not part of the raw Level Zero Phase 0b gate")
    if args.overhead_replays < 0:
        raise ValueError("--overhead-replays must be non-negative")

    protected_before = protected_process(args.protected_pid)
    if protected_before is not None and not protected_before["alive"]:
        raise RuntimeError(f"protected PID {args.protected_pid} was not alive at start")

    from vllm.platforms import current_platform

    current_platform.import_kernels()
    from vllm.models.deepseek_v4.xpu.xpu_qnorm_rope_kv_fp8_insert import (
        xpu_qnorm_rope_kv_fp8_insert_fused,
    )
    import triton
    import vllm
    import vllm_xpu_kernels
    import vllm_xpu_kernels._xpu_C as xpu_extension

    native_module = None
    if args.native_build_dir is not None:
        from option4_decoder.native import load_native_replay

        native_module = load_native_replay(args.native_build_dir)

    device = torch.device("xpu:0")
    torch.xpu.set_device(device)
    torch.manual_seed(args.seed)

    x = torch.empty((M, K), device=device, dtype=torch.bfloat16)
    kv = torch.empty((M, HEAD_DIM), device=device, dtype=torch.bfloat16)
    positions = torch.empty((M,), device=device, dtype=torch.int64)
    slots = torch.empty((M,), device=device, dtype=torch.int64)
    cache_storage, cache = make_cache(device)

    weight = (
        torch.randn((N, K), device=device, dtype=torch.bfloat16) * 0.1
    ).to(torch.float8_e4m3fn)
    k_blocks = torch.arange(K // 128, device=device)[:, None]
    n_blocks = torch.arange(N // 128, device=device)[None, :]
    weight_scale = torch.pow(
        2.0, ((k_blocks + 2 * n_blocks) % 7 - 3).to(torch.float32)
    ).contiguous()
    # The promoted M1 path passes rotary_emb.cos_sin_cache directly. Its real
    # specialization is FP32; using BF16 here produces a different Triton ABI.
    cos_sin = torch.randn(
        (MAX_POSITION, 64), device=device, dtype=torch.float32
    ) * 0.125

    def launch_with(
        src: torch.Tensor,
        kv_src: torch.Tensor,
        cache_dst: torch.Tensor,
        pos: torch.Tensor,
        slot: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        q = torch.ops._xpu_C.fp8_gemm_w8a16(
            src, weight.t(), weight_scale, None
        ).view(M, HEADS, HEAD_DIM)
        xpu_qnorm_rope_kv_fp8_insert_fused(
            q,
            kv_src,
            cache_dst,
            slot,
            pos,
            cos_sin,
            1e-6,
            BLOCK_SIZE,
        )
        return {"q": q, "kv_cache": cache_dst}

    def static_launch() -> dict[str, torch.Tensor]:
        return launch_with(x, kv, cache, positions, slots)

    initial_x, initial_kv, initial_pos, initial_slot = changed_values(
        args.seed + 1, device
    )
    x.copy_(initial_x)
    kv.copy_(initial_kv)
    positions.fill_(initial_pos)
    slots.fill_(initial_slot)
    cache.zero_()

    graph: FixedAddressCommandGraph | None = None
    inner_graph: FixedAddressCommandGraph | None = None
    graph_outputs: dict[str, torch.Tensor] = {}
    raw_lz_handles: tuple[int, int] | None = None
    raw_lz_harvest_appends: int | None = None
    raw_lz_handle_state: dict[str, tuple[int, int]] = {}

    def replay_raw_lz(executable_address: int) -> None:
        handles = raw_lz_handle_state.get("handles")
        if handles is None:
            raise AssertionError("raw Level Zero handles were not harvested")
        native_module.replay_raw_level_zero(*handles)

    if args.mode in {"graph", "raw-lz"}:
        graph = FixedAddressCommandGraph(
            static_launch,
            {
                "input": x,
                "weight": weight,
                "weight_scale": weight_scale,
                "kv": kv,
                "positions": positions,
                "slots": slots,
                "cos_sin": cos_sin,
                "kv_cache": cache,
                "kv_cache_storage": cache_storage,
            },
            native_replay=(
                replay_raw_lz
                if args.mode == "raw-lz"
                else (
                    None
                    if native_module is None
                    else native_module.replay_current_queue
                )
            ),
        )
        graph.warm(args.warmups)
        graph_outputs = dict(graph.build())
        if args.mode == "raw-lz":
            harvested = tuple(
                int(value)
                for value in native_module.harvest_raw_level_zero_handles(
                    graph.graph_exec
                )
            )
            raw_lz_handles = harvested[:2]
            raw_lz_harvest_appends = harvested[2]
            raw_lz_handle_state["handles"] = raw_lz_handles
            # The sacrificial ordinary SYCL replay and its host synchronization
            # are build-time only and remain outside parity, overhead, and PTI
            # verdict windows.
            torch.xpu.synchronize()
        if args.nested:
            if native_module is None:
                raise RuntimeError("--nested requires --native-build-dir")
            inner_graph = graph

            def nested_launch() -> dict[str, torch.Tensor]:
                native_module.replay_current_queue(inner_graph.graph_exec)
                return dict(inner_graph.outputs)

            graph = FixedAddressCommandGraph(
                nested_launch,
                {
                    "input": x,
                    "weight": weight,
                    "weight_scale": weight_scale,
                    "kv": kv,
                    "positions": positions,
                    "slots": slots,
                    "cos_sin": cos_sin,
                    "kv_cache": cache,
                    "kv_cache_storage": cache_storage,
                },
                native_replay=native_module.replay_current_queue,
            )
            graph.warm(args.warmups)
            graph_outputs = dict(graph.build())
    else:
        for _ in range(args.warmups):
            static_launch()
        torch.xpu.synchronize()

    parity_rows: list[dict[str, Any]] = []
    if graph is not None:
        for case in range(args.parity_cases):
            case_seed = args.seed + 100 + case
            changed_x, changed_kv, changed_pos, changed_slot = changed_values(
                case_seed, device
            )
            ref_storage, ref_cache = make_cache(device)
            ref_pos = torch.tensor([changed_pos], device=device, dtype=torch.int64)
            ref_slot = torch.tensor([changed_slot], device=device, dtype=torch.int64)
            reference = launch_with(
                changed_x, changed_kv, ref_cache, ref_pos, ref_slot
            )
            reference_q = reference["q"].clone()
            torch.xpu.synchronize()

            x.copy_(changed_x)
            kv.copy_(changed_kv)
            positions.fill_(changed_pos)
            slots.fill_(changed_slot)
            cache.zero_()
            graph.replay()
            torch.xpu.synchronize()

            reports = [
                compare_tensor_bits("q", graph_outputs["q"], reference_q),
                compare_tensor_bits("kv_cache", cache, ref_cache),
                compare_tensor_bits("cache_guard", cache_storage, ref_storage),
            ]
            parity_rows.append(
                {
                    "case": case,
                    "seed": case_seed,
                    "position": changed_pos,
                    "slot": changed_slot,
                    "reports": [report.to_dict() for report in reports],
                    "exact": all(report.exact for report in reports),
                }
            )
        if not all(row["exact"] for row in parity_rows):
            raise RuntimeError("fixed-address changed-input graph parity failed")
        graph.mark_parity_qualified(
            exact=all(row["exact"] for row in parity_rows)
        )

    overhead_durations_us: list[float] = []
    if graph is not None and args.overhead_replays:
        torch.xpu.synchronize()
        for replay_index in range(args.overhead_replays):
            # Model the real decoder boundary: device-side input preparation is
            # pending when replay is submitted. Raw append must preserve this
            # dependency on the same in-order immediate list without waiting on
            # the host.
            positions.fill_(11 + replay_index % (MAX_POSITION - 11))
            slots.fill_(replay_index % (NUM_CACHE_BLOCKS * BLOCK_SIZE))
            started_ns = time.monotonic_ns()
            graph.replay()
            ended_ns = time.monotonic_ns()
            overhead_durations_us.append((ended_ns - started_ns) / 1000.0)
            # A regular command list is never re-appended while its preceding
            # execution may still be in flight. This wait is excluded from the
            # recorded enqueue duration.
            torch.xpu.synchronize()

    trace_seed = args.seed + 10000
    trace_x, trace_kv, trace_pos, trace_slot = changed_values(trace_seed, device)
    ref_storage, ref_cache = make_cache(device)
    ref_pos = torch.tensor([trace_pos], device=device, dtype=torch.int64)
    ref_slot = torch.tensor([trace_slot], device=device, dtype=torch.int64)
    trace_reference = launch_with(
        trace_x, trace_kv, ref_cache, ref_pos, ref_slot
    )
    trace_reference_q = trace_reference["q"].clone()
    torch.xpu.synchronize()

    x.copy_(trace_x)
    kv.copy_(trace_kv)
    positions.fill_(trace_pos)
    slots.fill_(trace_slot)
    cache.zero_()
    torch.xpu.synchronize()

    controls: list[dict[str, Any]] = []
    if args.unitrace is not None and args.session is not None:
        controls.append(control(args.unitrace, "resume", args.session))
    trace_started_ns = time.monotonic_ns()
    if graph is not None:
        traced_outputs = dict(graph.replay())
    else:
        traced_outputs = static_launch()
    trace_ended_ns = time.monotonic_ns()
    if args.trace_completion:
        torch.xpu.synchronize()
    if args.unitrace is not None and args.session is not None:
        controls.append(control(args.unitrace, "pause", args.session))
    # The verdict window measures enqueue/submission structure only. Completion
    # is required for parity, but placing this explicit validation wait inside
    # the window would misclassify torch.xpu.synchronize() bookkeeping as a
    # graph-internal host synchronization.
    if not args.trace_completion:
        torch.xpu.synchronize()

    trace_reports = [
        compare_tensor_bits("q", traced_outputs["q"], trace_reference_q),
        compare_tensor_bits("kv_cache", cache, ref_cache),
        compare_tensor_bits("cache_guard", cache_storage, ref_storage),
    ]
    trace_exact = all(report.exact for report in trace_reports)

    if args.unitrace is not None and args.session is not None:
        controls.append(control(args.unitrace, "stop", args.session))

    protected_after = protected_process(args.protected_pid)
    protected_untouched = (
        protected_before is None
        or (
            protected_after is not None
            and protected_before["alive"]
            and protected_after["alive"]
            and protected_before["render_nodes"] == protected_after["render_nodes"]
        )
    )

    vllm_path = Path(vllm.__file__).resolve()
    kernels_path = Path(vllm_xpu_kernels.__file__).resolve()
    extension_path = Path(xpu_extension.__file__).resolve()
    qnorm_source = (
        vllm_path.parent
        / "models/deepseek_v4/xpu/xpu_qnorm_rope_kv_fp8_insert.py"
    )
    result = {
        "schema_version": 1,
        "classification": (
            "option4_phase0b_raw_level_zero_mixed_cluster"
            if args.mode == "raw-lz"
            else "option4_phase0_mixed_onednn_triton_command_graph"
        ),
        "mode": args.mode,
        "nested_surrounding_capture": args.nested,
        "verdict_inputs": {
            "bitwise_exact": trace_exact
            and all(row["exact"] for row in parity_rows),
            "submit_count_pending_trace_summary": args.unitrace is not None,
        },
        "gpu": {
            "ze_affinity_mask": os.environ["ZE_AFFINITY_MASK"],
            "visible_torch_device": "xpu:0",
            "name": torch.xpu.get_device_name(device),
            "current_sycl_queue": int(torch.xpu.current_stream().sycl_queue),
        },
        "protected_process": {
            "before": protected_before,
            "after": protected_after,
            "untouched": protected_untouched,
        },
        "runtime": {
            "torch": torch.__version__,
            "triton": triton.__version__,
            "vllm_module": str(vllm_path),
            "vllm_xpu_kernels_module": str(kernels_path),
            "xpu_extension": str(extension_path),
            "xpu_extension_sha256": sha256_file(extension_path),
            "qnorm_source": str(qnorm_source),
            "qnorm_source_sha256": sha256_file(qnorm_source),
        },
        "cluster": {
            "onednn": {
                "op": "torch.ops._xpu_C.fp8_gemm_w8a16",
                "logical_projection": "DeepSeek V4 M1 wq_b",
                "m": M,
                "n": N,
                "k": K,
                "src_dtype": "bfloat16",
                "weight_dtype": "float8_e4m3fn",
                "weight_scale_shape": list(weight_scale.shape),
                "weight_scale_dtype": str(weight_scale.dtype),
            },
            "triton": {
                "callable": "xpu_qnorm_rope_kv_fp8_insert_fused",
                "kernel": "_xpu_qnorm_rope_fp8_insert_kernel",
                "q_shape": [M, HEADS, HEAD_DIM],
                "grid": [M, HEADS + 1],
                "num_warps": 4,
                "cache_block_size": BLOCK_SIZE,
                "cache_shape": list(cache.shape),
                "cache_stride": list(cache.stride()),
                "cos_sin_dtype": str(cos_sin.dtype),
            },
            "dependency": "oneDNN wq_b output is the in-place Triton q input",
        },
        "graph": None
        if graph is None
        else {
            "state": graph.state.name,
            "queue_identity": graph.queue_identity,
            "native_queue_object_address": (
                None
                if native_module is None
                else int(native_module.current_queue_object_address())
            ),
            "native_replay": native_module is not None,
            "replay_backend": (
                "raw_level_zero_regular_list_on_owned_immediate_list"
                if args.mode == "raw-lz"
                else (
                    "native_sycl_ext_oneapi_graph"
                    if native_module is not None
                    else "torch_xpugraph_replay"
                )
            ),
            "raw_level_zero": None
            if raw_lz_handles is None
            else {
                "owned_immediate_command_list": raw_lz_handles[0],
                "regular_graph_command_list": raw_lz_handles[1],
                "ownership": "borrowed; retained by PyTorch queue and XPUGraph",
                "append_api": "zeCommandListImmediateAppendCommandListsExp",
                "harvest": {
                    "mechanism": "one sacrificial traced SYCL graph replay",
                    "matching_appends": raw_lz_harvest_appends,
                    "outside_verdict_window": True,
                },
            },
            "inner_graph_exec": (
                None if inner_graph is None else inner_graph.graph_exec
            ),
            "graph_exec": graph.graph_exec,
            "fixed_addresses": graph.address_manifest,
        },
        "parity": {
            "changed_input_cases": len(parity_rows),
            "exact_cases": sum(bool(row["exact"]) for row in parity_rows),
            "rows": parity_rows,
            "trace_case": {
                "seed": trace_seed,
                "position": trace_pos,
                "slot": trace_slot,
                "reports": [report.to_dict() for report in trace_reports],
                "exact": trace_exact,
            },
        },
        "trace_window": {
            "started_monotonic_ns": trace_started_ns,
            "ended_monotonic_ns": trace_ended_ns,
            "wall_us": (trace_ended_ns - trace_started_ns) / 1000.0,
            "controls": controls,
        },
        "replay_enqueue_overhead": None
        if not overhead_durations_us
        else {
            "replays": len(overhead_durations_us),
            "median_us": statistics.median(overhead_durations_us),
            "mean_us": statistics.fmean(overhead_durations_us),
            "min_us": min(overhead_durations_us),
            "max_us": max(overhead_durations_us),
            "samples_us": overhead_durations_us,
            "completion_wait_excluded": True,
            "pending_input_enqueues_before_each_replay": 2,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))

    if not trace_exact or not protected_untouched:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
