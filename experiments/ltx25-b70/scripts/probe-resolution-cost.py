#!/usr/bin/env python3
"""Diagnostic resolution scaling, batch 1, eager, one explicitly selected idle XPU.

ZE_AFFINITY_MASK=<card> python -B probe-resolution-cost.py <out.json> \
    [--blocks 12] [--sizes 256x256,512x320,640x384] [--skip-decode]

Never run alongside a GPU campaign. No server or packet custom nodes are started.
Only main() imports torch/ComfyUI or reads weights; --help and importing this
file are safe without a device. Bytecode writes are disabled even without -B.
The truncated transformer and synthetic inputs are cost diagnostics, not a
quality gate, full-model prediction, or end-to-end clip throughput measurement.
"""

import argparse
import gc
import glob
import json
import os
from pathlib import Path
import re
import statistics
import sys
import time
import traceback
from types import SimpleNamespace

sys.dont_write_bytecode = True

PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-workers-95')
SRC = PACKET / 'source'
MODEL_ROOT = Path('/mnt/fast-ai/llm-models/LTX-2.5-baseline')
CKPT = MODEL_ROOT / 'diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors'
SCHEMA = 'ltx.resolution-cost-probe.v1'
LENGTH, FRAME_RATE = 25, 24.0
TEXT_TOKENS, CONTEXT_TOKENS = 35, 1024
AUDIO_SHAPE = [1, 8, 26, 16]
SEED, NOISE_SEED = 20261004, 42
WARMUP, TIMED = 2, 6
SIGMAS_STAGE1 = '1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0'
SIGMAS_STAGE2 = '0.85, 0.7250, 0.4219, 0.0'
COMFY_ARGS = [
    '--cache-none', '--deterministic', '--disable-async-offload', '--disable-dynamic-vram',
    '--disable-comfy-compiler', '--disable-cuda-graphs', '--disable-pinned-memory',
    '--reserve-vram', '2', '--bf16-unet', '--bf16-text-enc', '--bf16-vae',
    '--use-pytorch-cross-attention', '--disable-xformers', '--disable-api-nodes',
]


def parse_sizes(value):
    sizes = []
    for item in value.split(','):
        match = re.fullmatch(r'(\d+)x(\d+)', item.strip())
        if not match:
            raise argparse.ArgumentTypeError('sizes must be comma-separated WIDTHxHEIGHT')
        width, height = map(int, match.groups())
        if min(width, height) < 128 or width % 64 or height % 64:
            raise argparse.ArgumentTypeError('output dimensions must be multiples of 64 and at least 128')
        if (width, height) not in sizes:
            sizes.append((width, height))
    # Always measure the named denominator, even with a custom --sizes list.
    return [(256, 256)] + [size for size in sizes if size != (256, 256)]


