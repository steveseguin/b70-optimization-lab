#!/usr/bin/env python3
"""How big is the window's difference next to the difference between two honest runs of the UNCHANGED encoder?

Encodes the first fixtures (a) padded to 1024 on the GPU [certified path], (b) padded to 1024 on the CPU
[the same unchanged model on different hardware], (c) with the suffix window on the GPU, and reports each
difference on the real-token rows. If (c)-(a) is no larger than (b)-(a), the window sits inside the
variation the unchanged model already shows between machines.

(Original docstring follows.)
Direct probe: is a suffix-window Gemma encode byte-identical to the 1024-token encode?

Stand-alone (no ComfyUI server, no sealed launcher, one card). Loads the LTX
text encoder exactly as the server does (same ComfyUI tree, same CLI flags),
encodes each prompt at the certified 1024-token left-padded length and then
at each window W in the bucket list, with

  * the last W tokens of the same padded sequence,
  * explicit position ids 1024-W .. 1023 (the positions those tokens have in
    the padded layout),
  * the sliding layers' window set to W for that pass, so the attention call
    takes the same expanded-KV path it takes at 1024 tokens,

and compares the all-layer hidden-state stack cropped to the real tokens,
which is everything the rest of the pipeline consumes, byte for byte.

    ZE_AFFINITY_MASK=<card> python probe-encoder-suffix-window.py <out.json>

The comparison is eager against eager on one card. The server replays
captured graphs, which the lane has shown bit-equal to eager at 1024 tokens;
a pass here is the reason to build the graph-captured window, not the proof
of it.
"""
import hashlib, json, os, sys, time

OUT = sys.argv[1]
PACKET = '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-decode-91b'
SRC = PACKET + '/source'
GEMMA = '/mnt/fast-ai/llm-models/LTX-2.5-baseline/text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors'
LANE = '/home/steve/llm-optimizations/experiments/ltx25-b70'
BUCKETS = [512, 256, 128, 64]
FULL = 1024

# Same numerics-relevant flags as the server (see server-args.json of any 91b/91c run).
sys.argv = [SRC + '/main.py', '--cache-none', '--deterministic', '--disable-async-offload', '--disable-dynamic-vram',
            '--disable-comfy-compiler', '--disable-cuda-graphs', '--disable-pinned-memory', '--reserve-vram', '2',
            '--bf16-unet', '--bf16-text-enc', '--bf16-vae', '--use-pytorch-cross-attention', '--disable-xformers',
            '--disable-api-nodes']
sys.path.insert(0, SRC)
os.chdir(SRC)

import torch  # noqa: E402
import comfy.sd  # noqa: E402
import comfy.model_management as mm  # noqa: E402

torch.use_deterministic_algorithms(True, warn_only=True)

fixtures = json.load(open(LANE + '/data/stability-01-prereg.json'))['fixtures']
prompts = [(f.get('name', f'fixture-{i}'), f['prompt']) for i, f in enumerate(fixtures)]
WORDS = ('a slow pan across a quiet harbour at dawn while gulls circle above the masts and a fisherman coils wet rope '
         'beside stacked wooden crates as soft light spreads over rippling water and distant bells ring twice').split()
for n in (1, 3, 6, 12, 20, 28, 40, 52, 58, 61, 63, 66, 80, 100, 118, 122, 126, 130, 160, 200, 240, 250, 256, 262, 300,
          380, 440, 500, 508, 514):
    prompts.append((f'synthetic-{n}w', ' '.join(WORDS[i % len(WORDS)] for i in range(n)) + '.'))

