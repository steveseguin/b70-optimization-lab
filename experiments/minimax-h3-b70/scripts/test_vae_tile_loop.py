#!/usr/bin/env python3
"""The runner's two-card tile loop is `AutoencoderKLMiniMaxH3`'s own loop, tile for tile.

    /mnt/fast-ai/venvs/minimax-h3-cpu/bin/python test_vae_tile_loop.py

CPU only, no GPU, no diffusers install needed, a few MB of host RAM.

Why it exists
-------------
`--vae-decode two-card` does not edit the diffusers checkout: `decode_video_two_card()` in
run_h3_t2v.py REIMPLEMENTS the chunk loop of `AutoencoderKLMiniMaxH3._decode` and the tile loop of
`._decode_clip`, so that the per-tile `post_quant_conv` + `decoder` calls can be dispatched to two
cards.  Everything that does arithmetic is still the VAE's own method (`_split_tiles`,
`post_quant_conv`, `decoder`, `_stitch_tiles`, `_blend`) -- but the *slicing*, the *order* and the
*gather* are this repo's, and if any of them drifts from upstream the clip changes silently.

So this test runs the two side by side.  The reference is not a copy of upstream pasted here: the
methods are extracted from the installed diffusers source file with `ast` and bound to a stub
autoencoder, so what the runner is compared against is literally upstream's code, executing.  The
stub's `decoder` is a cheap content-dependent expansion with the real shape contract
(`[B, C, f, h, w] -> [B, 3, 4f, 16h, 16w]`), which is what makes an ordering or blend-weight
difference show up as a different output tensor rather than as luck.

Checks
------
1. the diffusers source still hashes to `DIFFUSERS_VAE_SOURCE_SHA256` (the assertion the two-card
   path makes at start-up, made here too so a drift fails on CPU first);
2. the tile grid the runner plans -- indices, lengths and the overlaps that ARE the blend weights
   -- equals what upstream's `_split_tiles` returns;
3. the per-tile decoder inputs match one for one, in the same order, down to shape, strides and
   storage offset (a contiguity difference is enough to change a conv kernel on a card);
4. the decoded clip is bitwise equal to upstream's `_decode` output, for a latent that exercises
   two temporal chunks, uneven spatial overlaps and the temporal cross-fade;
5. the same holds with one worker card (the degenerate split) and with a latent length that forces
   `pad_tokens > 0`, i.e. the trailing-frame trim.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import math
import pathlib
import sys

import torch
import torch.nn as nn

HERE = pathlib.Path(__file__).resolve().parent

FAILURES: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{('  ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


def load_runner():
    spec = importlib.util.spec_from_file_location("run_h3_t2v", HERE / "run_h3_t2v.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_h3_t2v"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------------------------
# The reference: upstream's own methods, lifted out of the source file and bound to a stub.
# ---------------------------------------------------------------------------------------------

REFERENCE_METHODS = ("_split_tiles", "_blend", "_stitch_tiles", "_decode_clip", "_decode")


def upstream_methods(path: pathlib.Path) -> dict:
    """`{name: function}` for the tiling/chunking methods of `AutoencoderKLMiniMaxH3`.

    Parsed and compiled from the file itself, so this is upstream's code running, not a paraphrase
    of it.  Only these five functions are compiled, which is why the diffusers package does not
    have to be importable (the CPU venv has no diffusers).
    """
    tree = ast.parse(path.read_text(), filename=str(path))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AutoencoderKLMiniMaxH3")
    funcs = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in REFERENCE_METHODS]
    missing = set(REFERENCE_METHODS) - {f.name for f in funcs}
    if missing:
        raise SystemExit(f"{path} no longer defines {sorted(missing)}")
    module = ast.Module(body=funcs, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict = {"torch": torch, "math": math, "nn": nn}
    exec(compile(module, str(path), "exec"), namespace)  # noqa: S102 - upstream's own source
    return {name: namespace[name] for name in REFERENCE_METHODS}


class StubDecoder(nn.Module):
    """A decoder with the real shape contract and a content-dependent, deterministic output.

    One latent voxel becomes a `patch_size_t x patch_size x patch_size` pixel block, exactly as
    `MiniMaxH3VideoViTDecoder3d` does; here the block is a repeat instead of 36 transformer layers.
    The `weight` Parameter exists so `get_parameter_dtype(vae.decoder)` (which is what `decode()`
    casts the latents with) has something to read.
    """

    def __init__(self, patch_size: int = 16, patch_size_t: int = 4) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.tensor([1.5], dtype=torch.float32))
        self.patch_size = patch_size
        self.patch_size_t = patch_size_t
        self.calls: list[dict] = []

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        self.calls.append(fingerprint(z))
        y = (z[:, :3] * self.weight).tanh()
        return (y.repeat_interleave(self.patch_size_t, dim=2)
                 .repeat_interleave(self.patch_size, dim=3)
                 .repeat_interleave(self.patch_size, dim=4))


class StubPostQuantConv(nn.Conv3d):
    """`post_quant_conv`, recording the tile it was handed -- which IS the tile the loop sliced."""

    def __init__(self, channels: int) -> None:
        super().__init__(channels, channels, kernel_size=1)
        self.calls: list[dict] = []

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        self.calls.append(fingerprint(z))
        return super().forward(z)


class StubConfig(dict):
    """`vae.config.clip_length` / `.token_drop`, the two config reads the loops make."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:  # pragma: no cover
            raise AttributeError(name) from exc


