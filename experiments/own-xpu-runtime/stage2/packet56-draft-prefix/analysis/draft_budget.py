#!/usr/bin/env python3
"""Read retained timing receipts only; emit aggregate timings, never token IDs.

Run with nice -n 19 taskset -c 4-15,20-31 python3 -B.
These timing inputs must not participate in prefix selection.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics as st

ROOT = Path(__file__).resolve().parents[5]
STAGE = ROOT / 'experiments/own-xpu-runtime/stage2'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary(values):
    return {'count': len(values), 'median_ms': st.median(values),
            'mean_ms': st.mean(values)} if values else None


def window(path):
    sources, draft, traces, cycles, acceptance = [], [], [], {'hit': [], 'miss': []}, []
    for f in sorted((path / 'run/repeat-1').glob('*/receipt.json')):
        j = json.loads(f.read_bytes())
        sources.append({'path': str(f), 'sha256': digest(f)})
        draft.extend(r for r in j['draft_rows'] if r.get('hit') is not None)
        # Op::draft == 9. No output tokens or guesses are emitted by this script.
        traces.extend(1000*(r['rank_completed']-r['rank_received'])
                      for r in j['rank_trace']
                      if r['op'] == 9 and r['rank'] == 1 and r['position'] >= 100)
        for branch in cycles:
            cycles[branch].append(j['hit_miss_cycles'][branch]['mean_ms'])
        acceptance.append(j['acceptance'])
    assert len(sources) == 12, 'Expected complete retained 12-request suite'
    result = {'sources': sources, 'scope': 'all hit/miss-labeled draft rows; no prefill',
              'draft_wall': summary([r['draft_wall_ms'] for r in draft]),
              'draft_command_steady_position_ge_100': summary(traces),
              'cycle_median_of_request_means_ms': {k: st.median(v) for k, v in cycles.items()},
              'acceptance_median': st.median(acceptance)}
    for label, hit in [('hit', True), ('miss', False)]:
        result[f'draft_wall_{label}'] = summary([r['draft_wall_ms'] for r in draft if r['hit'] == hit])
    result['draft_gpu_timed_row_count'] = sum(r.get('draft_gpu_ms') is not None for r in draft)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selection', type=Path, default=Path(__file__).resolve().parents[1] / 'calibration/selection.json')
    a = ap.parse_args()
    selection = json.loads(a.selection.read_bytes())
    assert selection['schema'] == 'lab.packet56.draft-prefix-selection.v1'
    a.prefix = selection['draft_vocab_rows']
    a.outside_fraction = selection['excluded_tokens'] / selection['tokens']
    assert a.outside_fraction == selection['excluded_fraction']
    chain = STAGE / 'packet49c-round2/build/device-cards01-a'
    result = {'schema': 'packet56.draft-budget.v1', 'device_executed': False,
              'not_prefix_selection_data': True,
              'windows': {
                  'packet45-speed6': window(STAGE / 'packet45-merged3/build/speed6-c4096-dr1-s23-cards01-gpu/WS128'),
                  'packet49c-WS128': window(chain / 'WS128'),
                  'packet49c-WS128x': window(chain / 'WS128x')}}
    source = chain / 'K2/run0/summary.json'
    classes = json.loads(source.read_bytes())['classes']
    head = classes['gemv:logits']['comparisons']['p33.dense.segment']
    argmax = classes['argmax']['comparisons']['round2']['reread']['specialised']['execution_sum']
    proxy = {'source': str(source), 'sha256': digest(source),
             'scope': 'K2 operator proxies, not production draft per-site timing',
             'head_candidate': 'p33.dense.segment',
             'head_reread_ms': head['reread']['specialised']['execution_sum']['median_ns']/1e6,
             'head_rotated_ms': head['rotated']['specialised']['execution_sum']['median_ns']/1e6,
             'argmax_reread_ms': argmax['median_ns']/1e6,
             'repetitions': argmax['count']}
    d = result['windows']['packet49c-WS128']['draft_wall']['median_ms']
    proxy['head_plus_argmax_rotated_proxy_ms'] = proxy['head_rotated_ms'] + proxy['argmax_reread_ms']
    proxy['fraction_of_draft_wall_proxy'] = proxy['head_plus_argmax_rotated_proxy_ms'] / d
    proxy['remaining_wall_proxy_ms'] = d - proxy['head_plus_argmax_rotated_proxy_ms']
    result['operator_proxy'] = proxy
    result['profile_files'] = []
    for owner in ['owner0', 'owner1']:
        for name in ['sites.jsonl.gz', 'timings.jsonl.gz']:
            f = chain / 'KD' / owner / name
            with gzip.open(f, 'rb') as stream:
                n = len(stream.read())
            result['profile_files'].append({'path': str(f), 'sha256': digest(f),
                                           'uncompressed_bytes': n})
    result['head_layout'] = {'vocabulary_rows': 248320, 'columns': 2560,
                             'row_stride_bytes': 3380, 'code_scale_read_bytes_per_row': 3200,
                             'allocation_bytes': 839321600, 'useful_read_bytes': 794624000,
                             'unique_draft_weight_read_bytes': 1037289472}
    if a.prefix is not None or a.outside_fraction is not None:
        assert a.prefix is not None and a.outside_fraction is not None
        assert 0 < a.prefix <= 248320 and 0 <= a.outside_fraction <= 1
        base = result['windows']['packet49c-WS128']
        hit, miss = (base['cycle_median_of_request_means_ms'][k] for k in ['hit', 'miss'])
        p = base['acceptance_median']
        # Credit proportional GEMV saving only; argmax remains uncredited.
        saved = proxy['head_rotated_ms'] * (1-a.prefix/248320)
        baseline_ms = p*hit + (1-p)*miss
        cases = []
        # q is only a coverage statistic. Bounds follow from intersection of
        # previous hits and outside-prefix target tokens. In-prefix misses may
        # turn into hits, so this conservative envelope gives them no credit.
        for label, loss in [('no_lost_hit', max(0., p+a.outside_fraction-1)),
                            ('independence_illustration', p*a.outside_fraction),
                            ('all_outside_are_lost_hits', min(p, a.outside_fraction))]:
            pp = p-loss
            hh = hit-saved
            ms = pp*hh+(1-pp)*miss
            cases.append({'label': label, 'acceptance_assumed': pp,
                          'hit_ms': hh, 'miss_ms': miss,
                          'weighted_cycle_ms': ms, 'projected_tok_s': 1000/ms,
                          'gain_percent': 100*(baseline_ms/ms-1)})
        result['projection'] = {'measured': False, 'prefix': a.prefix,
                                'selection_sha256': digest(a.selection),
                                'outside_fraction_independent_calibration': a.outside_fraction,
                                'formula': 'hit=D+max(S,B); miss=max(D,R+A)+max(S,B)',
                                'assumptions': 'Linear head GEMV scaling; R+A remains greater than D; target halves unchanged; no credit for new in-prefix hits; calibration q assumed to transfer.',
                                'draft_ms_proxy_after': d-saved,
                                'head_gemv_saving_ms_proxy': saved,
                                'baseline_weighted_tok_s': 1000/baseline_ms,
                                'not_the_class_balanced_record': True,
                                'cases': cases}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
