#!/usr/bin/env python3
"""MiniMax-H3 text-to-video-with-audio on two Intel B70s, from the pruned BF16 FL2VA denoiser.

    Phase 0  plan       read safetensors headers, resolve the byte-balanced layer split
    Phase 1  encode     Qwen3-VL-32B INT8 ConvRot text encoder on xpu:0, hidden state after
                        decoder layer 50, then the encoder is freed before anything else loads
    Phase 2  load       pruned BF16 denoiser streamed tensor-by-tensor across xpu:0 / xpu:1
    Phase 3  sample     diffusers MiniMaxH3 modular blocks, cfg-free, one forward per step,
                        video shift 12 / audio shift 3
    Phase 4  decode     video VAE (float16) and audio VAE (float32), one at a time on xpu:0
    Phase 5  write      mp4 + audio via PyAV, and a sidecar JSON receipt

Only one large component is resident at a time; each phase frees its component before the next
loads.  Host RAM never holds a full state dict: every tensor is mmap-sliced out of the checkpoint
and copied straight to its card.

This is the `t2va` workflow driven against the `transformer/` (FL2VA) partition -- which is the
partition the pruned Comfy checkpoint is, and which serves both the text-only and the
first/last-keyframe modes.  No keyframes are passed, so no image encoder runs.

Hard constraints this script respects
-------------------------------------
* `--dry-run` never imports torch.xpu, diffusers or transformers and never allocates a device
  tensor: it reads configs and safetensors *headers* only.  It is the CPU validation path.
* GPU work is expected to run under `systemd-run --user` (see `smoke_h3.sh`), per the lab rule
  that the interactive harness may kill long GPU jobs, and under `mem-watchdog.sh`, per the
  2026-09-18 host OOM incident: this host has 15 GiB of RAM and `systemd-oomd` kills the user's
  whole session on sustained memory pressure.
* Nothing here starts, stops or restarts a service or container.

Environment switches
--------------------
* `B70_H3_LOADER=pread|mmap` -- how checkpoint tensors are read.  `pread` (the default) parses the
  safetensors header once, `os.pread`s each tensor's byte range into a private buffer and then
  `posix_fadvise(DONTNEED)`s that range: the file is never mapped, so RssFile stays flat.  `mmap`
  is the old `safe_open` path, kept for A/B: it holds the whole file mapped for the handle's
  lifetime, so RssFile grows with every byte touched (6.35 GiB at a 6 GiB budget in sessions 6/7)
  and `posix_fadvise` cannot evict a mapped page.
* `B70_H3_LOG_MEM=1` -- log host VmRSS / RssAnon / RssFile / MemAvailable every 50 tensors during
  both load loops (`B70_H3_LOG_MEM_EVERY` changes the interval).
* `B70_H3_DROP_PAGECACHE=1` -- posix_fadvise(DONTNEED) the checkpoint being streamed every 50
  tensors, to hold the mmap page cache down (`B70_H3_DROP_PAGECACHE_EVERY`). Off by default.
  `scripts/profile-encoder-load.py` measures both, on CPU, before any GPU run.

Run `--help` for the options.  `smoke_h3.sh` holds the exact command lines.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import json
import logging
import math
import os
import pathlib
import platform
import struct
import sys
import time

# ---------------------------------------------------------------------------------------------
# Paths (everything is already on this host; nothing here downloads)
# ---------------------------------------------------------------------------------------------

REPO_ORIGINAL = pathlib.Path("/mnt/fast-ai/llm-models/minimax-h3")
REPO_COMFY = pathlib.Path("/mnt/fast-ai/llm-models/minimax-h3-comfy")

PRUNED_DENOISER = REPO_COMFY / "diffusion_models" / "minimax_h3_fl2va_pruned_bf16.safetensors"
INT8_TEXT_ENCODER = REPO_COMFY / "text_encoders" / "qwen3vl_32b_minimax_h3_int8_convrot.safetensors"
CONVROT_ROTATION = pathlib.Path(__file__).resolve().parent.parent / "data" / "convrot-hadamard-256.safetensors"

TRANSFORMER_CONFIG = REPO_ORIGINAL / "transformer" / "config.json"
TEXT_ENCODER_DIR = REPO_ORIGINAL / "text_encoder"
TOKENIZER_DIR = REPO_ORIGINAL / "tokenizer"
VAE_DIR = REPO_ORIGINAL / "vae"
AUDIO_VAE_DIR = REPO_ORIGINAL / "audio_vae"
SCHEDULER_DIR = REPO_ORIGINAL / "scheduler"
AUDIO_SCHEDULER_DIR = REPO_ORIGINAL / "audio_scheduler"

LOG = logging.getLogger("h3")


# ---------------------------------------------------------------------------------------------
# safetensors header reading -- no torch, no mmap of the data, just the JSON header
# ---------------------------------------------------------------------------------------------

_DTYPE_BYTES = {"BOOL": 1, "U8": 1, "I8": 1, "F8_E4M3": 1, "F8_E5M2": 1, "I16": 2, "U16": 2,
                "F16": 2, "BF16": 2, "I32": 4, "U32": 4, "F32": 4, "I64": 8, "U64": 8, "F64": 8}


def read_header_and_data_start(path: pathlib.Path) -> tuple[dict, int]:
    """The safetensors header dict, and the file offset its `data_offsets` are relative to.

    The layout is `<u64 header_len><header json><data>`, so the data starts at `8 + header_len`
    and every `data_offsets` pair in the header is relative to that.  `PreadTensorReader` turns
    those two numbers into an absolute file range.
    """
    with path.open("rb") as fh:
        (header_len,) = struct.unpack("<Q", fh.read(8))
        header = json.loads(fh.read(header_len))
    header.pop("__metadata__", None)
    return header, 8 + header_len


def read_header(path: pathlib.Path) -> dict:
    """Return the safetensors header dict (tensor name -> {dtype, shape, data_offsets})."""
    return read_header_and_data_start(path)[0]


def tensor_bytes(entry: dict) -> int:
    n = 1
    for dim in entry["shape"]:
        n *= dim
    return n * _DTYPE_BYTES[entry["dtype"]]


# ---------------------------------------------------------------------------------------------
# Checkpoint key remap: Comfy/upstream naming -> diffusers MiniMaxH3Transformer3DModel naming
#
# Verified byte-for-byte on 2026-09-17 against the full BF16 diffusers checkpoint in
# /mnt/fast-ai/llm-models/minimax-h3/transformer/ (the pruned build only replaces the AdaLN
# branch, so every other tensor must be identical).  Results:
#
#   qkv_proj[0:7168] == to_q, [7168:14336] == to_k, [14336:21504] == to_v   EXACT
#   attn.out_proj == attn.to_out.0                                          EXACT
#   mlp.fc2 == ff.net.2                                                     EXACT
#   mlp.fc1 is [gate ; value], diffusers ff.net.0.proj is [value ; gate]     SWAPPED HALVES
#       (diffusers SwiGLU.forward: `hidden_states, gate = proj(x).chunk(2, -1)`,
#        src/diffusers/models/activations.py L143-146 -- the *first* half is the value)
#   video_patch_proj == proj_in, audio_patch_proj == audio_proj_in,
#   condition_proj == context_embedder, final_layer.{video_out,audio_out,norm}
#       == {proj_out, audio_proj_out, norm_out.norm}                        EXACT
#
# The AdaLN keys deliberately do NOT match the full checkpoint: that is the pruning.
# ---------------------------------------------------------------------------------------------

HIDDEN_SIZE = 5376
INNER_DIM = 56 * 128  # num_attention_heads * attention_head_dim = 7168
FFN_DIM = 14336
ADALN_RANK = 8  # the pruned AdaLN table's width


@dataclasses.dataclass(frozen=True)
class SourceSlice:
    """How one diffusers parameter is built out of the pruned checkpoint."""

    key: str  # tensor name in the pruned file
    row_slice: tuple[int, int] | None = None  # rows to take, or None for all
    swap_halves: bool = False  # concatenate [second half ; first half]

    def nbytes(self, header: dict) -> int:
        entry = header[self.key]
        total = tensor_bytes(entry)
        if self.row_slice is None:
            return total
        rows = entry["shape"][0]
        return total * (self.row_slice[1] - self.row_slice[0]) // rows


def build_remap(num_layers: int, num_refiner_layers: int) -> dict[str, SourceSlice]:
    """diffusers parameter name -> where it comes from in the pruned Comfy checkpoint."""
    remap: dict[str, SourceSlice] = {
        "proj_in.weight": SourceSlice("video_patch_proj.weight"),
        "proj_in.bias": SourceSlice("video_patch_proj.bias"),
        "audio_proj_in.weight": SourceSlice("audio_patch_proj.weight"),
        "audio_proj_in.bias": SourceSlice("audio_patch_proj.bias"),
        "context_embedder.weight": SourceSlice("condition_proj.weight"),
        "context_embedder.bias": SourceSlice("condition_proj.bias"),
        "token_refiner.final_norm.weight": SourceSlice("token_refiner.final_norm.weight"),
        # `norm_out` is Comfy's `final_layer`; its `adaln_proj.linear` is the pruned rank-8 form.
        "norm_out.norm.weight": SourceSlice("final_layer.norm.weight"),
        "norm_out.linear.weight": SourceSlice("final_layer.adaln_proj.linear.weight"),
        "norm_out.linear.bias": SourceSlice("final_layer.adaln_proj.linear.bias"),
        "proj_out.weight": SourceSlice("final_layer.video_out.weight"),
        "proj_out.bias": SourceSlice("final_layer.video_out.bias"),
        "audio_proj_out.weight": SourceSlice("final_layer.audio_out.weight"),
        "audio_proj_out.bias": SourceSlice("final_layer.audio_out.bias"),
    }

    def add_attn(dst_prefix: str, src_prefix: str) -> None:
        remap[f"{dst_prefix}.attn.to_q.weight"] = SourceSlice(f"{src_prefix}.attn.qkv_proj.weight", (0, INNER_DIM))
        remap[f"{dst_prefix}.attn.to_k.weight"] = SourceSlice(
            f"{src_prefix}.attn.qkv_proj.weight", (INNER_DIM, 2 * INNER_DIM)
        )
        remap[f"{dst_prefix}.attn.to_v.weight"] = SourceSlice(
            f"{src_prefix}.attn.qkv_proj.weight", (2 * INNER_DIM, 3 * INNER_DIM)
        )
        remap[f"{dst_prefix}.attn.norm_q.weight"] = SourceSlice(f"{src_prefix}.attn.q_norm.weight")
        remap[f"{dst_prefix}.attn.norm_k.weight"] = SourceSlice(f"{src_prefix}.attn.k_norm.weight")
        remap[f"{dst_prefix}.attn.to_out.0.weight"] = SourceSlice(f"{src_prefix}.attn.out_proj.weight")
        remap[f"{dst_prefix}.norm1.weight"] = SourceSlice(f"{src_prefix}.norm1.weight")
        remap[f"{dst_prefix}.norm2.weight"] = SourceSlice(f"{src_prefix}.norm2.weight")
        # SwiGLU: Comfy stores [gate ; value], diffusers reads [value ; gate].
        remap[f"{dst_prefix}.ff.net.0.proj.weight"] = SourceSlice(f"{src_prefix}.mlp.fc1.weight", swap_halves=True)
        remap[f"{dst_prefix}.ff.net.2.weight"] = SourceSlice(f"{src_prefix}.mlp.fc2.weight")

    for i in range(num_layers):
        add_attn(f"transformer_blocks.{i}", f"blocks.{i}")
        remap[f"transformer_blocks.{i}.adaln_proj.linear.weight"] = SourceSlice(f"blocks.{i}.adaln_proj.linear.weight")
        remap[f"transformer_blocks.{i}.adaln_proj.linear.bias"] = SourceSlice(f"blocks.{i}.adaln_proj.linear.bias")
    for i in range(num_refiner_layers):
        add_attn(f"token_refiner.refiner_blocks.{i}", f"token_refiner.blocks.{i}")
    return remap


# Mirrors MiniMaxH3Transformer3DModel._keep_in_fp32_modules
# (transformer_minimax_h3.py L444-451): the patch projections and the output heads are float32 in
# the released mixed-precision checkpoint, and the pruned file stores them that way too.
FP32_SUBSTRINGS = ("proj_in", "audio_proj_in", "proj_out", "audio_proj_out", "rope")


def target_dtype(name: str, adaln_dtype: str):
    import torch

    if any(s in name for s in FP32_SUBSTRINGS):
        return torch.float32
    if "adaln_proj.linear" in name or name.startswith("norm_out.linear"):
        # ComfyUI passes `adaln_dtype=float32` to every AdalnProj in the `use_adaln_curves` branch,
        # even though W8 is stored F16 (notes/2026-09-17-adaln-table-exactness.md).
        return torch.float32 if adaln_dtype == "fp32" else torch.bfloat16
    return torch.bfloat16


# ---------------------------------------------------------------------------------------------
# Phase 0 -- the byte-balanced two-card split (LTX lane policy)
# ---------------------------------------------------------------------------------------------


@dataclasses.dataclass
class SplitPlan:
    split_index: int
    num_layers: int
    block_bytes: list[int]
    non_block_bytes: int
    card0_bytes: int
    card1_bytes: int
    table_bytes: int

    def as_dict(self) -> dict:
        return {
            "split_index": self.split_index,
            "num_layers": self.num_layers,
            "non_block_bytes": self.non_block_bytes,
            "card0_bytes": self.card0_bytes,
            "card1_bytes": self.card1_bytes,
            "card0_gib": round(self.card0_bytes / 2**30, 3),
            "card1_gib": round(self.card1_bytes / 2**30, 3),
            "imbalance_bytes": abs(self.card0_bytes - self.card1_bytes),
            "adaln_table_bytes": self.table_bytes,
        }


def plan_split(header: dict, config: dict, adaln_dtype: str, split_index: int | None = None) -> SplitPlan:
    """Byte-balanced split of the block stack over two cards.

    The policy is `experiments/ltx25-b70/scripts/ltx_layer_shard.py` (`LTXLayerShardedPatcher.install`):
    non-block parameters live on the primary card, and `split_index` minimises

        |non_block + 2 * sum(block_bytes[:n]) - sum(block_bytes)|

    i.e. it balances `non_block + first n blocks` against `the remaining blocks`.

    Bytes are counted *after* the remap and the dtype policy, not as stored, because the AdaLN
    projections are widened F16 -> F32 when `--adaln-dtype fp32` and that is real card memory.
    """
    num_layers = config["num_layers"]
    num_refiner = config["num_refiner_layers"]
    remap = build_remap(num_layers, num_refiner)
    width = {"fp32": 4, "bf16": 2}

    def size_of(name: str) -> int:
        src = remap[name]
        raw = src.nbytes(header)
        stored = _DTYPE_BYTES[header[src.key]["dtype"]]
        if any(s in name for s in FP32_SUBSTRINGS):
            want = 4
        elif "adaln_proj.linear" in name or name.startswith("norm_out.linear"):
            want = width[adaln_dtype]
        else:
            want = 2
        return raw // stored * want

    block_bytes = [
        sum(size_of(n) for n in remap if n.startswith(f"transformer_blocks.{i}.")) for i in range(num_layers)
    ]
    block_names = {n for i in range(num_layers) for n in remap if n.startswith(f"transformer_blocks.{i}.")}
    non_block = sum(size_of(n) for n in remap if n not in block_names)
    # The AdaLN table replaces `time_embedder`; it is shared, so it lives on the primary card and
    # is broadcast to the secondary once per forward (it is [1025, 8] float32 = 32.8 KB).
    table_bytes = tensor_bytes(header["adaln_t_table"])
    non_block += table_bytes
    # `rope.inv_freq` is a non-persistent buffer diffusers recomputes; count it anyway (64 B).
    non_block += tensor_bytes(header["rope.inv_freq"])

    total_blocks = sum(block_bytes)
    if split_index is None:
        split_index = min(
            range(1, num_layers),
            key=lambda n: abs(non_block + 2 * sum(block_bytes[:n]) - total_blocks),
        )
    if not 0 < split_index < num_layers:
        raise ValueError(f"split_index must leave at least one block on each card, got {split_index}")

    return SplitPlan(
        split_index=split_index,
        num_layers=num_layers,
        block_bytes=block_bytes,
        non_block_bytes=non_block,
        card0_bytes=non_block + sum(block_bytes[:split_index]),
        card1_bytes=sum(block_bytes[split_index:]),
        table_bytes=table_bytes,
    )


# ---------------------------------------------------------------------------------------------
# The pruned AdaLN form -- ComfyUI `comfy/ldm/minimax/model.py`, `use_adaln_curves` branch
#
# Full model (diffusers transformer_minimax_h3.py L641-642, L124-131):
#     temb = time_embedder(time_proj(t))                       # 256 -> 5376 -> 2688, float32
#     m    = adaln_proj.linear(silu(temb).to(bf16))            # 2688 -> 96768
#
# Pruned model:
#     pos  = clamp(t, 0, 1) * 1024 ; i0 = floor(pos)
#     c    = lerp(adaln_t_table[i0], adaln_t_table[i0 + 1], pos - i0)     # [T, 8] float32
#     m    = W8 @ c + b8                                                  # no silu
#
# The table already holds the *post-silu* curve in 8 coordinates, so `apply_silu=False`, and the
# projection runs in float32 even though W8 is stored F16.
#
# The interpolation is load-bearing: measured in notes/2026-09-17-adaln-table-exactness.md, the
# lerp costs 1.2e-5 while snapping to the nearest grid row costs 4.2e-3 -- 5x the rank-8 fit error
# itself and comparable to the bf16 noise floor.  Never round to a grid row.
# ---------------------------------------------------------------------------------------------


def make_pruned_adaln_modules(torch, nn):
    """Build the three replacement modules, given the torch handles (keeps the import lazy)."""

    class AdaLNTableEmbedder(nn.Module):
        """Drop-in for `time_embedder`: maps t in [0, 1] to the 8 table coordinates.

        It is installed where `time_embedder` was, so the unmodified
        `MiniMaxH3Transformer3DModel.forward` keeps working: `time_proj` becomes an identity, and
        this module's output takes the place of the 2688-wide `temb` everywhere downstream.
        """

        def __init__(self, table):
            super().__init__()
            # Registered as a float32 Parameter so `get_parameter_dtype(self)` -- which
            # transformer_minimax_h3.py L642 calls before the cast -- reports float32.
            self.table = nn.Parameter(table, requires_grad=False)
            self.grid = table.shape[0] - 1  # 1024

        def forward(self, timestep):
            t = timestep.to(torch.float32).clamp(0.0, 1.0)
            pos = t * self.grid
            i0 = pos.floor().to(torch.long).clamp(0, self.grid - 1)
            frac = (pos - i0.to(pos.dtype)).unsqueeze(-1)
            lo = self.table.index_select(0, i0)
            hi = self.table.index_select(0, i0 + 1)
            return lo + (hi - lo) * frac  # [num_timesteps, 8], float32

    class PrunedAdaLNModulation(nn.Module):
        """Replaces `MiniMaxH3AdaLayerNormModulation` (transformer_minimax_h3.py L103-131).

        Same output contract -- six `(num_timesteps * 3, hidden_size)` tensors in
        `shift_msa, scale_msa, gate_msa, shift_mlp, scale_mlp, gate_mlp` order, rows laid out as
        `[t0_mod0, t0_mod1, t0_mod2, t1_mod0, ...]` -- but the input is the 8-wide table
        coordinate and there is no SiLU.
        """

        def __init__(self, hidden_size: int, out_dtype):
            super().__init__()
            self.hidden_size = hidden_size
            self.linear = nn.Linear(ADALN_RANK, 6 * hidden_size * 3, bias=True)
            self.out_dtype = out_dtype

        def forward(self, temb):
            m = self.linear(temb.to(self.linear.weight.dtype))
            m = m.view(-1, 6 * self.hidden_size).to(self.out_dtype)
            return m.chunk(6, dim=-1)

    class PrunedAdaLNOut(nn.Module):
        """Replaces `MiniMaxH3AdaLayerNormOut` (transformer_minimax_h3.py L134-157).

        Identical arithmetic (`x = norm(x) * (1 + scale[idx]) + shift[idx]`, shift then scale),
        only the projection is the rank-8 one and the SiLU is gone.
        """

        def __init__(self, hidden_size: int, eps: float, out_dtype):
            super().__init__()
            self.norm = nn.RMSNorm(hidden_size, eps=eps)
            self.linear = nn.Linear(ADALN_RANK, 2 * hidden_size, bias=True)
            self.out_dtype = out_dtype

        def forward(self, hidden_states, temb, timestep_indices):
            shift, scale = self.linear(temb.to(self.linear.weight.dtype)).to(self.out_dtype).chunk(2, dim=-1)
            hidden_states = self.norm(hidden_states)
            return hidden_states * (1.0 + scale.index_select(0, timestep_indices)) + shift.index_select(
                0, timestep_indices
            )

    return AdaLNTableEmbedder, PrunedAdaLNModulation, PrunedAdaLNOut


# ---------------------------------------------------------------------------------------------
# INT8 ConvRot Linear
#
# Format (read out of the safetensors headers, and the rotation recovered by
# scripts/recover-convrot-rotation.py from the fp16/int8 video-VAE pair on disk):
#
#   weight        I8  [out, in]      == round(W R / scale)
#   weight_scale  F32 [out, 1]       per output row, despite the "int8_tensorwise" label
#   comfy_quant   U8  ASCII JSON     {"format":"int8_tensorwise","convrot":true,
#                                     "convrot_groupsize":256}
#
# R is one fixed symmetric +-1/16 Hadamard matrix of order 256, block-diagonal along the input
# axis, identical for every quantized Linear.  Since W' = W R and R is orthogonal,
#
#     y = x W^T + b = (x R) W'^T + b
#
# so the runtime rotates the activation, not the weight.  There is no fused int8 GEMM on XPU
# (torch._int_mm / torch._scaled_mm are CUDA-centric), so the weight is widened to the activation
# dtype per call -- int8 values up to +-127 are exact in bfloat16 -- and the per-row scale is
# applied *after* the accumulation, in float32, which is both cheaper and more accurate than
# scaling the weight first.
# ---------------------------------------------------------------------------------------------


def make_convrot_linear(torch, nn, F):
    class ConvRotLinear(nn.Module):
        def __init__(self, qweight, scale, bias, rotation, group_size: int):
            super().__init__()
            self.register_buffer("qweight", qweight, persistent=False)  # int8 [out, in]
            self.register_buffer("scale", scale, persistent=False)  # float32 [out, 1]
            self.register_buffer("bias", bias, persistent=False)
            self.register_buffer("rotation", rotation, persistent=False)  # [G, G] or None
            self.group_size = group_size
            self.in_features = qweight.shape[1]
            self.out_features = qweight.shape[0]

        def forward(self, x):
            if self.rotation is not None:
                shape = x.shape
                x = x.reshape(*shape[:-1], shape[-1] // self.group_size, self.group_size)
                x = x @ self.rotation.to(x.dtype)
                x = x.reshape(shape)
            y = F.linear(x, self.qweight.to(x.dtype))
            y = (y.float() * self.scale.reshape(1, -1)).to(x.dtype)
            if self.bias is not None:
                y = y + self.bias.to(y.dtype)
            return y

    return ConvRotLinear


# ---------------------------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------------------------


def set_submodule_tensor(root, name: str, value) -> None:
    """Replace a (possibly meta) parameter or buffer by an already-placed tensor.

    Assigning into `_parameters` / `_buffers` directly is deliberate: `nn.Module.__setattr__`
    would reject a plain tensor where a Parameter lives, and `Parameter(...).data = ...` would
    keep the meta storage alive.
    """
    import torch

    parent_path, _, leaf = name.rpartition(".")
    parent = root.get_submodule(parent_path) if parent_path else root
    if leaf in parent._parameters:
        parent._parameters[leaf] = torch.nn.Parameter(value, requires_grad=False)
    elif leaf in parent._buffers:
        parent._buffers[leaf] = value
    else:
        raise KeyError(f"{name} is neither a parameter nor a buffer of {type(parent).__name__}")


def sha256_tensor(t) -> str:
    """SHA-256 of a tensor's raw bytes, in a fixed layout (cpu, contiguous, flattened).

    Reinterpreted as uint8 rather than converted, so bfloat16/float16 hash without a cast and the
    digest is exactly the bytes the tensor holds. This is the bytewise repeat gate.
    """
    import torch

    arr = t.detach().to("cpu").contiguous().flatten()
    if arr.dtype is not torch.uint8:
        arr = arr.view(torch.uint8)
    return hashlib.sha256(memoryview(arr.numpy())).hexdigest()


def gib(n: int) -> str:
    return f"{n / 2**30:.3f} GiB"


@contextlib.contextmanager
def phase(name: str, timings: dict):
    LOG.info("[phase] %s: start", name)
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt = time.perf_counter() - t0
        timings[name] = round(dt, 3)
        LOG.info("[phase] %s: done in %.2f s", name, dt)


def card_memory(torch, devices: list) -> dict:
    out = {}
    for dev in devices:
        out[str(dev)] = {
            "allocated_bytes": int(torch.xpu.memory_allocated(dev)),
            "max_allocated_bytes": int(torch.xpu.max_memory_allocated(dev)),
            "reserved_bytes": int(torch.xpu.memory_reserved(dev)),
            "max_reserved_bytes": int(torch.xpu.max_memory_reserved(dev)),
        }
    return out


def host_rss_bytes() -> int:
    with open("/proc/self/status") as fh:
        for line in fh:
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) * 1024
    return 0


# ---------------------------------------------------------------------------------------------
# Host-memory instrumentation for the load loops
#
# The 2026-09-18 03:05 first light died in `encode.load` with a 15 GiB host (incident:
# ../../qwen38-27b-b70/notes/2026-09-18-host-oomd-incident.md).  Both loaders stream tensor by
# tensor and hold no full state dict, but "holds no state dict" was an argument, not a
# measurement.  These two env switches make the load loops say what they actually cost:
#
#   B70_H3_LOG_MEM=1              log VmRSS / RssAnon / RssFile / MemAvailable every 50 tensors
#                                 (B70_H3_LOG_MEM_EVERY changes the interval)
#   B70_H3_DROP_PAGECACHE=1       posix_fadvise(DONTNEED) the checkpoint every 50 tensors
#                                 (B70_H3_DROP_PAGECACHE_EVERY changes the interval)
#   B70_H3_LOADER=pread|mmap      which tensor reader the load loops use (default pread; see the
#                                 reader section below for what sessions 6/7 measured)
#
# RssAnon is what the loader itself holds; RssFile is the checkpoint's mmap page cache, which is
# reclaimable but whose reclaim is exactly the memory pressure systemd-oomd kills on.  The
# page-cache drop is OFF by default because it is advisory and costs re-reads if a tensor is
# touched twice; `scripts/profile-encoder-load.py --drop-pagecache` is the A/B that says whether
# it is worth turning on for a given card/host.
# ---------------------------------------------------------------------------------------------

LOG_MEM = os.environ.get("B70_H3_LOG_MEM") == "1"
LOG_MEM_EVERY = max(1, int(os.environ.get("B70_H3_LOG_MEM_EVERY", "50")))
DROP_PAGECACHE = os.environ.get("B70_H3_DROP_PAGECACHE") == "1"
DROP_PAGECACHE_EVERY = max(1, int(os.environ.get("B70_H3_DROP_PAGECACHE_EVERY", "50")))


def host_mem_fields() -> dict:
    """VmRSS / VmHWM / RssAnon / RssFile from /proc/self/status, plus MemAvailable, in bytes."""
    want = ("VmRSS", "VmHWM", "RssAnon", "RssFile")
    out = {k: 0 for k in want}
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                key, _, rest = line.partition(":")
                if key in want:
                    out[key] = int(rest.split()[0]) * 1024
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    out["MemAvailable"] = int(line.split()[1]) * 1024
                    break
    except OSError:
        pass
    return out


def log_host_mem(tag: str, index: int, total: int | None = None, force: bool = False) -> None:
    """Log host memory every LOG_MEM_EVERY tensors when B70_H3_LOG_MEM=1."""
    if not LOG_MEM:
        return
    if not force and index % LOG_MEM_EVERY != 0:
        return
    m = host_mem_fields()
    LOG.info(
        "[mem] %s %s: VmRSS %s  anon %s  file %s  hwm %s  MemAvailable %s",
        tag,
        f"{index}/{total}" if total else str(index),
        gib(m.get("VmRSS", 0)),
        gib(m.get("RssAnon", 0)),
        gib(m.get("RssFile", 0)),
        gib(m.get("VmHWM", 0)),
        gib(m.get("MemAvailable", 0)),
    )


def drop_file_pagecache(path: pathlib.Path, index: int) -> None:
    """Advisory page-cache drop for a checkpoint being streamed (B70_H3_DROP_PAGECACHE=1)."""
    if not DROP_PAGECACHE or index % DROP_PAGECACHE_EVERY != 0:
        return
    try:
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(fd)
    except OSError as exc:  # advisory only; never fail a load over it
        LOG.debug("posix_fadvise(DONTNEED) on %s failed: %s", path, exc)


# ---------------------------------------------------------------------------------------------
# Tensor readers -- `pread` (default) and `mmap`
#
# Sessions 6 and 7 (2026-09-18, /mnt/fast-ai/bench-results/minimax-h3-s{6,7}-20260918/) measured
# the old `safe_open` path and it failed the go/no-go rule of
# `notes/2026-09-18-first-light-plan.md`: RssAnon peaked where it should (1.661 GiB encoder,
# 0.499 GiB denoiser -- one tensor's worth) but RssFile tracked every byte touched, 6.291 GiB at a
# 6 GiB budget, i.e. it would reach the whole 27 GB / 40 GB file. `--drop-pagecache` did not help
# (6.352 GiB): `safe_open` keeps the file mapped for the handle's lifetime, and
# `posix_fadvise(DONTNEED)` cannot evict a page that is still mapped. Mapped file pages are
# reclaimable, but reclaiming them under a streaming read is rmap work, and sustained reclaim is
# exactly the memory PRESSURE `systemd-oomd` kills the user's session on
# (../../qwen38-27b-b70/notes/2026-09-18-host-oomd-incident.md).
#
# So the default loader does not map the file at all:
#
#   1. the safetensors header is parsed once (`read_header_and_data_start`);
#   2. each tensor's byte range is `os.pread`-ed into a private buffer;
#   3. `torch.frombuffer(...).view(dtype).reshape(shape)` re-labels that buffer -- no copy, and
#      bit-for-bit what `safe_open(...).get_tensor(...)` returns (safetensors is little-endian and
#      row-major, and so is this host; `test_tensor_reader.py` checks it with `torch.equal`);
#   4. after the caller has copied the tensor to its card, `release()` calls
#      `posix_fadvise(DONTNEED)` on *that range only*, which now works because nothing maps it.
#
# The host cost is therefore one tensor's buffer at a time (plus the converted copy while a dtype
# changes), and RssFile stays flat. `B70_H3_LOADER=mmap` restores the old path for A/B.
#
# A row slice is a contiguous byte range in a row-major tensor, so `get_tensor(key, row_slice)`
# reads only those rows -- the qkv split reads a third of `qkv_proj` three times instead of the
# whole tensor three times.
# ---------------------------------------------------------------------------------------------

LOADER = os.environ.get("B70_H3_LOADER", "pread").strip().lower()
if LOADER not in ("pread", "mmap"):
    raise SystemExit(f"B70_H3_LOADER must be 'pread' or 'mmap', not {LOADER!r}")

# safetensors dtype string -> torch dtype attribute name. Resolved lazily against the live torch:
# this module must import with no torch at all (`--dry-run` is the CPU validation path).
_DTYPE_TORCH = {"BOOL": "bool", "U8": "uint8", "I8": "int8", "F8_E4M3": "float8_e4m3fn",
                "F8_E5M2": "float8_e5m2", "I16": "int16", "U16": "uint16", "F16": "float16",
                "BF16": "bfloat16", "I32": "int32", "U32": "uint32", "F32": "float32",
                "I64": "int64", "U64": "uint64", "F64": "float64"}


def torch_dtype_for(torch, dtype: str):
    """The torch dtype a safetensors dtype string stores, or a clear error."""
    name = _DTYPE_TORCH.get(dtype)
    resolved = getattr(torch, name) if name and hasattr(torch, name) else None
    if resolved is None:
        raise TypeError(f"safetensors dtype {dtype!r} has no torch dtype in this build")
    return resolved


class PreadTensorReader:
    """Read tensors from a safetensors file without ever mapping it.

    Same surface as the `mmap` reader: `get_tensor(key[, row_slice])` returns a CPU tensor with
    exactly the values `safe_open(...).get_tensor(key)` would give, and `release()` drops that
    range from the page cache once the caller is done with it.
    """

    backing = "anon"

    def __init__(self, path: pathlib.Path, header: dict | None = None):
        if sys.byteorder != "little":
            raise RuntimeError("safetensors is little-endian; this reader needs a little-endian host")
        self.path = pathlib.Path(path)
        parsed, data_start = read_header_and_data_start(self.path)
        self.header = parsed if header is None else header
        self._data_start = data_start
        self.fd = os.open(str(self.path), os.O_RDONLY)

    def __enter__(self) -> "PreadTensorReader":
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False

    def close(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def keys(self) -> list[str]:
        return list(self.header)

    def _range(self, key: str, row_slice: tuple[int, int] | None):
        """(absolute file offset, byte count, shape) of `key`, or of its leading-row slice."""
        entry = self.header[key]
        begin, end = entry["data_offsets"]
        shape = list(entry["shape"])
        if row_slice is not None:
            if not shape:
                raise ValueError(f"{key} is 0-dimensional; it has no rows to slice")
            rows = shape[0]
            if rows == 0:
                raise ValueError(f"{key} has zero rows")
            row_bytes = (end - begin) // rows
            lo, hi = row_slice
            begin, end = begin + lo * row_bytes, begin + hi * row_bytes
            shape[0] = hi - lo
        return self._data_start + begin, end - begin, shape

    def get_tensor(self, key: str, row_slice: tuple[int, int] | None = None):
        import torch

        offset, nbytes, shape = self._range(key, row_slice)
        dtype = torch_dtype_for(torch, self.header[key]["dtype"])
        if nbytes == 0:  # torch.frombuffer refuses an empty buffer
            return torch.empty(shape, dtype=dtype)
        buf = bytearray(nbytes)
        view = memoryview(buf)
        got = 0
        while got < nbytes:  # pread may return short, on any filesystem
            n = os.preadv(self.fd, [view[got:]], offset + got)
            if n == 0:
                raise EOFError(f"{self.path}: short read for {key} ({got}/{nbytes} bytes)")
            got += n
        # frombuffer keeps `buf` alive for the tensor's lifetime and copies nothing; `.view()`
        # re-labels the same bytes, which is what the mmap path hands out too.
        return torch.frombuffer(buf, dtype=torch.uint8).view(dtype).reshape(shape)

    def release(self, key: str, row_slice: tuple[int, int] | None = None) -> None:
        """Drop this tensor's page-cache range. Nothing maps it, so this actually frees it."""
        offset, nbytes, _ = self._range(key, row_slice)
        if nbytes <= 0:
            return
        try:
            os.posix_fadvise(self.fd, offset, nbytes, os.POSIX_FADV_DONTNEED)
        except OSError as exc:  # advisory only; never fail a load over it
            LOG.debug("posix_fadvise(DONTNEED) on %s[%s] failed: %s", self.path, key, exc)


