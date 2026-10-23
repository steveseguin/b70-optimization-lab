#!/usr/bin/env python3
"""V3 record-line interval replay (CPU-only, read-only).

Reads packet187's WS128 receipts (the 60.659520 tok/s record chain, 2026-10-22) and packet186's V3 bracket views,
decomposes every one of the 12 x 99 intervals with packet85's vendored interval model plus the V3 boundary
command (rank 0, op 15) on the ready side (exactly packet186 s186_decision.intervals_v3), and reproduces the
record metric: per prompt 99000 / sum(99 intervals), median of class medians.

Interval identity (ms): elapsed = max(D, R + C + Bd) + max(B, A + offset) + G
  D  draft on rank 1 (op 9)            B  rank-1 target half (op 1, non-speculative): layers 26-47 + full head
  A  rank-0 next speculative half       offset  A start - B start
  R  rank-0 rollback (op 3, misses)     C  rank-0 corrected half (op 1 non-spec, misses)
  Bd rank-0 boundary (op 15): layers 24-25 for the verified token   G  unresolved control gaps
Writes intervals-p187.csv and replay-p187.json next to this script.
"""
import csv, importlib.util, json, statistics as st, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2')
P187 = STAGE / 'packet187-record-bundle-v3/build/device-cards01-p187-a/WS128/run'
SUMMARY = STAGE / 'packet187-record-bundle-v3/evidence/device-cards01-p187-a/WS128/summary.json'
spec = importlib.util.spec_from_file_location('interval_model', STAGE / 'packet186-twocard-v3/v5/interval_model.py')
im = importlib.util.module_from_spec(spec); spec.loader.exec_module(im)
assert im.SOURCE_SHA256 == '6627ffa350361a85aed5160f1f5738409cb23bab4f9ca1f34fea7317a0b63ad4'
KEY = 'class_balanced_tok_s_1_100_intervals_after_ttft'


def intervals_v3(r, limit=99):
    rows = im.intervals(r, limit)
    bd = {t['position']: t for t in r['rank_trace'] if t['rank'] == 0 and t['op'] == 15}
    acc0 = {t['position']: t for t in r['rank_trace'] if t['rank'] == 0 and t['op'] == 2}
    acc1 = {t['position']: t for t in r['rank_trace'] if t['rank'] == 1 and t['op'] == 2}
    for x in rows:
        b = bd.get(x['position'])
        x['Bd'] = im.duration(b) if b else 0.0
        ready = max(x['D'], x['R'] + x['C'] + x['Bd'])
        race = max(x['B'], x['A'] + x['spec_start_offset_ms'])
        x['ready'] = ready; x['race'] = race
        x['G'] = x['elapsed_ms'] - ready - race
        x['acc0'] = im.duration(acc0[x['position']]) if x['position'] in acc0 else 0.0
        x['acc1'] = im.duration(acc1[x['position']]) if x['position'] in acc1 else 0.0
        x['rank1_binds'] = x['B'] >= x['A'] + x['spec_start_offset_ms']
        x['boundary_binds_ready'] = x['R'] + x['C'] + x['Bd'] > x['D']
    return rows


def load_view(view_dir, ids=None):
    view_dir = Path(view_dir)
    out = []
    for receipt in sorted(view_dir.glob('*/receipt.json')):
        r = json.loads(receipt.read_text())
        if 'prompt_class' not in r or (ids and r['prompt_id'] not in ids) or len(r.get('token_timestamps', [])) < 100:
            continue  # incident64 smoke receipts (64 tokens) are not part of the 128-token metric
        rows = intervals_v3(r)
        ts = r['token_timestamps']
        assert abs(sum(x['elapsed_ms'] for x in rows) - 1000 * (ts[99] - ts[0])) < 1e-6
        for x in rows:
            x['pid'] = r['prompt_id']; x['cls'] = r['prompt_class']
        out += rows
    return out


def metric(rows, T=None):
    T = T if T is not None else [x['elapsed_ms'] for x in rows]
    per, cls = defaultdict(float), {}
    for x, t in zip(rows, T):
        per[x['pid']] += t; cls[x['pid']] = x['cls']
    by = defaultdict(list)
    for p, s in per.items():
        by[cls[p]].append(99000 / s)
    return st.median(st.median(v) for v in by.values())


