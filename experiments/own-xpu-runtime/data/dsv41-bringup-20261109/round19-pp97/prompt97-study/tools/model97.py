"""Shapes, bytes and multiply-add counts of one card's share of a prompt block (DeepSeek V4.1 Flash, six B70, tp97).

Sources: engine/profiles/dsv41-iq2xxs/placement.tsv (formats per layer), backend_sycl_v41.hpp (tp_setup splits,
head_layout), backend_sycl_v41_mt.inc (tpm_layer: which matrices and exchanges a block runs), pack_v41.hpp row bytes
(as dsv41_step_budget.packed_row_bytes), runs/u84/p3k-ids-per-layer.txt (every 3K-prompt token's six experts).

Rates (all per card):
  ISSUE  32 Xe-cores x 8 XVEs x 16 FP32 lanes x 2.8 GHz = 11.47 T FP32 operations/s. A multiply-add of the reference
         is a multiply, then an add (built with -ffp-contract=off; the fused FMA rounds once and is not allowed), so
         PROD = ISSUE / 2 = 5.73 T multiply-adds/s. No DPAS / XMX, no bf16 / tf32 / int8 dot products.
  BW     550 GB/s card memory (608 peak; the output head reaches 572).
  LINK   25 GB/s that one card loads from its peers while all six exchange (xchg_bw_bench, lane note section 21),
         plus 2.5 us per exchange (one flag round trip).
  PORT   92.4 B/clock/Xe-core of loads through the L1 / data port (predict.py fit) = 8.28 TB/s at 2.8 GHz.
"""
import collections
import math

H, QR, HD, MID, NE, TOPK, L = 5120, 1280, 512, 2304, 384, 6, 40
NTOK = 3323
CLK = 2.8e9
ISSUE = 32 * 8 * 16 * CLK            # FP32 lane operations per second
PROD = ISSUE / 2                     # multiply-adds per second (a multiply and an add each)
BW = 550e9
LINK = 25e9
SYNC = 2.5e-6
PORT = 92.4 * 32 * CLK
IDDUMP = '/home/steve/dsv41-work/runs/u84/p3k-ids-per-layer.txt'

# formats per layer (placement.tsv)
DENSE = ['Q8_0'] * 27 + ['Q6_K'] * 13           # q_a, kv, q_b, o_a, o_b
SHARED = ['Q8_0'] * 27 + ['Q5_K'] * 13          # shared gate / up / down
GU = ['IQ1_S'] * 10 + ['IQ2_XXS'] * 15 + ['IQ2_S'] * 15
DN = (['Q2_K', 'IQ2_XS', 'IQ2_XXS', 'IQ2_XXS', 'IQ2_XXS'] + ['IQ2_XS'] * 5 + ['IQ2_S'] * 10 + ['IQ3_XXS'] * 15 +
      ['IQ2_S'] * 5)
COMP_LAYERS = {2: 2, 8: 2, 14: 2, 20: 1}         # compressor matrices (gate + kv, layer 20 kv only), 512 x 5120 BF16
IDX_LAYERS = [2, 8, 14, 20, 24, 28, 32, 36]     # indexer q_b 4096 x 1280, proj 32 x 5120 (BF16); k 128 x 512 on 2/8/14/20
ENGRAM = [1, 14]                                 # engram_kv 25600 x 6144 Q6_K, split over the cards


def pad16(n):
    return (n + 15) // 16 * 16


