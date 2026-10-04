#!/usr/bin/env python3
"""Localiser: which operation first differs between the 1024-token encode and a suffix window?

Same setup as probe-encoder-suffix-window.py; forward hooks record the output of every leaf module of the
first layers (and each whole layer) for one prompt at 1024 tokens and at window W, and the last W sequence
rows are compared in execution order.

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



W = int(os.environ.get('PROBE_WINDOW', '512'))
NLAYERS = int(os.environ.get('PROBE_LAYERS', '2'))
name, text = prompts[0]
pairs = clip.tokenize(text)[key]
layers = list(model.layers)
watch = []
for li, layer in enumerate(layers[:NLAYERS]):
    for mn, m in layer.named_modules():
        if mn and len(list(m.children())) == 0:
            watch.append((f'layer{li}.{mn}', m))
    watch.append((f'layer{li}', layer))
for li in (len(layers) // 2, len(layers) - 1):
    watch.append((f'layer{li}', layers[li]))
watch.append(('embed_tokens', model.embed_tokens))


def run(rows, window):
    rec, hooks = [], []
    def mk(label):
        def hook(_m, inp, out):
            o = out[0] if isinstance(out, (tuple, list)) else out
            i = inp[0] if isinstance(inp, (tuple, list)) and len(inp) and torch.is_tensor(inp[0]) else None
            rec.append((label, o.detach().float().cpu() if torch.is_tensor(o) else None,
                        i.detach().float().cpu() if i is not None else None, str(o.dtype) if torch.is_tensor(o) else None))
        return hook
    for label, m in watch:
        hooks.append(m.register_forward_hook(mk(label)))
    try:
        encode(rows, window)
    finally:
        for h in hooks:
            h.remove()
    return rec


def tail_rows(t, w):
    # the sequence axis is the one whose length is 1024 (full) or w (window)
    for ax, n in enumerate(t.shape):
        if n in (FULL, w) and ax > 0:
            return t.narrow(ax, n - w, w)
    return None


full = run(pairs, None)
win = run([pairs[0][-W:]], W)
assert [a[0] for a in full] == [b[0] for b in win], 'hook order differs'
report = []
for (label, fo, fi, dt), (_l, wo, wi, _d) in zip(full, win):
    row = {'module': label, 'dtype': dt, 'full_shape': list(fo.shape) if fo is not None else None,
           'win_shape': list(wo.shape) if wo is not None else None}
    for kind, a, b in (('input', fi, wi), ('output', fo, wo)):
        if a is None or b is None:
            row[kind] = None; continue
        ta = tail_rows(a, W); tb = tail_rows(b, W)
        if ta is None or tb is None or ta.shape != tb.shape:
            row[kind] = 'shape'; continue
        eq = bool(torch.equal(ta, tb))
        row[kind] = 'exact' if eq else 'diff %.3e' % float((ta.double() - tb.double()).abs().max())
        # also restrict to real-token rows only
        n_real = int(sum(1 for t in pairs[0] if t[0] != 0))
        for ax, n in enumerate(ta.shape):
            if n == W and ax > 0:
                ra, rb = ta.narrow(ax, W - n_real, n_real), tb.narrow(ax, W - n_real, n_real)
                row[kind + '_real_rows'] = 'exact' if bool(torch.equal(ra, rb)) else 'diff %.3e' % float((ra.double() - rb.double()).abs().max())
                break
    report.append(row)
    print(label.ljust(34), str(dt).ljust(15), 'in:', str(row.get('input')).ljust(16), 'in(real):', str(row.get('input_real_rows')).ljust(16),
          'out:', str(row.get('output')).ljust(16), 'out(real):', str(row.get('output_real_rows')), flush=True)
json.dump({'schema': 'ltx.encoder-window-localiser.v1', 'window': W, 'prompt': name, 'rows': report}, open(OUT, 'w'), indent=1)
