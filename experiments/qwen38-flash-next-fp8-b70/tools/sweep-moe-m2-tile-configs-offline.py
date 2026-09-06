#!/usr/bin/env python3
"""Offline M=2 tile-config sweep for the Flash-Next block-FP8 MoE GEMMs on card 0.
For each candidate, write a copy of the W13-N32 map with an explicit "2" entry, run the
event-timing tool (vllm.q38_timing hook, diagnostics overlay in PYTHONPATH) and parse its
'M=2 ep-like' line (10 local hits of 20 routed slots, the server's decode regime).
Usage: moe-m2-config-sweep.py <overlay-worktree> <out.json> [max_candidates]"""
import itertools, json, os, re, subprocess, sys, tempfile, shutil, time
from pathlib import Path
overlay, out = sys.argv[1], sys.argv[2]; limit = int(sys.argv[3]) if len(sys.argv) > 3 else 999
E = Path('/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70')
src = next(E.glob('configs/moe-m1-w13-n32/E=128,N=640,*.json'))
base = json.load(open(src))
STAGE = '/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70'
PY = '/home/steve/.venvs/vllm-xpu/bin/python'
def run(cfg2, label):
    d = tempfile.mkdtemp(prefix='q38-m2-sweep-'); m = dict(base); m['2'] = cfg2
    (Path(d) / src.name).write_text(json.dumps(m))
    env = dict(os.environ, VLLM_TUNED_CONFIG_FOLDER=d, PYTHONPATH=f'{STAGE}:{overlay}', ZE_AFFINITY_MASK='0', Q38_BENCH_SETS='8', VLLM_TARGET_DEVICE='xpu',
               LD_LIBRARY_PATH=f'{STAGE}/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:' + os.environ.get('LD_LIBRARY_PATH',''))
    t = time.time()
    p = subprocess.run([PY, str(E / 'tools/timing-moe-gemm-events-offline.py')], env=env, capture_output=True, text=True, timeout=900)
    shutil.rmtree(d, ignore_errors=True)
    lines = [l for l in p.stdout.splitlines() if l.startswith('M=')]
    rec = {'label': label, 'config': cfg2, 'seconds': round(time.time() - t, 1), 'lines': lines, 'rc': p.returncode}
    if p.returncode != 0: rec['stderr'] = p.stderr[-600:]
    for l in lines:
        mm = re.match(r"M=(\d) (\S+) local_hits=(\d+)/(\d+): (\{.*\}) ms", l)
        if mm:
            try: rec[f'M{mm.group(1)}_{mm.group(2)}'] = eval(mm.group(5))
            except Exception: pass
    return rec
results = []
cands = [('baseline-M1-entry', None)]
for bn, warps, stages, w1bn in itertools.product((32, 64, 128), (4, 8), (2, 3, 4), (None, 32)):
    cfg = {"BLOCK_SIZE_M": 16, "BLOCK_SIZE_N": bn, "BLOCK_SIZE_K": 128, "GROUP_SIZE_M": 1, "SPLIT_K": 1, "num_warps": warps, "num_stages": stages}
    if w1bn: cfg["W1_CONFIG"] = {"BLOCK_SIZE_N": w1bn}
    cands.append((f'bn{bn}-w{warps}-s{stages}' + (f'-w1bn{w1bn}' if w1bn else ''), cfg))
for label, cfg in cands[:limit]:
    rec = run(cfg if cfg is not None else base['1'], label) if cfg is not None else run(base['1'], label)
    results.append(rec); json.dump(results, open(out, 'w'), indent=1)
    key = rec.get('M2_ep-like') or {}
    print(label, rec['rc'], rec['seconds'], 's', {k: v for k, v in key.items() if 'ms' in k or 'w' in k}, flush=True)
