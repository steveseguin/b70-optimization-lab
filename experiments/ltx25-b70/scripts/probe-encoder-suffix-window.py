#!/usr/bin/env python3
"""Direct probe: is a suffix-window Gemma encode byte-identical to the 1024-token encode?

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


rows_out, summary = [], {str(w): {'tested': 0, 'exact': 0, 'first_mismatch': None, 'seconds': []} for w in BUCKETS}
full_seconds = []
for name, text in prompts:
    pairs = clip.tokenize(text)[key]
    assert len(pairs) == 1 and len(pairs[0]) == FULL, (len(pairs), len(pairs[0]))
    ref, n, dt = encode(pairs, None)
    ref2, _, dt2 = encode(pairs, None)
    full_seconds.append(dt2)
    row = {'prompt': name, 'real_tokens': n, 'shape': list(ref.shape), 'dtype': str(ref.dtype), 'sha256_1024': sha(ref),
           'repeat_1024_exact': bool(torch.equal(ref, ref2)), 'seconds_1024': round(dt2, 4), 'windows': {}}
    for w in BUCKETS:
        if n > w:
            continue
        got, n2, dtw = encode([pairs[0][-w:]], w)
        got2, _, dtw2 = encode([pairs[0][-w:]], w)
        exact = n2 == n and got.shape == ref.shape and bool(torch.equal(ref, got))
        diff = None if exact or got.shape != ref.shape else float((ref.double() - got.double()).abs().max())
        row['windows'][str(w)] = {'exact': exact, 'repeat_exact': bool(torch.equal(got, got2)), 'max_abs_diff': diff,
                                  'sha256': sha(got), 'seconds': round(dtw2, 4)}
        s = summary[str(w)]
        s['tested'] += 1; s['exact'] += int(exact); s['seconds'].append(dtw2)
        if not exact and s['first_mismatch'] is None:
            s['first_mismatch'] = {'prompt': name, 'real_tokens': n, 'max_abs_diff': diff}
    rows_out.append(row)
    print(name, n, {w: (v['exact'], v['max_abs_diff']) for w, v in row['windows'].items()}, flush=True)

for s in summary.values():
    sec = s.pop('seconds')
    s['median_seconds'] = round(sorted(sec)[len(sec) // 2], 4) if sec else None
result = {'schema': 'ltx.encoder-suffix-window-probe.v1', 'device': str(device), 'torch': torch.__version__,
          'packet_source': SRC, 'buckets': BUCKETS,
          'median_seconds_1024': round(sorted(full_seconds)[len(full_seconds) // 2], 4),
          'summary': summary, 'rows': rows_out}
json.dump(result, open(OUT, 'w'), indent=1)
print(json.dumps({'median_seconds_1024': result['median_seconds_1024'], 'summary': summary}, indent=1))
