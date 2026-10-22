"""Recompute packet186's V3 screen (rows 0-3, lane B, 2026-10-22) from retained tokens, clocks and proposals.

Evidence is read where packet186 retained it (never copied) and every file read is pinned by sha256 in
the result. The engine of every row must be packet187's device binary and the V3 views must have loaded
exactly packet187's active selection. Rates are recomputed: per prompt 99 intervals across token
timestamps 1-100, class-balanced median of class medians; exactness against the packet49 oracle.

Chain rule (coordinator ruling 2026-10-22, packet186 `s186_decision`): every view exact, identical draft
proposals and acceptance across the seven 128-token views, split-control and U drift <= 3 %, and the slower
V3 view >= 1.02 x the faster split-head control AND >= 1.02 x 58.798109 (59.974 tok/s).
"""
import hashlib, json, math, statistics
from pathlib import Path
O = Path(__file__).resolve().parent
ROOT = O.parents[3]
STAGE = ROOT / 'experiments/own-xpu-runtime/stage2'
EV = STAGE / 'packet186-twocard-v3/v5/evidence'
ROWS = ('device-row0-smoke-v3-B-p186', 'device-row1-control-production-B-p186', 'device-row2-bracket-u-v3-B-p186',
        'device-row3-control-production-B-p186')
ORACLE = STAGE / 'packet49-integrate/oracle/results'
RECORD = 58.798108759182306
CLASSES = {'incident-retrospective': 'operations', 'code-review': 'code', 'customer-email': 'prose', 'sql-debugging': 'code',
           'release-plan': 'operations', 'benchmark-analysis': 'analysis', 'architecture-tradeoff': 'analysis',
           'bug-report-synthesis': 'operations', 'technical-guide': 'documentation', 'risk-register': 'structured-writing',
           'performance-hypotheses': 'analysis', 'decision-memo': 'prose'}
BUNDLE8_SELECTION = '51b99015e6c1e18af01a14fadd18141be7191dd0a4a60091485dadd590edfd99'
U_SELECTION = '21ff4f4777f1'


def need(v, m):
    if not v:
        raise ValueError(m)


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def evaluate(split, u, v3, smoke_exact=True, exact=True, proposals=True, acceptance=True):
    need(len(split) == 2 and len(u) == 3 and len(v3) == 2, 'two split controls, three U and two V3 views required')
    need(all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in [*split, *u, *v3]), 'finite positive rates required')
    split_drift = 100 * (max(split) / min(split) - 1)
    u_drift = 100 * (max(u) / min(u) - 1)
    need(smoke_exact and exact and proposals and acceptance, 'every view exact with identical proposals/acceptance required')
    need(split_drift <= 3 and u_drift <= 3, 'control drift exceeds 3%')
    gain_split = 100 * (min(v3) / max(split) - 1)
    gain_all = 100 * (min(v3) / max([*split, *u]) - 1)
    need(gain_all >= 0.5, 'V3 must beat every control view by >= 0.5% (screen winner)')
    need(gain_split >= 2.0, 'V3 must beat every split-head control by >= 2% (chain rule)')
    need(min(v3) >= 1.02 * RECORD, 'V3 must reach 1.02 x 58.798109 = 59.974 tok/s (chain rule)')
    return dict(passed=True, chain_rule_met=True, screen_winner=True, split_control_rates=split, u_rates=u, v3_rates=v3,
                split_drift_percent=split_drift, u_drift_percent=u_drift, min_gain_vs_split_controls_percent=gain_split,
                min_gain_vs_every_control_percent=gain_all, slower_v3_rate=min(v3), record_bar=1.02 * RECORD,
                scope='screen admission only; the fresh chain WS128 must exceed 58.798109 and pass every exactness gate')


