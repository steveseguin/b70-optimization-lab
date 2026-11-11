"""Per-role (layer phase / kernel family) device time of OWN_TIMELINE steps (one-token steps or OWN_TIMELINE_CHECKS
checks), for the tp96 kernel names (ck-2 WS forms, OWN_ATT_T attention, DSPLIT finishes) and the older ones.

Successor of ck2tok/tools/roles.py. Roles come from the matrix in the kernel name (format + 32/256-column blocks:
Q8 160 / Q6 20 = q_a, kv (5,120 columns); Q8 40 / Q6 5 = q_b (1,280); Q8 128 / Q6 16 = o_a (4,096); Q8 256 / Q6 32 =
o_b (8,192); Q8 72 / Q5 9 = shared down (2,304); Q6 24 = engram (6,144); Q8 480 = the draft fc) plus position:
  - the router is the H16 160 launch right before a Route* launch; other H16 160 / H16 16 launches are the compressor
  - a rope launch right after q_b belongs to q_b; other rope launches to the compressor
  - a lone HcFinishRows launch (DSPLIT, M >= 4) is the attention mix's finish if o_b follows, else the FFN mix's
  - a pre-norm is the attention one if q_a + kv follows, the FFN one if the router / Route* follows
  - after the last MoE combine: mix, head norm + GEMV + argmax; after the argmax: the check tail (draft fc and rows)
  - an exchange's kind is its producer's (the last non-exchange launch before it); xpart 3 = engram
classify(t, step, card) -> [(role, launch, layer)], layer = ffn-rows exchanges completed before it (40 = head).
CLI: python3 -I roles96.py TIMELINE [card]  prints every role with its kernel names, launches and us per step."""
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, '/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine/tools/perf')
import dsv41_timeline as T  # noqa: E402

ROLES = [  # table order
    'embed/broadcast', 'engram rows/gate', 'head norm+GEMV+argmax', 'check-only: draft features/injection',
    'mix collapse (HcPre/HcPostPre/HcPost)', 'attn pre-norm (+dots)', 'q_a+kv rows (+dots)', 'q_a/kv norms',
    'q_b rows (+finish, rope)', 'compressor+indexer', 'attention core', 'o_a rows', 'attn mix finish alone (DSPLIT)',
    'o_b rows', 'ffn pre-norm (+dots)', 'router rows (+dots)', 'router pick+finish+shared gate/up', 'ExpertGroupM',
    'experts gate+up', 'SwiGLU', 'experts down', 'ffn mix finish alone (DSPLIT)', 'shared down', 'MoE combine',
    'xchg output-a (pull)', 'xchg output-b', 'xchg output-b [PushM]', 'xchg expert act (pull)', 'xchg ffn rows',
    'xchg ffn rows [PushM]', 'xchg engram', 'xchg check (draft fc)', 'xchg check (draft fc) [PushM]', 'xchg other',
]
MAT = re.compile(r'(GemvQ8P|WsQ8|GemvQ6KP|WsQ6|GemvQ5KP|WsQ5|GemvH16P|GemvF32P)<(\d+)u')
FMT = {'GemvQ8P': 'Q8', 'WsQ8': 'Q8', 'GemvQ6KP': 'Q6', 'WsQ6': 'Q6', 'GemvQ5KP': 'Q5', 'WsQ5': 'Q5',
       'GemvH16P': 'H16', 'GemvF32P': 'F32'}
BYMAT = {('Q8', 160): 'qakv', ('Q6', 20): 'qakv', ('Q8', 40): 'q_b', ('Q6', 5): 'q_b', ('Q8', 128): 'o_a',
         ('Q6', 16): 'o_a', ('Q8', 256): 'o_b', ('Q6', 32): 'o_b', ('Q8', 72): 'sdown', ('Q5', 9): 'sdown',
         ('Q6', 24): 'engram', ('Q8', 480): 'fc', ('H16', 160): 'h160', ('H16', 16): 'h16', ('Q5', 20): 'sgu',
         ('F32', 160): 'h160'}


def mats(nm):
    return [(FMT[a], int(b)) for a, b in MAT.findall(nm)]


def base(nm):
    """name-only class (no position)"""
    if nm.startswith('Xchg'):
        return 'xchg'
    if re.match(r'(EmbedRowA|Broadcast4PA)', nm):
        return 'embed/broadcast'
    if re.match(r'(EngRowsA|SkEngramGateW|EngramGateWM)', nm):
        return 'engram rows/gate'
    if 'ops41draft' in nm or re.match(r'(StreamMeanM|DraftKvRows|Markov)', nm):
        return 'check-only: draft features/injection'
    if re.match(r'Hc(Pre|Post)\w*<', nm):
        return 'mix collapse (HcPre/HcPostPre/HcPost)'
    if nm == 'RowsP<TokRows<HcFinishRows> >':
        return 'finish-alone'
    if re.match(r'Argmax', nm):
        return 'argmax'
    if re.match(r'(QbWaitRope|QbPush)', nm):
        return 'q_b rows (+finish, rope)'
    if nm.startswith('SkNormPair') or re.match(r'RowsP<RowsPair<TokRows<HcFinishRows>, RowsPair<TokRows<NormRows<1280u', nm):
        return 'q_a/kv norms'
    if re.match(r'(SkNorm(?!Pair)|RmsNormPS<5120)', nm) or re.match(r'RowsP<(RowsPair<)?TokRows<NormRows<5120u', nm):
        return 'prenorm'
    if re.match(r'Route(P|PM)Rows|RoutePM\b|RoutePM$', nm):
        return 'router pick+finish+shared gate/up'
    if nm.startswith('ExpertGroupM'):
        return 'ExpertGroupM'
    if nm.startswith('Routed'):
        if 'ops41draft' in nm:
            return 'check-only: draft features/injection'
        m = re.search(r'<(\d+)u', nm)
        return 'experts gate+up' if m and m.group(1) == '20' else 'experts down'
    if nm.startswith('SwigluBoth'):
        return 'SwiGLU'
    if nm.startswith('MoeCombine'):
        return 'MoE combine'
    if re.match(r'(WindowAppend|SparseScore|ScoreM|SparseSoftmax|SoftmaxM|SparseOut|OutM|RingCommit)', nm):
        return 'attention core'
    if re.match(r'(ToF32A|SkCompressPoolW|StatePackM|RmsNormA|RmsNormPS|RopePairsA|PubAppendA|CidxFill)', nm):
        return 'compressor+indexer'
    if 'RopeRows' in nm and not mats(nm):
        return 'rope'
    if re.match(r'RowsP<(RowsPair<)?TokRows<NormRows<512u', nm):
        return 'compressor+indexer'
    ms = mats(nm)
    if ms:
        k = BYMAT.get(ms[-1], '?')
        return {'qakv': 'q_a+kv rows (+dots)', 'q_b': 'q_b rows (+finish, rope)', 'o_a': 'o_a rows',
                'o_b': 'o_b rows', 'sdown': 'shared down', 'engram': 'engram rows/gate',
                'fc': 'check-only: draft features/injection', 'h160': 'h160', 'h16': 'compressor+indexer',
                'sgu': 'router pick+finish+shared gate/up'}.get(k, '?? ' + nm[:60])
    return '?? ' + nm[:60]