def row_bytes(fmt, cols):
    nb = cols // 256
    return {
        'Q8_0': lambda: pad16(cols // 32 * 34),
        'Q6_K': lambda: pad16(nb * 210),
        'Q5_K': lambda: pad16(nb * 176),
        'H16': lambda: pad16(cols * 2),
        'BF16': lambda: cols * 2,
        'IQ2_XXS': lambda: pad16(nb * 70),
        'IQ2_S': lambda: pad16(nb * 82),
        'IQ3_XXS': lambda: pad16(nb * 98),
        'IQ1_S': lambda: pad16(nb * 50),
        'IQ2_XS': lambda: pad16(nb * 74),
        'Q2_K': lambda: nb * 84,
    }[fmt]()


def split16(total, c, n=6):
    u = total // 16
    a = (u * c // n) * 16
    b = total if c + 1 == n else (u * (c + 1) // n) * 16
    return b - a


class Card:
    """one card's slices in prompt blocks (OWN_TP_HEADS 3,3,3,3,2,2 for blocks of >= 16 tokens)"""

    def __init__(self, c):
        self.c = c
        self.heads = [12, 12, 12, 12, 8, 8][c]
        self.qb = self.heads * HD           # q_b rows
        self.oa = self.heads * 128          # output-a rows (1,024 per group of 8 heads)
        self.td = split16(H, c)             # output-b / shared down / expert down rows
        self.tm = split16(MID, c)           # expert and shared gate / up rows
        self.te = split16(5 * H, c)         # engram rows
        self.pair = self.heads % 8 != 0     # holds half of a group: XchgPair, two output-a launches
        self.dsa = [1, 1, 1, 1, 4, 4][c] / 12.0   # OWN_MT_DSPLIT attention-mix token share (ds_split default)
        self.dsf = 1 / 6.0                        # FFN-mix share


def dense_layer(cd, Lr):
    """[(role, rows, cols, fmt)] of the dense matrices card cd runs for one token in layer Lr"""
    f, s = DENSE[Lr], SHARED[Lr]
    out = [('q_a + kv rows', QR, H, f), ('q_a + kv rows', HD, H, f), ('q_b rows', cd.qb, QR, f),
           ('o_a rows', cd.oa, 4096, f), ('o_b rows', cd.td, 8192, f), ('router rows', NE, H, 'H16'),
           ('route pick + shared gate/up', 2 * cd.tm, H, s), ('shared down', cd.td, MID, s)]
    if Lr in ENGRAM:
        out.append(('engram kv rows', cd.te, 6144, 'Q6_K'))
    for _ in range(COMP_LAYERS.get(Lr, 0)):
        out.append(('compressor rows', 512, H, 'BF16'))
    return out


def idx_tokens(nb, block):
    """tokens in the blocks that run the indexer rows and scores (dev_index past 512 compressed rows: blocks from
    token 512 on for the ratio-1 layers 20..39, from 1,024 on for the ratio-2 layers 2..19; matches the 328 launches
    of IndexerScoreBM / GemvH16P<40u> at blocks of 64)"""
    out = {}
    for Lr in IDX_LAYERS:
        start = 512 if Lr >= 20 else 1024
        t = 0
        for b in range(nb):
            t0, t1 = b * block, min(NTOK, (b + 1) * block)
            if t1 - 1 >= start:   # the block's last token past 512 rows
                t += t1 - t0
        out[Lr] = t
    return out


def dense_read(cd, block):
    """per read: role -> [multiply-adds, weight bytes, launches]"""
    nb = math.ceil(NTOK / block)
    acc = collections.defaultdict(lambda: [0.0, 0.0])
    for Lr in range(L):
        for role, r, cols, fmt in dense_layer(cd, Lr):
            acc[role][0] += r * cols * NTOK
            acc[role][1] += r * row_bytes(fmt, cols) * nb
    it = idx_tokens(nb, block)
    for Lr in IDX_LAYERS:
        nbi = math.ceil(it[Lr] / block)
        acc['indexer q_b + proj + k rows'][0] += (4096 * QR + 32 * H) * it[Lr]
        acc['indexer q_b + proj + k rows'][1] += (4096 * QR * 2 + 32 * H * 2) * nbi
    for Lr in (2, 8, 14, 20):
        acc['indexer q_b + proj + k rows'][0] += 128 * 512 * NTOK
        acc['indexer q_b + proj + k rows'][1] += 128 * 512 * 2 * nb
    return acc


def attention_read(cd):
    """multiply-adds per read: scores + outputs over the slots each token reads (window 128, compressed rows up to
    512: ratio 1 on layers 20..39, ratio 2 on layers 2..19, none on 0..1), heads of the card"""
    tot = 0
    for t in range(NTOK):
        w = min(128, t + 1)
        s1 = w + min(512, t + 1)
        s2 = w + min(512, (t + 1) // 2)
        tot += 20 * s1 + 18 * s2 + 2 * w
    return tot * cd.heads * HD * 2


def index_read(block):
    """indexer score multiply-adds per read: 32 heads x 128 per compressed row, every card"""
    nb = math.ceil(NTOK / block)
    tot = 0
    for Lr in IDX_LAYERS:
        ratio = 1 if Lr >= 20 else 2
        start = 512 if Lr >= 20 else 1024
        for b in range(nb):
            t0, t1 = b * block, min(NTOK, (b + 1) * block)
            if t1 - 1 < start:
                continue
            for t in range(t0, t1):
                tot += ((t + 1) // ratio) * 32 * 128
    return tot


def read_ids():
    per_layer = collections.defaultdict(list)
    with open(IDDUMP) as f:
        for line in f:
            v = line.split()
            if len(v) < 2:
                continue
            Lr, M = int(v[0]), int(v[1])
            ids = [int(x) for x in v[2:]]
            for i in range(M):
                per_layer[Lr].append(tuple(ids[6 * i:6 * i + 6]))
    return per_layer


def expert_read(cd, block, cap=6, ids=None):
    """per read on card cd: slots, distinct experts, groups (cap slots each), multiply-adds, weight bytes and
    group-row-weights (every row of a group is decoded once per group), for gate+up and down"""
    ids = ids or read_ids()
    out = {'gate+up': collections.Counter(), 'down': collections.Counter()}
    for Lr in range(L):
        toks = ids[Lr]
        gub = 2 * cd.tm * row_bytes(GU[Lr], H)
        dnb = cd.td * row_bytes(DN[Lr], MID)
        for b0 in range(0, len(toks), block):
            cnt = collections.Counter(e for tk in toks[b0:b0 + block] for e in tk)
            d = len(cnt)
            g = sum(math.ceil(n / cap) for n in cnt.values())
            s = sum(cnt.values())
            for k, rows, cols, by in (('gate+up', 2 * cd.tm, H, gub), ('down', cd.td, MID, dnb)):
                o = out[k]
                o['slots'] += s
                o['distinct'] += d
                o['groups'] += g
                o['macs'] += s * rows * cols
                o['bytes'] += d * by
                o['gweights'] += g * rows * cols
                o['blocks'] += 1 if k == 'gate+up' and Lr == 0 else 0
    return out


def exchanges_block(cd, M):
    """bytes card cd loads from its peers per block of M tokens, and exchange launches, by kind"""
    other = M * (1 - cd.dsa)
    x = collections.OrderedDict()
    x['output-a + attention-mix partials (XchgPull2)'] = (40, 40 * ((8192 - cd.oa) * 4 * M + other * 1600))
    x['expert act + FFN-mix partials (XchgPull2)'] = (40, 40 * ((MID - cd.tm) * 4 * 7 * M + M * (1 - cd.dsf) * 1600))
    x['output-b (XchgPull)'] = (40, 40 * (H - cd.td) * 4 * M)
    x['ffn rows (XchgPull)'] = (40, 40 * (H - cd.td) * 4 * M)
    x['engram rows (XchgPull)'] = (3, 2 * M * (5 * H - cd.te) * 4)
    x['head pairs (XchgPair)'] = (80 if cd.pair else 0, 40 * (4 * HD * 4 * M) if cd.pair else 0)
    return x