class StubVAE(nn.Module):
    """The geometry of `AutoencoderKLMiniMaxH3.__init__`, with tiles shrunk to keep this on CPU."""

    def __init__(self, tile: int = 64, min_overlap: int = 16, clip_length: int = 17,
                 token_drop: int = 3, spatial_ratio: int = 16, temporal_ratio: int = 4,
                 latent_channels: int = 24) -> None:
        super().__init__()
        self.config = StubConfig(clip_length=clip_length, token_drop=token_drop)
        self.spatial_compression_ratio = spatial_ratio
        self.temporal_compression_ratio = temporal_ratio
        self.post_quant_conv = StubPostQuantConv(latent_channels)
        self.decoder = StubDecoder(patch_size=spatial_ratio, patch_size_t=temporal_ratio)
        # Verbatim from the model's __init__ (L596-599).
        self.frame_pre_padding = (-clip_length) % temporal_ratio
        self.tokens_chunk_size = math.ceil(clip_length / temporal_ratio)
        self.token_overlap = (-token_drop) % self.tokens_chunk_size
        self.frame_overlap = max(self.token_overlap * temporal_ratio - self.frame_pre_padding, 0)
        self.use_slicing = False
        self.use_tiling = True
        self.tile_sample_min_height = tile
        self.tile_sample_min_width = tile
        self.tile_sample_min_overlap_height = min_overlap
        self.tile_sample_min_overlap_width = min_overlap


def bind_reference(methods: dict) -> None:
    for name, func in methods.items():
        setattr(StubVAE, name, func)


def fingerprint(t: torch.Tensor) -> dict:
    """Everything about a tile input that could change the kernel or the answer."""
    flat = t.detach().contiguous().flatten().view(torch.uint8)
    return {"shape": tuple(t.shape), "stride": tuple(t.stride()),
            "offset": int(t.storage_offset()), "sha256": hashlib.sha256(memoryview(flat.numpy())).hexdigest()}


def make_pair(seed: int = 7, **kwargs) -> tuple[StubVAE, StubVAE]:
    """Two stubs with identical weights -- the CPU stand-in for the two replicated cards."""
    torch.manual_seed(seed)
    a = StubVAE(**kwargs).eval()
    b = StubVAE(**kwargs).eval()
    b.load_state_dict(a.state_dict())
    return a, b


