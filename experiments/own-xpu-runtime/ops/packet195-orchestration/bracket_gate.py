"""Recompute packet194's exp-diet screen (rows 0-1, lane B, lanequeue-B40, 2026-10-23 05:56-06:11 UTC) from retained
tokens, clocks and proposals.

Evidence is read where packet194 retained it (never copied) and every file read is pinned by sha256 in the result.
The engine of both packet194 rows must be packet195's device binary (b8482321...); the k3x-diet views must have
loaded exactly packet195's active selection (eb417ec9..., 20 keys); the in-load control views the 20-key k3x
selection (c20504b7..., expert_gateup=production = the record path, packet194 full-shape gate). Rates are
recomputed: per prompt 99 intervals across token timestamps 1-100, class-balanced median of class medians;
exactness against the packet49 oracle.

Screen rule (coordinator ruling 2026-10-23, packet194 `s194_decision`): every view exact (smoke 12 x 64 + incident64;
five 128-token views), identical draft proposals and acceptance across the five 128-token views, k3x drift <= 0.5 %
over the three in-load k3x views, the per-layer gate/up saving >= 5 us on both ranks (host-side scopes), and the
slower k3x-diet view >= 1.005 x EVERY k3x view. Chain rule: the same AND >= 1.02 x every k3x view AND
>= 1.02 x 62.345281904743764 = 63.59218754283864 tok/s. The chain rule is NOT met (+1.96 %, 0.04 points short);
the coordinator's ruling admits the chain under the idle-lane provision of the chain policy, which policy195.json
records as `coordinator_idle_lane_exception_authorized`. This admits a chain, never a record: the fresh chain's
WS128 must beat 62.345282 and pass every exactness gate.
"""
import hashlib, json, math, statistics
from pathlib import Path
O = Path(__file__).resolve().parent
ROOT = O.parents[3]
STAGE = ROOT / 'experiments/own-xpu-runtime/stage2'
EV = STAGE / 'packet194-expert-diet-engine/v5/evidence'
ROWS = ('device-row0-smoke-k3x-diet-B-p194', 'device-row1-bracket-k3x-diet-B-p194')
ORACLE = STAGE / 'packet49-integrate/oracle/results'
RECORD = 62.345281904743764
RECORD_HARD_FLOOR = 62.345282
RECORD_ID = 'cmvk51wfn001gng01fpbfy89q'
SCREEN_BAR = 0.5
CHAIN_BAR = 2.0
DRIFT_MAX = 0.5
SAVING_MIN_US = 5.0
CLASSES = {'incident-retrospective': 'operations', 'code-review': 'code', 'customer-email': 'prose', 'sql-debugging': 'code',
           'release-plan': 'operations', 'benchmark-analysis': 'analysis', 'architecture-tradeoff': 'analysis',
           'bug-report-synthesis': 'operations', 'technical-guide': 'documentation', 'risk-register': 'structured-writing',
           'performance-hypotheses': 'analysis', 'decision-memo': 'prose'}
CONTROL_SELECTION = 'c20504b7c6de20af779954a29fa6f5471bf60bfe0aead960763c940cca4a22c0'  # packet194 k3x (20 keys, expert_gateup production)
RECORD_SELECTION = 'c5443bbfbc88b39fd562956a55ce05667de0781f640fd0cd522a1e5800f392bb'   # packet189/190 k3x (19 keys): same engine path
RULING = ("packet194 k3x-diet is a screen winner on 2026-10-23 (lane B, lanequeue-B40, 05:56–06:11 UTC): +1.96 % over every k3x view, "
          "every view exact; the +2 % chain bar is missed by 0.04 points, and the lanes are idle, which the chain policy allows. Derive the "
          "record bundle from packet190 with the `k3x-diet` selection and packet194's engine; prepare a fresh eleven-window chain on cards 0+1; "
          "its WS128 must beat 62.345282 (cmvk51wfn001gng01fpbfy89q) and pass every exactness gate.")


