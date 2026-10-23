"""Test the analyzer on REAL device evidence so packaging failures are caught on CPU (read in place).

1. packet58-onecard-cache23's real one-load WSCREEN bracket (screen/evidence/card0-58c23-v5-a, 5 views, 60 exact requests,
   the +1.72 % max23 screen win): the real 60-request checker re-verifies every token against the oracle; the comparator
   must REFUSE cache23's max/max23 views as this candidate (gate-up view order check); relabelled as max23/max23+diet the
   NULL TEST reproduces its +1.717 % minimum gain over the warm controls; the mechanism readout (fills/token, MB/token,
   miss-read regression, the new layer-body host scope) runs on all five views and its packet176/cache23 fields must
   equal cache23's committed summary (the additions change nothing already reported); the diet decision on that real
   data must fire the fills-equality kill (cache23's B views fill 12.9 % less: a capacity bracket is not a diet bracket).
2. packet58-onecard-cache23-chain's real record WS128 (the single-view chain layout, 12 exact requests): the record
   36.602512 tok/s reproduced from the raw streams; readout on the record stream; fills/token and MB/token must equal the
   bracket's max23 views (same cache policy at max23) and the miss-read slope must sit in the 0.030-0.040 ms/MB band.
3. Decision arithmetic on real token identities with explicitly synthetic rates/scopes: winner / not / chain / every
   kill rule; the queue_runner's field (candidate_beats_all_controls) is kept.
Writes evidence/analyzer-real-parent.json; raw streams are provenance only (never pinned).
"""
import copy, json, math, sys
from pathlib import Path
from build_engine import P, ROOT, sha, save
sys.path.insert(0, str(P / 'screen'))
import suite_driver as D
import mechanism as M
from compare_bracket import compare, s58de_decision, CONTROL_VIEW, CANDIDATE_VIEW
BRACKET = P.parent / 'packet58-onecard-cache23/screen/evidence/card0-58c23-v5-a/resident/WSCREEN/run'
RECORD = P.parent / 'packet58-onecard-cache23-chain/evidence/card0-cache23-a/WS128/run'
LABELS = ['A0', 'B0', 'A1', 'B1', 'A2']
RATE = 'class_balanced_tok_s_1_100_intervals_after_ttft'
RECORD_TOK_S = 36.602512
ORIGINAL_FIELDS = ('tokens', 'foreground_io', 'engine', 'wall_ms', 'wait_ms', 'transfer_wall_ms', 'fill_tokens', 'fill_mb_per_token', 'fills_per_token',
                   'readback_ms_per_fill_mb', 'wall_ms_per_fill_mb', 'wait_ms_per_fill_mb', 'end_of_position_states', 'fill_wait_carrier', 'miss_read_regression')


def rates(views, values):
    out = copy.deepcopy(views)
    for v, r in zip(out, values):
        v[RATE]['median'] = r
    return out


def scopes(readout, a_body, b_body):
    syn = copy.deepcopy(readout)
    for l in LABELS:
        syn['views'][l]['layer_body_ms'] = b_body if l in ('B0', 'B1') else a_body
    return syn


