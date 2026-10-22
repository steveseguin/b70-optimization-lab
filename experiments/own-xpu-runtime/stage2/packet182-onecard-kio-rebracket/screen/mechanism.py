"""Packet176 mechanism readout, kept on every outcome (win, neutral or loss).

Definitions are fixed before any packet176 device run:
- decode tokens are generated_index >= 2; a token's foreground transfer is slow
  when transfer_wall_ms > 1.0 (packet171 definition). transfer_wall_ms is ALL
  foreground transfer time of the token: the head (token id + lookup rows) and
  the tail (error/next_token). Packet171/174 called it "readback";
- head_transfer_ms / tail_transfer_ms / route_log_ms split it (new host-only
  fields in both arms); they are absent (None) on older streams;
- the fill bytes of a token are the bytes submitted by the maintenance boundary
  at the START of that same position: the delta of cache.jsonl
  fill_bytes_total between consecutive positions;
- cache.jsonl has one row per position, in run order: views in bracket order,
  requests in suite-inputs.tsv order, prefill rows then generated rows. The join
  refuses unless the row counts match exactly;
- the engine that carried each arm's foreground transfers is read from the
  timing rows: foreground_io == 'copy' -> the BCS foreground immediate list
  (same copy-only ordinal and index 0 as the maintenance fill list, see
  native/generated/single_device.cpp), with per-token copy-engine command
  counts from copy_counts; 'kernel' -> compute-queue kernels storing to / loading
  from USM host memory (no copy command). Older streams carry no label: copy.

Packet182 additions (fill_split, fill_lever_price; the original fields and
verdict are unchanged):
- the packet176 wall slope is fitted over FILLED tokens only, so it also carries
  miss-intensity autocorrelation: on packet171b's real spin streams, unfilled
  tokens show the same ~0.032 ms per MB slope against the NEXT token's fill
  bytes. fill_split therefore compares filled with unfilled decode tokens
  (fills are submitted every second position; misses happen on both) and
  reports the unfilled-vs-next-fill control slope beside the filled-token slope;
- fill_lever_price = (filled minus unfilled wall outside the transfer window) x
  filled fraction: the most any fill pacing/deferral could remove per token if
  fills became free. It is a ceiling, not a projected gain.
"""
import json
import statistics as st
from pathlib import Path

SLOW_MS = 1.0
COPY = 'copy engine: BCS foreground immediate list (copy-only ordinal, index 0, same engine as the maintenance fill list)'
KERNEL = 'compute queue: CCS kernel stores/loads to USM host memory; no copy command on any queue'


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
        r['_fill_mb'] = (c['fill_bytes_total'] - p['fill_bytes_total']) / 1e6 if same_view else None
        r['_prev_fill_mb'] = rows[i - 1]['_fill_mb'] if same_view else None
        r['_state'] = c.get('state')
    for i, r in enumerate(rows):
        same_next = i + 1 < len(rows) and rows[i + 1]['_view'] == r['_view']
        r['_next_fill_mb'] = rows[i + 1]['_fill_mb'] if same_next else None
    return rows


def fill_split(gen):
    """Filled vs unfilled decode tokens; wall outside the transfer window (packet182)."""
    filled = [r for r in gen if r['_fill_mb'] is not None and r['_fill_mb'] > 0]
    unfilled = [r for r in gen if r['_fill_mb'] == 0]
    if not filled or not unfilled:
        return dict(available=False, reason='needs both filled and unfilled decode tokens')
    def other(r):
        return r['wall_ms'] - r['transfer_wall_ms']
    def mean(rs, f):
        vals = [f(r) for r in rs]
        return round(st.mean(vals), 4) if vals and all(v is not None for v in vals) else None
    keys = dict(wall_ms=lambda r: r['wall_ms'], transfer_wall_ms=lambda r: r['transfer_wall_ms'],
                wall_outside_transfer_ms=other, wait_ms=lambda r: r.get('wait_ms'),
                enqueue_loop_ms=lambda r: r.get('enqueue_loop_ms'))
    table = {}
    for k, f in keys.items():
        a, b = mean(filled, f), mean(unfilled, f)
        table[k] = dict(filled=a, unfilled=b, filled_minus_unfilled=None if a is None or b is None else round(a - b, 4))
    fraction = len(filled) / len(gen)
    per_filled = table['wall_outside_transfer_ms']['filled_minus_unfilled']
    per_token = round(per_filled * fraction, 4)
    wall = st.mean(r['wall_ms'] for r in gen)
    ctrl = [r for r in unfilled if r['_next_fill_mb'] is not None]
    ctrl_slope, ctrl_int = _fit([r['_next_fill_mb'] for r in ctrl], [other(r) for r in ctrl]) if len(ctrl) >= 3 else (None, None)
    in_slope, _ = _fit([r['_fill_mb'] for r in filled], [other(r) for r in filled])
    return dict(available=True, filled_tokens=len(filled), unfilled_tokens=len(unfilled), filled_fraction=round(fraction, 4),
                fill_mb_per_filled_token=round(st.mean(r['_fill_mb'] for r in filled), 3), means=table,
                outside_transfer_ms_per_fill_mb_filled_tokens=in_slope,
                control_unfilled_outside_transfer_ms_per_next_fill_mb=ctrl_slope,
                fill_attributable_outside_transfer_ms_per_filled_token=per_filled,
                fill_attributable_outside_transfer_ms_per_token=per_token,
                fill_attributable_fraction_of_wall=round(per_token / wall, 5))


