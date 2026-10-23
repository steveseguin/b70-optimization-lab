"""Test the analyzer on REAL device evidence so packaging failures are caught on CPU (read in place).

1. packet182's real one-load bracket (screen/evidence/card0-182-v5-a, 5 views, 60 exact requests):
   the real 60-request checker re-verifies every token against the oracle; the comparator must
   REFUSE packet182's spin/spin-kio views as this candidate (capacity order check); the mechanism
   readout (fills/token, MB/token, miss-read regression) runs on all five views and its packet176
   fields must equal packet182's committed summary (the additions change nothing already reported).
2. packet182c's real record WS128 (the single-view chain layout, 12 exact requests): readout on the
   record stream; fills/token and MB/token must equal the bracket's kernel-I/O views (same cache
   policy at max), and the miss-read slope must sit in the 0.030-0.040 ms/MB band of every
   one-card spin stream since packet171.
3. Decision arithmetic on real token identities with explicitly synthetic rates: winner / not /
   chain / every kill rule; the queue_runner's field (candidate_beats_all_controls) is kept.
Writes evidence/analyzer-real-parent.json; raw streams are provenance only (never pinned).
"""
import copy, json, math, sys
from pathlib import Path
from build_engine import P, ROOT, sha, save
sys.path.insert(0, str(P / 'screen'))
import suite_driver as D
import mechanism as M
from compare_bracket import compare, s58c23_decision
BRACKET = P.parent / 'packet182-onecard-kio-rebracket/screen/evidence/card0-182-v5-a/resident/WSCREEN/run'
RECORD = P.parent / 'packet182c-chain/evidence/card0-182-a/WS128/run'
LABELS = ['A0', 'B0', 'A1', 'B1', 'A2']
RATE = 'class_balanced_tok_s_1_100_intervals_after_ttft'
ORIGINAL_FIELDS = ('tokens', 'foreground_io', 'engine', 'wall_ms', 'wait_ms', 'transfer_wall_ms', 'fill_tokens', 'fill_mb_per_token',
                   'readback_ms_per_fill_mb', 'wall_ms_per_fill_mb', 'wait_ms_per_fill_mb', 'end_of_position_states', 'fill_wait_carrier')


def rates(views, values):
    out = copy.deepcopy(views)
    for v, r in zip(out, values):
        v[RATE]['median'] = r
    return out


