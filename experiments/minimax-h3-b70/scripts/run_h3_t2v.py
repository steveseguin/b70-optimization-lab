#!/usr/bin/env python3
"""MiniMax-H3 text-to-video-with-audio on two Intel B70s, from either FL2VA denoiser build.

    Phase 0  plan       read safetensors headers, resolve the byte-balanced layer split
    Phase 1  encode     Qwen3-VL-32B INT8 ConvRot text encoder on xpu:0, hidden state after
                        decoder layer 50, then the encoder is freed before anything else loads
    Phase 2  load       the chosen denoiser streamed tensor-by-tensor across xpu:0 / xpu:1
    Phase 3  sample     diffusers MiniMaxH3 modular blocks, cfg-free, one forward per step,
                        video shift 12 / audio shift 3.  `--steps` counts SIGMA GRID POINTS
                        (terminal 0 included), so it drives `steps - 1` transformer evaluations:
                        51 for the base model's 50 NFE, 9 for the 8-step turbo LoRA.
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
* `PYTORCH_ALLOC_CONF=expandable_segments:True` is a precondition, not a tuning knob, whenever
  both cards are visible: session 10's probe matrix measured ~1 GiB of host RAM consumed per GiB
  placed on a card without it, and +54/+149 MiB for 8 GiB with it
  (`scripts/xpu-host-memory-probe.py`, `notes/2026-09-18-gpu-fault-first-light.md`).
  `smoke_h3.sh` sets it for every GPU run.

The two denoisers (`--denoiser`, env `B70_H3_DENOISER`)
------------------------------------------------------
Neither build is exact -- the exact BF16 denoiser is 66.3 GB and needs four cards -- so the choice
is *where* the error lives, not whether there is one:

* `pruned` (the default): Comfy's pruned BF16 file, 532 tensors, 40.23 GB.  Every weight in the
  residual stream is the released BF16 weight, bit for bit.  The timestep embedder and the 50
  AdaLN projections are replaced by an `adaln_t_table [1025, 8]` rank-8 fit, whose worst error
  (8e-4 / 1.2e-3) is *below* the BF16 weights' own error against float32
  (notes/2026-09-17-adaln-table-exactness.md).  The approximation is confined to the modulation
  branch.  This path installs `AdaLNTableEmbedder` / `PrunedAdaLNModulation` / `PrunedAdaLNOut`.
* `int8`: Comfy's full INT8 ConvRot file, 1035 tensors, 34.04 GB.  The AdaLN branch is the
  *unpruned* one (`time_embedder.proj_in/proj_out`, `adaln_proj.linear` 2688 -> 96768), so the
  modulation is exact in form and **no module swap happens at all** -- the stock diffusers
  modules and the stock arithmetic run unchanged.  In exchange, 250 of the block Linears are
  rotate-then-quantize int8 with a per-output-row float32 scale, i.e. the error moves out of the
  modulation branch and into every weight of the block stack.  Those Linears become
  `ConvRotLinear` modules, the same class and the same dequant arithmetic the INT8 text encoder
  already uses.

The ConvRot rotation is shared: the denoiser's attention and MLP Linears declare
`convrot_groupsize: 256`, exactly the rotation recovered from the video-VAE pair in
`data/convrot-hadamard-256.safetensors`.  Its `adaln_proj` declares `convrot_groupsize: 64`,
because 2688 is not a multiple of 256 -- and that order-64 rotation is the *leading 64x64 block*
of the one already recovered, so nothing new has to be recovered.  See `convrot_rotation()` for
the algebra and for the measurements that confirmed it against real weights.

Environment switches
--------------------
* `B70_H3_DENOISER=pruned|int8` -- the default for `--denoiser`.
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
* `B70_H3_LORA=PATH[:scale]` -- the default for `--lora`. A ComfyUI-format adapter, e.g. the 8-step
  turbo LoRA, which is what makes a short `--steps` legitimate. Merged exactly into dense BF16
  weights at load time; applied as an additive runtime term inside `ConvRotLinear` on the int8
  path, because a quantized weight cannot absorb a merge. See the LoRA section below and
  `notes/2026-09-18-steps-and-lora.md`.
* `B70_H3_XFER=host|direct` -- how a tensor crosses the two-card boundary. `host` (the default
  since the 2026-09-18 GPU fault) stages every cross-card move through host RAM; `direct` keeps
  the old `t.to(other_card)` device-to-device copy. Both are bit-exact; see `cross_card()`.

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
INT8_DENOISER = REPO_COMFY / "diffusion_models" / "minimax_h3_fl2va_int8_convrot.safetensors"
INT8_TEXT_ENCODER = REPO_COMFY / "text_encoders" / "qwen3vl_32b_minimax_h3_int8_convrot.safetensors"
CONVROT_ROTATION = pathlib.Path(__file__).resolve().parent.parent / "data" / "convrot-hadamard-256.safetensors"

# The two denoiser checkpoints, and what each one costs in fidelity.
#
#   pruned  BF16, 532 tensors, 40.23 GB.  Every weight is the released BF16 weight, but the
#           timestep embedder and the 50 AdaLN projections are re-parameterised through a
#           `adaln_t_table [1025, 8]` rank-8 fit (notes/2026-09-17-adaln-table-exactness.md:
#           worst error 8e-4 / 1.2e-3, *below* the BF16 weights' own error against float32).
#           Approximation confined to the modulation branch; the residual stream is untouched.
#   int8    INT8 ConvRot, 1035 tensors, 34.04 GB.  The AdaLN branch is the *unpruned* one
#           (`time_embedder.proj_in/proj_out`, `adaln_proj.linear` 2688 -> 96768), so the
#           modulation is exact in form -- but 250 of the block Linears are rotate-then-quantize
#           int8 with a per-output-row float32 scale, so every weight in the block stack carries
#           quantization error instead.
#
# Neither is exact: the exact BF16 denoiser is 66.3 GB and needs four cards.  The two paths trade
# *where* the error lives, which is why both exist here and why the pruned one is the control.
DENOISERS = {
    "pruned": PRUNED_DENOISER,
    "int8": INT8_DENOISER,
}
DEFAULT_DENOISER = os.environ.get("B70_H3_DENOISER", "pruned").strip().lower()


def denoiser_path(variant: str) -> pathlib.Path:
    try:
        return DENOISERS[variant]
    except KeyError:
        raise ValueError(f"unknown denoiser {variant!r}; choose one of {sorted(DENOISERS)}") from None

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


def read_metadata(path: pathlib.Path) -> dict:
    """The `__metadata__` block `read_header` drops.  Strings only, per the safetensors spec."""
    with path.open("rb") as fh:
        (header_len,) = struct.unpack("<Q", fh.read(8))
        return json.loads(fh.read(header_len)).get("__metadata__") or {}


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


@dataclasses.dataclass(frozen=True)
class QuantSlice:
    """How one diffusers `nn.Linear` is replaced wholesale by a `ConvRotLinear`.

    The int8 checkpoint stores each quantized Linear as three tensors under one base name:

        <base>.weight        I8  [out, in]   == round(W R / scale)
        <base>.weight_scale  F32 [out, 1]    per *output row*
        <base>.comfy_quant   U8  ASCII JSON  {"format", "convrot", "convrot_groupsize"}

    plus an optional `<base>.bias`.  `row_slice` and `swap_halves` mean exactly what they mean in
    `SourceSlice`, and they are safe here for the same reason: both act on the **output** axis,
    which is the axis the scale is indexed by and the axis the rotation does *not* touch.  So
    slicing rows of `weight` and of `weight_scale` together, or swapping their halves together,
    reproduces the sub-Linear exactly -- which is what turns Comfy's fused `qkv_proj` into
    diffusers' separate `to_q` / `to_k` / `to_v`, and Comfy's `[gate ; value]` `mlp.fc1` into
    diffusers' `[value ; gate]` `ff.net.0.proj`.
    """

    key: str  # base name in the int8 checkpoint, e.g. "blocks.0.attn.qkv_proj"
    row_slice: tuple[int, int] | None = None
    swap_halves: bool = False
    group_size: int = 256  # authoritative value comes from `.comfy_quant`; this is the fallback
    has_bias: bool = False

    def tensor_keys(self, header: dict) -> list[str]:
        """Every checkpoint tensor this substitution consumes."""
        keys = [f"{self.key}.weight", f"{self.key}.weight_scale", f"{self.key}.comfy_quant"]
        if f"{self.key}.bias" in header:
            keys.append(f"{self.key}.bias")
        return keys

    def param_names(self, module: str, header: dict) -> list[str]:
        """Every diffusers parameter this substitution stands in for."""
        names = [f"{module}.weight"]
        if f"{self.key}.bias" in header:
            names.append(f"{module}.bias")
        return names

    def nbytes(self, header: dict) -> int:
        """Card bytes once resident: int8 weight + float32 scale + bias, all as stored.

        Nothing is widened at load time on this path -- `ConvRotLinear` keeps the int8 weight and
        widens it per call -- so unlike `SourceSlice` the stored width *is* the resident width.
        """
        total = 0
        for suffix, sliced in ((".weight", True), (".weight_scale", True), (".bias", False)):
            name = self.key + suffix
            if name not in header:
                continue
            entry = header[name]
            n = tensor_bytes(entry)
            if sliced and self.row_slice is not None:
                n = n * (self.row_slice[1] - self.row_slice[0]) // entry["shape"][0]
            total += n
        return total  # `.comfy_quant` is metadata; it is never placed on a card


def build_remap(num_layers: int, num_refiner_layers: int, variant: str = "pruned") -> dict[str, SourceSlice]:
    """diffusers parameter name -> where it comes from in the Comfy checkpoint.

    `variant="pruned"` returns every parameter, because the pruned file stores every one of them
    densely.  `variant="int8"` returns only the parameters that are *not* replaced by a
    `ConvRotLinear` (see `build_quant_map`), plus the four unpruned timestep-embedder tensors the
    pruned file does not have at all.
    """
    quantized = variant == "int8"
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
    if quantized:
        # The unpruned AdaLN branch, which the pruned file replaces by `adaln_t_table`.
        # `TimestepEmbedding` (diffusers) calls them linear_1 / linear_2; Comfy calls them
        # proj_in / proj_out.  Shapes and dtypes match the full BF16 diffusers checkpoint exactly:
        #   proj_in  F32 [5376, 256]  == time_embedder.linear_1  (freq_dim -> time_embed_hidden)
        #   proj_out F32 [2688, 5376] == time_embedder.linear_2  (-> time_embed_dim)
        remap["time_embedder.linear_1.weight"] = SourceSlice("time_embedder.proj_in.weight")
        remap["time_embedder.linear_1.bias"] = SourceSlice("time_embedder.proj_in.bias")
        remap["time_embedder.linear_2.weight"] = SourceSlice("time_embedder.proj_out.weight")
        remap["time_embedder.linear_2.bias"] = SourceSlice("time_embedder.proj_out.bias")

    def add_attn(dst_prefix: str, src_prefix: str, quant: bool = False) -> None:
        # `quant=True` drops the six Linears this block hands to `build_quant_map` and keeps only
        # the norms, which stay BF16 in the int8 checkpoint.
        remap[f"{dst_prefix}.attn.norm_q.weight"] = SourceSlice(f"{src_prefix}.attn.q_norm.weight")
        remap[f"{dst_prefix}.attn.norm_k.weight"] = SourceSlice(f"{src_prefix}.attn.k_norm.weight")
        remap[f"{dst_prefix}.norm1.weight"] = SourceSlice(f"{src_prefix}.norm1.weight")
        remap[f"{dst_prefix}.norm2.weight"] = SourceSlice(f"{src_prefix}.norm2.weight")
        if quant:
            return
        remap[f"{dst_prefix}.attn.to_q.weight"] = SourceSlice(f"{src_prefix}.attn.qkv_proj.weight", (0, INNER_DIM))
        remap[f"{dst_prefix}.attn.to_k.weight"] = SourceSlice(
            f"{src_prefix}.attn.qkv_proj.weight", (INNER_DIM, 2 * INNER_DIM)
        )
        remap[f"{dst_prefix}.attn.to_v.weight"] = SourceSlice(
            f"{src_prefix}.attn.qkv_proj.weight", (2 * INNER_DIM, 3 * INNER_DIM)
        )
        remap[f"{dst_prefix}.attn.to_out.0.weight"] = SourceSlice(f"{src_prefix}.attn.out_proj.weight")
        # SwiGLU: Comfy stores [gate ; value], diffusers reads [value ; gate].
        remap[f"{dst_prefix}.ff.net.0.proj.weight"] = SourceSlice(f"{src_prefix}.mlp.fc1.weight", swap_halves=True)
        remap[f"{dst_prefix}.ff.net.2.weight"] = SourceSlice(f"{src_prefix}.mlp.fc2.weight")

    for i in range(num_layers):
        add_attn(f"transformer_blocks.{i}", f"blocks.{i}", quant=quantized)
        if not quantized:
            remap[f"transformer_blocks.{i}.adaln_proj.linear.weight"] = SourceSlice(
                f"blocks.{i}.adaln_proj.linear.weight"
            )
            remap[f"transformer_blocks.{i}.adaln_proj.linear.bias"] = SourceSlice(
                f"blocks.{i}.adaln_proj.linear.bias"
            )
    # The two token-refiner blocks are BF16 in *both* checkpoints -- Comfy quantizes only the 50
    # denoiser blocks -- so they always take the dense path.
    for i in range(num_refiner_layers):
        add_attn(f"token_refiner.refiner_blocks.{i}", f"token_refiner.blocks.{i}")
    return remap


# `<base>.comfy_quant` is a U8 tensor holding ~90 bytes of ASCII JSON.  It is the authoritative
# declaration of the quantization format, so the loader and the dry run both read it rather than
# assume: 250 blobs, about 22 KB in total for the denoiser.  `read_comfy_quant` uses a bare
# `os.pread` so the dry run stays torch-free.
def read_comfy_quant(path: pathlib.Path, header: dict | None = None) -> dict[str, dict]:
    """`{base name: parsed comfy_quant dict}` for every quantized Linear in `path`."""
    parsed, data_start = read_header_and_data_start(path)
    header = parsed if header is None else header
    out: dict[str, dict] = {}
    fd = os.open(str(path), os.O_RDONLY)
    try:
        for key in header:
            if not key.endswith(".comfy_quant"):
                continue
            begin, end = header[key]["data_offsets"]
            blob = os.pread(fd, end - begin, data_start + begin)
            out[key[: -len(".comfy_quant")]] = json.loads(blob.decode().rstrip("\x00"))
    finally:
        os.close(fd)
    return out


def build_quant_map(num_layers: int, header: dict, quant_meta: dict[str, dict]) -> dict[str, QuantSlice]:
    """diffusers *module* path -> the int8 ConvRot Linear that replaces it.

    Header-driven: the module list comes from the `.comfy_quant` keys actually present in the
    file, and each entry's group size comes from that blob, never from a constant here.  A
    quantized Linear the map does not know how to place is a hard error, not a silent skip.
    """
    quant: dict[str, QuantSlice] = {}

    def group_of(base: str) -> int:
        meta = quant_meta[base]
        if meta.get("format") != "int8_tensorwise" or meta.get("convrot") is not True:
            raise RuntimeError(f"{base}: unsupported comfy_quant {meta!r} (expected int8 convrot)")
        return int(meta["convrot_groupsize"])

    for i in range(num_layers):
        src, dst = f"blocks.{i}", f"transformer_blocks.{i}"
        # Comfy's fused qkv -> diffusers' three Linears, sliced on the output axis.
        for name, rows in (
            ("to_q", (0, INNER_DIM)),
            ("to_k", (INNER_DIM, 2 * INNER_DIM)),
            ("to_v", (2 * INNER_DIM, 3 * INNER_DIM)),
        ):
            base = f"{src}.attn.qkv_proj"
            quant[f"{dst}.attn.{name}"] = QuantSlice(base, rows, False, group_of(base))
        for dst_mod, base, swap in (
            (f"{dst}.attn.to_out.0", f"{src}.attn.out_proj", False),
            (f"{dst}.ff.net.0.proj", f"{src}.mlp.fc1", True),  # [gate ; value] -> [value ; gate]
            (f"{dst}.ff.net.2", f"{src}.mlp.fc2", False),
            (f"{dst}.adaln_proj.linear", f"{src}.adaln_proj.linear", False),
        ):
            quant[dst_mod] = QuantSlice(base, None, swap, group_of(base), f"{base}.bias" in header)

    placed = {q.key for q in quant.values()}
    stray = sorted(set(quant_meta) - placed)
    if stray:
        raise RuntimeError(f"{len(stray)} quantized Linears have no diffusers destination, e.g. {stray[:5]}")
    return quant


# ---------------------------------------------------------------------------------------------
# LoRA (ComfyUI generic LoRA), e.g. the 8-step turbo adapter
#
# The turbo file on this host is `loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors`
# (1.956 GB, 624 tensors = 208 modules x {alpha, lora_A, lora_B}).  Its `__metadata__` states the
# contract this code implements, so none of it is guessed:
#
#   training_rank    128          lora_A [r, in], lora_B [out, r]
#   training_alpha   8.0          per-module `<base>.alpha`, F32 scalar
#   training_scale   0.0625       == alpha / rank, the scale ComfyUI applies at strength 1.0
#   base_model       "Comfy-Org/MiniMax-H3 minimax_h3_fl2va_bf16.safetensors"
#   source_format    "Diffusers PEFT LoRA"    target_format "ComfyUI generic LoRA"
#   qkv_fusion       "block diagonal B; concat A; alpha multiplied by 3"
#   swi_glu_mapping  "Diffusers [value;gate] -> ComfyUI [gate;value]"
#
# The two fusion notes are why this maps onto `SourceSlice` / `QuantSlice` with no special cases:
#
# * `qkv_proj` carries ONE pair for the fused Linear -- `lora_A [384, 5376]` (three rank-128 A
#   blocks concatenated on the rank axis) and `lora_B [21504, 384]` (the three B blocks down the
#   diagonal).  `alpha` is 24.0 and the rank is 384, so `alpha / rank` is still 0.0625.  Taking
#   `lora_B`'s rows `[0, 7168)` and keeping the whole `lora_A` reproduces the `to_q` delta exactly,
#   because the columns of that row block outside `[0, 128)` are zero by construction.  So the
#   row slice that splits `qkv_proj.weight` into to_q/to_k/to_v splits `lora_B` the same way, and
#   the rank the runtime path then pays for is 384 rather than 128 -- exact, three times the
#   low-rank work, and the price of not assuming a structure the file only claims in a string.
# * `mlp.fc1` is stored `[gate ; value]` like the weight, so the same `swap_halves` that reorders
#   the weight's rows reorders `lora_B`'s rows.
#
# Both transforms act on the OUTPUT axis, which is `lora_B`'s first axis and the axis `lora_A`
# does not have -- the same argument that makes `row_slice` / `swap_halves` safe for the
# per-output-row int8 scale.  `lora_A` is therefore always taken whole.
#
# Where the delta is applied depends on the destination, and the two are NOT equivalent:
#
#   dense BF16 Linear  ->  MERGED at load time, exactly:  W' = W + s * (B @ A), the sum taken in
#                          float32 (bf16 -> float32 is exact) and rounded once to the destination
#                          dtype.  Nothing is left to do at runtime and nothing costs extra bytes.
#   ConvRotLinear      ->  merging is NOT AVAILABLE.  The stored weight is int8 `round(W R / s)`;
#                          `W + delta` cannot be re-quantized without changing every weight in the
#                          Linear, so a "merge" here would silently replace the measured int8
#                          error by a different, larger one.  Instead the adapter stays a separate
#                          additive term evaluated per call:
#                              y = dequant(W) x + scale * B (A x)
#                          which is the LoRA's own definition and is exact up to the same float32
#                          accumulation the dequant already uses.  It costs the adapter's bytes on
#                          the card (~2.30 GB for this file across both cards, because the three
#                          qkv destinations each keep a copy of the shared `lora_A`) and one extra
#                          rank-r GEMM pair per Linear per step.  See `notes/2026-09-18-steps-and-lora.md`.
#
# The LoRA acts on the ORIGINAL weight `W`, not on Comfy's rotated `W R`, so on the ConvRot path
# the term is computed from the UNROTATED activation.  Getting that backwards is the one silent
# way to be wrong here, so `ConvRotLinear.forward` keeps `x` before the rotation explicitly.
# ---------------------------------------------------------------------------------------------

LORA_PREFIX = "diffusion_model."
DEFAULT_LORA = REPO_COMFY / "loras" / "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"

# PEFT names them lora_A/lora_B, kohya and most ComfyUI exporters lora_down/lora_up; both with and
# without a trailing `.weight`.  Order matters only in that the longest suffix is tried first.
_LORA_DOWN_SUFFIXES = (".lora_A.weight", ".lora_down.weight", ".lora_A", ".lora_down")
_LORA_UP_SUFFIXES = (".lora_B.weight", ".lora_up.weight", ".lora_B", ".lora_up")


@dataclasses.dataclass(frozen=True)
class LoraPair:
    """One `(A, B)` pair as it is stored, before any destination-side slicing."""

    base: str  # checkpoint-side module base, prefix stripped: "blocks.0.attn.qkv_proj"
    down: str  # tensor name of A, [rank, in_features]
    up: str  # tensor name of B, [out_features, rank]
    rank: int
    in_features: int
    out_features: int
    alpha: float | None  # `<base>.alpha` if the file carries one

    @property
    def strength(self) -> float:
        """The file's own scale at user strength 1.0: `alpha / rank`, or 1.0 if no alpha."""
        return 1.0 if self.alpha is None else self.alpha / self.rank


