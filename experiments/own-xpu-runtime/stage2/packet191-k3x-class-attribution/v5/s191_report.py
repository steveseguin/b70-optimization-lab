"""Packet191 report (`s191_report`): per-class kernel cost on BOTH ranks of the k3x record line, measured in-engine.

A MEASUREMENT, never a win/loss screen. Rows (same lane, each depending on the previous): 0 k3x-on smoke (12 x 64 +
incident64, exact, first-request data proof, site rows present on both ranks); 1 ONE load of the k3x-off selection with
the views off / on / off / on / off (12 x 128 + incident64 each). `off` is the record k3x execution path byte for byte
(CPU proof: v5/evidence/k3-state.json canonical transcripts; the selection adds only the explicit `sites=off` key);
`on` records, for every kernel event of every site inside the SAMPLED halves (fixtures 9-16, 57-64, 105-112 of each
request: 24 of 127 decode positions), the device start/end timestamps read on the host at the half's own final drain,
and writes them to rank{0,1}/sites.jsonl (`packet191.site.v1`). Nothing is read from device memory, no kernel is added.

Coordinator ruling (lever synthesis 4, 2026-10-22, quoted): "on the k3x record line both ranks are 99.3% busy per hit and
every kernel class sits at its ledger floor; the only family that can still reach +2% is per-layer kernel cost on both
ranks (+1.32% per 0.01 ms per GDN layer; +2% needs 15.1 us per GDN layer, +0.5% needs 3.8 us). Build packet191 as a
measurement: the record k3x selection unchanged plus packet77-style per-class site instrumentation on both ranks as an
in-load view key, so each class's per-rank cost and its excess over the copy floor and over packet110 are measured on
the line that holds the record."

The report, per rank, per phase (rank 0: speculative half A = layers 0-23, corrected half C, boundary = layers 24-26;
rank 1: half B = layers 27-47 + head, draft) and per class: ms per half, us per GDN layer and per QSA layer, the excess
over the 537 GB/s copy floor (packet72/77 byte formulas on the pinned header census, read+write bytes, packet110's
convention) and over packet110's synthetic complete-layer call times (roofline.json, context 128), with the per-site
rows underneath. A class is flagged **lever-eligible by excess** only when its excess over the copy floor is >= 15.1 us
per GDN layer on BOTH ranks (>= 3.8 us for a screen), and every flagged class is listed with the mechanism families the
DO-NOT-REPEAT corpus closes for it (CLOSURES) and whether any open mechanism remains (OPEN) - so the report says
explicitly whether a kernel brief can honestly be priced at +2%.

Kill rules (recorded; a measurement, never a speed claim):
  exact           any view not 13/13 exact, or draft proposals / per-prompt acceptance differ across the five views -> STOP;
  control drift   max/min of the three `off` views - 1 > 0.5% -> STOP (instrumentation leaking into the controls);
  overhead        mean(on rates) / mean(off rates) < 0.93 -> the class table is INADMISSIBLE (packet128's rule: a failed
                  overhead gate withholds rankings; event times are never corrected by a throughput ratio);
  completeness    the per-half sum of every recorded class deviates from the half body (rank 0: the `layer_body` host
                  scope of the same half; rank 1: its `half_completion_ms`) by more than 10% (median over sampled halves)
                  -> STOP (missing events; packet157: an absent stream is never a zero).
Reported (never a condition): the `off` views against packet189's two measured k3x views (62.242 / 62.225, hash-pinned,
read in place) and the packet190 record (62.345282): timing equivalence of the record path within 0.5%; the on-view
cost on A / B / Bd / D (interval means off vs on); the three sampled windows separately (QSA attention grows with the
context); the per-site table.
"""
import hashlib, json, math, statistics as st
from pathlib import Path

RECORD = 62.345281904743764  # packet190 k3x chain WS128 (LocalMaxxing cmvk51wfn001gng01fpbfy89q)
CHAIN_BAR_US = 15.1          # lever synthesis 4, section 2.1: +2 % needs 15.1 us per GDN layer on both ranks
SCREEN_BAR_US = 3.8          # +0.5 %
GAIN_PCT_PER_10US = 1.32     # +1.32 % per 0.01 ms per GDN layer (both ranks)
FLOOR_GBS = 537.0            # packet110's copy reference (read + write bytes)
CONTROL, INSTRUMENTED = 'k3x-off', 'k3x-on'
ORDER = (CONTROL, INSTRUMENTED, CONTROL, INSTRUMENTED, CONTROL)
KILL = dict(control_drift_pct=0.5, instrumented_over_control_min=0.93, class_sum_vs_body_pct=10.0, timing_equivalence_pct=0.5)
SAMPLED = tuple(range(9, 17)) + tuple(range(57, 65)) + tuple(range(105, 113))
WINDOWS = {'9-16': range(9, 17), '57-64': range(57, 65), '105-112': range(105, 113)}
STAGE = Path(__file__).resolve().parents[2]
ROOT = STAGE.parents[2]
RULE = ('measurement: per rank, per phase, per class: ms/half, us per GDN and QSA layer, excess over the 537 GB/s copy floor '
        '(packet72/77 byte formulas) and over packet110 (roofline.json @128); lever-eligible by excess iff excess over the floor >= 15.1 us '
        'per GDN layer on BOTH ranks (3.8 us screen) with the DO-NOT-REPEAT closures named; kill rules: exact/proposals, off drift > 0.5 %, '
        'on/off < 0.93 (table withheld, never ratio-corrected), class sums vs body > 10 %')
# Real prior device data and the two byte/cost references, read in place and pinned by sha256 (never copied).
P189 = dict(summary='experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/v5/evidence/device-row1-bracket-v3k-k3x-B-p189/bracket-summary.json',
            sha256='e11a02d5350e35d5c4910dfe6525725d5ca7ede743216c32f4ab18aafc88a9cb', k3x_rates=[62.24199434282818, 62.22542821257332])
P190 = dict(summary='experiments/own-xpu-runtime/stage2/packet190-record-bundle-k3x/evidence/device-cards01-p190-a/WS128/run/summary.json',
            sha256='76bc7015b984ac489ec8d390cd8e588be5727f435705392c91919ef1fdf1f8bb', rate=RECORD)