def shape_record(width, height):
    stages = {}
    for name, divisor in (('stage1', 2), ('stage2', 1)):
        w, h = width // divisor, height // divisor
        shape = [1, 128, (LENGTH - 1) // 8 + 1, h // 32, w // 32]
        stages[name] = {
            'width': w, 'height': h, 'video_latent_shape': shape,
            'video_tokens': shape[2] * shape[3] * shape[4],
            'audio_latent_shape': list(AUDIO_SHAPE), 'audio_tokens': 26,
            'text_context_tokens': CONTEXT_TOKENS,
        }
    return {'width': width, 'height': height, 'stages': stages}


def initialize_runtime():
    # Copied setup from probe-batch-row-independence.py. Keep packet imports
    # behind main(): even importing model_management selects a device.
    for key, value in (('OMP_NUM_THREADS', '16'), ('MKL_NUM_THREADS', '16'),
                       ('TOKENIZERS_PARALLELISM', 'false'), ('HF_HUB_OFFLINE', '1')):
        os.environ.setdefault(key, value)
    # folder_paths creates this directory at import if missing. Refuse that
    # write into the sealed tree; no chdir or custom-node initialization either.
    if not (SRC / 'input').is_dir():
        raise RuntimeError('sealed source/input is missing; refusing an import that would create it')
    sys.argv = [str(SRC / 'main.py')] + COMFY_ARGS
    sys.path.insert(0, str(SRC))
    import torch
    torch.set_num_threads(16)
    import comfy.options
    comfy.options.enable_args_parsing()
    import comfy.model_management as mm
    from comfy.cli_args import args
    torch.use_deterministic_algorithms(True, warn_only=False)
    import comfy.sd
    from comfy.patcher_extension import WrappersMP
    import comfy_extras.nodes_lt as lt
    import comfy_extras.nodes_lt_audio as audio
    import comfy_extras.nodes_custom_sampler as sampler
    import nodes
    import folder_paths
    assert args.bf16_unet and args.bf16_vae and args.use_pytorch_cross_attention and not args.cpu
    device = mm.get_torch_device()
    if device.type != 'xpu' or torch.xpu.device_count() != 1:
        raise RuntimeError('select exactly one idle XPU using ZE_AFFINITY_MASK')
    return SimpleNamespace(torch=torch, mm=mm, lt=lt, audio=audio, sampler=sampler,
                           nodes=nodes, folder_paths=folder_paths, wrappers=WrappersMP, device=device)


def load_truncated(path, blocks):
    """Copied from the batch probe: skip dropped weights before get_tensor()."""
    from safetensors import safe_open
    import comfy.sd
    pat = re.compile(r'(?:^|\.)transformer_blocks\.(\d+)\.')
    sd, kept, skipped, kept_bytes, present = {}, 0, 0, 0, set()
    with safe_open(str(path), framework='pt', device='cpu') as f:
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
    cfg['transformer']['num_layers'] = blocks
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
        'checkpoint': str(path), 'checkpoint_blocks': len(present),
        'checkpoint_num_layers_metadata': full_layers, 'blocks_kept': blocks,
        'tensors_kept': kept, 'tensors_skipped': skipped, 'kept_bytes': kept_bytes,
        'left_over_keys': left_over[:20], 'left_over_count': len(left_over),
        'model_parameter_bytes': sum(p.numel() * p.element_size() for p in params),
        'weight_dtypes': sorted({str(p.dtype) for p in params}),
        'dtype_inference': str(patcher.model.get_dtype_inference()),
        'manual_cast_dtype': str(patcher.model.manual_cast_dtype),
        'load_device': str(patcher.load_device), 'offload_device': str(patcher.offload_device),
        'model_patcher_class': type(patcher).__name__,
    }


def drm_snap():
    """Same counter parsing and client deduplication as the batch probe."""
    cards, seen = {}, set()
    for f in glob.glob('/proc/self/fdinfo/*'):
        try:
            with open(f) as stream:
                kv = dict(line.split(':', 1) for line in stream.read().splitlines() if ':' in line)
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
    """delta cycles / delta total cycles * elapsed wall seconds (batch probe)."""
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


def measure(r, call):
    """Time a forward/decode; release every output before the next invocation."""
    walls, busy = [], []
    with r.torch.no_grad():
        for _ in range(WARMUP):
            out = call()
            r.torch.xpu.synchronize(r.device)
            del out
        for _ in range(TIMED):
            r.torch.xpu.synchronize(r.device)
            s0 = drm_snap()
            t0 = time.perf_counter()
            out = call()
            r.torch.xpu.synchronize(r.device)
            t1 = time.perf_counter()
            s1 = drm_snap()
            del out
            walls.append(t1 - t0)
            busy.append(drm_busy(s0, s1))
    valid = all(b is not None and b['ccs_busy_s'] >= 0 and b['bcs_busy_s'] >= 0 for b in busy)
    ccs = [b['ccs_busy_s'] for b in busy] if valid else None
    return {'wall_s': walls, 'wall_median_s': statistics.median(walls),
            'drm_samples': busy, 'ccs_busy_s': ccs,
            'ccs_busy_median_s': statistics.median(ccs) if ccs is not None else None,
            'bcs_busy_median_s': statistics.median([b['bcs_busy_s'] for b in busy]) if valid else None}