def need(v, m):
    if not v:
        raise ValueError(m)


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def evaluate(k3x, diet, saving_us=None, *, smoke_exact=True, exact=True, proposals=True, acceptance=True, idle_lane_exception=True):
    """k3x: the three in-load control rates; diet: the two k3x-diet view rates; saving_us: min per-layer gate/up saving over both ranks."""
    need(len(k3x) == 3 and len(diet) == 2, 'three in-load k3x views and two k3x-diet views required')
    need(all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in [*k3x, *diet]), 'finite positive rates required')
    need(saving_us is not None and type(saving_us) in (int, float) and math.isfinite(saving_us), 'a measured per-layer gate/up saving is required')
    drift = 100 * (max(k3x) / min(k3x) - 1)
    need(smoke_exact and exact and proposals and acceptance, 'every view exact with identical proposals/acceptance required')
    need(drift <= DRIFT_MAX, 'k3x drift exceeds 0.5%')
    need(saving_us >= SAVING_MIN_US, 'gate/up saving below 5 us per layer on a rank')
    gain = 100 * (min(diet) / max(k3x) - 1)
    need(gain >= SCREEN_BAR, 'k3x-diet must beat every k3x view by >= 0.5% (screen winner)')
    chain = gain >= CHAIN_BAR and min(diet) >= 1.02 * RECORD
    need(chain or idle_lane_exception, 'below the +2% chain rule without the coordinator idle-lane exception')
    return dict(passed=True, screen_winner=True, chain_rule_met=chain, chain_rule_shortfall_points=max(0.0, CHAIN_BAR - gain),
                idle_lane_exception=dict(authorized=bool(idle_lane_exception), required=not chain, ruling=RULING),
                k3x_rates=k3x, diet_rates=diet, k3x_drift_percent=drift, min_gain_vs_every_k3x_view_percent=gain,
                slower_diet_rate=min(diet), faster_k3x_rate=max(k3x), gateup_saving_min_both_ranks_us_per_layer=saving_us,
                record=RECORD, record_hard_floor=RECORD_HARD_FLOOR, record_id=RECORD_ID, record_bar=1.02 * RECORD,
                scope='screen admission only; the fresh chain WS128 must exceed 62.345282 and pass every exactness gate')


def view_evidence(read, pins, root, index, view, selection, cap):
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