def main():
    manifest = D.oracle_inputs()
    provenance = []
    # 1. packet182 bracket: real exactness checker on 60 requests; refusal as this candidate.
    rows = []
    for label in LABELS:
        s = D.summarize(BRACKET, 'WSCREEN', manifest, label, 128)
        assert s['passed'] and s['request_count'] == 12 and all(r['exact_oracle'] for r in s['requests'])
        s.update(label=label, view='spin-kio' if LABELS.index(label) % 2 else 'spin')
        rows.append(s)
    try:
        compare(rows)
    except ValueError as e:
        refused = str(e)
    else:
        raise AssertionError('packet182 spin/spin-kio views accepted as max/max23 views')
    try:
        D.verify_lookup_views(BRACKET, 'resident')
    except (ValueError, KeyError, FileNotFoundError):
        pass
    else:
        raise AssertionError('packet182 boundary records accepted as capacity views')
    readout = M.readout(BRACKET / 'run', LABELS, None, True)
    committed = json.loads((BRACKET / 'summary.json').read_text())['mechanism_readout']
    for label in LABELS:
        for k in ORIGINAL_FIELDS:
            assert readout['views'][label][k] == committed['views'][label][k], (label, k)
        v = readout['views'][label]
        assert v['tokens'] == 1524 and abs(v['fill_mb_per_token'] - 30.63) < 0.01 and abs(v['fills_per_token'] - 15.449) < 0.001
        mr = v['miss_read_regression']
        assert 0.030 <= mr['unfilled_ms_per_next_fill_mb'] <= 0.040 and 1500 <= mr['unfilled_tokens'] + mr['filled_tokens'] <= 1524
    for leaf in ('run/cache.jsonl', 'suite-inputs.tsv', 'run/receipt.json', 'summary.json'):
        provenance.append(dict(name='packet182:' + leaf, parent_relpath=str((BRACKET / leaf).relative_to(ROOT)), parent_digest=sha(BRACKET / leaf)))
    # 2. packet182c record WS128 (single view, label '').
    rec = D.summarize(RECORD, 'WS128', manifest, None, 128)
    assert rec['passed'] and rec['request_count'] == 12 and rec['timing_claim_eligible']
    assert abs(rec[RATE]['median'] - 35.92672010504166) < 1e-9, rec[RATE]['median']
    rr = M.readout(RECORD / 'run', [''], None, False)['views']['']
    assert rr['foreground_io'] == 'kernel' and rr['tokens'] == 1524
    assert abs(rr['fills_per_token'] - readout['views']['B0']['fills_per_token']) < 1e-9 and abs(rr['fill_mb_per_token'] - readout['views']['B0']['fill_mb_per_token']) < 1e-9
    assert 0.030 <= rr['miss_read_regression']['unfilled_ms_per_next_fill_mb'] <= 0.040
    for leaf in ('run/cache.jsonl', 'suite-inputs.tsv', 'run/receipt.json', 'summary.json'):
        provenance.append(dict(name='packet182c-WS128:' + leaf, parent_relpath=str((RECORD / leaf).relative_to(ROOT)), parent_digest=sha(RECORD / leaf)))
    # 3. Decision arithmetic on real token identities, synthetic rates (labeled synthetic; never device data).
    fixture = copy.deepcopy(rows)
    for i, r in enumerate(fixture):
        r.update(label=LABELS[i], view='max23' if i % 2 else 'max')
    # synthetic readout: B fills 10 % below A (passes the 8 % rule)
    syn = copy.deepcopy(readout)
    for l in ('B0', 'B1'):
        syn['views'][l]['fills_per_token'] = round(0.90 * syn['views']['A1']['fills_per_token'], 3)
    cases = {}
    def decide(values, ro=syn):
        c = compare(rates(fixture, values)); return c, s58c23_decision(c, ro)
    c, d = decide([35.9, 36.2, 35.93, 36.21, 35.92])        # +0.75 % screen win, no chain
    cases['screen_win'] = dict(candidate_beats_all_controls=c['candidate_beats_all_controls'], screen_winner=d['screen_winner'], chain_rule=d['chain_rule'], kills=d['kill_rules_fired'])
    assert c['candidate_beats_all_controls'] and d['screen_winner'] and not d['chain_rule'] and not d['kill_rules_fired']
    c, d = decide([35.9, 36.10, 35.93, 36.11, 35.92])       # +0.47 % < screen bar
    cases['below_screen_bar'] = dict(candidate_beats_all_controls=c['candidate_beats_all_controls'], screen_winner=d['screen_winner'])
    assert not c['candidate_beats_all_controls'] and not d['screen_winner']
    c, d = decide([35.9, 36.70, 35.93, 36.71, 35.92])       # >= +2 % over every max view and >= 36.645
    cases['chain_rule'] = dict(screen_winner=d['screen_winner'], chain_rule=d['chain_rule'], minimum_gain=d['minimum_gain_vs_every_max_view'])
    assert d['screen_winner'] and d['chain_rule']
    c, d = decide([35.9, 36.66, 35.93, 36.64, 35.92])       # one max23 view below 36.645 -> no chain
    assert d['screen_winner'] and not d['chain_rule']; cases['chain_bar_missed'] = dict(chain_rule=d['chain_rule'])
    c, d = decide([35.9, 36.2, 35.1, 36.21, 35.92])         # warm max below 35.2 -> host disturbed (A1/A2 drift 2.3 % still <= 3 %)
    assert not d['screen_winner'] and any('35.2' in k for k in d['kill_rules_fired']); cases['warm_floor'] = dict(kills=d['kill_rules_fired'])
    c, d = decide([35.9, 37.5, 35.93, 37.5, 34.80])         # drift 3.2 % -> kill
    assert not d['screen_winner'] and any('drift' in k for k in d['kill_rules_fired']); cases['drift'] = dict(kills=d['kill_rules_fired'], drift=c['control_drift_fraction'])
    flat = copy.deepcopy(readout)                           # real readout: fills identical on every view -> 8 % rule fails -> capacity closed
    c, d = decide([35.9, 36.2, 35.93, 36.21, 35.92], flat)
    assert not d['screen_winner'] and d['capacity_closed_at_23gb'] and not d['fills_reduced_8pct']; cases['fills_not_reduced'] = dict(kills=d['kill_rules_fired'], capacity_closed=d['capacity_closed_at_23gb'])
    for l in LABELS:
        assert d['per_view'][l]['fills_per_token'] == readout['views'][l]['fills_per_token'] and d['per_view'][l]['miss_read_regression'] == readout['views'][l]['miss_read_regression']
    bad = rates(fixture, [35.9, 36.2, 35.93, 36.21, 35.92]); bad[-1]['requests'][-1]['tokens'][-1] += 1
    try:
        compare(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('corruption accepted')
    for wrong in ('spin-kio', 'resident', 'max24'):
        relabeled = rates(fixture, [35.9, 36.2, 35.93, 36.21, 35.92]); relabeled[1]['view'] = wrong
        try:
            compare(relabeled)
        except ValueError:
            pass
        else:
            raise AssertionError(wrong + ' accepted as max23')
    save(P / 'evidence/analyzer-real-parent.json', dict(
        passed=True, device_executed=False, schema='packet58cache23.analyzer.v1',
        packet182_bracket=dict(exact_requests=60, refused_as_candidate=refused, measured_rates=[r[RATE]['median'] for r in rows],
                               packet176_fields_identical_to_committed_summary=True,
                               readout={l: dict(fills_per_token=readout['views'][l]['fills_per_token'], fill_mb_per_token=readout['views'][l]['fill_mb_per_token'],
                                                miss_read_regression=readout['views'][l]['miss_read_regression']) for l in LABELS}),
        packet182c_ws128=dict(exact_requests=12, record_tok_s=rec[RATE]['median'], fills_per_token=rr['fills_per_token'], fill_mb_per_token=rr['fill_mb_per_token'],
                              miss_read_regression=rr['miss_read_regression'], wall_ms=rr['wall_ms']),
        decision_cases=cases, synthetic_rates=True, provenance=provenance,
        note='fills/token are identical on every view of packet182 (same policy at the same capacity); the real readout therefore fails '
             'the 8 % rule by construction, which is the expected refusal of a no-capacity-change bracket, not a device result'))
    print('PASS analyzer on real packet182 bracket (60 exact) + packet182c WS128 (12 exact, 35.92672010504166); decision cases', len(cases))


if __name__ == '__main__':
    main()
