#!/usr/bin/env python3
"""Pack real HC weights (GGUF) and real activations + engine outputs (finish state dumps) for the HC kernel bench.

For every HC block of both ranks (blk.L.hc.a / blk.L.hc.f for L = 0..47, and rank 1's final hc) the pack holds:
  low   BF16 [320][10240]   (hc_*_down.weight; GGUF ne = [10240, 320])
  inj   BF16 [4][10240]     (hc_*_inject.weight; absent for final)
  gate  BF16 [10240][320]   (hc_*_up.weight)
  gain  F32  [10240]        (hc_*_norm.weight)
  x_low F32 [10240] = dumped <tag>.norm (the low/inject GEMV input), x_gate F32 [320] = dumped <tag>.act,
  ref_low F32 [320], ref_inj F32 [4], ref_gate F32 [10240] = the engine's dumped outputs of the same step.
  streams F32 [10240] (the rank's dumped streams; a real input for the norm kernels).
  branch F32 [2560], cinj F32 [4]: the real inputs of the combine that precedes this block's norm in the plan
  (hc.f: attn.combine of the same layer = attention + hc.a.inject; hc.a: ffn.combine of the previous layer = moe +
  hc.f.inject, or the same layer's attention + hc.a.inject at a rank's first layer; final: layer 47's ffn.combine).
Output: OUT/pack.bin + OUT/pack.json (offsets). Dumps: stage-overhead d2-r0-full (rank 0), d1-r1-full (rank 1).
"""
import json, os, struct, sys, hashlib
OUT = sys.argv[1] if len(sys.argv) > 1 else '/dev/shm/hc-kernels-2026-10-30/data'
MODEL = '/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a'
ARCH = '/mnt/raid-models/ownrt-experiment-archives/2026-10-30/stage-overhead-runs-d1-d2'
DUMPS = {0: f'{ARCH}/d2-r0-full/rank0/state-2147483647', 1: f'{ARCH}/d1-r1-full/rank1/state-2147483647'}

def gguf_tensors(path):
    f = open(path, 'rb')
    rd = lambda fmt: struct.unpack('<' + fmt, f.read(struct.calcsize('<' + fmt)))[0]
    def rstr():
        n = rd('Q'); return f.read(n).decode()
    assert f.read(4) == b'GGUF'
    ver = rd('I'); nt = rd('Q'); nkv = rd('Q')
    sizes = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i', 6: 'f', 7: '?', 10: 'Q', 11: 'q', 12: 'd'}
    align = 32
    def rval(t):
        if t == 8: return rstr()
        if t == 9:
            et = rd('I'); n = rd('Q'); return [rval(et) for _ in range(n)]
        return rd(sizes[t])
    for _ in range(nkv):
        k = rstr(); t = rd('I'); v = rval(t)
        if k == 'general.alignment': align = v
    tensors = {}
    for _ in range(nt):
        name = rstr(); nd = rd('I'); dims = [rd('Q') for _ in range(nd)]; typ = rd('I'); off = rd('Q')
        tensors[name] = (dims, typ, off)
    start = (f.tell() + align - 1) // align * align
    return f, start, tensors

shards = {}
for fn in sorted(os.listdir(MODEL)):
    if fn.endswith('.gguf'):
        f, start, t = gguf_tensors(os.path.join(MODEL, fn))
        for name, v in t.items(): shards[name] = (f, start, v)

def tensor(name, typ, nbytes):
    f, start, (dims, t, off) = shards[name]
    assert t == typ, (name, t, typ)
    f.seek(start + off); b = f.read(nbytes); assert len(b) == nbytes, name
    return b

def dump_reader(rank):
    d = DUMPS[rank]; idx = {}
    for line in open(f'{d}/state-index.tsv'):
        p = line.rstrip('\n').split('\t')
        if len(p) == 4: idx[p[0]] = (int(p[1]), int(p[2]), p[3])
    bundle = open(f'{d}/state.bundle', 'rb')
    def get(name):
        off, n, sha = idx[name + '.bin']; bundle.seek(off); b = bundle.read(n)
        assert hashlib.sha256(b).hexdigest() == sha, name
        return b
    return get

os.makedirs(OUT, exist_ok=True)
pack = open(f'{OUT}/pack.bin', 'wb'); entries = []
def put(b):
    off = pack.tell(); pack.write(b)
    pad = (-pack.tell()) % 256; pack.write(b'\0' * pad); return off
for rank, layers in ((0, range(0, 23)), (1, range(23, 48))):
    get = dump_reader(rank)
    streams = put(get('streams'))
    blocks = [(L, s) for L in layers for s in ('a', 'f')] + ([(None, 'final')] if rank == 1 else [])
    for L, s in blocks:
        if L is None: tag, wp, inject = 'final', 'output_hc_', False
        else: tag, wp, inject = f'blk.{L}.hc.{s}', f'blk.{L}.hc_{"attn" if s == "a" else "ffn"}_', True
        e = {'rank': rank, 'tag': tag, 'streams': streams,
             'low': put(tensor(wp + 'down.weight', 30, 320 * 10240 * 2)),
             'gate': put(tensor(wp + 'up.weight', 30, 10240 * 320 * 2)),
             'gain': put(tensor(wp + 'norm.weight', 0, 10240 * 4)),
             'x_low': put(get(tag + '.norm')), 'x_gate': put(get(tag + '.act')),
             'ref_low': put(get(tag + '.low')), 'ref_gate': put(get(tag + '.gate'))}
        if inject:
            e['inj'] = put(tensor(wp + 'inject.weight', 30, 4 * 10240 * 2)); e['ref_inj'] = put(get(tag + '.inject'))
        if L is None: bl, bt = 'blk.47.moe', 'blk.47.hc.f.inject'
        elif s == 'f': bl, bt = f'blk.{L}.attention', f'blk.{L}.hc.a.inject'
        elif L - 1 in layers: bl, bt = f'blk.{L-1}.moe', f'blk.{L-1}.hc.f.inject'
        else: bl, bt = f'blk.{L}.attention', f'blk.{L}.hc.a.inject'
        e['branch'] = put(get(bl)); e['cinj'] = put(get(bt)); e['combine_from'] = [bl, bt]
        entries.append(e)
pack.close()
json.dump({'blocks': entries, 'dumps': DUMPS, 'model': MODEL}, open(f'{OUT}/pack.json', 'w'), indent=0)
with open(f'{OUT}/pack.tsv', 'w') as f:
    for e in entries:
        f.write('\t'.join(str(x) for x in [e['rank'], e['tag'], e['streams'], e['low'], e.get('inj', -1), e['gate'], e['gain'], e['x_low'],
                                         e['x_gate'], e['ref_low'], e.get('ref_inj', -1), e['ref_gate'], e['branch'], e['cinj']]) + '\n')
print(len(entries), 'blocks', os.path.getsize(f'{OUT}/pack.bin') / 1e9, 'GB')