class MmapTensorReader:
    """The old `safetensors.safe_open` path, kept for A/B (`B70_H3_LOADER=mmap`).

    `release()` is a no-op on purpose: the file stays mapped for the handle's lifetime, so a
    per-range `posix_fadvise(DONTNEED)` frees nothing (sessions 6/7 measured exactly that). The
    whole-file `B70_H3_DROP_PAGECACHE=1` drop is the only thing this path has, and it is why
    RssFile still climbs with it.
    """

    backing = "mmap"

    def __init__(self, path: pathlib.Path, header: dict | None = None):
        from safetensors import safe_open

        self.path = pathlib.Path(path)
        self.header = read_header(self.path) if header is None else header
        self._fh = safe_open(str(self.path), framework="pt")

    def __enter__(self) -> "MmapTensorReader":
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False

    def close(self) -> None:
        self._fh = None

    def keys(self) -> list[str]:
        return list(self.header)

    def get_tensor(self, key: str, row_slice: tuple[int, int] | None = None):
        t = self._fh.get_tensor(key)
        return t if row_slice is None else t[row_slice[0] : row_slice[1]]

    def release(self, key: str, row_slice: tuple[int, int] | None = None) -> None:
        return None


def open_tensor_reader(path: pathlib.Path, header: dict | None = None, loader: str | None = None):
    """Open `path` with the configured loader (`B70_H3_LOADER`, default `pread`)."""
    chosen = (loader or LOADER).strip().lower()
    if chosen == "mmap":
        return MmapTensorReader(path, header)
    if chosen == "pread":
        return PreadTensorReader(path, header)
    raise ValueError(f"unknown loader {chosen!r}; use 'pread' or 'mmap'")


