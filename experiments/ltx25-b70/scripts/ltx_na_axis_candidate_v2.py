# SPDX-FileCopyrightText: Copyright (c) 2025 Comfy Org. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""3D neighborhood attention (NATTEN ``na3d`` semantics) in pure torch.

Per non-causal axis each query attends a window of exactly ``kernel_size``
positions centered on it, shifted inward at grid boundaries; per causal axis
it attends the ``min(i + 1, kernel_size)`` nearest previous positions.
Dilation is not supported.

Strategy: queries are tiled; tiles sharing the same relative window geometry
(all interior tiles, plus a handful of boundary cases per axis) are stacked
into batched ``scaled_dot_product_attention`` calls with one additive mask per
geometry group. SDPA's efficient backend does online softmax, so scores are
never materialized on CUDA.
"""

import math

import torch
import torch.nn.functional as functional

from comfy_kitchen.registry import registry

# Element budget for one tile's [Nq, Nk] attention mask (bounds the mask
# allocation and, on CPU, the math-backend score materialization).
NA_SCORE_BUDGET = 2 ** 25
# Element budget for the stacked K/V copies of one batched SDPA call on CUDA.
NA_KV_STACK_BUDGET = 2 ** 28


def _window_bounds(length, kernel, causal):
    """Per-index (start, end) of the attended window along one axis."""
    starts = []
    ends = []
    if causal:
        for i in range(length):
            starts.append(max(0, i - kernel + 1))
            ends.append(i + 1)
    else:
        kernel = min(kernel, length)
        lo = length - kernel
        half = kernel // 2
        for i in range(length):
            s = min(max(i - half, 0), lo)
            starts.append(s)
            ends.append(s + kernel)
    return starts, ends


def _pick_tiles(dims, kernels):
    """Per-axis query-tile lengths keeping one tile's [Nq, Nk] under budget."""
    tiles = list(dims)

    def cost(ts):
        nq = math.prod(ts)
        nk = math.prod(min(d, t + k - 1) for t, k, d in zip(ts, kernels, dims, strict=True))
        return nq * nk

    while cost(tiles) > NA_SCORE_BUDGET and max(tiles) > 1:
        i = max(range(3), key=lambda a: tiles[a] / kernels[a])
        if tiles[i] <= 1:
            break
        tiles[i] = max(1, (tiles[i] + 1) // 2)
    return tiles


def _group_mask(rel_bounds, dtype, device, axis_cache=None):
    """Additive ``[1, 1, Nq, Nk]`` mask for one tile-geometry group.

    ``rel_bounds``: per-axis (starts, ends) relative to the key region origin.
    """
    bools = []
    for starts, ends in rel_bounds:
        # The cache belongs to this na3d invocation, never to model state.
        # Axis visibility is bool and independent of the additive mask dtype.
        key = (starts, ends, device) if axis_cache is not None else None
        axis = axis_cache.get(key) if axis_cache is not None else None
        if axis is None:
            st = torch.tensor(starts, device=device)
            en = torch.tensor(ends, device=device)
            # `ends` is already a host tuple of ints (it is part of the cache key
            # above), so take the maximum on the host. Reading it back off the
            # device as int(en.max()) is a pointless round trip, and inside an
            # XPU graph capture operations are recorded rather than executed, so
            # that read returns whatever is in the recorded tensor's memory and
            # the result is then used as an allocation size.
            kj = torch.arange(max(ends), device=device)
            axis = (kj[None, :] >= st[:, None]) & (kj[None, :] < en[:, None])
            # At most64 entries of4096 bool elements:256KiB tensor storage.
            # Oversized axes still execute the original uncached operations.
            if axis_cache is not None and len(axis_cache) < 64 and axis.numel() <= 4096:
                axis_cache[key] = axis
        bools.append(axis)
    visible = (bools[0][:, None, None, :, None, None]
               & bools[1][None, :, None, None, :, None]
               & bools[2][None, None, :, None, None, :])
    nq = visible.shape[0] * visible.shape[1] * visible.shape[2]
    nk = visible.shape[3] * visible.shape[4] * visible.shape[5]
    mask = torch.zeros((nq, nk), dtype=dtype, device=device)
    mask.masked_fill_(~visible.reshape(nq, nk), torch.finfo(dtype).min)
    return mask.reshape(1, 1, nq, nk)


def na3d(
    q: torch.Tensor,
    k: torch.Tensor,
    v: torch.Tensor,
    kernel_size: list[int],
    is_causal: list[bool] | None = None,
    scale: float | None = None,
) -> torch.Tensor:
    """3D neighborhood attention over ``(B, T, H, W, NH, HD)`` tensors."""
    batch, t, h, w, nh, hd = q.shape
    dims = (t, h, w)
    causal = [False, False, False] if is_causal is None else list(is_causal)
    kernels = [k_ if c else min(k_, d) for k_, c, d in zip(kernel_size, causal, dims, strict=True)]
    if scale is None:
        scale = hd ** -0.5
    device = q.device
    if scale != 1.0:
        q = q * scale

    bounds = [_window_bounds(d, k_, c) for d, k_, c in zip(dims, kernels, causal, strict=True)]
    tile_t, tile_h, tile_w = _pick_tiles(dims, [min(k_, d) for k_, d in zip(kernels, dims, strict=True)])

    # Group tiles by relative window geometry so each group shares one mask
    # and stacks into batched SDPA calls.
    groups = {}
    for t0 in range(0, t, tile_t):
        t1 = min(t0 + tile_t, t)
        rt0, rt1 = bounds[0][0][t0], bounds[0][1][t1 - 1]
        rel_t = (tuple(s - rt0 for s in bounds[0][0][t0:t1]), tuple(e - rt0 for e in bounds[0][1][t0:t1]))
        for h0 in range(0, h, tile_h):
            h1 = min(h0 + tile_h, h)
            rh0, rh1 = bounds[1][0][h0], bounds[1][1][h1 - 1]
            rel_h = (tuple(s - rh0 for s in bounds[1][0][h0:h1]), tuple(e - rh0 for e in bounds[1][1][h0:h1]))
            for w0 in range(0, w, tile_w):
                w1 = min(w0 + tile_w, w)
                rw0, rw1 = bounds[2][0][w0], bounds[2][1][w1 - 1]
                rel_w = (tuple(s - rw0 for s in bounds[2][0][w0:w1]), tuple(e - rw0 for e in bounds[2][1][w0:w1]))
                groups.setdefault((rel_t, rel_h, rel_w), []).append((
                    (slice(t0, t1), slice(h0, h1), slice(w0, w1)),
                    (slice(rt0, rt1), slice(rh0, rh1), slice(rw0, rw1)),
                ))

    axis_cache = {}  # Invocation-local, read-only geometry; released on return.
    out = torch.empty((batch, t, h, w, nh, hd), device=device, dtype=v.dtype)
    for rel, tiles in groups.items():
        mask = _group_mask(rel, q.dtype, device, axis_cache)
        nq, nk = mask.shape[2], mask.shape[3]
        if device.type == "cuda":
            g_max = max(1, NA_KV_STACK_BUDGET // max(1, batch * nh * nk * hd * 2))
        else:
            g_max = 1  # CPU math backend materializes [G*B, NH, Nq, Nk]
        qs0, _ = tiles[0]
        tq, th, tw = (qs0[0].stop - qs0[0].start, qs0[1].stop - qs0[1].start, qs0[2].stop - qs0[2].start)
        for c0 in range(0, len(tiles), g_max):
            chunk = tiles[c0:c0 + g_max]
            g = len(chunk)
            q_s = torch.stack([q[:, qs[0], qs[1], qs[2]] for qs, _ in chunk])
            k_s = torch.stack([k[:, rs[0], rs[1], rs[2]] for _, rs in chunk])
            v_s = torch.stack([v[:, rs[0], rs[1], rs[2]] for _, rs in chunk])
            # [G, B, t, h, w, NH, HD] -> [G*B, NH, N, HD]
            q_s = q_s.permute(0, 1, 5, 2, 3, 4, 6).reshape(g * batch, nh, nq, hd)
            k_s = k_s.permute(0, 1, 5, 2, 3, 4, 6).reshape(g * batch, nh, nk, hd)
            v_s = v_s.permute(0, 1, 5, 2, 3, 4, 6).reshape(g * batch, nh, nk, hd)
            o = functional.scaled_dot_product_attention(q_s, k_s, v_s, attn_mask=mask, scale=1.0)
            o = o.view(g, batch, nh, tq, th, tw, hd).permute(0, 1, 3, 4, 5, 2, 6)
            for i, (qs, _) in enumerate(chunk):
                out[:, qs[0], qs[1], qs[2]] = o[i]

    return out


# =============================================================================
# torch.library Custom Op Definitions
# =============================================================================


@torch.library.custom_op("comfy_kitchen::na3d", mutates_args=())
def _op_na3d(
    q: torch.Tensor,
    k: torch.Tensor,
    v: torch.Tensor,
    kernel_size: list[int],
    is_causal: list[bool],
    scale: float | None,
) -> torch.Tensor:
    kwargs = {"q": q, "k": k, "v": v, "kernel_size": kernel_size, "is_causal": is_causal, "scale": scale}
    impl = registry.get_implementation("na3d", kwargs=kwargs)
    return impl(**kwargs)


@_op_na3d.register_fake
def _op_na3d_fake(q, k, v, kernel_size, is_causal, scale):
    return torch.empty_like(v)  # v's dtype, as the eager implementation returns