P110 = dict(path='experiments/own-xpu-runtime/stage2/packet110-class-roofline/roofline.json', sha256='93fdf583d045a9ab853cd1a62aa26b6f21654983c8513674c31ea05da0c66a19')
P77_BYTES = dict(path='experiments/own-xpu-runtime/stage2/packet77-attribution/byte_formulas.py', sha256='3e5898e513d837696c3d59a37755c95c21bc337bc7669cb6a17e8f900a6ea382')
P72_CENSUS = dict(path='experiments/own-xpu-runtime/stage2/packet72-occupancy/header-census.json', sha256='11c3341b995f3b3160bfd30a2bd0dd2c9513d67cb9f1cad63b0fd59643a1229f')

# Class groups (the brief's list) over the engine's site labels at the record selection (packet189 full-shape launch census).
GROUPS = {
    'experts': ('expsgate', 'expsup', 'expsdown', 'expsact', 'expsgate.check', 'expsup.check', 'expsdown.check'),
    'dense': ('gdn.qkv', 'gdn.z', 'attention', 'qsa.qgate', 'qsa.k', 'qsa.v', 'qsa.iq', 'qsa.ik'),
    'qsa_attention': ('qsa.attention', 'qsa.select', 'qsa.pool', 'qsa.prepare'),
    'recurrence': ('gdn.recurrence', 'gdn.conv', 'gdn.gated'),
    'hc': ('hc.a.gate', 'hc.f.gate', 'hc.a.low', 'hc.f.low', 'hc.a.mix', 'hc.f.mix', 'hc.a.act', 'hc.f.act', 'hc.a.inject', 'hc.f.inject'),
    'norms': ('hc.a.norm', 'hc.f.norm'),
    'route_small': ('route', 'router', 'moe', 'ffn.combine', 'shexpdown', 'shexpact', 'shexpgate', 'shexpup', 'shared_gate', 'gdn.a', 'gdn.b'),
}
SITE_GROUP = {s: g for g, sites in GROUPS.items() for s in sites}
LAYER_GROUPS = tuple(GROUPS) + ('ple',)
P110_SITE = {'gdn.a': 'small.gdn.ab', 'router': 'small.ffn.q6'}  # the rest share packet110's site names
QSA_LAYERS = frozenset(k for k in range(48) if k % 4 == 3)

# DO-NOT-REPEAT closures per class (analysis/dnr-class-grep.txt; all 223 stage2 DO-NOT-REPEAT.md files grepped) and what is open.
CLOSURES = {
    'experts': ['packet65 wide64 (in production)', 'packet73 experts2 (lost)', 'packet81 packed activation reads (neutral: "no repeat without ALU/latency evidence")',
                'packet95 E2 (arena) / E3 (packet100 negative)', 'packet104/104b tile16 arms 0.95-1.03 and packet142: "Packet104/104b gate/up tile16 lost. Do not rerun that arm"',
                'packet119 down-warm 1.079x', 'packet162 IQ2 lookup (CPU 22-40x, closed before device)', 'packet173 E1n2 +0.22 %', 'packet102/115 ILP/GRF (no measured win)',
                'packet142/145 kernel-order layouts (null)'],
    'dense': ['packet74 packed Q6_K/Q8_0 reads -0.8/-2.4/-2.9 % ("no repeat without a new unpack mechanism")', 'packet93/93x SWAR unpack (lane-A loss)',
              'packet183 S1 metadata scales -6.2 %', 'packet175 D2 warm-ahead 1.44x', 'packet175b D1 scale-word multicast 1.0665x', 'packet113 "near measured bandwidth limit"'],
    'qsa_attention': ['packet107 local sharing (lost)', 'packet116 schedule', 'context-dependent (52 us @128 -> 610 us @4096; the suite prompts are 60-90 tokens)'],
    'recurrence': ['packet82/82b rec-both-plus (in production)', 'packet67 rec-head -11.8 % ("Closed: extra launch and global scratch")',
                   'packet49d rows4/rows8 (K2 keeps round2)', 'approximate gate math / reordered reductions excluded (exactness)'],
    'hc': ['packet60 three-kernel fusion (in production; "do not reopen")', 'packet73 hc-wide +0.73 % (in production; virtual-four rejected: spills)',
           'packet94 norm-consumer fusion (closed)', 'packet117', 'packet122 HC remap 0.913x', 'packet140 N1/N3/G1 priors <= +0.3 %',
           'packet67 four-stream -6..-22 % ("do not repeat without measured in-engine GB/s per site")'],
    'norms': ['packet78 -0.65 %', 'packet94 "Do not duplicate a norm per consumer workgroup"'],
    'route_small': ['packet78 route-fast (in production)', 'packet109 epilogues (in production)', 'packet112 pruned top10 (missed its kill gate; "Forbidden")',
                    'packet164 "Not identifiable ... visible preceding gaps total 0.003 ms/half" (revisit: matched causal evidence of >= 0.4 ms/half)',
                    'p30/p49d small tuples (in production)'],
    'head': ['packet93 transpose (lane-A loss)', 'packet161 argmax (99.99992 % reads)', 'B-only ceiling +0.19 % (lever synthesis 4)'],
    'draft': ['packet158 lane closure (revisit only >= 0.42 ms/hit)', 'packet156/79/106b/114/108/122/161/126', 'D-only ceiling +0.23 % (lever synthesis 4)'],
    'ple': ['layer-0 PLE only (one layer per rank-0 half); no ledger row'],
}
OPEN = {g: [] for g in CLOSURES}  # no open mechanism is known for any class (lever synthesis 4 section 2.2; packet142 closes packet104b)
OVERHEAD_RULE = ('packet128: "A failed overhead gate withholds rankings. Do not correct event times by a throughput ratio." '
                 '(packet128b measured 0.728 and withheld; packet191 samples 24 of 127 fixtures)')


class Incomplete(ValueError):
    pass


def demand(ok, reason):
    if not ok:
        raise Incomplete(reason)


def mean(values):
    values = list(values)
    return st.mean(values) if values else None


def median(values):
    values = list(values)
    return st.median(values) if values else None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pinned(pin, key='path'):
    path = ROOT / pin[key]
    demand(path.is_file(), 'pinned input missing: ' + str(path))
    digest = sha(path)
    demand(digest == pin['sha256'], 'pinned input changed where it is retained: %s (%s)' % (path, digest))
    return path


