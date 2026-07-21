#!/usr/bin/env python3
"""Qualify M1AttentionBoundaryV1 as a raw-L0 fixed-address command list."""

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
sys.path.insert(0, str(ROOT / "tools"))

from option4_decoder import FixedAddressCommandGraph, compare_tensor_bits  # noqa: E402
from option4_decoder.native import load_native_replay  # noqa: E402
from phase1_m1_attention_replay import PacketCase, _pack_selected_rows  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def trace_control(unitrace: Path, action: str, session: str) -> dict[str, Any]:
    proc = subprocess.run(
        [str(unitrace), f"--{action}", session],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"unitrace --{action} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return {
        "action": action,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


class Boundary:
    def __init__(self, case: PacketCase) -> None:
        self.case = case
        self.device = case.device
        self.layer = int(case.meta["layer"])
        self.ratio = int(case.meta["compression_ratio"])
        self.rotary_name = f"attn_rotary_cos_sin_cache_c{self.ratio}"
        self.x = case.get("m1_boundary_ingress", "x").clone()
        self.base_x = self.x.clone()
        self.positions = case.get("m1_boundary_ingress", "positions").clone()
        self.residual = (
            None
            if self.layer == 0
            else case.get("m1_boundary_ingress", "residual").clone()
        )
        self.post_in = (
            None
            if self.layer == 0
            else case.get("m1_boundary_ingress", "post_mix").clone()
        )
        self.comb_in = (
            None
            if self.layer == 0
            else case.get("m1_boundary_ingress", "res_mix").clone()
        )
        self.swa_lens = case.get("attn_sparse_bindings", "swa_lens").clone()
        self.swa_valid = int(self.swa_lens.cpu().item())
        swa_raw = case.get("swa_kv_selected", "raw")
        self.swa_cache_initial = _pack_selected_rows(swa_raw, 64)
        self.swa_cache = self.swa_cache_initial.clone()
        swa_width = case.get("attn_sparse_bindings", "swa_indices").shape[-1]
        self.swa_indices = torch.arange(
            swa_width, dtype=torch.int32, device=self.device
        ).view(1, -1)
        self.compact_slot = self.swa_lens.to(torch.int64) - 1

        captured_topk = case.maybe("attn_sparse_bindings", "topk_indices")
        self.topk_lens = case.maybe("attn_sparse_bindings", "topk_lens")
        self.topk_valid = (
            0 if self.topk_lens is None else int(self.topk_lens.cpu().item())
        )
        self.compressed_cache = None
        self.topk_indices = None
        if captured_topk is not None:
            self.compressed_cache = _pack_selected_rows(
                case.get("compressed_kv_selected", "raw"), 16
            )
            self.topk_indices = torch.arange(
                captured_topk.shape[-1], dtype=torch.int32, device=self.device
            ).view(1, -1)

        self.state_cache = None
        self.state_initial = None
        self.state_block = None
        state_before = case.maybe("compressor_state_before", "rows")
        if state_before is not None:
            self.state_block = 4 if self.ratio == 4 else 8
            self.state_cache = torch.zeros(
                (1, self.state_block, state_before.shape[-1]),
                dtype=torch.float32,
                device=self.device,
            )
            self.state_cache[:, :3].copy_(state_before)
            self.state_initial = self.state_cache.clone()
            self.state_slot = torch.ones((1,), dtype=torch.int64, device=self.device)

    def reset(self, changed_case: int = 0) -> None:
        if changed_case:
            # Deterministic BF16 changes that retain the fixed M=1 geometry.
            delta = ((changed_case % 13) - 6) * (2.0**-10)
            self.x.copy_((self.base_x.float() + delta).to(torch.bfloat16))
        else:
            self.x.copy_(self.base_x)
        self.swa_cache.copy_(self.swa_cache_initial)
        if self.state_cache is not None and self.state_initial is not None:
            self.state_cache.copy_(self.state_initial)

    def launch(self) -> dict[str, torch.Tensor]:
        from vllm import _custom_ops as ops
        from vllm.models.deepseek_v4.common.ops.fused_qk_rmsnorm import (
            fused_q_kv_rmsnorm,
        )
        from vllm.models.deepseek_v4.common.ops.save_partial_states import (
            save_partial_states,
        )
        from vllm.models.deepseek_v4.xpu.xpu_qnorm_rope_kv_fp8_insert import (
            xpu_qnorm_rope_kv_fp8_insert_fused,
        )
        from vllm.models.deepseek_v4.xpu.xpu_sparse_decode_fp8 import (
            split_fp8_sparse_attention,
        )
        from vllm.v1.attention.ops.rocm_aiter_mla_sparse import (
            _fused_inverse_rope_gptj,
        )

        case = self.case
        fn = case.get("attn_static_binding", "hc_attn_fn")
        hc_scale = case.get("attn_static_binding", "hc_attn_scale")
        hc_base = case.get("attn_static_binding", "hc_attn_base")
        if self.layer == 0:
            residual_out = self.x
            post = torch.empty((1, 4, 1), dtype=torch.float32, device=self.device)
            comb = torch.empty((1, 4, 4), dtype=torch.float32, device=self.device)
            layer_input = torch.empty(
                (1, 4096), dtype=torch.bfloat16, device=self.device
            )
            torch.ops._xpu_C.mhc_pre_m1_out(
                residual_out,
                fn,
                hc_scale,
                hc_base,
                post,
                comb,
                layer_input,
                1e-6,
                1e-6,
                1e-6,
                2.0,
                20,
            )
        else:
            assert self.residual is not None
            assert self.post_in is not None and self.comb_in is not None
            residual_out = torch.empty_like(self.residual)
            post = torch.empty_like(self.post_in)
            comb = torch.empty_like(self.comb_in)
            layer_input = torch.empty_like(self.x)
            torch.ops._xpu_C.mhc_post_pre_m1_out(
                self.x,
                self.residual,
                self.post_in,
                self.comb_in,
                fn,
                hc_scale,
                hc_base,
                residual_out,
                post,
                comb,
                layer_input,
                1e-6,
                1e-6,
                1e-6,
                2.0,
                20,
            )
        attn_x = torch.empty_like(layer_input)
        ops.rms_norm(
            attn_x,
            layer_input,
            case.get("attn_static_binding", "attn_norm_weight"),
            1e-6,
        )
        qr_kv = torch.ops._xpu_C.fp8_gemm_w8a16(
            attn_x,
            case.get(
                "attn_static_binding", "attn_param::fused_wqa_wkv.weight"
            ).t(),
            case.get(
                "attn_static_binding",
                "attn_param::fused_wqa_wkv.weight_scale_inv",
            ),
            None,
        )
        outputs = {
            "mhc_residual": residual_out,
            "mhc_post": post,
            "mhc_comb": comb,
            "layer_input": layer_input,
            "attn_x": attn_x,
            "qr_kv": qr_kv,
        }
        compressor_weight = case.maybe(
            "attn_static_binding", "attn_param::compressor.fused_wkv_wgate.weight"
        )
        if compressor_weight is not None:
            assert self.state_cache is not None and self.state_block is not None
            kv_score = torch.mm(attn_x, compressor_weight.t(), out_dtype=torch.float32)
            state_width = self.state_cache.shape[-1] // 2
            partial_kv, partial_score = kv_score.split(
                [state_width, state_width], dim=-1
            )
            save_partial_states(
                partial_kv,
                partial_score,
                case.get("attn_static_binding", "attn_param::compressor.ape"),
                self.positions,
                self.state_cache,
                self.state_slot,
                self.state_block,
                state_width,
                self.ratio,
            )
            outputs["kv_score"] = kv_score
            outputs["state_rows"] = self.state_cache[:, :3]
        qr, kv = qr_kv.split([1024, 512], dim=-1)
        qr, kv = fused_q_kv_rmsnorm(
            qr,
            kv,
            case.get("attn_static_binding", "attn_param::q_norm.weight"),
            case.get("attn_static_binding", "attn_param::kv_norm.weight"),
            1e-6,
        )
        q = torch.ops._xpu_C.fp8_gemm_w8a16(
            qr,
            case.get("attn_static_binding", "attn_param::wq_b.weight").t(),
            case.get("attn_static_binding", "attn_param::wq_b.weight_scale_inv"),
            None,
        ).view(1, 16, 512)
        xpu_qnorm_rope_kv_fp8_insert_fused(
            q,
            kv,
            self.swa_cache,
            self.compact_slot,
            self.positions,
            case.get("attn_global_static_binding", self.rotary_name),
            1e-6,
            64,
        )
        o = torch.empty_like(q)
        scores, lse = split_fp8_sparse_attention(
            q,
            self.compressed_cache,
            self.topk_indices,
            self.topk_lens,
            self.swa_cache,
            self.swa_indices,
            self.swa_lens,
            case.get("attn_static_binding", "attn_param::attn_sink"),
            512**-0.5,
            o,
            block_h=4,
            qk_num_warps=16,
            pv_num_warps=4,
        )
        topk_width = 0 if self.topk_indices is None else self.topk_indices.shape[-1]
        valid_parts = []
        if self.topk_valid:
            valid_parts.append(scores[:, :, : self.topk_valid])
        valid_parts.append(
            scores[:, :, topk_width : topk_width + self.swa_valid]
        )
        score_valid = torch.cat(valid_parts, dim=-1)
        o_ref = _fused_inverse_rope_gptj(
            o,
            self.positions,
            case.get("attn_global_static_binding", self.rotary_name),
            64,
        ).view(1, 2, 4096)
        z = torch.einsum(
            "tgd,grd->tgr",
            o_ref,
            case.get("attn_static_binding", "wo_a_hot_bf16"),
        )
        local = torch.ops._xpu_C.fp8_gemm_w8a16(
            z.flatten(1),
            case.get("attn_static_binding", "attn_param::wo_b.weight").t(),
            case.get("attn_static_binding", "attn_param::wo_b.weight_scale_inv"),
            None,
        )
        outputs.update(
            {
                "qr": qr,
                "kv": kv,
                "q": q,
                "scores_initialized": score_valid,
                "lse": lse,
                "pv": o,
                "z": z,
                "local": local,
                "swa_cache": self.swa_cache,
            }
        )
        return outputs

    def bindings(self) -> dict[str, torch.Tensor]:
        result = {
            "x": self.x,
            "positions": self.positions,
            "swa_cache": self.swa_cache,
            "swa_indices": self.swa_indices,
            "swa_lens": self.swa_lens,
            "compact_slot": self.compact_slot,
        }
        for index, tensor in enumerate(self.case.rows.values()):
            result[f"packet_{index:03d}"] = tensor
        for name in ("residual", "post_in", "comb_in", "compressed_cache", "topk_indices", "topk_lens", "state_cache"):
            tensor = getattr(self, name)
            if tensor is not None:
                result[name] = tensor
        return result


def compare_outputs(
    actual: dict[str, torch.Tensor], expected: dict[str, torch.Tensor]
) -> tuple[bool, list[dict[str, Any]]]:
    reports = [
        compare_tensor_bits(name, actual[name], expected[name]).to_dict()
        for name in sorted(expected)
    ]
    return all(bool(row["exact"]) for row in reports), reports


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet", type=Path)
    parser.add_argument("--native-build-dir", type=Path, required=True)
    parser.add_argument("--rank", type=int, default=0)
    parser.add_argument("--layer", type=int, default=42)
    parser.add_argument(
        "--bucket",
        choices=("swa-resident-anchor64", "compressed-swa-full-anchor512"),
        default="compressed-swa-full-anchor512",
    )
    parser.add_argument("--changed-cases", type=int, default=40)
    parser.add_argument("--replays", type=int, default=70)
    parser.add_argument("--unitrace", type=Path)
    parser.add_argument("--session")
    parser.add_argument("--trace-mode", choices=("eager", "raw"), default="raw")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.unitrace is None) != (args.session is None):
        parser.error("--unitrace and --session must be supplied together")
    if os.environ.get("ZE_AFFINITY_MASK") is None:
        raise RuntimeError("ZE_AFFINITY_MASK must select one free card")
    if os.environ.get("ZE_ENABLE_TRACING_LAYER") != "1":
        raise RuntimeError("raw handle harvest requires ZE_ENABLE_TRACING_LAYER=1")

    from vllm.platforms import current_platform
    import vllm_xpu_kernels._xpu_C as xpu_extension

    current_platform.import_kernels()
    device = torch.device("xpu:0")
    torch.xpu.set_device(device)
    native = load_native_replay(args.native_build_dir)
    manifest = args.packet / "manifests" / (
        f"rank{args.rank}-layer{args.layer:02d}-{args.bucket}.json"
    )
    graph_boundary = Boundary(PacketCase(args.packet, manifest, device))
    ref_boundary = Boundary(PacketCase(args.packet, manifest, device))
    raw_handles: tuple[int, int] | None = None

    def raw_replay(_: int) -> None:
        assert raw_handles is not None
        native.replay_raw_level_zero(*raw_handles)

    graph = FixedAddressCommandGraph(
        graph_boundary.launch, graph_boundary.bindings(), native_replay=raw_replay
    )
    graph_boundary.reset()
    graph.warm(3)
    graph_outputs = dict(graph.build())
    harvested = tuple(int(x) for x in native.harvest_raw_level_zero_handles(graph.graph_exec))
    raw_handles = harvested[:2]
    torch.xpu.synchronize()

    changed_rows = []
    for case_index in range(1, args.changed_cases + 1):
        ref_boundary.reset(case_index)
        expected = ref_boundary.launch()
        torch.xpu.synchronize()
        graph_boundary.reset(case_index)
        graph.replay()
        torch.xpu.synchronize()
        exact, reports = compare_outputs(graph_outputs, expected)
        changed_rows.append(
            {"case": case_index, "exact": exact, "reports": reports}
        )
    if not all(row["exact"] for row in changed_rows):
        raise RuntimeError("changed-input raw command-list parity failed")
    graph.mark_parity_qualified(exact=True)

    replay_rows = []
    for epoch in range(args.replays):
        changed_case = 1 + epoch % max(args.changed_cases, 1)
        graph_boundary.reset(changed_case)
        started = time.monotonic_ns()
        graph.replay()
        submitted = time.monotonic_ns()
        torch.xpu.synchronize()
        replay_rows.append(
            {
                "epoch": epoch,
                "changed_case": changed_case,
                "enqueue_us": (submitted - started) / 1000.0,
                "witness_sha256": hashlib.sha256(
                    graph_outputs["local"].cpu().view(torch.uint8).numpy().tobytes()
                ).hexdigest(),
            }
        )

    trace_controls = []
    trace_started_ns = None
    trace_ended_ns = None
    if args.unitrace is not None and args.session is not None:
        graph_boundary.reset(17)
        trace_controls.append(trace_control(args.unitrace, "resume", args.session))
        trace_started_ns = time.monotonic_ns()
        if args.trace_mode == "raw":
            graph.replay()
        else:
            graph_boundary.launch()
        trace_ended_ns = time.monotonic_ns()
        trace_controls.append(trace_control(args.unitrace, "pause", args.session))
        torch.xpu.synchronize()
        trace_controls.append(trace_control(args.unitrace, "stop", args.session))

    extension = Path(xpu_extension.__file__).resolve()
    result = {
        "schema": "option4-m1-attention-boundary-v1-raw-lz-gate",
        "passed": all(row["exact"] for row in changed_rows)
        and len(replay_rows) == args.replays,
        "packet_manifest_sha256": json.loads(
            (args.packet / "packet-manifest.json").read_text()
        )["packet_manifest_sha256"],
        "rank": args.rank,
        "layer": args.layer,
        "bucket": args.bucket,
        "compression_ratio": graph_boundary.ratio,
        "changed": {
            "exact": sum(bool(row["exact"]) for row in changed_rows),
            "required": args.changed_cases,
            "rows": changed_rows,
        },
        "replay": {
            "passed": len(replay_rows),
            "required": args.replays,
            "includes_epochs": [28, 58],
            "epoch_28_present": any(row["epoch"] == 28 for row in replay_rows),
            "epoch_58_present": any(row["epoch"] == 58 for row in replay_rows),
            "median_enqueue_us": statistics.median(
                row["enqueue_us"] for row in replay_rows
            ),
            "rows": replay_rows,
        },
        "graph": {
            "state": graph.state.name,
            "queue_identity": graph.queue_identity,
            "graph_exec": graph.graph_exec,
            "raw_immediate_list": raw_handles[0],
            "raw_regular_list": raw_handles[1],
            "harvest_matching_appends": harvested[2],
            "fixed_bindings": graph.address_manifest,
        },
        "runtime": {
            "xpu_extension": str(extension),
            "xpu_extension_sha256": sha256_file(extension),
            "native_shim": str(Path(native.__file__).resolve()),
            "native_shim_sha256": sha256_file(Path(native.__file__).resolve()),
        },
        "trace": {
            "mode": args.trace_mode,
            "started_monotonic_ns": trace_started_ns,
            "ended_monotonic_ns": trace_ended_ns,
            "controls": trace_controls,
            "explicit_completion_wait_outside_window": True,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "changed": result["changed"]["exact"],
                "replays": result["replay"]["passed"],
                "median_enqueue_us": result["replay"]["median_enqueue_us"],
                "raw_harvest": harvested[2],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
