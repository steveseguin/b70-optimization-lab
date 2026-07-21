#!/usr/bin/env python3
"""Replay the checksummed Option-4 M=1 attention boundary packet on one XPU.

This is deliberately a no-model worker.  It reconstructs the exact incumbent
M=1 operator chain from the captured inputs, weights, sparse selections, and
KV bytes.  The packet remains immutable; all device buffers are fresh.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))


def _load(path: Path, device: torch.device) -> torch.Tensor:
    return torch.load(path, map_location="cpu", weights_only=True).to(device)


class PacketCase:
    def __init__(self, packet: Path, manifest: Path, device: torch.device) -> None:
        self.packet = packet
        self.meta = json.loads(manifest.read_text())
        self.device = device
        self.rows: dict[tuple[str, str], torch.Tensor] = {}
        for group in ("global_static_records", "shared_static_records", "records"):
            for row in self.meta[group]:
                key = (row["stage"], row["tensor_name"])
                # shared_static_records intentionally duplicate first-forward rows.
                if key not in self.rows:
                    self.rows[key] = _load(packet / "raw" / row["tensor_path"], device)

    def get(self, stage: str, name: str) -> torch.Tensor:
        return self.rows[(stage, name)]

    def maybe(self, stage: str, name: str) -> torch.Tensor | None:
        return self.rows.get((stage, name))


def _pack_selected_rows(raw: torch.Tensor, block_size: int) -> torch.Tensor:
    """Convert [slot, data576|scale8] captures to paged DS-MLA layout."""
    width = raw.shape[0]
    blocks = (width + block_size - 1) // block_size
    cache = torch.zeros(
        (blocks, block_size, 584), dtype=torch.uint8, device=raw.device
    )
    flat = cache.view(blocks, -1)
    for slot in range(width):
        block = slot // block_size
        offset = slot % block_size
        flat[block, offset * 576 : (offset + 1) * 576].copy_(raw[slot, :576])
        scale_start = block_size * 576 + offset * 8
        flat[block, scale_start : scale_start + 8].copy_(raw[slot, 576:])
    return cache


def _bits_equal(actual: torch.Tensor, expected: torch.Tensor) -> bool:
    if actual.shape != expected.shape or actual.dtype != expected.dtype:
        return False
    return torch.equal(actual.view(torch.uint8), expected.view(torch.uint8))


def _check(
    checks: dict[str, bool], name: str, actual: torch.Tensor, expected: torch.Tensor
) -> None:
    checks[name] = _bits_equal(actual, expected)


def replay_case(case: PacketCase) -> dict[str, Any]:
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

    checks: dict[str, bool] = {}
    layer = int(case.meta["layer"])
    rotary_name = (
        f"attn_rotary_cos_sin_cache_c{int(case.meta['compression_ratio'])}"
    )
    fn = case.get("attn_static_binding", "hc_attn_fn")
    hc_scale = case.get("attn_static_binding", "hc_attn_scale")
    hc_base = case.get("attn_static_binding", "hc_attn_base")
    ingress = case.get("m1_boundary_ingress", "x")

    if layer == 0:
        residual = ingress
        post = torch.empty((1, 4, 1), dtype=torch.float32, device=case.device)
        comb = torch.empty((1, 4, 4), dtype=torch.float32, device=case.device)
        layer_input = torch.empty((1, 4096), dtype=torch.bfloat16, device=case.device)
        torch.ops._xpu_C.mhc_pre_m1_out(
            residual,
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
        residual_out = residual
    else:
        residual = case.get("m1_boundary_ingress", "residual")
        post_in = case.get("m1_boundary_ingress", "post_mix")
        comb_in = case.get("m1_boundary_ingress", "res_mix")
        residual_out = torch.empty_like(residual)
        post = torch.empty_like(post_in)
        comb = torch.empty_like(comb_in)
        layer_input = torch.empty_like(ingress)
        torch.ops._xpu_C.mhc_post_pre_m1_out(
            ingress,
            residual,
            post_in,
            comb_in,
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

    _check(checks, "mhc.residual", residual_out, case.get("mhc_attn_out", "residual_out"))
    _check(checks, "mhc.post", post, case.get("mhc_attn_out", "next_post_mix"))
    _check(checks, "mhc.comb", comb, case.get("mhc_attn_out", "next_res_mix"))
    _check(checks, "mhc.layer_input", layer_input, case.get("mhc_attn_out", "layer_input"))

    attn_x = torch.empty_like(layer_input)
    ops.rms_norm(
        attn_x,
        layer_input,
        case.get("attn_static_binding", "attn_norm_weight"),
        1e-6,
    )
    _check(checks, "attn.norm", attn_x, case.get("attn_in", "x"))

    qr_kv = torch.ops._xpu_C.fp8_gemm_w8a16(
        attn_x,
        case.get("attn_static_binding", "attn_param::fused_wqa_wkv.weight").t(),
        case.get(
            "attn_static_binding", "attn_param::fused_wqa_wkv.weight_scale_inv"
        ),
        None,
    )
    _check(checks, "attn.qr_kv", qr_kv, case.get("attn_input_gemm", "qr_kv"))
    compressor_weight = case.maybe(
        "attn_static_binding", "attn_param::compressor.fused_wkv_wgate.weight"
    )
    if compressor_weight is not None:
        ratio = int(case.meta["compression_ratio"])
        kv_score = torch.mm(attn_x, compressor_weight.t(), out_dtype=torch.float32)
        _check(
            checks,
            "compressor.kv_score",
            kv_score,
            case.get("attn_input_gemm", "kv_score"),
        )
        state_before = case.get("compressor_state_before", "rows")
        state_after = case.get("compressor_state_after", "rows")
        state_block = 4 if ratio == 4 else 8
        state_width = state_before.shape[-1] // 2
        state_cache = torch.zeros(
            (1, state_block, state_before.shape[-1]),
            dtype=torch.float32,
            device=case.device,
        )
        state_cache[:, :3].copy_(state_before)
        partial_kv, partial_score = kv_score.split([state_width, state_width], -1)
        save_partial_states(
            partial_kv,
            partial_score,
            case.get("attn_static_binding", "attn_param::compressor.ape"),
            case.get("m1_boundary_ingress", "positions"),
            state_cache,
            torch.ones((1,), dtype=torch.int64, device=case.device),
            state_block,
            state_width,
            ratio,
        )
        _check(
            checks,
            "compressor.state_rows",
            state_cache[:, :3],
            state_after,
        )
    qr, kv = qr_kv.split([1024, 512], dim=-1)
    qr, kv = fused_q_kv_rmsnorm(
        qr,
        kv,
        case.get("attn_static_binding", "attn_param::q_norm.weight"),
        case.get("attn_static_binding", "attn_param::kv_norm.weight"),
        1e-6,
    )
    _check(checks, "attn.qr_norm", qr, case.get("attn_qkv_norm", "qr"))
    _check(checks, "attn.kv_norm", kv, case.get("attn_qkv_norm", "kv"))

    q = torch.ops._xpu_C.fp8_gemm_w8a16(
        qr,
        case.get("attn_static_binding", "attn_param::wq_b.weight").t(),
        case.get("attn_static_binding", "attn_param::wq_b.weight_scale_inv"),
        None,
    ).view(1, 16, 512)
    swa_raw = case.get("swa_kv_selected", "raw")
    swa_cache = _pack_selected_rows(swa_raw, 64)
    swa_lens = case.get("attn_sparse_bindings", "swa_lens")
    swa_width = case.get("attn_sparse_bindings", "swa_indices").shape[-1]
    swa_indices = torch.arange(
        swa_width, dtype=torch.int32, device=case.device
    ).view(1, swa_width)
    # The captured current slot is always the last valid SWA row at both anchors.
    compact_slot = swa_lens.to(torch.int64) - 1
    xpu_qnorm_rope_kv_fp8_insert_fused(
        q,
        kv,
        swa_cache,
        compact_slot,
        case.get("m1_boundary_ingress", "positions"),
        case.get("attn_global_static_binding", rotary_name),
        1e-6,
        64,
    )
    _check(checks, "attn.q_rope", q, case.get("swa_kv_after", "q_after"))

    topk_indices = case.maybe("attn_sparse_bindings", "topk_indices")
    topk_lens = case.maybe("attn_sparse_bindings", "topk_lens")
    compressed_cache = None
    compact_topk = None
    if topk_indices is not None:
        compressed_raw = case.get("compressed_kv_selected", "raw")
        compressed_cache = _pack_selected_rows(compressed_raw, 16)
        compact_topk = torch.arange(
            topk_indices.shape[-1], dtype=torch.int32, device=case.device
        ).view(1, -1)

    o = torch.empty_like(q)
    scores, lse = split_fp8_sparse_attention(
        q,
        compressed_cache,
        compact_topk,
        topk_lens,
        swa_cache,
        swa_indices,
        swa_lens,
        case.get("attn_static_binding", "attn_param::attn_sink"),
        512**-0.5,
        o,
        block_h=4,
        qk_num_warps=16,
        pv_num_warps=4,
    )
    # The split kernel intentionally leaves the static-capacity tail of
    # `scores` unwritten.  Only compare initialized compressed/SWA prefixes;
    # comparing allocator garbage would turn parity into an address accident.
    expected_scores = case.get("attn_qk_lse_pv", "scores")
    topk_valid = 0 if topk_lens is None else int(topk_lens.item())
    swa_valid = int(swa_lens.item())
    score_parts = []
    expected_parts = []
    if topk_valid:
        score_parts.append(scores[:, :, :topk_valid])
        expected_parts.append(expected_scores[:, :, :topk_valid])
    score_parts.append(scores[:, :, swa_width * 0 + (0 if topk_indices is None else topk_indices.shape[-1]) :][:, :, :swa_valid])
    expected_parts.append(expected_scores[:, :, (0 if topk_indices is None else topk_indices.shape[-1]) :][:, :, :swa_valid])
    _check(
        checks,
        "attn.scores_initialized",
        torch.cat(score_parts, dim=-1),
        torch.cat(expected_parts, dim=-1),
    )
    _check(checks, "attn.lse", lse, case.get("attn_qk_lse_pv", "lse"))
    _check(checks, "attn.pv", o, case.get("attn_qk_lse_pv", "pv"))

    o_ref = _fused_inverse_rope_gptj(
        o,
        case.get("m1_boundary_ingress", "positions"),
        case.get("attn_global_static_binding", rotary_name),
        64,
    ).view(1, 2, 4096)
    z = torch.einsum(
        "tgd,grd->tgr",
        o_ref,
        case.get("attn_static_binding", "wo_a_hot_bf16"),
    )
    _check(checks, "attn.wo_a", z, case.get("attn_wo_a", "z"))
    local = torch.ops._xpu_C.fp8_gemm_w8a16(
        z.flatten(1),
        case.get("attn_static_binding", "attn_param::wo_b.weight").t(),
        case.get("attn_static_binding", "attn_param::wo_b.weight_scale_inv"),
        None,
    )
    _check(checks, "attn.wo_b_local", local, case.get("attn_wo_b_local", "output"))
    torch.xpu.synchronize()
    return {
        "rank": case.meta["rank"],
        "layer": layer,
        "bucket": case.meta["bucket"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet", type=Path)
    parser.add_argument("--rank", type=int, default=0)
    parser.add_argument("--layer", type=int, default=0)
    parser.add_argument("--all-layers", action="store_true")
    parser.add_argument(
        "--bucket",
        choices=("swa-resident-anchor64", "compressed-swa-full-anchor512"),
        default="swa-resident-anchor64",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if os.environ.get("ZE_AFFINITY_MASK") is None:
        raise RuntimeError("ZE_AFFINITY_MASK must select one verified free card")

    from vllm.platforms import current_platform

    current_platform.import_kernels()
    device = torch.device("xpu:0")
    torch.xpu.set_device(device)
    layers = range(43) if args.all_layers else [args.layer]
    cases = []
    for layer in layers:
        manifest = args.packet / "manifests" / (
            f"rank{args.rank}-layer{layer:02d}-{args.bucket}.json"
        )
        cases.append(replay_case(PacketCase(args.packet, manifest, device)))
        torch.xpu.empty_cache()
    result = {
        "schema": "option4-m1-attention-eager-oracle-gate-v1",
        "rank": args.rank,
        "bucket": args.bucket,
        "layers": len(cases),
        "exact_layers": sum(bool(case["passed"]) for case in cases),
        "cases": cases,
        "passed": all(case["passed"] for case in cases),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
