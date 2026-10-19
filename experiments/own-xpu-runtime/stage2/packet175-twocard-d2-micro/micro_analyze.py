"""Packet175 D2 analyzer: dense GEMV device time, arm A versus arm B (+ warm-ahead).

Decision rule (coordinator hourly review 44, superseding the original 4.8% rule
before this packet was sealed): weighted dense GEMV time B/A <= 0.97, i.e. a reduction
of at least 3% INCLUDING the warm-ahead kernels' own time. On that outcome D2 is
"eligible for combined bundle-9": it is built only together with packet153's static
descriptors (+0.35%, exact, retained), never alone. Otherwise "close D2" with a
DO-NOT-REPEAT row.
"""
import hashlib, json, statistics
from pathlib import Path

P = Path(__file__).resolve().parent
DENSE = ('hc_low_inject', 'hc_gate_mix', 'projection', 'small_tuple', 'attention_projection', 'shared_down_mix')
OTHER = ('hc_norm', 'conv', 'gdn_recurrence', 'gdn_norm_gate', 'qsa_prepare', 'qsa_pool', 'qsa_select',
         'qsa_attention', 'route_shared_activation', 'expert_gate_up', 'expert_activation', 'expert_down', 'combine')
LAYERS = {0: 36, 3: 12}           # GDN / QSA layer weights of the 48-layer body
REPEATS = 240
POSITION = 31
MAX_RATIO = 0.97                   # review 44: B/A dense GEMV time incl. warm-ahead
THRESHOLD = 1 - MAX_RATIO          # >= 3% reduction
CENSUS_DENSE_MS = 11.532           # packet168 v3 dense_hc, summed over both ranks (5.574 + 5.955)
# packet173 thresholds.json: summed census ms -> token gain % (symmetric levers)
GAIN_POINTS = ((0.0, 0.0), (0.140, 0.5), (0.278, 1.0), (0.550, 2.0), (0.817, 3.0), (0.949, 3.5))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_events(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def event_duration(row):
    return row['end_ns'] - row['start_ns']


def gain_percent(saving_ms):
    """Piecewise-linear packet173 mapping; linear extrapolation outside the table."""
    pts = GAIN_POINTS
    if saving_ms <= pts[1][0]:
        return saving_ms * pts[1][1] / pts[1][0]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if saving_ms <= x1:
            return y0 + (saving_ms - x0) * (y1 - y0) / (x1 - x0)
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    return y1 + (saving_ms - x1) * (y1 - y0) / (x1 - x0)


def quantile(values, q):
    v = sorted(values)
    i = (len(v) - 1) * q
    lo, hi = int(i), min(int(i) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)


def validate(rows):
    if not rows or rows[-1].get('kind') != 'summary':
        raise ValueError('missing native summary')
    s = rows[-1]
    if not all(s.get(k) is True for k in ('passed', 'drained', 'zero_errors', 'finite_outputs', 'cpu_oracle_match', 'ab_byte_identical')) \
            or s.get('identity') != 'iq3-p49-split32-v1' or s.get('backend') != 'device':
        raise ValueError('oracle gate or identity-matched D2 device summary failed')
    if any(r['kind'] == 'bytes' and r['different_bytes'] for r in rows):
        raise ValueError('oracle gate: A/B bytes differ')
    oracle = {(r['layer'], r['repeat'], r['arm']) for r in rows if r['kind'] == 'oracle' and r.get('passed') is True}
    need = {(l, rep, arm) for l in LAYERS for rep in range(REPEATS) for arm in (0, 1)}
    if oracle != need:
        raise ValueError('oracle gate: timed arms without a passed exact check')
    samples = [r for r in rows if r['kind'] == 'sample']
    if {r['layer'] for r in samples} != set(LAYERS) or {r['position'] for r in samples} != {POSITION}:
        raise ValueError('not an identity-matched packet175 stream (layers/position)')
    return samples


def evaluate(output):
    output = Path(output)
    rows = read_events(output / 'samples.jsonl')
    samples = validate(rows)
    passes = {}
    for r in samples:
        passes.setdefault((r['layer'], r['repeat'], r['arm']), []).append(r)
    sequences = {}
    for key, events in passes.items():
        events.sort(key=lambda r: r['event'])
        classes = [r['class'] for r in events]
        unknown = set(classes) - set(DENSE) - set(OTHER) - {'warm', 'evict'}
        if unknown or classes.count('evict') != 2:
            raise ValueError('not an identity-matched packet175 stream (classes)')
        if (key[2] == 0) == ('warm' in classes):
            raise ValueError('not an identity-matched packet175 stream (warm only in arm B)')
        sequences.setdefault((key[0], key[2]), set()).add(tuple(c for c in classes if c != 'warm'))
    for layer in LAYERS:
        if len(sequences[(layer, 0)]) != 1 or sequences[(layer, 0)] != sequences[(layer, 1)]:
            raise ValueError('arms differ in launch order apart from warm-ahead')
    layers = {}
    for layer in LAYERS:
        a_dense, b_dense, b_warm, a_span, b_span, red = [], [], [], [], [], []
        for rep in range(REPEATS):
            ea, eb = passes[(layer, rep, 0)], passes[(layer, rep, 1)]
            ad = sum(event_duration(r) for r in ea if r['class'] in DENSE)
            bd = sum(event_duration(r) for r in eb if r['class'] in DENSE)
            bw = sum(event_duration(r) for r in eb if r['class'] == 'warm')
            a_dense.append(ad); b_dense.append(bd); b_warm.append(bw)
            span = lambda ev: max(r['end_ns'] for r in ev) - min(r['start_ns'] for r in ev if r['class'] != 'evict')
            a_span.append(span(ea)); b_span.append(span(eb))
            red.append(1 - (bd + bw) / ad)
        med = statistics.median
        layers[layer] = dict(
            repeats=REPEATS, rows_per_pass=2,
            dense_a_ms_per_row=med(a_dense) / 2e6, dense_b_gemv_only_ms_per_row=med(b_dense) / 2e6,
            warm_b_prime_ms_per_row=med(b_warm) / 2e6, dense_b_including_warm_ms_per_row=med([x + y for x, y in zip(b_dense, b_warm)]) / 2e6,
            reduction_median=med(red), reduction_p10=quantile(red, .1), reduction_p90=quantile(red, .9),
            reduction_mean=statistics.fmean(red), reduction_stdev=statistics.stdev(red),
            gemv_only_reduction_median=1 - med(b_dense) / med(a_dense),
            layer_span_a_ms_per_row=med(a_span) / 2e6, layer_span_b_ms_per_row=med(b_span) / 2e6)
    w = LAYERS
    weighted = sum(w[l] * (layers[l]['dense_a_ms_per_row'] - layers[l]['dense_b_including_warm_ms_per_row']) for l in w) \
        / sum(w[l] * layers[l]['dense_a_ms_per_row'] for l in w)
    weighted_p10 = min(layers[l]['reduction_p10'] for l in w)
    saving = weighted * CENSUS_DENSE_MS
    ratio = 1 - weighted
    build = ratio <= MAX_RATIO + 1e-12
    result = dict(schema='own-runtime.packet175.d2-analysis.v1', device_measurement=True,
                  samples_sha256=sha(output / 'samples.jsonl'), threshold_reduction=THRESHOLD, maximum_b_over_a=MAX_RATIO,
                  weighted_b_over_a=ratio,
                  dense_classes=list(DENSE), layer_weights={str(k): v for k, v in w.items()},
                  layers={str(k): v for k, v in layers.items()},
                  weighted_reduction=weighted, worst_layer_reduction_p10=weighted_p10,
                  projected_census_saving_ms=saving, census_dense_ms=CENSUS_DENSE_MS,
                  projected_token_gain_percent=gain_percent(saving),
                  decision='eligible for combined bundle-9' if build else 'close D2', eligible_combined_bundle9=build,
                  combined_with='packet153 static descriptors (+0.35%, exact, retained); D2 is never built alone',
                  realism='real packet166 M1 launch order (HC, projections, GDN/QSA, routed experts, shared) per row, '
                          'plus a 256 MiB stream-read interposer before each row pass (other layers of the token)')
    (output / 'analysis.json').write_text(json.dumps(result, indent=2) + '\n')
    if build:
        (output / 'COMBINED-BUNDLE9-ELIGIBLE.md').write_text(
            '# D2 eligible for combined bundle-9 (packet175 micro passed)\n\n'
            f'Weighted dense GEMV B/A including warm-ahead: {ratio:.4f} (maximum {MAX_RATIO}); reduction {weighted:.4%}.\n'
            f'Projected summed census saving {saving:.3f} ms, about {gain_percent(saving):+.2f}% tok/s (micro projection only).\n'
            'Build D2 only inside a combined bundle-9 candidate with packet153 static descriptors (+0.35%, exact),\n'
            'never alone: the packet173 LEVER-TABLE flag pattern (process-wide `--warm-ahead off|dense`, all six sites),\n'
            'then one v5 C0/X1/C2/X3/C4 bracket of the combined candidate. Evidence: ' + str(output) + '\n')
    else:
        with (P / 'DO-NOT-REPEAT.md').open('a') as f:
            f.write(f'| D2 dense-weight L2 warm-ahead (separate warm kernel before every dense GEMV, real packet166 M1 '
                    f'launch order + 256 MiB interposer) | packet175 device micro: weighted reduction {weighted:.2%} '
                    f'including warm time, B/A {ratio:.4f} > {MAX_RATIO}; GEMV-only median per layer '
                    + ', '.join(f"L{l} {layers[l]['gemv_only_reduction_median']:.2%}" for l in w)
                    + f'; warm alone ' + ', '.join(f"L{l} {layers[l]['warm_b_prime_ms_per_row']:.3f} ms/row" for l in w)
                    + f'. Evidence {output}. | A warm-ahead that costs no serial device time (folded into a latency-bound '
                    'predecessor) AND a measured GEMV-only reduction of at least 3% on its own. |\n')
    return result