# ---------------------------------------------------------------------------------------------
# Phase 1 -- text encoder
# ---------------------------------------------------------------------------------------------


def encode_prompt(args, timings: dict) -> "tuple":
    """Run the Qwen3-VL-32B INT8 ConvRot conditioner on one card, return (embeds, token_tags).

    MiniMax-H3 conditions on the *unnormalized* hidden state after decoder layer 50 -- not the
    final one (diffusers `MiniMaxH3ModularPipeline.text_encoder_layer`, and the Comfy repackage's
    own `__metadata__`: `{"num_hidden_layers": 50, "output": "unnormalized_hidden_after_layer_50"}`).
    The file holds exactly `model.layers.0..49`, no final norm and no `lm_head`, so a 50-layer
    stack read at its last hidden state *is* that quantity.

    Presentation for `t2va` is the prompt verbatim: no chat template, no special tokens
    (encoders.py `MiniMaxH3TextEncoderStep.__call__`).
    """
    import torch
    from transformers import AutoConfig, AutoTokenizer

    device = torch.device(f"xpu:{args.encoder_card}")

    with phase("encode.tokenize", timings):
        tokenizer = AutoTokenizer.from_pretrained(str(TOKENIZER_DIR))
        token_ids = tokenizer(args.prompt, add_special_tokens=False)["input_ids"]
        LOG.info("prompt tokenizes to %d rows", len(token_ids))

    with phase("encode.load", timings):
        config = AutoConfig.from_pretrained(str(TEXT_ENCODER_DIR))
        # MiniMax-H3 conditions on `hidden_states[50]` of the *64-layer* Qwen3-VL, i.e. the
        # UNNORMALIZED output of decoder layer 50 -- transformers' `hidden_states[i]` for
        # `i < num_layers` is the input to layer `i`, so on the full stack that index is exactly
        # "after layer 50, before the final norm".  Layers 50..63 and the LM head are dead weight
        # and the Comfy repackage ships neither them nor `model.norm.weight`.
        #
        # So: build a 50-layer stack AND neutralize its final norm.  Then `last_hidden_state` is
        # that same quantity -- with no truncated tail to run and no 51-entry hidden-state tuple
        # to hold (that tuple alone is ~0.5 GB for a 1k-token Context-IR prompt).
        config.text_config.num_hidden_layers = 50
        model = _build_text_encoder(torch, config, device, args)

    with phase("encode.forward", timings):
        input_ids = torch.tensor([token_ids], dtype=torch.long, device=device)
        attention_mask = torch.ones_like(input_ids)
        # `mm_token_type_ids` is Qwen-internal (0 text / 1 image / 2 video) and drives the
        # per-modality rotary layout; a `t2va` presentation is all text, so it is all zeros.
        # (diffusers builds it with `processor.create_mm_token_type_ids`, encoders.py L72.)
        kwargs = dict(input_ids=input_ids, attention_mask=attention_mask, use_cache=False)
        try:
            out = model.model(**kwargs, mm_token_type_ids=torch.zeros_like(input_ids))
        except TypeError:
            LOG.warning("this transformers build does not take `mm_token_type_ids`; retrying without it")
            out = model.model(**kwargs)
        embeds = out.last_hidden_state.to(device=device, dtype=torch.bfloat16).clone()

    del model, out
    _free(torch)
    tags = torch.full((len(token_ids),), 1, dtype=torch.long)  # MINIMAX_H3_TEXT_TAG == 1
    return embeds, tags, token_ids


