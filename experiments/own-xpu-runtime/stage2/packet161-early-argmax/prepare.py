"""Reconstruct final target HC with original FP32 order; never run the model.

Only main opens GGUF, after checking the one-card chain is inactive. Uses the
existing CPU-only deterministic math bridge, no compiler/runtime/device imports.
"""
import ctypes
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from audit import P, ROOT, guard


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def weight_admission():
    result = subprocess.run(['systemctl', '--user', 'is-active', 'packet58-onecard-58aj-a'],
                            capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert result.stdout.strip() in ('inactive', 'failed'), 'one-card timing chain still active/unknown'
    return dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                unit='packet58-onecard-58aj-a', state=result.stdout.strip())


def bf(x):
    a = np.asarray(x, dtype=np.float32)
    u = a.view(np.uint32)
    return ((u + np.uint32(0x7fff) + ((u >> 16) & 1)) & np.uint32(0xffff0000)).view(np.float32)


def unpack(raw):
    return (np.frombuffer(raw, '<u2').astype(np.uint32) << 16).view(np.float32)


def tree(x):
    while x.shape[-1] > 1:
        if x.shape[-1] % 2:
            x = np.pad(x, [(0, 0)]*(x.ndim-1)+[(0, 1)])
        x = x[..., 0::2] + x[..., 1::2]
    return x[..., 0]


