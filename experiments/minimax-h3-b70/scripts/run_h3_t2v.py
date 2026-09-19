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
    Phase 4  decode     video VAE then audio VAE, one at a time, on whichever card the denoiser
                        release left emptiest (or `--vae-card`).  Both are FLOAT32 on the card --
                        `AutoencoderKLMiniMaxH3._keep_in_fp32_modules` pins every module it has,
                        so `torch_dtype=float16` narrows nothing: 9.700 + 0.564 GiB, not half that.
    Phase 5  write      mp4 + audio via PyAV, and a sidecar JSON receipt

Only one large component is resident at a time; each phase frees its component before the next
loads, explicitly (`release_denoiser`, `strip_module_tensors`) rather than by hoping a `del` is
enough, and every phase boundary prints a `[vram]` line per card so the log says what was resident
instead of leaving it to be reconstructed after an OOM (2026-09-19).  Host RAM never holds a full
state dict: every tensor is mmap-sliced out of the checkpoint and copied straight to its card.

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
* `B70_H3_VAE_DECODE=single|two-card` -- the default for `--vae-decode`. `single` is the
  bytewise-gated path (`vae.decode` on one card). `two-card` replicates the video VAE onto the
  second card through `cross_card()` and splits the 105 per-tile decoder calls between the two,
  blending in the original order on the original card: intended to be bit-identical, gated by
  experiment E1 and by reproducing the single-card `video_tensor_sha256`. See
  `decode_video_two_card()` and notes/2026-09-19-speed-plan.md.
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
import threading
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


# ---------------------------------------------------------------------------------------------
# Sharing one activation rotation across the q/k/v ConvRotLinears of a block (lever 6)
#
# `to_q`, `to_k` and `to_v` are three separate `ConvRotLinear`s fed the SAME activation tensor with
# the SAME rotation and the same group size (`build_quant_map`: all three come from Comfy's fused
# `blocks.N.attn.qkv_proj`), so the rotation `x @ R` is computed three times over.  Computing it
# once and handing the other two the same tensor is bit-identical BY CONSTRUCTION -- not "to within
# rounding": it is literally the same tensor object, produced by the same op on the same operands.
#
# The cache is therefore keyed on OBJECT IDENTITY, never on value: a hit requires `x is x_cached`
# and `rotation is rotation_cached` (plus the group size and the compute dtype).  It holds strong
# references to both, so no id can be recycled underneath it, and it has exactly ONE slot, so the
# next miss drops the previous activation and its rotated copy -- at most one extra live tensor,
# and the rotated copy is one the unshared path would have allocated anyway.  A cast (`compute !=
# x.dtype`) makes a fresh tensor per call, so it simply misses and the unshared arithmetic runs.
#
# The slot is thread-local, so two threads can never hand each other a tensor from another card.
# `clear_rotation_cache()` is called at phase boundaries so the slot cannot pin a card allocation
# past the phase that made it.  `test_convrot_linear.py` section 6 proves the bitwise equality and
# checks that the hits actually happen.
# ---------------------------------------------------------------------------------------------

_ROTATION_CACHE = threading.local()
ROTATION_CACHE_STATS = {"hits": 0, "misses": 0}


def clear_rotation_cache() -> None:
    """Drop the shared-rotation slot (and with it its references to a card tensor)."""
    _ROTATION_CACHE.slot = None


def rotation_cache_stats() -> dict:
    return dict(ROTATION_CACHE_STATS)


def _rotation_cache_get(x, rotation, group_size, compute):
    slot = getattr(_ROTATION_CACHE, "slot", None)
    if (slot is not None and slot[0] is x and slot[1] is rotation
            and slot[2] == group_size and slot[3] == compute):
        ROTATION_CACHE_STATS["hits"] += 1
        return slot[4]
    ROTATION_CACHE_STATS["misses"] += 1
    return None