def _build_text_encoder(torch, config, device, args):
    """Instantiate Qwen3-VL on meta, then stream the INT8 ConvRot file onto `device`."""
    import torch.nn as nn
    import torch.nn.functional as F
    from transformers import Qwen3VLForConditionalGeneration

    ConvRotLinear = make_convrot_linear(torch, nn, F)

    with torch.device("meta"):
        model = Qwen3VLForConditionalGeneration(config)
    model.eval()

    header = read_header(INT8_TEXT_ENCODER)
    quantized = {k[: -len(".comfy_quant")] for k in header if k.endswith(".comfy_quant")}
    group_size = 256
    rotation = None
    if args.te_rotation == "hadamard256":
        if not CONVROT_ROTATION.exists():
            raise FileNotFoundError(
                f"{CONVROT_ROTATION} is missing. Regenerate it with scripts/recover-convrot-rotation.py "
                "(CPU-only), or pass --te-rotation none to A/B the unrotated path."
            )
        with open_tensor_reader(CONVROT_ROTATION) as fh:
            signs = fh.get_tensor("convrot_signs")
        rotation = (signs.to(torch.float32) / math.sqrt(group_size)).to(device=device, dtype=torch.bfloat16)

    # The checkpoint uses the upstream Qwen3-VL names (`model.layers.N.*`, `visual.*`); a
    # transformers build may expose them under `model.language_model.*` / `model.visual.*`.
    # Detect rather than assume.
    live = set(dict(model.named_parameters()).keys()) | set(dict(model.named_buffers()).keys())
    lang_prefix = "model.language_model." if any(k.startswith("model.language_model.") for k in live) else "model."
    vis_prefix = "model.visual." if any(k.startswith("model.visual.") for k in live) else "visual."
    LOG.info("text encoder prefixes: language=%r visual=%r", lang_prefix, vis_prefix)

    def to_live(key: str) -> str:
        if key.startswith("visual."):
            return vis_prefix + key[len("visual.") :]
        if key.startswith("model."):
            return lang_prefix + key[len("model.") :]
        return key

    loaded = 0
    LOG.info("text encoder loader: %s (B70_H3_LOADER)", LOADER)
    with open_tensor_reader(INT8_TEXT_ENCODER, header) as fh:
        # 1. Plain tensors.
        for key in header:
            if key.endswith((".comfy_quant", ".weight_scale")):
                continue
            base = key[: -len(".weight")] if key.endswith(".weight") else None
            if base is not None and base in quantized:
                continue  # handled below
            name = to_live(key)
            if name not in live:
                LOG.debug("skipping unmatched checkpoint key %s", key)
                continue
            # `get_tensor` hands back one tensor's worth of host bytes (a private buffer on the
            # pread loader, a view on the mapping on the mmap one); `.to()` allocates on the card
            # and reads every source byte.  `del t` hands our reference to the device tensor
            # straight back -- the module owns it now -- and drops the host buffer with it, so
            # nothing host-side survives this iteration.  `release` then drops that byte range
            # from the page cache (a no-op on the mmap loader, which cannot).
            t = fh.get_tensor(key).to(device=device)
            set_submodule_tensor(model, name, t)
            del t
            fh.release(key)
            loaded += 1
            log_host_mem("encode.load", loaded, len(header))
            drop_file_pagecache(INT8_TEXT_ENCODER, loaded)

        # 2. Quantized Linears -> ConvRotLinear.
        for base in sorted(quantized):
            name = to_live(base)
            parent_path, _, leaf = name.rpartition(".")
            try:
                parent = model.get_submodule(parent_path)
            except AttributeError:
                LOG.warning("no module at %s for quantized %s; skipping", parent_path, base)
                continue
            old = getattr(parent, leaf)
            bias = None
            if getattr(old, "bias", None) is not None and base + ".bias" in header:
                bias = fh.get_tensor(base + ".bias").to(device=device, dtype=torch.bfloat16)
            qw = fh.get_tensor(base + ".weight").to(device=device)
            sc = fh.get_tensor(base + ".weight_scale").to(device=device, dtype=torch.float32)
            setattr(parent, leaf, ConvRotLinear(qw, sc, bias, rotation, group_size))
            del qw, sc, bias  # the ConvRotLinear buffers own them now; drop our host-side names
            for suffix in (".bias", ".weight", ".weight_scale"):
                if base + suffix in header:
                    fh.release(base + suffix)
            loaded += 1
            log_host_mem("encode.load", loaded, len(header))
            drop_file_pagecache(INT8_TEXT_ENCODER, loaded)

    # The checkpoint carries no final norm (see the `hidden_states[50]` note in `encode_prompt`).
    # Assert that, then make the norm an identity so `last_hidden_state` is the unnormalized state.
    if any(k in header for k in ("model.norm.weight", "model.language_model.norm.weight")):
        raise RuntimeError(
            "this text-encoder checkpoint DOES carry a final norm, so the unnormalized-after-layer-50 "
            "assumption is wrong for it; re-derive the conditioning before going further"
        )
    lm_path = "model.language_model" if lang_prefix.endswith("language_model.") else "model"
    language_model = model.get_submodule(lm_path)
    if isinstance(getattr(language_model, "norm", None), nn.Module):
        LOG.info("neutralizing %s.norm (the conditioning is the unnormalized hidden state)", lm_path)
        language_model.norm = nn.Identity()
    else:
        raise RuntimeError(f"could not find the final norm at {lm_path}.norm; inspect the model layout")

    log_host_mem("encode.load", loaded, len(header), force=True)
    LOG.info("text encoder: placed %d tensors (%d quantized Linears) on %s", loaded, len(quantized), device)
    leftover = [n for n, p in model.named_parameters() if p.device.type == "meta"]
    leftover += [n for n, b in model.named_buffers() if b.device.type == "meta"]
    leftover = [n for n in leftover if not n.startswith(("lm_head",))]
    if leftover:
        LOG.warning("text encoder has %d tensors still on meta, e.g. %s", len(leftover), leftover[:8])
    return model


