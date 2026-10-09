"""Packet117: the cone-restricted anchor decode (LTX_ANCHOR_DECODE=cone). Torch is passed in; no device import.

Packet118: unchanged arithmetic and checks; only the identity strings change (schema ltx.stream118.*, latch
anchor-decode-118-refused.json; the packet-118 launcher refuses the lever while this latch or the packet-117 one exists).

Why (notes/2026-10-08-continuation-tail-decode-design.md, option 116b). The frame anchor is the decoded
last pixel frame of a chunk, so the chain waits for the video decode (1.57 s of the 5.5 s period at 97
frames on packet 116b, graph replay, compute-bound). The NA diffusion decoder is non-causal in time, so
a tail decode is not the same mathematics, and a shorter input changes every GEMM's row count. But the
last pixel frame only needs part of the stage-5 work: stage 5 is eight DiffusionNABlocks with temporal
kernel 11 over the pixel-rate context, so after the eight blocks the last frame depends on the last 46
pixel frames of the stage-5 input (51..96 of 97, 75..120 of 121), and stages 1-4 cost little.

What this module does. Inside `cone_decode()` on the decode thread, `NADiffusionDecoder.forward_diff_step`
(the stage-5 step; one call per decode at the single x0 step) is replaced by `ConeStep`, a line-for-line
re-implementation of the sealed `forward_diff_step` / `DiffusionNABlock.forward` /
`NeighborhoodAttention3D.forward` / `SwiGLU.forward` and of the eager `na.na3d` tile loop that issues
ONLY the calls of the full step whose output rows reach the last frame:

- per block L (1..8), the needed output frames N_L (N_8 = {T-1}) and input frames N_{L-1} = the union of
  the na3d temporal windows of N_L (exact `na._window_bounds`);
- `context_proj` chunks (MLP_TOKEN_CHUNK // (h*w) frames) and `qkv` chunks ((2**25) // (h*w*dim) frames)
  run when they intersect N_{L-1}; na3d query tiles run when their frames intersect N_L; `proj` and the
  SwiGLU chunks run when they intersect N_L. A call that runs is the full step's call: the same module,
  the same input slice shape, the same rows for every frame in the cone;
- q/k/v and the na3d output are zero-filled where nothing ran (finite: a masked key adds an exact 0);
- `conv_in_x_t`, the timestep embedding, `norm_out` and `conv_out` run on the whole tensor (they must keep
  their row count M), as do stages 1-4 (`forward_pre_diffusion`, untouched) and the seed-0 noise.

Why that is exact. On this stack every kernel call's output row depends only on the call's shape and on
that row's inputs (GEMM rows: the batch-row probes; per-token norms, RoPE and elementwise ops by
construction; an SDPA query row: softmax and P*V are per row, and a key outside the query's window gets
the additive mask finfo.min, so exp underflows to exactly 0 whatever the key's value). Each call that runs
has the full step's shape and, for every row in the cone, the full step's input bytes; so the last frame
is the full step's last frame bit for bit. Everything after the step (the VAE's F32 cast, process_output,
movedim, reshape) is the native VAE.decode path, which runs unchanged on the cone output. Two cases where
this could not hold are refused at install: na3d not dispatched to the eager backend (another kernel), and
CUDA tile stacking (g_max > 1: skipping a tile would change a batched call's shape).

The runtime still decodes the full chunk for display (native VAEDecode, graph or eager) and requires its
last frame to equal the cone's byte for byte; a mismatch latches the server and writes LATCH_NAME, after
which the launcher refuses LTX_ANCHOR_DECODE=cone.
"""
import contextlib
import hashlib
import threading
import time