def run_case(runner, label: str, latent_frames: int, latent_h: int, latent_w: int, cards: int) -> None:
    a, b = make_pair()
    z = torch.randn(1, 24, latent_frames, latent_h, latent_w, dtype=torch.float32)

    a.post_quant_conv.calls.clear()
    with torch.no_grad():
        reference = a._decode(z)
    ref_calls = list(a.post_quant_conv.calls)

    replicas = [(torch.device("cpu"), a)] + ([(torch.device("cpu"), b)] if cards > 1 else [])
    seen: dict[int, dict] = {}

    def hook(worker, k, c, i, j, tile, out):
        seen[k] = {"worker": worker, "chunk": c, "row": i, "column": j, **fingerprint(tile)}

    a.post_quant_conv.calls.clear()
    b.post_quant_conv.calls.clear()
    with torch.no_grad():
        got, plan = runner.decode_video_two_card(torch, replicas, z, tile_hook=hook)

    print(f"{label}: latent {tuple(z.shape)}, {plan['num_chunks']} chunks x "
          f"{plan['tiles_per_chunk']} tiles over {cards} card(s), split {plan['tiles_per_card']}")

    # 2. the tile grid and the blend weights (the overlaps ARE the blend extents)
    height, width = latent_h * a.spatial_compression_ratio, latent_w * a.spatial_compression_ratio
    y_ref = a._split_tiles(height, a.tile_sample_min_height, a.tile_sample_min_overlap_height)
    x_ref = a._split_tiles(width, a.tile_sample_min_width, a.tile_sample_min_overlap_width)
    grid_ok = (list(y_ref[0]) == plan["y_indices"] and list(y_ref[1]) == plan["y_lengths"]
               and list(y_ref[2]) == plan["y_overlaps"] and list(x_ref[0]) == plan["x_indices"]
               and list(x_ref[1]) == plan["x_lengths"] and list(x_ref[2]) == plan["x_overlaps"])
    check(grid_ok, f"{label}: tile grid and blend extents match _split_tiles",
          f"rows {plan['y_indices']} overlaps {plan['y_overlaps']}, "
          f"cols {plan['x_indices']} overlaps {plan['x_overlaps']}")

    # 3. the per-tile decoder inputs, one for one, in the original order
    got_calls = [seen[k] for k in sorted(seen)]
    same_len = len(got_calls) == len(ref_calls)
    check(same_len, f"{label}: one decoder call per upstream call",
          f"{len(got_calls)} vs {len(ref_calls)}")
    if same_len:
        bad = [k for k, (g, r) in enumerate(zip(got_calls, ref_calls))
               if (g["shape"], g["stride"], g["offset"], g["sha256"])
               != (r["shape"], r["stride"], r["offset"], r["sha256"])]
        check(not bad, f"{label}: tile inputs identical in order (shape, strides, offset, bytes)",
              "" if not bad else f"first mismatch at job {bad[0]}")
        order_ok = [(c["chunk"], c["row"], c["column"]) for c in got_calls] == [
            (c, i, j) for c in range(plan["num_chunks"])
            for i in range(len(plan["y_indices"])) for j in range(len(plan["x_indices"]))
        ]
        check(order_ok, f"{label}: jobs enumerated in the original row-major (chunk, row, col) order")

    # 4. the decoded clip
    check(got.shape == reference.shape, f"{label}: decoded shape", f"{tuple(got.shape)}")
    check(bool(torch.equal(got, reference)), f"{label}: decoded clip is bitwise equal to _decode",
          f"max|d| {float((got.double() - reference.double()).abs().max()):.3e}")


def main() -> int:
    runner = load_runner()

    print("1. the diffusers source this reimplementation was written against")
    source = runner.check_vae_source(require=False)
    check(bool(source["matches"]), "diffusers VAE source hash matches DIFFUSERS_VAE_SOURCE_SHA256",
          f"{source['sha256']} at {source['path']}")
    if not source["matches"]:
        print("  (re-read _decode / _decode_clip before trusting anything below)")
    path = pathlib.Path(source["path"])
    if not path.exists():
        print(f"  cannot find {path}; nothing to compare against")
        return 1
    bind_reference(upstream_methods(path))
    print()

    print("2-4. the tile loop, against upstream's own _decode")
    # 12 latent frames -> 2 chunks, no padding; 12x16 latents -> 192x256 pixels -> a 4x5 tile grid
    # whose row overlaps are uneven (32, 16, 16), which is what catches a blend-extent mix-up.
    run_case(runner, "two cards", latent_frames=12, latent_h=12, latent_w=16, cards=2)
    print()
    run_case(runner, "one card ", latent_frames=12, latent_h=12, latent_w=16, cards=1)
    print()
    # 10 latent frames -> num_tokens 13 -> pad_tokens 2 -> the trailing-frame trim of _decode.
    run_case(runner, "padded   ", latent_frames=10, latent_h=12, latent_w=16, cards=2)
    print()

    if FAILURES:
        print(f"FAILED: {len(FAILURES)}")
        for name in FAILURES:
            print(f"  - {name}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
