"""Read the OWN_GPROF=2 prompt profiles (pp97 / pp92) and sort every kernel type into a role and a family.

The kernel table of a prompt profile is the total over the whole read (every prompt block) plus the one answer step
that follows it ("- 2": the second token). The answer step's kernels mostly have one-token names (GemvQ8P,
SkNormDotsW, RoutedIQ2SPe, ...); they go to the role "answer step" and are left out. Shared names get their
answer-step part taken off:
  XchgPull: 83 one-token pulls (output-a, expert act, engram; ck2tok96 tl_one: 452 + 566 + 43 us per step)
  RoutedQ2KF / EngRowsA / RmsNormA / HcPostPreP: launch counts above a multiple of the block count are the step's.

usage (library): runs() -> {tag: Run}; Run.roles(): {role: (ms per read, launches per read)}
"""
import math
import os
import re

W = '/home/steve/dsv41-work'
RUNS = {
    'pp97': W + '/runs/pp97',
    'pp92': W + '/runs/pp92',
}
NTOK = 3323
KLINE = re.compile(r'^\s+([0-9.]+)\s+[0-9.]+%\s+(\d+)\s+([0-9.]+) us\s+(\S.*)$')
PLINE = re.compile(r'prompt: (\d+) tokens read on the cards in ([0-9.]+)s \(([0-9.]+) tok/s; first step ([0-9.]+)s')
ONE_TOKEN_PULL_MS = (452 + 566 + 43) / 1000.0  # ck2tok96 one-token path: output-a, expert act, engram pulls per step


def nblocks(b):
    return math.ceil(NTOK / b)


# role, family. Families are the ones the question asks for.
FAM = {
    'q_a + kv rows': 'dense rows',
    'q_b rows': 'dense rows',
    'o_a rows': 'dense rows',
    'o_b rows': 'dense rows',
    'router rows': 'dense rows',
    'route pick + shared gate/up': 'dense rows',
    'shared down': 'dense rows',
    'engram kv rows': 'dense rows',
    'experts gate+up': 'experts gate+up',
    'experts down': 'experts down',
    'expert grouping': 'experts other',
    'swiglu': 'experts other',
    'moe combine': 'experts other',
    'attention score': 'attention',
    'attention softmax': 'attention',
    'attention output': 'attention',
    'window append + ring commit': 'attention',
    'q / kv rope': 'attention',
    'compressor rows': 'compressor + indexer',
    'compressor pool / state / publish': 'compressor + indexer',
    'indexer q_b + proj + k rows': 'compressor + indexer',
    'index score + top-k + fill': 'compressor + indexer',
    'pre-norm + dot rows (SkNormDotsWM)': 'norms + dot rows',
    'mix finish (own launches)': 'norms + dot rows',
    'q_a / kv norms': 'norms + dot rows',
    'stream post + pre (HcPostPrePMG etc.)': 'norms + dot rows',
    'xchg output-a + act (XchgPull2)': 'exchanges',
    'xchg output-b + ffn rows + engram (XchgPull)': 'exchanges',
    'xchg head pairs (XchgPair)': 'exchanges',
    'engram gate + rows': 'small ops',
    'embed + broadcast': 'small ops',
    'head (last block)': 'small ops',
    'other small': 'small ops',
    'answer step': None,
}