class StubAudioVAE:
    """Geometry only, as in the batch probe; no audio weights needed to sample."""
    latent_channels = 8

    class first_stage_model:
        latent_frequency_bins = 16

        @staticmethod
        def num_of_latents_from_frames(frames_number, frame_rate):
            assert (frames_number, float(frame_rate)) == (LENGTH, FRAME_RATE)
            return 26


def random_latent(r, shape, seed):
    generator = r.torch.Generator(device='cpu').manual_seed(seed)
    return {'samples': r.torch.randn(shape, generator=generator, dtype=r.torch.float32)
            .to(r.mm.intermediate_device())}


def sample_stage(r, patcher, positive, negative, sigmas_text, latent):
    guider = r.lt.LTXVDualCFGGuider.execute(model=patcher, positive=positive, negative=negative,
                                          video_cfg=1.0, audio_cfg=1.0).result[0]
    noise = r.sampler.RandomNoise.execute(noise_seed=NOISE_SEED).result[0]
    sampler = r.sampler.KSamplerSelect.execute(sampler_name='euler_ancestral').result[0]
    sigmas = r.sampler.ManualSigmas.execute(sigmas=sigmas_text).result[0]
    return r.sampler.SamplerCustomAdvanced.execute(
        noise=noise, guider=guider, sampler=sampler, sigmas=sigmas, latent_image=latent).result[0]


def sample_size(r, patcher, row, state):
    dm = patcher.model.diffusion_model
    generator = r.torch.Generator(device='cpu').manual_seed(SEED + 1)
    context = r.torch.randn((1, TEXT_TOKENS, dm.cross_attention_dim + dm.audio_cross_attention_dim),
                            generator=generator, dtype=r.torch.float32)
    cond = [[context, {'pooled_output': None, 'unprocessed_ltxav_embeds': True}]]
    positive, negative = r.lt.LTXVConditioning.execute(
        positive=cond, negative=cond, frame_rate=FRAME_RATE).result[:2]
    first = row['stages']['stage1']
    video = r.lt.EmptyLTXVLatentVideo.execute(
        width=first['width'], height=first['height'], length=LENGTH, batch_size=1).result[0]
    assert list(video['samples'].shape) == first['video_latent_shape']
    audio = r.audio.LTXVEmptyLatentAudio.execute(
        frames_number=LENGTH, frame_rate=FRAME_RATE, batch_size=1, audio_vae=StubAudioVAE).result[0]
    assert list(audio['samples'].shape) == AUDIO_SHAPE
    latent = r.lt.LTXVConcatAVLatent.execute(video_latent=video, audio_latent=audio).result[0]
    for name, sigmas in (('stage1', SIGMAS_STAGE1), ('stage2', SIGMAS_STAGE2)):
        state['stage'], state['forwards'] = row['stages'][name], 0
        out = sample_stage(r, patcher, positive, negative, sigmas, latent)
        state['stage']['sampler_forwards'] = state['forwards']
        if name == 'stage1':
            _, audio_next = r.lt.LTXVSeparateAVLatent.execute(av_latent=out).result[:2]
            video_next = random_latent(r, row['stages']['stage2']['video_latent_shape'], SEED + 7)
            latent = r.lt.LTXVConcatAVLatent.execute(
                video_latent=video_next, audio_latent=audio_next).result[0]
        del out
    row['sampling_status'] = 'ok'


def record_error(row, error):
    row.update(error=repr(error), traceback_tail=traceback.format_exc()[-4000:])
    print('FAILED:', repr(error)[:250], flush=True)
    # Do not continue submitting work to a lost device. OOMs remain per-size.
    if re.search(r'device.lost|device.hung|fault response|engine reset|UR_RESULT_ERROR_DEVICE',
                 str(error), re.IGNORECASE):
        raise error


def release_tensors(r):
    gc.collect()
    r.torch.xpu.synchronize(r.device)
    r.torch.xpu.empty_cache()


