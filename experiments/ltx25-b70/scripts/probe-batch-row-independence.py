#!/usr/bin/env python3
"""Probe: is each row of a fixed-size LTX 2.5 transformer batch independent of the other rows?

Stand-alone (no ComfyUI server, no sealed launcher, one card, eager, no graph
capture, none of the lane's capture/shard/pipeline/fast-path nodes). Packet 72
showed a batch-2 forward's rows are not bitwise equal to batch-1 forwards, even
for two identical rows. GEMM rounding on this stack depends on the row count,
so that alone does not close batching. What decides it is whether, at a FIXED
batch size, a row's result depends only on that row's inputs:

  a. neighbour independence: row 0 of (A,B,..) == row 0 of (A,C,..)
  b. slot independence:      A in slot 0 of (A,B,..) == A in slot j of (B,..,A,..)
  c. identical rows:         (A,A,..) rows all equal
  d. repeatability:          the same batch twice is equal
  e. versus batch 1:         expected to differ; sized in bf16 ulps, against the
                             output scale and against two unrelated clips
  f. batch-size dependence:  A's row at batch 2 vs 3 vs 4

and it sizes the saving: per-forward wall time and compute-engine busy time
(this process's own DRM fdinfo counters) at batch 1..4 for the stage-1 and
stage-2 shapes.

    ZE_AFFINITY_MASK=<card> python probe-batch-row-independence.py <out.json>
        [--blocks 12] [--batches 2,3,4] [--forwards first|all] [--cpu]

Model: the transformer checkpoint is read through safetensors' memory map and
only the first --blocks transformer blocks (plus every non-block weight) are
put in the state dict; the checkpoint's config metadata gets num_layers=N, and
the dict goes through ComfyUI's own comfy.sd.load_diffusion_model_state_dict
(the function UNETLoader -> comfy.sd.load_diffusion_model calls, with the same
empty model_options as UNETLoader 'default'). The dropped blocks are never
read, never constructed and never moved. The output is not a meaningful video;
the probe is about arithmetic and every kernel type of a block is exercised.

Sampling follows the workflow (graph-capture-all48-pipe-samp2-tsh-rep-wlean /
pipe-batchproof): EmptyLTXVLatentVideo 128x128x25 + LTXVEmptyLatentAudio
(25 frames at 24 fps; driven with a stub audio VAE that carries only the latent
geometry, [1, 8, 26, 16] as recorded by packet 72's census, because the audio VAE
is not loaded), LTXVConcatAVLatent, LTXVConditioning(frame_rate=24),
LTXVDualCFGGuider(video_cfg=1, audio_cfg=1), KSamplerSelect euler_ancestral,
RandomNoise 42, ManualSigmas 404 (stage 1) and 395 (stage 2),
SamplerCustomAdvanced. The text conditioning is a seeded random fp32 CPU tensor
[1, 35, 6144] marked unprocessed_ltxav_embeds (what the Gemma encoder's
dual_linear projection hands over); the model's own connector pads it to 1024
tokens in extra_conds. Stage 2 is NOT driven from the latent upsampler: its
video latent is a seeded random [1, 128, 4, 8, 8] tensor (the upsampler's output
shape for 256x256), concatenated with stage 1's real audio output.
"""
import argparse, glob, json, math, os, re, statistics, sys, time, traceback

PACKET = '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-workers-95'
SRC = PACKET + '/source'
CKPT = '/mnt/fast-ai/llm-models/LTX-2.5-baseline/diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors'
SCHEMA = 'ltx.batch-row-independence-probe.v1'