def role_of(name):
    n = name.replace(' ', '')
    if n in ('XchgPull2',):
        return 'xchg output-a + act (XchgPull2)'
    if n == 'XchgPull':
        return 'xchg output-b + ffn rows + engram (XchgPull)'
    if n == 'XchgPair':
        return 'xchg head pairs (XchgPair)'
    if n.startswith('XchgP'):
        return 'answer step'
    # routed experts (block forms: RoutedUT / RoutedU3 / RoutedU / RoutedQ2KF)
    m = re.match(r'(RoutedUT|RoutedU3|RoutedU)<\w*?(IQ\w+?)<(\d+)u>', n)
    if m:
        return 'experts gate+up' if m.group(3) == '20' else 'experts down'
    if n.startswith('RoutedQ2KF'):
        return 'experts down'
    if re.match(r'Routed\w+P[a-z]?<', n):
        return 'answer step'  # one-token expert kernels
    if n.startswith('ExpertGroupM'):
        return 'expert grouping'
    if n.startswith('SwigluBothSM'):
        return 'swiglu'
    if n.startswith('MoeCombineAM'):
        return 'moe combine'
    # dense rows, block forms
    m = re.match(r'RowsP<DenseRowsWS<Ws(Q8|Q6|Q5)<(\d+)u>,(\d+)u,(\d+)u', n)
    if m:
        f, c = m.group(1), int(m.group(2))
        cols = c * (32 if f == 'Q8' else 256)
        if cols == 5120 and f in ('Q8', 'Q6'):
            return 'q_a + kv rows'
        if cols == 1280:
            return 'q_b rows'
        if cols == 4096:
            return 'o_a rows'
        if cols == 8192:
            return 'o_b rows'
        if cols == 2304:
            return 'shared down'
        if cols == 6144:
            return 'engram kv rows'
        if cols == 5120 and f == 'Q5':
            return 'q_a + kv rows'
    if n.startswith('RowsP<DenseRowsGR<GemvQ6KP<24u'):
        return 'engram kv rows'
    if n.startswith('RoutePMRows<'):
        return 'route pick + shared gate/up'
    if n.startswith('RowsP<DenseRowsG<GemvH16P<160u'):
        return 'router rows'  # (+ compressor gate / kv and indexer proj: split by split_h16())
    if n.startswith('RowsP<DenseRowsG<GemvH16P<40u') or n.startswith('RowsP<DenseRowsG<GemvH16P<16u'):
        return 'indexer q_b + proj + k rows'
    # attention
    if n.startswith('ScoreM<'):
        return 'attention score'
    if n.startswith('SoftmaxM<'):
        return 'attention softmax'
    if n.startswith('OutM<'):
        return 'attention output'
    if n.startswith('WindowAppendM') or n.startswith('RingCommitM'):
        return 'window append + ring commit'
    if n.startswith('RowsP<RowsPair<TokRows<RopeRows'):
        return 'q / kv rope'
    # compressor / indexer
    if n.startswith('SkCompressPoolWM') or n.startswith('CompressPoolPM') or n.startswith('StatePackM') or \
            n.startswith('PubAppendAM') or n.startswith('RowsP<TokRows<NormRows<512u'):
        return 'compressor pool / state / publish'
    if n.startswith('IndexerScoreBM') or n.startswith('TopKSelM') or n.startswith('CidxFillM') or \
            n.startswith('RowsP<TokRows<RopeRows'):
        return 'index score + top-k + fill'
    # norms, dots, stream mix
    if n.startswith('SkNormDotsWM') or n.startswith('SkDotsWM') or n.startswith('RowsP<TokRows<NormRows<5120u'):
        return 'pre-norm + dot rows (SkNormDotsWM)'
    if n.startswith('RowsP<TokRows<HcFinishRows>'):
        return 'mix finish (own launches)'
    if n.startswith('SkNormPairWM') or n.startswith('RowsP<RowsPair<TokRows<NormRows<1280u'):
        return 'q_a / kv norms'
    if n.startswith('HcPostPrePM') or n.startswith('HcPostPM') or n.startswith('HcPreAM'):
        return 'stream post + pre (HcPostPrePMG etc.)'
    # small
    if n.startswith('EngramGateWM') or n.startswith('EngRowsA'):
        return 'engram gate + rows'
    if n.startswith('EmbedRowA') or n.startswith('Broadcast4PA'):
        return 'embed + broadcast'
    if n.startswith('RmsNormA'):
        return 'other small'
    return 'answer step'


class Run:
    def __init__(self, path):
        self.path = path
        base = os.path.basename(path)
        m = re.match(r'c(\d)_b(\d+)\.log', base)
        self.card, self.block = int(m.group(1)), int(m.group(2))
        self.nb = nblocks(self.block)
        self.k = []  # (ms, launches, us, name)
        self.wall = self.rate = self.first = None
        on = False
        for line in open(path):
            p = PLINE.search(line)
            if p:
                self.wall, self.rate, self.first = float(p.group(2)), float(p.group(3)), float(p.group(4))
            if line.startswith('kernel time per type'):
                on = True
                continue
            if on:
                k = KLINE.match(line)
                if k:
                    self.k.append((float(k.group(1)), int(k.group(2)), float(k.group(3)), k.group(4).strip()))
                elif line.strip().startswith('kernels '):
                    on = False
        self.kernel_sum = sum(x[0] for x in self.k)

    def rows(self):
        """(role, ms per read, launches per read, us per launch, name) for the prompt part, answer step removed"""
        out = []
        for ms, n, us, name in self.k:
            r = role_of(name)
            nn = name.replace(' ', '')
            if nn == 'XchgPull':
                ms, n = ms - ONE_TOKEN_PULL_MS, n - 83
            elif r != 'answer step':
                extra = n % self.nb if n > self.nb else 0
                # a launch count just above a multiple of the block count: the extra launches are the answer step's
                if nn.startswith('RoutedQ2KF') or nn.startswith('EngRowsA') or nn.startswith('RmsNormA'):
                    ms, n = ms - extra * us * 1e-3, n - extra
            out.append((r, ms, n, (ms * 1e3 / n) if n else 0.0, name))
        return out

    def roles(self):
        d = {}
        for r, ms, n, _, _ in self.rows():
            a = d.setdefault(r, [0.0, 0])
            a[0] += ms
            a[1] += n
        return d


def runs():
    out = {}
    for tag, d in RUNS.items():
        for f in sorted(os.listdir(d)):
            if re.match(r'c\d_b\d+\.log$', f):
                r = Run(os.path.join(d, f))
                out['%s/c%d_b%d' % (tag, r.card, r.block)] = r
    return out


if __name__ == '__main__':
    R = runs()
    for k, r in R.items():
        print(k, 'wall', r.wall, 'rate', r.rate, 'first', r.first, 'blocks', r.nb, 'kernel sum %.1f' % r.kernel_sum)
    import sys
    tag = sys.argv[1] if len(sys.argv) > 1 else 'pp97/c2_b64'
    for row in sorted(R[tag].rows(), key=lambda x: -x[1]):
        print('%-48s %9.2f %6d %9.2f  %s' % row)