# ---------------------------------------------------------------- interval model (packet189's, unchanged)
def intervals_v3(r, limit=99):
    """Vendored packet85 intervals plus the boundary command (rank 0, op 15) on the ready side, with the draft's observed wall
    (draft_rows.draft_wall_ms, publication observed) as D. The op-9 command duration is kept as D_op9 (reported only)."""
    from interval_model import intervals, duration
    rows = intervals(r, limit)
    boundaries = {t['position']: t for t in r['rank_trace'] if t['rank'] == 0 and t['op'] == 15}
    walls = {d['position']: d['draft_wall_ms'] for d in r.get('draft_rows', []) if d.get('draft_wall_ms') is not None}
    for x in rows:
        b = boundaries.get(x['position'])
        x['Bd'] = duration(b) if b else 0.0
        demand(x['position'] in walls and math.isfinite(walls[x['position']]) and walls[x['position']] > 0, 'missing draft wall (draft_rows.draft_wall_ms) at position %d' % x['position'])
        x['D_op9'] = x['D']
        x['D'] = walls[x['position']]
        ready = max(x['D'], x['R'] + x['C'] + x['Bd'])
        race = max(x['B'], x['A'] + x['spec_start_offset_ms'])
        x['ready_v3_ms'] = ready
        x['boundary_over_draft'] = x['Bd'] > x['D']
        x['prediction_without_gaps_ms'] = ready + race
        x['unresolved_control_gaps_ms'] = x['elapsed_ms'] - ready - race
    return rows


ENVELOPE = ('half_total', 'layer_body', 'snapshot', 'token_history', 'token_prep', 'boundary_total', 'boundary_body', 'handoff_export')


def envelope(view_dir, prompt_ids):
    """Rank-0 host scopes per decode cycle (p150 records in rank0/timings.jsonl) and p76 retirement per speculative half."""
    view_dir = Path(view_dir)
    sums, counts, retire, prepare, halves = {k: 0.0 for k in ENVELOPE}, {k: 0 for k in ENVELOPE}, 0.0, 0.0, 0
    for prompt in prompt_ids:
        r = json.loads((view_dir / prompt / 'receipt.json').read_text())
        stamps = r['token_timestamps'][:100]
        path = view_dir / prompt / 'rank0/timings.jsonl'
        demand(path.is_file(), 'missing rank0 timing stream: ' + str(path))
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            x = json.loads(line)
            if x.get('p150_segment') in sums and stamps[0] <= x['start'] <= x['end'] <= stamps[-1]:
                sums[x['p150_segment']] += x['ms']; counts[x['p150_segment']] += 1
            elif 'half_completion_ms' in x and x.get('speculative') and x.get('fixture', 0) >= 2:
                retire += x.get('p76_retirement_ms', 0.0); prepare += x.get('prepare_ms', 0.0); halves += 1
    per = lambda k: sums[k] / counts[k] if counts[k] else None
    half, body = per('half_total'), per('layer_body')
    parts = {k: per(k) or 0.0 for k in ('snapshot', 'token_history', 'token_prep')}
    out = dict(scopes_ms={k: per(k) for k in ENVELOPE}, scope_counts=counts,
               p76_retirement_ms_per_half=retire / halves if halves else None, prepare_ms_per_half=prepare / halves if halves else None)
    if half is not None and body is not None:
        env = half - body
        out.update(rank0_half_envelope_ms=env, envelope_parts_ms=parts, envelope_unattributed_ms=env - sum(parts.values()))
    bt, bb = per('boundary_total'), per('boundary_body')
    if bt is not None and bb is not None:
        out.update(boundary_envelope_ms=bt - bb, boundary_export_ms=per('handoff_export'))
    return out


def view_stats(view_dir, prompt_ids, variant, require_exact=True):
    """Interval statistics + rank-0 envelope of one view directory (12 prompts, first 99 intervals each)."""
    view_dir = Path(view_dir)
    rows, boundaries = [], 0
    for prompt in prompt_ids:
        receipt = view_dir / prompt / 'receipt.json'
        demand(receipt.is_file(), 'missing request receipt: ' + str(receipt))
        r = json.loads(receipt.read_text())
        demand(r.get('passed') is True and (r.get('exact_oracle') is True or not require_exact) and r.get('cached_tokens') == 0, 'request not exact/cold: ' + prompt)
        demand('rank_trace' in r and 'guess_rows' in r and 'generated_token_completion_timestamps' in r and 'draft_rows' in r, 'missing native correction/draft stream: ' + prompt)
        part = intervals_v3(r)
        demand(len(part) == 99, 'expected 99 intervals per 128-token prompt: ' + prompt)
        n = sum(1 for t in r['rank_trace'] if t['rank'] == 0 and t['op'] == 15)
        demand(n > 0, 'every packet191 view runs the boundary: ' + prompt)
        boundaries += n
        rows += part
    hits = [x for x in rows if x['hit']]
    misses = [x for x in rows if not x['hit']]
    demand(len(hits) >= 600 and len(misses) >= 100, 'too few hit/miss intervals')
    return dict(
        variant=variant, intervals=len(rows), hits=len(hits), misses=len(misses), boundary_commands=boundaries,
        hit=dict(D=mean(x['D'] for x in hits), D_op9=mean(x['D_op9'] for x in hits), A=mean(x['A'] for x in hits), B=mean(x['B'] for x in hits), Bd=mean(x['Bd'] for x in hits),
                 offset=mean(x['spec_start_offset_ms'] for x in hits), ready=mean(x['ready_v3_ms'] for x in hits),
                 boundary_over_draft=mean(float(x['boundary_over_draft']) for x in hits),
                 rank1_binds_emission=mean(float(x['B'] >= x['A'] + x['spec_start_offset_ms']) for x in hits),
                 G=mean(x['unresolved_control_gaps_ms'] for x in hits), elapsed=mean(x['elapsed_ms'] for x in hits)),
        miss=dict(D=mean(x['D'] for x in misses), R=mean(x['R'] for x in misses), C=mean(x['C'] for x in misses), Bd=mean(x['Bd'] for x in misses),
                  A=mean(x['A'] for x in misses), B=mean(x['B'] for x in misses), G=mean(x['unresolved_control_gaps_ms'] for x in misses),
                  elapsed=mean(x['elapsed_ms'] for x in misses)),
        pooled_interval_ms=mean(x['elapsed_ms'] for x in rows), envelope=envelope(view_dir, prompt_ids),
        definition='packet85 intervals (vendored) + boundary on the ready side; D = draft_rows.draft_wall_ms (publication observed); hit = guess verified at the starting emission')