@dataclasses.dataclass(frozen=True)
class LoraSlice:
    """One LoRA pair aimed at one diffusers destination, sliced exactly like that destination."""

    pair: LoraPair
    row_slice: tuple[int, int] | None  # rows of `lora_B` == rows of the weight
    swap_halves: bool  # `lora_B`'s halves, like the weight's
    scale: float  # user scale * pair.strength -- the full multiplier on `B @ A`

    def nbytes(self, header: dict) -> int:
        """Bytes this destination keeps resident when the term is applied at runtime."""
        a = tensor_bytes(header[self.pair.down])
        b = tensor_bytes(header[self.pair.up])
        if self.row_slice is not None:
            b = b * (self.row_slice[1] - self.row_slice[0]) // self.pair.out_features
        return a + b


@dataclasses.dataclass
class LoraPlan:
    path: pathlib.Path
    scale: float
    header: dict
    pairs: dict[str, LoraPair]  # every pair in the file, by stripped base
    dense: dict[str, LoraSlice]  # diffusers PARAMETER name ("....weight") -> merged at load
    runtime: dict[str, LoraSlice]  # diffusers MODULE path -> additive term inside ConvRotLinear
    unmatched: list[str]  # pairs no destination claimed
    shape_errors: list[str]

    @property
    def matched(self) -> set[str]:
        return {s.pair.base for s in self.dense.values()} | {s.pair.base for s in self.runtime.values()}

    def runtime_bytes(self) -> int:
        return sum(s.nbytes(self.header) for s in self.runtime.values())