def verify(evidence=EV):
    evidence = Path(evidence)
    pins = {}

    def read(f):
        f = Path(f)
        pins[str(f.relative_to(ROOT))] = sha(f)
        return json.loads(f.read_text())
    active = json.loads((STAGE / 'packet195-record-bundle-diet/selection.json').read_text())
    active_sha = sha(STAGE / 'packet195-record-bundle-diet/selection.json')
    need(len(active['choices']) == 20 and active['choices']['expert_gateup'] == 'diet', 'active selection is not the 20-key k3x-diet')
    policy = json.loads((O / 'policy195.json').read_text())
    binding = json.loads((O / 'inputs/packet194-native.json').read_text())
    device = binding['binaries']['build/device/own-rt-iq3']['sha256']
    rows, views, proposals_all, counts_all = [], [], [], []
    # packet194 row 0: k3x-diet smoke (12 x 64 + incident64); row 1: one load k3x/k3x-diet/k3x/k3x-diet/k3x (12 x 128 + incident64 each).
    for index, name in enumerate(ROWS):
        root = evidence / name
        window, identity, summary = row_identity(read, root, name, index, 'B', device)
        kind = summary['kind']
        need(kind == ('smoke' if index == 0 else 'bracket'), name + ': row kind')
        cap = 64 if kind == 'smoke' else 128
        want_variants = ['k3x-diet'] if kind == 'smoke' else ['k3x', 'k3x-diet', 'k3x', 'k3x-diet', 'k3x']
        need([v['variant'] for v in summary['views']] == want_variants, name + ': view order')
        if kind == 'smoke':
            need(summary.get('timing_data_proof', {}).get('passed') is True, name + ': first-request data proof')
        for i, view in enumerate(summary['views']):
            selection = identity['bracket']['views'][i]
            loaded = read(Path(selection['selection']))
            if view['variant'] == 'k3x-diet':
                need(loaded == active and selection['selection_sha256'] == active_sha, name + ': k3x-diet view selection is not packet195\'s')
            else:
                need(selection['selection_sha256'] == CONTROL_SELECTION and loaded['choices']['expert_gateup'] == 'production', name + ': control view selection is not the 20-key k3x (production gate/up)')
                need({k: v for k, v in loaded['choices'].items() if k != 'expert_gateup'} == {k: v for k, v in active['choices'].items() if k != 'expert_gateup'} and loaded['draft'] == active['draft'],
                     name + ': control and candidate differ beyond expert_gateup')
            rate, proposals, counts = view_evidence(read, pins, root, i, view, selection, cap)
            if cap == 128:
                views.append(dict(row=index, view=i, variant=view['variant'], rate=rate))
                proposals_all.append(proposals)
                counts_all.append(counts)
        rows.append(dict(row=index, packet='packet194-expert-diet-engine', kind=kind, elapsed_seconds=window.get('elapsed_seconds'), views=[(v['variant'], v['rate']) for v in summary['views']]))
    k3x = [v['rate'] for v in views if v['variant'] == 'k3x']
    diet = [v['rate'] for v in views if v['variant'] == 'k3x-diet']
    decision = read(evidence / ROWS[1] / 'bracket-summary.json')['s194_decision']
    saving = decision['gateup_saving']
    need(saving['min_both_ranks_us_per_layer'] == min(saving['rank0_A_us_per_layer'], saving['rank1_B_us_per_layer']), 's194 saving minimum differs from its rank terms')
    result = evaluate(k3x, diet, saving['min_both_ranks_us_per_layer'],
                      proposals=all(x == proposals_all[0] for x in proposals_all), acceptance=all(x == counts_all[0] for x in counts_all),
                      idle_lane_exception=policy['coordinator_idle_lane_exception_authorized'] is True)
    need(decision['screen_winner'] is True and decision['chain_rule_met'] is False and not decision['kill_rules']['fired'], 'packet194 row 1 s194_decision is not a screen winner below the chain bar')
    need(decision['every_view_exact'] is True and decision['draft_proposals_identical'] is True and decision['acceptance_identical'] is True, 's194 exactness/proposal flags')
    need(abs(decision['slower_diet_rate'] - result['slower_diet_rate']) < 1e-9 and abs(decision['faster_k3x_rate'] - result['faster_k3x_rate']) < 1e-9
         and abs(decision['min_gain_vs_every_k3x_view_percent'] - result['min_gain_vs_every_k3x_view_percent']) < 1e-9
         and abs(decision['k3x_drift_percent'] - result['k3x_drift_percent']) < 1e-9, 'recomputed rates differ from s194_decision')
    need(abs(decision['thresholds']['record'] - RECORD) < 1e-12 and abs(decision['thresholds']['record_bar'] - 1.02 * RECORD) < 1e-9, 's194 record pins differ')
    need(result['chain_rule_met'] is False and result['chain_rule_shortfall_points'] < 0.1, 'this packet exists for the 0.04-point idle-lane case; a chain-rule win would be derived the same way')
    result.update(all_views_exact=True, exact_count=13 * 6, rows=rows, evidence=pins, bracket_lane='B', chain_lane='A', chain_cards=[0, 1],
                  s194_kill_rules=dict(thresholds=decision['kill_rules']['thresholds'], fired=decision['kill_rules']['fired']),
                  s194_gateup_saving={k: saving[k] for k in ('layers', 'clock', 'rank0_A_us_per_layer', 'rank0_layer_body_us_per_layer', 'rank1_B_us_per_layer', 'boundary_body_us_per_layer',
                                                             'miss_C_us_per_layer', 'min_both_ranks_us_per_layer', 'priced_gain_percent_from_saving')},
                  s194_outcome=decision['outcome'], control_selection_sha256=CONTROL_SELECTION, record_selection_sha256=RECORD_SELECTION, active_selection_sha256=active_sha)
    return result


def summary(proof):
    """READY carries the recomputed screen and a digest of its evidence map; the map itself (packet194 files, pinned
    where they were retained) stays in evidence/bracket-gate.json, a gate receipt outside the lane-queue pin guard's
    metadata walk. verify_ready recomputes every file hash before launch."""
    row = {k: v for k, v in proof.items() if k != 'evidence'}
    row.update(evidence_files=len(proof['evidence']),
               evidence_map_sha256=hashlib.sha256(json.dumps(proof['evidence'], sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
               evidence_receipt='ops/packet195-orchestration/evidence/bracket-gate.json')
    return row


if __name__ == '__main__':
    proof = verify()
    receipt = dict(proof, device_executed=False, schema='packet195.bracket-gate.v1',
                   sources={str(Path(__file__).resolve().relative_to(ROOT)): sha(__file__)}, summary=summary(proof))
    (O / 'evidence/bracket-gate.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('bracket gate PASS: slower k3x-diet', round(proof['slower_diet_rate'], 4), 'tok/s,', round(proof['min_gain_vs_every_k3x_view_percent'], 3),
          '% over every k3x view (fastest', round(proof['faster_k3x_rate'], 4), '), drift', round(proof['k3x_drift_percent'], 3), '%, saving',
          round(proof['gateup_saving_min_both_ranks_us_per_layer'], 2), 'us/layer; chain rule met:', proof['chain_rule_met'], '(idle-lane exception authorized);',
          len(proof['evidence']), 'evidence files pinned')