def _copies(r):
    counts = r.get('copy_counts') or []
    return sum(c.get('host_to_device', 0) + c.get('device_to_host', 0) for c in counts)


def view(rows, label):
    vr = [r for r in rows if r['_view'] == label]
    gen = [r for r in vr if r.get('kind') == 'generated_token' and r['generated_index'] >= 2]
    if not gen:
        raise ValueError('no decode tokens for mechanism readout')
    slow = [r for r in gen if r['transfer_wall_ms'] > SLOW_MS]
    filled = [r for r in gen if r['_fill_mb'] is not None and r['_fill_mb'] > 0]
    unfilled = [r for r in gen if r['_fill_mb'] == 0]
    after_fill = [r for r in gen if r['_prev_fill_mb'] is not None and r['_prev_fill_mb'] > 0]
    mean = lambda rs, k: round(st.mean(r[k] for r in rs), 4) if rs and all(r.get(k) is not None for r in rs) else None
    def slope(key, rs=filled, x='_fill_mb'):
        if not rs or any(r.get(key) is None for r in rs):
            return None, None
        return _fit([r[x] for r in rs], [r[key] for r in rs])
    io = sorted({r.get('foreground_io', 'copy') for r in gen})
    if len(io) != 1:
        raise ValueError(f'mixed foreground transport in one view: {io}')
    split = all(r.get('head_transfer_ms') is not None for r in gen)
    t_slope, t_int = slope('transfer_wall_ms')
    h_slope, h_int = slope('head_transfer_ms')
    tl_slope, tl_int = slope('tail_transfer_ms')
    r_slope, _ = slope('route_log_ms')
    w_slope, w_int = slope('wall_ms')
    wait_slope, wait_int = slope('wait_ms')
    nxt, _ = slope('transfer_wall_ms', after_fill, '_prev_fill_mb')
    states = {}
    for r in gen:
        states[str(r['_state'])] = states.get(str(r['_state']), 0) + 1
    if split and t_slope:
        share_head = round(h_slope / t_slope, 3) if h_slope is not None else None
        carrier = 'head' if share_head is not None and share_head >= 0.6 else 'tail' if share_head is not None and share_head <= 0.4 else 'both'
    else:
        share_head, carrier = None, 'unsplit (stream predates packet176 fields)'
    return dict(
        tokens=len(gen), foreground_io=io[0], engine=KERNEL if io[0] == 'kernel' else COPY,
        copy_engine_commands_per_decode_token=round(st.mean(_copies(r) for r in gen), 3),
        wall_ms=mean(gen, 'wall_ms'), wait_ms=mean(gen, 'wait_ms'),
        transfer_wall_ms=mean(gen, 'transfer_wall_ms'), median_transfer_wall_ms=round(st.median(r['transfer_wall_ms'] for r in gen), 4),
        head_transfer_ms=mean(gen, 'head_transfer_ms'), tail_transfer_ms=mean(gen, 'tail_transfer_ms'), route_log_ms=mean(gen, 'route_log_ms'),
        slow_readback_fraction=round(len(slow) / len(gen), 4),
        slow_head_fraction=round(sum(r['head_transfer_ms'] > SLOW_MS for r in gen) / len(gen), 4) if split else None,
        slow_tail_fraction=round(sum(r['tail_transfer_ms'] > SLOW_MS for r in gen) / len(gen), 4) if split else None,
        fill_tokens=len(filled), fill_mb_per_token=round(sum(r['_fill_mb'] or 0 for r in gen) / len(gen), 3),
        p_slow_readback_on_fill_token=round(sum(r['transfer_wall_ms'] > SLOW_MS for r in filled) / len(filled), 4) if filled else None,
        p_slow_readback_on_unfilled_token=round(sum(r['transfer_wall_ms'] > SLOW_MS for r in unfilled) / len(unfilled), 4) if unfilled else None,
        readback_ms_per_fill_mb=t_slope, readback_intercept_ms=t_int,
        head_ms_per_fill_mb=h_slope, head_intercept_ms=h_int, tail_ms_per_fill_mb=tl_slope, tail_intercept_ms=tl_int,
        route_log_ms_per_fill_mb=r_slope, head_share_of_fill_slope=share_head, fill_wait_carrier=carrier,
        wall_ms_per_fill_mb=w_slope, wall_intercept_ms=w_int, wait_ms_per_fill_mb=wait_slope, wait_intercept_ms=wait_int,
        next_token_transfer_ms_per_previous_fill_mb=nxt, end_of_position_states=states,
        fill_split=fill_split(gen))