def exact_gemv(w, x, splits=1):
    """batch x rows; original lane*8, tile256, sequential FP32 then tree32."""
    n, k = w.shape
    parts = []
    tiles = (k+255)//256
    for part in range(splits):
        acc = np.zeros((len(x), n, 32), np.float32)
        begin, end = min(k, tiles*part//splits*256), min(k, tiles*(part+1)//splits*256)
        for tile in range(begin, end, 256):
            for j in range(8):
                ix = tile+np.arange(32)*8+j
                valid = ix < end
                ix = ix[valid]
                acc[..., valid] += x[:, None, ix]*w[None, :, ix]
        parts.append(tree(acc))
    return bf(tree(np.stack(parts, -1)))


class Weights:
    def __init__(self):
        self.admission = weight_admission()
        sys.path.insert(0, str(ROOT/'experiments/own-xpu-runtime/stage1/packet1b'))
        from loaders.headers import gguf_header
        sys.path.insert(0, str(ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle'))
        from packed import decode
        self.decode = decode
        authority = P.parent/'packet49c-round2/build/input'
        self.model = Path(json.loads((authority/'input.json').read_text())['model_dir'])
        self.identities = {}
        for line in (authority/'identity.tsv').read_text().splitlines():
            name, *identity = line.split()
            s = (self.model/name).stat()
            assert (s.st_size, s.st_dev, s.st_ino, s.st_mtime_ns, s.st_ctime_ns) == tuple(map(int, identity))
            self.identities[name] = identity
        self.path = self.model/'Qwen3.8-Flash-Next-UD-IQ3_XXS-00002-of-00003.gguf'
        with self.path.open('rb') as f:
            self.header = gguf_header(f, self.path.stat().st_size)
        self.reads = []

    def rows(self, name, start=0, count=None):
        weight_admission()
        t = self.header['tensors'][name]
        shape = t['shape']
        count = shape[0]-start if count is None else count
        stride = t['bytes']//shape[0]
        with self.path.open('rb') as f:
            f.seek(t['file_offsets'][0]+start*stride)
            raw = f.read(count*stride)
        assert len(raw) == count*stride
        self.reads.append(dict(name=name, start=start, count=count, bytes=len(raw), sha256=sha(raw)))
        return self.decode(t['type'], raw).reshape(count, *shape[1:])


def target_sources():
    base = Path('/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/results')
    records = []
    for directory in sorted(base.iterdir()):
        if not (directory/'step1/layer-47.bf16').exists() or directory.name.endswith('repeat'):
            continue
        steps = {r['step']: r for r in map(json.loads, (directory/'tokens.jsonl').read_text().splitlines())}
        selected = list(range(1, 9))+list(range(97, 105))
        if directory.name == 'incident-retrospective':
            selected += list(range(9, 17))
        for step in sorted(selected):
            path = directory/f'step{step}/layer-47.bf16'
            if not path.exists():
                size = len(json.loads((directory/'input.json').read_text())['tokens'])
                path = directory/f'capture-streams/streams-{size+step-2}.bf16'
            raw = path.read_bytes()
            records.append(dict(corpus='suite', prompt=directory.name, step=step, path=str(path),
                                stream_sha256=sha(raw), oracle=steps[step], raw=raw))
    assert len(records) == 200 and len({r['prompt'] for r in records}) == 12
    base = P.parent/'packet132-two-candidate/build/capture'
    for i in range(5):
        directory = base/f'doc-{i}'
        steps = json.loads((directory/'target/result.json').read_text())['steps']
        for row in steps:
            path = directory/f'target/capture-streams/streams-{row["step"]+14}.bf16'
            raw = path.read_bytes()
            records.append(dict(corpus='independent', prompt=f'doc-{i}', step=row['step'],
                                path=str(path), stream_sha256=sha(raw), oracle=row, raw=raw))
    assert len(records) == 320
    return records


def transform(weights, records):
    bridge = Path('/home/steve/own-xpu-runtime-results/packet49d-round3/build/gnu-host/libmath_bridge.so')
    assert sha(bridge.read_bytes()) == '0549ae1040a3d445ee0a5977798275701a3f4b7d85d46b2d4635b61fb8b12514'
    lib = ctypes.CDLL(str(bridge))
    for name in ('v2_exp', 'v2_sqrt'):
        f = getattr(lib, name)
        f.argtypes = [ctypes.c_float]
        f.restype = ctypes.c_float
    cache = {}
    def exp(x):
        unique, inverse = np.unique(x, return_inverse=True)
        for value in unique:
            key = float(value)
            if key not in cache:
                cache[key] = lib.v2_exp(key)
        return np.array([cache[float(v)] for v in unique], np.float32)[inverse].reshape(x.shape)
    def sigmoid(x):
        return np.float32(1)/(np.float32(1)+exp(-x))
    norm = weights.rows('output_hc_norm.weight').reshape(4, 2560)
    down = weights.rows('output_hc_down.weight')
    up = weights.rows('output_hc_up.weight')
    out = []
    for start in range(0, len(records), 8):
        x = np.stack([unpack(r['raw']).reshape(4, 2560) for r in records[start:start+8]])
        mean = tree(x*x)/np.float32(2560)+np.float32(1e-6)
        root = np.array([lib.v2_sqrt(float(v)) for v in mean.ravel()], np.float32).reshape(mean.shape)
        xn = bf((x*(np.float32(1)/root)[..., None])*norm)
        low = exact_gemv(down, xn.reshape(len(x), -1), 4)/np.float32(4)
        act = bf(low*sigmoid(low))
        gate = exact_gemv(up, act).reshape(len(x), 4, 2560)
        acc = np.zeros((len(x), 2560), np.float32)
        for i in range(4):
            acc += sigmoid(gate[:, i])*xn[:, i]
        out.extend(bf(acc/np.float32(4)))
    return np.stack(out)


def main():
    guard()
    global np
    import numpy as np
    weights = Weights()
    records = target_sources()
    hidden = transform(weights, records)
    # Verify reconstructed hidden through all five stored exact head logits.
    for i, row in enumerate(records):
        w = np.concatenate([weights.rows('output.weight', index, 1) for index in row['oracle']['top5_ids']])
        logits = exact_gemv(w, hidden[i:i+1])[0]
        assert logits.tolist() == row['oracle']['top5_logits'], (i, logits, row['oracle']['top5_logits'])
    for row in records:
        del row['raw']
        row['head'] = 'target'
        row['max_logit'] = row['oracle']['top5_logits'][0]
    draft = Path('/home/steve/own-xpu-runtime-results/packet61x-spin-hcfusion-wait/build/device-cards01-a/KD/host-reference')
    dh = []
    for directory in sorted(draft.glob('row-*'), key=lambda p: int(p.name[4:])):
        path = directory/'final.mix.bf16'
        raw = path.read_bytes()
        x = unpack(raw)
        all_logits = unpack((directory/'logits.bf16').read_bytes())
        assert len(x) == 2560 and len(all_logits) >= 80128
        logits = all_logits[:80128]
        winner = int(np.argmax(logits))
        got = exact_gemv(weights.rows('output.weight', winner, 1), x[None, :])[0, 0]
        assert got == logits[winner]
        dh.append(x)
        records.append(dict(corpus='suite-incident-only', prompt='incident-retrospective',
                            head='draft', position=int(directory.name[4:]), path=str(path),
                            stream_sha256=sha(raw), max_logit=float(got), winner=winner,
                            original_logits_sha256=sha((directory/'logits.bf16').read_bytes())))
    assert len(dh) == 65
    all_hidden = np.concatenate([hidden, np.stack(dh)])
    raw = (all_hidden.view(np.uint32) >> 16).astype('<u2').tobytes()
    with (P/'evidence/hidden.bf16.gz').open('wb') as f:
        f.write(gzip.compress(raw, mtime=0))
    (P/'evidence/positions.json').write_text(json.dumps(records, indent=2)+'\n')
    (P/'evidence/preparation.json').write_text(json.dumps(dict(
        target_top5_exact_checks=len(hidden)*5, draft_winner_checks=len(dh),
        hidden_bytes=len(raw), hidden_sha256=sha(raw), shape=[len(records), 2560],
        weights_admission=weights.admission, weight_reads=weights.reads,
        math_bridge_sha256='0549ae1040a3d445ee0a5977798275701a3f4b7d85d46b2d4635b61fb8b12514',
        draft_independent_positions=0, complete_requested_coverage=False), indent=2)+'\n')
    print(json.dumps(dict(target_positions=len(hidden), draft_positions=len(dh), exact_checks=1665)), flush=True)


if __name__ == '__main__':
    main()
