"""Packet183 S1 bracket decision: one rule, used by the bracket summary and the waiter.

screen winner: both candidate (metadata) views >= +0.5% over every control view and
               control drift <= 3% (packet153/182 v5 screen bar);
chain rule:    both candidates >= +2% over every control (packet153's
               candidate_qualified) AND both >= 1.02 x the live two-card record
               58.798108759 tok/s (packet182's record bar, two-card form).
Exactness (13/13 per view) and identical draft proposals are enforced upstream by
p183_v5_compare.finish_bracket; from_summary() re-checks them on a saved summary.
"""
RECORD=58.798108759182306

def decide(views,drift):
    controls=[v['rate'] for v in views if v['choice']=='control']
    cand=[v['rate'] for v in views if v['choice']=='candidate']
    if len(controls)!=3 or len(cand)!=2:raise ValueError('S1 decision needs the five-view A/B/A/B/A bracket')
    gain=min(cand)/max(controls)-1;bar=1.02*RECORD
    qualified=drift<=3.0 and all(c>=1.02*max(controls) for c in cand)
    return dict(min_gain_percent=100*gain,best_control_rate=max(controls),slower_candidate_rate=min(cand),control_drift_percent=drift,
                screen_winner=bool(drift<=3.0 and gain>=0.005),candidate_qualified=bool(qualified),record_rate=RECORD,record_bar_rate=bar,
                chain_rule_met=bool(qualified and min(cand)>=bar),
                rule='screen winner: both candidates >= +0.5% over every control, drift <= 3%; chain: both >= +2% over every control AND >= 1.02 x 58.798109 (record); every view 13/13 exact and identical draft proposals')

def from_summary(summary):
    if not (summary.get('passed') is True and summary.get('kind')=='bracket' and summary.get('all_13_exact') is True
            and summary.get('draft_proposals_identical') is True):raise ValueError('summary is not a passed exact bracket')
    views=summary['views']
    if [v['choice'] for v in views]!=['control','candidate','control','candidate','control']:raise ValueError('view order')
    if not all(v.get('all_13_exact') is True and v.get('exact_count')==13 for v in views):raise ValueError('inexact view')
    controls=[v['rate'] for v in views if v['choice']=='control'];drift=100*(max(controls)/min(controls)-1)
    if abs(drift-summary['control_drift_percent'])>1e-9:raise ValueError('drift does not match the summary')
    return decide(views,drift)