SCHEMA = 'ltx.stream118.anchor-decode.v1'
LATCH_NAME = 'anchor-decode-118-refused.json'
DECODER_SOURCE_PATH = 'source/comfy/ldm/lightricks/vae/na_diffusion_decoder.py'
DECODER_SOURCE_SHA256 = '7356bfcaedc545e8af1f4820e7466bbde0a56ccd2e8b2941902af83f16657f21'
NA_EAGER_SHA256 = '4f1d82fe02af995d395969667f6cfd8d10635c3144eec8ca78fe37c103803995'
QKV_ELEMENT_BUDGET = 2 ** 25      # the literal of NeighborhoodAttention3D.forward (`chunk = max(1, (2 ** 25) // ...)`)
MAX_PLANS = 2                     # one stream geometry per server; a second would mean a drifting shape
OPS = ('context_proj', 'qkv', 'na3d_tile', 'proj', 'mlp')


class ConeRefusal(RuntimeError):
    pass


def require(ok, why):
    if not ok:
        raise ConeRefusal(why)


def interval(rows, length):
    """A non-empty contiguous set of frame indices as (lo, hi); refuses anything else."""
    lo, hi = min(rows), max(rows) + 1
    require(0 <= lo and hi <= length and len(rows) == hi - lo, 'Cone frame set is not one interval')
    return lo, hi


def temporal_cone(length, kernel_t, depth, window_bounds):
    """need[0] .. need[depth] as intervals: need[depth] = (length-1, length); need[L-1] = the union of the
    non-causal na3d temporal windows of need[L] (window_bounds = the eager na._window_bounds)."""
    starts, ends = window_bounds(length, min(kernel_t, length), False)
    need = [(length - 1, length)]
    for _ in range(depth):
        lo, hi = need[-1]
        rows = set()
        for q in range(lo, hi):
            rows.update(range(starts[q], ends[q]))
        need.append(interval(rows, length))
    need.reverse()
    return need


def hits(t0, t1, cone):
    """Does the frame range [t0, t1) intersect the interval cone = (lo, hi)?"""
    return t0 < cone[1] and cone[0] < t1