def parse_lora_arg(value: str) -> tuple[pathlib.Path, float]:
    """`PATH` or `PATH:scale`.  The suffix is a scale only if it parses as a float.

    Splitting on the last colon and requiring a float means a path that itself contains a colon is
    still usable, and a typo in the scale is a hard error rather than a silently ignored suffix.
    """
    head, sep, tail = value.rpartition(":")
    if sep and head:
        try:
            return pathlib.Path(head), float(tail)
        except ValueError:
            pass
    return pathlib.Path(value), 1.0


def scan_lora_header(header: dict) -> tuple[dict[str, LoraPair], list[str]]:
    """Every `(A, B)` pair in a LoRA file, keyed by module base with `diffusion_model.` stripped.

    Returns `(pairs, stray)`, where `stray` names every tensor that is neither half of a pair nor
    an `alpha` -- so a file with a naming convention this does not understand is visible as such
    instead of silently contributing nothing.
    """
    downs: dict[str, str] = {}
    ups: dict[str, str] = {}
    alphas: dict[str, str] = {}
    stray: list[str] = []

    def strip(name: str, suffixes: tuple[str, ...]) -> str | None:
        for suffix in suffixes:
            if name.endswith(suffix):
                base = name[: -len(suffix)]
                return base[len(LORA_PREFIX):] if base.startswith(LORA_PREFIX) else base
        return None

    for name in header:
        base = strip(name, _LORA_DOWN_SUFFIXES)
        if base is not None:
            downs[base] = name
            continue
        base = strip(name, _LORA_UP_SUFFIXES)
        if base is not None:
            ups[base] = name
            continue
        base = strip(name, (".alpha",))
        if base is not None:
            alphas[base] = name
            continue
        stray.append(name)

    pairs: dict[str, LoraPair] = {}
    for base in sorted(set(downs) | set(ups)):
        if base not in downs or base not in ups:
            stray.append(downs.get(base) or ups[base])
            continue
        a_shape = header[downs[base]]["shape"]
        b_shape = header[ups[base]]["shape"]
        if len(a_shape) != 2 or len(b_shape) != 2:
            stray.append(downs[base])
            continue
        pairs[base] = LoraPair(
            base=base,
            down=downs[base],
            up=ups[base],
            rank=a_shape[0],
            in_features=a_shape[1],
            out_features=b_shape[0],
            alpha=None,  # filled by `read_lora_alphas`; the header alone cannot know it
        )
    return pairs, sorted(stray)


def read_lora_alphas(path: pathlib.Path, pairs: dict[str, LoraPair], header: dict) -> dict[str, LoraPair]:
    """Fill each pair's `alpha` by preading its scalar.  208 x 4 bytes for the turbo file.

    The same exception the dry run already makes for `.comfy_quant`: a few hundred bytes of the
    file's own declaration, read with a bare `os.pread`, so the dry run stays torch-free.
    """
    _, data_start = read_header_and_data_start(path)
    fd = os.open(str(path), os.O_RDONLY)
    try:
        out: dict[str, LoraPair] = {}
        for base, pair in pairs.items():
            alpha = None
            for name in (f"{LORA_PREFIX}{base}.alpha", f"{base}.alpha"):
                entry = header.get(name)
                if entry is None:
                    continue
                begin, end = entry["data_offsets"]
                blob = os.pread(fd, end - begin, data_start + begin)
                if entry["dtype"] == "F32" and end - begin == 4:
                    alpha = struct.unpack("<f", blob)[0]
                elif entry["dtype"] == "F64" and end - begin == 8:
                    alpha = struct.unpack("<d", blob)[0]
                else:
                    raise RuntimeError(f"{name}: alpha is {entry['dtype']} {end - begin}B, not a f32/f64 scalar")
                break
            out[base] = dataclasses.replace(pair, alpha=alpha)
        return out
    finally:
        os.close(fd)


def build_lora_plan(
    path: pathlib.Path,
    scale: float,
    denoiser_header: dict,
    remap: dict[str, SourceSlice],
    quant: dict[str, QuantSlice],
) -> LoraPlan:
    """Aim every pair in `path` at the destinations the weight remap already defines.

    A destination is claimed by the pair whose base equals the *checkpoint* module the destination
    reads its weight from, so the LoRA needs no name table of its own: it inherits the one the
    weights are already loaded through, including the qkv row slices and the SwiGLU half swap.
    `remap` supplies the dense destinations (which are merged) and `quant` the ConvRot ones (which
    get the runtime term); on the pruned path `quant` is empty and everything is merged.
    """
    header = read_header(path)
    pairs, stray = scan_lora_header(header)
    pairs = read_lora_alphas(path, pairs, header)

    dense: dict[str, LoraSlice] = {}
    runtime: dict[str, LoraSlice] = {}
    shape_errors: list[str] = []

    def aim(dest: str, base: str, row_slice, swap_halves: bool, into: dict) -> None:
        pair = pairs.get(base)
        if pair is None:
            return
        weight = denoiser_header.get(f"{base}.weight")
        if weight is not None:
            out_features, in_features = weight["shape"]
            if (pair.out_features, pair.in_features) != (out_features, in_features):
                shape_errors.append(
                    f"{base}: lora is [{pair.out_features}, {pair.rank}] x [{pair.rank}, "
                    f"{pair.in_features}] but the checkpoint weight is [{out_features}, {in_features}]"
                )
                return
        if row_slice is not None and not (0 <= row_slice[0] < row_slice[1] <= pair.out_features):
            shape_errors.append(f"{base}: row slice {row_slice} is outside lora_B's {pair.out_features} rows")
            return
        if swap_halves and pair.out_features % 2:
            shape_errors.append(f"{base}: lora_B has an odd {pair.out_features} rows, cannot swap halves")
            return
        into[dest] = LoraSlice(pair, row_slice, swap_halves, scale * pair.strength)

    for name, src in remap.items():
        if not name.endswith(".weight") or not src.key.endswith(".weight"):
            continue
        aim(name, src.key[: -len(".weight")], src.row_slice, src.swap_halves, dense)
    for module, q in quant.items():
        aim(module, q.key, q.row_slice, q.swap_halves, runtime)

    plan = LoraPlan(
        path=path,
        scale=scale,
        header=header,
        pairs=pairs,
        dense=dense,
        runtime=runtime,
        unmatched=[],
        shape_errors=shape_errors,
    )
    plan.unmatched = sorted(set(pairs) - plan.matched) + stray
    return plan


def lora_delta(torch, fh, sl: LoraSlice, device=None):
    """`scale * (B @ A)` for one destination, as float32 on `device`, sliced like the weight.

    `lora_B`'s rows are the output axis, so `row_slice` reads a contiguous byte range and
    `swap_halves` is the same concatenation the weight gets.  `lora_A` is always whole.  The
    product is taken in float32: bf16 -> float32 is exact, so the only rounding in the merged
    weight is the single cast at the end, which is what "merged exactly" means here.

    The product is formed *on the destination card*, not on the host: only the two small factors
    (at most ~11 MB together for this file) cross the bus, and the `[out, in]` float32 transient
    -- 616 MB for an `mlp.fc1` -- is paid in card memory, which is the resource this host has and
    host RAM is the one it does not (notes/2026-09-18-gpu-fault-first-light.md).
    """
    b = fh.get_tensor(sl.pair.up, sl.row_slice)
    if sl.swap_halves:
        half = b.shape[0] // 2
        b = torch.cat((b[half:], b[:half]), dim=0)
    a = fh.get_tensor(sl.pair.down)
    if device is not None:
        a, b = a.to(device=device), b.to(device=device)
    delta = (b.to(torch.float32) @ a.to(torch.float32)) * sl.scale
    del a, b
    fh.release(sl.pair.up, sl.row_slice)
    fh.release(sl.pair.down)
    return delta


def lora_runtime_tensors(torch, fh, sl: LoraSlice, device):
    """`(A, B)` for the runtime term, on `device`, in the dtype they are stored in.

    Stored dtype (bf16) rather than float32 on purpose: widening here would double the resident
    cost of the adapter for no gain, because `ConvRotLinear` widens per call exactly as it already
    does for the int8 weight.  `B` is sliced and swapped like the weight; `A` is whole.
    """
    b = fh.get_tensor(sl.pair.up, sl.row_slice)
    if sl.swap_halves:
        half = b.shape[0] // 2
        b = torch.cat((b[half:], b[:half]), dim=0)
    a = fh.get_tensor(sl.pair.down)
    a = a.to(device=device).contiguous()
    b = b.to(device=device).contiguous()
    fh.release(sl.pair.up, sl.row_slice)
    fh.release(sl.pair.down)
    return a, b


# Mirrors MiniMaxH3Transformer3DModel._keep_in_fp32_modules
# (transformer_minimax_h3.py L444-451): the patch projections and the output heads are float32 in
# the released mixed-precision checkpoint, and the pruned file stores them that way too.
FP32_SUBSTRINGS = ("proj_in", "audio_proj_in", "proj_out", "audio_proj_out", "rope")


def target_dtype(name: str, adaln_dtype: str, variant: str = "pruned"):
    import torch

    if any(s in name for s in FP32_SUBSTRINGS):
        return torch.float32
    if variant == "int8":
        # `time_embedder` is float32 in `_keep_in_fp32_modules` and float32 as stored, and the
        # int8 file's AdaLN projections are its *own* bf16/int8 tensors, not a rank-8 fit -- so
        # `--adaln-dtype`, which only names the width of that fit, has nothing to widen here.
        # Every remaining dense tensor (`norm_out.linear` BF16, the norms, the refiner) keeps
        # the dtype it is stored in.
        return torch.float32 if "time_embedder." in name else torch.bfloat16
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
    variant: str = "pruned"
    quant_bytes: int = 0  # int8 weights + f32 scales + biases inside the block stack
    rotation_bytes: int = 0  # the ConvRot rotation matrices, resident on *each* card
    dequant_peak_bytes: int = 0  # transient: the largest quantized weight widened to bf16

    def as_dict(self) -> dict:
        return {
            "variant": self.variant,
            "split_index": self.split_index,
            "num_layers": self.num_layers,
            "non_block_bytes": self.non_block_bytes,
            "quant_bytes": self.quant_bytes,
            "rotation_bytes_per_card": self.rotation_bytes,
            "dequant_peak_bytes": self.dequant_peak_bytes,
            "card0_bytes": self.card0_bytes,
            "card1_bytes": self.card1_bytes,
            "card0_gib": round(self.card0_bytes / 2**30, 3),
            "card1_gib": round(self.card1_bytes / 2**30, 3),
            "imbalance_bytes": abs(self.card0_bytes - self.card1_bytes),
            "adaln_table_bytes": self.table_bytes,
        }