def describe(rows):
    hits = [x for x in rows if x['hit']]; miss = [x for x in rows if not x['hit']]
    keys = ['elapsed_ms', 'D', 'B', 'A', 'spec_start_offset_ms', 'Bd', 'R', 'C', 'G', 'acc0', 'acc1', 'ready', 'race']
    d = dict(intervals=len(rows), hits=len(hits), misses=len(miss), hit_fraction=len(hits) / len(rows),
             hit={k: st.mean(x[k] for x in hits) for k in keys}, miss={k: st.mean(x[k] for x in miss) for k in keys})
    slack = [x['B'] - x['A'] - x['spec_start_offset_ms'] for x in hits]
    q = st.quantiles(slack, n=20)
    d['hit_rank0_race_slack_B_minus_A_plus_offset'] = dict(mean=st.mean(slack), p5=q[0], p10=q[1], p50=st.median(slack), min=min(slack))
    dw = [x['D'] - x['Bd'] for x in hits]; q = st.quantiles(dw, n=20)
    d['hit_draft_window_slack_D_minus_Bd'] = dict(mean=st.mean(dw), p5=q[0], p10=q[1], min=min(dw))
    d['hit_rank1_binds_fraction'] = st.mean(float(x['rank1_binds']) for x in hits)
    d['miss_rank1_binds_fraction'] = st.mean(float(x['rank1_binds']) for x in miss)
    d['miss_boundary_binds_ready_fraction'] = st.mean(float(x['boundary_binds_ready']) for x in miss)
    tot = sum(x['elapsed_ms'] for x in rows)
    d['time_share'] = dict(hits=sum(x['elapsed_ms'] for x in hits) / tot, misses=sum(x['elapsed_ms'] for x in miss) / tot)
    # critical-path attribution (pooled ms per interval)
    n = len(rows)
    cp = defaultdict(float)
    for x in rows:
        if x['D'] >= x['R'] + x['C'] + x['Bd']:
            cp['ready: D (rank 1 draft)'] += x['D']
        else:
            cp['ready: R (rank 0 restore)'] += x['R']; cp['ready: C (rank 0 corrected half)'] += x['C']; cp['ready: Bd (rank 0 boundary)'] += x['Bd']
        if x['rank1_binds']:
            cp['race: B (rank 1 half)'] += x['B']
        else:
            cp['race: A + offset (rank 0 speculative half)'] += x['A'] + x['spec_start_offset_ms']
        cp['G (control gaps)'] += x['G']
    d['critical_path_ms_per_interval'] = {k: v / n for k, v in cp.items()}
    d['critical_path_share'] = {k: v / tot for k, v in cp.items()}
    return d


if __name__ == '__main__':
    rows = load_view(P187 / 'repeat-1')
    assert len(rows) == 12 * 99
    rate = metric(rows)
    stored = json.loads(SUMMARY.read_text())[KEY]['median']
    print('packet187 WS128 replay', rate, 'stored', stored, 'diff', rate - stored)
    assert abs(rate - stored) < 1e-9
    with open(HERE / 'intervals-p187.csv', 'w', newline='') as f:
        cols = ['pid', 'cls', 'i', 'position', 'hit', 'elapsed_ms', 'D', 'B', 'A', 'spec_start_offset_ms', 'Bd', 'R', 'C', 'G', 'acc0', 'acc1']
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    out = dict(source=str(P187), rate=rate, stored=stored, p187=describe(rows))
    # packet186 bracket V3 views (rows 2: views 1 and 3) for cross-check
    br = STAGE / 'packet186-twocard-v3/v5/evidence/device-row2-bracket-u-v3-B-p186/run/views'
    if br.is_dir():
        for v in sorted(br.iterdir()):
            vr = load_view(v)
            if len(vr) == 12 * 99:
                out['p186_' + v.name] = dict(rate=metric(vr), **{k: describe(vr)[k] for k in ('hit', 'miss', 'hit_fraction', 'hit_rank1_binds_fraction', 'hit_rank0_race_slack_B_minus_A_plus_offset', 'hit_draft_window_slack_D_minus_Bd')})
    (HERE / 'replay-p187.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out['p187'], indent=1))
    for k, v in out.items():
        if k.startswith('p186_'):
            print(k, round(v['rate'], 4), 'hit B', round(v['hit']['B'], 3), 'A', round(v['hit']['A'], 3), 'D', round(v['hit']['D'], 3), 'Bd', round(v['hit']['Bd'], 3))
