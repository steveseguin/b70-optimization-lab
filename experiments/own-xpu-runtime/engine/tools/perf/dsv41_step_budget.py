#!/usr/bin/env python3
"""Time-vs-floor ledger for one DeepSeek V4.1 Flash step on the six-card own engine (OWN_TP=6).

Reads the engine's OWN_GPROF=2 profiles (one per card: OWN_GPROF_CARD=c), the model's GGUF headers (tensor
shapes and quant types; tensor data is never read) and an unprofiled run for the real step time, models the
bytes every launch must read under the engine's per-card slicing (backend_sycl_v41.hpp: tp_rows, tp_setup,
head_layout, tp_phase), and prints for every kernel type: launches per step, us per launch, ms per step,
bytes per launch (weights + activations), the floor at --bw GB/s, the gap. Then category totals per card
and across cards (the slowest card per category), and the top recoverable items.

Inputs (defaults are the b1 run of 2026-11-11):
  --runs DIR        dec_c{0..5}.log (answer steps, OWN_GPROF=2 OWN_GPROF_DECODE=1 OWN_GPROF_CARD=c),
                    pre_c{0..5}.log (a prompt read with OWN_GPROF=2; needs >= 2 answer tokens or the runner
                    prints no profile), plain.log (unprofiled, for the real step time)
  --pre-fallback    prompt profiles used when the pre_c logs carry no kernel table (default: the e80 3K
                    profiles of cards 0, 2, 4, 5)
  --model DIR       GGUF directory (headers only)

Floors (all parameters):
  weights/activations: bytes / --bw (GB/s, default 550)
  exchanges:           --xchg-sync-us (one PCIe flag round trip, default 2.5) + bytes / --link-gbs
  prompt blocks:       max(bytes / --bw, multiply-adds / --macs-per-s)
The floor is a structural ideal (every launch at the card's bandwidth, no launch, no ramp, no tail); a fused or
persistent form is needed to reach it for the small kernels. `--launch-us` adds a "standalone" floor
(max(floor, launch cost)) so the table also shows what is reachable without fusing.

Writes markdown to stdout (or --md FILE) and optionally JSON (--json FILE). No GPU, no compile, stdlib only.
"""
import argparse
import glob
import json
import math
import os
import re
import struct
import sys
from collections import OrderedDict, defaultdict

# ----------------------------------------------------------------------------------------------------------
# GGUF header (metadata + tensor infos only; the data section is never touched)
# ----------------------------------------------------------------------------------------------------------
GGML_TYPES = {0: 'F32', 1: 'F16', 2: 'Q4_0', 3: 'Q4_1', 6: 'Q5_0', 7: 'Q5_1', 8: 'Q8_0', 9: 'Q8_1', 10: 'Q2_K',
              11: 'Q3_K', 12: 'Q4_K', 13: 'Q5_K', 14: 'Q6_K', 15: 'Q8_K', 16: 'IQ2_XXS', 17: 'IQ2_XS',
              18: 'IQ3_XXS', 19: 'IQ1_S', 20: 'IQ4_NL', 21: 'IQ3_S', 22: 'IQ2_S', 23: 'IQ4_XS', 24: 'I8',
              25: 'I16', 26: 'I32', 27: 'I64', 28: 'F64', 29: 'IQ1_M', 30: 'BF16', 39: 'MXFP4'}
# (elements per block, bytes per block) as stored in GGUF
GGUF_BLOCK = {'F32': (1, 4), 'F16': (1, 2), 'BF16': (1, 2), 'Q8_0': (32, 34), 'Q2_K': (256, 84),
              'Q5_K': (256, 176), 'Q6_K': (256, 210), 'IQ2_XXS': (256, 66), 'IQ2_XS': (256, 74),
              'IQ2_S': (256, 82), 'IQ3_XXS': (256, 98), 'IQ1_S': (256, 50), 'MXFP4': (32, 17)}
_SCALAR = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i', 6: 'f', 7: '?', 10: 'Q', 11: 'q', 12: 'd'}


def _rd(f, fmt):
    n = struct.calcsize('<' + fmt)
    b = f.read(n)
    if len(b) != n:
        raise EOFError('short GGUF header')
    return struct.unpack('<' + fmt, b)


def _rstr(f):
    (n,) = _rd(f, 'Q')
    return f.read(n).decode('utf-8', 'replace')


def _rval(f, t, keep_arrays):
    if t in _SCALAR:
        return _rd(f, _SCALAR[t])[0]
    if t == 8:
        return _rstr(f)
    if t == 9:
        (et,) = _rd(f, 'I')
        (n,) = _rd(f, 'Q')
        if et in _SCALAR and not keep_arrays and n > 256:
            f.seek(n * struct.calcsize('<' + _SCALAR[et]), 1)  # big numeric arrays (token maps): skipped
            return '<array %d>' % n
        if et in (8, 9) and not keep_arrays and n > 256:
            for _ in range(n):
                _rval(f, et, False)  # vocabulary strings: read past
            return '<array %d>' % n
        return [_rval(f, et, keep_arrays) for _ in range(n)]
    raise ValueError('GGUF value type %d' % t)


def read_gguf_header(path):
    kv, tensors = {}, {}
    with open(path, 'rb') as f:
        if f.read(4) != b'GGUF':
            raise ValueError(path + ': not a GGUF file')
        (ver,) = _rd(f, 'I')
        if ver < 2:
            raise ValueError(path + ': GGUF v1 not supported')
        (nt,) = _rd(f, 'Q')
        (nkv,) = _rd(f, 'Q')
        for _ in range(nkv):
            k = _rstr(f)
            (t,) = _rd(f, 'I')
            kv[k] = _rval(f, t, keep_arrays=False)
        for _ in range(nt):
            name = _rstr(f)
            (nd,) = _rd(f, 'I')
            dims = list(_rd(f, 'Q' * nd))
            (tt,) = _rd(f, 'I')
            _rd(f, 'Q')  # offset
            tensors[name] = (dims, GGML_TYPES.get(tt, str(tt)))
    return kv, tensors


def load_model(model_dir):
    files = sorted(glob.glob(os.path.join(model_dir, '*.gguf')))
    files = [p for p in files if 'mmproj' not in os.path.basename(p) and 'dspark' not in os.path.basename(p)]
    if not files:
        sub = sorted(glob.glob(os.path.join(model_dir, '*', '*-00001-of-*.gguf')))
        if sub:
            files = sorted(glob.glob(os.path.join(os.path.dirname(sub[0]), '*.gguf')))
    if not files:
        raise SystemExit('no GGUF files under ' + model_dir)
    kv, tensors = {}, {}
    for p in files:
        k, t = read_gguf_header(p)
        for a, b in k.items():
            kv.setdefault(a, b)
        tensors.update(t)
    return kv, tensors, files


# ----------------------------------------------------------------------------------------------------------
# Row bytes as the engine stores them (kernels/pack_v41.hpp: packed_row_bytes; unpacked = GGUF row)
# ----------------------------------------------------------------------------------------------------------
def pad16(n):
    return (n + 15) // 16 * 16