def verify(evidence=EV):
    evidence = Path(evidence)
    pins = {}

    def read(f):
        f = Path(f)
        pins[str(f.relative_to(ROOT))] = sha(f)
        return json.loads(f.read_text())
    active = json.loads((STAGE / 'packet187-record-bundle-v3/selection.json').read_text())
    active_sha = sha(STAGE / 'packet187-record-bundle-v3/selection.json')
    binding = json.loads((O / 'inputs/packet186-native.json').read_text())
    device = binding['binaries']['build/device/own-rt-iq3']['sha256']
    rows, views, proposals_all, counts_all = [], [], [], []
    for index, name in enumerate(ROWS):
        root = evidence / name
        window = read(root / 'window.json')
        need(window['passed'] is True and window['device_executed'] is True and window['device_complete'] is True and
             window['lease_released'] is True and not window['stop_reasons'] and not window['child_still_running'], name + ': incomplete row')
        need(read(root / 'run/device-isolation.json')['passed'] is True and read(root / 'run/teardown.json')['drained'] is True, name + ': isolation/teardown')
        identity = read(root / 'identity.json')
        need(identity['binary_sha256'] == device, name + ': row engine is not packet187\'s device binary')
        need(identity['lane'] == 'B' and identity['bracket']['row_index'] == index, name + ': row identity')
        summary = read(root / 'bracket-summary.json')
        need(summary['passed'] is True and summary['row_index'] == index and summary['all_13_exact'] is True, name + ': row failed')
        for i, view in enumerate(summary['views']):
            selection = identity['bracket']['views'][i]
            variant = view['variant']
            want = {'v3': active_sha, 'production': BUNDLE8_SELECTION}.get(variant)
            if variant == 'v3':
                need(read(Path(selection['selection'])) == active and selection['selection_sha256'] == active_sha, name + ': V3 view selection is not packet187\'s')
            elif variant == 'production':
                need(selection['selection_sha256'] == BUNDLE8_SELECTION, name + ': control is not bundle 8')
            else:
                need(variant == 'u' and selection['selection_sha256'].startswith(U_SELECTION), name + ': U view selection')
            dest = root / 'run/views' / f'{i:02d}-{view["choice"]}'
            row = read(dest / 'summary.json')
            need(row['arithmetic'] == 'iq3-p49-split32-v1' and row['kv_dtype'] == 'BF16' and row['cached_tokens'] == 0 and row['passed'] is True, name + ': arithmetic/cache')
            cap = 64 if summary['kind'] == 'smoke' else 128
            need(row['requested_max_new'] == cap and row['request_count'] == 12, name + ': request cap/count')
            need([r['prompt_id'] for r in row['requests']] == list(CLASSES), name + ': fixed complete suite required')
            grouped, counts, proposals = {}, [], {}
            incident = read(dest / 'incident64/receipt.json')
            for r, label in [(incident, 'incident64'), *[(x, x['prompt_id']) for x in row['requests']]]:
                prompt = r['prompt_id'] if label != 'incident64' else 'incident-retrospective'
                n = 64 if label == 'incident64' else cap
                oracle = read(ORACLE / prompt / 'result.json')['tokens']
                need(r['tokens'] == oracle[:n] and len(r['tokens']) == n and r['passed'] is True and r['exact_oracle'] is True and r['cached_tokens'] == 0, name + ': oracle tokens differ')
                trace = dest / label / 'rank1/draft-rows.jsonl'
                pins[str(trace.relative_to(ROOT))] = sha(trace)
                values = [[x[k] for k in ('draft_position', 'confirmed_token', 'guess', 'head')] for x in (json.loads(l) for l in trace.read_text().splitlines() if l.strip())]
                need(values and any(x[3] for x in values), name + ': proposal stream empty')
                proposals[label] = dict(rows=len(values), sha256=hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest())
                if label == 'incident64':
                    continue
                ts = r['token_timestamps']
                need(len(ts) == cap and all(math.isfinite(t) for t in ts) and all(b > a for a, b in zip(ts, ts[1:])), name + ': timestamps')
                need(r['prompt_class'] == CLASSES[prompt], name + ': class')
                last = min(cap, 100) - 1
                grouped.setdefault(r['prompt_class'], []).append(last / (ts[last] - ts[0]))
                counts.append(dict(prompt_id=prompt, hits=r['hits'], guesses=r['guesses']))
            rate = statistics.median(statistics.median(v) for v in grouped.values())
            need(abs(rate - view['rate']) < 1e-9 and counts == view['acceptance_counts'] and proposals == view['draft_proposals'], name + ': stored summary differs from retained evidence')
            for rank in (0, 1):
                boundary = read(dest / 'boundary' / f'boundary-rank{rank}.json')
                need(boundary['passed'] is True and boundary['total_reset'] is True and boundary['cached_tokens'] == 0 and boundary['weight_uploads_after_load'] == 0 and boundary['selection_sha256'] == selection['selection_sha256'], name + ': reset/selection')
            if cap == 128:
                views.append(dict(row=index, view=i, variant=variant, rate=rate))
                proposals_all.append(proposals)
                counts_all.append(counts)
        rows.append(dict(row=index, kind=summary['kind'], elapsed_seconds=window.get('elapsed_seconds'), views=[(v['variant'], v['rate']) for v in summary['views']]))
    split = [v['rate'] for v in views if v['variant'] == 'production']
    u = [v['rate'] for v in views if v['variant'] == 'u']
    v3 = [v['rate'] for v in views if v['variant'] == 'v3']
    result = evaluate(split, u, v3, proposals=all(x == proposals_all[0] for x in proposals_all), acceptance=all(x == counts_all[0] for x in counts_all))
    decision = read(evidence / ROWS[3] / 'bracket-summary.json')['s186_decision']
    need(decision['chain_rule_met'] is True and decision['screen_winner'] is True, 'packet186 row 3 s186_decision does not meet the chain rule')
    need(abs(decision['slower_v3_rate'] - result['slower_v3_rate']) < 1e-9, 'recomputed V3 rate differs from s186_decision')
    result.update(all_views_exact=True, exact_count=13 * 8, rows=rows, evidence=pins, bracket_lane='B', chain_lane='A', chain_cards=[0, 1],
                  s186_measured=decision.get('measured'), s186_outcome=decision['outcome'])
    return result


def summary(proof):
    """READY carries the recomputed screen and a digest of its evidence map; the map itself (169 packet186
    files, pinned where packet186 retained them) stays in evidence/bracket-gate.json, a gate receipt outside
    the lane-queue pin guard's metadata walk. verify_ready recomputes every file hash before launch."""
    row = {k: v for k, v in proof.items() if k != 'evidence'}
    row.update(evidence_files=len(proof['evidence']),
               evidence_map_sha256=hashlib.sha256(json.dumps(proof['evidence'], sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
               evidence_receipt='ops/packet187-orchestration/evidence/bracket-gate.json')
    return row


if __name__ == '__main__':
    proof = verify()
    receipt = dict(proof, device_executed=False, schema='packet187.bracket-gate.v1',
                   sources={str(Path(__file__).resolve().relative_to(ROOT)): sha(__file__)}, summary=summary(proof))
    (O / 'evidence/bracket-gate.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('bracket gate PASS: slower V3', round(proof['slower_v3_rate'], 4), 'tok/s,', round(proof['min_gain_vs_split_controls_percent'], 3),
          '% over split controls,', len(proof['evidence']), 'evidence files pinned')