XKIND = {'o_a rows': 'xchg output-a (pull)', 'o_b rows': 'xchg output-b', 'SwiGLU': 'xchg expert act (pull)',
         'MoE combine': 'xchg ffn rows', 'engram rows/gate': 'xchg engram'}


def classify(t, step, card):
    v = t['L'][(step, card)]
    names = t['names']
    nm = [names[x.nid] for x in v]
    b = [base(n) for n in nm]
    n = len(v)
    lastc = max([i for i in range(n) if b[i] == 'MoE combine'], default=-1)
    am = [i for i in range(n) if b[i] == 'argmax' and i > lastc]
    arg = am[0] if am else n
    r = [None] * n
    for i in range(n):
        bi = b[i]
        nxt = next((b[j] for j in range(i + 1, min(n, i + 4)) if b[j] not in ('xchg',)), '')
        prv = b[i - 1] if i else ''
        if i > arg:
            r[i] = 'xchg' if bi == 'xchg' else 'check-only: draft features/injection'
            continue
        if i > lastc >= 0 and bi not in ('xchg', 'mix collapse (HcPre/HcPostPre/HcPost)',
                                          'check-only: draft features/injection'):
            r[i] = 'head norm+GEMV+argmax'
            continue
        if bi == 'argmax':
            r[i] = 'head norm+GEMV+argmax'
        elif bi == 'h160':
            r[i] = 'router rows (+dots)' if nxt == 'router pick+finish+shared gate/up' else 'compressor+indexer'
        elif bi == 'rope':
            r[i] = 'q_b rows (+finish, rope)' if r[i - 1] == 'q_b rows (+finish, rope)' else 'compressor+indexer'
        elif bi == 'finish-alone':
            r[i] = 'attn mix finish alone (DSPLIT)' if nxt == 'o_b rows' else 'ffn mix finish alone (DSPLIT)'
        elif bi == 'prenorm':
            if nxt == 'q_a+kv rows (+dots)':
                r[i] = 'attn pre-norm (+dots)'
            elif nxt in ('h160', 'router pick+finish+shared gate/up'):
                r[i] = 'ffn pre-norm (+dots)'
            else:
                r[i] = 'attn pre-norm (+dots)'
        else:
            r[i] = bi
    # exchanges: the producer's kind
    layer = 0
    out = []
    for i in range(n):
        if r[i] == 'xchg':
            x = v[i]
            k = 'xchg other'
            if x.xpart == 3:
                k = 'xchg engram'
            elif i > arg:
                k = 'xchg check (draft fc)'
            else:
                for j in range(i - 1, -1, -1):
                    if r[j].startswith('xchg'):
                        continue
                    k = XKIND.get(r[j], 'xchg other')
                    break
            r[i] = k + (' [PushM]' if nm[i] == 'XchgPushM' else '')
        out.append((r[i], v[i], layer))
        if r[i] == 'xchg ffn rows':
            layer += 1
    return out


def table(t, S, cards):
    """{card: {role: [us per step, launches per step]}} averaged over steps S"""
    res = {}
    for c in cards:
        acc = defaultdict(lambda: [0.0, 0.0])
        for s in S:
            for r, x, _ in classify(t, s, c):
                a = acc[r]
                a[0] += (x.de - x.ds) / 1e3 / len(S)
                a[1] += 1 / len(S)
        res[c] = acc
    return res


def order_key(k):
    return (ROLES.index(k) if k in ROLES else 100, k)


if __name__ == '__main__':
    t = T.read_timeline(sys.argv[1])
    card = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    steps = sorted(set(k[0] for k in t['L']))
    acc = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
    for s in steps:
        for r, x, _ in classify(t, s, card):
            a = acc[r][t['names'][x.nid]]
            a[0] += (x.de - x.ds) / 1e3 / len(steps)
            a[1] += 1
    for r in sorted(acc, key=order_key):
        tot = sum(a[0] for a in acc[r].values())
        print('%-40s %8.1f us/step' % (r, tot))
        for nm, a in sorted(acc[r].items(), key=lambda kv: -kv[1][0]):
            print('      %8.1f %5d  %s' % (a[0], a[1], nm[:170]))