def run_transformer(r, result, blocks, save):
    patcher, result['model'] = load_truncated(CKPT, blocks)
    state = {}

    def wrapper(executor, *args, **kwargs):
        stage = state['stage']
        index = state['forwards']
        state['forwards'] += 1
        if index == 0:
            stage['observed_video_latent_shape'] = list(args[0][0].shape)
            stage['observed_audio_latent_shape'] = list(args[0][1].shape)
            stage['observed_context_shape'] = list(args[2].shape)
            assert stage['observed_video_latent_shape'] == stage['video_latent_shape']
            assert stage['observed_audio_latent_shape'] == AUDIO_SHAPE
            assert args[2].shape[1] == CONTEXT_TOKENS
            timing = measure(r, lambda: executor(*args, **kwargs))
            for metric in ('wall', 'ccs_busy'):
                seconds = timing[metric + '_median_s']
                timing[metric + '_ms_per_forward_per_block'] = (
                    seconds * 1000 / blocks if seconds is not None else None)
            stage['timing'] = timing
        return executor(*args, **kwargs)

    patcher.add_wrapper_with_key(r.wrappers.DIFFUSION_MODEL, 'ltx_resolution_cost_probe', wrapper)
    try:
        for key, row in result['sizes'].items():
            print('sampling', key, flush=True)
            r.torch.xpu.reset_peak_memory_stats(r.device)
            try:
                with r.torch.no_grad():
                    sample_size(r, patcher, row, state)
            except Exception as error:
                row['sampling_status'] = 'error'
                record_error(row, error)
            finally:
                row['sampling_peak_device_memory_bytes'] = r.torch.xpu.max_memory_allocated(r.device)
                state.clear()
                save()
            release_tensors(r)
    finally:
        # Only this process's loaded models; no external server is contacted.
        r.mm.unload_all_models()


def load_vaes(r, result):
    # pipeline_decode_node.decode_clip calls VAEDecode and LTXVAudioVAEDecode.
    # ltx_decode_replica copies these VAEs; do NOT import its placement/thread
    # machinery. Native VAELoader uses load_torch_file(return_metadata=True),
    # comfy.sd.VAE(sd=sd, metadata=metadata), then throw_exception_if_invalid().
    r.folder_paths.add_model_folder_path('vae', str(MODEL_ROOT / 'vae'), is_default=True)
    vaes = []
    for kind in ('video', 'audio'):
        filename = f'ltx-2.5-{kind}-vae-bf16.safetensors'
        vae = r.nodes.VAELoader().load_vae(filename)[0]
        assert vae.vae_dtype == r.torch.bfloat16, (kind, vae.vae_dtype)
        assert vae.device == r.device, (kind, vae.device, r.device)
        result.setdefault('vaes', {})[kind] = {
            'checkpoint': str(MODEL_ROOT / 'vae' / filename), 'dtype': str(vae.vae_dtype),
            'device': str(vae.device), 'output_device': str(vae.output_device),
        }
        # Native VAE.decode silently retries OOM with tiling. Reject that
        # fallback, so a changed decode method cannot masquerade as scaling.
        def reject_tiled(*args, **kwargs):
            raise RuntimeError('non-tiled VAE decode ran out of memory; tiled fallback excluded')
        for method in ('decode_tiled_1d', 'decode_tiled_', 'decode_tiled_3d', '_decode_tiled_owned'):
            setattr(vae, method, reject_tiled)
        vaes.append(vae)
    r.mm.load_models_gpu([v.patcher for v in vaes], force_full_load=True)
    return vaes


def decode_video_size(r, vae, row):
    latent = random_latent(r, row['stages']['stage2']['video_latent_shape'], SEED + 7)
    return measure(r, lambda: r.nodes.VAEDecode().decode(vae, latent))


def decode_audio(r, vae):
    latent = random_latent(r, AUDIO_SHAPE, SEED + 8)
    return measure(r, lambda: r.audio.LTXVAudioVAEDecode.execute(samples=latent, audio_vae=vae).result[0])


