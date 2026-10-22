"""Recompute packet189's k3x screen (rows 0-1, lane B, lanequeue-B36, 2026-10-22 21:17-21:32 UTC) and packet188's
fresh V3 reference (row 1, lane B, lanequeue-B35) from retained tokens, clocks and proposals.

Evidence is read where packet189 and packet188 retained it (never copied) and every file read is pinned by
sha256 in the result. The engine of both packet189 rows must be packet190's device binary (87eec645...); the
k3x views must have loaded exactly packet190's active selection (c5443bbf...); the in-load V3 views the v3k
selection (92f5fcf7..., the k3 storage executed as V3); packet188 row 1 the packet187 record selection
(923639a9...) on packet188's engine (d7765245..., pinned). Rates are recomputed: per prompt 99 intervals
across token timestamps 1-100, class-balanced median of class medians; exactness against the packet49 oracle.

Chain rule (coordinator ruling 2026-10-22, packet189 `s189_decision`): every view exact (smoke 12 x 64 +
incident64; five 128-token views), identical draft proposals and acceptance across the five 128-token views
and the fresh V3 row, V3 drift <= 3 % over the three in-load V3 views plus the fresh row, and the slower k3x
view >= 1.02 x EVERY V3 view AND >= 1.02 x 60.659520 = 61.87271031814733 tok/s.
"""
import hashlib, json, math, statistics
from pathlib import Path
O = Path(__file__).resolve().parent
ROOT = O.parents[3]
STAGE = ROOT / 'experiments/own-xpu-runtime/stage2'
EV = STAGE / 'packet189-twocard-k3x/v5/evidence'
ROWS = ('device-row0-smoke-k3x-B-p189', 'device-row1-bracket-v3k-k3x-B-p189')
FRESH = STAGE / 'packet188-twocard-k3-composite/v5/evidence/device-row1-control-v3-B-p188'
FRESH_ENGINE = 'd776524532f110528dea5f67f13771feb71945cf35f44247f77ef9118539eb45'
FRESH_SUMMARY_SHA256 = '4ff1ec14a842c5ec652c9cdc0527658929a84edd2baaefecb9de753f12db0aae'
ORACLE = STAGE / 'packet49-integrate/oracle/results'
RECORD = 60.65951991975228
RECORD_ID = 'cmvjvabyv040jrf01dricuz8s'
CLASSES = {'incident-retrospective': 'operations', 'code-review': 'code', 'customer-email': 'prose', 'sql-debugging': 'code',
           'release-plan': 'operations', 'benchmark-analysis': 'analysis', 'architecture-tradeoff': 'analysis',
           'bug-report-synthesis': 'operations', 'technical-guide': 'documentation', 'risk-register': 'structured-writing',
           'performance-hypotheses': 'analysis', 'decision-memo': 'prose'}
V3_SELECTION = '923639a9c03fe8b58a4647ba5c4135c1f1360aaa20a1192b49c35f6fd282912e'   # packet187 record selection (0-25 storage)
V3K_SELECTION = '92f5fcf7373a47c40ca156aa5bd86a3f9e973744bc45c51e8735005ef9712ae3'  # k3 storage executed as V3