# Workflow parameters (graph-capture-all48-pipe-samp2-tsh-rep-wlean.json).
WIDTH = HEIGHT = 128            # node 356, stage 1 (upsampled x2 for stage 2)
LENGTH = 25                     # node 356 / 366 frames_number
FRAME_RATE = 24.0               # node 365 / 366
NOISE_SEED = 42                 # nodes 338 and 339
SAMPLER = 'euler_ancestral'     # nodes 341 and 352
SIGMAS_STAGE1 = '1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0'  # node 404
SIGMAS_STAGE2 = '0.85, 0.7250, 0.4219, 0.0'                                            # node 395
CFG = 1.0                       # nodes 388 and 391, video_cfg = audio_cfg
AUDIO_CHANNELS, AUDIO_LATENTS, AUDIO_FREQ = 8, 26, 16      # packet 72 census args[0][1] = [1, 8, 26, 16]
STAGE2_VIDEO_SHAPE = (1, 128, (LENGTH - 1) // 8 + 1, 2 * HEIGHT // 32, 2 * WIDTH // 32)  # [1, 128, 4, 8, 8]
TEXT_TOKENS = 35
SEED = 20261004
WARMUP, TIMED = 2, 6

ap = argparse.ArgumentParser()
ap.add_argument('out')
ap.add_argument('--blocks', type=int, default=None, help='transformer blocks kept (default 12, or 2 with --cpu)')
ap.add_argument('--batches', default='2,3,4')
ap.add_argument('--forwards', choices=('first', 'all'), default='first')
ap.add_argument('--cpu', action='store_true', help='logic check on the CPU (never touches torch.xpu)')
ap.add_argument('--checkpoint', default=CKPT, help='transformer checkpoint (tests only)')
ap.add_argument('--skip-timing', action='store_true')
OPT = ap.parse_args()
OPT.blocks = OPT.blocks if OPT.blocks is not None else (2 if OPT.cpu else 12)
OPT.batch_sizes = sorted({int(b) for b in OPT.batches.split(',') if b.strip()})
assert OPT.blocks >= 1 and all(2 <= b <= 4 for b in OPT.batch_sizes), (OPT.blocks, OPT.batch_sizes)
OUT = os.path.abspath(OPT.out)

# Same environment and numerics-relevant flags as the server (launch/serve-encoder.py and
# encoder-server-workers-95b-shard4-a-w3/server-args.json).
for key, value in (('OMP_NUM_THREADS', '16'), ('MKL_NUM_THREADS', '16'), ('TOKENIZERS_PARALLELISM', 'false'),
                   ('HF_HUB_OFFLINE', '1')):
    os.environ.setdefault(key, value)
COMFY_ARGS = ['--cache-none', '--deterministic', '--disable-async-offload', '--disable-dynamic-vram',
              '--disable-comfy-compiler', '--disable-cuda-graphs', '--disable-pinned-memory', '--reserve-vram', '2',
              '--bf16-unet', '--bf16-text-enc', '--bf16-vae', '--use-pytorch-cross-attention', '--disable-xformers',
              '--disable-api-nodes'] + (['--cpu'] if OPT.cpu else [])
sys.argv = [SRC + '/main.py'] + COMFY_ARGS
sys.path.insert(0, SRC)
os.chdir(SRC)

import torch  # noqa: E402

if OPT.cpu:
    # Tripwire: the CPU logic check must never enumerate or touch a card (a server owns them).
    torch.xpu.device_count = lambda: 0
    torch.xpu.is_available = lambda: False

    def _trip(name):
        def f(*a, **k):
            raise RuntimeError('probe --cpu: torch.xpu.%s must not be called' % name)
        return f
    for _name in ('synchronize', 'current_device', 'set_device', 'memory_stats', 'get_device_properties',
                  'get_device_name', 'mem_get_info', 'empty_cache', 'is_bf16_supported', 'init', '_lazy_init',
                  'current_stream', 'Stream', 'Event', 'memory_allocated', 'memory_reserved'):
        if hasattr(torch.xpu, _name):
            setattr(torch.xpu, _name, _trip(_name))

torch.set_num_threads(16)
import comfy.options  # noqa: E402
comfy.options.enable_args_parsing()  # without this comfy.cli_args parses [] and every flag above is ignored
import comfy.model_management as mm  # noqa: E402
from comfy.cli_args import args as comfy_args  # noqa: E402
# Comfy's import selects warn_only=True; the server restores strict mode right after it.
torch.use_deterministic_algorithms(True, warn_only=False)
import comfy.sd  # noqa: E402
import comfy.patcher_extension  # noqa: E402
from comfy.patcher_extension import WrappersMP  # noqa: E402
from comfy_extras.nodes_lt import (EmptyLTXVLatentVideo, LTXVConditioning, LTXVConcatAVLatent,  # noqa: E402
                                   LTXVSeparateAVLatent, LTXVDualCFGGuider)
from comfy_extras.nodes_lt_audio import LTXVEmptyLatentAudio  # noqa: E402
from comfy_extras.nodes_custom_sampler import SamplerCustomAdvanced, KSamplerSelect, ManualSigmas, RandomNoise  # noqa: E402

try:
    from comfy.ldm.lightricks.av_model import CompressedTimestep
except Exception:  # noqa: BLE001
    CompressedTimestep = None

assert comfy_args.bf16_unet and comfy_args.use_pytorch_cross_attention and comfy_args.cpu == OPT.cpu, \
    'ComfyUI flags were not parsed'


# ----------------------------------------------------------------------------- model

def load_truncated(path, blocks):
    """First `blocks` transformer blocks + all non-block weights, through ComfyUI's loader."""
    from safetensors import safe_open
    pat = re.compile(r'(?:^|\.)transformer_blocks\.(\d+)\.')
    sd, kept, skipped, kept_bytes, present = {}, 0, 0, 0, set()
    with safe_open(path, framework='pt', device='cpu') as f:
        metadata = dict(f.metadata() or {})
        for k in f.keys():
            m = pat.search(k)
            if m:
                present.add(int(m.group(1)))
                if int(m.group(1)) >= blocks:
                    skipped += 1
                    continue
            t = f.get_tensor(k)
            sd[k] = t
            kept += 1
            kept_bytes += t.numel() * t.element_size()
    assert blocks <= len(present), (blocks, len(present))
    cfg = json.loads(metadata['config'])
    full_layers = cfg['transformer'].get('num_layers')
    cfg['transformer']['num_layers'] = blocks  # the metadata config overrides the counted block number
    metadata['config'] = json.dumps(cfg)
    patcher = comfy.sd.load_diffusion_model_state_dict(sd, model_options={}, metadata=metadata)
    assert patcher is not None, 'ComfyUI did not detect the model'
    left_over = sorted(sd.keys())
    del sd
    dm = patcher.model.diffusion_model
    assert type(patcher.model).__name__ == 'LTXAV', type(patcher.model)
    assert len(dm.transformer_blocks) == blocks, (len(dm.transformer_blocks), blocks)
    params = list(patcher.model.parameters())
    return patcher, {
        'checkpoint': path, 'checkpoint_blocks': len(present), 'checkpoint_num_layers_metadata': full_layers,
        'blocks_kept': blocks, 'tensors_kept': kept, 'tensors_skipped': skipped,
        'kept_bytes': kept_bytes, 'left_over_keys': left_over[:20], 'left_over_count': len(left_over),
        'model_parameter_bytes': sum(p.numel() * p.element_size() for p in params),
        'weight_dtypes': sorted({str(p.dtype) for p in params}),
        'dtype_inference': str(patcher.model.get_dtype_inference()),
        'manual_cast_dtype': str(patcher.model.manual_cast_dtype),
        'load_device': str(patcher.load_device), 'offload_device': str(patcher.offload_device),
        'model_patcher_class': type(patcher).__name__}


# ----------------------------------------------------------------------------- DRM fdinfo (copied from sample-gpu-engine-busy.py)

def drm_snap():
    cards, seen = {}, set()
    for f in glob.glob('/proc/self/fdinfo/*'):
        try:
            kv = dict(l.split(':', 1) for l in open(f).read().splitlines() if ':' in l)
        except OSError:
            continue
        pdev = kv.get('drm-pdev', '').strip()
        cid = kv.get('drm-client-id', '').strip()
        if not pdev or (pdev, cid) in seen:
            continue
        seen.add((pdev, cid))
        c = cards.setdefault(pdev, {'ccs': 0, 'bcs': 0, 'total': 0})
        for eng in ('ccs', 'bcs'):
            c[eng] += int(kv.get(f'drm-cycles-{eng}', '0').split()[0])
        c['total'] = max(c['total'], int(kv.get('drm-total-cycles-ccs', '0').split()[0]))
    return time.perf_counter(), cards


def drm_busy(s0, s1):
    """busy seconds per engine over the interval = delta cycles / delta total cycles x wall."""
    (t0, c0), (t1, c1) = s0, s1
    out = {}
    for pdev, c in c1.items():
        p = c0.get(pdev)
        if not p or c['total'] <= p['total']:
            continue
        dtot = c['total'] - p['total']
        out[pdev] = {e + '_busy_s': (c[e] - p[e]) / dtot * (t1 - t0) for e in ('ccs', 'bcs')}
    if not out:
        return None
    return {'ccs_busy_s': sum(v['ccs_busy_s'] for v in out.values()),
            'bcs_busy_s': sum(v['bcs_busy_s'] for v in out.values()), 'cards': sorted(out)}


# ----------------------------------------------------------------------------- batch stacking
# Generalised from SRC/scripts/concurrent_cfg_node.py (batchproof, packets 66-72): every
# tensor argument with a leading batch dimension of 1 is concatenated over the rows,
# CompressedTimestep is rebuilt around its stacked .data, lists/tuples are walked, dicts are
# NOT walked except transformer_options, where ComfyUI's per-batch lists cond_or_uncond and
# uuids and the per-batch 'sigmas' tensor are extended to the batch (the packet 66 failure).

def stack_tree(values):
    v0 = values[0]
    if isinstance(v0, torch.Tensor):
        if v0.dim() >= 1 and v0.shape[0] == 1:
            return torch.cat(list(values), dim=0)
        return v0
    if CompressedTimestep is not None and isinstance(v0, CompressedTimestep):
        return CompressedTimestep(stack_tree([v.data for v in values]), v0.patches_per_frame, per_frame=True)
    if isinstance(v0, (list, tuple)):
        out = [stack_tree([v[i] for v in values]) for i in range(len(v0))]
        return type(v0)(out) if isinstance(v0, tuple) else out
    return v0


def stack_options(options):
    out = dict(options[0])
    for key in ('cond_or_uncond', 'uuids'):
        if isinstance(out.get(key), list) and len(out[key]) == 1:
            out[key] = [o[key][0] for o in options]
    sig = out.get('sigmas')
    if isinstance(sig, torch.Tensor) and sig.dim() >= 1 and sig.shape[0] == 1:
        out['sigmas'] = torch.cat([o.get('sigmas', sig) for o in options], dim=0)
    return out


def stack_inputs(rows):
    """rows: list of (args, kwargs) of batch-1 forwards -> (args, kwargs) of one batch-k forward."""
    if len(rows) == 1:
        return list(rows[0][0]), dict(rows[0][1])
    args = stack_tree([list(a) for a, _ in rows])
    if len(args) > 5 and isinstance(rows[0][0][5], dict):
        args[5] = stack_options([a[5] for a, _ in rows])
    kwargs = {k: stack_tree([kw[k] for _, kw in rows]) for k in rows[0][1]}
    if isinstance(kwargs.get('transformer_options'), dict):
        kwargs['transformer_options'] = stack_options([kw['transformer_options'] for _, kw in rows])
    return args, kwargs


def census(value, path='arg'):
    out = {}
    if isinstance(value, torch.Tensor):
        out[path] = list(value.shape) + [str(value.dtype), str(value.device)]
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            out.update(census(v, f'{path}[{i}]'))
    elif isinstance(value, dict):
        for k, v in value.items():
            if k in ('patches_replace', 'wrappers', 'callbacks', 'patches'):
                continue
            out.update(census(v, f'{path}.{k}'))
    elif CompressedTimestep is not None and isinstance(value, CompressedTimestep):
        out[path + '<CT>'] = list(value.data.shape)
    elif isinstance(value, (int, float, str, bool)) or value is None:
        out[path] = repr(value)[:80]
    else:
        out[path] = type(value).__name__
    return out


# ----------------------------------------------------------------------------- comparisons (CPU)

def components(out):
    outs = list(out) if isinstance(out, (list, tuple)) else [out]
    return [o.detach().to('cpu', copy=True) for o in outs]


def bits(t):
    if t.dtype in (torch.bfloat16, torch.float16):
        return t.contiguous().view(torch.int16)
    if t.dtype == torch.float32:
        return t.contiguous().view(torch.int32)
    return t


def names(n):
    return ['video', 'audio'][:n] if n <= 2 else [f'c{i}' for i in range(n)]


def eq(a, b):
    """Bitwise check of two component lists (each [1, ...]); per component."""
    res = {}
    for name, x, y in zip(names(len(a)), a, b):
        if x.shape != y.shape:
            res[name] = {'equal': False, 'shape_mismatch': [list(x.shape), list(y.shape)]}
            continue
        ne = bits(x) != bits(y)
        d = (x.double() - y.double()).abs()
        res[name] = {'equal': not bool(ne.any()), 'n_diff': int(ne.sum()), 'numel': x.numel(),
                     'max_abs_diff': float(d.max()) if d.numel() else 0.0}
    return res


def all_equal(r):
    return all(v.get('equal') is True for v in r.values())


def row(comps, i):
    return [c[i:i + 1] for c in comps]


def bf16_ulp(mag):
    mag = mag.clamp_min(2.0 ** -126)
    return torch.exp2(torch.floor(torch.log2(mag)) - 7)


def detail(test, ref):
    """test vs ref (ref = batch-1 output), sized in bf16 spacing at each element's magnitude."""
    res = {}
    for name, x, y in zip(names(len(test)), test, ref):
        if x.shape != y.shape:
            res[name] = {'shape_mismatch': [list(x.shape), list(y.shape)]}
            continue
        xd, yd = x.double(), y.double()
        d = (xd - yd).abs()
        ne = bits(x) != bits(y)
        ulps = d / bf16_ulp(torch.maximum(xd.abs(), yd.abs()))
        res[name] = {'dtype': str(x.dtype), 'equal': not bool(ne.any()),
                     'max_abs_diff': float(d.max()), 'mean_abs_diff': float(d.mean()),
                     'frac_diff': float(ne.double().mean()), 'n_diff': int(ne.sum()), 'numel': x.numel(),
                     'ulps_max': float(ulps.max()), 'ulps_median': float(ulps.median()),
                     'ulps_median_of_differing': float(ulps[ne].median()) if bool(ne.any()) else 0.0,
                     'ref_max_abs': float(yd.abs().max()), 'ref_rms': float(yd.pow(2).mean().sqrt())}
    return res


# ----------------------------------------------------------------------------- the forward wrapper

STATE = {'stage': None, 'fwd_in_stage': 0, 'fwd_total': 0, 'records': [], 'timing': {}, 'contexts': {},
         'census': None, 'dm': None}
VARIANTS = ['B', 'C', 'D', 'E']


def device_sync(device):
    if device.type == 'xpu':
        torch.xpu.synchronize(device)


def first_tensor(value):
    if isinstance(value, torch.Tensor):
        return value
    if isinstance(value, (list, tuple)):
        for v in value:
            t = first_tensor(v)
            if t is not None:
                return t
    return None


def raw_context(index, dim):
    g = torch.Generator(device='cpu').manual_seed(SEED + 1 + index)
    return torch.randn((1, TEXT_TOKENS, dim), generator=g, dtype=torch.float32)


def processed_context(name, like):
    """Variant text context through the model's own connector, as LTXAV.extra_conds does it."""
    if name not in STATE['contexts']:
        dm = STATE['dm']
        dim = dm.cross_attention_dim + dm.audio_cross_attention_dim
        raw = raw_context(1 + VARIANTS.index(name), dim)
        dtype = STATE['patcher'].model.get_dtype_inference()
        ctx = dm.preprocess_text_embeds(raw.to(device=like.device, dtype=dtype), unprocessed=True)
        STATE['contexts'][name] = ctx.to(dtype=like.dtype)
    return STATE['contexts'][name]


def variant(args, kwargs, name):
    """Same-shape inputs of another clip at the same sigma: new latent (args[0]) and new context (args[2])."""
    g = torch.Generator(device='cpu').manual_seed(SEED + 1000 * (STATE['fwd_total'] + 1) + 1 + VARIANTS.index(name))

    def fresh(t):
        if not isinstance(t, torch.Tensor) or not t.is_floating_point():
            return t
        rms = float(t.float().pow(2).mean().sqrt()) or 1.0
        return (torch.randn(t.shape, generator=g, dtype=torch.float32) * rms).to(dtype=t.dtype, device=t.device)

    def walk(v):
        if isinstance(v, torch.Tensor):
            return fresh(v)
        if isinstance(v, (list, tuple)):
            out = [walk(x) for x in v]
            return type(v)(out) if isinstance(v, tuple) else out
        return v

    new = list(args)
    new[0] = walk(args[0])
    new[2] = processed_context(name, args[2])
    return new, dict(kwargs)


def guarded(rec, key, fn):
    try:
        rec[key] = fn()
    except Exception as error:  # noqa: BLE001
        rec[key] = {'error': repr(error)[:400], 'traceback_tail': traceback.format_exc()[-2500:]}
        print(f'  [{key}] FAILED: {error!r}'[:300], flush=True)


def experiments(executor, args, kwargs, out1_comps, rec):
    rows = {'A': (list(args), dict(kwargs))}
    for name in VARIANTS[:max(OPT.batch_sizes)]:
        rows[name] = variant(args, kwargs, name)

    def run(names_):
        a, k = stack_inputs([rows[n] for n in names_])
        with torch.no_grad():
            out = executor(*a, **k)
        comps = components(out)
        del out, a, k
        return comps

    b1 = {'A': out1_comps}
    rec['batch1'] = {}
    guarded(rec['batch1'], 'repeat_A', lambda: eq(run(['A']), out1_comps))
    for n in ('B', 'C'):
        def one(n=n):
            b1[n] = run([n])
            return {'shapes': [list(c.shape) for c in b1[n]]}
        guarded(rec['batch1'], 'out1_' + n, one)
    if 'B' in b1:
        rec['batch1']['scale_reference_A_vs_B'] = detail(b1['B'], b1['A'])

    a_rows = {}
    for k in OPT.batch_sizes:
        r = rec.setdefault('batch', {}).setdefault(str(k), {})
        primary = ['A'] + VARIANTS[:k - 1]                    # (A, B, C, D)[:k]
        neighbour = ['A'] + VARIANTS[1:k]                     # (A, C, D, E)[:k]: every other row changed
        store = {}

        def prim():
            store['p'] = run(primary)
            a_rows[k] = row(store['p'], 0)
            return {'rows': primary, 'shapes': [list(c.shape) for c in store['p']]}
        guarded(r, 'primary', prim)
        if 'p' not in store:
            continue
        p = store['p']
        guarded(r, 'neighbour', lambda: {'rows': neighbour, 'row0': eq(row(run(neighbour), 0), row(p, 0))})

        def slots():
            out = {}
            for j in range(1, k):
                names_ = VARIANTS[:j] + ['A'] + VARIANTS[j:k - 1]
                out[str(j)] = {'rows': names_, 'A': eq(row(run(names_), j), row(p, 0))}
            return out
        guarded(r, 'slot', slots)

        def identical():
            s = run(['A'] * k)
            return {'rows_vs_row0': {str(i): eq(row(s, i), row(s, 0)) for i in range(1, k)},
                    'row0_vs_primary_row0': eq(row(s, 0), row(p, 0)),
                    'row0_vs_batch1': detail(row(s, 0), out1_comps)}
        guarded(r, 'identical', identical)
        guarded(r, 'repeat', lambda: {str(i): eq(row(run(primary), i), row(p, i)) for i in range(k)})
        r['vs_batch1'] = {name: detail(row(p, i), b1[name]) for i, name in enumerate(primary) if name in b1}
        del store['p'], p

    rec['batch_size_dependence'] = {f'{a}_vs_{b}': eq(a_rows[a], a_rows[b])
                                    for a in sorted(a_rows) for b in sorted(a_rows) if a < b}
    del rows


def timing(executor, args, kwargs, rec):
    device = first_tensor(args[0]).device
    rows = [(list(args), dict(kwargs))] + [variant(args, kwargs, n) for n in VARIANTS[:3]]
    res = {}
    for k in sorted({1, 2, 3, 4} | set(OPT.batch_sizes)):
        try:
            a, kw = stack_inputs(rows[:k])
            with torch.no_grad():
                for _ in range(WARMUP):
                    out = executor(*a, **kw)
                    device_sync(device)
                    del out
                walls, busy = [], []
                for _ in range(TIMED):
                    device_sync(device)
                    s0 = drm_snap()
                    t0 = time.perf_counter()
                    out = executor(*a, **kw)
                    device_sync(device)
                    t1 = time.perf_counter()
                    s1 = drm_snap()
                    del out
                    walls.append(t1 - t0)
                    busy.append(drm_busy(s0, s1))
            del a, kw
            ccs = [b['ccs_busy_s'] for b in busy if b] if all(busy) else None
            res[str(k)] = {'wall_s': walls, 'wall_median_s': statistics.median(walls),
                           'ccs_busy_s': ccs, 'ccs_busy_median_s': statistics.median(ccs) if ccs else None,
                           'bcs_busy_median_s': statistics.median([b['bcs_busy_s'] for b in busy]) if ccs else None,
                           'drm_cards': busy[0]['cards'] if ccs else None}
        except Exception as error:  # noqa: BLE001
            res[str(k)] = {'error': repr(error)[:400], 'traceback_tail': traceback.format_exc()[-2500:]}
            print(f'  [timing batch {k}] FAILED: {error!r}'[:300], flush=True)
    base = res.get('1', {})
    for k, v in res.items():
        if 'error' in v:
            continue
        kk = int(k)
        v['per_clip_wall_s'] = v['wall_median_s'] / kk
        if base.get('wall_median_s'):
            v['per_clip_wall_ratio_to_batch1'] = v['per_clip_wall_s'] / base['wall_median_s']
        if v.get('ccs_busy_median_s') is not None:
            v['per_clip_ccs_busy_s'] = v['ccs_busy_median_s'] / kk
            if base.get('ccs_busy_median_s'):
                v['per_clip_ccs_busy_ratio_to_batch1'] = v['per_clip_ccs_busy_s'] / base['ccs_busy_median_s']
    rec.update(res)


def probe_wrapper(executor, *args, **kwargs):
    out1 = executor(*args, **kwargs)
    stage, idx = STATE['stage'], STATE['fwd_in_stage']
    STATE['fwd_in_stage'] += 1
    if STATE['census'] is None:
        STATE['census'] = {**census(list(args), 'args'), **census(dict(kwargs), 'kwargs')}
    if OPT.forwards == 'all' or idx == 0:
        rec = {'stage': stage, 'forward_in_stage': idx, 'forward_index': STATE['fwd_total'],
               'census': {**census(list(args), 'args'), **census(dict(kwargs), 'kwargs')}}
        sig = (args[5] if len(args) > 5 and isinstance(args[5], dict) else {}).get('sigmas')
        rec['sigma'] = [float(s) for s in sig.flatten()] if isinstance(sig, torch.Tensor) else None
        print(f'stage {stage} forward {idx}: sigma {rec["sigma"]}', flush=True)
        t = time.time()
        try:
            out1_comps = components(out1)
            experiments(executor, args, kwargs, out1_comps, rec)
        except Exception as error:  # noqa: BLE001
            rec['error'] = repr(error)[:400]
            rec['traceback_tail'] = traceback.format_exc()[-2500:]
            print(f'  experiments FAILED: {error!r}'[:300], flush=True)
        rec['experiment_seconds'] = time.time() - t
        STATE['records'].append(rec)
        if idx == 0 and not OPT.skip_timing:
            tr = STATE['timing'].setdefault(stage, {'census': rec['census']})
            try:
                timing(executor, args, kwargs, tr)
            except Exception as error:  # noqa: BLE001
                tr['error'] = repr(error)[:400]
                tr['traceback_tail'] = traceback.format_exc()[-2500:]
        write_result(partial=True)
    STATE['fwd_total'] += 1
    return out1


# ----------------------------------------------------------------------------- sampling

class StubAudioVAE:
    """Only the latent geometry LTXVEmptyLatentAudio reads (the audio VAE itself is not loaded)."""
    latent_channels = AUDIO_CHANNELS

    class first_stage_model:  # noqa: N801
        latent_frequency_bins = AUDIO_FREQ

        @staticmethod
        def num_of_latents_from_frames(frames_number, frame_rate):
            assert (frames_number, float(frame_rate)) == (LENGTH, FRAME_RATE)
            return AUDIO_LATENTS


def sample_stage(name, patcher, positive, negative, sigmas_text, latent):
    STATE['stage'], STATE['fwd_in_stage'] = name, 0
    guider = LTXVDualCFGGuider.execute(model=patcher, positive=positive, negative=negative,
                                       video_cfg=CFG, audio_cfg=CFG).result[0]
    noise = RandomNoise.execute(noise_seed=NOISE_SEED).result[0]
    sampler = KSamplerSelect.execute(sampler_name=SAMPLER).result[0]
    sigmas = ManualSigmas.execute(sigmas=sigmas_text).result[0]
    out = SamplerCustomAdvanced.execute(noise=noise, guider=guider, sampler=sampler, sigmas=sigmas,
                                        latent_image=latent).result[0]
    return out, STATE['fwd_in_stage']


RESULT = {}


def write_result(partial=False):
    RESULT.update(records=STATE['records'], timing=STATE['timing'], first_forward_census=STATE['census'],
                  partial=partial)
    tmp = OUT + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(RESULT, f, indent=1)
    os.replace(tmp, OUT)


def verdicts():
    out = {}
    for k in OPT.batch_sizes:
        flags = {'neighbour': [], 'slot': [], 'identical': [], 'repeat': [], 'batch1_equal': []}
        errors = 0
        for rec in STATE['records']:
            r = rec.get('batch', {}).get(str(k))
            if not r:
                errors += 1
                continue

            def ok(v, path):
                if not isinstance(v, dict) or 'error' in v:
                    return None
                for p in path:
                    v = v[p]
                return all_equal(v)
            for key, val in (('neighbour', ok(r.get('neighbour'), ['row0'])),
                             ('identical', None if 'error' in r.get('identical', {'error': 1}) else
                              all(all_equal(v) for v in r['identical']['rows_vs_row0'].values())),
                             ('repeat', None if 'error' in r.get('repeat', {'error': 1}) else
                              all(all_equal(v) for v in r['repeat'].values())),
                             ('slot', None if 'error' in r.get('slot', {'error': 1}) else
                              all(all_equal(v['A']) for v in r['slot'].values())),
                             ('batch1_equal', None if 'vs_batch1' not in r else
                              all(all_equal(v) for v in r['vs_batch1'].values()))):
                if val is None:
                    errors += 1
                else:
                    flags[key].append(val)
        summary = {key: (all(v) if v else None) for key, v in flags.items()}
        summary['forwards_checked'] = len(flags['neighbour'])
        summary['errors'] = errors
        summary['row_independent'] = (all(summary[x] is True for x in ('neighbour', 'slot', 'identical', 'repeat'))
                                      and errors == 0)
        maxdiff = [c['max_abs_diff'] for rec in STATE['records']
                   for c in rec.get('batch', {}).get(str(k), {}).get('vs_batch1', {}).get('A', {}).values()
                   if 'max_abs_diff' in c]
        summary['max_abs_diff_vs_batch1_A'] = max(maxdiff) if maxdiff else None
        out[str(k)] = summary
    return out


def main():
    started = time.time()
    device = mm.get_torch_device()
    device_name = None if device.type == 'cpu' else torch.xpu.get_device_name(device)
    RESULT.update({'schema': SCHEMA, 'started_unix': started, 'device': str(device), 'device_name': device_name,
                   'ze_affinity_mask': os.environ.get('ZE_AFFINITY_MASK'), 'torch': torch.__version__,
                   'packet_source': SRC, 'comfy_args': COMFY_ARGS,
                   'deterministic': {'enabled': torch.are_deterministic_algorithms_enabled(),
                                     'warn_only': torch.is_deterministic_algorithms_warn_only_enabled()},
                   'options': {'blocks': OPT.blocks, 'batches': OPT.batch_sizes, 'forwards': OPT.forwards,
                               'cpu': OPT.cpu, 'skip_timing': OPT.skip_timing},
                   'seeds': {'base': SEED, 'noise': NOISE_SEED, 'context_A': SEED + 1,
                             'context_variants': {n: SEED + 2 + i for i, n in enumerate(VARIANTS)},
                             'variant_latent': 'SEED + 1000*(forward_index+1) + 1 + variant_index',
                             'stage2_video_latent': SEED + 7},
                   'workflow': {'width_height_stage1': [WIDTH, HEIGHT], 'length': LENGTH, 'frame_rate': FRAME_RATE,
                                'sampler': SAMPLER, 'sigmas_stage1': SIGMAS_STAGE1, 'sigmas_stage2': SIGMAS_STAGE2,
                                'cfg': CFG, 'noise_seed': NOISE_SEED, 'text_tokens': TEXT_TOKENS,
                                'stage2_driver': 'seeded random video latent %s (no latent upsampler) + stage-1 '
                                                 'audio output' % (list(STAGE2_VIDEO_SHAPE),),
                                'audio_latent': 'LTXVEmptyLatentAudio with a stub audio VAE: [1, %d, %d, %d]'
                                                % (AUDIO_CHANNELS, AUDIO_LATENTS, AUDIO_FREQ),
                                'text_conditioning': 'seeded random fp32 [1, %d, cross+audio_cross dims], '
                                                     'unprocessed_ltxav_embeds=True' % TEXT_TOKENS},
                   'method': {'lockstep': 'variant rows differ from A only in the latent (args[0], seeded randn '
                                          'scaled to the RMS of A\'s component) and the text context (args[2], '
                                          'seeded raw context through the model connector); timestep, '
                                          'a_timestep, sigmas and everything else are A\'s',
                              'stacking': 'tensors with leading dim 1 in args/kwargs concatenated (args[0] '
                                          'video+audio list, args[1] timestep, args[2] context, '
                                          'kwargs a_timestep); transformer_options: cond_or_uncond, uuids, '
                                          'sigmas extended; other dict entries shared',
                              'timing_note': 'eager wall time includes Python dispatch; drm ccs busy seconds '
                                             '(this process, /proc/self/fdinfo) are the GPU cost that matters',
                              'warmup': WARMUP, 'timed': TIMED}})
    print(f'device {device} {device_name or ""}; loading {OPT.blocks} blocks from {OPT.checkpoint}', flush=True)
    t = time.time()
    patcher, load_info = load_truncated(OPT.checkpoint, OPT.blocks)
    load_info['seconds'] = time.time() - t
    RESULT['model'] = load_info
    dm = patcher.model.diffusion_model
    STATE['dm'], STATE['patcher'] = dm, patcher
    text_dim = dm.cross_attention_dim + dm.audio_cross_attention_dim
    RESULT['workflow']['text_dim'] = text_dim
    print(f'loaded in {load_info["seconds"]:.0f} s: {json.dumps({k: load_info[k] for k in ("blocks_kept", "tensors_skipped", "model_parameter_bytes", "dtype_inference")})}', flush=True)

    patcher.add_wrapper_with_key(WrappersMP.DIFFUSION_MODEL, 'ltx_batch_row_probe', probe_wrapper)

    cond = [[raw_context(0, text_dim), {'pooled_output': None, 'unprocessed_ltxav_embeds': True}]]
    positive, negative = LTXVConditioning.execute(positive=cond, negative=cond, frame_rate=FRAME_RATE).result[:2]
    video = EmptyLTXVLatentVideo.execute(width=WIDTH, height=HEIGHT, length=LENGTH, batch_size=1).result[0]
    audio = LTXVEmptyLatentAudio.execute(frames_number=LENGTH, frame_rate=FRAME_RATE, batch_size=1,
                                         audio_vae=StubAudioVAE).result[0]
    av = LTXVConcatAVLatent.execute(video_latent=video, audio_latent=audio).result[0]

    stage_info = {}
    with torch.no_grad():
        try:
            out_a, n_a = sample_stage('stage1', patcher, positive, negative, SIGMAS_STAGE1, av)
            stage_info['stage1'] = {'forwards': n_a}
            _video_a, audio_a = LTXVSeparateAVLatent.execute(av_latent=out_a).result[:2]
            g = torch.Generator(device='cpu').manual_seed(SEED + 7)
            video_b = {'samples': torch.randn(STAGE2_VIDEO_SHAPE, generator=g, dtype=torch.float32)
                       .to(mm.intermediate_device())}
            av2 = LTXVConcatAVLatent.execute(video_latent=video_b, audio_latent=audio_a).result[0]
            out_b, n_b = sample_stage('stage2', patcher, positive, negative, SIGMAS_STAGE2, av2)
            stage_info['stage2'] = {'forwards': n_b}
            v_s, a_s = out_b['samples'].unbind()[:2]
            stage_info['final_finite'] = bool(torch.isfinite(v_s).all()) and bool(torch.isfinite(a_s).all())
            import hashlib
            stage_info['final_sha256'] = {n: hashlib.sha256(t.detach().to('cpu', copy=True).contiguous().view(torch.uint8)
                                                            .numpy().tobytes()).hexdigest()
                                          for n, t in (('video', v_s), ('audio', a_s))}
        except Exception as error:  # noqa: BLE001
            stage_info['error'] = repr(error)[:400]
            stage_info['traceback_tail'] = traceback.format_exc()[-3000:]
            print('SAMPLING FAILED: ' + repr(error)[:300], flush=True)
    RESULT['sampling'] = stage_info
    RESULT['verdicts'] = verdicts()
    RESULT['seconds'] = time.time() - started
    write_result(partial=False)

    print('\n== batch row independence (%d blocks, forwards=%s, device %s) ==' % (OPT.blocks, OPT.forwards, device))
    print('sampling:', json.dumps({k: v for k, v in stage_info.items() if k != 'traceback_tail'}))
    for rec in STATE['records']:
        ref = rec.get('batch1', {}).get('scale_reference_A_vs_B', {})
        rep = rec.get('batch1', {}).get('repeat_A', {})
        line = f"{rec['stage']} f{rec['forward_in_stage']}: batch1 repeat {all_equal(rep) if 'error' not in rep else 'ERR'}"
        for name, c in ref.items():
            line += f"; A-vs-B {name} max {c['max_abs_diff']:.3g} (|A| max {c['ref_max_abs']:.3g}, rms {c['ref_rms']:.3g})"
        print(line)
        for k, r in rec.get('batch', {}).items():
            for name, c in r.get('vs_batch1', {}).get('A', {}).items():
                if 'max_abs_diff' in c:
                    print(f"   batch {k} A-row vs batch1 {name}: max {c['max_abs_diff']:.3g} mean {c['mean_abs_diff']:.3g} "
                          f"frac {c['frac_diff']:.3f} ulps max {c['ulps_max']:.1f} median {c['ulps_median']:.1f}")
    for stage, tr in STATE['timing'].items():
        print(f'timing {stage}:')
        for k in sorted((x for x in tr if x.isdigit()), key=int):
            v = tr[k]
            if 'error' in v:
                print(f'   batch {k}: ERROR {v["error"][:120]}')
                continue
            busy = (f"ccs busy {v['ccs_busy_median_s'] * 1e3:.1f} ms/fwd, {v['per_clip_ccs_busy_s'] * 1e3:.1f} ms/clip "
                    f"(x{v.get('per_clip_ccs_busy_ratio_to_batch1', float('nan')):.2f})"
                    if v.get('ccs_busy_median_s') is not None else 'ccs busy n/a')
            print(f"   batch {k}: wall {v['wall_median_s'] * 1e3:.1f} ms/fwd, {v['per_clip_wall_s'] * 1e3:.1f} ms/clip "
                  f"(x{v.get('per_clip_wall_ratio_to_batch1', float('nan')):.2f}); {busy}")
    print('(eager wall includes Python dispatch; the ccs busy counter is the GPU cost that matters)')
    for k, s in RESULT['verdicts'].items():
        yn = lambda b: 'yes' if b is True else ('no' if b is False else 'n/a')  # noqa: E731
        print(f"batch {k}: row-independent: {yn(s['row_independent'])} (neighbour {yn(s['neighbour'])}, "
              f"slot {yn(s['slot'])}, identical {yn(s['identical'])}, repeat {yn(s['repeat'])}); "
              f"equal to batch1: {yn(s['batch1_equal'])}; forwards {s['forwards_checked']}, errors {s['errors']}")
    print('wrote', OUT)


if __name__ == '__main__':
    main()