def packed_row_bytes(ty, cols):
    nb = cols // 256
    if ty == 'Q8_0':
        c = cols // 32
        return pad16(c * 32 + c * 2)
    if ty == 'IQ2_XXS':
        return pad16(nb * 70)
    if ty == 'IQ2_S':
        return pad16(nb * 82)
    if ty == 'IQ3_XXS':
        return pad16(nb * 98)
    if ty == 'IQ1_S':
        return pad16(nb * 50)
    if ty == 'IQ2_XS':
        return pad16(nb * 74)
    if ty == 'Q6_K':
        return pad16(nb * 210)
    if ty == 'Q5_K':
        return pad16(nb * 176)
    if ty == 'F32':
        return pad16(cols * 2)  # the router rows: upper halves only (exact in 16 bits)
    if ty == 'MXFP4':
        return pad16(cols // 2 + cols // 32)
    return gguf_row_bytes(ty, cols)


def gguf_row_bytes(ty, cols):
    be, bb = GGUF_BLOCK[ty]
    return cols // be * bb


# ----------------------------------------------------------------------------------------------------------
# The engine's slicing (tp_setup / tp_rows / head_layout) for OWN_TP=6
# ----------------------------------------------------------------------------------------------------------
class Geometry:
    def __init__(self, kv, tensors):
        a = kv.get('general.architecture', 'deepseek41')
        g = lambda k, d=None: kv.get(a + '.' + k, d)
        self.layers = int(g('block_count', 40))
        self.h = int(g('embedding_length', 5120))
        self.qh = int(g('attention.head_count', 64))
        self.hd = int(g('attention.key_length', 512))
        self.qrank = int(g('attention.q_lora_rank', 1280))
        self.mid = int(g('expert_feed_forward_length', 2304))
        self.experts = int(g('expert_count', 384))
        self.used = int(g('expert_used_count', 6))
        self.ogroups = int(g('attention.output_group_count', 8))
        self.orank = int(g('attention.output_lora_rank', 1024))
        self.ototal = self.ogroups * self.orank
        self.oin = self.qh // self.ogroups * self.hd
        cr = g('attention.compress_ratios', [])
        self.cr = [int(x) for x in cr] if isinstance(cr, list) else [0] * self.layers
        self.kv_src = [int(x) for x in g('attention.kv_source_layers', [2, 8, 14, 20])]
        self.idx_src = [int(x) for x in g('attention.indexer.source_layers', [2, 8, 14, 20, 24, 28, 32, 36])]
        self.ple = [int(x) for x in g('ple.layers', [1, 14])]
        self.vocab = int(tensors['output.weight'][0][1])
        self.t = tensors

    def ty(self, name):
        return self.t[name][1]

    def shape(self, name):
        d = self.t[name][0]
        return d[0], (d[1] if len(d) > 1 else 1)  # cols, rows


class Slicing:
    """Per-card row ranges (tp_setup with equal OWN_TP_WEIGHTS) and the two head layouts."""

    def __init__(self, G, n=6, prompt_heads=(3, 3, 3, 3, 2, 2)):
        self.n = n
        self.G = G

        def split(total, c, al=16):
            u = total // al
            a = (u * c // n) * al
            b = total if c + 1 == n else (u * (c + 1) // n) * al
            return a, b
        self.tm = [split(G.mid, c) for c in range(n)]
        self.td = [split(G.h, c) for c in range(n)]
        self.tv = [split(G.vocab, c) for c in range(n)]
        self.te = [split(5 * G.h, c) for c in range(n)]
        U = G.qh // 4
        ur = G.ototal // U

        def layout(units):
            hq, oa = [], []
            for c in range(n):
                u0, u1 = units[c], units[c + 1]
                hq.append((4 * u0, 4 * u1))
                oa.append((u0 * ur, u1 * ur))
            return hq, oa
        whole = [2 * (8 * c // n) for c in range(n + 1)]  # hl[0]: one-token steps (whole groups of 8 heads)
        self.hq_dec, self.oa_dec = layout(whole)
        pu = [0]
        for x in prompt_heads:
            pu.append(pu[-1] + x)
        self.hq_pre, self.oa_pre = layout(pu)  # hl[2]: blocks of >= 16 tokens (OWN_TP_HEADS default)

    @staticmethod
    def rows(r):
        return r[1] - r[0]


# ----------------------------------------------------------------------------------------------------------
# Kernel names as the profile prints them (demangled, "ops41sycl::" dropped). Compared without spaces.
# ----------------------------------------------------------------------------------------------------------
def T(name, *args):
    return '%s<%s>' % (name, ', '.join(args))


def nkey(s):
    return s.replace(' ', '')


def dense_k(ty, cols):
    if ty == 'Q8_0':
        return T('GemvQ8P', '%du' % (cols // 32), 'ActF32')
    if ty == 'Q6_K':
        return T('GemvQ6KP', '%du' % (cols // 256), 'ActF32')
    if ty == 'Q5_K':
        return T('GemvQ5KP', '%du' % (cols // 256), 'ActF32')
    if ty in ('F32', 'BF16'):
        return T('GemvH16P', '%du' % (cols // 32), 'ActF32')
    raise ValueError('dense kernel for ' + ty)


RFMT = {'IQ2_XXS': 'IQ2XXS', 'IQ2_S': 'IQ2S', 'IQ3_XXS': 'IQ3XXS', 'IQ2_XS': 'IQ2XS', 'IQ1_S': 'IQ1S'}


def routed_k(ty, nb):
    if ty == 'Q2_K':
        return T('RoutedQ2KF', '%du' % nb)
    if ty == 'IQ1_S':
        return T('RoutedIQ1SP', '%du' % nb, 'ActF32', 'true', 'NoRows')
    return T('Routed%sP' % RFMT[ty], '%du' % nb, 'ActF32', 'NoRows')


DR = lambda k: T('DenseRows', k)
RP = lambda a, b: T('RowsPair', a, b)
HCD = T('HcDotsRows', '5120u', '8u')
NORM5120 = T('NormRows', '5120u', '4u')
ROPE = T('RopeRows', 'ActF32')

WEIGHT_ROLES = {'routed gate+up', 'routed down', 'q_a + kv', 'q_a + kv + mix dots', 'q_b', 'output-a', 'output-b',
                'router logits + compressor', 'router logits', 'route pick + shared gate/up', 'shared down',
                'head', 'engram kv', 'indexer k', 'kv', 'q_a + mix dots', 'router logits + mix dots',
                'compressor + indexer proj', 'indexer q_b', 'expert rows'}
SMALL_ROLES = {'norm + mix dots', 'q_a/kv norms', 'q rope', 'stream post+collapse', 'stream post', 'stream collapse',
               'swiglu', 'moe combine', 'engram gate', 'engram rows decode', 'norm', 'compress pool', 'argmax',
               'to f32', 'publish append', 'rope pairs', 'small'}
ATT_ROLES = {'attention score', 'attention softmax', 'attention output', 'window append', 'index fill', 'index score',
             'index top-k', 'ring commit', 'attention'}


def cat_of(role):
    if role.startswith('exchange'):
        return 'exchanges'
    if role in WEIGHT_ROLES:
        return 'weights'
    if role in ATT_ROLES:
        return 'attention'
    return 'small serial ops'


class Acc:
    """Predicted launches of one kernel type on one card: totals per step."""

    def __init__(self, name, role):
        self.name, self.role = name, role
        self.n = 0.0
        self.wb = 0.0  # weight bytes per step
        self.ab = 0.0  # activation / cache bytes per step
        self.xb = 0.0  # bytes over the card-to-card link per step
        self.macs = 0.0  # multiply-adds per step (prompt compute floor)
        self.parts = defaultdict(float)  # role detail -> weight bytes

    def add(self, n=1.0, wb=0.0, ab=0.0, xb=0.0, macs=0.0, part=None):
        self.n += n
        self.wb += n * wb
        self.ab += n * ab
        self.xb += n * xb
        self.macs += n * macs
        if part:
            self.parts[part] += n * wb


class Model:
    def __init__(self):
        self.k = OrderedDict()

    def add(self, name, role, **kw):
        key = nkey(name)
        if key not in self.k:
            self.k[key] = Acc(name, role)
        a = self.k[key]
        if a.role != role and role not in a.role.split(' | '):
            a.role = a.role + ' | ' + role
        a.add(**kw)


# ----------------------------------------------------------------------------------------------------------
# One-token answer step on card c (tp_card_step / tp_phase / tp_head with the round-18 defaults)
# ----------------------------------------------------------------------------------------------------------
def decode_model(G, S, c, ctx_len):
    M = Model()
    t = G.t
    F4 = 4
    td = S.rows(S.td[c])
    tm = S.rows(S.tm[c])
    nh = S.rows(S.hq_dec[c])
    oa_rows = S.rows(S.oa_dec[c])
    others = [d for d in range(S.n) if d != c]
    hcfn = 24 * 4 * G.h * 4  # hc_*_fn.weight: 24 rows x 20480 F32
    streams = 4 * G.h * F4
    rb = lambda name, cols: packed_row_bytes(G.ty(name), cols)

    def xpull(nslot, rng):  # bytes this card loads from its peers
        return nslot * sum(S.rows(rng[d]) for d in others) * F4

    def xpush(nslot, own):  # bytes this card stores into its peers
        return nslot * own * F4 * len(others)

    def pull_or_push(nslot, rng):
        return max(S.rows(rng[d]) for d in range(S.n)) * nslot * 4 >= 8192  # use_pull, OWN_XPULL_MIN=8192

    def xchg(nslot, rng, label):
        if pull_or_push(nslot, rng):
            M.add('XchgPull', 'exchange (pull)', xb=xpull(nslot, rng), part=label)
        else:
            M.add('XchgP', 'exchange (push)', xb=xpush(nslot, S.rows(rng[c])), part=label)

    # engram rows (eng_late: after layer 0's launches) + their split projection, pushed at once
    def engram_kv():
        for L in G.ple:
            n = 'blk.%d.engram_kv.weight' % L
            cols, _ = G.shape(n)
            M.add('EngRowsA<ActF32>', 'engram rows decode', ab=24 * 176 + 24 * 256 * F4)
            M.add(dense_k(G.ty(n), cols), 'engram kv', wb=S.rows(S.te[c]) * rb(n, cols),
                  ab=cols * F4 + S.rows(S.te[c]) * F4, macs=S.rows(S.te[c]) * cols, part='engram_kv')
        M.add('XchgPull', 'exchange (pull)', xb=0, part='engram (flags only)')

    x_ready = False
    for L in range(G.layers):
        if L == 1:
            engram_kv()
        p = 'blk.%d.' % L
        q8 = G.ty(p + 'attn_q_a.weight')
        cr = G.cr[L] if L < len(G.cr) else 0
        # ---- phase 0
        if L in G.ple:
            M.add('XchgPull', 'exchange (pull)', xb=xpull(2, S.te), part='engram rows')
            M.add('EngramGateP', 'engram gate', ab=2 * streams + 5 * G.h * F4 + 4 * G.h * F4)
        qa_rows = G.shape(p + 'attn_q_a.weight')[1] + G.shape(p + 'attn_kv.weight')[1]
        qa_w = qa_rows * rb(p + 'attn_q_a.weight', G.h)
        pair = RP(DR(dense_k(q8, G.h)), DR(dense_k(q8, G.h)))
        if x_ready:
            M.add(T('RowsP', RP(NORM5120, HCD)), 'norm + mix dots', wb=hcfn, ab=streams + 3 * G.h * F4,
                  part='hc_attn_fn (replicated)')
            M.add(T('RowsP', RP('NoRows', pair)), 'q_a + kv', wb=qa_w, ab=G.h * F4 + qa_rows * F4,
                  macs=qa_rows * G.h, part='q_a + kv (replicated)')
        else:
            M.add('HcPreA<ActF32>', 'stream collapse', ab=streams + G.h * F4)
            M.add(T('RmsNormPS', '5120u', '4u'), 'norm', ab=3 * G.h * F4)
            M.add(T('RowsP', RP(HCD, pair)), 'q_a + kv + mix dots', wb=qa_w + hcfn,
                  ab=G.h * F4 + qa_rows * F4 + streams, macs=qa_rows * G.h, part='q_a + kv + hc_attn_fn (replicated)')
        M.add(T('RowsP', RP(T('NormRows', '1280u', '4u'), T('NormRows', '512u', '2u'))), 'q_a/kv norms',
              ab=3 * qa_rows * F4)
        qb_rows = nh * G.hd
        M.add(T('RowsP', RP(RP('HcFinishRows', ROPE), DR(dense_k(q8, G.qrank)))), 'q_b',
              wb=qb_rows * rb(p + 'attn_q_b.weight', G.qrank), ab=G.qrank * F4 + qb_rows * F4,
              macs=qb_rows * G.qrank, part='q_b (heads)')
        M.add(T('RowsP', ROPE), 'q rope', ab=2 * nh * 64 * F4)
        if cr and L in G.kv_src:
            # publish_tp (per step averages: ratio-2 layers pool every other position)
            nbf = 512 * G.h * 2
            if cr == 1:
                M.add(T('GemvH16P', '160u', 'ActF32'), 'router logits + compressor', wb=nbf, ab=G.h * F4,
                      macs=512 * G.h, part='compressor (replicated)')
                M.add(T('RmsNormPS', '512u', '2u'), 'norm', ab=3 * 512 * F4)
                f = 1.0
            else:
                M.add(T('GemvH16P', '160u', 'ActF32'), 'router logits + compressor', n=2, wb=nbf, ab=G.h * F4,
                      macs=512 * G.h, part='compressor (replicated)')
                M.add('ToF32A<ActF32>', 'to f32', n=2, ab=2 * 512 * F4)
                M.add('CompressPoolP<ActF32>', 'compress pool', n=0.5, ab=4 * 512 * F4)
                f = 0.5
            M.add(T('GemvH16P', '16u', 'ActF32'), 'indexer k', n=f, wb=128 * 512 * 2, ab=512 * F4, macs=128 * 512,
                  part='indexer attn_k (replicated)')
            M.add('RmsNormA<ActF32>', 'norm', n=f, ab=3 * 128 * F4)
            M.add('RopePairsA<ActF32>', 'rope pairs', n=2 * f, ab=2 * 576 * F4)
            M.add('PubAppendA<ActF32>', 'publish append', n=f, ab=(512 + 128) * (F4 + 2))
        if cr and L in G.idx_src:
            M.add('CidxFill', 'index fill', ab=512 * 4)  # short context path (<= 512 compressed rows)
        # ---- phase 1: attention
        clen = 0 if not cr else max(1, ctx_len // cr)
        n_idx = 128 if not cr else (128 + max(32, (clen + 31) // 32 * 32) if clen < 512 else 640)
        keys = n_idx * G.hd * 2
        M.add('WindowAppendP<ActF32>', 'window append', ab=G.hd * (F4 + 2) + n_idx * 4)
        if n_idx == 128:
            M.add(T('SparseScoreP', '512u'), 'attention score', ab=nh * G.hd * F4 + keys + nh * n_idx * F4)
            M.add(T('SparseSoftmaxP', '128'), 'attention softmax', ab=2 * nh * n_idx * F4)
        else:
            M.add(T('SparseScoreHG', '512u', '4u'), 'attention score', ab=nh * G.hd * F4 + keys + nh * n_idx * F4)
            M.add(T('SparseSoftmaxPN', '640'), 'attention softmax', ab=2 * nh * n_idx * F4)
        M.add(T('SparseOutJC', '512u', '16u', '128u', '16u'), 'attention output',
              ab=keys + nh * n_idx * F4 + nh * G.hd * F4)
        M.add(dense_k(q8, G.oin), 'output-a',
              wb=oa_rows * rb(p + 'attn_output_a.weight', G.oin), ab=(oa_rows // G.orank) * G.oin * F4 + oa_rows * F4,
              macs=oa_rows * G.oin, part='output-a (heads)')
        xchg(1, S.oa_dec, 'output-a rows')
        # ---- phase 2
        M.add(dense_k(q8, G.ototal), 'output-b', wb=td * rb(p + 'attn_output_b.weight', G.ototal),
              ab=G.ototal * F4 + td * F4, macs=td * G.ototal, part='output-b')
        xchg(1, S.td, 'output-b rows')
        # ---- phase 3
        M.add('HcPostPreP<ActF32>', 'stream post+collapse', ab=2 * streams + 2 * G.h * F4)
        M.add(T('RowsP', RP(NORM5120, HCD)), 'norm + mix dots', wb=hcfn, ab=streams + 3 * G.h * F4,
              part='hc_ffn_fn (replicated)')
        ri = p + 'ffn_gate_inp.weight'
        M.add(T('GemvH16P', '160u', 'ActF32'), 'router logits + compressor', wb=G.experts * rb(ri, G.h),
              ab=G.h * F4 + G.experts * F4, macs=G.experts * G.h, part='router (replicated)')
        sty = G.ty(p + 'ffn_gate_shexp.weight')
        M.add(T('RoutePRows', RP('HcFinishRows', RP(DR(dense_k(sty, G.h)), DR(dense_k(sty, G.h))))),
              'route pick + shared gate/up', wb=2 * tm * rb(p + 'ffn_gate_shexp.weight', G.h),
              ab=G.h * F4 + 2 * G.experts * F4 + 2 * tm * F4, macs=2 * tm * G.h, part='shared gate/up')
        ety = G.ty(p + 'ffn_up_exps.weight')
        M.add(routed_k(ety, G.h // 256), 'routed gate+up',
              wb=G.used * 2 * tm * rb(p + 'ffn_up_exps.weight', G.h), ab=G.h * F4 + 2 * G.used * tm * F4,
              macs=G.used * 2 * tm * G.h, part='experts gate/up (%s)' % ety)
        M.add('SwigluBothS<ActF32>', 'swiglu', ab=3 * 7 * tm * F4)
        xchg(7, S.tm, 'expert activations')
        # ---- phase 4
        dty = G.ty(p + 'ffn_down_exps.weight')
        drow = packed_row_bytes(dty, G.mid) if dty != 'Q2_K' else gguf_row_bytes(dty, G.mid)
        M.add(routed_k(dty, G.mid // 256), 'routed down', wb=G.used * td * drow,
              ab=G.used * G.mid * F4 + G.used * td * F4, macs=G.used * td * G.mid, part='experts down (%s)' % dty)
        M.add(dense_k(G.ty(p + 'ffn_down_shexp.weight'), G.mid), 'shared down',
              wb=td * rb(p + 'ffn_down_shexp.weight', G.mid), ab=G.mid * F4 + td * F4, macs=td * G.mid,
              part='shared down')
        M.add('MoeCombineA<ActF32>', 'moe combine', ab=8 * td * F4)
        xchg(1, S.td, 'ffn rows')
        # ---- phase 5
        Ln = L + 1
        if Ln not in G.ple:
            M.add('HcPostPreP<ActF32>', 'stream post+collapse', ab=2 * streams + 2 * G.h * F4)
            x_ready = True
        else:
            M.add('HcPostP<ActF32>', 'stream post', ab=2 * streams + G.h * F4)
            x_ready = False
    # head
    M.add(T('RmsNormPS', '5120u', '4u'), 'norm', ab=3 * G.h * F4)
    nl = S.rows(S.tv[c])
    M.add(dense_k(G.ty('output.weight'), G.h), 'head', wb=nl * packed_row_bytes(G.ty('output.weight'), G.h),
          ab=G.h * F4 + nl * F4, macs=nl * G.h, part='head (vocab rows)')
    M.add('ArgmaxP1O', 'argmax', ab=nl * F4)
    return M


# ----------------------------------------------------------------------------------------------------------
# Prompt block (backend_sycl_v41_mt.inc, blocks of 16, heads 12,12,12,12,8,8): kernels classified by name
# ----------------------------------------------------------------------------------------------------------
def prompt_role(name):
    n = nkey(name)
    # the one-token kernels (the answer step after the read; their block forms carry M / TokRows / DenseRowsG)
    one = (r'^(RowsP<RowsPair<NormRows<5120u,4u>,HcDotsRows|RowsP<RowsPair<RowsPair<HcFinishRows|RowsP<RowsPair<NoRows'
           r'|RowsP<RowsPair<HcDotsRows|RowsP<RowsPair<NormRows<1280u|RowsP<RopeRows|RoutePRows<|Routed\w+P<|Gemv'
           r'|SparseScore|SparseSoftmax|SparseOut|HcPostPreP<|HcPostP<|HcPreA<|MoeCombineA<|SwigluBothS<'
           r'|WindowAppendP<|CidxFill$|EngramGateP$|CompressPoolP<|PubAppendA<|RmsNormPS<|ArgmaxP1O)')
    if re.search(one, n):
        return 'answer step'
    rules = [
        (r'^Xchg(Pull|P)$', 'exchange'), (r'^XchgPair', 'exchange (head pairs)'),
        (r'RoutedU<RUFmt\w+<20u', 'routed gate+up'), (r'RoutedU<RUFmt\w+<9u', 'routed down'),
        (r'^RoutedQ2KF<9u>', 'routed down'),
        (r'TokRows<HcDotsRows.*GemvH16P<160u', 'router logits + mix dots'),
        (r'TokRows<HcDotsRows.*Gemv(Q8P<160u|Q6KP<20u)', 'q_a + mix dots'),
        (r'^RoutePMRows', 'route pick + shared gate/up'),
        (r'^RowsP<DenseRowsG<Gemv(Q8P<40u|Q6KP<5u)', 'q_b'),
        (r'^RowsP<DenseRowsG<Gemv(Q8P<128u|Q6KP<16u)', 'output-a'),
        (r'^RowsP<DenseRowsG<Gemv(Q8P<256u|Q6KP<32u)', 'output-b'),
        (r'^RowsP<DenseRowsG<Gemv(Q8P<72u|Q5KP<9u)', 'shared down'),
        (r'^RowsP<DenseRowsG<Gemv(Q8P<160u|Q6KP<20u)', 'kv'),
        (r'^RowsP<DenseRowsG<GemvQ6KP<24u', 'engram kv'),
        (r'^RowsP<DenseRowsG<GemvH16P<160u', 'compressor + indexer proj'),
        (r'^RowsP<DenseRowsG<GemvH16P<40u', 'indexer q_b'),
        (r'^RowsP<DenseRowsG<GemvH16P<16u', 'indexer k'),
        (r'^(ExpertGroupM)', 'expert grouping'),
        (r'^(OutM|SparseOut)', 'attention output'), (r'^(ScoreM|SparseScore)', 'attention score'),
        (r'^(SoftmaxM|SparseSoftmax)', 'attention softmax'), (r'^(WindowAppend)', 'window append'),
        (r'^RingCommit', 'ring commit'), (r'^Cidx', 'index fill'), (r'^Indexer', 'index score'),
        (r'^TopKSel', 'index top-k'),
        (r'NormRows<5120u', 'norm'), (r'NormRows<1280u', 'q_a/kv norms'), (r'NormRows<512u', 'norm'),
        (r'^HcPostPre', 'stream post+collapse'), (r'^HcPost', 'stream post'), (r'^HcPre', 'stream collapse'),
        (r'^MoeCombine', 'moe combine'), (r'^Swiglu', 'swiglu'), (r'^EngramGate', 'engram gate'),
        (r'^EngRows', 'engram rows decode'), (r'^CompressPool', 'compress pool'), (r'RopeRows|RopePairs', 'q rope'),
        (r'^(EmbedRow|Broadcast4)', 'small'), (r'^(RmsNorm)', 'norm'), (r'^(StatePack|PubAppend|ToF32)', 'small'),
        (r'^Argmax', 'argmax'),
    ]
    for rx, role in rules:
        if re.search(rx, n):
            return role
    return 'small'


def prompt_bytes(G, S, c, role, mt, distinct):
    """(weight bytes, multiply-adds) per block of mt tokens for the role on card c, summed over layers."""
    tm, td = S.rows(S.tm[c]), S.rows(S.td[c])
    nh = S.rows(S.hq_pre[c])
    oa = S.rows(S.oa_pre[c])
    hcfn = 24 * 4 * G.h * 4
    wb = mac = 0.0
    per_layer = defaultdict(float)
    for L in range(G.layers):
        p = 'blk.%d.' % L
        q8 = G.ty(p + 'attn_q_a.weight')
        rb = lambda n, cols: packed_row_bytes(G.ty(n), cols)
        if role == 'routed gate+up':
            ty = G.ty(p + 'ffn_up_exps.weight')
            wb += distinct * 2 * tm * packed_row_bytes(ty, G.h)
            mac += mt * G.used * 2 * tm * G.h
        elif role == 'routed down':
            ty = G.ty(p + 'ffn_down_exps.weight')
            r = packed_row_bytes(ty, G.mid) if ty != 'Q2_K' else gguf_row_bytes(ty, G.mid)
            wb += distinct * td * r
            mac += mt * G.used * td * G.mid
        elif role == 'router logits + mix dots':
            wb += G.experts * rb(p + 'ffn_gate_inp.weight', G.h) + hcfn
            mac += mt * (G.experts * G.h + 24 * 4 * G.h)
        elif role == 'q_a + mix dots':
            wb += G.qrank * rb(p + 'attn_q_a.weight', G.h) + hcfn
            mac += mt * (G.qrank * G.h + 24 * 4 * G.h)
        elif role == 'kv':
            wb += G.hd * rb(p + 'attn_kv.weight', G.h)
            mac += mt * G.hd * G.h
        elif role == 'q_b':
            wb += nh * G.hd * rb(p + 'attn_q_b.weight', G.qrank)
            mac += mt * nh * G.hd * G.qrank
        elif role == 'output-a':
            wb += oa * rb(p + 'attn_output_a.weight', 4096)
            mac += mt * oa * 4096
        elif role == 'output-b':
            wb += td * rb(p + 'attn_output_b.weight', G.ototal)
            mac += mt * td * G.ototal
        elif role == 'route pick + shared gate/up':
            wb += 2 * tm * rb(p + 'ffn_gate_shexp.weight', G.h)
            mac += mt * 2 * tm * G.h
        elif role == 'shared down':
            wb += td * rb(p + 'ffn_down_shexp.weight', G.mid)
            mac += mt * td * G.mid
        elif role == 'engram kv' and L in G.ple:
            n = p + 'engram_kv.weight'
            cols, _ = G.shape(n)
            wb += S.rows(S.te[c]) * rb(n, cols)
            mac += mt * S.rows(S.te[c]) * cols
        elif role == 'compressor + indexer proj':
            cr = G.cr[L] if L < len(G.cr) else 0
            if cr and L in G.kv_src:
                k = 1 if cr == 1 else 2
                wb += k * 512 * G.h * 2
                mac += mt * k * 512 * G.h
            if cr and L in G.idx_src:
                wb += 32 * G.h * 2
                mac += mt * 32 * G.h
        elif role == 'indexer q_b' and (L in G.idx_src):
            wb += 4096 * G.qrank * 2
            mac += mt * 4096 * G.qrank
        elif role == 'indexer k' and L in G.kv_src and (G.cr[L] if L < len(G.cr) else 0):
            wb += 128 * 512 * 2
            mac += mt * 128 * 512
    return wb, mac


# ----------------------------------------------------------------------------------------------------------
# Profile parsing
# ----------------------------------------------------------------------------------------------------------
KLINE = re.compile(r'^\s+([0-9.]+)\s+[0-9.]+%\s+([0-9.]+)\s+([0-9.]+) us\s+(\S.*)$')
MLINE = re.compile(r'^\s+(\w+)\s+([0-9.]+)\s+[0-9.]+%\s+\((\d+) marks/step\)')


def parse_profile(path):
    P = {'path': path, 'marks': OrderedDict(), 'kernels': OrderedDict(), 'marks_total': None, 'wall': None,
         'ktotal': None, 'launches': None, 'gaps': None, 'tok_s': None, 'steps': None, 'prompt_tokens': None,
         'prompt_s': None, 'header': ''}
    sec = None
    with open(path, errors='replace') as f:
        for ln in f:
            if ln.startswith('#'):
                P['header'] += ln
            m = re.search(r'prompt: (\d+) tokens read on the cards in ([0-9.]+)s', ln)
            if m:
                P['prompt_tokens'], P['prompt_s'] = int(m.group(1)), float(m.group(2))
            m = re.search(r'decode: (\d+) steps after the first, [0-9.]+ s/step, ([0-9.]+) tok/s', ln)
            if m:
                P['steps'], P['tok_s'] = int(m.group(1)), float(m.group(2))
            if ln.startswith('GPU-time profile'):
                sec = 'marks'
                continue
            if ln.startswith('kernel time per type'):
                sec = 'kernels'
                continue
            if sec == 'marks':
                m = re.match(r'^\s+total\s+([0-9.]+)\s+\(wall ([0-9.]+)\)', ln)
                if m:
                    P['marks_total'], P['wall'] = float(m.group(1)), float(m.group(2))
                    continue
                m = MLINE.match(ln)
                if m:
                    P['marks'][m.group(1)] = (float(m.group(2)), int(m.group(3)))
            elif sec == 'kernels':
                m = re.match(r'^\s+kernels\s+([0-9.]+) ms, launches (\d+) per step; marks total ([0-9.-]+) -> '
                             r'gaps/copies ([0-9.-]+) ms', ln)
                if m:
                    P['ktotal'], P['launches'] = float(m.group(1)), int(m.group(2))
                    P['gaps'] = float(m.group(4))
                    sec = None
                    continue
                m = KLINE.match(ln)
                if m:
                    ms, us, name = float(m.group(1)), float(m.group(3)), m.group(4).strip()
                    n = ms * 1e3 / us if us > 0 else float(m.group(2))
                    P['kernels'][name] = {'ms': ms, 'us': us, 'n': n}
    return P


def card_of(path, default=None):
    b = os.path.basename(path)
    m = re.search(r'(?:_c|card)(\d)', b)
    return int(m.group(1)) if m else default


# ----------------------------------------------------------------------------------------------------------
# Ledger
# ----------------------------------------------------------------------------------------------------------
def fmt_b(b):
    if b >= 1e9:
        return '%.2f GB' % (b / 1e9)
    if b >= 1e6:
        return '%.2f MB' % (b / 1e6)
    if b >= 1e3:
        return '%.1f KB' % (b / 1e3)
    return '%d B' % b


def short(name, n=58):
    return name if len(name) <= n else name[:n - 3] + '...'


class Ledger:
    def __init__(self, a, G, S):
        self.a, self.G, self.S = a, G, S
        self.out = []
        self.data = {}

    def w(self, s=''):
        self.out.append(s)

    def floor_us(self, acc, per_launch=True):
        n = acc.n if acc.n else 1.0
        wb, ab, xb = acc.wb / n, acc.ab / n, acc.xb / n
        if acc.role.startswith('exchange'):
            return self.a.xchg_sync_us + xb / (self.a.link_gbs * 1e3)
        return (wb + ab) / (self.a.bw * 1e3)

    # ---------------- decode ----------------
    def decode(self, profs, real_ms, ctx_len):
        a, G, S = self.a, self.G, self.S
        cards = sorted(profs)
        rows = {}  # card -> list of row dicts
        unmatched = {}
        cat_tot = {}
        models = {}
        for c in cards:
            P = profs[c]
            M = decode_model(G, S, c, ctx_len)
            models[c] = M
            seen = set()
            rr = []
            for name, k in P['kernels'].items():
                key = nkey(name)
                acc = M.k.get(key)
                if acc is None:  # e.g. kernels renamed by a newer build: classify, no bytes
                    acc = Acc(name, prompt_role(name) if not name.startswith('Xchg') else 'exchange (pull)')
                    acc.n = k['n']
                    unmatched.setdefault(c, []).append(name)
                seen.add(key)
                fl = self.floor_us(acc)
                fl_ms = fl * k['n'] / 1e3
                stand = max(fl, a.launch_us) * k['n'] / 1e3
                byt = (acc.wb + acc.ab + acc.xb) / (acc.n or 1)
                rr.append({'name': name, 'role': acc.role, 'cat': cat_of(acc.role), 'n': k['n'], 'pred_n': acc.n,
                           'us': k['us'], 'ms': k['ms'], 'wb': acc.wb / (acc.n or 1), 'ab': acc.ab / (acc.n or 1),
                           'xb': acc.xb / (acc.n or 1), 'bytes': byt, 'floor_us': fl, 'floor_ms': fl_ms,
                           'gap_ms': k['ms'] - fl_ms, 'stand_ms': stand,
                           'gbs': (acc.wb + acc.ab) / (acc.n or 1) / (k['us'] * 1e3) if k['us'] else 0,
                           'parts': dict(acc.parts)})
            missing = [M.k[k].name for k in M.k if k not in seen and M.k[k].n >= 1]
            if missing:
                unmatched.setdefault(c, []).extend('(predicted, not in profile) ' + m for m in missing)
            rows[c] = rr
            kt = sum(r['ms'] for r in rr)
            ct = defaultdict(float)
            cf = defaultdict(float)
            cs = defaultdict(float)
            for r in rr:
                ct[r['cat']] += r['ms']
                cf[r['cat']] += r['floor_ms']
                cs[r['cat']] += r['stand_ms']
            # idle time on the card between kernels: the profile's own number (inflated by its barriers) and the
            # estimate against the unprofiled step (kernel durations assumed the same with and without profiling)
            ct['gaps, profiled (marks - kernels)'] = P['marks_total'] - kt if P['marks_total'] else 0.0
            ct['gaps, real (real step - kernels)'] = max(0.0, real_ms - kt) if real_ms else 0.0
            ct['profiling inflation (profiled wall - real)'] = (P['wall'] or 0) - real_ms if real_ms else 0.0
            cat_tot[c] = (ct, cf, kt, P, cs)
        self.data['decode'] = {'rows': rows, 'cat': {c: (dict(v[0]), dict(v[1])) for c, v in cat_tot.items()}}

        # ---------- header
        self.w('## Answer step (one token), %d cards profiled' % len(cards))
        self.w()
        b_c = {c: sum(r['wb'] * r['n'] for r in rows[c]) for c in cards}
        a_c = {c: sum(r['ab'] * r['n'] for r in rows[c]) for c in cards}
        x_c = {c: sum(r['xb'] * r['n'] for r in rows[c]) for c in cards}
        self.w('Real step (unprofiled, `plain.log`): **%.2f ms** (%.1f tok/s). Profiled walls: %s ms.' % (
            real_ms, 1e3 / real_ms if real_ms else 0,
            ', '.join('c%d %.2f' % (c, cat_tot[c][3]['wall'] or 0) for c in cards)))
        self.w('Context for the attention bytes: %d positions. Floors: weights/activations at %.0f GB/s; '
               'exchanges %.1f us sync + bytes at %.0f GB/s; standalone launch %.1f us.' % (
                   ctx_len, a.bw, a.xchg_sync_us, a.link_gbs, a.launch_us))
        self.w()
        self.w('| card | weight bytes / step | activation bytes | link bytes | weight floor ms | all-bytes floor ms |'
               ' kernels ms | launches |')
        self.w('|---|---|---|---|---|---|---|---|')
        for c in cards:
            P = cat_tot[c][3]
            self.w('| %d | %s | %s | %s | %.2f | %.2f | %.2f | %s |' % (
                c, fmt_b(b_c[c]), fmt_b(a_c[c]), fmt_b(x_c[c]), b_c[c] / (a.bw * 1e6),
                (b_c[c] + a_c[c]) / (a.bw * 1e6), cat_tot[c][2], P['launches']))
        self.w()
        # replicated share
        M0 = models[cards[0]]
        rep = defaultdict(float)
        for acc in M0.k.values():
            for part, b in acc.parts.items():
                if 'replicated' in part:
                    rep[part] += b
        rep_tot = sum(rep.values())
        self.data['decode']['replicated_bytes'] = rep_tot
        self.w('Replicated reads (every card reads the whole tensor each step): %s per card (%.2f ms at the floor): %s.'
               % (fmt_b(rep_tot), rep_tot / (a.bw * 1e6),
                  '; '.join('%s %s' % (k.replace(' (replicated)', ''), fmt_b(v)) for k, v in
                            sorted(rep.items(), key=lambda x: -x[1]))))
        self.w()

        # ---------- per kernel type (the slowest card's view + spread)
        self.w('### Per kernel type (ms per step, mean over cards; us/launch and floor ranges over the cards)')
        self.w()
        self.w('| kernel | role | cat | launches | us/launch (min-max) | ms/step mean | bytes/launch (c0) | floor us |'
               ' floor ms | gap ms (mean) | GB/s (c0) |')
        self.w('|---|---|---|---|---|---|---|---|---|---|---|')
        byname = OrderedDict()
        for c in cards:
            for r in rows[c]:
                byname.setdefault(nkey(r['name']), {})[c] = r
        items = []
        for key, per in byname.items():
            rs = list(per.values())
            ms_mean = sum(r['ms'] for r in rs) / len(rs)
            gap_mean = sum(r['gap_ms'] for r in rs) / len(rs)
            gap_max = max(r['gap_ms'] for r in rs)
            r0 = per.get(cards[0], rs[0])
            items.append((ms_mean, key, per, gap_mean, gap_max))
        items.sort(key=lambda x: -x[0])
        self.data['decode']['kernels'] = []
        for ms_mean, key, per, gap_mean, gap_max in items:
            rs = list(per.values())
            r0 = per.get(cards[0], rs[0])
            us_min, us_max = min(r['us'] for r in rs), max(r['us'] for r in rs)
            fl_min, fl_max = min(r['floor_us'] for r in rs), max(r['floor_us'] for r in rs)
            fl_ms = sum(r['floor_ms'] for r in rs) / len(rs)
            self.w('| `%s` | %s | %s | %.1f | %.2f-%.2f | %.3f | %s | %s | %.3f | %.3f | %s |' % (
                short(r0['name'], 70), r0['role'], r0['cat'], r0['n'], us_min, us_max, ms_mean, fmt_b(r0['bytes']),
                ('%.2f' % fl_min) if abs(fl_max - fl_min) < 0.05 else '%.2f-%.2f' % (fl_min, fl_max), fl_ms, gap_mean,
                ('%.0f' % r0['gbs']) if r0['cat'] in ('weights',) or r0['wb'] > 1e5 else '-'))
            self.data['decode']['kernels'].append({'name': r0['name'], 'role': r0['role'], 'cat': r0['cat'],
                                                   'n': r0['n'], 'ms_mean': ms_mean, 'gap_mean': gap_mean,
                                                   'gap_max': gap_max, 'floor_ms_mean': fl_ms,
                                                   'per_card': {c: {k: per[c][k] for k in ('us', 'ms', 'floor_us', 'gap_ms', 'bytes')}
                                                                for c in per}})
        self.w()

        # ---------- by role (one fix per role, not per kernel)
        roles = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0, 0.0]))
        for c in cards:
            for r in rows[c]:
                v = roles[r['role']][c]
                v[0] += r['ms']
                v[1] += r['floor_ms']
                v[2] += r['n']
                v[3] += r['stand_ms']
        rl = []
        for role, per in roles.items():
            ms = sum(v[0] for v in per.values()) / len(per)
            fl = sum(v[1] for v in per.values()) / len(per)
            st = sum(v[3] for v in per.values()) / len(per)
            n = sum(v[2] for v in per.values()) / len(per)
            cm = max(per, key=lambda c: per[c][0])
            rl.append((ms, role, fl, st, n, cm, per[cm][0], cat_of(role)))
        rl.sort(key=lambda x: -x[0])
        self.w('### Per role (all kernel types of a role summed; mean over cards)')
        self.w()
        self.w('| role | cat | launches | ms/step | floor ms | standalone floor ms | gap ms | max card |')
        self.w('|---|---|---|---|---|---|---|---|')
        for ms, role, fl, st, n, cm, cmv, cat in rl:
            self.w('| %s | %s | %.0f | %.3f | %.3f | %.3f | %.3f | c%d %.3f |' % (role, cat, n, ms, fl, st, ms - fl,
                                                                             cm, cmv))
        self.w()
        self.data['decode']['roles'] = [{'role': r[1], 'ms': r[0], 'floor': r[2], 'standalone': r[3], 'n': r[4],
                                         'max_card': r[5], 'max_ms': r[6]} for r in rl]

        # ---------- categories per card
        cats = ['weights', 'small serial ops', 'exchanges', 'attention', 'gaps, profiled (marks - kernels)',
                'gaps, real (real step - kernels)', 'profiling inflation (profiled wall - real)']
        self.w('### Categories per card (ms per step: actual / floor / standalone floor)')
        self.w()
        self.w('"Standalone floor": every launch kept, each at least %.1f us. Gaps have no floor (0).' % a.launch_us)
        self.w()
        self.w('| category | ' + ' | '.join('c%d' % c for c in cards) + ' | slowest card | its floor |')
        self.w('|---|' + '---|' * len(cards) + '---|---|')
        self.data['decode']['categories'] = {}
        for k in cats:
            vals = {c: cat_tot[c][0].get(k, 0.0) for c in cards}
            fls = {c: cat_tot[c][1].get(k, 0.0) for c in cards}
            sts = {c: cat_tot[c][4].get(k, 0.0) for c in cards}
            cm = max(vals, key=lambda c: vals[c])
            cells = ' | '.join(('%.2f / %.2f / %.2f' % (vals[c], fls[c], sts[c])) if k in cat_tot[c][1]
                               else '%.2f' % vals[c] for c in cards)
            self.w('| %s | %s | c%d %.2f | %.2f |' % (k, cells, cm, vals[cm], fls.get(cm, 0.0)))
            self.data['decode']['categories'][k] = {'per_card': vals, 'floor': fls, 'standalone': sts, 'max_card': cm}
        tot = {c: cat_tot[c][3]['wall'] for c in cards}
        self.w('| **profiled wall** | ' + ' | '.join('%.2f' % (tot[c] or 0) for c in cards) + ' | | |')
        self.w()
        busy = {c: sum(r['ms'] for r in rows[c] if r['cat'] != 'exchanges') for c in cards}
        xch = {c: cat_tot[c][0]['exchanges'] for c in cards}
        g_real = {c: cat_tot[c][0]['gaps, real (real step - kernels)'] for c in cards}
        gaps = {c: cat_tot[c][0]['gaps, profiled (marks - kernels)'] for c in cards}
        pace = max(cards, key=lambda c: busy[c])
        self.w('Busy outside exchanges: %s ms; the most-loaded card is c%d (+%.2f ms over the least loaded). Exchange '
               'kernel time %s ms. Each run profiles one card, so these come from six runs; their min, %.2f ms, '
               'bounds the pure exchange cost from above, the rest of a card\'s exchange time is waiting for a slower '
               'card. If the busiest card were always the last to arrive, it would have the least exchange time; '
               'it does not here, so who waits for whom changes from exchange to exchange or the exchange itself '
               'costs more on some cards (needs the per-exchange arrival data, `OWN_XWAIT`).' % (
                   ', '.join('c%d %.2f' % (c, busy[c]) for c in cards), pace, busy[pace] - min(busy.values()),
                   ', '.join('c%d %.2f' % (c, xch[c]) for c in cards), min(xch.values())))
        self.w()
        self.data['decode']['busy'] = busy
        self.data['decode']['xchg'] = xch

        # ---------- floor of the whole step
        fl_c = {c: (b_c[c] + a_c[c]) / (a.bw * 1e6) for c in cards}
        fl_step = max(fl_c.values())
        fl_mean = sum(fl_c.values()) / len(fl_c)
        nx = sum(r['n'] for r in rows[cards[0]] if r['cat'] == 'exchanges')
        self.w('Whole-step floor (slowest card, every byte once at %.0f GB/s, exchanges hidden): **%.2f ms** '
               '(%.0f tok/s); with the %d exchanges at the %.1f us sync floor not hidden: %.2f ms (%.0f tok/s). '
               'Mean card %.2f ms (the head groups put %.2f ms more on c%d). Today: %.2f ms.' % (
                   a.bw, fl_step, 1e3 / fl_step, round(nx), a.xchg_sync_us, fl_step + nx * a.xchg_sync_us / 1e3,
                   1e3 / (fl_step + nx * a.xchg_sync_us / 1e3), fl_mean, fl_step - min(fl_c.values()),
                   max(fl_c, key=lambda c: fl_c[c]), real_ms))
        self.w()
        self.data['decode']['step_floor_ms'] = fl_step
        self.data['decode']['step_floor_by_card'] = fl_c

        # ---------- recoverable (today's time above the floor)
        rec = []
        for ms_mean, key, per, gap_mean, gap_max in items:
            r0 = list(per.values())[0]
            if r0['cat'] == 'exchanges':
                continue
            frac = sum(r['floor_ms'] for r in per.values()) / max(1e-9, sum(r['ms'] for r in per.values()))
            rec.append({'item': '`%s` (%s, %.0f/step)' % (short(r0['name'], 60), r0['role'], r0['n']),
                        'cat': r0['cat'], 'ms': gap_mean, 'max': gap_max,
                        'note': 'runs at %.0f%% of floor speed' % (100 * frac)})
        x_items = defaultdict(lambda: [0.0, 0.0, 0.0])
        for c in cards:
            for r in rows[c]:
                if r['cat'] == 'exchanges':
                    x_items[r['name']][0] += r['ms'] / len(cards)
                    x_items[r['name']][1] += r['floor_ms'] / len(cards)
                    x_items[r['name']][2] += r['n'] / len(cards)
        for name, (ms, fl, n) in x_items.items():
            rec.append({'item': '`%s` exchanges (%.0f/step, %.1f us each)' % (name, n, ms * 1e3 / n), 'cat': 'exchanges',
                        'ms': ms - fl, 'max': max(r['gap_ms'] for c in cards for r in rows[c] if r['name'] == name),
                        'note': 'floor %.2f ms (%.1f us sync + bytes); includes waiting for slower cards' % (
                            fl, a.xchg_sync_us)})
        rec.append({'item': 'idle gaps between kernels (real step - kernel sum)', 'cat': 'gaps',
                    'ms': sum(g_real.values()) / len(cards), 'max': max(g_real.values()),
                    'note': 'profiled gaps %.2f-%.2f ms; ~1,050 launches per step' % (min(gaps.values()),
                                                                                    max(gaps.values()))})
        rec.sort(key=lambda x: -x['ms'])
        self.w('### Top %d recoverable items (ms per step above the floor; mean over cards, max card in brackets)'
               % a.top)
        self.w()
        self.w('| # | item | category | recoverable ms | note |')
        self.w('|---|---|---|---|---|')
        for i, r in enumerate(rec[:a.top]):
            self.w('| %d | %s | %s | %.3f (%.3f) | %s |' % (i + 1, r['item'], r['cat'], r['ms'], r['max'], r['note']))
        self.w()
        self.data['decode']['recoverable'] = rec

        # ---------- structural levers: changes of the floor itself
        S2 = Slicing(G)
        S2.hq_dec, S2.oa_dec = S.hq_pre, S.oa_pre  # the prompt's split heads in one-token steps too
        fl_split = max(sum(x.wb + x.ab for x in decode_model(G, S2, c, ctx_len).k.values()) for c in range(S.n))
        fl_split /= a.bw * 1e6
        rep_ms = rep_tot * 5 / 6 / (a.bw * 1e6)
        rep_now = sum(r['ms'] for c in cards for r in rows[c]
                      if r['role'] in ('q_a + kv', 'q_a + kv + mix dots')) / len(cards)
        self.w('### Structural levers (they move the floor or hide whole categories)')
        self.w()
        self.w('| lever | floor change ms | today\'s time involved ms | cost |')
        self.w('|---|---|---|---|')
        self.w('| split the replicated reads 6 ways (q_a + kv %s, router %s, stream-mix rows %s, compressor) | -%.2f | '
               'q_a + kv launches %.2f | an all-gather per split matrix (~12 us each today) unless fused into an '
               'existing exchange |' % (fmt_b(rep['q_a + kv (replicated)'] / G.layers),
                                       fmt_b(rep['router (replicated)'] / G.layers),
                                       fmt_b((rep['hc_attn_fn (replicated)'] + rep['hc_ffn_fn (replicated)'])
                                             / (2 * G.layers - 3)), rep_ms, rep_now))
        self.w('| heads split 12,12,12,12,8,8 in one-token steps too (as prompt blocks) | %+.2f (slowest card %.2f '
               '-> %.2f) | q_b + output-a on c2/c5 | 40 head-pair exchanges per step (~8 us each today) |' % (
                   fl_split - fl_step, fl_step, fl_split))
        self.w('| exchanges hidden behind weight reads (persistent layer kernel, weights loaded before the flag '
               'wait) | 0 | exchanges %.2f + gaps %.2f | a persistent-kernel rewrite (strategy S1/S2) |' % (
                   sum(xch.values()) / len(xch), sum(g_real.values()) / len(g_real)))
        self.w()
        self.data['decode']['structural'] = {'replicated_ms': rep_ms, 'split_heads_floor_ms': fl_split}
        if unmatched:
            self.w('Kernel names the step model did not predict (no bytes assigned; a newer build renamed or added '
                   'them) or predicted but absent:')
            for c, names in sorted(unmatched.items()):
                for n in sorted(set(names)):
                    self.w('- c%d: `%s`' % (c, n))
            self.w()
        # launch count check
        bad = []
        for c in cards:
            for r in rows[c]:
                if r['pred_n'] and abs(r['pred_n'] - r['n']) > 0.6:
                    bad.append('c%d `%s`: profile %.2f, model %.2f' % (c, short(r['name'], 60), r['n'], r['pred_n']))
        self.w('Launch-count check (model vs profile, per step): %s' % (
            'all kernel types agree within 0.6.' if not bad else '; '.join(bad[:12])))
        self.w()

    # ---------------- prompt ----------------
    def prompt(self, profs, mt, distinct):
        a, G, S = self.a, self.G, self.S
        cards = sorted(profs)
        self.w('## Prompt reading, blocks of %d tokens (%d cards profiled)' % (mt, len(cards)))
        self.w()
        src = ', '.join(os.path.basename(profs[c]['path']) for c in cards)
        self.w('Profiles: %s. Kernel times are totals over the read, divided by the block count. Routed experts: '
               '%.0f distinct of %d per (block, layer) assumed (`--distinct`; OWN_MT_IDSTAT=1 measures it). Floor = '
               'max(bytes / %.0f GB/s, multiply-adds / %.2f T/s).' % (src, distinct, G.experts, a.bw, a.macs / 1e12))
        self.w()
        per_role = defaultdict(dict)
        blocks = {}
        for c in cards:
            P = profs[c]
            nb = math.ceil(P['prompt_tokens'] / mt) if P['prompt_tokens'] else 208
            blocks[c] = nb
            for name, k in P['kernels'].items():
                role = prompt_role(name)
                if role == 'answer step' or k['n'] < nb / 4:
                    role = 'outside blocks (answer step, last-block head)'
                d = per_role[role].setdefault(c, {'ms': 0.0, 'n': 0.0, 'names': []})
                d['ms'] += k['ms'] / nb
                d['n'] += k['n'] / nb
                d['names'].append(name)
        rows = []
        for role, per in per_role.items():
            if role.startswith('outside'):
                continue
            vals = []
            for c, d in per.items():
                wb, mac = prompt_bytes(G, S, c, role, mt, distinct)
                if role.startswith('exchange'):
                    fl = d['n'] * a.xchg_sync_us / 1e3
                else:
                    fl = max(wb / (a.bw * 1e6), mac / a.macs * 1e3)
                vals.append((c, d['ms'], d['n'], wb, mac, fl))
            ms = sum(v[1] for v in vals) / len(vals)
            fl = sum(v[5] for v in vals) / len(vals)
            cmax = max(vals, key=lambda v: v[1])
            rows.append({'role': role, 'cat': cat_of(role if not role.startswith('exchange') else 'exchange'),
                         'ms': ms, 'floor': fl, 'gap': ms - fl, 'n': vals[0][2], 'wb': vals[0][3], 'mac': vals[0][4],
                         'max_card': cmax[0], 'max_ms': cmax[1], 'bound': ('compute' if vals[0][4] / a.macs > vals[0][3] / (a.bw * 1e9) else 'bytes') if vals[0][3] else '-'})
        rows.sort(key=lambda r: -r['ms'])
        tot = sum(r['ms'] for r in rows)
        self.w('| role | cat | launches / block | ms / block (mean) | max card | weight bytes / block (c%d) | '
               'multiply-adds (c%d) | floor ms | bound | gap ms |' % (cards[0], cards[0]))
        self.w('|---|---|---|---|---|---|---|---|---|---|')
        for r in rows:
            self.w('| %s | %s | %.1f | %.3f | c%d %.3f | %s | %.2f G | %.3f | %s | %.3f |' % (
                r['role'], r['cat'], r['n'], r['ms'], r['max_card'], r['max_ms'], fmt_b(r['wb']) if r['wb'] else '-',
                r['mac'] / 1e9, r['floor'], r['bound'], r['gap']))
        out = per_role.get('outside blocks (answer step, last-block head)', {})
        if out:
            o = sum(d['ms'] for d in out.values()) / len(out)
            self.w('| (outside blocks: answer step, last head) | - | - | %.3f | | | | | | |' % o)
        self.w()
        cats = defaultdict(lambda: [0.0, 0.0])
        for r in rows:
            cats[r['cat']][0] += r['ms']
            cats[r['cat']][1] += r['floor']
        wall = {c: profs[c]['prompt_s'] / blocks[c] * 1e3 for c in cards if profs[c]['prompt_s']}
        self.w('Kernel time per block (mean over cards): %.2f ms; profiled read %.2f ms per block (%s); '
               'by category: %s.' % (tot, sum(wall.values()) / max(1, len(wall)),
                                     ', '.join('c%d %.2f' % (c, wall[c]) for c in sorted(wall)),
                                     '; '.join('%s %.2f (floor %.2f)' % (k, v[0], v[1]) for k, v in
                                               sorted(cats.items(), key=lambda x: -x[1][0]))))
        fl_tot = sum(r['floor'] for r in rows if r['cat'] != 'exchanges')
        if wall:
            wmean = sum(wall.values()) / len(wall)
            self.w()
            self.w('Gaps per block (profiled read per block - kernel sum): %.2f ms.' % (wmean - tot))
        self.w()
        self.w('Block floor (all kernels at their floor, exchanges hidden): %.2f ms -> %.0f tok/s at %d tokens per '
               'block (today ~%.0f tok/s profiled).' % (fl_tot, mt * 1e3 / fl_tot if fl_tot else 0, mt,
                                                        mt * 1e3 / (sum(wall.values()) / max(1, len(wall))) if wall else 0))
        self.w()
        self.data['prompt'] = {'rows': rows, 'categories': {k: v for k, v in cats.items()}, 'floor_ms': fl_tot,
                               'wall_ms_per_block': wall}

        # block size what-if: the floor per token when the weights are read once per block (experts: the union of
        # the block's picks, uniform picks as an upper bound on the union; real prompts repeat experts more)
        c0 = cards[0]
        self.w('Floor per token by block size (card c%d; weight roles only; distinct experts per layer from uniform '
               'picks, an upper bound; exchanges and small ops excluded):' % c0)
        self.w()
        self.w('| tokens per block | distinct experts / layer | expert bytes / block | other weight bytes / block | '
               'floor ms / block | floor tok/s | bound |')
        self.w('|---|---|---|---|---|---|---|')
        wroles = [r['role'] for r in rows if r['cat'] == 'weights']
        out_rows = []
        for m in (16, 32, 64, 128, 256, 512):
            d = G.experts * (1 - (1 - 1.0 / G.experts) ** (G.used * m))
            eb = ob = fl = 0.0
            bnd = defaultdict(float)
            for role in wroles:
                wb, mac = prompt_bytes(G, S, c0, role, m, d)
                t_b, t_c = wb / (a.bw * 1e6), mac / a.macs * 1e3
                fl += max(t_b, t_c)
                bnd['bytes' if t_b >= t_c else 'compute'] += max(t_b, t_c)
                if role.startswith('routed'):
                    eb += wb
                else:
                    ob += wb
            self.w('| %d | %.0f | %s | %s | %.2f | %.0f | %s |' % (
                m, d, fmt_b(eb), fmt_b(ob), fl, m * 1e3 / fl, max(bnd, key=lambda k: bnd[k])))
            out_rows.append({'m': m, 'distinct': d, 'expert_bytes': eb, 'other_bytes': ob, 'floor_ms': fl})
        self.w()
        self.data['prompt']['block_whatif'] = out_rows


def xwait_report(L, path, mhz):
    """Who arrives last at each exchange: lines of the OWN_XWAIT patch (dsv41_xwait.patch)."""
    ex = defaultdict(dict)  # (step, k) -> card -> (label, spins[6], ticks[6])
    for ln in open(path):
        f = ln.split()
        if len(f) < 17 or f[0] != 'xw':  # (dsv41_timeline.patch appends push ticks, kernel ticks, answer step)
            continue
        step, c, k, lab = int(f[1]), int(f[2]), int(f[3]), int(f[4])
        ex[(step, k)][c] = (lab, [int(x) for x in f[5:11]], [int(x) for x in f[11:17]])
    if not ex:
        L.w('`%s`: no xw records.' % path)
        return
    kinds = {0: 'q_a/q_b phase', 1: 'output-a rows', 2: 'output-b rows', 3: 'expert activations', 4: 'ffn rows',
             5: 'phase 5'}
    cards = sorted({c for v in ex.values() for c in v})
    last = defaultdict(lambda: defaultdict(int))
    wait = defaultdict(lambda: defaultdict(float))
    nex = defaultdict(int)
    steps = set()
    for (step, k), per in ex.items():
        if len(per) < 2:
            continue
        steps.add(step)
        lab = next(iter(per.values()))[0]
        ph, part = lab // 10 % 10, lab % 10
        kind = 'engram rows' if part == 3 else kinds.get(ph, 'other')
        nex[kind] += 1
        late = {t: sum(per[c][2][t] for c in per if c != t) / max(1, len(per) - 1) for t in per}
        last[kind][max(late, key=lambda t: late[t])] += 1
        for c in per:
            wait[kind][c] += max(per[c][2][t] for t in per if t != c)
    ns = max(1, len(steps))
    L.w('### Who waits for whom (OWN_XWAIT, %d steps, ticks -> us at %.0f MHz)' % (ns, mhz))
    L.w()
    L.w('| exchange | per step | last to arrive (share of exchanges) | wait per card, us per step |')
    L.w('|---|---|---|---|')
    for kind in sorted(nex, key=lambda k: -nex[k]):
        n = nex[kind]
        lst = ', '.join('c%d %.0f%%' % (c, 100.0 * last[kind][c] / n) for c in sorted(last[kind], key=lambda c: -last[kind][c]))
        wt = ', '.join('c%d %.1f' % (c, wait[kind][c] / ns / mhz) for c in cards)
        L.w('| %s | %.0f | %s | %s |' % (kind, n / ns, lst, wt))
    tot = {c: sum(wait[k][c] for k in wait) / ns / mhz for c in cards}
    L.w()
    L.w('Total wait per step: %s us (the least-waiting card sets the pace).' % ', '.join('c%d %.0f' % (c, tot[c])
                                                                                       for c in cards))
    L.w()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    here = os.path.dirname(os.path.abspath(__file__))
    rt = os.path.normpath(os.path.join(here, '..', '..', '..'))
    data = os.path.join(rt, 'data', 'dsv41-bringup-20261109')
    ap.add_argument('--runs', default='/home/steve/dsv41-work/runs/b1')
    ap.add_argument('--dec', nargs='*', help='answer-step profiles (default: RUNS/dec_c*.log)')
    ap.add_argument('--pre', nargs='*', help='prompt profiles (default: RUNS/pre_c*.log)')
    ap.add_argument('--pre-fallback', nargs='*',
                    default=sorted(glob.glob(os.path.join(data, 'round18-e80-prompt-3k-heads-profile-card*.txt'))))
    ap.add_argument('--plain', help='unprofiled run for the real step time (default RUNS/plain.log)')
    ap.add_argument('--model', default='/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS')
    ap.add_argument('--bw', type=float, default=550.0, help='card memory floor, GB/s')
    ap.add_argument('--link-gbs', type=float, default=25.0, help='card-to-card bytes floor, GB/s')
    ap.add_argument('--xchg-sync-us', type=float, default=2.5, help='per-exchange sync floor (one flag round trip)')
    ap.add_argument('--launch-us', type=float, default=2.2, help='empty launch on this stack (e81b), for the '
                    'standalone floor')
    ap.add_argument('--macs', type=float, default=5.7e12, help='multiply-adds per second per card (prompt floor)')
    ap.add_argument('--ctx', type=int, default=0, help='positions for the attention bytes (default: prompt + '
                    'half the answer steps from the logs)')
    ap.add_argument('--block', type=int, default=16, help='prompt block (OWN_PROMPT_BLOCK)')
    ap.add_argument('--distinct', type=float, default=80.0, help='distinct experts per (block, layer) in prompt '
                    'blocks (uniform picks of 96 from 384 give ~85)')
    ap.add_argument('--top', type=int, default=15)
    ap.add_argument('--xwait', help='OWN_XWAIT file (dsv41_xwait.patch) for the who-waits-for-whom table')
    ap.add_argument('--xw-mhz', type=float, default=2400.0, help='sub-group clock rate for OWN_XWAIT ticks '
                    '(uncalibrated default; check against the exchange kernel times)')
    ap.add_argument('--md', help='write the markdown here (default stdout)')
    ap.add_argument('--json', help='write the numbers here')
    a = ap.parse_args()

    kv, tensors, files = load_model(a.model)
    G = Geometry(kv, tensors)
    S = Slicing(G)
    L = Ledger(a, G, S)
    L.w('# DeepSeek V4.1 Flash step budget (generated by `engine/tools/perf/dsv41_step_budget.py`)')
    L.w()
    L.w('Model: %d GGUF headers in `%s` (%d tensors). Slicing (OWN_TP=6): expert/shared mid rows %s; model rows %s; '
        'vocab rows %s; heads per card for one token %s, for prompt blocks %s.' % (
            len(files), a.model, len(tensors), [S.rows(r) for r in S.tm], [S.rows(r) for r in S.td],
            [S.rows(r) for r in S.tv], [S.rows(r) for r in S.hq_dec], [S.rows(r) for r in S.hq_pre]))
    L.w()

    dec = a.dec if a.dec is not None else sorted(glob.glob(os.path.join(a.runs, 'dec_c*.log')))
    profs = {}
    for p in dec:
        P = parse_profile(p)
        c = card_of(p)
        if P['kernels'] and c is not None:
            profs[c] = P
    plain = a.plain or os.path.join(a.runs, 'plain.log')
    real_ms = None
    if os.path.exists(plain):
        pp = parse_profile(plain)
        if pp['tok_s']:
            real_ms = 1e3 / pp['tok_s']
    if profs:
        if real_ms is None:
            real_ms = min(P['wall'] for P in profs.values())
        ctx = a.ctx
        if not ctx:
            P0 = next(iter(profs.values()))
            ctx = (P0['prompt_tokens'] or 36) + (P0['steps'] or 48) // 2
        L.decode(profs, real_ms, ctx)
    else:
        L.w('No answer-step profiles with a kernel table found.')
        L.w()

    pre = a.pre if a.pre is not None else sorted(glob.glob(os.path.join(a.runs, 'pre_c*.log')))
    pprofs = {}
    for p in pre:
        P = parse_profile(p)
        c = card_of(p)
        if P['kernels'] and c is not None and P['prompt_tokens']:
            pprofs[c] = P
    if not pprofs and a.pre_fallback:
        L.w('(The prompt logs %s carry no kernel table: with one answer token the runner prints no profile; '
            'run them with 2 answer tokens. Using %s instead.)' % (
                ', '.join(os.path.basename(p) for p in pre) or 'none',
                ', '.join(os.path.basename(p) for p in a.pre_fallback)))
        L.w()
        for p in a.pre_fallback:
            P = parse_profile(p)
            c = card_of(p)
            if P['kernels'] and c is not None and P['prompt_tokens']:
                pprofs[c] = P
    if pprofs:
        L.prompt(pprofs, a.block, a.distinct)
    if a.xwait:
        xwait_report(L, a.xwait, a.xw_mhz)
    text = '\n'.join(L.out) + '\n'
    if a.md:
        with open(a.md, 'w') as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    if a.json:
        with open(a.json, 'w') as f:
            json.dump(L.data, f, indent=1, default=str)


if __name__ == '__main__':
    main()