def readout(run_root, labels, prompt_ids=None, candidate_wins=False):
    rows = _rows(run_root, labels)
    views = {label: view(rows, label) for label in labels}
    controls = [views[l] for l in ('A1', 'A2') if l in views]
    candidates = [views[l] for l in ('B0', 'B1') if l in views]
    collapsed = bool(controls and candidates) and \
        max(c['slow_readback_fraction'] for c in candidates) <= 0.5 * min(a['slow_readback_fraction'] for a in controls) and \
        all(c['readback_ms_per_fill_mb'] is not None and a['readback_ms_per_fill_mb'] is not None and
            c['readback_ms_per_fill_mb'] <= 0.5 * a['readback_ms_per_fill_mb'] for c in candidates for a in controls)
    moved = bool(controls and candidates) and all(
        c['wall_ms_per_fill_mb'] is not None and a['wall_ms_per_fill_mb'] is not None and
        c['wall_ms_per_fill_mb'] > 0.5 * a['wall_ms_per_fill_mb'] for c in candidates for a in controls)
    carriers = sorted({a['fill_wait_carrier'] for a in controls})
    price = {}
    for label, v in views.items():
        s = v.get('fill_split') or {}
        if s.get('available'):
            price[label] = dict(ceiling_ms_per_token=s['fill_attributable_outside_transfer_ms_per_token'],
                                ceiling_fraction_of_wall=s['fill_attributable_fraction_of_wall'],
                                filled_minus_unfilled_outside_transfer_ms=s['fill_attributable_outside_transfer_ms_per_filled_token'],
                                filled_slope_vs_unfilled_control=[s['outside_transfer_ms_per_fill_mb_filled_tokens'],
                                                                  s['control_unfilled_outside_transfer_ms_per_next_fill_mb']])
    if candidate_wins and collapsed:
        verdict = 'confirmed: foreground transfers waited behind fill bytes on the shared copy engine; kernel I/O removes the wait'
    elif not candidate_wins and collapsed and moved:
        verdict = 'moved: kernel I/O removed the transfer wait but the fill cost reappeared in the token wall (fill contention elsewhere)'
    elif not candidate_wins and not collapsed:
        verdict = 'close: kernel I/O did not remove the fill coupling of the foreground transfers'
    else:
        verdict = 'mixed: speed and transfer-slope collapse disagree; record and review before any follow-up'
    return dict(schema='packet176.mechanism.v1', definitions=dict(
        slow_readback_ms=SLOW_MS, tokens='generated_index >= 2',
        transfer='transfer_wall_ms = head (token id + lookup rows) + tail (error/next_token) foreground transfer time',
        fill_bytes='same-position delta of cache.jsonl fill_bytes_total (submitted at that position start)',
        carrier_rule='head when head slope >= 0.6 x transfer slope, tail when <= 0.4 x, else both'),
        views=views, slow_mode_collapsed=collapsed, fill_cost_moved=moved, control_fill_wait_carrier=carriers,
        fill_lever_price=dict(rule='(filled minus unfilled wall outside the transfer window) x filled fraction; ceiling for any fill pacing/deferral, not a projection',
                              views=price),
        collapse_rule='max B slow fraction <= 0.5 x min warm A slow fraction AND every B transfer slope <= 0.5 x every warm A slope',
        moved_rule='every B wall slope per same-token fill MB > 0.5 x every warm A wall slope',
        candidate_wins=bool(candidate_wins), verdict=verdict)
