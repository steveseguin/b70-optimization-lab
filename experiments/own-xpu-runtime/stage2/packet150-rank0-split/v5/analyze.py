"""Preregistered host-boundary attribution; never a performance promotion.

Use only complete scopes inside timestamps 1..64, excluding prefill and the
incident request. Sum each scope over those 63 cycles, then median prompts.
Replay-minus-skip estimates incremental duplicate service, not safe removal.
"""
import json
import math
import statistics
from pathlib import Path

SEGMENTS = {
    'token_prep': ('token_prep', 'token_history'),
    'capture_snapshot': ('snapshot', 'accept', 'rollback'),
    'suffix_head': ('suffix_head',),
    'merge_handoff_waits': ('head_hidden_wait', 'head_import', 'head_export',
                            'handoff_export', 'handoff_host', 'remote_reply_wait'),
    'draft_wait': ('draft_wait',),
}
REPLAYS = {'token_prep': 'token_prep_duplicate',
           'capture_snapshot': 'snapshot_duplicate',
           'suffix_head': 'suffix_duplicate',
           'merge_handoff_waits': 'head_zero_wait',
           'draft_wait': 'draft_zero_wait'}
THRESHOLD_MS = 0.4


def demand(value, reason):
    if not value:
        raise ValueError(reason)


def request_split(root, request):
    native_path = root / request['prompt_id'] / 'native-result.json'
    native = json.loads(native_path.read_text()) if native_path.exists() else request
    stamps = request['token_timestamps']
    demand(len(stamps) == 64 and all(math.isfinite(x) for x in stamps)
           and all(b > a for a, b in zip(stamps, stamps[1:])), '64 monotone timestamps required')
    clock = root / request['prompt_id'] / 'rank0/timings.jsonl'
    demand(clock.is_file(), 'missing rank0 timing receipt')
    records = [json.loads(line) for line in clock.read_text().splitlines() if line.strip()]
    samples = [r for r in records if 'p150_segment' in r]
    demand(samples, 'missing packet150 scopes; old traces cannot answer this split')
    demand(all(r['rank'] == 0 and math.isfinite(r['ms']) and r['ms'] >= 0
               and r['start'] <= r['end'] for r in samples), 'invalid scope clock')
    measured = [r for r in samples if stamps[0] <= r['start'] <= r['end'] <= stamps[-1]]
    totals = {}
    for r in measured:
        name = r['p150_segment']
        totals[name] = totals.get(name, 0.) + r['ms']
    demand(all(any(r['p150_segment'] == n for r in samples)
               for n in ('token_prep', 'snapshot', 'suffix_head', 'draft_wait',
                         'remote_reply_wait')), 'incomplete scope census')
    # Snapshot includes its duplicate internally. Subtract this nested scope
    # before combining disjoint original-work segments; retain both raw values.
    original = dict(totals)
    def exclusive(parent, children):
        value = 0.
        for scope in measured:
            if scope['p150_segment'] != parent:
                continue
            nested = sum(r['ms'] for r in samples if r['p150_segment'] in children
                         and scope['start'] <= r['start'] <= r['end'] <= scope['end'])
            demand(nested <= scope['ms'] + 0.01, 'nested clocks exceed parent')
            value += max(0., scope['ms']-nested)
        return value
    original['snapshot'] = exclusive('snapshot', {'snapshot_duplicate'})
    half_other = exclusive('half_total', {'layer_body', 'snapshot', 'token_prep',
                                          'token_history', 'handoff_export', 'token_prep_duplicate'})
    head_other = exclusive('head_service_total', {'suffix_head', 'suffix_duplicate', 'head_import',
                                                 'head_export', 'head_hidden_wait', 'head_zero_wait'})
    return dict(prompt_id=request['prompt_id'], interval_count=63,
                first_timestamp=stamps[0], last_timestamp=stamps[-1],
                complete_scopes=len(measured), boundary_or_prefill_scopes=len(samples)-len(measured),
                segments_ms_per_cycle={k: sum(original.get(n, 0.) for n in names)/63
                                       for k, names in SEGMENTS.items()},
                replay_ms_per_cycle={k: totals.get(n, 0.)/63 for k, n in REPLAYS.items()},
                other_outside_ms_per_cycle=(half_other+head_other)/63,
                residual_definition='exclusive half setup/finalization/report plus suffix setup/publication',
                raw_scope_totals_ms=totals,
                cancelled_halves=sum(bool(r.get('cancelled')) for r in records
                                     if 'p150_segment' not in r and r.get('fixture', 0) > 0),
                hits=native.get('stats', {}).get('hits', request.get('hits')),
                misses=native.get('stats', {}).get('misses', request.get('misses')))


def analyze(views, synthetic=False):
    if synthetic:
        return dict(status='synthetic report wiring only', removable_segments=[],
                    device_evidence=False, speed_evidence_eligible=False)
    rows = []
    for v in views:
        requests = [request_split(Path(v['output']), r) for r in v['requests']]
        rows.append(dict(index=v['index'], choice=v['choice'], requests=requests,
                         segments_ms_per_cycle={k: statistics.median(r['segments_ms_per_cycle'][k]
                                                                     for r in requests) for k in SEGMENTS},
                         replay_ms_per_cycle={k: statistics.median(r['replay_ms_per_cycle'][k]
                                                                   for r in requests) for k in SEGMENTS}))
    controls = [r for r in rows if r['choice'] == 'control']
    candidates = [r for r in rows if r['choice'] == 'candidate']
    demand(len(controls) == 3 and len(candidates) == 2, 'complete C/X/C/X/C required')
    decisions = []
    for name in SEGMENTS:
        values = [r['segments_ms_per_cycle'][name] for r in controls]
        observed = statistics.median(values)
        replay = [r['replay_ms_per_cycle'][name] - statistics.mean(c['replay_ms_per_cycle'][name]
                                                                               for c in controls)
                  for r in candidates]
        decisions.append(dict(segment=name, control_median_ms_per_cycle=observed,
                              control_range_ms=max(values)-min(values),
                              replay_minus_skip_ms_per_cycle=replay,
                              at_least_0_4_ms_in_every_control=min(values) >= THRESHOLD_MS,
                              removable=False,
                              verdict=('large measured boundary; removal unproven'
                                       if min(values) >= THRESHOLD_MS else 'below threshold or unresolved drift'),
                              reason='replay isolates duplicate service; required target work and peer dependencies remain'))
    return dict(schema='packet150.rank0-split.v1', status='measured host scopes',
                threshold_ms_per_cycle=THRESHOLD_MS, views=rows, decisions=decisions,
                removable_segments=[], device_evidence=True, speed_evidence_eligible=False,
                clock='host monotonic; asynchronous submission can overlap device work',
                limitation='Boundary-straddling scopes are excluded. Snapshot is host capture/submission cost; '
                           'its asynchronous device copy is not independently timed. Rank1 merge work remains '
                           'inside rank0 reply wait. No replay proves a safe lossless removal.')


if __name__ == '__main__':
    import argparse
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (4*1024**3, 4*1024**3))
    ap = argparse.ArgumentParser()
    ap.add_argument('output', type=Path)
    a = ap.parse_args()
    proof = json.loads((a.output/'run/bracket-inputs.json').read_text())
    print(json.dumps(analyze(proof['views']), indent=2))