def run_decode(r, result, save):
    video_vae, audio_vae = load_vaes(r, result)
    try:
        for key, row in result['sizes'].items():
            print('video decode', key, flush=True)
            record = row.setdefault('video_decode', {})
            r.torch.xpu.reset_peak_memory_stats(r.device)
            try:
                record.update(decode_video_size(r, video_vae, row), status='ok')
            except Exception as error:
                record['status'] = 'error'
                record_error(record, error)
            finally:
                record['peak_device_memory_bytes'] = r.torch.xpu.max_memory_allocated(r.device)
                save()
            release_tensors(r)
        record = result.setdefault('audio_decode', {'latent_shape': list(AUDIO_SHAPE)})
        r.torch.xpu.reset_peak_memory_stats(r.device)
        try:
            record.update(decode_audio(r, audio_vae), status='ok')
        except Exception as error:
            record['status'] = 'error'
            record_error(record, error)
        finally:
            record['peak_device_memory_bytes'] = r.torch.xpu.max_memory_allocated(r.device)
            save()
    finally:
        r.mm.unload_all_models()


def add_ratios(result):
    base = result['sizes']['256x256']
    caveats = result['caveats']
    for section in ('stage1', 'stage2', 'video_decode'):
        def get(row):
            if section == 'video_decode':
                return row.get(section, {})
            return row['stages'][section].get('timing', {})
        reference = get(base)
        busy_ratios = []
        for key, row in result['sizes'].items():
            measured = get(row)
            for metric in ('wall', 'ccs_busy'):
                value, denominator = measured.get(metric + '_median_s'), reference.get(metric + '_median_s')
                ratio = value / denominator if value is not None and denominator and denominator > 0 else None
                if measured:
                    measured[metric + '_ratio_to_256x256'] = ratio
                if metric == 'ccs_busy' and key != '256x256' and ratio is not None:
                    busy_ratios.append(ratio)
            if measured.get('wall_median_s') is not None and measured.get('ccs_busy_median_s') in (None, 0):
                caveats.append(f'{key} {section}: compute busy counters missing/zero; GPU cost is inconclusive.')
        if busy_ratios and all(abs(ratio - 1) <= 0.10 for ratio in busy_ratios):
            caveats.append(f'{section}: compute busy time also looks flat (all available larger-size '
                           'ratios within 10% of 256x256); this does not prove resolution is free.')
    result['caveats'] = list(dict.fromkeys(caveats))


