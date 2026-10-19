"""Packet175b D1 analyzer: dense GEMV device time, arm A (bundle-8 dense lane) versus arm B
(D1 same-bit scale-word multicast inside the dense lane).

Decision rule (coordinator hourly review 44): weighted dense GEMV time B/A <= 0.97, i.e. a
reduction of at least 3%. D1 adds no kernels: its overhead (owner loads, predicates and
subgroup broadcasts) is inside the timed dense GEMV events, so B already includes it.
On that outcome D1 is "eligible for the combined bundle-9 candidate": it is built only
together with packet153's static descriptors (+0.35%, exact, retained) and D2, never
alone. Otherwise "close D1" with a DO-NOT-REPEAT row.

The denominator is the same six dense classes as packet175 (HC low/inject, HC gate/mix,
projections, small tuples, attention projection, shared down/mix). Arm B changes only
the Q6_K/Q8_0 dense-lane sites; in this M1 harness those are the Q6_K large projections
and attention projections. The HC (p60/p73), p49d small-tuple and p109 shared-down
kernels are unchanged in B and are kept in both sums, as the rule is stated on dense
GEMV time. The changed-class ratio is reported separately as information only.
"""
import hashlib, json, statistics
from pathlib import Path

P = Path(__file__).resolve().parent
DENSE = ('hc_low_inject', 'hc_gate_mix', 'projection', 'small_tuple', 'attention_projection', 'shared_down_mix')
CHANGED = ('projection', 'attention_projection')   # Q6_K dense-lane sites switched by arm B (info only)
OTHER = ('hc_norm', 'conv', 'gdn_recurrence', 'gdn_norm_gate', 'qsa_prepare', 'qsa_pool', 'qsa_select',
         'qsa_attention', 'route_shared_activation', 'expert_gate_up', 'expert_activation', 'expert_down', 'combine')
