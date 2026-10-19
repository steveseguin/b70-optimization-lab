"""Packet174 mechanism readout, kept on every outcome (win, neutral or loss).

Definitions are fixed before any packet174 device run:
- decode tokens are generated_index >= 2; a readback is slow when
  transfer_wall_ms > 1.0 (packet171 definition);
- the fill bytes of a token are the bytes submitted by the maintenance
  boundary at the START of that same position: the delta of
  cache.jsonl fill_bytes_total between consecutive positions (the cache row of a
  position is written at its end, after its token readback);
- cache.jsonl has one row per position, in run order: views in bracket order,
  requests in suite-inputs.tsv order, prefill rows then generated rows. The
  join refuses unless the row counts match exactly.

Packet171b's readout labelled the high-"other" token (the publication/plan
token) as the fill token; on packet58as/171b streams the slow readback is on
the fill-submission token itself and its excess is linear in that token's
fill bytes (about 0.035 ms/MB, intercept about 0). This readout reports that
slope directly, plus fill MB per token, kicks and the host-counted hit rate.
"""
import json
import statistics as st
from pathlib import Path

SLOW_MS = 1.0


def _fit(xs, ys):
    if len(xs) < 3:
        return None, None
    mx, my = st.mean(xs), st.mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None, None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    return round(b, 5), round(my - b * mx, 4)


def _rows(run_root, labels):
    run_root = Path(run_root)
    order = [line.split()[0] for line in (run_root.parent / 'suite-inputs.tsv').read_text().splitlines() if line.strip()]
    cache = [json.loads(s) for s in (run_root / 'cache.jsonl').read_text().splitlines() if s.strip()]
    rows = []
    for label in labels:
        for request in order:
            for name in ('prefill-timings.jsonl', 'timings.jsonl'):
                for s in (run_root / label / request / name).read_text().splitlines():
                    if s.strip():
                        r = json.loads(s); r['_view'] = label; rows.append(r)
    if len(rows) != len(cache):
        raise ValueError(f'cache/timing join mismatch: {len(cache)} cache rows, {len(rows)} timing rows')
    for i in range(1, len(cache)):
        if cache[i]['position'] != cache[i - 1]['position'] + 1:
            raise ValueError('non-contiguous cache positions')
    for i, (r, c) in enumerate(zip(rows, cache)):
        p = cache[i - 1] if i else None
        same_view = p is not None and rows[i - 1]['_view'] == r['_view']
        r['_fill_mb'] = (c['fill_bytes_total'] - (p['fill_bytes_total'] if same_view else c['fill_bytes_total'])) / 1e6 if same_view else None
        for k in ('fill_kicks_total', 'route_hits_total', 'routes_total'):
            r['_' + k] = (c[k] - p[k]) if (same_view and k in c and k in p) else None
    return rows


def view(rows, label):
    vr = [r for r in rows if r['_view'] == label]
    gen = [r for r in vr if r.get('kind') == 'generated_token' and r['generated_index'] >= 2]
    if not gen:
        raise ValueError('no decode tokens for mechanism readout')
    slow = [r for r in gen if r['transfer_wall_ms'] > SLOW_MS]
    fast = [r for r in gen if r['transfer_wall_ms'] <= SLOW_MS]
    filled = [r for r in gen if r['_fill_mb'] is not None and r['_fill_mb'] > 0]
    unfilled = [r for r in gen if r['_fill_mb'] == 0]
    mean = lambda rs, k: round(st.mean(r[k] for r in rs), 4) if rs else None
    slope, intercept = _fit([r['_fill_mb'] for r in filled], [r['transfer_wall_ms'] for r in filled])
    wslope, wint = _fit([r['_fill_mb'] for r in filled], [r['wait_ms'] for r in filled])
    known = [r for r in gen if r['_routes_total']]
    kicks = [r['_fill_kicks_total'] for r in vr if r['_fill_kicks_total'] is not None]
    return dict(
        tokens=len(gen), wall_ms=mean(gen, 'wall_ms'), wait_ms=mean(gen, 'wait_ms'),
        transfer_wall_ms=mean(gen, 'transfer_wall_ms'),
        median_transfer_wall_ms=round(st.median(r['transfer_wall_ms'] for r in gen), 4),
        slow_readback_fraction=round(len(slow) / len(gen), 4),
        slow_transfer_wall_ms=mean(slow, 'transfer_wall_ms'), fast_transfer_wall_ms=mean(fast, 'transfer_wall_ms'),
        fill_tokens=len(filled),
        fill_mb_per_token=round(sum(r['_fill_mb'] or 0 for r in gen) / len(gen), 3),
        p_slow_readback_on_fill_token=round(sum(r['transfer_wall_ms'] > SLOW_MS for r in filled) / len(filled), 4) if filled else None,
        p_slow_readback_on_unfilled_token=round(sum(r['transfer_wall_ms'] > SLOW_MS for r in unfilled) / len(unfilled), 4) if unfilled else None,
        fill_token_transfer_ms=mean(filled, 'transfer_wall_ms'), unfilled_token_transfer_ms=mean(unfilled, 'transfer_wall_ms'),
        fill_token_wait_ms=mean(filled, 'wait_ms'), unfilled_token_wait_ms=mean(unfilled, 'wait_ms'),
        readback_ms_per_fill_mb=slope, readback_intercept_ms=intercept,
        wait_ms_per_fill_mb=wslope, wait_intercept_ms=wint,
        decode_hit_rate=round(sum(r['_route_hits_total'] for r in known) / sum(r['_routes_total'] for r in known), 5) if known else None,
        fill_kicks=sum(kicks) if kicks else None)


def readout(run_root, labels, prompt_ids=None, candidate_wins=False):
    rows = _rows(run_root, labels)
    views = {label: view(rows, label) for label in labels}
    controls = [views[l] for l in ('A1', 'A2') if l in views]
    candidates = [views[l] for l in ('B0', 'B1') if l in views]
    collapsed = bool(controls and candidates) and \
        max(c['slow_readback_fraction'] for c in candidates) <= 0.5 * min(a['slow_readback_fraction'] for a in controls) and \
        all(c['readback_ms_per_fill_mb'] is not None and a['readback_ms_per_fill_mb'] is not None and
            c['readback_ms_per_fill_mb'] <= 0.5 * a['readback_ms_per_fill_mb'] for c in candidates for a in controls)
    if candidate_wins and collapsed:
        verdict = 'confirmed: fills waited for a host synchronization; the kick overlaps them with compute'
    elif not candidate_wins and not collapsed:
        verdict = 'close: the kick does not start fills early; fill execution is gated below the host flush'
    else:
        verdict = 'mixed: speed and readback-slope collapse disagree; record and review before any follow-up'
    return dict(schema='packet174.mechanism.v1', definitions=dict(
        slow_readback_ms=SLOW_MS, tokens='generated_index >= 2',
        fill_bytes='same-position delta of cache.jsonl fill_bytes_total (submitted at that position start)'),
        views=views, slow_mode_collapsed=collapsed,
        collapse_rule='max B slow fraction <= 0.5 x min warm A slow fraction AND every B readback slope <= 0.5 x every warm A slope',
        candidate_wins=bool(candidate_wins), verdict=verdict)