def print_table(result):
    def fmt(value):
        return '-' if value is None else f'{value:.3f}'
    print('\nsize       operation  tokens  wall ms/block  busy ms/block  wall x  busy x')
    for key, row in result['sizes'].items():
        for name, stage in row['stages'].items():
            timing = stage.get('timing', {})
            print(f"{key:10} {name:10} {stage['video_tokens']:6}  "
                  f"{fmt(timing.get('wall_ms_per_forward_per_block')):>13}  "
                  f"{fmt(timing.get('ccs_busy_ms_per_forward_per_block')):>13}  "
                  f"{fmt(timing.get('wall_ratio_to_256x256')):>6}  "
                  f"{fmt(timing.get('ccs_busy_ratio_to_256x256')):>6}")
    if not result['skip_decode']:
        print('\nsize       decode  wall s  busy s  wall x  busy x  peak GiB')
        rows = [(key, 'video', row.get('video_decode', {})) for key, row in result['sizes'].items()]
        rows.append(('all sizes', 'audio', result.get('audio_decode', {})))
        for key, kind, timing in rows:
            peak = timing.get('peak_device_memory_bytes')
            print(f"{key:10} {kind:6}  {fmt(timing.get('wall_median_s')):>6}  "
                  f"{fmt(timing.get('ccs_busy_median_s')):>6}  "
                  f"{fmt(timing.get('wall_ratio_to_256x256')):>6}  "
                  f"{fmt(timing.get('ccs_busy_ratio_to_256x256')):>6}  "
                  f"{fmt(peak / 2**30 if peak is not None else None):>8}")
    print('Eager wall includes Python dispatch; compute-engine busy time is the GPU cost that matters.')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('out', type=Path)
    parser.add_argument('--blocks', type=int, default=12)
    parser.add_argument('--sizes', type=parse_sizes, default='256x256,512x320,640x384')
    parser.add_argument('--skip-decode', action='store_true')
    opt = parser.parse_args()
    if opt.blocks < 1:
        parser.error('--blocks must be positive')
    affinity = os.environ.get('ZE_AFFINITY_MASK', '')
    if not re.fullmatch(r'\d+(?:\.\d+)?', affinity):
        parser.error('ZE_AFFINITY_MASK must select one idle card before running this probe')
    out = opt.out.resolve()
    if any(p.name.startswith('prepared-') for p in (out, *out.parents)):
        parser.error('output must be outside all prepared-* sealed packets')
    if not out.parent.is_dir() or out.exists() or Path(str(out) + '.tmp').exists():
        parser.error('choose a new output file in an existing directory (including a free .tmp name)')
    result = {
        'schema': SCHEMA, 'blocks': opt.blocks, 'batch_size': 1, 'frames': LENGTH,
        'frame_rate': FRAME_RATE, 'source': str(SRC), 'affinity_mask': affinity,
        'comfy_args': COMFY_ARGS, 'skip_decode': opt.skip_decode,
        'sizes': {f'{w}x{h}': shape_record(w, h) for w, h in opt.sizes},
        'method': {
            'warmups': WARMUP, 'timed': TIMED, 'aggregate': 'median',
            'transformer_scope': 'first forward inputs of each real sampler stage, replayed eagerly',
            'sampler': 'euler_ancestral', 'cfg': 1.0, 'noise_seed': NOISE_SEED, 'seed': SEED,
            'sigmas_stage1': SIGMAS_STAGE1, 'sigmas_stage2': SIGMAS_STAGE2,
            'conditioning': 'seeded fp32 [1,35,6144], unprocessed_ltxav_embeds=True; connector pads to 1024',
            'stage2_driver': 'seeded random full-resolution video latent plus actual stage-1 audio output',
            'decode': 'native VAEDecode / LTXVAudioVAEDecode, bf16 weights/compute, non-tiled',
            'audio': 'one shape measured once as a 2-warmup/6-timed group, shared by all resolutions',
            'memory': 'process max_memory_allocated, reset per size, includes resident weights and warmups; '
                      'transformer unloaded before loading both VAEs',
        },
        'caveats': [
            'Eager wall time includes Python dispatch. The process DRM compute-engine busy seconds '
            'are the GPU cost that matters; the earlier batch probe found nearly flat eager wall times.',
            'Diagnostic only: truncated transformer, random conditioning and latents, no quality claim.',
            'Per-block numbers divide the whole diffusion-model forward by blocks; non-block work is included.',
            'No extrapolation to 48 blocks or deployed multi-card graph throughput; text encoding, '
            'latent upsampling, saving and end-to-end pipeline overlap are not timed.',
            '640x384 is the valid padded geometry for the 640x360 question; no 640x360 cost is measured.',
            'Decode wall includes native output copies to the intermediate device; VAE OOM tiling is excluded.',
            'Ratios always use measured 256x256; that baseline is added to custom size lists. '
            'A missing/failed denominator produces null, never an estimated ratio.',
        ], 'partial': True,
    }

    def save():
        tmp = Path(str(out) + '.tmp')
        with tmp.open('w') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
        os.replace(tmp, out)

    started = time.perf_counter()
    r = None
    save()
    try:
        r = initialize_runtime()
        result.update(device=str(r.device), device_name=r.torch.xpu.get_device_name(r.device),
                      torch_version=str(r.torch.__version__))
        with r.torch.no_grad():
            run_transformer(r, result, opt.blocks, save)
            release_tensors(r)
            if not opt.skip_decode:
                run_decode(r, result, save)
                release_tensors(r)
        result['partial'] = False
    except Exception as error:
        result.update(fatal_error=repr(error), fatal_traceback=traceback.format_exc()[-5000:])
        print('PROBE FAILED:', repr(error), file=sys.stderr)
    finally:
        result['elapsed_s'] = time.perf_counter() - started
        add_ratios(result)
        save()
        print_table(result)
        print('wrote', out)
    failed = result.get('fatal_error') or any(
        row.get('sampling_status') != 'ok' or
        (not opt.skip_decode and row.get('video_decode', {}).get('status') != 'ok')
        for row in result['sizes'].values())
    failed = failed or (not opt.skip_decode and result.get('audio_decode', {}).get('status') != 'ok')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