def need(v, m):
    if not v:
        raise ValueError(m)


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def evaluate(v3, k3x, smoke_exact=True, exact=True, proposals=True, acceptance=True, fresh_proposals=True):
    """v3: [fresh packet188 row-1 rate, three in-load V3 rates]; k3x: the two k3x view rates."""
    need(len(v3) == 4 and len(k3x) == 2, 'one fresh V3 reference, three in-load V3 views and two k3x views required')
    need(all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in [*v3, *k3x]), 'finite positive rates required')
    drift = 100 * (max(v3) / min(v3) - 1)
    need(smoke_exact and exact and proposals and acceptance and fresh_proposals, 'every view exact with identical proposals/acceptance required')
    need(drift <= 3, 'V3 drift exceeds 3%')
    gain = 100 * (min(k3x) / max(v3) - 1)
    need(gain >= 0.5, 'k3x must beat every V3 view by >= 0.5% (screen winner)')
    need(gain >= 2.0, 'k3x must beat every V3 view by >= 2% (chain rule)')
    need(min(k3x) >= 1.02 * RECORD, 'k3x must reach 1.02 x 60.659520 = 61.873 tok/s (chain rule)')
    return dict(passed=True, chain_rule_met=True, screen_winner=True, v3_rates=v3, fresh_v3_rate=v3[0], inload_v3_rates=v3[1:], k3x_rates=k3x,
                v3_drift_percent=drift, min_gain_vs_every_v3_view_percent=gain, slower_k3x_rate=min(k3x), faster_v3_rate=max(v3),
                record=RECORD, record_id=RECORD_ID, record_bar=1.02 * RECORD,
                scope='screen admission only; the fresh chain WS128 must exceed 60.659520 and pass every exactness gate')


def view_evidence(read, pins, root, index, view, selection, cap, require_prompt_ids=True):
    """Recompute one view's class-balanced rate, exactness, proposals and acceptance from retained bytes."""
    dest = root / 'run/views' / f'{index:02d}-{view["choice"]}'
    row = read(dest / 'summary.json')
    need(row['arithmetic'] == 'iq3-p49-split32-v1' and row['kv_dtype'] == 'BF16' and row['cached_tokens'] == 0 and row['passed'] is True, 'arithmetic/cache')
    need(row['requested_max_new'] == cap and row['request_count'] == 12, 'request cap/count')
    need([r['prompt_id'] for r in row['requests']] == list(CLASSES), 'fixed complete suite required')
    grouped, counts, proposals = {}, [], {}
    incident = read(dest / 'incident64/receipt.json')
    for r, label in [(incident, 'incident64'), *[(x, x['prompt_id']) for x in row['requests']]]:
        prompt = r['prompt_id'] if label != 'incident64' else 'incident-retrospective'
        n = 64 if label == 'incident64' else cap
        oracle = read(ORACLE / prompt / 'result.json')['tokens']
        need(r['tokens'] == oracle[:n] and len(r['tokens']) == n and r['passed'] is True and r['exact_oracle'] is True and r['cached_tokens'] == 0, 'oracle tokens differ: ' + label)
        trace = dest / label / 'rank1/draft-rows.jsonl'
        pins[str(trace.relative_to(ROOT))] = sha(trace)
        values = [[x[k] for k in ('draft_position', 'confirmed_token', 'guess', 'head')] for x in (json.loads(l) for l in trace.read_text().splitlines() if l.strip())]
        need(values and any(x[3] for x in values), 'proposal stream empty: ' + label)
        proposals[label] = dict(rows=len(values), sha256=hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest())
        if label == 'incident64':
            continue
        ts = r['token_timestamps']
        need(len(ts) == cap and all(math.isfinite(t) for t in ts) and all(b > a for a, b in zip(ts, ts[1:])), 'timestamps: ' + label)
        need(r['prompt_class'] == CLASSES[prompt], 'class: ' + label)
        last = min(cap, 100) - 1
        grouped.setdefault(r['prompt_class'], []).append(last / (ts[last] - ts[0]))
        counts.append(dict(prompt_id=prompt, hits=r['hits'], guesses=r['guesses']))
    rate = statistics.median(statistics.median(v) for v in grouped.values())
    need(abs(rate - view['rate']) < 1e-9 and counts == view['acceptance_counts'] and proposals == view['draft_proposals'], 'stored summary differs from retained evidence')
    need(view['all_13_exact'] is True and view['exact_count'] == 13, 'view not 13/13 exact')
    for rank in (0, 1):
        boundary = read(dest / 'boundary' / f'boundary-rank{rank}.json')
        need(boundary['passed'] is True and boundary['total_reset'] is True and boundary['cached_tokens'] == 0 and boundary['weight_uploads_after_load'] == 0 and boundary['selection_sha256'] == selection['selection_sha256'], 'reset/selection')
    return rate, proposals, counts