def plan_split(
    header: dict,
    config: dict,
    adaln_dtype: str,
    split_index: int | None = None,
    variant: str = "pruned",
    quant_meta: dict[str, dict] | None = None,
) -> SplitPlan:
    """Byte-balanced split of the block stack over two cards.

    The policy is `experiments/ltx25-b70/scripts/ltx_layer_shard.py` (`LTXLayerShardedPatcher.install`):
    non-block parameters live on the primary card, and `split_index` minimises

        |non_block + 2 * sum(block_bytes[:n]) - sum(block_bytes)|

    i.e. it balances `non_block + first n blocks` against `the remaining blocks`.

    Bytes are counted *after* the remap and the dtype policy, not as stored, because the AdaLN
    projections are widened F16 -> F32 when `--adaln-dtype fp32` and that is real card memory.

    On the `int8` path the arithmetic changes in three ways:

    * a quantized Linear is *not* widened at load time -- `ConvRotLinear` keeps the int8 weight
      and widens it per call -- so its resident cost is `1 B/elem` for the weight plus `4 B/row`
      for the scale plus the bias, i.e. the stored width is the resident width;
    * each card holds its own copy of the ConvRot rotation matrices (a 256x256 and a 64x64 bf16
      matrix, 139 KB together), because blocks on both cards call them;
    * there is a *transient* on top of the resident total: the largest quantized weight widened
      to bfloat16 for one `F.linear`.  That peak is reported separately and must be left free.
    """
    num_layers = config["num_layers"]
    num_refiner = config["num_refiner_layers"]
    quantized = variant == "int8"
    remap = build_remap(num_layers, num_refiner, variant)
    quant: dict[str, QuantSlice] = {}
    if quantized:
        if quant_meta is None:
            raise ValueError("plan_split(variant='int8') needs quant_meta from read_comfy_quant()")
        quant = build_quant_map(num_layers, header, quant_meta)
    width = {"fp32": 4, "bf16": 2}

    def size_of(name: str) -> int:
        src = remap[name]
        raw = src.nbytes(header)
        stored = _DTYPE_BYTES[header[src.key]["dtype"]]
        if any(s in name for s in FP32_SUBSTRINGS):
            want = 4
        elif quantized:
            want = 4 if "time_embedder." in name else 2
        elif "adaln_proj.linear" in name or name.startswith("norm_out.linear"):
            want = width[adaln_dtype]
        else:
            want = 2
        return raw // stored * want

    def block_of(prefix: str, names) -> list[str]:
        return [n for n in names if n.startswith(prefix)]

    block_bytes = []
    for i in range(num_layers):
        prefix = f"transformer_blocks.{i}."
        n = sum(size_of(x) for x in block_of(prefix, remap))
        n += sum(quant[x].nbytes(header) for x in block_of(prefix, quant))
        block_bytes.append(n)
    block_names = {n for i in range(num_layers) for n in block_of(f"transformer_blocks.{i}.", remap)}
    non_block = sum(size_of(n) for n in remap if n not in block_names)

    quant_bytes = sum(q.nbytes(header) for q in quant.values())
    rotation_bytes = 0
    dequant_peak = 0
    table_bytes = 0
    if quantized:
        # One bf16 matrix per distinct group size, shared by every Linear that uses it, per card.
        rotation_bytes = sum(g * g * 2 for g in sorted({q.group_size for q in quant.values()}))
        non_block += rotation_bytes  # the primary card's copy; the secondary's is added below
        dequant_peak = max(
            (tensor_bytes(header[q.key + ".weight"]) * 2 for q in quant.values()), default=0
        )
    else:
        # The AdaLN table replaces `time_embedder`; it is shared, so it lives on the primary card
        # and is broadcast to the secondary once per forward ([1025, 8] float32 = 32.8 KB).
        table_bytes = tensor_bytes(header["adaln_t_table"])
        non_block += table_bytes
    # `rope.inv_freq` is a non-persistent buffer diffusers recomputes; count it anyway (64 B).
    non_block += tensor_bytes(header["rope.inv_freq"])

    total_blocks = sum(block_bytes)
    if split_index is None:
        # Balance card0 = non_block + blocks[:n] against card1 = blocks[n:] + rotation_bytes.
        # `non_block` already carries the primary's rotation copy, so it cancels out here.
        offset = non_block - rotation_bytes
        split_index = min(
            range(1, num_layers),
            key=lambda n: abs(offset + 2 * sum(block_bytes[:n]) - total_blocks),
        )
    if not 0 < split_index < num_layers:
        raise ValueError(f"split_index must leave at least one block on each card, got {split_index}")

    return SplitPlan(
        split_index=split_index,
        num_layers=num_layers,
        block_bytes=block_bytes,
        non_block_bytes=non_block,
        card0_bytes=non_block + sum(block_bytes[:split_index]),
        # The secondary card carries its own copy of the rotation matrices (0 on the pruned path).
        card1_bytes=sum(block_bytes[split_index:]) + rotation_bytes,
        table_bytes=table_bytes,
        variant=variant,
        quant_bytes=quant_bytes,
        rotation_bytes=rotation_bytes,
        dequant_peak_bytes=dequant_peak,
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
        """`compute_dtype` / `out_dtype` default to `None`, i.e. "follow the activation".

        That default is the text encoder's behaviour, unchanged.  The denoiser's block
        `adaln_proj.linear` needs both: diffusers reads `get_parameter_dtype(self.linear)` before
        calling it, and with no Parameters that walk lands on the first floating-point *buffer*,
        which is the float32 `scale` -- so the activation would arrive float32, the int8 weight
        would be widened to float32 (a 1.04 GB transient for the 96768x2688 AdaLN projection,
        twice the bf16 one) and the modulation would come back float32 and promote the whole
        packed sequence.  Pinning `compute_dtype=bfloat16` reproduces the unpruned checkpoint,
        whose `adaln_proj` *is* bf16 and whose input is cast to bf16 by exactly that call.
        """

        def __init__(self, qweight, scale, bias, rotation, group_size: int, compute_dtype=None, out_dtype=None,
                     lora_a=None, lora_b=None, lora_scale: float = 1.0):
            super().__init__()
            if qweight.shape[1] % group_size:
                raise ValueError(
                    f"in_features {qweight.shape[1]} is not a multiple of the ConvRot group size {group_size}"
                )
            if (lora_a is None) != (lora_b is None):
                raise ValueError("lora_a and lora_b must be given together")
            if lora_a is not None:
                if lora_a.shape[1] != qweight.shape[1] or lora_b.shape[0] != qweight.shape[0]:
                    raise ValueError(
                        f"lora [{lora_b.shape[0]}, {lora_b.shape[1]}] x [{lora_a.shape[0]}, {lora_a.shape[1]}] "
                        f"does not fit the Linear [{qweight.shape[0]}, {qweight.shape[1]}]"
                    )
                if lora_a.shape[0] != lora_b.shape[1]:
                    raise ValueError(f"lora ranks disagree: A {lora_a.shape[0]} vs B {lora_b.shape[1]}")
            self.register_buffer("qweight", qweight, persistent=False)  # int8 [out, in]
            self.register_buffer("scale", scale, persistent=False)  # float32 [out, 1]
            self.register_buffer("bias", bias, persistent=False)
            self.register_buffer("rotation", rotation, persistent=False)  # [G, G] or None
            self.register_buffer("lora_a", lora_a, persistent=False)  # [rank, in] or None
            self.register_buffer("lora_b", lora_b, persistent=False)  # [out, rank] or None
            self.lora_scale = float(lora_scale)
            self.group_size = group_size
            self.compute_dtype = compute_dtype
            self.out_dtype = out_dtype
            self.in_features = qweight.shape[1]
            self.out_features = qweight.shape[0]

        def forward(self, x):
            compute = self.compute_dtype or x.dtype
            out = self.out_dtype or x.dtype
            if compute != x.dtype:
                x = x.to(compute)
            # The LoRA is an adapter on the ORIGINAL weight W, not on Comfy's rotated `W R`, so
            # its term is built from the activation *before* the rotation.  Keep the reference now.
            x_unrotated = x
            if self.rotation is not None:
                shape = x.shape
                x = x.reshape(*shape[:-1], shape[-1] // self.group_size, self.group_size)
                x = x @ self.rotation.to(compute)
                x = x.reshape(shape)
            y = F.linear(x, self.qweight.to(compute))
            # The scale is applied after the accumulation, at no less than float32: that is both
            # cheaper and more accurate than scaling the weight first.  `promote_types` rather
            # than a bare `.float()` so a float64 activation is not silently *narrowed* to
            # float32 -- for the bf16/f16 activations the cards actually run, it is the same
            # float32 it always was.
            acc = torch.promote_types(y.dtype, torch.float32)
            y = y.to(acc) * self.scale.reshape(1, -1).to(acc)
            if self.lora_a is not None:
                # y += scale * B (A x).  The quantized weight cannot absorb the delta (see the
                # LoRA section), so the adapter stays additive here.  `A x` is taken in the
                # compute dtype -- the same GEMM precision the dequantized path itself runs at --
                # and everything from there on is float32: the rank axis is small, so the second
                # GEMM and the scale cost almost nothing at full width, and the sum lands in the
                # same float32 accumulator the dequant scale already produced.  Fixed operand
                # order, no atomics: bitwise repeatable, exactly like the path it adds to.
                xa = F.linear(x_unrotated, self.lora_a.to(compute)).to(acc) * self.lora_scale
                y = y + F.linear(xa, self.lora_b.to(acc))
            y = y.to(out)
            if self.bias is not None:
                y = y + self.bias.to(out)
            return y

    return ConvRotLinear


def convrot_rotation(torch, signs256, group_size: int):
    """The orthogonal ConvRot rotation `R` for `group_size`, from the recovered order-256 signs.

    Comfy's ConvRot rotation is not an arbitrary Hadamard matrix: measured on this host
    (2026-09-18) the recovered order-256 sign matrix is *exactly* `A (x) A (x) A (x) A`, the
    fourth Kronecker power of the symmetric order-4 Hadamard matrix

        A = [[ 1,  1,  1, -1],
             [ 1,  1, -1,  1],
             [ 1, -1,  1,  1],
             [-1,  1,  1,  1]]

    and `A[0, 0] = 1`, so the leading `4^j x 4^j` block of `A^(x)k` is `A^(x)j`.  The order-64
    rotation the denoiser's `adaln_proj` needs (`convrot_groupsize: 64`, because its 2688 inputs
    are not a multiple of 256) is therefore *already in the file we have*: it is the top-left
    64x64 block, no second recovery pass and no second checkpoint pair required.

    Checked against real weights, not just algebra: least-squares recovery of `R` from
    `transformer_blocks.0.adaln_proj.linear.weight` in the full BF16 diffusers checkpoint against
    `blocks.0.adaln_proj.linear.{weight,weight_scale}` in the int8 file agreed on the sign of
    every entry over four different 64-column groups, and `max|W R - W'| = 2.105e-3` against an
    int8 half-step of 2.161e-3 -- i.e. the residual is the rounding floor and nothing else.  The
    same check on `qkv_proj`, `mlp.fc2` and `attn.out_proj` at group 256 also sits exactly at
    their half-steps, so the denoiser shares the encoder's and the VAE's rotation family.

    Fails closed: the returned matrix is asserted exactly orthogonal before it is handed out.
    """
    order = signs256.shape[0]
    if group_size > order or order % group_size or (group_size & (group_size - 1)):
        raise ValueError(f"group size {group_size} is not a power-of-two divisor of the recovered order {order}")
    block = signs256[:group_size, :group_size].to(torch.float32)
    err = (block.T @ block - group_size * torch.eye(group_size)).abs().max().item()
    if err != 0.0:
        raise RuntimeError(f"the order-{group_size} ConvRot block is not exactly orthogonal (err {err:.3e})")
    return block / math.sqrt(group_size)


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
#   B70_H3_XFER=host|direct       route for every cross-card tensor move (default host; see the
#                                 cross-card section below and the 2026-09-18 fault note)
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
# IS IT SAFE TO DROP THE HOST BUFFER THE INSTANT `.to(device)` RETURNS?  Yes -- verified against
# this venv's torch 2.14.0+xpu (`torch.version.xpu` 20260100, git 08187d9e0), 2026-09-18. No XPU
# C++ sources ship with the wheel, but `torch/lib/libtorch_xpu.so` is not stripped and the SYCL
# `code_location` constants carry the original file and line. `copy_stub` for XPU dispatches to
# `at::native::xpu::_copy_xpu`, which branches on `non_blocking`; the `non_blocking == false`
# branch is `queue.memcpy(dst, src, nbytes).wait()` -- an unconditional host-side
# `sycl::event::wait()` right after the memcpy, at `torch-xpu-ops/src/ATen/native/xpu/Copy.cpp`
# line 313, with no `is_pinned` test on that path. So when `.to(device)` returns, the host bytes
# have already been read, and `del t` (which frees the pread buffer) and `release()` (which only
# fadvises the page cache) are both safe with no `torch.xpu.synchronize()` in between.
# For the record, the `non_blocking=True` pageable path is also buffer-safe by a different route:
# it stages through the caching host allocator (a CPU `memcpy` into a pinned block, then an async
# device copy from the staging block, then `record_event`) -- the destination, not the source, is
# what needs a synchronize there. Re-check this if the venv's torch is rebased.
#
# A row slice is a contiguous byte range in a row-major tensor, so `get_tensor(key, row_slice)`
# reads only those rows -- the qkv split reads a third of `qkv_proj` three times instead of the
# whole tensor three times.
# ---------------------------------------------------------------------------------------------

LOADER = os.environ.get("B70_H3_LOADER", "pread").strip().lower()
if LOADER not in ("pread", "mmap"):
    raise SystemExit(f"B70_H3_LOADER must be 'pread' or 'mmap', not {LOADER!r}")


# ---------------------------------------------------------------------------------------------
# Cross-card transfers (`B70_H3_XFER`, default `host`)
# ---------------------------------------------------------------------------------------------
#
# 2026-09-18, session 10: the first run that reached `sample` died three seconds in with
# `UR_RESULT_ERROR_DEVICE_LOST`, and the kernel logged 25 copy-engine (`EngineClass: 3 bcs`) page
# faults on `xe 0000:03:00.0` -- the card holding blocks 0..23 -- followed by CAT errors, a bcs
# engine reset and a device coredump. The moment it died is the moment hidden states first cross
# from xpu:0 to xpu:1 at the block-24 split, i.e. the first device-to-device copy this process
# ever issues.  See `notes/2026-09-18-gpu-fault-first-light.md`.
#
# HYPOTHESIS, not proof: `x.to(other_card)` between two XPUs in one process is a peer-to-peer
# PCIe copy issued on the blitter, and this host has faulted on peer access before -- the
# 2026-09-17 07:17Z ccs fault on both cards was attributed to oneCCL's non-simple SYCL kernels
# using peer memory access (qwen38 lane `DO-NOT-REPEAT.md`, 2026-09-17 row). The FP8 service,
# which runs on both cards for hours, never does P2P: its oneCCL simple thresholds are pinned at
# 4 GiB and its allreduce is host-waited.
#
# So the default route is through host RAM: synchronize the source card, copy device->host into a
# fresh CPU tensor, copy host->device onto the target card, synchronize the target. Two PCIe
# transfers instead of one, and the staging buffer is one tensor's worth of host RAM (the packed
# hidden state at 256x448x124, not a weight), which is why this is affordable per block boundary.
#
# A COPY IS A COPY: `host` and `direct` move the same bytes and produce bitwise identical
# tensors. This switch changes the route, never the arithmetic, so a `host` run and a `direct`
# run are comparable hash for hash.
XFER = os.environ.get("B70_H3_XFER", "host").strip().lower()
if XFER not in ("host", "direct"):
    raise SystemExit(f"B70_H3_XFER must be 'host' or 'direct', not {XFER!r}")


def cross_card(torch, t, target, *, mode: str | None = None):
    """Move `t` to `target`, staging through host RAM unless `B70_H3_XFER=direct`.

    Bit-exact either way: a copy does not change values, so `host` and `direct` return tensors
    that compare equal bit for bit and hash identically. The only difference is the route -- two
    PCIe transfers through a host buffer, or one device-to-device transfer on the blitter.

    On the `host` route the source card is synchronized before the device->host copy (so the
    bytes read are the bytes the last kernel wrote) and the target card after the host->device
    copy. That second synchronize is belt and braces rather than a correctness requirement: this
    venv's torch issues a blocking `queue.memcpy(...).wait()` for `non_blocking=False`, so the
    staging tensor is already safe to free when `.to()` returns (see the loader section above,
    where the same fact is what makes `release()` safe). It is cheap and it is explicit, so it
    stays. Non-XPU endpoints and same-device moves fall through to a plain `.to()`; a same-device
    move returns the tensor untouched.
    """
    if not isinstance(t, torch.Tensor):
        return t
    target = torch.device(target)
    if t.device == target:
        return t
    chosen = (mode or XFER).strip().lower()
    if chosen == "direct" or t.device.type != "xpu" or target.type != "xpu":
        return t.to(target, non_blocking=False)
    torch.xpu.synchronize(t.device)
    staged = t.to("cpu", copy=True)
    out = staged.to(target)
    torch.xpu.synchronize(target)
    del staged
    return out

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
    # The encoder's group size used to be a constant here.  It is the file's to declare, and the
    # denoiser proved why that matters: *its* adaln_proj declares 64, not 256.  Read and check.
    declared = {int(m["convrot_groupsize"]) for m in read_comfy_quant(INT8_TEXT_ENCODER, header).values()}
    if declared != {256}:
        raise RuntimeError(
            f"the text encoder declares ConvRot group sizes {sorted(declared)}, not just 256; "
            "this loader places one rotation for all of its Linears and would be wrong"
        )
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
    import torch.nn.functional as F
    from diffusers import MiniMaxH3Transformer3DModel

    primary = torch.device(f"xpu:{args.cards[0]}")
    secondary = torch.device(f"xpu:{args.cards[1]}")
    variant = args.denoiser
    quantized = variant == "int8"
    path = denoiser_path(variant)
    AdaLNTableEmbedder, PrunedAdaLNModulation, PrunedAdaLNOut = make_pruned_adaln_modules(torch, nn)
    ConvRotLinear = make_convrot_linear(torch, nn, F)
    block_dtype = torch.bfloat16
    adaln_out_dtype = torch.float32 if args.adaln_out_dtype == "fp32" else torch.bfloat16

    with phase("load.skeleton", timings):
        # Everything here is built on `meta`: no host allocation, no init, nothing to page.
        with torch.device("meta"):
            model = MiniMaxH3Transformer3DModel.from_config(config)
            if not quantized:
                # Install the pruned AdaLN form.  `time_proj` becomes an identity and
                # `time_embedder` becomes the table lerp, so the stock `forward` (L641-642) needs
                # no patching at all.
                model.time_proj = nn.Identity()
                for block in model.transformer_blocks:
                    block.adaln_proj = PrunedAdaLNModulation(HIDDEN_SIZE, adaln_out_dtype)
                model.norm_out = PrunedAdaLNOut(HIDDEN_SIZE, config["final_norm_eps"], adaln_out_dtype)
            # On the int8 path there is NO module swap: the checkpoint carries the unpruned AdaLN
            # branch, so `time_proj`, `time_embedder`, every `adaln_proj` and `norm_out` stay the
            # stock diffusers modules and the stock arithmetic (silu, then the 2688-wide
            # projection) runs unchanged.  Only the *weights* of the quantized Linears are
            # substituted, below.
        model.eval()

    header = read_header(path)
    remap = build_remap(config["num_layers"], config["num_refiner_layers"], variant)
    quant: dict[str, QuantSlice] = {}
    rotations: dict[tuple, object] = {}
    if quantized:
        quant = build_quant_map(config["num_layers"], header, read_comfy_quant(path, header))
        groups = sorted({q.group_size for q in quant.values()})
        LOG.info("int8 denoiser: %d quantized Linears, ConvRot group sizes %s", len(quant), groups)
        if args.denoiser_rotation == "hadamard":
            if not CONVROT_ROTATION.exists():
                raise FileNotFoundError(
                    f"{CONVROT_ROTATION} is missing. Regenerate it with "
                    "scripts/recover-convrot-rotation.py (CPU-only), or pass "
                    "--denoiser-rotation none to A/B the unrotated path."
                )
            with open_tensor_reader(CONVROT_ROTATION) as fh:
                signs = fh.get_tensor("convrot_signs")
            # One bf16 copy per (group size, card): every ConvRotLinear on a card shares it.
            for g in groups:
                base = convrot_rotation(torch, signs, g)
                for dev in (primary, secondary):
                    rotations[(g, dev)] = base.to(device=dev, dtype=torch.bfloat16)
            del signs, base
        else:
            LOG.warning("--denoiser-rotation none: this is the A/B control and WILL produce garbage "
                        "if the rotation is real")

    lora: LoraPlan | None = None
    if args.lora:
        lora_path, lora_scale = parse_lora_arg(args.lora)
        lora = build_lora_plan(lora_path, lora_scale, header, remap, quant)
        # Fail closed, the same rule `build_quant_map` applies: an adapter tensor that lands
        # nowhere is a mapping bug, and the only symptom would be a subtly wrong clip.
        if lora.shape_errors:
            raise RuntimeError(f"{lora_path.name}: {len(lora.shape_errors)} shape mismatches, "
                               f"e.g. {lora.shape_errors[:3]}")
        if lora.unmatched:
            raise RuntimeError(
                f"{lora_path.name}: {len(lora.unmatched)} LoRA keys have no destination in the "
                f"{variant} denoiser, e.g. {lora.unmatched[:5]}"
            )
        LOG.info(
            "lora %s scale %.4f: %d pairs -> %d merged + %d runtime destinations%s",
            lora_path.name, lora_scale, len(lora.pairs), len(lora.dense), len(lora.runtime),
            f", {gib(lora.runtime_bytes())} resident" if lora.runtime else "",
        )

    def device_for(name: str):
        if name.startswith("transformer_blocks."):
            return primary if int(name.split(".")[1]) < plan.split_index else secondary
        return primary

    with phase("load.stream", timings):
        LOG.info("denoiser loader: %s (B70_H3_LOADER), checkpoint %s", LOADER, path.name)
        lora_reader = (
            open_tensor_reader(lora.path, lora.header) if lora is not None else contextlib.nullcontext()
        )
        with open_tensor_reader(path, header) as fh, lora_reader as lfh:
            if not quantized:
                table = fh.get_tensor("adaln_t_table").to(device=primary, dtype=torch.float32)
                model.time_embedder = AdaLNTableEmbedder(table)
                fh.release("adaln_t_table")
            placed = 0
            merged = 0  # dense destinations the LoRA was folded into
            for name, src in remap.items():
                dev = device_for(name)
                # A row slice is a contiguous byte range, so the pread loader reads only those
                # rows: the qkv split reads a third of `qkv_proj` three times, not the whole
                # tensor three times.  The mmap loader slices the view, exactly as before.
                t = fh.get_tensor(src.key, src.row_slice)
                if src.swap_halves:
                    half = t.shape[0] // 2
                    t = torch.cat((t[half:], t[:half]), dim=0)
                dtype = target_dtype(name, args.adaln_dtype, variant)
                sl = lora.dense.get(name) if lora is not None else None
                if sl is None:
                    t = t.to(device=dev, dtype=dtype).contiguous()
                else:
                    # Merge exactly: widen W to float32 (bf16 -> float32 loses nothing), add the
                    # float32 delta, and round ONCE, into the dtype the weight would have had.
                    # The no-LoRA branch above is left byte-for-byte as it was.
                    t = t.to(device=dev, dtype=torch.float32)
                    t = (t + lora_delta(torch, lfh, sl, dev)).to(dtype).contiguous()
                    merged += 1
                set_submodule_tensor(model, name, t)
                del t  # the module owns the device tensor; drop the host-side name and the buffer
                fh.release(src.key, src.row_slice)
                placed += 1
                if placed % 100 == 0:
                    LOG.info("  placed %d/%d tensors (host peak RSS %s)", placed, len(remap), gib(host_rss_bytes()))
                log_host_mem("load.stream", placed, len(remap))
                drop_file_pagecache(path, placed)

            # --- the quantized Linears, int8 path only -------------------------------------
            # Same dequant contract as the text encoder (`_build_text_encoder`, step 2): the int8
            # weight and its per-row float32 scale go to the card as they are stored, and
            # `ConvRotLinear` rotates the activation and applies the scale after accumulation.
            # The only differences are that the destination Linears here are *sliced* out of
            # Comfy's fused tensors, and that two group sizes are in play.
            total = len(remap) + len(quant)
            runtime_lora = 0  # ConvRotLinears carrying an additive LoRA term
            for module, q in quant.items():
                dev = device_for(module)
                parent_path, _, leaf = module.rpartition(".")
                parent = model.get_submodule(parent_path)
                qw = fh.get_tensor(q.key + ".weight", q.row_slice)
                sc = fh.get_tensor(q.key + ".weight_scale", q.row_slice)
                bias = None
                if q.has_bias:
                    bias = fh.get_tensor(q.key + ".bias").to(device=dev, dtype=torch.bfloat16)
                if q.swap_halves:
                    # The output axis again -- weight and scale must be permuted together.
                    half = qw.shape[0] // 2
                    qw = torch.cat((qw[half:], qw[:half]), dim=0)
                    sc = torch.cat((sc[half:], sc[:half]), dim=0)
                qw = qw.to(device=dev).contiguous()
                sc = sc.to(device=dev, dtype=torch.float32).contiguous()
                # `adaln_proj.linear` is the one Linear diffusers probes with
                # `get_parameter_dtype` before calling; pin it to the unpruned checkpoint's bf16.
                is_adaln = module.endswith("adaln_proj.linear")
                # The int8 weight cannot absorb a LoRA (re-quantizing would move every weight), so
                # the adapter rides along as an additive low-rank term evaluated per call.
                sl = lora.runtime.get(module) if lora is not None else None
                lora_a, lora_b = lora_runtime_tensors(torch, lfh, sl, dev) if sl is not None else (None, None)
                setattr(
                    parent,
                    leaf,
                    ConvRotLinear(
                        qw,
                        sc,
                        bias,
                        rotations.get((q.group_size, dev)),
                        q.group_size,
                        compute_dtype=torch.bfloat16 if is_adaln else None,
                        out_dtype=adaln_out_dtype if is_adaln else None,
                        lora_a=lora_a,
                        lora_b=lora_b,
                        lora_scale=sl.scale if sl is not None else 1.0,
                    ),
                )
                if sl is not None:
                    runtime_lora += 1
                del qw, sc, bias, lora_a, lora_b  # the ConvRotLinear buffers own them now
                for suffix in (".weight", ".weight_scale"):
                    fh.release(q.key + suffix, q.row_slice)
                if q.has_bias:
                    fh.release(q.key + ".bias")
                placed += 1
                if placed % 100 == 0:
                    LOG.info("  placed %d/%d tensors (host peak RSS %s)", placed, total, gib(host_rss_bytes()))
                log_host_mem("load.stream", placed, total)
                drop_file_pagecache(path, placed)
        log_host_mem("load.stream", placed, len(remap) + len(quant), force=True)
        # `rope.inv_freq` is non-persistent and recomputed from the config, not loaded
        # (transformer_minimax_h3.py L88-91).  Rebuild it on the primary card and cross-check.
        freq_dim = config["rope_freq_dim"]
        inv_freq = 1.0 / (
            config["rope_theta"] ** (torch.arange(0, 2 * freq_dim, 2, dtype=torch.float32) / (2 * freq_dim))
        )
        set_submodule_tensor(model, "rope.inv_freq", inv_freq.to(primary))
        with open_tensor_reader(path, header) as fh:
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

    if lora is not None:
        if merged != len(lora.dense) or runtime_lora != len(lora.runtime):
            raise RuntimeError(
                f"lora application is incomplete: merged {merged}/{len(lora.dense)} dense, "
                f"attached {runtime_lora}/{len(lora.runtime)} runtime"
            )
        LOG.info(
            "lora applied: %d weights merged exactly (float32, one rounding), %d ConvRotLinears "
            "carry the additive term (%s resident) -- the two are NOT the same arithmetic",
            merged, runtime_lora, gib(lora.runtime_bytes()),
        )

    _install_boundary_hooks(torch, model, plan.split_index, primary, secondary)
    LOG.info("cross-card transfer route: %s (B70_H3_XFER)", XFER)
    if quantized:
        LOG.info(
            "int8 denoiser: %d ConvRotLinears placed, transient dequant peak %s (leave it free)",
            len(quant),
            gib(plan.dequant_peak_bytes),
        )
    LOG.info(
        "denoiser (%s) split at block %d: %s on %s, %s on %s",
        variant,
        plan.split_index,
        gib(plan.card0_bytes),
        primary,
        gib(plan.card1_bytes),
        secondary,
    )
    return model, primary, secondary, lora


def _install_boundary_hooks(torch, model, split_index: int, primary, secondary) -> None:
    """Move the per-forward tensors across the PCIe boundary exactly once.

    `hidden_states` flows block to block, so it crosses once on its own.  `temb`, `adaln_indices`
    and the two `rope` outputs are read by *every* block from the model's forward frame, so each
    secondary block would pull them across again -- hence the per-forward transfer cache, which is
    the same device-crossing policy as `ltx_layer_shard.py::_move` / `_forward_transfers`.

    Every crossing here goes through `cross_card()`, i.e. through host RAM unless
    `B70_H3_XFER=direct`: these are the transfers the 2026-09-18 copy-engine fault happened on.
    """
    cache: dict = {}

    def move(value):
        if isinstance(value, torch.Tensor):
            if value.device == secondary:
                return value
            key = id(value)
            if key not in cache:
                # the source tensor is kept in the cache entry so `id(value)` cannot be reused by
                # another tensor while this forward runs
                cache[key] = (value, cross_card(torch, value, secondary))
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
        # the gather back to the primary card after the last block, for norm_out and the VAE
        return cross_card(torch, output, primary) if isinstance(output, torch.Tensor) else output

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


# num_inference_steps is the number of SIGMA GRID POINTS, terminal 0 included, so it drives
# `steps - 1` transformer evaluations (NFE) -- `MiniMaxH3Scheduler.set_timesteps`,
# scheduling_minimax_h3.py L133-136, verified against the source on this host.  Upstream always
# quotes NFE, so every published number needs the +1 here (which is exactly what lightx2v's own
# runner does: `scheduler_grid_points = args.inference_steps + 1`).
#
#   base model      50 NFE  -> 51   (lightx2v/ModelTC reference runner, DIFFUSERS_SETUP_AND_INFERENCE.md)
#                   20 NFE  -> 21   (official ComfyUI template, turbo_mode off)
#   8-step turbo    8 NFE   ->  9   (ModelTC spec table "FL2VA Turbo 8-step v1.0", ComfyUI
#                                    template `turbo_steps` = 8; 4 NFE also supported)
#
# There is no guidance_scale / true_cfg_scale at any step count: the released checkpoints are
# CFG-distilled and every step is a single forward pass.  See notes/2026-09-18-steps-and-lora.md
# for the full citation list.
DEFAULT_STEPS = 51
TURBO_STEPS = 9

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
        default=DEFAULT_STEPS,
        help=f"num_inference_steps -- SIGMA GRID POINTS, terminal 0 included, so this drives "
        f"steps - 1 transformer evaluations (MiniMaxH3Scheduler.set_timesteps docstring, "
        f"scheduling_minimax_h3.py L133-136). The default {DEFAULT_STEPS} is the reference runner's "
        f"50 NFE + 1. With the 8-step turbo LoRA pass --steps {TURBO_STEPS} (8 NFE); 21 (20 NFE) is "
        "the official ComfyUI template's base setting. There is no guidance_scale: the checkpoint "
        "is CFG-distilled and every step is one forward pass. See notes/2026-09-18-steps-and-lora.md.",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--video-shift", type=float, default=None, help="override the video scheduler shift (default 12.0)")
    p.add_argument("--audio-shift", type=float, default=None, help="override the audio scheduler shift (default 3.0)")
    p.add_argument(
        "--denoiser",
        choices=sorted(DENOISERS),
        default=DEFAULT_DENOISER,
        help="which denoiser checkpoint to load (env B70_H3_DENOISER). `pruned` is the BF16 file "
        "whose AdaLN branch is a rank-8 fit, error below the bf16 noise floor, every other weight "
        "exact; `int8` is the full INT8 ConvRot file, whose AdaLN branch is exact in form but "
        "whose 250 block Linears are int8. Default stays `pruned` until the pruned control has "
        "rendered a clip.",
    )
    p.add_argument(
        "--lora",
        default=os.environ.get("B70_H3_LORA") or None,
        metavar="PATH[:SCALE]",
        help="a ComfyUI-format LoRA to apply to the denoiser (env B70_H3_LORA). SCALE is the user "
        "strength, default 1.0, and multiplies the file's own alpha/rank. On dense BF16 weights "
        "the adapter is MERGED at load time (W + s*B@A in float32, rounded once); on "
        "`--denoiser int8` the quantized Linears cannot absorb it, so there it stays an additive "
        f"low-rank term inside ConvRotLinear. The 8-step turbo adapter is {DEFAULT_LORA.name}; "
        f"it is the precondition for --steps {TURBO_STEPS} (= 8 NFE).",
    )
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
    p.add_argument(
        "--denoiser-rotation",
        choices=["hadamard", "none"],
        default="hadamard",
        help="the ConvRot activation rotation for `--denoiser int8`. `hadamard` takes both orders "
        "it needs (256 for the attention/MLP Linears, 64 for adaln_proj) from "
        "data/convrot-hadamard-256.safetensors -- the order-64 one is that matrix's leading 64x64 "
        "block, see convrot_rotation(). `none` is the A/B control. Ignored on the pruned path.",
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


def diffusers_parameter_names() -> set[str] | None:
    """The authoritative diffusers parameter set, from the full BF16 checkpoint's index.

    This is what `MiniMaxH3Transformer3DModel(config).state_dict()` would list, read as JSON so
    the dry run never has to import diffusers or torch.  `rope.inv_freq` is not in it: diffusers
    registers it non-persistent and recomputes it (transformer_minimax_h3.py L88-91), and the
    loader recomputes it too, so it is added here to keep the two sides comparable.
    """
    index_path = REPO_ORIGINAL / "transformer" / "diffusion_pytorch_model.safetensors.index.json"
    if not index_path.exists():
        return None
    return set(json.loads(index_path.read_text())["weight_map"]) | {"rope.inv_freq"}


def check_coverage(variant: str, header: dict, config: dict, quant_meta: dict[str, dict]) -> int:
    """Both directions of the load contract, from headers alone.

    1. every tensor in the checkpoint is consumed by something, and
    2. every diffusers parameter is produced -- by the dense remap, by a ConvRotLinear
       substitution, or by a named structural substitution (the pruned AdaLN table) --
    with nothing left over on either side.
    """
    num_layers, num_refiner = config["num_layers"], config["num_refiner_layers"]
    remap = build_remap(num_layers, num_refiner, variant)
    quant = build_quant_map(num_layers, header, quant_meta) if variant == "int8" else {}

    # ---- checkpoint side ----------------------------------------------------------------
    missing = sorted({s.key for s in remap.values()} - set(header))
    if missing:
        print(f"  FAIL: {len(missing)} remapped source keys are absent, e.g. {missing[:5]}")
        return 1
    consumed = {s.key for s in remap.values()} | {"rope.inv_freq"}
    for module, q in quant.items():
        consumed |= set(q.tensor_keys(header))
    if variant == "pruned":
        consumed.add("adaln_t_table")
    unconsumed = sorted(set(header) - consumed)

    # ---- diffusers side -----------------------------------------------------------------
    produced = set(remap)
    substituted: set[str] = set()
    for module, q in quant.items():
        substituted |= set(q.param_names(module, header))
    # `rope.inv_freq` is recomputed from the config by the loader and cross-checked against the
    # checkpoint's copy (max drift must be < 1e-6), so it is produced without being remapped.
    structural: set[str] = {"rope.inv_freq"}
    if variant == "pruned":
        # The rank-8 table stands in for the whole unpruned timestep MLP; `adaln_t_table` is an
        # `AdaLNTableEmbedder` buffer, not any of these four parameters.
        structural |= {
            "time_embedder.linear_1.weight",
            "time_embedder.linear_1.bias",
            "time_embedder.linear_2.weight",
            "time_embedder.linear_2.bias",
        }
    expected = diffusers_parameter_names()

    print(f"  checkpoint tensors    : {len(header)}")
    print(f"  dense remap           : {len(remap)} diffusers parameters from "
          f"{len({s.key for s in remap.values()})} tensors")
    if quant:
        groups = sorted({q.group_size for q in quant.values()})
        print(f"  ConvRot substitutions : {len(quant)} Linears -> {len(substituted)} parameters, "
              f"from {sum(len(q.tensor_keys(header)) for q in quant.values())} tensors "
              f"(group sizes {groups})")
    if len(structural) > 1:
        print(f"  structural substitute : {len(structural) - 1} parameters replaced by adaln_t_table, "
              "+ rope.inv_freq recomputed")
    else:
        print("  structural substitute : rope.inv_freq recomputed from the config")
    print(f"  tensors not consumed  : {len(unconsumed)}"
          f"{' -> ' + str(unconsumed[:5]) if unconsumed else '  (0, every tensor is used)'}")

    rc = 1 if unconsumed else 0
    if expected is None:
        print("  (skipping the diffusers-parameter check: the full BF16 checkpoint is not on this host)")
        return rc
    accounted = produced | substituted | structural
    unproduced = sorted(expected - accounted)
    extra = sorted(accounted - expected)
    print(f"  diffusers parameters  : {len(expected)} expected, {len(accounted)} accounted for")
    if unproduced:
        print(f"  FAIL: {len(unproduced)} diffusers parameters would stay on meta, e.g. {unproduced[:5]}")
        rc = 1
    if extra:
        print(f"  FAIL: {len(extra)} produced names are not diffusers parameters, e.g. {extra[:5]}")
        rc = 1
    if not unproduced and not extra:
        print("  coverage              : EXACT -- 0 tensors left over, 0 parameters left on meta")
    return rc


def dry_run(args) -> int:
    """Configs + safetensors headers only. No torch.xpu, no diffusers, no device tensor.

    The one exception to "headers only" is `read_comfy_quant`, which preads the ~90-byte ASCII
    JSON blob of each quantized Linear (about 22 KB for the whole int8 denoiser). Those blobs are
    the file's own declaration of its quantization format, so deriving the remap from them is the
    difference between a header-driven plan and a hardcoded guess. It still imports no torch.
    """
    config = json.loads(TRANSFORMER_CONFIG.read_text())
    variant = args.denoiser
    denoiser = denoiser_path(variant)
    print("=" * 96)
    print(f"MiniMax-H3 two-B70 pipeline -- DRY RUN (CPU only, headers only, nothing placed)")
    print(f"denoiser: {variant}  {denoiser.name}")
    print("=" * 96)

    for label, path in [
        (f"denoiser ({variant})", denoiser),
        ("int8 text encoder", INT8_TEXT_ENCODER),
        ("video vae (fp32 repo)", VAE_DIR / "diffusion_pytorch_model.safetensors.index.json"),
        ("audio vae (fp32 repo)", AUDIO_VAE_DIR / "diffusion_pytorch_model.safetensors"),
        ("convrot rotation", CONVROT_ROTATION),
    ]:
        ok = path.exists()
        size = path.stat().st_size if ok else 0
        print(f"  {'OK ' if ok else 'MISSING'} {label:24s} {size / 1e9:8.2f} GB  {path}")
    print()

    header = read_header(denoiser)
    print(f"denoiser header: {len(header)} tensors, {sum(tensor_bytes(e) for e in header.values()) / 1e9:.2f} GB stored")

    quant_meta = read_comfy_quant(denoiser, header) if variant == "int8" else {}
    rc = check_coverage(variant, header, config, quant_meta)
    if rc:
        return rc
    if variant == "pruned":
        table = header["adaln_t_table"]
        print(f"  adaln_t_table         : {table['dtype']} {table['shape']}  "
              f"(grid of {table['shape'][0] - 1} + terminal row)")
    else:
        fmt = sorted({(m["format"], m["convrot"], m["convrot_groupsize"]) for m in quant_meta.values()})
        for f in fmt:
            n = sum(1 for m in quant_meta.values()
                    if (m["format"], m["convrot"], m["convrot_groupsize"]) == f)
            print(f"  comfy_quant           : {n:4d} Linears  format={f[0]} convrot={f[1]} groupsize={f[2]}")
        print(f"  rotation source       : {'present' if CONVROT_ROTATION.exists() else 'MISSING'} "
              f"{CONVROT_ROTATION.name} ({args.denoiser_rotation}; the order-64 block is its leading 64x64)")
    print()

    plan = plan_split(header, config, args.adaln_dtype, args.split_index, variant, quant_meta or None)
    print("layer split (LTX byte-balancing policy, ltx_layer_shard.py::install):")
    print(f"  blocks                : {plan.num_layers}")
    print(f"  per-block bytes       : min {plan.block_bytes[0] / 1e6:.1f} MB, max {max(plan.block_bytes) / 1e6:.1f} MB")
    print(f"  non-block bytes       : {plan.non_block_bytes / 1e9:.3f} GB ({gib(plan.non_block_bytes)})")
    print(f"  split_index           : {plan.split_index}  -> blocks 0..{plan.split_index - 1} | {plan.split_index}..{plan.num_layers - 1}")
    print(f"  card {args.cards[0]} (primary)      : {plan.card0_bytes / 1e9:8.3f} GB  {gib(plan.card0_bytes)}")
    print(f"  card {args.cards[1]} (secondary)    : {plan.card1_bytes / 1e9:8.3f} GB  {gib(plan.card1_bytes)}")
    print(f"  imbalance             : {abs(plan.card0_bytes - plan.card1_bytes) / 1e6:.1f} MB")
    print(f"  free per card (32 GiB): {gib(32 * 2**30 - plan.card0_bytes)} / {gib(32 * 2**30 - plan.card1_bytes)}")
    if plan.variant == "int8":
        print(f"  of which quantized    : {plan.quant_bytes / 1e9:8.3f} GB  {gib(plan.quant_bytes)} "
              f"(int8 weights + f32 scales + biases)")
        print(f"  rotation per card     : {plan.rotation_bytes / 1e3:8.1f} kB")
        print(f"  transient dequant peak: {plan.dequant_peak_bytes / 1e6:8.1f} MB  "
              f"{gib(plan.dequant_peak_bytes)}  <-- must stay free ON TOP of the resident bytes")
        worst = max(plan.card0_bytes, plan.card1_bytes) + plan.dequant_peak_bytes
        print(f"  worst card + transient: {worst / 1e9:8.3f} GB  {gib(worst)}  "
              f"-> {gib(32 * 2**30 - worst)} free")
    print()

    if args.lora:
        rc = dry_run_lora(args, config, header, quant_meta)
        if rc:
            return rc

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
    print(f"  steps                 : {args.steps} sigma grid points -> {args.steps - 1} transformer "
          f"evaluations (NFE){'' if args.lora else '   [base model: 50 NFE reference / 20 NFE ComfyUI template]'}")
    if args.lora:
        print(f"                          the 8-step turbo LoRA wants 8 NFE, i.e. --steps {TURBO_STEPS}"
              f"{'  OK' if args.steps == TURBO_STEPS else '  <-- MISMATCH'}")
    print(f"  schedulers            : video shift {json.loads((SCHEDULER_DIR / 'scheduler_config.json').read_text())['shift']}, "
          f"audio shift {json.loads((AUDIO_SCHEDULER_DIR / 'scheduler_config.json').read_text())['shift']}, cfg-free "
          f"(rectified-flow Euler, eta 0; no guidance_scale exists)")
    print()

    if args.verify_remap:
        rc = verify_remap_against_full(config, variant)
        if rc:
            return rc

    print("dry run complete: no GPU touched, no service touched, nothing downloaded.")
    return 0


def dry_run_lora(args, config: dict, header: dict, quant_meta: dict[str, dict]) -> int:
    """The LoRA half of the dry run: how many pairs matched, where they land, what did not match.

    Headers plus the 4-byte `alpha` scalars.  No torch, no tensor data, nothing placed.
    """
    lora_path, scale = parse_lora_arg(args.lora)
    variant = args.denoiser
    print(f"lora: {lora_path}")
    if not lora_path.exists():
        print(f"  FAIL: {lora_path} does not exist")
        return 1
    size = lora_path.stat().st_size
    remap = build_remap(config["num_layers"], config["num_refiner_layers"], variant)
    quant = build_quant_map(config["num_layers"], header, quant_meta) if variant == "int8" else {}
    plan = build_lora_plan(lora_path, scale, header, remap, quant)

    meta = read_metadata(lora_path)
    print(f"  file                  : {size / 1e9:.3f} GB, {len(plan.header)} tensors, "
          f"{len(plan.pairs)} (A, B) pairs")
    if meta:
        for key in ("training_rank", "training_alpha", "training_scale", "base_model",
                    "source_format", "target_format", "qkv_fusion", "swi_glu_mapping"):
            if key in meta:
                print(f"    {key:20s}: {meta[key]}")
    ranks = sorted({(p.rank, p.alpha, round(p.strength, 6)) for p in plan.pairs.values()})
    for rank, alpha, strength in ranks:
        n = sum(1 for p in plan.pairs.values() if p.rank == rank)
        print(f"  rank {rank:<4d}            : {n:4d} pairs, alpha {alpha}, alpha/rank {strength:.6f}, "
              f"x user scale {scale} = {strength * scale:.6f}")
    print(f"  matched pairs         : {len(plan.matched)}/{len(plan.pairs)}")
    print(f"  merged destinations   : {len(plan.dense)}  (dense BF16 weights; W + s*B@A in float32, "
          f"rounded once -- exact)")
    print(f"  runtime destinations  : {len(plan.runtime)}  (ConvRotLinear; additive term, "
          f"NOT a merge -- the int8 weight cannot absorb it)")
    if plan.runtime:
        print(f"  runtime resident      : {plan.runtime_bytes() / 1e9:.3f} GB  {gib(plan.runtime_bytes())}  "
              f"<-- on top of the split plan above")
    if plan.dense:
        widest = max(
            ((s.row_slice[1] - s.row_slice[0]) if s.row_slice else s.pair.out_features)
            * s.pair.in_features * 4
            for s in plan.dense.values()
        )
        print(f"  merge transient peak  : {widest / 1e6:8.1f} MB on the destination card "
              f"(one float32 [out, in] delta at a time)")
    if plan.shape_errors:
        print(f"  FAIL: {len(plan.shape_errors)} shape mismatches")
        for e in plan.shape_errors[:5]:
            print(f"    {e}")
    if plan.unmatched:
        print(f"  FAIL: {len(plan.unmatched)} unmatched LoRA keys")
        for k in plan.unmatched[:10]:
            print(f"    {k}")
    if not plan.shape_errors and not plan.unmatched:
        print("  unmatched keys        : 0  (every pair in the file has a destination)")
    print()
    return 1 if (plan.shape_errors or plan.unmatched) else 0


VERIFY_ROWS = 256  # output rows sampled per quantized Linear; keeps every read a few MB


def verify_remap_against_full(config: dict, variant: str = "pruned") -> int:
    """Compare a sample of remapped tensors against the full BF16 diffusers checkpoint.

    Dense tensors must be *bit-identical*: neither build re-derives them, so the qkv split order
    and the SwiGLU half order are pinned by this check.

    Quantized tensors cannot be identical by construction, so they are checked against the thing
    that must be true instead: dequantizing them, `W' = int8 * scale`, must reproduce `W R` to
    within the int8 rounding floor, where `R` is the ConvRot rotation for that Linear's declared
    group size.  A failure here means the rotation, the group size, the scale axis or the row
    mapping is wrong -- all four of which would otherwise only show up as a garbage clip.

    Reads are row slices through the pread reader, a few MB per sample, never a whole tensor.
    """
    index_path = REPO_ORIGINAL / "transformer" / "diffusion_pytorch_model.safetensors.index.json"
    if not index_path.exists():
        print("  (skipping --verify-remap: the full BF16 checkpoint is not on this host)")
        return 0
    weight_map = json.loads(index_path.read_text())["weight_map"]
    num_layers, num_refiner = config["num_layers"], config["num_refiner_layers"]
    remap = build_remap(num_layers, num_refiner, variant)
    path = denoiser_path(variant)
    header = read_header(path)
    quant = build_quant_map(num_layers, header, read_comfy_quant(path, header)) if variant == "int8" else {}

    import torch

    handles: dict[str, PreadTensorReader] = {}

    def full_rows(name: str, rows: tuple[int, int] | None):
        shard = weight_map[name]
        if shard not in handles:
            handles[shard] = PreadTensorReader(REPO_ORIGINAL / "transformer" / shard)
        return handles[shard].get_tensor(name, rows)

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
        "time_embedder.linear_1.weight",
        "time_embedder.linear_2.weight",
    ]
    failures = 0
    checked = 0
    try:
        with PreadTensorReader(path, header) as fh:
            print("dense remap verification against the full BF16 checkpoint (first 64 input columns):")
            for name in sample:
                if name not in weight_map or name not in remap:
                    continue  # quantized on this path, or absent from this build
                src = remap[name]
                a = fh.get_tensor(src.key, src.row_slice)
                if src.swap_halves:
                    half = a.shape[0] // 2
                    a = torch.cat((a[half:], a[:half]), dim=0)
                b = full_rows(name, None)
                if a.ndim == 2:
                    a, b = a[:, :64], b[:, :64]
                ok = a.shape == b.shape and a.dtype == b.dtype and torch.equal(a, b)
                failures += 0 if ok else 1
                checked += 1
                print(f"  {'EXACT ' if ok else 'DIFFER'} {name:52s} <- {src.key}")

            if quant:
                print(f"\nConvRot dequant verification ({VERIFY_ROWS} output rows per Linear, "
                      "against the full BF16 weights):")
                with open_tensor_reader(CONVROT_ROTATION) as rot_fh:
                    signs = rot_fh.get_tensor("convrot_signs")
                probes = [
                    "transformer_blocks.0.attn.to_q",
                    "transformer_blocks.0.attn.to_v",
                    "transformer_blocks.0.attn.to_out.0",
                    "transformer_blocks.0.ff.net.0.proj",
                    "transformer_blocks.25.ff.net.2",
                    "transformer_blocks.0.adaln_proj.linear",
                    "transformer_blocks.49.adaln_proj.linear",
                ]
                for module in probes:
                    q = quant[module]
                    name = module + ".weight"
                    if name not in weight_map:
                        continue
                    lo = q.row_slice[0] if q.row_slice else 0
                    src_rows = (lo, lo + VERIFY_ROWS)
                    if q.swap_halves:
                        # diffusers row i is Comfy row i + half; sample the diffusers rows.
                        half = header[q.key + ".weight"]["shape"][0] // 2
                        src_rows = (half, half + VERIFY_ROWS)
                    qw = fh.get_tensor(q.key + ".weight", src_rows).float()
                    sc = fh.get_tensor(q.key + ".weight_scale", src_rows).float()
                    w = full_rows(name, (0, VERIFY_ROWS)).float()
                    R = convrot_rotation(torch, signs, q.group_size)
                    cols = q.group_size  # one group is enough: R is block-diagonal
                    err = ((w[:, :cols] @ R) - (qw * sc)[:, :cols]).abs().max().item()
                    half_step = (sc.abs().max().item()) / 2
                    ok = err <= 1.05 * half_step
                    failures += 0 if ok else 1
                    checked += 1
                    print(f"  {'FLOOR ' if ok else 'ABOVE '} {module:44s} G={q.group_size:<4d} "
                          f"max|WR-W'|={err:.3e} vs int8 half-step {half_step:.3e}")
    finally:
        for h in handles.values():
            h.close()
    print(f"  {checked - failures}/{checked} pass")
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
    denoiser = denoiser_path(args.denoiser)
    header = read_header(denoiser)
    quant_meta = read_comfy_quant(denoiser, header) if args.denoiser == "int8" else None
    plan = plan_split(header, config, args.adaln_dtype, args.split_index, args.denoiser, quant_meta)
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
    transformer, primary, secondary, lora_plan = load_sharded_transformer(args, plan, config, timings)
    # Captured now, because the receipt is written long after the denoiser has been freed.
    lora_receipt = None
    if lora_plan is not None:
        lora_receipt = {
            "path": str(lora_plan.path),
            "sha256": file_digest(lora_plan.path),
            "bytes": lora_plan.path.stat().st_size,
            "user_scale": lora_plan.scale,
            "effective_scales": sorted({round(s.scale, 9) for s in
                                        list(lora_plan.dense.values()) + list(lora_plan.runtime.values())}),
            "metadata": read_metadata(lora_plan.path),
            "pairs": len(lora_plan.pairs),
            "pairs_matched": len(lora_plan.matched),
            "merged_destinations": len(lora_plan.dense),
            "runtime_destinations": len(lora_plan.runtime),
            "runtime_resident_bytes": lora_plan.runtime_bytes(),
            "application": (
                "dense weights merged exactly (W + s*B@A in float32, one rounding); "
                "ConvRotLinear destinations carry an additive runtime term instead, because an "
                "int8 weight cannot absorb a merge"
            ),
        }
    # `--encoder-card` may differ from `--cards[0]`, in which case this is a card crossing
    prompt_embeds = cross_card(torch, prompt_embeds, primary)

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
        latents = cross_card(torch, latents, decode_device)
        video = vae.decode((latents * latents_std + latents_mean).to(vae.dtype), return_dict=False)[0]
        pixel_mean = torch.tensor((0.485, 0.456, 0.406), device=decode_device).view(1, -1, 1, 1, 1)
        pixel_std = torch.tensor((0.229, 0.224, 0.225), device=decode_device).view(1, -1, 1, 1, 1)
        video = (video.float() * pixel_std + pixel_mean).clamp(0, 1)
    del vae
    _free(torch)
    with phase("decode.audio", timings):
        a_mean = torch.tensor(audio_vae.config.latents_mean, device=decode_device).view(1, -1, 1)
        a_std = torch.tensor(audio_vae.config.latents_std, device=decode_device).view(1, -1, 1)
        audio_latents = cross_card(torch, audio_latents, decode_device)
        audio = audio_vae.decode((audio_latents * a_std + a_mean).float(), return_dict=False)[0]
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
        "num_function_evaluations": args.steps - 1,
        "num_inference_steps_note": (
            "sigma grid points, terminal 0 included; NFE = steps - 1 "
            "(MiniMaxH3Scheduler.set_timesteps). Base reference is 50 NFE (steps 51); the 8-step "
            f"turbo LoRA is 8 NFE (steps {TURBO_STEPS}). CFG-distilled: no guidance_scale exists. "
            "See notes/2026-09-18-steps-and-lora.md"
        ),
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
            "denoiser": str(denoiser),
            "denoiser_variant": args.denoiser,
            "denoiser_rotation": args.denoiser_rotation if args.denoiser == "int8" else None,
            "denoiser_header_sha256": file_digest(denoiser, limit=1 << 20),
            "lora": lora_receipt,
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
        "loader": LOADER,
        "cross_card_transfer": XFER,
    }
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    LOG.info("video sha256 %s", receipt["hashes"]["video_tensor_sha256"])
    LOG.info("audio sha256 %s", receipt["hashes"]["audio_tensor_sha256"])
    LOG.info("wrote %s and %s", mp4, out_dir / "receipt.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
