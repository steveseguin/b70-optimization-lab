#!/usr/bin/env python3
"""Probe: is each row of a fixed-size batch through the LTX latent upsampler independent of the other rows?

Companion to probe-batch-row-independence.py (the transformer). Stand-alone, one card, eager, the packet's
ComfyUI tree with the server's flags. Loads the x2 spatial latent upsampler the way LatentUpscaleModelLoader
does and runs seeded random stage-1 latents [B, 128, 4, 4, 4] through it at batch 1, 2 and 4. The per-channel
normalisation around the model in LTXVLatentUpsampler is elementwise and is not part of the question.

    ZE_AFFINITY_MASK=<card> python -B probe-upsampler-row-independence.py <out.json>
"""
import json, sys, time

OUT = sys.argv[1]
PACKET = '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-workers-95'
SRC = PACKET + '/source'
CKPT = '/mnt/fast-ai/llm-models/LTX-2.5-baseline/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors'
sys.argv = [SRC + '/main.py', '--cache-none', '--deterministic', '--disable-async-offload', '--disable-dynamic-vram',
            '--disable-comfy-compiler', '--disable-cuda-graphs', '--disable-pinned-memory', '--reserve-vram', '2',
            '--bf16-unet', '--bf16-text-enc', '--bf16-vae', '--use-pytorch-cross-attention', '--disable-xformers',
            '--disable-api-nodes']
sys.path.insert(0, SRC)
import os
os.chdir(SRC)
import torch  # noqa: E402
import comfy.options  # noqa: E402
comfy.options.enable_args_parsing()
import comfy.model_management as mm  # noqa: E402
torch.use_deterministic_algorithms(True, warn_only=False)
import comfy.utils, comfy.ops  # noqa: E402
from comfy.ldm.lightricks.latent_upsampler import LatentUpsampler  # noqa: E402

device = mm.get_torch_device()
sd, metadata = comfy.utils.load_torch_file(CKPT, safe_load=True, return_metadata=True)
config = json.loads(metadata['config'])
dtype = mm.vae_dtype(allowed_dtypes=[torch.bfloat16, torch.float32])
model = LatentUpsampler.from_config(config, operations=comfy.ops.disable_weight_init).to(dtype=dtype)
model.load_state_dict(sd)
model = model.to(device).eval()
print('upsampler on', device, 'dtype', dtype, flush=True)


def clip(seed):
    g = torch.Generator().manual_seed(seed)
    return torch.randn(1, 128, 4, 4, 4, generator=g).to(dtype=dtype, device=device)


def run(rows):
    with torch.no_grad():
        y = model(torch.cat(rows, dim=0))
    torch.xpu.synchronize(device)
    return y.float().cpu()


def cmp(a, b):
    d = (a.double() - b.double()).abs()
    return {'equal': bool(torch.equal(a, b)), 'n_diff': int((d > 0).sum()), 'numel': a.numel(), 'max_abs_diff': float(d.max()),
            'mean_abs_diff': float(d.mean())}


A, B, C, D, E = (clip(s) for s in (101, 202, 303, 404, 505))
o1 = run([A]); o1b = run([A])
res = {'schema': 'ltx.upsampler-row-independence-probe.v1', 'device': str(device), 'dtype': str(dtype), 'torch': torch.__version__,
       'output_shape': list(o1.shape), 'batch1_repeat': cmp(o1, o1b), 'out_rms': float(o1.double().pow(2).mean().sqrt()),
       'out_max_abs': float(o1.abs().max()), 'A_vs_B_batch1': cmp(o1, run([B])), 'batches': {}}
for k in (2, 3, 4):
    others, alt = [B, C, D][:k - 1], [C, D, E][:k - 1]
    prim = run([A] + others)
    r = {'neighbour': cmp(prim[0:1], run([A] + alt)[0:1]), 'repeat': cmp(prim, run([A] + others)),
         'identical': {str(j): cmp(x[0:1], x[j:j + 1]) for x in [run([A] * k)] for j in range(1, k)},
         'slot': {}, 'vs_batch1': cmp(prim[0:1], o1)}
    for j in range(1, k):
        rows = list(others); rows.insert(j, A)
        r['slot'][str(j)] = cmp(prim[0:1], run(rows)[j:j + 1])
    r['row_independent'] = bool(r['neighbour']['equal'] and r['repeat']['equal'] and all(v['equal'] for v in r['identical'].values())
                                and all(v['equal'] for v in r['slot'].values()))
    res['batches'][str(k)] = r
    print(f"batch {k}: row-independent: {'yes' if r['row_independent'] else 'no'} (neighbour {r['neighbour']['equal']}, slot "
          f"{all(v['equal'] for v in r['slot'].values())}, identical {all(v['equal'] for v in r['identical'].values())}, repeat "
          f"{r['repeat']['equal']}); equal to batch 1: {r['vs_batch1']['equal']} (max diff {r['vs_batch1']['max_abs_diff']:.4g}, mean "
          f"{r['vs_batch1']['mean_abs_diff']:.4g}, {r['vs_batch1']['n_diff']}/{r['vs_batch1']['numel']} values; output rms {res['out_rms']:.3g})", flush=True)
json.dump(res, open(OUT, 'w'), indent=1)
print('batch-1 repeat equal:', res['batch1_repeat']['equal'], '| wrote', OUT)