def _rotation_cache_put(x, rotation, group_size, compute, rotated) -> None:
    _ROTATION_CACHE.slot = (x, rotation, group_size, compute, rotated)


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
                     lora_a=None, lora_b=None, lora_scale: float = 1.0, share_rotation: bool = False):
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
            # Lever 6: reuse the q/k/v rotation of this block's attention input. Identity-keyed,
            # so it is the same tensor or it is not a hit; see the cache section above.
            self.share_rotation = bool(share_rotation)
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
                cached = (_rotation_cache_get(x, self.rotation, self.group_size, compute)
                          if self.share_rotation else None)
                if cached is not None:
                    x = cached
                else:
                    shape = x.shape
                    rotated = x.reshape(*shape[:-1], shape[-1] // self.group_size, self.group_size)
                    rotated = rotated @ self.rotation.to(compute)
                    rotated = rotated.reshape(shape)
                    if self.share_rotation:
                        _rotation_cache_put(x, self.rotation, self.group_size, compute, rotated)
                    x = rotated
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


def device_total_bytes(torch, dev) -> int:
    """Total memory of one card, or 0 if this torch build will not say."""
    try:
        return int(torch.xpu.get_device_properties(dev).total_memory)
    except Exception:  # pragma: no cover - depends on the driver/runtime build
        return 0


def device_free_bytes(torch, dev) -> int:
    """Free memory on one card: the driver's number if it has one, else total - reserved.

    `mem_get_info` is the honest figure -- it counts what *other* processes and the driver hold as
    well -- but it is not in every torch build, so the fallback is this process's own accounting.
    """
    try:
        return int(torch.xpu.mem_get_info(dev)[0])
    except Exception:
        total = device_total_bytes(torch, dev)
        return max(total - int(torch.xpu.memory_reserved(dev)), 0) if total else 0


def log_vram(torch, devices, tag: str) -> dict:
    """One `[vram]` line per card at a phase boundary.  Always on, and cheap.

    Two allocator counters and one driver query per card, no synchronize, no allocation -- the
    2026-09-19 decode OOM happened with no per-phase memory line anywhere in the log, so what was
    resident at `decode.video` had to be reconstructed from arithmetic afterwards.  It does not
    have to be reconstructed again.
    """
    out = {}
    for dev in devices:
        alloc = int(torch.xpu.memory_allocated(dev))
        reserved = int(torch.xpu.memory_reserved(dev))
        total = device_total_bytes(torch, dev)
        free = device_free_bytes(torch, dev)
        out[str(dev)] = {"allocated_bytes": alloc, "reserved_bytes": reserved, "free_bytes": free,
                         "total_bytes": total}
        LOG.info(
            "[vram] %-26s %s  allocated %s  reserved %s  free %s of %s",
            tag, dev, gib(alloc), gib(reserved), gib(free), gib(total),
        )
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

    log_vram(torch, [device], "before encode.load")

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

    log_vram(torch, [device], "after encode.forward")
    # 25.28 GiB of INT8 encoder has to be off this card before the 18.8 GiB denoiser shard lands on
    # it.  `.clone()` above is what makes that possible -- `embeds` owns its own storage and is not
    # a view into the encoder's last hidden state -- and the strip makes the release independent of
    # who else still holds `model` (transformers caches, a traceback frame, an attention backend).
    strip_module_tensors(model)
    del model, out
    _free(torch, [device])
    log_vram(torch, [device], "after encoder release")
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


def _free(torch, devices=None) -> None:
    """Drain the queues, drop Python references, then hand the cached blocks back to the driver.

    The order is deliberate and it is not the order this function used to have (`gc.collect()`,
    `empty_cache()`, `synchronize()`).  A block whose last kernel is still in flight cannot be
    returned to the allocator, so an `empty_cache()` issued before the queues drain reclaims less
    than it appears to; and `synchronize()` / `empty_cache()` with no device argument speak for the
    *current* device only, which on a two-card split is at best half the job.  So: synchronize
    every card, collect, then empty each card's cache with that card current.

    `devices=None` keeps the old single-current-device behaviour for callers that have no list.
    """
    import gc

    devs = list(devices) if devices is not None else [None]
    for dev in devs:
        torch.xpu.synchronize() if dev is None else torch.xpu.synchronize(dev)
    gc.collect()
    for dev in devs:
        if dev is None:
            torch.xpu.empty_cache()
        else:
            with torch.xpu.device(dev):
                torch.xpu.empty_cache()


def strip_module_tensors(model) -> int:
    """Null every parameter and buffer of `model`, in place.  Returns how many were dropped.

    `del model` is only as good as the weakest reference to it: a diffusers component spec, a
    closure in a forward hook, a traceback frame, an interpreter-level cache.  Nulling the
    `_parameters` / `_buffers` dicts drops the *device storage* no matter who still holds the
    module object -- what survives is an empty skeleton, not 18.8 GiB of weights.  Everything this
    loader places is a Parameter or a registered buffer (`set_submodule_tensor`, `ConvRotLinear`,
    `AdaLNTableEmbedder`), so this reaches all of it.
    """
    dropped = 0
    for module in model.modules():
        for store in (module._parameters, module._buffers):
            for key, value in list(store.items()):
                if value is not None:
                    store[key] = None
                    dropped += 1
    return dropped


def release_denoiser(torch, transformer, pipe, devices) -> None:
    """Give both cards the denoiser's memory back, and prove it in the log.

    Called between `sample` and `decode.load_vae`.  On 2026-09-19 the decode OOMed with 31.21 GiB
    live on xpu:0 -- 18.797 GiB of denoiser shard that the plain `del transformer, pipe` before it
    had not returned, plus 10.264 GiB of VAE weights and ~2 GiB of decode transients.  This does
    the release explicitly instead of hoping refcounting gets there:

      1. clear the boundary-hook transfer cache (it still holds the *last* forward's crossed
         tensors: it is reset at the start of a forward, not at the end);
      2. remove the hooks, so their closures stop referencing that cache;
      3. unhook the components from the pipeline object;
      4. null every parameter and buffer on both shards;
      5. synchronize / collect / empty_cache, per card.

    The caller still `del`s its own names afterwards; this makes that `del` cosmetic rather than
    load-bearing.
    """
    if pipe is not None:
        for name in ("transformer", "scheduler", "audio_scheduler"):
            if getattr(pipe, name, None) is not None:
                try:
                    setattr(pipe, name, None)
                except Exception as exc:  # pragma: no cover - diffusers may guard the attribute
                    LOG.debug("could not unset pipeline.%s: %s", name, exc)
    dropped = 0
    if transformer is not None:
        cache = getattr(transformer, "_b70_boundary_cache", None)
        if isinstance(cache, dict):
            cache.clear()
        for handle in getattr(transformer, "_b70_hook_handles", ()) or ():
            try:
                handle.remove()
            except Exception:  # pragma: no cover
                pass
        transformer._b70_hook_handles = []
        transformer._b70_boundary_cache = None
        dropped = strip_module_tensors(transformer)
    # The shared-rotation slot (lever 6) holds a reference to the last rotated activation; drop it
    # here so it cannot pin a card allocation across the release.
    clear_rotation_cache()
    _free(torch, devices)
    LOG.info("denoiser released: %d parameters/buffers dropped on %s",
             dropped, ", ".join(str(d) for d in devices))


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
                    #
                    # Two float32 [out, in] transients exist here at once -- the widened weight and
                    # the delta, 616 MB each for an `mlp.fc1` -- plus the float32 sum.  Each one is
                    # named and deleted rather than left to a rebinding, so the allocator gets the
                    # blocks back at the end of *this* iteration and not whenever CPython happens
                    # to drop the last temporary.  The arithmetic is unchanged: same widen, same
                    # add, same single rounding.
                    w32 = t.to(device=dev, dtype=torch.float32)
                    delta = lora_delta(torch, lfh, sl, dev)
                    summed = w32 + delta
                    del w32, delta
                    t = summed.to(dtype).contiguous()
                    del summed
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
                        share_rotation=bool(getattr(args, "int8_share_rotation", False)),
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
        # The merge loop above churned float32 [out, in] transients through the allocator on both
        # cards.  They are freed, but the blocks they sized are still cached and badly shaped for
        # what sampling allocates next; hand them back once, here, where it costs nothing.
        _free(torch, [primary, secondary])
    log_vram(torch, [primary, secondary], "after load.stream")

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

    The cache and the hook handles are parked on the model (`_b70_boundary_cache`,
    `_b70_hook_handles`) so `release_denoiser()` can clear and remove them: `reset` empties the
    cache at the *start* of a forward, so after the last one it still holds that forward's crossed
    tensors on both cards.
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

    handles = [model.register_forward_pre_hook(reset)]

    def pre_hook(_module, args):
        return tuple(move(a) for a in args)

    def post_hook(_module, _args, output):
        # the gather back to the primary card after the last block, for norm_out and the VAE
        return cross_card(torch, output, primary) if isinstance(output, torch.Tensor) else output

    blocks = model.transformer_blocks
    for block in list(blocks)[split_index:]:
        handles.append(block.register_forward_pre_hook(pre_hook))
    handles.append(blocks[len(blocks) - 1].register_forward_hook(post_hook))
    model._b70_boundary_cache = cache
    model._b70_hook_handles = handles


# ---------------------------------------------------------------------------------------------
# Phases 3-4 -- sampling and decoding through the diffusers modular blocks
# ---------------------------------------------------------------------------------------------


def build_pipeline(args, transformer, timings: dict):
    """Assemble the core denoise chain over locally loaded components.

    The full `MiniMaxH3Blocks` chain also owns the text encoder, the VAE *encoder* and the two
    decode blocks.  None of them belongs here: the prompt is already encoded and freed, `t2va` has
    no visual conditioning, and the decode has to happen *after* the denoiser is freed, or one card
    holds 18.8 GiB of denoiser shard and 10.3 GiB of float32 VAE at once -- which is exactly the
    2026-09-19 OOM, and why the release between the two phases is now explicit and logged.  So the
    pipeline stops at the latents and this script decodes by hand, mirroring `decoders.py` step for
    step.

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


def pick_decode_card(torch, args, devices):
    """Which card decodes: `--vae-card` if given, else whichever has the most free memory.

    Called *after* the denoiser has been released, so the free-memory reading is the one that
    matters.  With a balanced split the two cards come back within tens of MB of each other and
    either is fine; the point of the rule is that an unbalanced release (one shard returned, the
    other not) sends the VAE to the card that can hold it instead of the card it started on.
    """
    if args.vae_card is not None:
        return torch.device(f"xpu:{args.vae_card}")
    free = {dev: device_free_bytes(torch, dev) for dev in devices}
    best = max(free, key=lambda d: free[d])
    LOG.info("decode card: %s (free %s)", best, ", ".join(f"{d} {gib(b)}" for d, b in free.items()))
    return best


def _apply_vae_tiling(args, vae) -> str:
    """Honour `--vae-tiling`, and say in the log what the VAE is actually doing.

    Unlike most autoencoders in diffusers, `AutoencoderKLMiniMaxH3` ships with **tiling on**
    (`__init__`: `self.use_tiling = True`, and the class docstring: "MiniMax-H3 was released with
    tiling enabled ... the released frames are the blended-tile ones, so disabling tiling changes
    the output").  So `auto` -- the default -- keeps the checkpoint's own setting, which is on, and
    `off` is the A/B control, not the safe choice.

    Tiling does not cost determinism: the tile layout is a pure function of the canvas
    (`_split_tiles`), the blend weights are a pure function of the overlap, and the tiles are
    decoded in a fixed order, so the repeat-hash gate holds either way.  What it *does* change is
    the numbers, so an A/B (pruned vs int8, canvas vs canvas) must use the same setting on both
    sides.  The setting is written into the receipt for exactly that reason.

    `enable_slicing` exists too and is left alone: it splits the *batch*, and every decode here is
    batch 1, so it would be inert.
    """
    want = args.vae_tiling
    if want == "on":
        vae.enable_tiling()
    elif want == "off":
        vae.disable_tiling()
    state = "on" if getattr(vae, "use_tiling", False) else "off"
    LOG.info(
        "video vae tiling: %s (--vae-tiling %s; tiles %dx%d, min overlap %dx%d) -- deterministic, "
        "but it changes the pixels, so both sides of an A/B must match",
        state, want, getattr(vae, "tile_sample_min_height", 0), getattr(vae, "tile_sample_min_width", 0),
        getattr(vae, "tile_sample_min_overlap_height", 0), getattr(vae, "tile_sample_min_overlap_width", 0),
    )
    return state


def load_video_vae(args, timings: dict, device):
    """Load the video VAE alone.  Called only after the denoiser has been released.

    `torch_dtype=torch.float16` does **not** halve this one.  `AutoencoderKLMiniMaxH3` declares
    `_keep_in_fp32_modules = ["encoder", "decoder", "quant_conv", "post_quant_conv"]` -- that is
    every weight-bearing module it has -- so the weights land float32 whatever dtype is asked for:
    9.700 GiB, not the 4.85 GiB the dtype suggests.  The argument is kept because it is still what
    picks the compute path (`decode` casts the latents to `get_parameter_dtype(self.decoder)`), and
    because dropping it would change the arithmetic rather than the footprint.

    The encoder half of those weights (0.672 GiB) is dead on a `t2va` run -- nothing encodes -- but
    it is loaded and left in place: dropping it would make the model no longer the checkpoint, and
    0.672 GiB is not what the decode was short of.  `--plan-memory` reports it separately.
    """
    import torch
    from diffusers import AutoencoderKLMiniMaxH3

    with phase("decode.load_vae", timings):
        vae = AutoencoderKLMiniMaxH3.from_pretrained(str(VAE_DIR), torch_dtype=torch.float16).to(device).eval()
    tiling = _apply_vae_tiling(args, vae)
    log_vram(torch, [device], "after decode.load_vae")
    return vae, tiling


def load_audio_vae(args, timings: dict, device):
    """Load the audio VAE, after the video VAE has been freed.  0.564 GiB, float32 as shipped."""
    import torch
    from diffusers import AutoencoderKLMiniMaxH3Audio

    with phase("decode.load_audio_vae", timings):
        audio_vae = AutoencoderKLMiniMaxH3Audio.from_pretrained(str(AUDIO_VAE_DIR), torch_dtype=torch.float32)
        audio_vae = audio_vae.to(device).eval()
    log_vram(torch, [device], "after decode.load_audio_vae")
    return audio_vae


# ---------------------------------------------------------------------------------------------
# Phase 4b -- the two-card tiled video decode (lever 2 of notes/2026-09-19-speed-plan.md)
#
# `decode.video` is 80.0 s of the 244 s clip and it is exactly `tiles x per-tile cost`: 7 temporal
# chunks x 15 spatial tiles = 105 independent decoder calls at 960x544, each reading only its own
# latent slice and the weights.  Nothing flows from tile to tile -- `_decode_clip` decodes every
# tile before any blending -- so the tiles can be split across two cards and the result is the same
# bytes, provided three things hold:
#
#   1. copy B's weights are copy A's bytes (they are: `replicate_video_vae` copies tensor by tensor
#      through `cross_card()`, and a copy does not change values);
#   2. each card sees the SAME tile input, down to the strides -- so the whole latent is staged to
#      card B once and sliced there with the identical expressions, rather than slicing on A and
#      shipping a tile (a shipped slice arrives contiguous, and a conv on a contiguous input may
#      pick a different kernel than the same conv on a strided view);
#   3. the blend runs in the ORIGINAL order with the ORIGINAL arithmetic on the ORIGINAL card --
#      which it does, because the gather is positional and the stitch is the VAE's own
#      `_stitch_tiles` on card A.
#
# What this does NOT do is edit the diffusers checkout.  The chunk loop of `_decode` and the tile
# loop of `_decode_clip` are reimplemented here, and every piece of arithmetic they perform is the
# VAE's own method, called on the VAE object:
#
#     vae._split_tiles(...)        the tile grid (indices, lengths, overlaps)
#     vae.post_quant_conv(tile)    per tile, as `_decode_clip` calls it
#     vae.decoder(...)             per tile, as `_decode_clip` calls it
#     vae._stitch_tiles(...)       the spatial blend, per chunk, on the blending card
#     vae._blend(...)              the temporal cross-fade between chunks
#
# Everything else here is slicing and bookkeeping copied from `_decode` / `_decode_clip`.  Because
# that copy is only as good as the source it was copied from, `check_vae_source()` refuses to run
# the two-card path unless the diffusers file still hashes to what this was written against.
# ---------------------------------------------------------------------------------------------

# `/mnt/fast-ai/build/diffusers-src` is the editable checkout this venv imports diffusers from
# (site-packages/__editable__.diffusers-0.41.0.dev0.pth -> .../src).  The path is only a fallback:
# at run time the file is located through the class itself.
DIFFUSERS_VAE_SOURCE = pathlib.Path(
    "/mnt/fast-ai/build/diffusers-src/src/diffusers/models/autoencoders/autoencoder_kl_minimax_h3.py"
)
# sha256 of that file as of 2026-09-19, the version `decode_video_two_card` was written against and
# the version `test_vae_tile_loop.py` checks the reimplementation against.  If upstream changes the
# tile geometry, the chunk arithmetic or the blend, this hash changes and the two-card path stops
# rather than silently decoding something else.
DIFFUSERS_VAE_SOURCE_SHA256 = "4c3c9745ee27d16ff343c4998244bad41cd8f4213f0029cf7ce11ebb6d72ca1b"


def diffusers_vae_source_path(cls=None) -> pathlib.Path:
    """Where `AutoencoderKLMiniMaxH3` is defined on this host."""
    if cls is not None:
        import inspect

        src = inspect.getsourcefile(cls)
        if src:
            return pathlib.Path(src)
    return DIFFUSERS_VAE_SOURCE


def check_vae_source(cls=None, *, require: bool = True) -> dict:
    """Hash the diffusers VAE source and (by default) refuse to continue if it has moved.

    The two-card decode reimplements `_decode`'s chunk loop and `_decode_clip`'s tile loop.  That
    is only safe while the original still looks the way it did when the copy was made, so this is a
    start-up assertion and a receipt field, not a comment.
    """
    path = diffusers_vae_source_path(cls)
    digest = file_digest(path) if path.exists() else None
    row = {"path": str(path), "sha256": digest, "expected": DIFFUSERS_VAE_SOURCE_SHA256,
           "matches": digest == DIFFUSERS_VAE_SOURCE_SHA256}
    if require and not row["matches"]:
        raise SystemExit(
            f"the diffusers VAE source at {path} hashes {digest}, not the "
            f"{DIFFUSERS_VAE_SOURCE_SHA256} this two-card decode was written against.\n"
            "  The tile loop here is a reimplementation of `_decode` / `_decode_clip`; if upstream "
            "changed them it must be re-read before this path runs again.\n"
            "  Re-read the file, re-check the loop, then update DIFFUSERS_VAE_SOURCE_SHA256 -- or "
            "run with --vae-decode single, which calls `vae.decode` and is unaffected."
        )
    return row


def _device_ctx(torch, device):
    """`torch.xpu.device(dev)` on a card, a no-op anywhere else (so the CPU tests run this code)."""
    device = torch.device(device)
    if device.type == "xpu":
        return torch.xpu.device(device)
    return contextlib.nullcontext()


def vae_autocast_context(torch, mode: str, device):
    """Upstream's decode autocast (`modular_pipelines/minimax_h3/decoders.py` L187), switchable.

    Upstream writes `torch.autocast(device_type=device.type, dtype=torch.float16,
    enabled=device.type == "cuda")` -- the recipe the VAE docstring names ("float16 autocast over
    float32 weights", autoencoder_kl_minimax_h3.py L529-530) but enabled only on CUDA, so an XPU
    decode runs the whole float32 ViT.  `--vae-autocast fp16` is that same call with
    `enabled=True`.  It is NOT bit-identical and must never be the default: it is experiment E2,
    gated on a repeat and measured against the fp32 control with `compare-h3-runs.py`.
    """
    if mode == "off":
        return contextlib.nullcontext()
    dtype = {"fp16": torch.float16, "bf16": torch.bfloat16}[mode]
    return torch.autocast(device_type=torch.device(device).type, dtype=dtype, enabled=True)


def replicate_video_vae(torch, vae, target, timings: dict, phase_name: str = "decode.replicate_vae"):
    """Build a second video VAE on `target` from `vae`'s own tensors, one tensor at a time.

    NOT a second `from_pretrained`: that maps the 9.7 GB checkpoint again on a 15 GiB host whose
    VmHWM is already 12.467 GiB.  This walks copy A's parameters and buffers (including the
    non-persistent `rope.inv_freq`) and stages each one through `cross_card()`, so the host holds
    one tensor at a time and copy B's weights are copy A's bytes by construction.

    The skeleton is built on the meta device from copy A's own config, so no second allocation of
    the weights ever exists on the host.
    """
    from diffusers import AutoencoderKLMiniMaxH3

    target = torch.device(target)
    tensors = list(vae.named_parameters()) + list(vae.named_buffers())
    need = sum(t.numel() * t.element_size() for _, t in tensors if t is not None)
    free = device_free_bytes(torch, target)
    if free and free < int(need * 1.05):
        raise SystemExit(
            f"two-card decode needs {gib(need)} of weights on {target}, which reports {gib(free)} "
            "free. Run with --vae-decode single."
        )
    with phase(phase_name, timings):
        with torch.device("meta"):
            copy = AutoencoderKLMiniMaxH3.from_config(vae.config)
        copy.eval()
        moved = 0
        for name, tensor in tensors:
            if tensor is None:
                continue
            set_submodule_tensor(copy, name, cross_card(torch, tensor.detach(), target))
            moved += 1
        for attr in ("use_tiling", "use_slicing", "tile_sample_min_height", "tile_sample_min_width",
                     "tile_sample_min_overlap_height", "tile_sample_min_overlap_width"):
            setattr(copy, attr, getattr(vae, attr))
    left = [n for n, t in list(copy.named_parameters()) + list(copy.named_buffers())
            if t is not None and t.is_meta]
    if left:
        raise SystemExit(f"replicated VAE still has {len(left)} meta tensors, e.g. {left[:4]}")
    LOG.info("video vae replicated onto %s: %d tensors, %s, tensor by tensor through cross_card()",
             target, moved, gib(need))
    log_vram(torch, [target], "after decode.replicate_vae")
    return copy


def vae_decode_plan(vae, z) -> dict:
    """The chunk and tile plan `_decode` / `_decode_clip` would use for this latent.

    Pure arithmetic and one call to the VAE's own `_split_tiles`; no tensor is touched.
    """
    ratio = vae.spatial_compression_ratio
    tokens_chunk_size = vae.tokens_chunk_size
    token_drop = int(vae.config.token_drop)
    num_tokens = z.shape[2] + token_drop
    pad_tokens = (-num_tokens) % tokens_chunk_size
    num_chunks = (num_tokens + pad_tokens) // tokens_chunk_size - int(token_drop > 0)
    height = z.shape[-2] * ratio
    width = z.shape[-1] * ratio
    y_indices, y_lengths, y_overlaps = vae._split_tiles(
        height, vae.tile_sample_min_height, vae.tile_sample_min_overlap_height
    )
    x_indices, x_lengths, x_overlaps = vae._split_tiles(
        width, vae.tile_sample_min_width, vae.tile_sample_min_overlap_width
    )
    return {
        "pad_tokens": pad_tokens,
        "num_chunks": num_chunks,
        "tokens_chunk_size": tokens_chunk_size,
        "token_overlap": vae.token_overlap,
        "frame_overlap": vae.frame_overlap,
        "frame_pre_padding": vae.frame_pre_padding,
        "y_indices": list(y_indices), "y_lengths": list(y_lengths), "y_overlaps": list(y_overlaps),
        "x_indices": list(x_indices), "x_lengths": list(x_lengths), "x_overlaps": list(x_overlaps),
        "tiles_per_chunk": len(y_indices) * len(x_indices),
        "tiles_total": num_chunks * len(y_indices) * len(x_indices),
    }


def decode_video_two_card(torch, vaes, z, *, autocast="off", tile_hook=None):
    """`vae.decode(z, return_dict=False)[0]`, with the per-tile decoder calls split over two cards.

    `vaes` is `[(device_a, vae_a), (device_b, vae_b), ...]`; `device_a` is the BLENDING card and
    `z` must already be on it.  Returns `(decoded, plan)`.

    Order of operations, mirroring `_decode` and `_decode_clip` (see the section header for the
    list of VAE methods called):

      1. the latents are cast exactly as `decode()` casts them, the temporal padding of `_decode`
         is applied, and the whole padded latent is staged onto every other card once (~7 MB), so
         every card slices the identical view with the identical strides;
      2. the (chunk, row, column) tiles are enumerated in the ORIGINAL row-major order, flattened
         across chunks, and job `k` goes to card `k % n` -- 53/52 of 105 at 960x544, against 8/7 of
         15 if the split stayed inside a chunk;
      3. one thread per card runs its own jobs inside `torch.xpu.device(dev)` and `torch.no_grad()`
         (grad mode is thread-local, and a decoder that keeps activations is the 2026-09-19 OOM),
         and brings each finished tile back to the blending card with `cross_card()` -- host
         staged, no P2P, per the 2026-09-18 copy-engine fault;
      4. the tiles are gathered POSITIONALLY, never by completion order, and each chunk is stitched
         by the VAE's own `_stitch_tiles` on the blending card;
      5. the temporal cross-fade, the concatenation and the pad-frame trim are `_decode`'s, in its
         order, on the blending card.

    Memory: the flattened split holds every decoded tile until its chunk is stitched -- 105 x 22 MB
    = 2.3 GiB at 960x544 on the blending card, on top of 9.7 GiB of weights.  Tiles are dropped as
    soon as their chunk is stitched.
    """
    if not vaes:
        raise ValueError("decode_video_two_card needs at least one (device, vae) pair")
    blend_device = torch.device(vaes[0][0])
    vae_a = vaes[0][1]
    if not getattr(vae_a, "use_tiling", False):
        raise SystemExit(
            "--vae-decode two-card needs the VAE's spatial tiling (it is what makes the decode "
            "splittable). --vae-tiling off changes the pixels anyway; use --vae-decode single."
        )

    try:
        from diffusers.models.modeling_utils import get_parameter_dtype

        want_dtype = get_parameter_dtype(vae_a.decoder)
    except Exception:  # pragma: no cover - depends on the diffusers version
        want_dtype = next(vae_a.decoder.parameters()).dtype
    z = z.to(want_dtype)  # `decode()` L887

    ratio = vae_a.spatial_compression_ratio
    temporal_ratio = vae_a.temporal_compression_ratio
    tokens_chunk_size = vae_a.tokens_chunk_size
    token_drop = int(vae_a.config.token_drop)
    chunk_num_frames = tokens_chunk_size * temporal_ratio
    plan = vae_decode_plan(vae_a, z)
    pad_tokens, num_chunks = plan["pad_tokens"], plan["num_chunks"]
    if pad_tokens > 0:  # `_decode` L809-810
        z = torch.cat([z, z[:, :, -1:].repeat(1, 1, pad_tokens, 1, 1)], dim=2)

    # One staged copy of the whole latent per card: every card then slices the same expressions and
    # hands its decoder a view with the same shape AND the same strides as the single-card path.
    z_by_card = [z] + [cross_card(torch, z, dev) for dev, _ in vaes[1:]]

    y_indices, y_lengths = plan["y_indices"], plan["y_lengths"]
    x_indices, x_lengths = plan["x_indices"], plan["x_lengths"]
    jobs = [(c, i, j) for c in range(num_chunks) for i in range(len(y_indices)) for j in range(len(x_indices))]
    results: list = [None] * len(jobs)
    errors: list = []
    per_card = [0] * len(vaes)

    def slice_tile(zc, i, j):
        i_pos, i_len = y_indices[i], y_lengths[i]
        j_pos, j_len = x_indices[j], x_lengths[j]
        return zc[..., i_pos // ratio : i_pos // ratio + i_len // ratio,   # `_decode_clip` L755-759
                  j_pos // ratio : j_pos // ratio + j_len // ratio]

    def worker(w: int) -> None:
        dev, vae = vaes[w]
        zw = z_by_card[w]
        try:
            with _device_ctx(torch, dev), torch.no_grad(), vae_autocast_context(torch, autocast, dev):
                for k in range(w, len(jobs), len(vaes)):
                    c, i, j = jobs[k]
                    start = c * tokens_chunk_size  # `_decode` L815-816
                    zc = zw[:, :, start : start + tokens_chunk_size + vae_a.token_overlap]
                    tile = slice_tile(zc, i, j)
                    out = vae.decoder(vae.post_quant_conv(tile))  # `_decode_clip` L760
                    if tile_hook is not None:  # the CPU test's window onto the dispatch
                        tile_hook(w, k, c, i, j, tile, out)
                    results[k] = cross_card(torch, out, blend_device)
                    per_card[w] += 1
                    del out, tile, zc
        except BaseException as exc:  # noqa: BLE001 - re-raised on the calling thread
            errors.append((w, exc))

    threads = [threading.Thread(target=worker, args=(w,), name=f"h3-vae-card{w}", daemon=True)
               for w in range(len(vaes))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        w, exc = errors[0]
        raise RuntimeError(f"the tile worker on {vaes[w][0]} failed: {exc}") from exc
    if any(r is None for r in results):
        raise RuntimeError("a tile came back empty; refusing to blend a partial decode")

    tiles_per_chunk = len(y_indices) * len(x_indices)
    decoded_chunks = []
    overlap = None
    # Upstream wraps the WHOLE of `decode` in the autocast, blending included, so the blend runs
    # inside it here too.  It makes no difference in practice -- `_stitch_tiles` and `_blend` are
    # multiplies, adds and concatenations, none of which autocast touches -- but "no difference in
    # practice" is not a reason to run a different program.
    with vae_autocast_context(torch, autocast, blend_device):
        for c in range(num_chunks):  # `_decode` L812-828, with `_decode_clip`'s stitch inlined
            base = c * tiles_per_chunk
            rows = [[results[base + i * len(x_indices) + j] for j in range(len(x_indices))]
                    for i in range(len(y_indices))]
            clip = vae_a._stitch_tiles(rows, plan["y_overlaps"], plan["x_overlaps"])  # `_decode_clip` L763
            for k in range(base, base + tiles_per_chunk):
                results[k] = None  # the tiles are the 2.3 GiB; drop them as soon as they are blended
            del rows
            for j in range(int(token_drop > 0) + 1):
                frame_start = j * chunk_num_frames
                chunk = clip[:, :, frame_start : frame_start + chunk_num_frames]
                chunk = chunk[:, :, vae_a.frame_pre_padding :]
                if j == 0:
                    if overlap is not None:
                        chunk = vae_a._blend(overlap, chunk, vae_a.frame_overlap, dim=-3)
                    decoded_chunks.append(chunk)
                else:
                    overlap = chunk
            del clip
        if overlap is not None:
            decoded_chunks.append(overlap)

        dec = torch.cat(decoded_chunks, dim=2)
        if pad_tokens > 0:  # `_decode` L832-841
            intra_tail = vae_a.config.clip_length % temporal_ratio
            num_tokens_before_pad = z.shape[2] - pad_tokens
            pad_frames = sum(
                intra_tail if intra_tail and (num_tokens_before_pad + k) % tokens_chunk_size == 0 else temporal_ratio
                for k in range(pad_tokens)
            )
            dec = dec[:, :, :-pad_frames]

    plan = dict(plan)
    plan.update({
        "mode": "two-card",
        "cards": [str(torch.device(dev)) for dev, _ in vaes],
        "blend_card": str(blend_device),
        "tiles_per_card": per_card,
        "dispatch": "job k -> card k % n over the flattened (chunk, row, column) order",
        "autocast": autocast,
    })
    LOG.info("two-card decode: %d tiles over %s (%s), blended on %s",
             len(jobs), ", ".join(plan["cards"]), "/".join(str(n) for n in per_card), blend_device)
    return dec, plan


# ---------------------------------------------------------------------------------------------
# Experiment E1 -- the cross-card tile identity probe
# ---------------------------------------------------------------------------------------------


def probe_tile_identity(args, timings: dict) -> int:
    """Decode the first N tiles on BOTH cards, twice, and hash every one.

    This is the gate of `notes/2026-09-19-speed-plan.md` E1: it decides whether the two-card decode
    can be called bit-identical at all, before any clip is rendered through it.  It loads no
    denoiser and samples nothing -- the latents come from a previous run's `tensors.safetensors`
    (`--latents-from`), so it costs a VAE load per card and N x 2 x 2 tile decodes.

    Four gates, all reported in `probe.json`:
      1. identity   -- tile hash equal ACROSS cards, every tile
      2. repeat     -- each card's own tile hash equal across two consecutive passes
      3. memory     -- `[vram]` per card with both replicas up
      4. host       -- VmHWM, which is what proves the cross-card build beats a second
                       `from_pretrained`
    """
    import torch
    from safetensors.torch import load_file

    if args.latents_from is None:
        raise SystemExit("--probe-tile-identity needs --latents-from PATH (a run's tensors.safetensors)")
    source = check_vae_source()
    devices = [torch.device(f"xpu:{i}") for i in args.cards]
    torch.xpu.init()
    torch.set_grad_enabled(False)
    for dev in devices:
        torch.xpu.reset_peak_memory_stats(dev)

    with phase("probe.load_latents", timings):
        payload = load_file(str(args.latents_from))
        latents = payload["latents"].detach().to("cpu", copy=True)
    del payload

    vae_a, tiling = load_video_vae(args, timings, devices[0])
    source = check_vae_source(type(vae_a))
    vae_b = replicate_video_vae(torch, vae_a, devices[1], timings)
    log_vram(torch, devices, "probe: both replicas up")

    latents_mean = torch.tensor(vae_a.config.latents_mean, device=devices[0]).view(1, -1, 1, 1, 1)
    latents_std = torch.tensor(vae_a.config.latents_std, device=devices[0]).view(1, -1, 1, 1, 1)
    z = (latents.to(devices[0]) * latents_std + latents_mean).to(vae_a.dtype)
    try:
        from diffusers.models.modeling_utils import get_parameter_dtype

        z = z.to(get_parameter_dtype(vae_a.decoder))
    except Exception:  # pragma: no cover
        z = z.to(next(vae_a.decoder.parameters()).dtype)

    plan = vae_decode_plan(vae_a, z)
    n_tiles = min(int(args.probe_tile_identity), plan["tiles_per_chunk"])
    ratio = vae_a.spatial_compression_ratio
    z_by_card = [z, cross_card(torch, z, devices[1])]
    # Chunk 0 only: `_decode`'s first clip, sliced exactly as `_decode` slices it.
    chunk0 = [zc[:, :, 0 : plan["tokens_chunk_size"] + plan["token_overlap"]] for zc in z_by_card]

    rows: list[dict] = []
    for pass_index in range(2):
        with phase(f"probe.pass{pass_index}", timings):
            for k in range(n_tiles):
                i, j = divmod(k, len(plan["x_indices"]))
                digests = []
                for card, (dev, vae) in enumerate(((devices[0], vae_a), (devices[1], vae_b))):
                    i_pos, i_len = plan["y_indices"][i], plan["y_lengths"][i]
                    j_pos, j_len = plan["x_indices"][j], plan["x_lengths"][j]
                    tile = chunk0[card][..., i_pos // ratio : i_pos // ratio + i_len // ratio,
                                        j_pos // ratio : j_pos // ratio + j_len // ratio]
                    with _device_ctx(torch, dev), torch.no_grad(), \
                            vae_autocast_context(torch, args.vae_autocast, dev):
                        out = vae.decoder(vae.post_quant_conv(tile))
                    digests.append(sha256_tensor(out.float()))
                    del out, tile
                rows.append({"pass": pass_index, "tile": k, "row": i, "column": j,
                             "sha256": {str(devices[0]): digests[0], str(devices[1]): digests[1]},
                             "cards_agree": digests[0] == digests[1]})
    log_vram(torch, devices, "probe: after tiles")

    by_tile: dict[int, dict[int, dict]] = {}
    for row in rows:
        by_tile.setdefault(row["tile"], {})[row["pass"]] = row
    repeatable = bool(by_tile) and all(
        len(passes) == 2
        and all(passes[0]["sha256"][str(dev)] == passes[1]["sha256"][str(dev)] for dev in devices)
        for passes in by_tile.values()
    )
    identical = all(row["cards_agree"] for row in rows)

    report = {
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": platform.node(),
        "argv": sys.argv,
        "latents_from": str(args.latents_from),
        "latents_shape": list(latents.shape),
        "latents_sha256": sha256_tensor(latents),
        "cards": [str(d) for d in devices],
        "tiles_probed": n_tiles,
        "video_vae_tiling": tiling,
        "vae_autocast": args.vae_autocast,
        "plan": plan,
        "diffusers_vae_source": source,
        "tiles": rows,
        "gates": {
            "identity_across_cards": identical,
            "repeatable_per_card": repeatable,
            "peak_memory": card_memory(torch, devices),
            "vram": log_vram(torch, devices, "probe: final"),
            "host_peak_rss_bytes": host_rss_bytes(),
        },
        "timings_seconds": timings,
        "versions": {"python": platform.python_version(), "torch": torch.__version__,
                     "diffusers": __import__("diffusers").__version__},
        "cross_card_transfer": XFER,
    }
    run_name = args.run_name or time.strftime("probe-%Y%m%dT%H%M%SZ", time.gmtime())
    out_dir = args.out_dir / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "probe.json").write_text(json.dumps(report, indent=2) + "\n")

    for row in rows:
        LOG.info("[probe] pass %d tile %d (row %d col %d): %s  %s / %s", row["pass"], row["tile"],
                 row["row"], row["column"], "SAME" if row["cards_agree"] else "DIFFERS",
                 row["sha256"][str(devices[0])][:16], row["sha256"][str(devices[1])][:16])
    LOG.info("[probe] identity across cards: %s", "PASS" if identical else "FAIL")
    LOG.info("[probe] repeatable per card:   %s", "PASS" if repeatable else "FAIL")
    LOG.info("[probe] host peak RSS %s", gib(report["gates"]["host_peak_rss_bytes"]))
    LOG.info("wrote %s", out_dir / "probe.json")

    strip_module_tensors(vae_b)
    strip_module_tensors(vae_a)
    del vae_a, vae_b
    _free(torch, devices)
    return 0 if (identical and repeatable) else 1


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
    p.add_argument(
        "--vae-card",
        type=int,
        default=None,
        help="card the two VAEs decode on. Default: whichever of --cards has the most free memory "
        "once the denoiser has been released (the release is explicit and logged; see the [vram] "
        "lines). The two VAEs are loaded one at a time, video then audio.",
    )
    p.add_argument(
        "--vae-tiling",
        choices=["auto", "on", "off"],
        default="auto",
        help="spatial tiling in the video VAE. `auto` (the default) keeps the checkpoint's own "
        "setting, which is ON -- AutoencoderKLMiniMaxH3 ships with tiling enabled and the released "
        "frames are the blended-tile ones, so `off` CHANGES THE PIXELS and is an A/B control, not a "
        "safe fallback. Tiling is deterministic either way (fixed tile layout, fixed blend, fixed "
        "order), so the repeat gate holds; but both sides of a comparison must use the same "
        "setting, and the receipt records which was used.",
    )
    p.add_argument(
        "--vae-decode",
        choices=["single", "two-card"],
        default=(os.environ.get("B70_H3_VAE_DECODE") or "single").strip().lower(),
        help="how the video VAE decodes (env B70_H3_VAE_DECODE). `single` (the default) calls "
        "`vae.decode` on one card and is the bytewise-gated path, unchanged. `two-card` replicates "
        "the VAE onto the second card through cross_card() and splits the 105 tile decodes between "
        "them, blending in the original order on the original card -- intended to be BIT-IDENTICAL "
        "(experiment E1 in notes/2026-09-19-speed-plan.md is its gate; the finished decode is gated "
        "on reproducing the single-card video_tensor_sha256 exactly).",
    )
    p.add_argument(
        "--vae-autocast",
        choices=["off", "fp16", "bf16"],
        default="off",
        help="wrap the video decode in torch.autocast over the float32 VAE weights, exactly as "
        "upstream's decoders.py does on CUDA (and only on CUDA). `off` is the default and the only "
        "bit-identical setting. This is experiment E2: it is NOT exact, it must pass a repeat gate "
        "of its own, and the difference against the fp32 control is a compare-h3-runs.py number, "
        "not a claim.",
    )
    p.add_argument(
        "--decode-only",
        action="store_true",
        help="skip phases 1-3 and decode the latents saved by a previous run (--latents-from). "
        "About 1.5 min instead of 4, which is what makes the decode experiments cheap. The receipt "
        "records the source run's hashes, so the four hashes of a two-card or autocast decode can "
        "be checked against the original single-card ones.",
    )
    p.add_argument(
        "--latents-from",
        type=pathlib.Path,
        default=None,
        help="a previous run's tensors.safetensors (keys `latents` and `audio_latents`), for "
        "--decode-only and --probe-tile-identity.",
    )
    p.add_argument(
        "--probe-tile-identity",
        type=int,
        default=None,
        metavar="N",
        help="experiment E1, and nothing else: decode the first N tiles of chunk 0 on BOTH cards, "
        "twice, hash every decoded tile and write probe.json. Needs --latents-from. Loads no "
        "denoiser and renders no clip; exits nonzero if the tiles differ across cards or across "
        "the two passes.",
    )
    p.add_argument(
        "--int8-share-rotation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="int8 denoiser only: compute the ConvRot activation rotation ONCE per (activation, "
        "rotation, group size) instead of once per Linear, so a block's to_q/to_k/to_v share the "
        "one `x @ R`. Bit-identical by construction -- the cache is keyed on object identity, so a "
        "hit hands back literally the same tensor (test_convrot_linear.py section 6 proves it "
        "bitwise). On by default for that reason; --no-int8-share-rotation is the A/B control.",
    )
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
    p.add_argument(
        "--plan-memory",
        action="store_true",
        help="dry-run extra: the per-phase, per-card VRAM budget for the requested canvas -- "
        "resident weights from the split plan and the VAE headers, plus a stated upper bound for "
        "the decode activations. A dry run cannot measure VRAM; this is arithmetic, and the "
        "formula and its uncertainty are printed with it.",
    )
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

    if args.plan_memory:
        print_plan_memory(args, config, plan, header)

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


def vae_weight_bytes(directory: pathlib.Path) -> dict[str, int]:
    """Resident bytes per top-level module of a VAE, from its safetensors headers.

    Headers only, sharded or not.  The numbers are the *stored* widths, which for both MiniMax-H3
    VAEs is float32 -- and float32 is also what lands on the card: `AutoencoderKLMiniMaxH3` pins
    `encoder`, `decoder`, `quant_conv` and `post_quant_conv` in `_keep_in_fp32_modules`, i.e. every
    module it has, so `torch_dtype=torch.float16` does not narrow a single weight.  That is the
    difference between a 4.85 GiB guess and the 9.70 GiB the card actually gives up.
    """
    shards = sorted(directory.glob("*.safetensors"))
    out: dict[str, int] = {}
    for shard in shards:
        for key, entry in read_header(shard).items():
            out[key.split(".")[0]] = out.get(key.split(".")[0], 0) + tensor_bytes(entry)
    return out


def _tile_spans(length: int, tile: int, min_overlap: int, ratio: int) -> list[int]:
    """`AutoencoderKLMiniMaxH3._split_tiles`, in pixels, reimplemented for the dry run.

    Same arithmetic as the model (autoencoder_kl_minimax_h3.py `_split_tiles`): the smallest tile
    count whose union covers `length` with every overlap at least `min_overlap`, slack distributed
    in whole `ratio` steps.  Only the tile *sizes* matter here, and every tile is `tile` wide, so
    this returns one entry per tile.
    """
    if tile >= length:
        return [length]
    num_tiles = math.ceil(length / tile)
    while tile * num_tiles - min_overlap * (num_tiles - 1) - length < 0:
        num_tiles += 1
    return [tile] * num_tiles


def plan_memory(args, config: dict, plan: SplitPlan, header: dict) -> dict:
    """Per-phase, per-card VRAM arithmetic for the requested canvas.  No torch, no device.

    THE FORMULA, and what each term is worth trusting.

    Resident weights are exact.  They come from the safetensors headers and the dtype policy the
    loader actually applies: `plan_split` for the denoiser shards, `vae_weight_bytes` for the two
    VAEs (float32, pinned -- see that function), the text-encoder header for phase 1.  These are
    the numbers the 2026-09-19 log confirms: the split plan said 18.797 GiB on xpu:0 and the run
    printed 18.797 GiB.

    Activations are an UPPER BOUND, not a measurement, and the dominant term is one line of the
    diffusers decoder:

        attention = 2 * heads * S^2 * 4 bytes            S = tokens in one decode tile
        streams   = 10 * S * dim * 4 bytes               q,k,v, attn out, residual, norm, ffn
        output    = 3 * frames * H * W * 4 bytes         the assembled clip, float32
        latents   = 24 * latent_frames * H/16 * W/16 * 4

    The `2 *` in the attention term is the scores matrix plus the softmax result: the 2026-09-19
    traceback died inside `_native_attention` -> `torch.nn.functional.scaled_dot_product_attention`
    asking for 396.00 MiB, which is exactly `heads * S^2 * 4` at the smoke canvas, so the math
    backend really does materialize it.  UNCERTAINTY: if the XPU backend ever dispatches a
    flash/memory-efficient kernel instead, that whole term collapses to a few MB and this bound is
    far too generous.  The `10 *` streams coefficient is a count of the live `[S, dim]` tensors in
    `MiniMaxH3VideoTransformerBlock.forward`, read off the source, not measured; call it +-50 %.
    Fragmentation, the caching allocator's held blocks and `expandable_segments:True` add a few
    per cent on top of all of it, and `reserved` always runs ahead of `allocated`.

    The denoise activations are the weakest line here: the packed sequence is known exactly but
    what diffusers keeps live across a block is not read off the source the way the VAE's is.  The
    bound below uses the same shape of formula at the denoiser's own widths, and the run's `[vram]`
    lines will replace it with a measurement on the next pass.
    """
    vae_cfg = json.loads((VAE_DIR / "config.json").read_text())
    audio_cfg = json.loads((AUDIO_VAE_DIR / "config.json").read_text())

    spatial = math.prod(vae_cfg["spatial_downsample_factors"])
    temporal = math.prod(vae_cfg["temporal_downsample_factors"])
    clip_len, token_drop = vae_cfg["clip_length"], vae_cfg["token_drop"]
    frames = args.frames
    while frames % clip_len != 5:
        frames += 1
    latent_frames = (frames - 5) // clip_len * 5 + 2
    height, width = args.height, args.width
    if height is None or width is None:
        height, width = 768, 1344
    lat_h, lat_w = height // spatial, width // spatial

    # --- phase 4 activations, from the decoder's own geometry ---------------------------------
    dim = vae_cfg["decoder_num_attention_heads"] * vae_cfg["decoder_attention_head_dim"]
    heads = vae_cfg["decoder_num_attention_heads"]
    tokens_chunk = math.ceil(clip_len / temporal)
    token_overlap = (-token_drop) % tokens_chunk
    tile_h = max(_tile_spans(height, 256, 64, spatial))
    tile_w = max(_tile_spans(width, 256, 64, spatial))
    seq = (tokens_chunk + token_overlap) * (tile_h // spatial) * (tile_w // spatial)
    seq += vae_cfg["decoder_num_register_tokens"] + 1
    attn_bytes = 2 * heads * seq * seq * 4
    stream_bytes = 10 * seq * dim * 4
    out_bytes = 3 * frames * height * width * 4
    latent_bytes = vae_cfg["latent_channels"] * latent_frames * lat_h * lat_w * 4
    decode_act = attn_bytes + stream_bytes + out_bytes + latent_bytes

    video_vae = vae_weight_bytes(VAE_DIR)
    audio_vae = vae_weight_bytes(AUDIO_VAE_DIR)

    # --- phase 3 activations, same shape of formula at the denoiser's widths -------------------
    patch = config["patch_size"]
    video_rows = (latent_frames // patch[0]) * (lat_h // patch[1]) * (lat_w // patch[2])
    audio_rows = int(round(frames / 24 * 40)) * 2
    text_rows = 64  # nominal; the smoke prompt is 46 rows and a long one is a few hundred
    rows = video_rows + audio_rows + text_rows
    d_heads = config["num_attention_heads"]
    d_dim = config["num_attention_heads"] * config["attention_head_dim"]
    sample_attn = 2 * d_heads * rows * rows * 2  # bf16 scores + probs, math backend
    sample_stream = 10 * rows * HIDDEN_SIZE * 2
    sample_act = sample_attn + sample_stream

    # --- phase 1 ------------------------------------------------------------------------------
    te_header = read_header(INT8_TEXT_ENCODER)
    te_bytes = sum(tensor_bytes(e) for k, e in te_header.items() if not k.endswith(".comfy_quant"))
    te_dequant = max((tensor_bytes(e) * 2 for e in te_header.values() if e["dtype"] == "I8"), default=0)

    cards = [int(c) for c in args.cards]
    enc_card, dec_card = int(args.encoder_card), (cards[0] if args.vae_card is None else int(args.vae_card))
    phases = []

    def row(name: str, per_card: dict[int, int], note: str) -> None:
        phases.append({"phase": name, "per_card": per_card, "note": note})

    row("encode", {enc_card: te_bytes + te_dequant},
        f"{gib(te_bytes)} INT8 encoder + {gib(te_dequant)} largest dequant transient; freed before load.stream")
    # The merge widens one destination weight to float32 and builds a float32 delta beside it, so
    # the transient is twice the widest destination.  Both are deleted per tensor (`load.stream`).
    remap = build_remap(config["num_layers"], config["num_refiner_layers"], args.denoiser)
    widest_fp32 = max(
        src.nbytes(header) // _DTYPE_BYTES[header[src.key]["dtype"]] * 4 for src in remap.values()
    )
    merge_transient = 2 * widest_fp32 if args.lora else 0
    row("load.stream",
        {cards[0]: plan.card0_bytes + merge_transient, cards[1]: plan.card1_bytes + merge_transient},
        f"includes {gib(merge_transient)} of float32 LoRA merge transients (widened weight + delta, "
        "one destination at a time) -- deleted per tensor, cache emptied at the end of the phase"
        if args.lora else "no LoRA: nothing is widened, no merge transient")
    row("sample", {cards[0]: plan.card0_bytes + sample_act, cards[1]: plan.card1_bytes + sample_act},
        f"{gib(sample_act)} of activations at {rows} packed rows, of which {gib(sample_attn)} is "
        f"the bf16 attention matrix ({d_heads} heads x {rows}^2 x 2, materialized): that term is "
        "QUADRATIC in the canvas and vanishes if the XPU dispatches a memory-efficient SDPA kernel")
    row("decode.video", {dec_card: sum(video_vae.values()) + decode_act},
        f"{gib(sum(video_vae.values()))} float32 video VAE + {gib(decode_act)} activations "
        f"(tile {tile_h}x{tile_w}, {seq} tokens, {gib(attn_bytes)} attention) -- tiling caps this, "
        "so it barely grows with the canvas")
    row("decode.audio", {dec_card: sum(audio_vae.values()) + out_bytes},
        f"{gib(sum(audio_vae.values()))} float32 audio VAE, video VAE already released; the "
        f"{gib(out_bytes)} decoded clip is still resident")

    return {
        "canvas": {"height": height, "width": width, "frames": frames, "latent_frames": latent_frames,
                   "latent_hw": [lat_h, lat_w], "packed_rows": rows},
        "video_vae_bytes": video_vae,
        "audio_vae_bytes": audio_vae,
        "decode": {"tile": [tile_h, tile_w], "tokens": seq, "attention_bytes": attn_bytes,
                   "stream_bytes": stream_bytes, "output_bytes": out_bytes, "latent_bytes": latent_bytes},
        "sample": {"rows": rows, "attention_bytes": sample_attn, "stream_bytes": sample_stream},
        "phases": phases,
        "cards": cards,
    }


# The OOM message of 2026-09-19 reports the card as "a total capacity of 31.89 GiB": 32 GiB of
# board memory less what the driver keeps.  That, not 32, is the number a budget has to fit under.
USABLE_CARD_BYTES = int(31.89 * 2**30)


def print_plan_memory(args, config: dict, plan: SplitPlan, header: dict) -> None:
    report = plan_memory(args, config, plan, header)
    c = report["canvas"]
    print(f"memory plan -- {c['height']}x{c['width']}x{c['frames']} "
          f"(latent {c['latent_frames']}x{c['latent_hw'][0]}x{c['latent_hw'][1]}, "
          f"{c['packed_rows']} packed rows), per card, against {gib(USABLE_CARD_BYTES)} usable:")
    for entry in report["phases"]:
        line = "  ".join(
            f"card {card} {gib(b)}{'  OVER' if b > USABLE_CARD_BYTES else ''}"
            for card, b in sorted(entry["per_card"].items())
        )
        print(f"  {entry['phase']:14s} {line}")
        print(f"                 {entry['note']}")
    v = report["video_vae_bytes"]
    print(f"  video vae weights: decoder {gib(v.get('decoder', 0))} + encoder {gib(v.get('encoder', 0))} "
          f"(float32 -- _keep_in_fp32_modules pins every module; --vae-tiling {args.vae_tiling})")
    print("  activations are an UPPER BOUND from the formula in plan_memory()'s docstring, not a "
          "measurement; the run's [vram] lines are the measurement.")
    print()


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

    if (args.decode_only or args.probe_tile_identity is not None) and args.latents_from is None:
        LOG.error("--decode-only and --probe-tile-identity both need --latents-from PATH "
                  "(a previous run's tensors.safetensors, written by --save-tensors)")
        return 2
    if args.latents_from is not None and not args.latents_from.exists():
        LOG.error("--latents-from %s does not exist", args.latents_from)
        return 2

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

    # Experiment E1 exits here: no denoiser, no clip, just tiles and hashes.
    if args.probe_tile_identity is not None:
        if len(args.cards) < 2:
            LOG.error("--probe-tile-identity compares two cards; pass --cards A B")
            return 2
        return probe_tile_identity(args, {})

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
    # Inference only: without this every module call keeps its activations for a backward pass that never comes.
    # 2026-09-19: the video VAE decode grew from 9.7 GiB of weights to 31.4 GiB and ran the card out of memory
    # at 256x448x124 (ViT decoder attention matrices retained layer after layer). No arithmetic changes.
    torch.set_grad_enabled(False)
    for dev in devices:
        torch.xpu.reset_peak_memory_stats(dev)

    # ---- phases 1-3, or the saved latents of a previous run -----------------------------------
    token_ids: list[int] | None = None
    prompt_embeds = None
    source_run: dict | None = None
    if args.decode_only:
        # `--decode-only` exists so a decode experiment costs a decode: ~1.5 min instead of ~4.
        # The latents are the ones the source run saved with --save-tensors, so the only thing
        # that changed between the two runs is the decode itself -- which is what makes
        # "reproduces the source run's video_tensor_sha256" a meaningful gate.
        from safetensors.torch import load_file

        with phase("decode_only.load_latents", timings):
            payload = load_file(str(args.latents_from))
            latents = payload["latents"].detach().to("cpu", copy=True)
            audio_latents = payload["audio_latents"].detach().to("cpu", copy=True)
            del payload
        source_receipt = args.latents_from.parent / "receipt.json"
        source_run = {
            "latents_from": str(args.latents_from),
            "source_dir": str(args.latents_from.parent),
            "source_receipt": str(source_receipt) if source_receipt.exists() else None,
            "source_hashes": None,
            "source_timings_seconds": None,
            "source_settings": None,
        }
        if source_receipt.exists():
            src = json.loads(source_receipt.read_text())
            source_run["source_run_name"] = src.get("run_name")
            source_run["source_hashes"] = src.get("hashes")
            source_run["source_timings_seconds"] = src.get("timings_seconds")
            source_run["source_settings"] = {
                k: src.get("settings", {}).get(k)
                for k in ("denoiser", "lora", "seed", "steps", "height", "width", "frames",
                          "vae_tiling", "vae_decode", "vae_autocast")
            }
        LOG.info("decode-only: %s latents %s from %s (the canvas comes from the latents, so "
                 "--height/--width/--frames are ignored)", args.denoiser, tuple(latents.shape),
                 args.latents_from)
        encoder_peak = sample_peak = card_memory(torch, devices)
        lora_receipt = None
    else:
        latents, audio_latents, prompt_embeds, token_ids, lora_receipt, encoder_peak, sample_peak = (
            _sample_clip(torch, args, plan, config, devices, timings)
        )

    # ---- phase 4: decode ---------------------------------------------------------------------
    return _decode_and_write(torch, args, timings, devices, latents, audio_latents, run_name, out_dir,
                             plan, denoiser, lora_receipt, encoder_peak, sample_peak,
                             prompt_embeds, token_ids, source_run)


def _sample_clip(torch, args, plan, config, devices, timings):
    """Phases 1-3: conditioning, the sharded denoiser, sampling, and the denoiser's release.

    Returns `(latents, audio_latents, prompt_embeds, token_ids, lora_receipt, encoder_peak,
    sample_peak)`; both latent tensors are on the HOST, because the next thing that happens is the
    denoiser teardown.  Unchanged from the version that produced the 2026-09-19 canvas receipts --
    it moved into a function only so `--decode-only` can skip it.
    """
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

    log_vram(torch, devices, "before sample")
    with phase("sample", timings):
        # `output=[...]` returns a dict of those intermediates (ModularPipeline.__call__ docstring).
        result = pipe(**call_kwargs, output=["latents", "audio_latents"])
    sample_peak = card_memory(torch, devices)
    log_vram(torch, devices, "after sample")

    # The latents are the only thing worth keeping out of phase 3 and they are tiny -- 1.6 MB of
    # video latents at 256x448x124, 0.1 MB of audio -- so they go to the host while the denoiser is
    # torn down, and come back to whichever card ends up decoding.  Holding them on a card would
    # pin one allocator block through the release for no reason.
    latents = result["latents"].detach().to("cpu", copy=True)
    audio_latents = result["audio_latents"].detach().to("cpu", copy=True)
    del result
    release_denoiser(torch, transformer, pipe, devices)
    del transformer, pipe
    log_vram(torch, devices, "after denoiser release")
    for dev in devices:
        torch.xpu.reset_peak_memory_stats(dev)
    return latents, audio_latents, prompt_embeds, token_ids, lora_receipt, encoder_peak, sample_peak


def _decode_and_write(torch, args, timings, devices, latents, audio_latents, run_name, out_dir,
                      plan, denoiser, lora_receipt, encoder_peak, sample_peak,
                      prompt_embeds, token_ids, source_run) -> int:
    """Phases 4-5: the two VAEs, the mp4, and the receipt."""
    # ---- phase 4: decode ---------------------------------------------------------------------
    # One VAE on the card at a time, on whichever card the release left emptiest.  The video VAE is
    # 9.700 GiB of float32 weights (see `load_video_vae`) and its ViT decoder's attention is the
    # single largest transient in the run, so the audio VAE's 0.564 GiB waits until it is gone.
    decode_device = pick_decode_card(torch, args, devices)
    # `--vae-card` may name a card outside `--cards`; every release below has to reach it too.
    all_devices = devices if decode_device in devices else devices + [decode_device]
    two_card = args.vae_decode == "two-card"
    vae_source = None
    if two_card:
        # Fail before the 9.7 GiB load if the reimplemented tile loop no longer matches upstream.
        vae_source = check_vae_source()
    vae, vae_tiling = load_video_vae(args, timings, decode_device)
    vae_b = None
    decode_plan = {"mode": "single", "cards": [str(decode_device)], "autocast": args.vae_autocast}
    if two_card:
        vae_source = check_vae_source(type(vae))
        second = next((d for d in devices if d != decode_device), None)
        if second is None:
            raise SystemExit("--vae-decode two-card needs two distinct cards; pass --cards A B")
        vae_b = replicate_video_vae(torch, vae, second, timings)
        if second not in all_devices:
            all_devices = all_devices + [second]
    with phase("decode.video", timings):
        latents_mean = torch.tensor(vae.config.latents_mean, device=decode_device).view(1, -1, 1, 1, 1)
        latents_std = torch.tensor(vae.config.latents_std, device=decode_device).view(1, -1, 1, 1, 1)
        latents = latents.to(decode_device)
        z = (latents * latents_std + latents_mean).to(vae.dtype)
        if two_card:
            video, decode_plan = decode_video_two_card(
                torch, [(decode_device, vae), (second, vae_b)], z, autocast=args.vae_autocast
            )
        else:
            # The single path stays exactly what it was: one `vae.decode` call on one card, with
            # the autocast wrapper upstream applies on CUDA and `--vae-autocast off` disables.
            with vae_autocast_context(torch, args.vae_autocast, decode_device):
                video = vae.decode(z, return_dict=False)[0]
        del z
        pixel_mean = torch.tensor((0.485, 0.456, 0.406), device=decode_device).view(1, -1, 1, 1, 1)
        pixel_std = torch.tensor((0.229, 0.224, 0.225), device=decode_device).view(1, -1, 1, 1, 1)
        video = (video.float() * pixel_std + pixel_mean).clamp(0, 1)
    video_peak = card_memory(torch, all_devices)
    log_vram(torch, all_devices, "after decode.video")
    strip_module_tensors(vae)
    if vae_b is not None:
        strip_module_tensors(vae_b)
    del vae, vae_b
    _free(torch, all_devices)
    log_vram(torch, all_devices, "after video vae release")

    audio_vae = load_audio_vae(args, timings, decode_device)
    with phase("decode.audio", timings):
        a_mean = torch.tensor(audio_vae.config.latents_mean, device=decode_device).view(1, -1, 1)
        a_std = torch.tensor(audio_vae.config.latents_std, device=decode_device).view(1, -1, 1)
        audio_latents = audio_latents.to(decode_device)
        audio = audio_vae.decode((audio_latents * a_std + a_mean).float(), return_dict=False)[0]
        # decode returns (2, 1, N); decoders.py L248 permutes it to (1, 2, N).
        audio = audio.float().permute(1, 0, 2).contiguous()
        sampling_rate = int(audio_vae.config.sampling_rate)
    decode_peak = card_memory(torch, all_devices)
    log_vram(torch, all_devices, "after decode.audio")
    strip_module_tensors(audio_vae)
    del audio_vae
    _free(torch, all_devices)

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
        "prompt": args.prompt if (args.prompt_embeds is None and not args.decode_only) else None,
        "prompt_tokens": (len(token_ids) if token_ids is not None
                          else (int(prompt_embeds.shape[1]) if prompt_embeds is not None else None)),
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
        "peak_memory": {
            "encode": encoder_peak,
            "sample": sample_peak,
            "decode_video": video_peak,
            "decode": decode_peak,
        },
        "decode_placement": {
            "card": str(decode_device),
            "requested": args.vae_card,
            "video_vae_tiling": vae_tiling,
            "one_vae_at_a_time": True,
            "vae_decode": args.vae_decode,
            "vae_autocast": args.vae_autocast,
            "vae_autocast_note": (
                "off = the bit-identical path. fp16/bf16 is upstream's decoders.py autocast with "
                "enabled=True on XPU: an arithmetic change, gated by its own repeat and measured "
                "with compare-h3-runs.py"
            ),
            "video_decode_plan": decode_plan,
            "diffusers_vae_source": vae_source,
        },
        "decode_only": source_run,
        "int8_share_rotation": bool(args.int8_share_rotation) if args.denoiser == "int8" else None,
        "int8_rotation_cache": rotation_cache_stats() if args.denoiser == "int8" else None,
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
            "text_encoder": (None if args.decode_only else
                             (str(INT8_TEXT_ENCODER) if args.prompt_embeds is None else str(args.prompt_embeds))),
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
    # A decode-only run is a decode experiment: say at once whether it reproduced the run it
    # decoded the latents of.  `off` + `single` must match exactly; anything else is the A/B.
    if source_run and source_run.get("source_hashes"):
        agree = True
        for key in ("video_tensor_sha256", "audio_tensor_sha256"):
            same = receipt["hashes"][key] == source_run["source_hashes"].get(key)
            agree &= same
            LOG.info("[decode-only] %-22s %s  source %s", key, "MATCH" if same else "DIFFERS",
                     str(source_run["source_hashes"].get(key))[:16])
        LOG.info("[decode-only] vs %s: %s (--vae-decode %s, --vae-autocast %s)",
                 source_run.get("source_run_name") or source_run["source_dir"],
                 "bytewise-equal" if agree else "NOT bytewise-equal",
                 args.vae_decode, args.vae_autocast)
    LOG.info("wrote %s and %s", mp4, out_dir / "receipt.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