class ConePlan:
    """The per-geometry plan: the cone intervals and the kept/total call counts per op (receipts)."""

    def __init__(self, length, h, w, dim, kernel, depth, window_bounds, pick_tiles, mlp_token_chunk):
        self.length, self.h, self.w, self.dim, self.kernel, self.depth = length, h, w, dim, tuple(kernel), depth
        self.need = temporal_cone(length, kernel[0], depth, window_bounds)
        kernels = [min(k, d) for k, d in zip(kernel, (length, h, w))]
        self.tiles = list(pick_tiles([length, h, w], kernels))
        self.chunks = {'context_proj': max(1, mlp_token_chunk // max(h * w, 1)),
                       'qkv': max(1, QKV_ELEMENT_BUDGET // max(h * w * dim, 1)),
                       'proj': max(1, QKV_ELEMENT_BUDGET // max(h * w * dim, 1)),
                       'mlp': max(1, mlp_token_chunk // max(h * w, 1))}
        spatial_tiles = -(-h // self.tiles[1]) * -(-w // self.tiles[2])
        self.calls = {op: {'kept': 0, 'total': 0, 'kept_rows': 0, 'total_rows': 0} for op in OPS}
        for block in range(1, depth + 1):
            need_in, need_out = self.need[block - 1], self.need[block]
            for op, cone in (('context_proj', need_in), ('qkv', need_in), ('proj', need_out), ('mlp', need_out)):
                step = self.chunks[op]
                for t0 in range(0, length, step):
                    t1 = min(t0 + step, length)
                    self._count(op, hits(t0, t1, cone), t1 - t0)
            for t0 in range(0, length, self.tiles[0]):
                t1 = min(t0 + self.tiles[0], length)
                for _ in range(spatial_tiles):
                    self._count('na3d_tile', hits(t0, t1, need_out), t1 - t0)

    def _count(self, op, kept, rows):
        row = self.calls[op]
        row['total'] += 1
        row['total_rows'] += rows
        if kept:
            row['kept'] += 1
            row['kept_rows'] += rows

    def receipt(self):
        return {'frames': self.length, 'spatial': [self.h, self.w], 'dim': self.dim, 'kernel': list(self.kernel),
                'blocks': self.depth, 'cone': [list(c) for c in self.need], 'na3d_tiles': self.tiles,
                'chunk_frames': dict(self.chunks),
                'calls': {op: dict(v, kept_fraction=round(v['kept'] / v['total'], 6) if v['total'] else None)
                          for op, v in self.calls.items()}}


class ConeStep:
    """The cone-restricted NADiffusionDecoder.forward_diff_step. Mirrors the sealed source line by line;
    `keep_all=True` reproduces the full step (tests compare it with the original byte for byte)."""

    def __init__(self, torch, decoder_module, na_module, kitchen, tracer=None):
        self.torch, self.dm, self.na, self.kitchen = torch, decoder_module, na_module, kitchen
        self.tracer = tracer                 # tests: tracer(op, shape) for every kernel-level call
        self.plans = {}

    def _trace(self, op, *shapes):
        if self.tracer is not None:
            self.tracer(op, tuple(tuple(s) for s in shapes))

    def plan(self, dec, context):
        _batch, t5, h5, w5, _c = context.shape
        block = dec.diff_blocks[0]
        key = (int(t5), int(h5), int(w5), int(block.attn.dim), tuple(block.attn.kernel_size), len(dec.diff_blocks))
        plan = self.plans.get(key)
        if plan is None:
            require(len(self.plans) < MAX_PLANS, 'Cone plan count exceeded: the stream geometry drifted')
            require(all(tuple(b.attn.kernel_size) == key[4] and b.attn.dim == key[3] for b in dec.diff_blocks),
                    'Stage-5 blocks differ in kernel or width')
            plan = ConePlan(key[0], key[1], key[2], key[3], key[4], key[5], self.na._window_bounds,
                            self.na._pick_tiles, self.dm.MLP_TOKEN_CHUNK)
            self.plans[key] = plan
        return plan

    def __call__(self, dec, context, x_t, t, keep_all=False):
        """forward_diff_step(context, x_t, t) of the sealed decoder, cone-restricted to the last frame."""
        dm = self.dm
        plan = self.plan(dec, context)
        need = [(0, plan.length)] * (plan.depth + 1) if keep_all else plan.need
        x = dm.patchify(x_t, patch_size_hw=dec.patch_size, patch_size_t=1)
        x = dec.conv_in_x_t(x.permute(0, 2, 3, 4, 1))
        self._trace('conv_in_x_t', x.shape)
        t_emb = dec.t_embedder(dec.timestep_scale_multiplier * t, dtype=x.dtype)
        modulation = dec.shared_adaln(t_emb)
        for index, block in enumerate(dec.diff_blocks):
            x = self._block(block, x, context, modulation, need[index], need[index + 1])
        x = dec.norm_out(x)
        x = dec.conv_out(x)
        self._trace('norm_out+conv_out', x.shape)
        x = x.permute(0, 4, 1, 2, 3)
        return dm.unpatchify(x, patch_size_hw=dec.patch_size, patch_size_t=1)

    # -- DiffusionNABlock.forward ---------------------------------------------------------------
    def _block(self, block, x, latent_context, modulation, need_in, need_out):
        dm = self.dm
        scale_msa, shift_msa, _, scale_mlp, shift_mlp, _, _ = [
            modulation[i] + block.scale_shift_table[i].view(1, 1, 1, 1, -1) for i in range(dm.AdaLNZero.NUM_CHUNKS)
        ]
        chunk = max(1, dm.MLP_TOKEN_CHUNK // max(x.shape[2] * x.shape[3], 1))
        for t0 in range(0, x.shape[1], chunk):
            if hits(t0, min(t0 + chunk, x.shape[1]), need_in):
                x[:, t0:t0 + chunk] += block.context_proj(latent_context[:, t0:t0 + chunk])
                self._trace('context_proj', latent_context[:, t0:t0 + chunk].shape)
        x = self._attn(block.attn, x, lambda s: dm.modulate(block.norm1(s), scale_msa, shift_msa), x,
                       need_in, need_out)
        return self._mlp(block.mlp, x, lambda s: dm.modulate(block.norm2(s), scale_mlp, shift_mlp), x, need_out)

    # -- NeighborhoodAttention3D.forward ----------------------------------------------------------
    def _attn(self, attn, x, pre, add_to, need_in, need_out):
        torch, dm = self.torch, self.dm
        batch, t, h, w, _ = x.shape
        inv_freqs = tuple(dm.rope_inv_freqs(d, attn.rope_base, device=x.device) for d in attn.rope_split)
        tables = dm._rope_tables((t, h, w), inv_freqs, x.device)
        shape = (batch, t, h, w, attn.num_heads, attn.head_dim)
        # Cone: zero-filled where no qkv chunk runs (the full step leaves no row unwritten).
        q = torch.zeros(shape, dtype=x.dtype, device=x.device)
        k = torch.zeros(shape, dtype=x.dtype, device=x.device)
        v = torch.zeros(shape, dtype=x.dtype, device=x.device)
        q_weight = (attn.q_norm.weight.detach() * attn.scale).to(x.dtype)
        k_weight = attn.k_norm.weight.detach().to(x.dtype)
        chunk = max(1, QKV_ELEMENT_BUDGET // max(h * w * attn.dim, 1))
        for t0 in range(0, t, chunk):
            t1 = min(t0 + chunk, t)
            if not hits(t0, t1, need_in):
                continue
            sl = x[:, t0:t1] if pre is None else pre(x[:, t0:t1])
            qc, kc, vc = attn.qkv(sl).chunk(3, dim=-1)
            self._trace('qkv', sl.shape)
            cshape = (batch, t1 - t0, h, w, attn.num_heads, attn.head_dim)
            q[:, t0:t1] = qc.reshape(cshape)
            k[:, t0:t1] = kc.reshape(cshape)
            v[:, t0:t1] = vc.reshape(cshape)
            freqs = dm._rope_matrices_slice(tables, t0, t1, h, w)
            nt = (t1 - t0) * h * w
            for b in range(batch):
                self.kitchen.rms_rope_(
                    q[b, t0:t1].view(1, nt, attn.num_heads, attn.head_dim),
                    k[b, t0:t1].view(1, nt, attn.num_heads, attn.head_dim),
                    freqs, q_weight, k_weight)
                self._trace('rms_rope_', (1, nt, attn.num_heads, attn.head_dim))
        out = self._na3d(q, k, v, list(attn.kernel_size), need_out)
        del q, k, v
        out = out.reshape(batch, t, h, w, attn.dim)
        res = add_to if add_to is not None else torch.empty_like(out)
        for t0 in range(0, t, chunk):
            t1 = min(t0 + chunk, t)
            if not hits(t0, t1, need_out):
                continue
            if add_to is not None:
                res[:, t0:t1] += attn.proj(out[:, t0:t1])
            else:
                res[:, t0:t1] = attn.proj(out[:, t0:t1])
            self._trace('proj', out[:, t0:t1].shape)
        return res

    # -- comfy_kitchen eager na.na3d (scale 1.0, non-causal) ----------------------------------------------
    def _na3d(self, q, k, v, kernel_size, need_out):
        torch, na = self.torch, self.na
        batch, t, h, w, nh, hd = q.shape
        dims = (t, h, w)
        causal = [False, False, False]
        kernels = [k_ if c else min(k_, d) for k_, c, d in zip(kernel_size, causal, dims, strict=True)]
        device = q.device
        bounds = [na._window_bounds(d, k_, c) for d, k_, c in zip(dims, kernels, causal, strict=True)]
        tile_t, tile_h, tile_w = na._pick_tiles(dims, [min(k_, d) for k_, d in zip(kernels, dims, strict=True)])
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
        # Cone: rows of skipped tiles stay zero (the full na3d writes every row).
        out = torch.zeros((batch, t, h, w, nh, hd), device=device, dtype=v.dtype)
        for rel, tiles in groups.items():
            kept = [tile for tile in tiles if hits(tile[0][0].start, tile[0][0].stop, need_out)]
            if not kept:
                continue
            mask = na._group_mask(rel, q.dtype, device)
            nq, nk = mask.shape[2], mask.shape[3]
            require(device.type != 'cuda', 'Cone na3d refuses CUDA tile stacking (g_max > 1 changes call shapes)')
            g_max = 1
            qs0, _ = tiles[0]
            tq, th, tw = (qs0[0].stop - qs0[0].start, qs0[1].stop - qs0[1].start, qs0[2].stop - qs0[2].start)
            for c0 in range(0, len(kept), g_max):
                chunk = kept[c0:c0 + g_max]
                g = len(chunk)
                q_s = torch.stack([q[:, qs[0], qs[1], qs[2]] for qs, _ in chunk])
                k_s = torch.stack([k[:, rs[0], rs[1], rs[2]] for _, rs in chunk])
                v_s = torch.stack([v[:, rs[0], rs[1], rs[2]] for _, rs in chunk])
                q_s = q_s.permute(0, 1, 5, 2, 3, 4, 6).reshape(g * batch, nh, nq, hd)
                k_s = k_s.permute(0, 1, 5, 2, 3, 4, 6).reshape(g * batch, nh, nk, hd)
                v_s = v_s.permute(0, 1, 5, 2, 3, 4, 6).reshape(g * batch, nh, nk, hd)
                o = na.functional.scaled_dot_product_attention(q_s, k_s, v_s, attn_mask=mask, scale=1.0)
                self._trace('na3d_tile', q_s.shape, k_s.shape)
                o = o.view(g, batch, nh, tq, th, tw, hd).permute(0, 1, 3, 4, 5, 2, 6)
                for i, (qs, _) in enumerate(chunk):
                    out[:, qs[0], qs[1], qs[2]] = o[i]
        return out

    # -- SwiGLU.forward -------------------------------------------------------------------------------
    def _mlp(self, mlp, x, pre, add_to, need_out):
        torch, dm = self.torch, self.dm
        _, t, h, w, _ = x.shape
        chunk = max(1, dm.MLP_TOKEN_CHUNK // max(h * w, 1))
        out = add_to if add_to is not None else torch.empty_like(x)
        for t0 in range(0, t, chunk):
            t1 = min(t0 + chunk, t)
            if not hits(t0, t1, need_out):
                continue
            sl = x[:, t0:t1] if pre is None else pre(x[:, t0:t1])
            y = mlp.w_down(dm.F.silu(mlp.w_gate(sl)) * mlp.w_up(sl))
            self._trace('mlp', sl.shape)
            if add_to is not None:
                out[:, t0:t1] += y
            else:
                out[:, t0:t1] = y
        return out


class ConeShadow:
    """Instance attribute over NADiffusionDecoder.forward_diff_step: the cone step inside cone_decode() on
    the owner thread, the inner callable (the decoder-graph shadow or the original method) otherwise."""

    def __init__(self, ctl, inner):
        self.ctl, self.inner = ctl, inner

    def __call__(self, context, x_t, t):
        ctl = self.ctl
        if not ctl.active():
            return self.inner(context, x_t, t)
        started = time.monotonic()
        out = ctl.step(ctl.decoder, context, x_t, t)
        ctl.steps += 1
        ctl.last_step_s = round(time.monotonic() - started, 6)
        return out


class ConeAnchorDecode:
    """Installs the cone step on ONE resident NADiffusionDecoder; thread-confined scope; receipts."""

    def __init__(self, torch, decoder_module, na_module, decoder, kitchen, digest, decoder_graph=None, tracer=None):
        require(type(decoder).__name__ == 'NADiffusionDecoder' and
                getattr(decoder_module, 'NADiffusionDecoder', None) is type(decoder),
                'Expected the sealed NA diffusion decoder')
        require(digest(decoder_module.__file__) == DECODER_SOURCE_SHA256,
                'Decoder module differs from the sealed na_diffusion_decoder.py')
        require(digest(na_module.__file__) == NA_EAGER_SHA256, 'Eager na3d backend differs from the pinned file')
        require(int(decoder.default_inference_timesteps.shape[0]) == 1 and decoder.model_output_type == 'x0',
                'Cone decode assumes the single-step x0 decoder configuration')
        require(all(type(b) is decoder_module.DiffusionNABlock and
                    type(b.attn) is decoder_module.NeighborhoodAttention3D and type(b.mlp) is decoder_module.SwiGLU
                    for b in decoder.diff_blocks), 'Stage-5 block classes differ from the sealed module')
        for module in decoder.modules():
            require(not (module._forward_hooks or module._forward_pre_hooks),
                    'Cone decode does not support module hooks')
        for name in ('_window_bounds', '_pick_tiles', '_group_mask', 'functional'):
            require(getattr(na_module, name, None) is not None, 'Eager na3d helper missing: ' + name)
        require(callable(getattr(kitchen, 'rms_rope_', None)) and getattr(decoder_module, 'comfy_kitchen', None) is kitchen,
                'Decoder module does not use this comfy_kitchen')
        self.torch, self.decoder, self.dm, self.na = torch, decoder, decoder_module, na_module
        self.step = ConeStep(torch, decoder_module, na_module, kitchen, tracer=tracer)
        self.decoder_graph = decoder_graph
        self.local = threading.local()
        self.owner_thread = None
        self.shadow = None
        self.steps = 0
        self.decodes = 0
        self.last_step_s = None
        self.checks = {'equal': 0, 'differ': 0}

    def install(self):
        require(self.shadow is None, 'Cone decode installed twice')
        dec = self.decoder
        inner = vars(dec).get('forward_diff_step')
        if self.decoder_graph is not None:
            require(inner is not None and inner is self.decoder_graph.installed['shadows']['forward_diff_step'],
                    'Install the cone over the decoder-graph shadow')
        else:
            require(inner is None, 'forward_diff_step is already shadowed by something else')
            inner = dec.forward_diff_step
            require(getattr(inner, '__func__', None) is self.dm.NADiffusionDecoder.forward_diff_step,
                    'forward_diff_step is not the sealed method')
        self.shadow = ConeShadow(self, inner)
        dec.forward_diff_step = self.shadow
        if self.decoder_graph is not None:
            self.decoder_graph.register_outer('forward_diff_step', self.shadow)
        return self.receipt()

    def check(self):
        require(self.shadow is not None and vars(self.decoder).get('forward_diff_step') is self.shadow,
                'Cone shadow was replaced or removed')

    def active(self):
        return getattr(self.local, 'active', False) and threading.get_ident() == self.owner_thread

    @contextlib.contextmanager
    def cone_decode(self):
        """Decode thread only: inside this block the stage-5 step is the cone step."""
        self.check()
        if self.owner_thread is None:
            self.owner_thread = threading.get_ident()
        require(threading.get_ident() == self.owner_thread, 'Cone decode is bound to the decode thread')
        require(not getattr(self.local, 'active', False), 'Re-entrant cone decode')
        before = self.steps
        self.local.active = True
        try:
            yield self
        finally:
            self.local.active = False
        require(self.steps == before + 1, 'The cone decode did not run exactly one stage-5 step')
        self.decodes += 1

    def note_check(self, equal):
        self.checks['equal' if equal else 'differ'] += 1

    def receipt(self):
        return {'schema': SCHEMA, 'installed': self.shadow is not None,
                'over': 'decoder-graph shadow' if self.decoder_graph is not None else 'sealed method',
                'decoder_source_sha256': DECODER_SOURCE_SHA256, 'na_eager_sha256': NA_EAGER_SHA256,
                'steps': self.steps, 'decodes': self.decodes, 'checks': dict(self.checks),
                'last_step_s': self.last_step_s,
                'plans': [p.receipt() for p in self.step.plans.values()]}


def frame_bytes(torch, images, index):
    """images[index] as complete little-endian F32 bytes (the anchor form, stream_preview.anchor_bytes)."""
    frame = images.detach().to('cpu')[index:index + 1]
    return frame.contiguous().view(torch.uint8).numpy().tobytes()


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()