def main():
    manifest = D.oracle_inputs()
    provenance = []
    # 1. cache23 bracket: real exactness checker on 60 requests; refusal as this candidate; null test relabelled.
    rows = []
    for label in LABELS:
        s = D.summarize(BRACKET, 'WSCREEN', manifest, label, 128)
        assert s['passed'] and s['request_count'] == 12 and all(r['exact_oracle'] for r in s['requests'])
        s.update(label=label, view='max23' if LABELS.index(label) % 2 else 'max')
        rows.append(s)
    try:
        compare(rows)
    except ValueError as e:
        refused = str(e)
    else:
        raise AssertionError('cache23 max/max23 views accepted as max23/max23+diet views')
    try:
        D.verify_lookup_views(BRACKET, 'resident')
    except (ValueError, KeyError, FileNotFoundError):
        pass
    else:
        raise AssertionError('cache23 boundary records (no expert_gateup) accepted as gate-up views')
    null = copy.deepcopy(rows)
    for i, r in enumerate(null):
        r.update(view=CANDIDATE_VIEW if i % 2 else CONTROL_VIEW)
    c = compare(null)
    measured = [r[RATE]['median'] for r in rows]
    assert abs(c['minimum_gain_vs_best_control'] - 0.01717) < 0.0002 and c['candidate_beats_all_controls'], c
    readout = M.readout(BRACKET / 'run', LABELS, None, True)
    committed = json.loads((BRACKET / 'summary.json').read_text())['mechanism_readout']
    for label in LABELS:
        for k in ORIGINAL_FIELDS:
            assert readout['views'][label][k] == committed['views'][label][k], (label, k)
        v = readout['views'][label]
        assert v['tokens'] == 1524 and 0.030 <= v['miss_read_regression']['unfilled_ms_per_next_fill_mb'] <= 0.040
        assert 20 < v['layer_body_ms'] < 35 and v['layer_body_ms'] < v['wall_ms']
    null_decision = s58de_decision(c, readout)
    assert not null_decision['screen_winner'] and null_decision['fills_equal_across_arms'] is False and any('moved bytes' in k for k in null_decision['kill_rules_fired']), null_decision
    capacity_saving = null_decision['gateup_saving_us_per_layer']
    assert 5 < capacity_saving < 12, capacity_saving   # cache23's +1.72 % was the capacity effect (fewer fills): ~8.6 us per layer of layer body, not a gate/up saving
    for leaf in ('run/cache.jsonl', 'suite-inputs.tsv', 'run/receipt.json', 'summary.json'):
        provenance.append(dict(name='packet58-onecard-cache23:' + leaf, parent_relpath=str((BRACKET / leaf).relative_to(ROOT)), parent_digest=sha(BRACKET / leaf)))
    # 2. cache23-chain record WS128 (single view, label '').
    rec = D.summarize(RECORD, 'WS128', manifest, None, 128)
    assert rec['passed'] and rec['request_count'] == 12 and rec['timing_claim_eligible']
    assert abs(rec[RATE]['median'] - RECORD_TOK_S) < 5e-7, rec[RATE]['median']
    rr = M.readout(RECORD / 'run', [''], None, False)['views']['']
    assert rr['foreground_io'] == 'kernel' and rr['tokens'] == 1524
    assert abs(rr['fills_per_token'] - readout['views']['B0']['fills_per_token']) < 1e-9 and abs(rr['fill_mb_per_token'] - readout['views']['B0']['fill_mb_per_token']) < 1e-9
    assert 0.030 <= rr['miss_read_regression']['unfilled_ms_per_next_fill_mb'] <= 0.040
    for leaf in ('run/cache.jsonl', 'suite-inputs.tsv', 'run/receipt.json', 'summary.json'):
        provenance.append(dict(name='packet58-onecard-cache23-chain-WS128:' + leaf, parent_relpath=str((RECORD / leaf).relative_to(ROOT)), parent_digest=sha(RECORD / leaf)))
    # 3. Decision arithmetic on real token identities, synthetic rates and scopes (labeled synthetic; never device data).
    fixture = copy.deepcopy(null)
    equal = copy.deepcopy(readout)
    for l in LABELS:   # synthetic readout: identical fills on every view (the diet moves no bytes), 12.5 us/layer saving
        equal['views'][l]['fills_per_token'] = readout['views']['B0']['fills_per_token']; equal['views'][l]['fill_mb_per_token'] = readout['views']['B0']['fill_mb_per_token']
    syn = scopes(equal, 27.60, 27.00)
    cases = {}
    def decide(values, ro=syn):
        c = compare(rates(fixture, values)); return c, s58de_decision(c, ro)
    c, d = decide([36.55, 36.95, 36.60, 36.96, 36.58])        # +0.96 % screen win, no chain
    cases['screen_win'] = dict(candidate_beats_all_controls=c['candidate_beats_all_controls'], screen_winner=d['screen_winner'], chain_rule=d['chain_rule'], kills=d['kill_rules_fired'], saving=d['gateup_saving_us_per_layer'])
    assert c['candidate_beats_all_controls'] and d['screen_winner'] and not d['chain_rule'] and not d['kill_rules_fired'] and abs(d['gateup_saving_us_per_layer'] - 12.5) < 1e-6
    c, d = decide([36.55, 36.77, 36.60, 36.78, 36.58])        # +0.46 % < screen bar
    cases['below_screen_bar'] = dict(candidate_beats_all_controls=c['candidate_beats_all_controls'], screen_winner=d['screen_winner'])
    assert not c['candidate_beats_all_controls'] and not d['screen_winner']
    c, d = decide([36.55, 37.40, 36.60, 37.41, 36.58])        # >= +2 % over every control view and >= 37.3346
    cases['chain_rule'] = dict(screen_winner=d['screen_winner'], chain_rule=d['chain_rule'], minimum_gain=d['minimum_gain_vs_every_control_view'])
    assert d['screen_winner'] and d['chain_rule']
    c, d = decide([36.55, 37.34, 36.60, 37.33, 36.58])        # one diet view below the bar -> no chain
    assert d['screen_winner'] and not d['chain_rule']; cases['chain_bar_missed'] = dict(chain_rule=d['chain_rule'])
    c, d = decide([36.55, 36.95, 35.99, 36.96, 36.58])        # warm control below 36.0 -> host disturbed
    assert not d['screen_winner'] and any('36.0' in k for k in d['kill_rules_fired']); cases['warm_floor'] = dict(kills=d['kill_rules_fired'])
    c, d = decide([36.55, 38.2, 36.60, 38.2, 35.40])          # drift 3.4 % -> kill
    assert not d['screen_winner'] and any('drift' in k for k in d['kill_rules_fired']); cases['drift'] = dict(kills=d['kill_rules_fired'], drift=c['control_drift_fraction'])
    c, d = decide([36.55, 36.95, 36.60, 36.96, 36.58], scopes(equal, 27.60, 27.40))   # 4.2 us/layer < 5 -> kill
    assert not d['screen_winner'] and any('us per layer' in k for k in d['kill_rules_fired']); cases['saving_floor'] = dict(kills=d['kill_rules_fired'], saving=d['gateup_saving_us_per_layer'])
    c, d = decide([36.55, 36.95, 36.60, 36.96, 36.58], scopes(readout, 27.60, 27.00))  # real cache23 fills (B 12.9 % below A) -> moved bytes kill
    assert not d['screen_winner'] and d['fills_equal_across_arms'] is False; cases['fills_differ'] = dict(kills=d['kill_rules_fired'])
    for l in LABELS:
        assert d['per_view'][l]['fills_per_token'] == readout['views'][l]['fills_per_token'] and d['per_view'][l]['miss_read_regression'] == readout['views'][l]['miss_read_regression']
    bad = rates(fixture, [36.55, 36.95, 36.60, 36.96, 36.58]); bad[-1]['requests'][-1]['tokens'][-1] += 1
    try:
        compare(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('corruption accepted')
    for wrong in ('spin-kio', 'resident', 'max23', 'max+diet'):
        relabeled = rates(fixture, [36.55, 36.95, 36.60, 36.96, 36.58]); relabeled[1]['view'] = wrong
        try:
            compare(relabeled)
        except ValueError:
            pass
        else:
            raise AssertionError(wrong + ' accepted as max23+diet')
    save(P / 'evidence/analyzer-real-parent.json', dict(
        passed=True, device_executed=False, schema='packet58dietengine.analyzer.v1',
        cache23_bracket=dict(exact_requests=60, refused_as_candidate=refused, measured_rates=measured,
                             null_test=dict(relabelled_views=[CONTROL_VIEW, CANDIDATE_VIEW], minimum_gain_vs_best_control=c['minimum_gain_vs_best_control'] if False else compare(null)['minimum_gain_vs_best_control'],
                                            reproduces_cache23_plus_1_72_pct=True, diet_decision_on_capacity_data=dict(screen_winner=null_decision['screen_winner'], kills=null_decision['kill_rules_fired'],
                                            layer_body_delta_us_per_layer=capacity_saving, note='the +1.72 % of cache23 is the capacity effect (fewer fills); as a diet bracket it is refused by the fills-equality rule, which is the expected refusal of a capacity bracket, not a device result')),
                             packet176_cache23_fields_identical_to_committed_summary=True,
                             readout={l: dict(fills_per_token=readout['views'][l]['fills_per_token'], fill_mb_per_token=readout['views'][l]['fill_mb_per_token'],
                                              layer_body_ms=readout['views'][l]['layer_body_ms'], wall_ms=readout['views'][l]['wall_ms'], wait_ms=readout['views'][l]['wait_ms'],
                                              miss_read_regression=readout['views'][l]['miss_read_regression']) for l in LABELS}),
        cache23_chain_ws128=dict(exact_requests=12, record_tok_s=rec[RATE]['median'], fills_per_token=rr['fills_per_token'], fill_mb_per_token=rr['fill_mb_per_token'],
                                 layer_body_ms=rr['layer_body_ms'], miss_read_regression=rr['miss_read_regression'], wall_ms=rr['wall_ms']),
        decision_cases=cases, synthetic_rates=True, provenance=provenance))
    print('PASS analyzer on real cache23 bracket (60 exact, null +%.3f %%) + cache23-chain WS128 (12 exact, %.6f); decision cases %d' % (100 * compare(null)['minimum_gain_vs_best_control'], rec[RATE]['median'], len(cases)))


if __name__ == '__main__':
    main()