def row_identity(read, root, name, index, lane, engine):
    window = read(root / 'window.json')
    need(window['passed'] is True and window['device_executed'] is True and window['device_complete'] is True and
         window['lease_released'] is True and not window['stop_reasons'] and not window['child_still_running'], name + ': incomplete row')
    need(read(root / 'run/device-isolation.json')['passed'] is True and read(root / 'run/teardown.json')['drained'] is True, name + ': isolation/teardown')
    identity = read(root / 'identity.json')
    need(identity['binary_sha256'] == engine, name + ': row engine differs from the pinned engine')
    need(identity['lane'] == lane and identity['bracket']['row_index'] == index, name + ': row identity')
    summary = read(root / 'bracket-summary.json')
    need(summary['passed'] is True and summary['row_index'] == index and summary['all_13_exact'] is True, name + ': row failed')
    return window, identity, summary


def verify(evidence=EV, fresh_root=FRESH):
    evidence, fresh_root = Path(evidence), Path(fresh_root)
    pins = {}

    def read(f):
        f = Path(f)
        pins[str(f.relative_to(ROOT))] = sha(f)
        return json.loads(f.read_text())
    active = json.loads((STAGE / 'packet190-record-bundle-k3x/selection.json').read_text())
    active_sha = sha(STAGE / 'packet190-record-bundle-k3x/selection.json')
    binding = json.loads((O / 'inputs/packet189-native.json').read_text())
    device = binding['binaries']['build/device/own-rt-iq3']['sha256']
    rows, views, proposals_all, counts_all = [], [], [], []
    # packet189 row 0: k3x smoke (12 x 64 + incident64); row 1: one load V3/k3x/V3/k3x/V3 (12 x 128 + incident64 each).
    for index, name in enumerate(ROWS):
        root = evidence / name
        window, identity, summary = row_identity(read, root, name, index, 'B', device)
        kind = summary['kind']
        need(kind == ('smoke' if index == 0 else 'bracket'), name + ': row kind')
        cap = 64 if kind == 'smoke' else 128
        want_variants = ['k3x'] if kind == 'smoke' else ['v3k', 'k3x', 'v3k', 'k3x', 'v3k']
        need([v['variant'] for v in summary['views']] == want_variants, name + ': view order')
        if kind == 'smoke':
            need(summary.get('timing_data_proof', {}).get('passed') is True, name + ': first-request data proof')
        for i, view in enumerate(summary['views']):
            selection = identity['bracket']['views'][i]
            if view['variant'] == 'k3x':
                need(read(Path(selection['selection'])) == active and selection['selection_sha256'] == active_sha, name + ': k3x view selection is not packet190\'s')
            else:
                need(selection['selection_sha256'] == V3K_SELECTION and read(Path(selection['selection']))['choices']['boundary'] == 'rank0', name + ': V3 view selection is not the k3-storage V3 (v3k)')
            rate, proposals, counts = view_evidence(read, pins, root, i, view, selection, cap)
            if cap == 128:
                views.append(dict(row=index, view=i, variant=view['variant'], rate=rate))
                proposals_all.append(proposals)
                counts_all.append(counts)
        rows.append(dict(row=index, packet='packet189-twocard-k3x', kind=kind, elapsed_seconds=window.get('elapsed_seconds'), views=[(v['variant'], v['rate']) for v in summary['views']]))
    # packet188 row 1: the packet187 record selection loaded fresh on lane B (the fresh V3 reference s189 pins by sha256).
    need(sha(fresh_root / 'bracket-summary.json') == FRESH_SUMMARY_SHA256, 'packet188 fresh V3 summary changed where packet188 retained it')
    window, identity, summary = row_identity(read, fresh_root, 'packet188-row1', 1, 'B', FRESH_ENGINE)
    need(summary['kind'] == 'view' and len(summary['views']) == 1 and summary['views'][0]['variant'] == 'v3', 'packet188 row 1 is not a single fresh V3 view')
    selection = identity['bracket']['views'][0]
    need(selection['selection_sha256'] == V3_SELECTION and sha(Path(selection['selection'])) == V3_SELECTION, 'packet188 row 1 is not the packet187 record selection')
    fresh_rate, fresh_proposals, fresh_counts = view_evidence(read, pins, fresh_root, 0, summary['views'][0], selection, 128)
    rows.append(dict(row=1, packet='packet188-twocard-k3-composite', kind='view', elapsed_seconds=window.get('elapsed_seconds'), views=[('v3', fresh_rate)]))
    inload = [v['rate'] for v in views if v['variant'] == 'v3k']
    k3x = [v['rate'] for v in views if v['variant'] == 'k3x']
    result = evaluate([fresh_rate, *inload], k3x,
                      proposals=all(x == proposals_all[0] for x in proposals_all), acceptance=all(x == counts_all[0] for x in counts_all),
                      fresh_proposals=(fresh_proposals == proposals_all[0] and fresh_counts == counts_all[0]))
    decision = read(evidence / ROWS[1] / 'bracket-summary.json')['s189_decision']
    need(decision['chain_rule_met'] is True and decision['screen_winner'] is True and not decision['kill_rules']['fired'], 'packet189 row 1 s189_decision does not meet the chain rule')
    need(abs(decision['slower_k3x_rate'] - result['slower_k3x_rate']) < 1e-9 and abs(decision['fresh_v3_rate'] - fresh_rate) < 1e-9, 'recomputed rates differ from s189_decision')
    need(decision['fresh_v3_source']['sha256'] == FRESH_SUMMARY_SHA256 and abs(decision['thresholds']['record'] - RECORD) < 1e-12, 's189 pins differ')
    result.update(all_views_exact=True, exact_count=13 * 7, rows=rows, evidence=pins, bracket_lane='B', chain_lane='A', chain_cards=[0, 1],
                  s189_kill_rules={k: decision['kill_rules'][k] for k in ('thresholds', 'handoff_export_ms', 'boundary_total_ms', 'k3_hit_saving_ms', 'boundary_over_draft_wall_fraction', 'trims_A_saving_ms', 'fired')},
                  s189_outcome=decision['outcome'], fresh_v3_source=decision['fresh_v3_source'])
    return result