def _free(torch) -> None:
    """Drop Python references, then hand the cached blocks back to the driver."""
    import gc

    gc.collect()
    torch.xpu.empty_cache()
    torch.xpu.synchronize()


# ---------------------------------------------------------------------------------------------
# Phase 2 -- the pruned denoiser, split across two cards
# ---------------------------------------------------------------------------------------------


def load_sharded_transformer(args, plan: SplitPlan, config: dict, timings: dict):
    import torch
    import torch.nn as nn
    from diffusers import MiniMaxH3Transformer3DModel

    primary = torch.device(f"xpu:{args.cards[0]}")
    secondary = torch.device(f"xpu:{args.cards[1]}")
    AdaLNTableEmbedder, PrunedAdaLNModulation, PrunedAdaLNOut = make_pruned_adaln_modules(torch, nn)
    block_dtype = torch.bfloat16
    adaln_out_dtype = torch.float32 if args.adaln_out_dtype == "fp32" else torch.bfloat16

    with phase("load.skeleton", timings):
        # Everything here is built on `meta`: no host allocation, no init, nothing to page.
        with torch.device("meta"):
            model = MiniMaxH3Transformer3DModel.from_config(config)
            # Install the pruned AdaLN form.  `time_proj` becomes an identity and `time_embedder`
            # becomes the table lerp, so the stock `forward` (L641-642) needs no patching at all.
            model.time_proj = nn.Identity()
            for block in model.transformer_blocks:
                block.adaln_proj = PrunedAdaLNModulation(HIDDEN_SIZE, adaln_out_dtype)
            model.norm_out = PrunedAdaLNOut(HIDDEN_SIZE, config["final_norm_eps"], adaln_out_dtype)
        model.eval()

    header = read_header(PRUNED_DENOISER)
    remap = build_remap(config["num_layers"], config["num_refiner_layers"])

    def device_for(name: str):
        if name.startswith("transformer_blocks."):
            return primary if int(name.split(".")[1]) < plan.split_index else secondary
        return primary

    with phase("load.stream", timings):
        LOG.info("denoiser loader: %s (B70_H3_LOADER)", LOADER)
        with open_tensor_reader(PRUNED_DENOISER, header) as fh:
            table = fh.get_tensor("adaln_t_table").to(device=primary, dtype=torch.float32)
            model.time_embedder = AdaLNTableEmbedder(table)
            fh.release("adaln_t_table")
            placed = 0
            for name, src in remap.items():
                dev = device_for(name)
                # A row slice is a contiguous byte range, so the pread loader reads only those
                # rows: the qkv split reads a third of `qkv_proj` three times, not the whole
                # tensor three times.  The mmap loader slices the view, exactly as before.
                t = fh.get_tensor(src.key, src.row_slice)
                if src.swap_halves:
                    half = t.shape[0] // 2
                    t = torch.cat((t[half:], t[:half]), dim=0)
                t = t.to(device=dev, dtype=target_dtype(name, args.adaln_dtype)).contiguous()
                set_submodule_tensor(model, name, t)
                del t  # the module owns the device tensor; drop the host-side name and the buffer
                fh.release(src.key, src.row_slice)
                placed += 1
                if placed % 100 == 0:
                    LOG.info("  placed %d/%d tensors (host peak RSS %s)", placed, len(remap), gib(host_rss_bytes()))
                log_host_mem("load.stream", placed, len(remap))
                drop_file_pagecache(PRUNED_DENOISER, placed)
        log_host_mem("load.stream", placed, len(remap), force=True)
        # `rope.inv_freq` is non-persistent and recomputed from the config, not loaded
        # (transformer_minimax_h3.py L88-91).  Rebuild it on the primary card and cross-check.
        freq_dim = config["rope_freq_dim"]
        inv_freq = 1.0 / (
            config["rope_theta"] ** (torch.arange(0, 2 * freq_dim, 2, dtype=torch.float32) / (2 * freq_dim))
        )
        set_submodule_tensor(model, "rope.inv_freq", inv_freq.to(primary))
        with open_tensor_reader(PRUNED_DENOISER, header) as fh:
            stored = fh.get_tensor("rope.inv_freq").float()
            fh.release("rope.inv_freq")
        drift = (stored - inv_freq).abs().max().item()
        LOG.info("rope.inv_freq recomputed; max drift vs checkpoint copy = %.3e", drift)
        if drift > 1e-6:
            raise RuntimeError(f"recomputed rope.inv_freq disagrees with the checkpoint by {drift:.3e}")

    # Residency gate: the LTX lane's ON_PRE_RUN check, run once here.
    stragglers = [n for n, p in model.named_parameters() if p.device.type != "xpu"]
    stragglers += [n for n, b in model.named_buffers() if b.device.type != "xpu"]
    if stragglers:
        raise RuntimeError(f"denoiser is not fully resident on the cards: {stragglers[:10]}")

    _install_boundary_hooks(torch, model, plan.split_index, primary, secondary)
    LOG.info(
        "denoiser split at block %d: %s on %s, %s on %s",
        plan.split_index,
        gib(plan.card0_bytes),
        primary,
        gib(plan.card1_bytes),
        secondary,
    )
    return model, primary, secondary


