"""Time against floor for the 3K prompt read on six B70 (tp97), from the pp97 / pp92 OWN_GPROF=2 profiles.

usage: python3 -I budget97.py [OUTDIR]      (default: ../tables)
writes:
  ledger_b64.txt            per 64-token block on card 2 (pace proxy) and card 0: every role and family against its floor
  families_by_block.txt     per read, card 2 (64 / 128 / 256) and card 0 (64 / 256): what scales with tokens / blocks
  exchanges_b64.txt         exchange launches, bytes, floors, measured, card 0 against card 2
  experts_floor.txt         experts by block size: distinct, groups, bytes, multiply-adds, the three floors, measured
  dense_forms_b64.txt       dense kernels per launch, ns per multiply-add, against the FP32 floor; Q8 against Q6 / Q5
  tp92_vs_tp97.txt          family changes tp92 -> tp97 per block size and card
  card0_vs_card2.txt        card 0 / card 2 per family (the clock signature)
  kernels_<run>.txt         every kernel type with its role (one file per run)
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model97 as M  # noqa: E402
import prof97 as P  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tables')
UNPROF_WALL_64 = 6.80     # s, the unprofiled 3K read at blocks of 64 on tp96 / tp97 (strategy note, tg97)
LAUNCH_US = 0.65          # an empty launch, event-timed as the profile times kernels (predict.py fit; 0.52 measured)
FF_OPS = 11               # FP32 operations per float-float product in SkDotsFF (mul, fma, 2-sum, adds, abs)
DECODE_OPS = 7            # instructions per expert weight decode (prefill plan calibration, u1)

ORDER = ['dense rows', 'experts gate+up', 'experts down', 'experts other', 'attention', 'compressor + indexer',
         'norms + dot rows', 'exchanges', 'small ops']
FAM = dict(P.FAM)
FAM['compressor rows'] = 'compressor + indexer'


def split_h16(roles, block):
    """RowsP<DenseRowsG<GemvH16P<160u>>> runs the router (40 per block), the compressor (7 per block) and the indexer
    proj rows: split its time by multiply-adds"""
    if 'router rows' not in roles:
        return roles
    ms, n = roles['router rows']
    nb = math.ceil(M.NTOK / block)
    it = M.idx_tokens(nb, block)
    r = 384 * M.H * M.NTOK * 40
    c = 512 * M.H * M.NTOK * 7
    p = 32 * M.H * sum(it.values())
    roles = dict(roles)
    roles['router rows'] = [ms * r / (r + c + p), 40 * nb]
    roles['compressor rows'] = [ms * c / (r + c + p), 7 * nb]
    a = roles.get('indexer q_b + proj + k rows', [0, 0])
    roles['indexer q_b + proj + k rows'] = [a[0] + ms * p / (r + c + p), a[1] + n - 47 * nb]
    return roles


def roles_of(run):
    return split_h16(run.roles(), run.block)


def floors(card, block):
    """role -> (FP32 floor s, byte floor s, macs, bytes, note) per read"""
    nb = math.ceil(M.NTOK / block)
    f = {}
    for role, (macs, by) in M.dense_read(card, block).items():
        f[role] = (2 * macs / M.ISSUE, by / M.BW, macs, by, 'mul + add per weight-token')
    ex = M.expert_read(card, block, 6, IDS)
    for k, role in (('gate+up', 'experts gate+up'), ('down', 'experts down')):
        o = ex[k]
        f[role] = (2 * o['macs'] / M.ISSUE, o['bytes'] / M.BW, o['macs'], o['bytes'], 'distinct experts x slice bytes')
    am = M.attention_read(card)
    f['attention output'] = (am / M.ISSUE, 0.0, am / 2, 0, 'half of the score + output products')
    f['attention score'] = (am / M.ISSUE, 0.0, am / 2, 0, '')
    im = M.index_read(block)
    f['index score + top-k + fill'] = (2 * im / M.ISSUE, 0.0, im, 0, 'every card the same rows')
    toks = M.NTOK * 40 * (card.dsa + card.dsf)
    dm = toks * 25 * 20480
    fnb = 2 * 24 * 20480 * 4 * 40 * nb
    f['pre-norm + dot rows (SkNormDotsWM)'] = (FF_OPS * dm / M.ISSUE, fnb / M.BW, dm, fnb, 'float-float, this card\'s tokens')
    x = M.exchanges_block(card, block)
    for k, (n, by) in x.items():
        pass
    return f


def exch_floor(card, block):
    nb = math.ceil(M.NTOK / block)
    x = M.exchanges_block(card, block)
    tot = {}
    groups = {'xchg output-a + act (XchgPull2)': ['output-a + attention-mix partials (XchgPull2)',
                                                  'expert act + FFN-mix partials (XchgPull2)'],
              'xchg output-b + ffn rows + engram (XchgPull)': ['output-b (XchgPull)', 'ffn rows (XchgPull)',
                                                               'engram rows (XchgPull)'],
              'xchg head pairs (XchgPair)': ['head pairs (XchgPair)']}
    for role, ks in groups.items():
        n = sum(x[k][0] for k in ks)
        by = sum(x[k][1] for k in ks)
        # the last block is shorter: bytes scale with tokens
        tot[role] = (n * nb, by * nb * M.NTOK / (nb * block), (by * nb * M.NTOK / (nb * block)) / M.LINK + n * nb * M.SYNC)
    return tot


def fmt_row(cols, widths):
    return ' | '.join(str(c).rjust(w) if i else str(c).ljust(w) for i, (c, w) in enumerate(zip(cols, widths)))


def table(lines, head, rows, widths=None):
    widths = widths or [max(len(str(r[i])) for r in [head] + rows) for i in range(len(head))]
    lines.append('| ' + ' | '.join(str(h) for h in head) + ' |')
    lines.append('|' + '|'.join('---' for _ in head) + '|')
    for r in rows:
        lines.append('| ' + ' | '.join(str(c) for c in r) + ' |')


def ledger(R):
    c2, c0 = R['pp97/c2_b64'], R['pp97/c0_b64']
    nb = c2.nb
    r2, r0 = roles_of(c2), roles_of(c0)
    fl = floors(M.Card(2), 64)
    xf = exch_floor(M.Card(2), 64)
    out = ['# Per 64-token block, card 2 (12 heads, 230 W card: the pace proxy) and card 0 (12 heads, 275 W card)',
           '# pp97 profiles (tp97 defaults), kernel totals over the 3K read / 52 blocks (the last block has 59 tokens).',
           '# floor = max(FP32 ops / 11.47 T/s, weight bytes / 550 GB/s); exchanges: bytes / 25 GB/s + 2.5 us each.',
           '# FP32 ops: 2 per multiply-add (a multiply, then an add; no FMA, no DPAS); dot rows 11 per float-float product.',
           '']
    rows = []
    famt = {}
    for role in sorted(r2, key=lambda k: (ORDER.index(FAM[k]) if FAM.get(k) in ORDER else 99, -r2[k][0])):
        fam = FAM.get(role)
        if fam is None:
            continue
        ms2, n2 = r2[role]
        ms0 = r0.get(role, [0, 0])[0]
        if role in fl:
            fs, bs, macs, by, note = fl[role]
            if role in ('attention output', 'attention score'):
                pass
            flo = max(fs, bs)
            bound = 'FP32' if fs >= bs else 'bytes'
        elif role in xf:
            n, by, flo = xf[role]
            fs, bs, macs = 0.0, flo, 0.0
            bound = 'link'
        else:
            fs = bs = macs = by = 0.0
            flo = n2 * LAUNCH_US * 1e-6
            bound = 'launches'
        a = famt.setdefault(fam, [0, 0, 0, 0, 0])
        a[0] += ms2
        a[1] += ms0
        a[2] += flo * 1e3
        a[3] += n2
        a[4] += macs
        rows.append([role, fam, '%.1f' % (n2 / nb), '%.2f' % (ms2 / nb), '%.2f' % (ms0 / nb),
                     '%.1f' % (by / nb / 1e6) if by else '-', '%.2f' % (bs * 1e3 / nb) if by else '-',
                     '%.2f' % (macs / nb / 1e9) if macs else '-', '%.2f' % (fs * 1e3 / nb) if fs else '-',
                     bound, '%.2f' % (flo * 1e3 / nb), '%.1fx' % (ms2 / (flo * 1e3)) if flo > 0 else '-',
                     '%.2f' % ((ms2 - flo * 1e3) / nb)])
    table(out, ['role', 'family', 'launches', 'card 2 ms', 'card 0 ms', 'MB', 'bytes ms', 'G mul-add', 'FP32 ms',
                'bound', 'floor ms', 'card 2 / floor', 'gap ms'], rows)
    out.append('')
    out.append('Families (ms per 64-token block; per read = x 52):')
    out.append('')
    rows = []
    t2 = t0 = tf = 0
    for fam in ORDER:
        if fam not in famt:
            continue
        a = famt[fam]
        t2 += a[0]
        t0 += a[1]
        tf += a[2]
        rows.append([fam, '%.0f' % (a[3] / nb), '%.2f' % (a[0] / nb), '%.1f %%' % (100 * a[0] / sum(v[0] for v in famt.values())),
                     '%.2f' % (a[1] / nb), '%.2f' % (a[2] / nb), '%.1fx' % (a[0] / a[2]) if a[2] else '-',
                     '%.2f' % ((a[0] - a[2]) / nb), '%.3f' % (a[0] / 1e3), '%.3f' % (a[2] / 1e3)])
    gap2 = UNPROF_WALL_64 * 1e3 - t2
    rows.append(['all kernels', '%.0f' % (sum(v[3] for v in famt.values()) / nb), '%.2f' % (t2 / nb), '100 %', '%.2f' % (t0 / nb),
                 '%.2f' % (tf / nb), '%.1fx' % (t2 / tf), '%.2f' % ((t2 - tf) / nb), '%.3f' % (t2 / 1e3), '%.3f' % (tf / 1e3)])
    rows.append(['gaps (unprofiled 6.80 s wall - card 2 kernels)', '', '%.2f' % (gap2 / nb), '', '', '0', '', '%.2f' % (gap2 / nb),
                 '%.3f' % (gap2 / 1e3), '0'])
    table(out, ['family', 'launches', 'card 2 ms', 'share', 'card 0 ms', 'floor ms', 'card 2 / floor', 'gap ms',
                'card 2 s per read', 'floor s per read'], rows)
    out.append('')
    out.append('profiled walls: card 2 %.2f s, card 0 %.2f s; kernels per read: card 2 %.3f s, card 0 %.3f s; '
               'unprofiled wall %.2f s' % (c2.wall, c0.wall, t2 / 1e3, t0 / 1e3, UNPROF_WALL_64))
    return out, famt


def by_block(R):
    keys = ['pp97/c2_b64', 'pp97/c2_b128', 'pp97/c2_b256', 'pp97/c0_b64', 'pp97/c0_b256']
    rs = {k: roles_of(R[k]) for k in keys}
    out = ['# Per read (ms, 3,323 tokens), by role, at blocks of 64 / 128 / 256 (pp97, tp97 defaults).',
           '# "kind": per token = the cost per read stays (within 5 %) as blocks grow; falls / grows = it moves with the',
           '# block size; launches per read fall 2x / 4x at 128 / 256. us per launch at 64 and 256 alongside.', '']
    rows = []
    roles = [r for r in rs['pp97/c2_b64'] if FAM.get(r)]
    roles += [r for r in rs['pp97/c2_b256'] if FAM.get(r) and r not in roles]
    tot = {k: 0 for k in keys}
    famsum = {}
    for role in sorted(roles, key=lambda k: (ORDER.index(FAM[k]), -rs['pp97/c2_b64'].get(k, [0])[0])):
        v = [rs[k].get(role, [0, 0])[0] for k in keys]
        n = [rs[k].get(role, [0, 0])[1] for k in keys]
        for k, x in zip(keys, v):
            tot[k] += x
        fs = famsum.setdefault(FAM[role], [0] * len(keys))
        for i, x in enumerate(v):
            fs[i] += x
        a, b = v[0], v[2]
        kind = 'per token' if a and abs(b / a - 1) < 0.05 else ('falls' if b < a else 'grows')
        rows.append([role, FAM[role]] + ['%.1f' % x for x in v] +
                    ['%+.0f %%' % (100 * (v[1] / a - 1)) if a else '-', '%+.0f %%' % (100 * (b / a - 1)) if a else '-', kind,
                     '%.1f' % (v[0] * 1e3 / n[0]) if n[0] else '-', '%.1f' % (v[2] * 1e3 / n[2]) if n[2] else '-'])
    table(out, ['role', 'family', 'c2 64', 'c2 128', 'c2 256', 'c0 64', 'c0 256', '128 vs 64', '256 vs 64', 'kind',
                'us/launch 64', 'us/launch 256'], rows)
    out.append('')
    rows = []
    for fam in ORDER:
        if fam in famsum:
            v = famsum[fam]
            rows.append([fam] + ['%.1f' % x for x in v] + ['%+.1f' % (v[1] - v[0]), '%+.1f' % (v[2] - v[0])])
    rows.append(['all kernels'] + ['%.1f' % tot[k] for k in keys] + ['%+.1f' % (tot[keys[1]] - tot[keys[0]]),
                                                                     '%+.1f' % (tot[keys[2]] - tot[keys[0]])])
    rows.append(['profiled wall'] + ['%.0f' % (R[k].wall * 1e3) for k in keys] + ['', ''])
    rows.append(['wall - kernels'] + ['%.0f' % (R[k].wall * 1e3 - tot[k]) for k in keys] + ['', ''])
    rows.append(['first step (incl. kernel build)'] + ['%.0f' % (R[k].first * 1e3) for k in keys] + ['', ''])
    table(out, ['family', 'c2 64', 'c2 128', 'c2 256', 'c0 64', 'c0 256', '128 - 64', '256 - 64'], rows)
    # best of each role over 64 / 256 (and 128): what "larger blocks, every family at its best size" would give
    out.append('')
    out.append('Every role at the cheaper of its 64- and 256-token cost (card 2), against 64 and 256 today:')
    best = 0
    lines = []
    for role in roles:
        a = rs['pp97/c2_b64'].get(role, [0])[0]
        b = rs['pp97/c2_b256'].get(role, [0])[0]
        best += min(a, b)
        if a - b > 5:
            lines.append('  %-46s 64: %7.1f  256: %7.1f  saves %6.1f at 256' % (role, a, b, a - b))
        elif b - a > 5:
            lines.append('  %-46s 64: %7.1f  256: %7.1f  costs %6.1f at 256 (keep the 64-token cost)' % (role, a, b, b - a))
    out += lines
    out.append('  sum of the minima %.1f ms; 64 today %.1f; 256 today %.1f; minima - 64 = %+.1f ms' %
               (best, tot['pp97/c2_b64'], tot['pp97/c2_b256'], best - tot['pp97/c2_b64']))
    return out


def exchanges(R):
    out = ['# Exchanges per block and per read (card 2 = 12 heads; cards 4 / 5 hold 8 heads and launch no XchgPair).',
           '# Floor: bytes this card loads from its peers / 25 GB/s + 2.5 us per launch. Measured = the exchange kernels\'',
           '# time from start to end: copy + wait for the peers\' flags (the profile does not split the two).', '']
    cd = M.Card(2)
    rows = []
    for B in (64, 128, 256):
        x = M.exchanges_block(cd, B)
        nb = math.ceil(M.NTOK / B)
        for k, (n, by) in x.items():
            rows.append([B, k, n, '%.2f' % (by / 1e6), '%.3f' % (by / M.LINK * 1e3 + n * M.SYNC * 1e3),
                         '%.1f' % (by * M.NTOK / B / 1e9)])
    table(out, ['block', 'exchange', 'launches / block', 'MB / block', 'floor ms / block', 'GB per read'], rows)
    out.append('')
    rows = []
    for k in ['pp97/c2_b64', 'pp97/c0_b64', 'pp97/c2_b128', 'pp97/c2_b256', 'pp97/c0_b256', 'pp92/c2_b64', 'pp92/c0_b64']:
        r = R[k]
        rr = roles_of(r)
        xf = exch_floor(M.Card(r.card), r.block)
        for role in ('xchg output-a + act (XchgPull2)', 'xchg output-b + ffn rows + engram (XchgPull)',
                     'xchg head pairs (XchgPair)'):
            ms, n = rr.get(role, [0, 0])
            nn, by, flo = xf[role]
            rows.append([k, role, n, '%.1f' % (n / r.nb), '%.1f' % ms, '%.1f' % (ms * 1e3 / n) if n else '-',
                         '%.1f' % (flo * 1e3), '%.2f' % (ms / (flo * 1e3)) if flo else '-',
                         '%.1f' % (by / (ms * 1e-3) / 1e9) if ms else '-'])
        tot = sum(rr.get(x, [0])[0] for x in xf)
        tfl = sum(v[2] for v in xf.values()) * 1e3
        rows.append([k, 'all exchanges', sum(rr.get(x, [0, 0])[1] for x in xf), '%.1f' % (sum(rr.get(x, [0, 0])[1] for x in xf) / r.nb),
                     '%.1f' % tot, '', '%.1f' % tfl, '%.2f' % (tot / tfl), '%.1f' % (sum(v[1] for v in xf.values()) / (tot * 1e-3) / 1e9)])
    table(out, ['run', 'kind', 'launches', 'per block', 'ms per read', 'us / launch', 'floor ms', 'measured / floor',
                'GB/s effective'], rows)
    return out


def experts(R):
    out = ['# Routed experts per read on card 2: the 3K prompt\'s own picks (u84 dump), blocks of consecutive tokens.',
           '# FP32 floor: 2 ops per slot-weight at 11.47 T/s. Decode-inclusive: + %d instructions per weight per expert group'
           % DECODE_OPS,
           '# (every row of a group decoded once; groups of <= 6 slots, OWN_MT_RUX_CAP=6). x port: every slot-weight',
           '# loads its activation float once per R rows through the L1 port (8.28 TB/s): R = 2 (two-row tiles).', '']
    cd = M.Card(2)
    rows = []
    for B in (64, 128, 256):
        nb = math.ceil(M.NTOK / B)
        e = M.expert_read(cd, B, 6, IDS)
        e16 = M.expert_read(cd, B, 16, IDS)
        r = roles_of(R['pp97/c2_b%d' % B])
        for k, role in (('gate+up', 'experts gate+up'), ('down', 'experts down')):
            o, o16 = e[k], e16[k]
            fp = 2 * o['macs'] / M.ISSUE
            by = o['bytes'] / M.BW
            dec = (2 * o['macs'] + DECODE_OPS * o['gweights']) / M.ISSUE
            dec16 = (2 * o['macs'] + DECODE_OPS * o16['gweights']) / M.ISSUE
            port2 = o['macs'] * 4 / 2 / M.PORT
            meas = r[role][0] / 1e3
            rows.append([B, k, '%.1f' % (o['distinct'] / (40 * nb)), '%.1f' % (o['groups'] / (40 * nb)),
                         '%.1f' % (o16['groups'] / (40 * nb)), '%.2f' % (o['macs'] / 1e12), '%.1f' % (o['bytes'] / 1e9),
                         '%.3f' % fp, '%.3f' % by, '%.3f' % dec, '%.3f' % dec16, '%.3f' % port2, '%.3f' % meas,
                         '%.2fx' % (meas / max(fp, by)), '%.2fx' % (meas / dec)])
    table(out, ['block', 'part', 'distinct / layer', 'groups cap 6', 'groups cap 16', 'T mul-add', 'GB',
                'FP32 floor s', 'byte floor s', 'with decode s', 'with decode, cap 16 s', 'x port (R=2) s', 'measured s',
                'measured / hard floor', 'measured / decode floor'], rows)
    out.append('')
    out.append('Per launch at 64 tokens, card 2 (us): measured against the per-launch floors of its format')
    rows = []
    run = R['pp97/c2_b64']
    e = M.expert_read(cd, 64, 6, IDS)
    for role, ms, n, us, name in run.rows():
        if role not in ('experts gate+up', 'experts down'):
            continue
        rows.append([name[:70], n, '%.1f' % us])
    table(out, ['kernel', 'launches', 'us / launch'], rows)
    return out


def dense_forms(R):
    out = ['# Dense kernels per launch at blocks of 64 (card 2, pp97) against the FP32 floor of that launch',
           '# (2 ops per multiply-add at 11.47 T/s). ps per mul-add = launch time / its multiply-adds.', '']
    cd = M.Card(2)
    run = R['pp97/c2_b64']
    nb = run.nb
    shapes = {  # role, cols, fmt -> rows per launch (card 2), layers using it
        ('q_a + kv rows', 'Q8'): ((1280 + 512) / 2, 27), ('q_a + kv rows', 'Q6'): ((1280 + 512) / 2, 13),
        ('q_b rows', 'Q8'): (6144, 27), ('q_b rows', 'Q6'): (6144, 13),
        ('o_a rows', 'Q8'): (1536 / 2, 27), ('o_b rows', 'Q8'): (864, 27), ('o_b rows', 'Q6'): (864, 13),
        ('shared down', 'Q8'): (864, 27), ('shared down', 'Q5'): (864, 13),
        ('route pick + shared gate/up', 'Q8'): (768, 27), ('route pick + shared gate/up', 'Q5'): (768, 13),
        ('engram kv rows', 'Q6'): (4272, 2)}
    cols = {'q_a + kv rows': 5120, 'q_b rows': 1280, 'o_a rows': 4096, 'o_b rows': 8192, 'shared down': 2304,
            'route pick + shared gate/up': 5120, 'engram kv rows': 6144}
    rows = []
    for role, ms, n, us, name in run.rows():
        if FAM.get(role) != 'dense rows' or 'GemvH16P' in name:
            continue
        f = 'Q8' if 'Q8' in name else 'Q6' if 'Q6' in name else 'Q5'
        if role == 'o_a rows' and f == 'Q6':
            r = 1024 if ',8u,' in name.replace(' ', '') else 512
        else:
            r = shapes[(role, f)][0]
        macs = r * cols[role] * M.NTOK / nb
        fl = 2 * macs / M.ISSUE * 1e6
        rows.append([role, f, name.replace('RowsP<DenseRowsWS<', '').replace('RoutePMRows<RowsPair<TokRows<HcFinishRows>, RowsPair<DenseRowsWS<', 'pair ')[:44],
                     n, '%.1f' % us, int(r), '%.1f' % fl, '%.2f' % (us / fl), '%.2f' % (us * 1e6 / macs)])
    # the H16 rows (router + compressor + indexer proj share one kernel type; indexer q_b its own)
    for role, ms, n, us, name in run.rows():
        if 'GemvH16P<160u' in name or 'GemvH16P<40u' in name:
            r = 384 if '160u' in name else 4096
            c = 5120 if '160u' in name else 1280
            macs = r * c * M.NTOK / nb
            fl = 2 * macs / M.ISSUE * 1e6
            rows.append([role + ' (H16 / BF16)', 'H16', name[:44], n, '%.1f' % us, r, '%.1f' % fl, '%.2f' % (us / fl),
                         '%.2f' % (us * 1e6 / macs)])
    table(out, ['role', 'fmt', 'form', 'launches', 'us / launch', 'rows (approx.)', 'FP32 floor us', 'x floor',
                'ps / mul-add'], rows)
    # Q6 / Q5 layers at the Q8 layers' time per launch (same shapes)
    rs = {}
    for role, ms, n, us, name in run.rows():
        if FAM.get(role) != 'dense rows' or 'GemvH16P' in name:
            continue
        f = 'Q8' if 'Q8' in name else 'Q6' if 'Q6' in name else 'Q5'
        a = rs.setdefault((role, f), [0, 0])
        a[0] += ms
        a[1] += n
    out.append('')
    out.append('Q6_K / Q5_K layers (13) against the Q8_0 layers (27) of the same shapes, per layer and block (us):')
    sav = 0
    for role in ('q_a + kv rows', 'q_b rows', 'o_a rows', 'o_b rows', 'route pick + shared gate/up', 'shared down'):
        q8 = rs.get((role, 'Q8'))
        lo = rs.get((role, 'Q6')) or rs.get((role, 'Q5'))
        if not q8 or not lo:
            continue
        p8 = q8[0] * 1e3 / (27 * nb)
        pl = lo[0] * 1e3 / (13 * nb)
        sav += lo[0] - p8 * 13 * nb / 1e3
        out.append('  %-30s Q8 %7.1f   Q6/Q5 %7.1f   ratio %.2f   Q6/Q5 at the Q8 time saves %6.1f ms per read' %
                   (role, p8, pl, pl / p8, lo[0] - p8 * 13 * nb / 1e3))
    out.append('  total %.1f ms per read (bytes per weight: Q6_K 0.82, Q5_K 0.69 of Q8_0)' % sav)
    return out


def tp92_97(R):
    out = ['# tp92 -> tp97 per family (ms per read). tp97 adds: rux-1 prompt expert kernels (OWN_MT_RUX=1, CAP=6), the',
           '# fused pre-norm + dot rows (skn-1), HcPostPrePMG, ATT / CK (checks only). The task text calls tp92 "before the',
           '# decode-once dense rows were widened": the dense WS kernels have the same names and times in both,',
           '# except the Q6_K o_b and engram forms (below).', '']
    rows = []
    for tag in ('c2_b64', 'c0_b64', 'c2_b128', 'c2_b256', 'c0_b256'):
        a, b = roles_of(R['pp92/' + tag]), roles_of(R['pp97/' + tag])
        fa, fb = {}, {}
        for d, f in ((a, fa), (b, fb)):
            for role, (ms, n) in d.items():
                if FAM.get(role):
                    f[FAM[role]] = f.get(FAM[role], 0) + ms
        for fam in ORDER:
            if abs(fb.get(fam, 0) - fa.get(fam, 0)) >= 5:
                rows.append([tag, fam, '%.1f' % fa.get(fam, 0), '%.1f' % fb.get(fam, 0), '%+.1f' % (fb.get(fam, 0) - fa.get(fam, 0))])
        rows.append([tag, 'all kernels', '%.1f' % sum(fa.values()), '%.1f' % sum(fb.values()),
                     '%+.1f' % (sum(fb.values()) - sum(fa.values()))])
        rows.append([tag, 'profiled wall', '%.0f' % (R['pp92/' + tag].wall * 1e3), '%.0f' % (R['pp97/' + tag].wall * 1e3),
                     '%+.0f' % ((R['pp97/' + tag].wall - R['pp92/' + tag].wall) * 1e3)])
    table(out, ['run', 'family', 'tp92', 'tp97', 'change'], rows)
    out.append('')
    out.append('Kernels with the same code in both builds whose time moved by more than 5 % (us per launch):')

    def canon(n):
        n = n.replace(' ', '')
        n = n.replace(',0u,0u>', ',0u>').replace(',1u,0u>', ',1u>').replace(',2u,0u>', ',2u>')
        return n
    for tag in ('c2_b64', 'c0_b64', 'c2_b128', 'c2_b256', 'c0_b256'):
        a = {canon(x[4]): x for x in R['pp92/' + tag].rows()}
        b = {canon(x[4]): x for x in R['pp97/' + tag].rows()}
        for k in sorted(set(a) & set(b)):
            if a[k][2] == b[k][2] and a[k][1] > 20 and abs(b[k][3] / a[k][3] - 1) > 0.05 and not k.startswith('Xchg'):
                out.append('  %-7s %-70s %8.1f -> %8.1f us (%+.0f %%), %+.1f ms per read' %
                           (tag, k[:70], a[k][3], b[k][3], 100 * (b[k][3] / a[k][3] - 1), b[k][1] - a[k][1]))
    return out


def card_ratio(R):
    out = ['# Card 0 / card 2 kernel time per family (both hold 12 heads and the same row counts within 2 %).',
           '# A uniform ratio across compute kernels is a clock difference, not a kernel one (card 0 = 0000:03, one of',
           '# the two 275 W cards; card 2 = 0000:43, one of the four 230 W cards; lane note section 24-25, e68).', '']
    rows = []
    for B in (64, 256):
        a, b = roles_of(R['pp97/c2_b%d' % B]), roles_of(R['pp97/c0_b%d' % B])
        comp2 = comp0 = 0
        for role in sorted(a, key=lambda k: -a[k][0]):
            if not FAM.get(role) or a[role][0] < 30:
                continue
            r = b.get(role, [0])[0] / a[role][0]
            rows.append([B, role, '%.1f' % a[role][0], '%.1f' % b.get(role, [0])[0], '%.3f' % r])
        for role in a:
            if FAM.get(role) and FAM[role] != 'exchanges':
                comp2 += a[role][0]
                comp0 += b.get(role, [0])[0]
        x2 = sum(a.get(r, [0])[0] for r in a if FAM.get(r) == 'exchanges')
        x0 = sum(b.get(r, [0])[0] for r in b if FAM.get(r) == 'exchanges')
        rows.append([B, 'all but exchanges', '%.1f' % comp2, '%.1f' % comp0, '%.3f' % (comp0 / comp2)])
        rows.append([B, 'exchanges', '%.1f' % x2, '%.1f' % x0, '%.3f' % (x0 / x2)])
        rows.append([B, 'card 0 extra exchange time - its compute saving', '', '%.1f' % ((x0 - x2) - (comp2 - comp0)), ''])
    table(out, ['block', 'role', 'card 2 ms', 'card 0 ms', 'card 0 / card 2'], rows)
    return out


def kernels(R, k):
    r = R[k]
    out = ['# %s: every kernel type (ms per read, launches, us per launch), its role; answer step removed' % k, '']
    rows = []
    for role, ms, n, us, name in sorted(r.rows(), key=lambda x: -x[1]):
        rows.append(['%.2f' % ms, n, '%.2f' % us, role, FAM.get(role) or '-', name])
    table(out, ['ms', 'launches', 'us', 'role', 'family', 'kernel'], rows)
    return out


def main():
    global IDS
    IDS = M.read_ids()
    R = P.runs()
    os.makedirs(OUT, exist_ok=True)
    led, famt = ledger(R)
    files = {'ledger_b64.txt': led, 'families_by_block.txt': by_block(R), 'exchanges_b64.txt': exchanges(R),
             'experts_floor.txt': experts(R), 'dense_forms_b64.txt': dense_forms(R), 'tp92_vs_tp97.txt': tp92_97(R),
             'card0_vs_card2.txt': card_ratio(R)}
    for k in R:
        files['kernels_%s.txt' % k.replace('/', '_')] = kernels(R, k)
    for fn, lines in files.items():
        with open(os.path.join(OUT, fn), 'w') as f:
            f.write('\n'.join(lines) + '\n')
    print('\n'.join(led))


IDS = None
if __name__ == '__main__':
    main()