def summary(proof):
    """READY carries the recomputed screen and a digest of its evidence map; the map itself (packet189/188
    files, pinned where they were retained) stays in evidence/bracket-gate.json, a gate receipt outside the
    lane-queue pin guard's metadata walk. verify_ready recomputes every file hash before launch."""
    row = {k: v for k, v in proof.items() if k != 'evidence'}
    row.update(evidence_files=len(proof['evidence']),
               evidence_map_sha256=hashlib.sha256(json.dumps(proof['evidence'], sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
               evidence_receipt='ops/packet190-orchestration/evidence/bracket-gate.json')
    return row


if __name__ == '__main__':
    proof = verify()
    receipt = dict(proof, device_executed=False, schema='packet190.bracket-gate.v1',
                   sources={str(Path(__file__).resolve().relative_to(ROOT)): sha(__file__)}, summary=summary(proof))
    (O / 'evidence/bracket-gate.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('bracket gate PASS: slower k3x', round(proof['slower_k3x_rate'], 4), 'tok/s,', round(proof['min_gain_vs_every_v3_view_percent'], 3),
          '% over every V3 view (fresh', round(proof['fresh_v3_rate'], 4), '), drift', round(proof['v3_drift_percent'], 3), '%,', len(proof['evidence']), 'evidence files pinned')