def _install_boundary_hooks(torch, model, split_index: int, primary, secondary) -> None:
    """Move the per-forward tensors across the PCIe boundary exactly once.

    `hidden_states` flows block to block, so it crosses once on its own.  `temb`, `adaln_indices`
    and the two `rope` outputs are read by *every* block from the model's forward frame, so each
    secondary block would pull them across again -- hence the per-forward transfer cache, which is
    the same device-crossing policy as `ltx_layer_shard.py::_move` / `_forward_transfers`.
    """
    cache: dict = {}

    def move(value):
        if isinstance(value, torch.Tensor):
            if value.device == secondary:
                return value
            key = id(value)
            if key not in cache:
                cache[key] = (value, value.to(secondary, non_blocking=False))
            return cache[key][1]
        if isinstance(value, tuple):
            return tuple(move(v) for v in value)
        if isinstance(value, list):
            return [move(v) for v in value]
        return value

    def reset(_module, _args):
        cache.clear()

    model.register_forward_pre_hook(reset)

    def pre_hook(_module, args):
        return tuple(move(a) for a in args)

    def post_hook(_module, _args, output):
        return output.to(primary, non_blocking=False) if isinstance(output, torch.Tensor) else output

    blocks = model.transformer_blocks
    for block in list(blocks)[split_index:]:
        block.register_forward_pre_hook(pre_hook)
    blocks[len(blocks) - 1].register_forward_hook(post_hook)


# ---------------------------------------------------------------------------------------------
# Phases 3-4 -- sampling and decoding through the diffusers modular blocks
# ---------------------------------------------------------------------------------------------


def build_pipeline(args, transformer, timings: dict):
    """Assemble the core denoise chain over locally loaded components.

    The full `MiniMaxH3Blocks` chain also owns the text encoder, the VAE *encoder* and the two
    decode blocks.  None of them belongs here: the prompt is already encoded and freed, `t2va` has
    no visual conditioning, and the decode has to happen *after* the denoiser is freed, or the
    cards hold 37 GiB of denoiser and 5 GiB of VAE at once.  So the pipeline stops at the latents
    and this script decodes by hand, mirroring `decoders.py` step for step.

    `MiniMaxH3CoreDenoiseStep` (modular_blocks_minimax_h3.py L234-290) is itself the sequence
    no_keyframe_anchors -> prepare_layout -> prepare_latents -> set_timesteps -> denoise ->
    after_denoise, so the packed-sequence layout, the three noise draws from the one generator,
    the per-row timestep plan and the row unpacking all stay upstream code.
    """
    from diffusers import MiniMaxH3Scheduler
    from diffusers.modular_pipelines.minimax_h3.modular_blocks_minimax_h3 import MiniMaxH3CoreDenoiseStep

    with phase("sample.build_pipeline", timings):
        pipe = MiniMaxH3CoreDenoiseStep().init_pipeline()
        pipe.update_components(
            transformer=transformer,
            scheduler=MiniMaxH3Scheduler.from_pretrained(str(SCHEDULER_DIR)),
            audio_scheduler=MiniMaxH3Scheduler.from_pretrained(str(AUDIO_SCHEDULER_DIR)),
        )
    return pipe


def load_vaes(args, timings: dict):
    """Load the two VAEs onto one card.  Called only after the denoiser has been freed."""
    import torch
    from diffusers import AutoencoderKLMiniMaxH3, AutoencoderKLMiniMaxH3Audio

    device = torch.device(f"xpu:{args.cards[0]}")
    with phase("decode.load_vae", timings):
        # The original repo ships both VAEs as float32 diffusers checkpoints.  The video VAE runs
        # in float16 (the decode block's own autocast intent, decoders.py L187-188); the audio VAE
        # stays float32, which is what its 0.6 GB costs.
        vae = AutoencoderKLMiniMaxH3.from_pretrained(str(VAE_DIR), torch_dtype=torch.float16).to(device).eval()
        audio_vae = AutoencoderKLMiniMaxH3Audio.from_pretrained(str(AUDIO_VAE_DIR), torch_dtype=torch.float32)
        audio_vae = audio_vae.to(device).eval()
    return vae, audio_vae, device


# ---------------------------------------------------------------------------------------------
# Phase 5 -- mp4 + receipt
# ---------------------------------------------------------------------------------------------


def write_mp4(path: pathlib.Path, frames, audio, fps: int, sample_rate: int, crf: int) -> None:
    """Mux the decoded frames and waveform into one mp4 (H.264 + AAC).

    `frames` is `(T, H, W, 3)` uint8, `audio` is `(2, num_samples)` float32 in [-1, 1].
    The mp4 is the human-facing artifact; the exactness gate is the SHA-256 in the sidecar, taken
    on the *pre-encode* tensors, because H.264 and AAC are both lossy.
    """
    from fractions import Fraction

    import av
    import numpy as np

    container = av.open(str(path), mode="w")
    height, width = frames.shape[1], frames.shape[2]
    video_stream = container.add_stream("libx264", rate=fps)
    video_stream.width, video_stream.height = width, height
    video_stream.pix_fmt = "yuv420p"
    video_stream.options = {"crf": str(crf)}
    audio_stream = container.add_stream("aac", rate=sample_rate)
    audio_stream.layout = "stereo"

    for i in range(frames.shape[0]):
        frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(frames[i]), format="rgb24")
        for packet in video_stream.encode(frame):
            container.mux(packet)
    for packet in video_stream.encode():
        container.mux(packet)

    planar = np.ascontiguousarray(audio.astype(np.float32))  # (2, N), fltp is planar
    chunk = 8192
    for start in range(0, planar.shape[1], chunk):
        block = np.ascontiguousarray(planar[:, start : start + chunk])
        aframe = av.AudioFrame.from_ndarray(block, format="fltp", layout="stereo")
        aframe.sample_rate = sample_rate
        aframe.time_base = Fraction(1, sample_rate)
        aframe.pts = start
        for packet in audio_stream.encode(aframe):
            container.mux(packet)
    for packet in audio_stream.encode():
        container.mux(packet)
    container.close()