# ---------------------------------------------------------------- site rows
def classify(label):
    """(layer or None, site, group) of an engine site label."""
    if label.startswith('blk.'):
        parts = label.split('.', 2)
        try:
            layer = int(parts[1])
        except ValueError:
            return None, label, 'unknown'
        site = parts[2] if len(parts) > 2 else ''
        if site.startswith('ple.'):
            return layer, site, 'ple'
        return layer, site, SITE_GROUP.get(site, 'unknown')
    if label == 'draft':
        return None, 'draft', 'draft'
    if label.startswith('final.') or label in ('logits', 'argmax'):
        return None, label, 'head'
    if label == 'embedding':
        return None, label, 'embedding'
    if label.startswith('begin.') or label.startswith('commit.') or label == 'streams':
        return None, label, 'control'
    return None, label, 'unknown'


def read_rows(path):
    path = Path(path)
    if not path.is_file():
        return [], []
    sites, halves = [], []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        x = json.loads(line)
        schema = x.get('schema')
        if schema == 'packet191.site.v1':
            sites.append(x)
        elif schema == 'packet65.half.v1':
            halves.append(x)
    return sites, halves


def group_halves(rows, rank):
    """Site rows -> {(half id, phase): dict(phase, fixture, position, speculative, corrected, layers={layer: {site: us}}, other={site: us}, events)}.
    The rank-1 draft shares the id of the half it follows (the engine only opens a new id per half/boundary), hence the (id, phase) key."""
    out = {}
    for r in rows:
        demand(r['rank'] == rank, 'site row of another rank in rank %d stream' % rank)
        demand(isinstance(r['start_ns'], int) and isinstance(r['end_ns'], int) and r['end_ns'] > r['start_ns'], 'zero/negative compute event: ' + r['label'])
        h = out.setdefault((r['half'], r['phase']), dict(phase=r['phase'], fixture=r['fixture'], position=r['position'], speculative=bool(r['speculative']),
                                                        corrected=bool(r.get('corrected')), layers={}, other={}, events=0, labels=set()))
        demand(h['position'] == r['position'], 'half %s mixes positions' % r['half'])
        us = (r['end_ns'] - r['start_ns']) / 1000.0
        layer, site, group = classify(r['label'])
        if layer is None:
            h['other'][site] = h['other'].get(site, 0.0) + us
        else:
            h['layers'].setdefault(layer, {})[site] = h['layers'].setdefault(layer, {}).get(site, 0.0) + us
        h['events'] += 1
        h['labels'].add(r['label'])
    return out


def sites_census(view_dir, names, variant):
    """Count the site rows of a view (both ranks, every request). On: rows on both ranks of every request; off: none."""
    view_dir = Path(view_dir)
    per_rank = {0: 0, 1: 0}
    requests_with_rows = {0: 0, 1: 0}
    halves = {0: 0, 1: 0}
    for name in names:
        for rank in (0, 1):
            sites, half_rows = read_rows(view_dir / name / f'rank{rank}/sites.jsonl')
            per_rank[rank] += len(sites)
            halves[rank] += len(half_rows)
            requests_with_rows[rank] += bool(sites)
    expected = variant == INSTRUMENTED
    total = per_rank[0] + per_rank[1]
    passed = (total > 0 and requests_with_rows[0] == len(names) and requests_with_rows[1] == len(names)) if expected else total == 0
    return dict(variant=variant, expected_present=expected, rows_total=total, rows_per_rank={str(k): v for k, v in per_rank.items()},
                half_rows_per_rank={str(k): v for k, v in halves.items()}, requests=len(names),
                requests_with_rows_per_rank={str(k): v for k, v in requests_with_rows.items()}, passed=bool(passed))