LAYERS = {0: 36, 3: 12}           # GDN / QSA layer weights of the 48-layer body
REPEATS = 240
POSITION = 31
VARIANT = 'd1-scale-multicast'
MAX_RATIO = 0.97                   # review 44: B/A dense GEMV time, overhead included
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
        raise ValueError('oracle gate or identity-matched D1 device summary failed')
    if s.get('variant') != VARIANT:
        raise ValueError('not an identity-matched packet175b stream (variant)')
    if any(r['kind'] == 'bytes' and r['different_bytes'] for r in rows):
        raise ValueError('oracle gate: A/B bytes differ')
    oracle = {(r['layer'], r['repeat'], r['arm']) for r in rows if r['kind'] == 'oracle' and r.get('passed') is True}
    need = {(l, rep, arm) for l in LAYERS for rep in range(REPEATS) for arm in (0, 1)}
    if oracle != need:
        raise ValueError('oracle gate: timed arms without a passed exact check')
    samples = [r for r in rows if r['kind'] == 'sample']
    if {r['layer'] for r in samples} != set(LAYERS) or {r['position'] for r in samples} != {POSITION}:
        raise ValueError('not an identity-matched packet175b stream (layers/position)')
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
        unknown = set(classes) - set(DENSE) - set(OTHER) - {'evict'}
        if unknown or classes.count('evict') != 2:
            raise ValueError('not an identity-matched packet175b stream (classes; no warm-ahead in either arm)')
        sequences.setdefault((key[0], key[2]), set()).add(tuple(classes))
    for layer in LAYERS:
        if len(sequences[(layer, 0)]) != 1 or sequences[(layer, 0)] != sequences[(layer, 1)]:
            raise ValueError('arms differ in launch order (D1 adds no launches)')
    layers = {}
    for layer in LAYERS:
        a_dense, b_dense, a_changed, b_changed, a_span, b_span, ratio = [], [], [], [], [], [], []
        for rep in range(REPEATS):
            ea, eb = passes[(layer, rep, 0)], passes[(layer, rep, 1)]
            ad = sum(event_duration(r) for r in ea if r['class'] in DENSE)
            bd = sum(event_duration(r) for r in eb if r['class'] in DENSE)
            a_dense.append(ad); b_dense.append(bd)
            a_changed.append(sum(event_duration(r) for r in ea if r['class'] in CHANGED))
            b_changed.append(sum(event_duration(r) for r in eb if r['class'] in CHANGED))
            span = lambda ev: max(r['end_ns'] for r in ev) - min(r['start_ns'] for r in ev if r['class'] != 'evict')
            a_span.append(span(ea)); b_span.append(span(eb))
            ratio.append(bd / ad)
        med = statistics.median
        layers[layer] = dict(
            repeats=REPEATS, rows_per_pass=2,
            dense_a_ms_per_row=med(a_dense) / 2e6, dense_b_ms_per_row=med(b_dense) / 2e6,
            b_over_a_of_medians=med(b_dense) / med(a_dense),
            paired_ratio_median=med(ratio), paired_ratio_p10=quantile(ratio, .1), paired_ratio_p90=quantile(ratio, .9),
            paired_ratio_mean=statistics.fmean(ratio), paired_ratio_stdev=statistics.stdev(ratio),
            changed_sites_a_ms_per_row=med(a_changed) / 2e6, changed_sites_b_ms_per_row=med(b_changed) / 2e6,
            changed_sites_b_over_a=med(b_changed) / med(a_changed) if med(a_changed) else None,
            layer_span_a_ms_per_row=med(a_span) / 2e6, layer_span_b_ms_per_row=med(b_span) / 2e6)
    w = LAYERS
    weighted_ratio = sum(w[l] * layers[l]['dense_b_ms_per_row'] for l in w) / sum(w[l] * layers[l]['dense_a_ms_per_row'] for l in w)
    weighted = 1 - weighted_ratio
    spread = dict(worst_layer_paired_ratio_p90=max(layers[l]['paired_ratio_p90'] for l in w),
                  best_layer_paired_ratio_p10=min(layers[l]['paired_ratio_p10'] for l in w))
    saving = weighted * CENSUS_DENSE_MS
    eligible = weighted_ratio <= MAX_RATIO + 1e-12
    result = dict(schema='own-runtime.packet175b.d1-analysis.v1', device_measurement=True, variant=VARIANT,
                  samples_sha256=sha(output / 'samples.jsonl'), threshold_reduction=THRESHOLD, maximum_b_over_a=MAX_RATIO,
                  weighted_b_over_a=weighted_ratio, spread=spread,
                  dense_classes=list(DENSE), changed_classes_info_only=list(CHANGED), layer_weights={str(k): v for k, v in w.items()},
                  layers={str(k): v for k, v in layers.items()},
                  weighted_reduction=weighted,
                  projected_census_saving_ms=saving, census_dense_ms=CENSUS_DENSE_MS,
                  projected_token_gain_percent=gain_percent(saving),
                  decision='eligible for the combined bundle-9 candidate' if eligible else 'close D1',
                  eligible_combined_bundle9=eligible,
                  combined_with='packet153 static descriptors (+0.35%, exact, retained) and D2; D1 is never built alone',
                  realism='packet175 harness: real packet166 M1 launch order (HC, projections, GDN/QSA, routed experts, shared) '
                          'per row, plus a 256 MiB stream-read interposer before each row pass (other layers of the token)')
    (output / 'analysis.json').write_text(json.dumps(result, indent=2) + '\n')
    if eligible:
        (output / 'COMBINED-BUNDLE9-ELIGIBLE.md').write_text(
            '# D1 eligible for the combined bundle-9 candidate (packet175b micro passed)\n\n'
            f'Weighted dense GEMV B/A (in-kernel overhead included): {weighted_ratio:.4f} (maximum {MAX_RATIO}); '
            f'reduction {weighted:.4%}. Paired-ratio spread: p10 {spread["best_layer_paired_ratio_p10"]:.4f}, '
            f'p90 {spread["worst_layer_paired_ratio_p90"]:.4f}.\n'
            f'Projected summed census saving {saving:.3f} ms, about {gain_percent(saving):+.2f}% tok/s (micro projection only).\n'
            'Build D1 only inside the combined bundle-9 candidate with packet153 static descriptors (+0.35%, exact) and D2,\n'
            'never alone: the packet173 LEVER-TABLE flag pattern (a process-wide kernel-changing flag at all six sites,\n'
            'K1 byte proof of the candidate fixtures), then one v5 C0/X1/C2/X3/C4 bracket. Evidence: ' + str(output) + '\n')
    else:
        with (P / 'DO-NOT-REPEAT.md').open('a') as f:
            f.write(f'| D1 same-bit scale-word multicast in the dense lane (one owner load per 32-word chunk + '
                    f'select_from_group; packet175 harness, real packet166 M1 launch order + 256 MiB interposer) | '
                    f'packet175b device micro: weighted dense GEMV B/A {weighted_ratio:.4f} > {MAX_RATIO} '
                    f'(reduction {weighted:.2%}); changed-site B/A per layer '
                    + ', '.join(f"L{l} {layers[l]['changed_sites_b_over_a']:.4f}" for l in w)
                    + f'; paired p10/p90 per layer '
                    + ', '.join(f"L{l} {layers[l]['paired_ratio_p10']:.4f}/{layers[l]['paired_ratio_p90']:.4f}" for l in w)
                    + f'. Evidence {output}. | Native evidence of a scale-load issue stall in the dense lane AND a '
                    'different multicast mechanism with a measured dense GEMV B/A <= 0.97. |\n')
    return result