def file_digest(path: pathlib.Path, limit: int | None = None) -> str:
    """SHA-256 of a file, or of its first `limit` bytes (the safetensors header region)."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        remaining = limit
        while True:
            want = 1 << 20 if remaining is None else min(1 << 20, remaining)
            if want <= 0:
                break
            chunk = fh.read(want)
            if not chunk:
                break
            h.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------


DEFAULT_PROMPT = (
    "A slow dolly-in on a rain-slicked city street at night; neon signs reflect in the puddles, "
    "a lone figure with an umbrella walks away from camera. Ambient rain, distant traffic, "
    "a low synth drone."
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--prompt", default=DEFAULT_PROMPT, help="the request's prompt, a single string")
    p.add_argument(
        "--prompt-embeds",
        type=pathlib.Path,
        default=None,
        help="a precomputed prompt embedding (.safetensors with `prompt_embeds` [1, N, 5120] and "
        "optionally `text_token_tags`). Skips phase 1 entirely -- use this if the INT8 encoder "
        "path is not trusted yet, or to hold the conditioning fixed across denoiser experiments.",
    )
    p.add_argument("--height", type=int, default=None, help="multiple of 32; default = MiniMax-H3's own canvas")
    p.add_argument("--width", type=int, default=None, help="multiple of 32; default = MiniMax-H3's own canvas")
    p.add_argument(
        "--frames",
        type=int,
        default=124,
        help="frames at 24 fps; snapped up to the next 17n+5 the video VAE can decode. 124 (5.167 s) "
        "is the smallest legal clip.",
    )
    p.add_argument(
        "--steps",
        type=int,
        default=50,
        help="num_inference_steps. THE REAL DEFAULT IS UNKNOWN: no file on this host and no diffusers "
        "block declares one (the H3 blocks mark it required with no default). 50 here is the generic "
        "diffusers template value, i.e. a guess -- resolve it in the first GPU session.",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--video-shift", type=float, default=None, help="override the video scheduler shift (default 12.0)")
    p.add_argument("--audio-shift", type=float, default=None, help="override the audio scheduler shift (default 3.0)")
    p.add_argument("--cards", type=int, nargs=2, default=[0, 1], help="the two XPU indices for the denoiser")
    p.add_argument("--encoder-card", type=int, default=0, help="card the text encoder runs on, alone")
    p.add_argument("--split-index", type=int, default=None, help="force the block split instead of balancing bytes")
    p.add_argument(
        "--adaln-dtype",
        choices=["fp32", "bf16"],
        default="fp32",
        help="storage dtype of the rank-8 AdaLN projections. fp32 mirrors ComfyUI's adaln_dtype=float32.",
    )
    p.add_argument(
        "--adaln-out-dtype",
        choices=["bf16", "fp32"],
        default="bf16",
        help="dtype the modulation is cast to before it multiplies the residual stream. bf16 matches the "
        "unpruned checkpoint (its adaln_proj is bf16); fp32 keeps the projection's precision but "
        "promotes the whole packed sequence to float32. A/B this on the first GPU session.",
    )
    p.add_argument(
        "--te-rotation",
        choices=["hadamard256", "none"],
        default="hadamard256",
        help="the ConvRot activation rotation. `hadamard256` uses data/convrot-hadamard-256.safetensors, "
        "recovered from the fp16/int8 video-VAE pair on disk; `none` is the A/B control and will "
        "produce garbage if the rotation is real.",
    )
    p.add_argument("--out-dir", type=pathlib.Path, default=pathlib.Path("/mnt/fast-ai/bench-results/minimax-h3"))
    p.add_argument("--run-name", default=None, help="subdirectory name; default is a UTC timestamp")
    p.add_argument("--crf", type=int, default=16, help="x264 quality for the mp4 (the receipt hashes are exact)")
    p.add_argument("--save-tensors", action="store_true", help="also write the raw decoded tensors as safetensors")
    p.add_argument("--deterministic", action="store_true", help="torch.use_deterministic_algorithms(True), fail closed")
    p.add_argument("--dry-run", action="store_true", help="CPU only: configs + headers, print the split plan, exit")
    p.add_argument("--verify-remap", action="store_true", help="dry-run extra: check the key remap against the full BF16 checkpoint")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


# ---------------------------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------------------------


def dry_run(args) -> int:
    """Configs + safetensors headers only. No torch.xpu, no diffusers, no device tensor."""
    config = json.loads(TRANSFORMER_CONFIG.read_text())
    print("=" * 96)
    print("MiniMax-H3 two-B70 pipeline -- DRY RUN (CPU only, headers only, nothing placed)")
    print("=" * 96)

    for label, path in [
        ("pruned denoiser", PRUNED_DENOISER),
        ("int8 text encoder", INT8_TEXT_ENCODER),
        ("video vae (fp32 repo)", VAE_DIR / "diffusion_pytorch_model.safetensors.index.json"),
        ("audio vae (fp32 repo)", AUDIO_VAE_DIR / "diffusion_pytorch_model.safetensors"),
        ("convrot rotation", CONVROT_ROTATION),
    ]:
        ok = path.exists()
        size = path.stat().st_size if ok else 0
        print(f"  {'OK ' if ok else 'MISSING'} {label:24s} {size / 1e9:8.2f} GB  {path}")
    print()

    header = read_header(PRUNED_DENOISER)
    print(f"denoiser header: {len(header)} tensors, {sum(tensor_bytes(e) for e in header.values()) / 1e9:.2f} GB stored")

    # Every diffusers parameter must be reachable from the checkpoint.
    remap = build_remap(config["num_layers"], config["num_refiner_layers"])
    missing = sorted({s.key for s in remap.values()} - set(header))
    if missing:
        print(f"  FAIL: {len(missing)} remapped source keys are absent, e.g. {missing[:5]}")
        return 1
    consumed = {s.key for s in remap.values()} | {"adaln_t_table", "rope.inv_freq"}
    unconsumed = sorted(set(header) - consumed)
    print(f"  remap covers {len(remap)} diffusers parameters from {len(consumed)} checkpoint tensors")
    print(f"  checkpoint tensors not consumed: {len(unconsumed)}{' -> ' + str(unconsumed[:5]) if unconsumed else ''}")
    table = header["adaln_t_table"]
    print(f"  adaln_t_table: {table['dtype']} {table['shape']}  (grid of {table['shape'][0] - 1} + terminal row)")
    print()

    plan = plan_split(header, config, args.adaln_dtype, args.split_index)
    print("layer split (LTX byte-balancing policy, ltx_layer_shard.py::install):")
    print(f"  blocks                : {plan.num_layers}")
    print(f"  per-block bytes       : min {plan.block_bytes[0] / 1e6:.1f} MB, max {max(plan.block_bytes) / 1e6:.1f} MB")
    print(f"  non-block bytes       : {plan.non_block_bytes / 1e9:.3f} GB ({gib(plan.non_block_bytes)})")
    print(f"  split_index           : {plan.split_index}  -> blocks 0..{plan.split_index - 1} | {plan.split_index}..{plan.num_layers - 1}")
    print(f"  card {args.cards[0]} (primary)      : {plan.card0_bytes / 1e9:8.3f} GB  {gib(plan.card0_bytes)}")
    print(f"  card {args.cards[1]} (secondary)    : {plan.card1_bytes / 1e9:8.3f} GB  {gib(plan.card1_bytes)}")
    print(f"  imbalance             : {abs(plan.card0_bytes - plan.card1_bytes) / 1e6:.1f} MB")
    print(f"  free per card (32 GiB): {gib(32 * 2**30 - plan.card0_bytes)} / {gib(32 * 2**30 - plan.card1_bytes)}")
    print()

    te_header = read_header(INT8_TEXT_ENCODER)
    quantized = {k for k in te_header if k.endswith(".comfy_quant")}
    te_bytes = sum(tensor_bytes(e) for k, e in te_header.items() if not k.endswith(".comfy_quant"))
    print("text encoder (phase 1, alone on one card, freed before the denoiser loads):")
    print(f"  tensors               : {len(te_header)}  ({len(quantized)} ConvRot Linears)")
    print(f"  resident bytes        : {te_bytes / 1e9:.3f} GB  {gib(te_bytes)}")
    print(f"  free after load       : {gib(32 * 2**30 - te_bytes)}")
    largest = max((tensor_bytes(e), k) for k, e in te_header.items() if e["dtype"] == "I8")
    print(f"  largest dequant buffer: {largest[1]} -> {largest[0] * 2 / 1e6:.1f} MB in bf16")
    print(f"  rotation file         : {'present' if CONVROT_ROTATION.exists() else 'MISSING'} ({args.te_rotation})")
    print()

    # Geometry of the requested clip, from the configs only.
    vae_cfg = json.loads((VAE_DIR / "config.json").read_text())
    audio_cfg = json.loads((AUDIO_VAE_DIR / "config.json").read_text())
    frames = args.frames
    clip_len, token_drop = vae_cfg["clip_length"], 5
    while frames % clip_len != token_drop:
        frames += 1
    latent_frames = (frames - token_drop) // clip_len * token_drop + 2
    spatial = 1
    for f in vae_cfg["spatial_downsample_factors"]:
        spatial *= f
    patch = config["patch_size"]
    height, width = args.height, args.width
    if height is None or width is None:
        height, width = 768, 1344  # resolve_canvas_size(16, 9, 32, 768, 1032192), modular_pipeline.py L40-96
    rows_video = (latent_frames // patch[0]) * (height // spatial // patch[1]) * (width // spatial // patch[2])
    audio_rows = int(round(frames / 24 * 40)) * 2
    print("requested clip:")
    print(f"  frames                : {args.frames} -> {frames} (17n+5), {frames / 24:.3f} s at 24 fps")
    print(f"  canvas                : {height} x {width}  (latent {height // spatial} x {width // spatial})")
    print(f"  latent frames         : {latent_frames}")
    print(f"  video rows            : {rows_video}")
    print(f"  audio rows            : {audio_rows} ({audio_cfg['sampling_rate']} Hz stereo)")
    print(f"  packed sequence       : {rows_video + audio_rows} + text rows")
    print(f"  steps                 : {args.steps}  <-- ASSUMED, the real default is unknown")
    print(f"  schedulers            : video shift {json.loads((SCHEDULER_DIR / 'scheduler_config.json').read_text())['shift']}, "
          f"audio shift {json.loads((AUDIO_SCHEDULER_DIR / 'scheduler_config.json').read_text())['shift']}, cfg-free")
    print()

    if args.verify_remap:
        rc = verify_remap_against_full(config)
        if rc:
            return rc

    print("dry run complete: no GPU touched, no service touched, nothing downloaded.")
    return 0


def verify_remap_against_full(config: dict) -> int:
    """Compare a sample of remapped tensors against the full BF16 diffusers checkpoint.

    The pruned build only replaces the AdaLN branch, so every non-AdaLN tensor must be identical.
    This is what pinned the qkv split order and the SwiGLU half order.  Needs `safetensors` only.
    """
    from safetensors import safe_open

    index_path = REPO_ORIGINAL / "transformer" / "diffusion_pytorch_model.safetensors.index.json"
    if not index_path.exists():
        print("  (skipping --verify-remap: the full BF16 checkpoint is not on this host)")
        return 0
    weight_map = json.loads(index_path.read_text())["weight_map"]
    remap = build_remap(config["num_layers"], config["num_refiner_layers"])
    handles: dict[str, object] = {}

    def full_slice(name: str):
        shard = weight_map[name]
        if shard not in handles:
            handles[shard] = safe_open(str(REPO_ORIGINAL / "transformer" / shard), framework="pt")
        return handles[shard].get_slice(name)

    import torch

    pruned = safe_open(str(PRUNED_DENOISER), framework="pt")
    sample = [
        "proj_in.weight",
        "audio_proj_in.weight",
        "context_embedder.weight",
        "transformer_blocks.0.attn.to_q.weight",
        "transformer_blocks.0.attn.to_k.weight",
        "transformer_blocks.0.attn.to_v.weight",
        "transformer_blocks.0.attn.to_out.0.weight",
        "transformer_blocks.0.ff.net.0.proj.weight",
        "transformer_blocks.0.ff.net.2.weight",
        "transformer_blocks.49.ff.net.0.proj.weight",
        "token_refiner.refiner_blocks.1.ff.net.0.proj.weight",
        "norm_out.norm.weight",
        "proj_out.weight",
        "audio_proj_out.weight",
    ]
    print("remap verification against the full BF16 checkpoint (first 64 input columns):")
    failures = 0
    for name in sample:
        if name not in weight_map:
            continue
        src = remap[name]
        t = pruned.get_slice(src.key)
        lo, hi = src.row_slice if src.row_slice else (0, t.get_shape()[0])
        a = t[lo:hi]
        if src.swap_halves:
            half = a.shape[0] // 2
            a = torch.cat((a[half:], a[:half]), dim=0)
        a = a[:, :64] if a.ndim == 2 else a
        b = full_slice(name)
        b = b[:, :64] if len(b.get_shape()) == 2 else b[:]
        ok = a.shape == b.shape and torch.equal(a, b)
        failures += 0 if ok else 1
        print(f"  {'EXACT ' if ok else 'DIFFER'} {name:52s} <- {src.key}")
    print(f"  {len(sample) - failures}/{len(sample)} exact")
    return 1 if failures else 0


# ---------------------------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
    )

    if args.dry_run:
        return dry_run(args)

    # ---- everything below this line touches the GPU -----------------------------------------
    import torch

    if not torch.xpu.is_available():
        LOG.error("no XPU devices. This script only runs on the two-B70 host with the cards free.")
        return 2
    if torch.xpu.device_count() <= max(args.cards):
        LOG.error("need cards %s but only %d XPUs are visible", args.cards, torch.xpu.device_count())
        return 2
    if args.deterministic:
        torch.use_deterministic_algorithms(True, warn_only=False)

    run_name = args.run_name or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_dir = args.out_dir / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    LOG.info("run %s -> %s", run_name, out_dir)

    timings: dict[str, float] = {}
    config = json.loads(TRANSFORMER_CONFIG.read_text())
    header = read_header(PRUNED_DENOISER)
    plan = plan_split(header, config, args.adaln_dtype, args.split_index)
    devices = [torch.device(f"xpu:{i}") for i in args.cards]
    torch.xpu.init()  # the allocator stats calls below raise "Invalid device argument" before lazy init
    for dev in devices:
        torch.xpu.reset_peak_memory_stats(dev)

    # ---- phase 1: prompt conditioning --------------------------------------------------------
    token_ids: list[int] | None = None
    if args.prompt_embeds is not None:
        from safetensors.torch import load_file

        with phase("encode.load_precomputed", timings):
            payload = load_file(str(args.prompt_embeds))
            prompt_embeds = payload["prompt_embeds"].to(devices[0], dtype=torch.bfloat16)
            text_token_tags = payload.get(
                "text_token_tags", torch.full((prompt_embeds.shape[1],), 1, dtype=torch.long)
            )
        LOG.info("using precomputed prompt embeds %s from %s", tuple(prompt_embeds.shape), args.prompt_embeds)
    else:
        prompt_embeds, text_token_tags, token_ids = encode_prompt(args, timings)
        LOG.info("prompt embeds %s, encoder freed", tuple(prompt_embeds.shape))
    encoder_peak = card_memory(torch, devices)
    for dev in devices:
        torch.xpu.reset_peak_memory_stats(dev)

    # ---- phase 2: the denoiser ---------------------------------------------------------------
    transformer, primary, secondary = load_sharded_transformer(args, plan, config, timings)
    prompt_embeds = prompt_embeds.to(primary)

    # ---- phase 3: sampling -------------------------------------------------------------------
    pipe = build_pipeline(args, transformer, timings)
    if args.video_shift is not None:
        pipe.scheduler.set_shift(args.video_shift)
    if args.audio_shift is not None:
        pipe.audio_scheduler.set_shift(args.audio_shift)

    generator = torch.Generator(device="cpu").manual_seed(args.seed)
    call_kwargs = dict(
        prompt_embeds=prompt_embeds,
        text_token_tags=text_token_tags,
        num_frames=args.frames,
        num_inference_steps=args.steps,
        generator=generator,
    )
    if args.height is not None:
        call_kwargs["height"] = args.height
    if args.width is not None:
        call_kwargs["width"] = args.width

    with phase("sample", timings):
        # `output=[...]` returns a dict of those intermediates (ModularPipeline.__call__ docstring).
        result = pipe(**call_kwargs, output=["latents", "audio_latents"])
    sample_peak = card_memory(torch, devices)

    latents = result["latents"].detach()
    audio_latents = result["audio_latents"].detach()
    del result
    del transformer, pipe
    _free(torch)
    for dev in devices:
        torch.xpu.reset_peak_memory_stats(dev)

    # ---- phase 4: decode ---------------------------------------------------------------------
    vae, audio_vae, decode_device = load_vaes(args, timings)
    with phase("decode.video", timings):
        latents_mean = torch.tensor(vae.config.latents_mean, device=decode_device).view(1, -1, 1, 1, 1)
        latents_std = torch.tensor(vae.config.latents_std, device=decode_device).view(1, -1, 1, 1, 1)
        video = vae.decode((latents.to(decode_device) * latents_std + latents_mean).to(vae.dtype), return_dict=False)[0]
        pixel_mean = torch.tensor((0.485, 0.456, 0.406), device=decode_device).view(1, -1, 1, 1, 1)
        pixel_std = torch.tensor((0.229, 0.224, 0.225), device=decode_device).view(1, -1, 1, 1, 1)
        video = (video.float() * pixel_std + pixel_mean).clamp(0, 1)
    del vae
    _free(torch)
    with phase("decode.audio", timings):
        a_mean = torch.tensor(audio_vae.config.latents_mean, device=decode_device).view(1, -1, 1)
        a_std = torch.tensor(audio_vae.config.latents_std, device=decode_device).view(1, -1, 1)
        audio = audio_vae.decode((audio_latents.to(decode_device) * a_std + a_mean).float(), return_dict=False)[0]
        # decode returns (2, 1, N); decoders.py L248 permutes it to (1, 2, N).
        audio = audio.float().permute(1, 0, 2).contiguous()
        sampling_rate = int(audio_vae.config.sampling_rate)
    decode_peak = card_memory(torch, devices)
    del audio_vae
    _free(torch)

    # ---- phase 5: write ----------------------------------------------------------------------
    video_cpu = video.detach().float().cpu().contiguous()  # (1, 3, T, H, W) in [0, 1]
    audio_cpu = audio.detach().float().cpu().contiguous()  # (1, 2, N)
    with phase("write", timings):
        frames_u8 = (video_cpu[0].permute(1, 2, 3, 0) * 255.0).round().clamp(0, 255).to(torch.uint8).numpy()
        mp4 = out_dir / "clip.mp4"
        write_mp4(mp4, frames_u8, audio_cpu[0].numpy(), fps=24, sample_rate=sampling_rate, crf=args.crf)
        if args.save_tensors:
            from safetensors.torch import save_file

            save_file(
                {"video": video_cpu, "audio": audio_cpu, "latents": latents.cpu(), "audio_latents": audio_latents.cpu()},
                str(out_dir / "tensors.safetensors"),
            )

    receipt = {
        "run_name": run_name,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": platform.node(),
        "argv": sys.argv,
        "settings": {
            k: (str(v) if isinstance(v, pathlib.Path) else v) for k, v in sorted(vars(args).items())
        },
        "prompt": args.prompt if args.prompt_embeds is None else None,
        "prompt_tokens": len(token_ids) if token_ids is not None else int(prompt_embeds.shape[1]),
        "seed": args.seed,
        "num_inference_steps": args.steps,
        "num_inference_steps_note": "ASSUMED; no default is declared anywhere on this host",
        "resolved": {
            "video_latents_shape": list(latents.shape),
            "audio_latents_shape": list(audio_latents.shape),
            "video_shape": list(video_cpu.shape),
            "audio_shape": list(audio_cpu.shape),
            "sampling_rate": sampling_rate,
            "fps": 24,
        },
        "split_plan": plan.as_dict(),
        "timings_seconds": timings,
        "seconds_per_second_of_video": round(sum(timings.values()) / (video_cpu.shape[2] / 24.0), 3),
        "peak_memory": {"encode": encoder_peak, "sample": sample_peak, "decode": decode_peak},
        "host_peak_rss_bytes": host_rss_bytes(),
        "hashes": {
            "video_tensor_sha256": sha256_tensor(video_cpu),
            "audio_tensor_sha256": sha256_tensor(audio_cpu),
            "video_latents_sha256": sha256_tensor(latents.cpu()),
            "audio_latents_sha256": sha256_tensor(audio_latents.cpu()),
        },
        "inputs": {
            "denoiser": str(PRUNED_DENOISER),
            "denoiser_header_sha256": file_digest(PRUNED_DENOISER, limit=1 << 20),
            "text_encoder": str(INT8_TEXT_ENCODER) if args.prompt_embeds is None else str(args.prompt_embeds),
            "convrot_rotation_sha256": file_digest(CONVROT_ROTATION) if CONVROT_ROTATION.exists() else None,
            "vae": str(VAE_DIR),
            "audio_vae": str(AUDIO_VAE_DIR),
        },
        "versions": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "diffusers": __import__("diffusers").__version__,
            "transformers": __import__("transformers").__version__,
        },
        "environment": {k: v for k, v in os.environ.items() if k.startswith(("ZE_", "SYCL_", "PYTORCH_", "ONEAPI", "IPEX"))},
        "deterministic": bool(args.deterministic),
    }
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    LOG.info("video sha256 %s", receipt["hashes"]["video_tensor_sha256"])
    LOG.info("audio sha256 %s", receipt["hashes"]["audio_tensor_sha256"])
    LOG.info("wrote %s and %s", mp4, out_dir / "receipt.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