# ---------------------------------------------------------------- floors and references
def floor_model():
    """packet72/77 byte formulas on the pinned header census: (layer, site, position) -> floor us at 537 GB/s (read + write), or None."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('p77_byte_formulas', pinned(P77_BYTES))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    tensors = json.loads(pinned(P72_CENSUS).read_text())['tensors']
    account = m.accounting(tensors)
    cache = {}

    def floor_us(layer, site, position):
        key = (layer, site, position if site in ('qsa.select', 'qsa.attention', 'qsa.pool') else -1)
        if key not in cache:
            try:
                b = account(layer, site, position)
                cache[key] = (b['read_bytes'] + b['write_bytes']) / (FLOOR_GBS * 1000.0)
            except (ValueError, KeyError):
                cache[key] = None
        return cache[key]
    return floor_us


def packet110_reference():
    """packet110 roofline.json rows at context 128 -> {(kind, site): dict(measured_us, floor_us, above_floor_us)}."""
    rows = json.loads(pinned(P110).read_text())['rows']
    return {(r['kind'], r['site']): dict(measured_us=r['measured_us'], floor_us=r['floor_us'], above_floor_us=r['above_floor_us']) for r in rows if r['context'] == 128}


def packet189_k3x_reference(summary_path=None):
    path = Path(summary_path) if summary_path else pinned(P189, 'summary')
    if summary_path:
        demand(sha(path) == P189['sha256'], 'packet189 bracket summary changed')
    s = json.loads(path.read_text())
    rates = [v['rate'] for v in s['views'] if v['variant'] == 'k3x']
    demand(rates == P189['k3x_rates'] and s.get('kind') == 'bracket' and all(v['all_13_exact'] for v in s['views']), 'packet189 k3x views differ from their pin')
    return dict(rates=rates, source=P189['summary'], sha256=P189['sha256'], read_in_place=True,
                hit_elapsed_ms=[v['interval_stats']['hit']['elapsed'] for v in s['views'] if v['variant'] == 'k3x'])


def packet190_record_reference():
    s = json.loads(pinned(P190, 'summary').read_text())
    rate = s['class_balanced_tok_s_1_100_intervals_after_ttft']['median']
    demand(rate == RECORD, 'packet190 record metric differs from its pin')
    return dict(rate=rate, source=P190['summary'], sha256=P190['sha256'], read_in_place=True)


# ---------------------------------------------------------------- attribution of one instrumented view
def half_bodies(view_dir, prompt, rank):
    """rank 0: (fixture, position, speculative, corrected) -> layer_body ms of that half (the k-th layer_body scope pairs with the
    k-th half record of rank0/timings.jsonl); rank 1: -> half_completion_ms."""
    path = Path(view_dir) / prompt / f'rank{rank}/timings.jsonl'
    demand(path.is_file(), 'missing rank timing stream: ' + str(path))
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    halves = [x for x in rows if 'half_completion_ms' in x]
    key = lambda x: (x['fixture'], x['position'], bool(x['speculative']), bool(x.get('corrected')))
    if rank == 1:
        return {key(x): x['half_completion_ms'] for x in halves}
    # rank 0: the half records are written per half, the p150 scopes are flushed at the end of the request (same order).
    scopes = [x for x in rows if x.get('p150_segment') == 'layer_body']
    demand(len(scopes) == len(halves), 'rank 0: %d layer_body scopes for %d half records (%s)' % (len(scopes), len(halves), prompt))
    demand(all(a['position'] == b['position'] for a, b in zip(scopes, halves)), 'rank 0: layer_body scopes do not pair with the half records in order (%s)' % prompt)
    return {key(b): a['ms'] for a, b in zip(scopes, halves)}


def phase_of(rank, h):
    if h['phase'] == 'boundary':
        return 'boundary'
    if h['phase'] == 'draft':
        return 'draft'
    if rank == 0:
        return 'corrected' if h['corrected'] else ('speculative' if h['speculative'] else 'plain')
    return 'half'


EXPECTED_LAYERS = {(0, 'speculative'): range(0, 24), (0, 'corrected'): range(0, 24), (0, 'plain'): range(0, 24), (0, 'boundary'): range(24, 27), (1, 'half'): range(27, 48)}


def attribute_view(view_dir, prompt_ids, floor_us=None, p110=None):
    """Per rank, per phase, per class (and per site): the sampled halves of one instrumented view."""
    view_dir = Path(view_dir)
    floor_us = floor_us or floor_model()
    p110 = p110 or packet110_reference()
    halves = {0: [], 1: []}
    dropped = {0: dict(cancelled=0, incomplete=0, unsampled=0), 1: dict(cancelled=0, incomplete=0, unsampled=0)}
    unknown = set()
    for prompt in prompt_ids:
        for rank in (0, 1):
            rows, half_rows = read_rows(view_dir / prompt / f'rank{rank}/sites.jsonl')
            demand(rows, 'instrumented view without site rows: %s rank %d' % (prompt, rank))
            cancelled = {h['half'] for h in half_rows if h.get('cancelled')}
            bodies = half_bodies(view_dir, prompt, rank)
            for hid, h in group_halves(rows, rank).items():
                unknown |= {l for l in h['labels'] if classify(l)[2] == 'unknown'}
                if hid[1] == 'half' and hid[0] in cancelled:
                    dropped[rank]['cancelled'] += 1; continue
                if h['fixture'] not in SAMPLED:
                    dropped[rank]['unsampled'] += 1; continue
                phase = phase_of(rank, h)
                expected = EXPECTED_LAYERS.get((rank, phase))
                if expected is not None and (sorted(h['layers']) != list(expected) or any('ffn.combine' not in h['layers'][k] for k in expected)):
                    dropped[rank]['incomplete'] += 1; continue
                if phase == 'draft':
                    body = None
                elif phase == 'boundary':
                    body = None
                else:
                    body = bodies.get((h['fixture'], h['position'], h['speculative'], h['corrected']))
                    demand(body is not None, 'no body record for rank %d half at position %d (%s)' % (rank, h['position'], prompt))
                kernel_ms = (sum(sum(v.values()) for v in h['layers'].values()) + sum(h['other'].values())) / 1000.0
                halves[rank].append(dict(prompt=prompt, phase=phase, fixture=h['fixture'], position=h['position'], layers=h['layers'], other=h['other'],
                                         events=h['events'], kernel_ms=kernel_ms, body_ms=body))
    demand(not unknown, 'unclassified site labels: ' + ', '.join(sorted(unknown)))
    table, completeness = {}, {}
    for rank in (0, 1):
        for phase in sorted({h['phase'] for h in halves[rank]}):
            sample = [h for h in halves[rank] if h['phase'] == phase]
            if phase in ('speculative', 'corrected', 'plain', 'half'):
                ratios = [h['kernel_ms'] / h['body_ms'] for h in sample if h['body_ms']]
                completeness[f'rank{rank}/{phase}'] = dict(halves=len(sample), kernel_ms=median(h['kernel_ms'] for h in sample), body_ms=median(h['body_ms'] for h in sample),
                                                           kernel_over_body=median(ratios), deviation_pct=100 * abs(1 - (median(ratios) or 0)))
            groups = {}
            for h in sample:
                for layer, sites in h['layers'].items():
                    kind = 'qsa' if layer in QSA_LAYERS else 'gdn'
                    for site, us in sites.items():
                        g = classify(f'blk.{layer}.{site}')[2]
                        row = groups.setdefault(g, dict(per_half=[], gdn=[], qsa=[], sites={}))
                        s = row['sites'].setdefault(site, dict(gdn=[], qsa=[], floor_gdn=[], floor_qsa=[], p110=p110.get(('GDN', P110_SITE.get(site, site)), {}).get('measured_us'),
                                                                 p110_qsa=p110.get(('QSA', P110_SITE.get(site, site)), {}).get('measured_us')))
                        s[kind].append(us)
                        f = floor_us(layer, site, h['position'])
                        if f is not None:
                            s['floor_' + kind].append(f)
                for site, us in h['other'].items():
                    g = classify(site)[2]
                    row = groups.setdefault(g, dict(per_half=[], gdn=[], qsa=[], sites={}))
                    row['sites'].setdefault(site, dict(gdn=[], qsa=[], floor_gdn=[], floor_qsa=[], p110=None, p110_qsa=None))['gdn'].append(us)
                # per-half group sums and per-layer group sums
                layer_sums = {}
                for layer, sites in h['layers'].items():
                    for site, us in sites.items():
                        g = classify(f'blk.{layer}.{site}')[2]
                        layer_sums.setdefault(g, {}).setdefault(layer, 0.0)
                        layer_sums[g][layer] += us
                for g, per_layer in layer_sums.items():
                    groups[g]['per_half'].append(sum(per_layer.values()) / 1000.0)
                    for layer, us in per_layer.items():
                        groups[g]['qsa' if layer in QSA_LAYERS else 'gdn'].append(us)
                for g in ('head', 'draft', 'embedding', 'control'):
                    v = sum(us for site, us in h['other'].items() if classify(site)[2] == g)
                    if v:
                        groups.setdefault(g, dict(per_half=[], gdn=[], qsa=[], sites={}))['per_half'].append(v / 1000.0)
            out = {}
            for g, row in groups.items():
                sites = {}
                for site, s in row['sites'].items():
                    us_g, us_q = median(s['gdn']), median(s['qsa'])
                    fl_g, fl_q = median(s['floor_gdn']), median(s['floor_qsa'])
                    sites[site] = dict(us_per_gdn_layer=us_g, us_per_qsa_layer=us_q, floor_us_gdn=fl_g, floor_us_qsa=fl_q,
                                       excess_floor_us_gdn=None if us_g is None or fl_g is None else us_g - fl_g,
                                       excess_floor_us_qsa=None if us_q is None or fl_q is None else us_q - fl_q,
                                       packet110_us_gdn=s['p110'], excess_packet110_us_gdn=None if us_g is None or s['p110'] is None else us_g - s['p110'],
                                       packet110_us_qsa=s['p110_qsa'], excess_packet110_us_qsa=None if us_q is None or s['p110_qsa'] is None else us_q - s['p110_qsa'],
                                       calls_gdn=len(s['gdn']), calls_qsa=len(s['qsa']))
                def summed(key, kind):
                    vals = [v[key] for v in sites.values() if v[key] is not None and v['us_per_%s_layer' % kind] is not None]
                    return sum(vals) if vals else None
                covered = lambda kind, key: sum(v['us_per_%s_layer' % kind] for v in sites.values() if v[key] is not None and v['us_per_%s_layer' % kind] is not None)
                total = lambda kind: sum(v['us_per_%s_layer' % kind] for v in sites.values() if v['us_per_%s_layer' % kind] is not None)
                out[g] = dict(ms_per_half=median(row['per_half']), halves=len(row['per_half']),
                              us_per_gdn_layer=median(row['gdn']), us_per_qsa_layer=median(row['qsa']), gdn_layer_samples=len(row['gdn']), qsa_layer_samples=len(row['qsa']),
                              floor_us_per_gdn_layer=summed('floor_us_gdn', 'gdn'), excess_floor_us_per_gdn_layer=summed('excess_floor_us_gdn', 'gdn'),
                              floor_us_per_qsa_layer=summed('floor_us_qsa', 'qsa'), excess_floor_us_per_qsa_layer=summed('excess_floor_us_qsa', 'qsa'),
                              floor_coverage_gdn=(covered('gdn', 'floor_us_gdn') / total('gdn')) if total('gdn') else None,
                              packet110_us_per_gdn_layer=summed('packet110_us_gdn', 'gdn'), excess_packet110_us_per_gdn_layer=summed('excess_packet110_us_gdn', 'gdn'),
                              packet110_us_per_qsa_layer=summed('packet110_us_qsa', 'qsa'), excess_packet110_us_per_qsa_layer=summed('excess_packet110_us_qsa', 'qsa'),
                              packet110_coverage_gdn=(covered('gdn', 'packet110_us_gdn') / total('gdn')) if total('gdn') else None,
                              sites=sites)
            table[f'rank{rank}/{phase}'] = out
    windows = {}
    for rank in (0, 1):
        for name, rng in WINDOWS.items():
            sample = [h for h in halves[rank] if h['fixture'] in rng and h['phase'] in ('speculative', 'half')]
            if not sample:
                continue
            per = {}
            for h in sample:
                for layer, sites in h['layers'].items():
                    for site, us in sites.items():
                        per.setdefault(classify(f'blk.{layer}.{site}')[2], []).append((layer, us))
            windows[f'rank{rank}/{name}'] = dict(halves=len(sample), ms_per_half={g: sum(us for _, us in v) / len(sample) / 1000.0 for g, v in per.items()},
                                               qsa_attention_us_per_qsa_layer=median(us for layer, us in per.get('qsa_attention', []) if layer in QSA_LAYERS))
    return dict(halves={str(r): len(halves[r]) for r in (0, 1)}, dropped={str(r): dropped[r] for r in (0, 1)}, completeness=completeness, table=table, windows=windows,
                sampled_fixtures=list(SAMPLED), floor='packet72/77 byte formulas (read + write) / 537 GB/s', packet110='roofline.json context 128 (GDN rows for GDN layers, QSA rows for QSA layers)')


# ---------------------------------------------------------------- the report
def class_table(attributions):
    """Merge the on views: per rank, per phase, per class medians across views (reported per view too)."""
    merged = {}
    keys = sorted({k for a in attributions for k in a['table']})
    for key in keys:
        groups = sorted({g for a in attributions for g in a['table'].get(key, {})})
        merged[key] = {}
        for g in groups:
            rows = [a['table'][key][g] for a in attributions if g in a['table'].get(key, {})]
            m = {}
            for field in ('ms_per_half', 'us_per_gdn_layer', 'us_per_qsa_layer', 'floor_us_per_gdn_layer', 'excess_floor_us_per_gdn_layer', 'floor_us_per_qsa_layer',
                          'excess_floor_us_per_qsa_layer', 'packet110_us_per_gdn_layer', 'excess_packet110_us_per_gdn_layer', 'packet110_us_per_qsa_layer',
                          'excess_packet110_us_per_qsa_layer', 'floor_coverage_gdn', 'packet110_coverage_gdn'):
                vals = [r[field] for r in rows if r.get(field) is not None]
                m[field] = median(vals)
            m['per_view'] = [dict(ms_per_half=r['ms_per_half'], us_per_gdn_layer=r['us_per_gdn_layer'], excess_floor_us_per_gdn_layer=r['excess_floor_us_per_gdn_layer']) for r in rows]
            m['halves'] = sum(r['halves'] for r in rows)
            first = lambda s: next(r['sites'][s] for r in rows if s in r['sites'])
            m['sites'] = rows[0]['sites'] if len(rows) == 1 else {s: dict(us_per_gdn_layer=median(r['sites'][s]['us_per_gdn_layer'] for r in rows if s in r['sites'] and r['sites'][s]['us_per_gdn_layer'] is not None),
                                                                            us_per_qsa_layer=median(r['sites'][s]['us_per_qsa_layer'] for r in rows if s in r['sites'] and r['sites'][s]['us_per_qsa_layer'] is not None),
                                                                            floor_us_gdn=first(s)['floor_us_gdn'], packet110_us_gdn=first(s)['packet110_us_gdn'],
                                                                            excess_floor_us_gdn=median(r['sites'][s]['excess_floor_us_gdn'] for r in rows if s in r['sites'] and r['sites'][s]['excess_floor_us_gdn'] is not None),
                                                                            excess_packet110_us_gdn=median(r['sites'][s]['excess_packet110_us_gdn'] for r in rows if s in r['sites'] and r['sites'][s]['excess_packet110_us_gdn'] is not None))
                                                                   for s in sorted({s for r in rows for s in r['sites']})}
            merged[key][g] = m
    return merged


def eligibility(table):
    """Per class: excess over the copy floor per GDN layer on rank 0's speculative half and rank 1's half; lever-eligible only on BOTH."""
    a, b = table.get('rank0/speculative', {}), table.get('rank1/half', {})
    out = {}
    for g in LAYER_GROUPS:
        ea = (a.get(g) or {}).get('excess_floor_us_per_gdn_layer')
        eb = (b.get(g) or {}).get('excess_floor_us_per_gdn_layer')
        both = None if ea is None or eb is None else min(ea, eb)
        out[g] = dict(excess_floor_us_per_gdn_layer=dict(rank0=ea, rank1=eb), min_over_ranks=both,
                      chain_eligible_by_excess=bool(both is not None and both >= CHAIN_BAR_US),
                      screen_eligible_by_excess=bool(both is not None and both >= SCREEN_BAR_US),
                      gain_if_all_excess_removed_pct=None if both is None else GAIN_PCT_PER_10US * both / 10.0,
                      excess_packet110_us_per_gdn_layer=dict(rank0=(a.get(g) or {}).get('excess_packet110_us_per_gdn_layer'), rank1=(b.get(g) or {}).get('excess_packet110_us_per_gdn_layer')),
                      closures=CLOSURES.get(g, []), open_mechanisms=OPEN.get(g, []))
    return out


def decide(smoke, bracket, references=None):
    """smoke: dict(kind='smoke', passed, exact, sites_present); bracket: dict(kind='bracket', views=[5 records with variant, rate, all_13_exact,
    exact_count, draft_proposals, acceptance_counts, interval_stats, sites_data, output]); references: packet189/190 pins (default: read in place)."""
    demand(smoke.get('kind') == 'smoke' and smoke.get('passed') is True and smoke.get('exact') is True, 'k3x-on smoke must pass exact first')
    demand(smoke.get('sites_present') is True, 'k3x-on smoke must carry site rows on both ranks (instrumentation did not run)')
    demand(bracket.get('kind') == 'bracket' and [v['variant'] for v in bracket['views']] == list(ORDER), 'bracket must be off/on/off/on/off')
    views = list(bracket['views'])
    for v in views:
        demand(isinstance(v.get('rate'), (int, float)) and math.isfinite(v['rate']) and v['rate'] > 0, 'invalid view rate')
    exact = all(v.get('all_13_exact') is True and v.get('exact_count') == 13 for v in views)
    proposals = all(v['draft_proposals'] == views[0]['draft_proposals'] for v in views)
    acceptance = all(v['acceptance_counts'] == views[0]['acceptance_counts'] for v in views)
    sites_ok = all(isinstance(v.get('sites_data'), dict) and v['sites_data'].get('passed') is True and v['sites_data'].get('expected_present') == (v['variant'] == INSTRUMENTED) for v in views)
    off = [v['rate'] for v in views if v['variant'] == CONTROL]
    on = [v['rate'] for v in views if v['variant'] == INSTRUMENTED]
    drift = 100 * (max(off) / min(off) - 1)
    ratio = mean(on) / mean(off)
    refs = references or dict(packet189=packet189_k3x_reference(), packet190=packet190_record_reference())
    off_vs_189 = 100 * (mean(off) / mean(refs['packet189']['rates']) - 1)
    off_vs_record = 100 * (mean(off) / refs['packet190']['rate'] - 1)
    prompt_ids = [c['prompt_id'] for c in views[0]['acceptance_counts']]
    attributions, completeness_fail, attribution_error = [], [], None
    try:
        floor_us, p110 = floor_model(), packet110_reference()
        for v in views:
            if v['variant'] == INSTRUMENTED:
                a = attribute_view(Path(v['output']), prompt_ids, floor_us, p110)
                attributions.append(a)
                for key, c in a['completeness'].items():
                    if c['deviation_pct'] > KILL['class_sum_vs_body_pct']:
                        completeness_fail.append(dict(view=v.get('index'), key=key, **c))
    except Incomplete as error:
        attribution_error = str(error)
    stats = lambda rows: [r.get('interval_stats') for r in rows if isinstance(r.get('interval_stats'), dict) and 'hit' in r.get('interval_stats', {})]
    s_off, s_on = stats([v for v in views if v['variant'] == CONTROL]), stats([v for v in views if v['variant'] == INSTRUMENTED])
    cost = {}
    for side, key in (('hit', 'A'), ('hit', 'B'), ('hit', 'Bd'), ('hit', 'D'), ('hit', 'elapsed'), ('miss', 'elapsed'), ('miss', 'C')):
        a, b = mean(s[side][key] for s in s_off if s[side].get(key) is not None), mean(s[side][key] for s in s_on if s[side].get(key) is not None)
        if a is not None and b is not None:
            cost[f'{side}_{key}_ms'] = dict(off=a, on=b, added=b - a)
    fired = []
    if not exact or not proposals or not acceptance:
        fired.append('exact_or_proposals')
    if not sites_ok:
        fired.append('sites_rows_presence')
    if drift > KILL['control_drift_pct']:
        fired.append('control_drift_pct')
    if ratio < KILL['instrumented_over_control_min']:
        fired.append('instrumented_over_control_min')
    if completeness_fail or attribution_error:
        fired.append('class_sum_vs_body_pct')
    stop = any(k in fired for k in ('exact_or_proposals', 'sites_rows_presence', 'control_drift_pct', 'class_sum_vs_body_pct'))
    admissible = not stop and ratio >= KILL['instrumented_over_control_min'] and bool(attributions)
    # packet128's rule: a failed overhead gate (or a stop) withholds the class table and the rankings entirely.
    table = class_table(attributions) if attributions and admissible else {}
    elig = eligibility(table) if admissible else {}
    chain = sorted(g for g, e in elig.items() if e['chain_eligible_by_excess'])
    screen = sorted(g for g, e in elig.items() if e['screen_eligible_by_excess'])
    open_left = {g: e['open_mechanisms'] for g, e in elig.items() if (e['chain_eligible_by_excess'] or e['screen_eligible_by_excess']) and e['open_mechanisms']}
    if stop:
        outcome = 'STOP: kill rule fired (%s); the class table is not reported' % ', '.join(fired)
    elif not admissible:
        outcome = 'TABLE INADMISSIBLE: instrumented/control %.4f < %.2f (%s)' % (ratio, KILL['instrumented_over_control_min'], OVERHEAD_RULE)
    else:
        outcome = ('MEASUREMENT COMPLETE: instrumented/control %.4f; classes >= %.1f us/GDN layer over the copy floor on BOTH ranks (chain bar): %s; '
                   '>= %.1f us (screen bar): %s; open mechanisms among them: %s' % (ratio, CHAIN_BAR_US, chain or 'none', SCREEN_BAR_US, screen or 'none',
                                                                                 json.dumps(open_left) if open_left else 'NONE (every excess-eligible class is closed by the DO-NOT-REPEAT rows named; no kernel brief can honestly be priced at +2 %)'))
    return dict(schema='packet191.s191-report.v1', measurement_complete=admissible, table_admissible=admissible, screen_winner=False, chain_rule_met=False,
                outcome=outcome, rule=RULE, thresholds=dict(chain_bar_us_per_gdn_layer=CHAIN_BAR_US, screen_bar_us_per_gdn_layer=SCREEN_BAR_US, gain_pct_per_10us=GAIN_PCT_PER_10US,
                                                           floor_GBs=FLOOR_GBS, record=RECORD, **KILL),
                every_view_exact=exact, draft_proposals_identical=proposals, acceptance_identical=acceptance, sites_rows_presence_ok=sites_ok,
                off_rates=off, on_rates=on, control_drift_percent=drift, instrumented_over_control=ratio,
                off_vs_packet189_k3x_percent=off_vs_189, off_timing_equivalent_to_packet189=bool(abs(off_vs_189) <= KILL['timing_equivalence_pct']),
                off_vs_packet190_record_percent=off_vs_record, references=refs, instrumentation_cost=cost,
                kill_rules=dict(thresholds=KILL, fired=fired, completeness=[c for a in attributions for c in a['completeness'].values()] if attributions else [],
                                completeness_failures=completeness_fail, attribution_error=attribution_error, overhead_rule=OVERHEAD_RULE),
                attribution=[dict(halves=a['halves'], dropped=a['dropped'], windows=a['windows']) for a in attributions],
                class_table=table, eligibility=elig, chain_eligible_by_excess=chain, screen_eligible_by_excess=screen, open_mechanisms_remaining=open_left,
                closures_corpus='analysis/dnr-class-grep.txt (all stage2 DO-NOT-REPEAT.md files)')


def decide_or_incomplete(*rows, references=None):
    try:
        for row in rows:
            if isinstance(row, Exception):
                raise row
        return decide(*rows, references=references)
    except (Incomplete, KeyError, ValueError, TypeError, OSError) as error:
        return dict(schema='packet191.s191-report.v1', measurement_complete=False, table_admissible=False, screen_winner=False, chain_rule_met=False,
                    outcome='INCOMPLETE: no report', reason=str(error), rule=RULE)


def bracket_record(summary):
    return dict(kind='bracket', views=[dict(index=v.get('index'), variant=v['variant'], rate=v['rate'], all_13_exact=v['all_13_exact'], exact_count=v['exact_count'],
                                            draft_proposals=v['draft_proposals'], acceptance_counts=v['acceptance_counts'], interval_stats=v.get('interval_stats'),
                                            sites_data=v.get('sites_data'), output=v.get('output')) for v in summary['views']])


def smoke_record(summary):
    view = (summary.get('views') or [{}])[0]
    sites = view.get('sites_data') or {}
    return dict(kind='smoke', passed=summary.get('passed') is True, exact=summary.get('passed') is True and summary.get('kind') == 'smoke'
                and summary.get('timing_data_proof', {}).get('passed') is True,
                sites_present=bool(view.get('variant') == INSTRUMENTED and sites.get('passed') is True and sites.get('rows_total', 0) > 0))


def render(report):
    """Plain-text table of the report (rank / phase / class)."""
    lines = [report['outcome'], '']
    for key, groups in report.get('class_table', {}).items():
        lines.append('%-22s %-14s %9s %9s %9s %9s %9s %9s' % (key, 'class', 'ms/half', 'us/GDN', 'floor', 'xs_floor', 'p110', 'xs_p110'))
        for g, m in sorted(groups.items(), key=lambda kv: -(kv[1]['ms_per_half'] or 0)):
            f = lambda v: '%9.1f' % v if isinstance(v, (int, float)) else '%9s' % '-'
            lines.append('%-22s %-14s %s %s %s %s %s %s' % ('', g, f((m['ms_per_half'] or 0) * 1), f(m['us_per_gdn_layer']), f(m['floor_us_per_gdn_layer']),
                                                             f(m['excess_floor_us_per_gdn_layer']), f(m['packet110_us_per_gdn_layer']), f(m['excess_packet110_us_per_gdn_layer'])))
        lines.append('')
    for g, e in report.get('eligibility', {}).items():
        lines.append('%-14s excess rank0 %s rank1 %s chain %s screen %s open %s' % (g, e['excess_floor_us_per_gdn_layer']['rank0'], e['excess_floor_us_per_gdn_layer']['rank1'],
                                                                                   e['chain_eligible_by_excess'], e['screen_eligible_by_excess'], e['open_mechanisms'] or 'none'))
    return '\n'.join(lines)


if __name__ == '__main__':
    import argparse, resource
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    ap = argparse.ArgumentParser(description='Recompute s191_report from the two retained row outputs (rows 0..1).')
    ap.add_argument('outputs', nargs=2, type=Path)
    ap.add_argument('--write', type=Path)
    a = ap.parse_args()
    from p191_v5_compare import load
    s, b = (load(p) for p in a.outputs)
    result = decide_or_incomplete(smoke_record(s), bracket_record(b))
    print(json.dumps(result, indent=2))
    print(render(result))
    if a.write:
        a.write.write_text(json.dumps(result, indent=2) + '\n')