t0 = time.time()
clip = comfy.sd.load_clip(ckpt_paths=[GEMMA], embedding_directory=None, clip_type=comfy.sd.CLIPType.LTXV, model_options={})
te = clip.cond_stage_model
key = te.text_encoder_key
inner = te.gemma3_12b  # the module is named gemma3_12b even for the Gemma 4 encoder; tokens use te.text_encoder_key
clip.load_model(clip.tokenize(prompts[0][1]))  # the LTX memory estimate needs real tokens
device = mm.get_torch_device()
model = next(m for m in inner.transformer.modules() if hasattr(m, 'compute_freqs_cis'))
sliding = [m for m in inner.transformer.modules() if getattr(m, 'sliding_attention', False) == FULL]
print(f'loaded in {time.time() - t0:.0f} s on {device}; {len(sliding)} sliding layers; model {type(model).__name__}', flush=True)

state = {'window': None}
orig_forward = model.forward


def forward(x, *a, **k):
    w = state['window']
    if w is not None and k.get('position_ids') is None:
        ref = k['embeds'] if k.get('embeds') is not None else x
        assert ref.shape[1] == w, (ref.shape, w)
        k['position_ids'] = torch.arange(FULL - w, FULL, device=ref.device).unsqueeze(0)
    return orig_forward(x, *a, **k)


model.forward = forward


def sync():
    if device.type == 'xpu':
        torch.xpu.synchronize(device)


def encode(rows, window):
    state['window'] = window
    for m in sliding:
        m.sliding_attention = FULL if window is None else window
    try:
        sync(); t = time.time()
        with torch.no_grad():
            out, _pooled, extra = inner.encode_token_weights(rows)
        sync(); dt = time.time() - t
    finally:
        state['window'] = None
        for m in sliding:
            m.sliding_attention = FULL
    n = int(extra['attention_mask'].sum().item())
    return out[:, :, -n:].contiguous().cpu(), n, dt


def sha(t):
    return hashlib.sha256(t.numpy().tobytes()).hexdigest()



NPROMPTS = int(os.environ.get('PROBE_PROMPTS', '3'))
gpu = {}
for name, text in prompts[:NPROMPTS]:
    pairs = clip.tokenize(text)[key]
    ref, n, _ = encode(pairs, None)
    w = next(b for b in sorted(BUCKETS) if b >= n)
    win, _, _ = encode([pairs[0][-w:]], w)
    gpu[name] = (pairs, ref, win, n, w)
    print('gpu', name, n, w, flush=True)
# second copy of the unchanged encoder on the CPU
del clip, te, inner, model, sliding
import gc; gc.collect()
cpu = torch.device('cpu')
clip2 = comfy.sd.load_clip(ckpt_paths=[GEMMA], embedding_directory=None, clip_type=comfy.sd.CLIPType.LTXV,
                           model_options={'load_device': cpu, 'offload_device': cpu})
inner2 = clip2.cond_stage_model.gemma3_12b
clip2.load_model(clip2.tokenize(prompts[0][1]))
report = []
def stats(a, b):
    d = (a.double() - b.double()).abs()
    scale = a.double().abs()
    return {'max_abs': float(d.max()), 'mean_abs': float(d.mean()), 'mean_abs_value': float(scale.mean()),
            'max_abs_value': float(scale.max()), 'relative_mean': float(d.mean() / scale.mean()),
            'cosine': float(torch.nn.functional.cosine_similarity(a.double().flatten(), b.double().flatten(), dim=0))}
for name, (pairs, ref, win, n, w) in gpu.items():
    t = time.time()
    with torch.no_grad():
        out, _p, extra = inner2.encode_token_weights(pairs)
    cpu_ref = out[:, :, -n:].contiguous().cpu()
    row = {'prompt': name, 'real_tokens': n, 'window': w, 'cpu_seconds': round(time.time() - t, 1),
           'cpu1024_vs_gpu1024': stats(ref, cpu_ref), 'gpuwindow_vs_gpu1024': stats(ref, win)}
    report.append(row); print(json.dumps(row), flush=True)
json.dump({'schema': 'ltx.encoder-window-vs-hardware-noise.v1', 'rows': report}, open(OUT, 'w'), indent=1)
