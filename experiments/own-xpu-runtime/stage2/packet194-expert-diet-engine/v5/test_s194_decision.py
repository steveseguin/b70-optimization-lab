"""s194_decision on REAL device data, read where packet189/packet190 retained it (never copied; the analysis gate pins every
file it reads by sha256).

* packet189 row 1 (2026-10-22, lane B, lanequeue-B36): the one-load V3/k3x/V3/k3x/V3 bracket whose k3x views (01/03) ARE the
  record line's engine path (62.242 / 62.225 tok/s). Null test: the k3x views as both control and candidate must say
  NOT A SCREEN WINNER with the per-layer-saving kill rule fired at ~0 us; the v3k views as the candidate (the slower
  record-line V3) must not be a winner either. Scalings of the real k3x views with an injected per-layer saving cover every
  branch (chain, winner-only, below +0.5 %, drift, inexact, proposals, saving below 5 us, unmeasured saving, missing smoke).
* packet190 (2026-10-22, the record chain, WS128): view_stats on its 12 real request streams reproduces the record metric
  (RECORD equals its stored class-balanced median) and the k3x hit/miss/boundary picture.
"""
import copy, json, unittest
from pathlib import Path
import s194_decision as s

P = Path(__file__).resolve().parent
STAGE = P.parents[1]
P189 = STAGE / 'packet189-twocard-k3x/v5/evidence'
BRACKET189 = P189 / 'device-row1-bracket-v3k-k3x-B-p189'
SMOKE189 = P189 / 'device-row0-smoke-k3x-B-p189/bracket-summary.json'
P190 = STAGE / 'packet190-record-bundle-k3x/build/device-cards01-p190-a/WS128/run'
P190_SUMMARY = P190 / 'summary.json'
PROMPTS = ('incident-retrospective', 'code-review', 'customer-email', 'sql-debugging', 'release-plan', 'benchmark-analysis',
           'architecture-tradeoff', 'bug-report-synthesis', 'technical-guide', 'risk-register', 'performance-hypotheses', 'decision-memo')
_STATS = {}
SMOKE = dict(kind='smoke', passed=True, exact=True)


def read(path):
    return json.loads(Path(path).read_text())


def stats(index):
    """view_stats of packet189 row-1 view `index` (cached): 00/02/04 are the V3 views (v3k), 01/03 the k3x views."""
    if index not in _STATS:
        choice = 'candidate' if index % 2 else 'control'
        _STATS[index] = s.view_stats(BRACKET189 / 'run/views' / f'{index:02d}-{choice}', list(PROMPTS), 'k3x' if index % 2 else 'v3k')
    return _STATS[index]


def real_views():
    rec = s.bracket_record(read(BRACKET189 / 'bracket-summary.json'))
    for i, v in enumerate(rec['views']):
        v['interval_stats'] = stats(i)
    return rec['views']


def null_bracket():
    """packet189's two real k3x views as BOTH control and candidate (controls 01/03/01, candidates 03/01)."""
    v = real_views()
    order = [v[1], v[3], v[3], v[1], v[1]]
    out = []
    for i, x in enumerate(order):
        y = copy.deepcopy(x); y['variant'] = s.CONTROL if i % 2 == 0 else s.CANDIDATE; out.append(y)
    return dict(kind='bracket', views=out)


def inject_saving(view, us_per_layer):
    """Shift the candidate's hit A/B (and layer_body/boundary_body scopes) by a per-layer saving, in place."""
    st_ = view['interval_stats']
    st_['hit']['A'] -= us_per_layer * s.LAYERS['rank0_half'] / 1000.0
    st_['hit']['B'] -= us_per_layer * s.LAYERS['rank1_half'] / 1000.0
    st_['envelope']['scopes_ms']['layer_body'] -= us_per_layer * s.LAYERS['rank0_half'] / 1000.0
    st_['envelope']['scopes_ms']['boundary_body'] -= us_per_layer * s.LAYERS['boundary'] / 1000.0
    return view


class Packet189Real(unittest.TestCase):
    def setUp(self):
        self.null = null_bracket()

    def test_smoke_record_from_real_smoke(self):
        r = s.smoke_record(read(SMOKE189))
        self.assertTrue(r['passed'] and r['exact'])

    def test_null_k3x_as_candidate_is_not_a_winner_and_the_saving_rule_fires(self):
        d = s.decide(SMOKE, self.null)
        self.assertFalse(d['screen_winner'] or d['chain_rule_met']); self.assertIn('NOT A SCREEN WINNER', d['outcome'])
        self.assertTrue(d['every_view_exact'] and d['draft_proposals_identical'] and d['acceptance_identical'])
        self.assertEqual(d['k3x_rates'], [62.24199434282818, 62.22542821257332, 62.24199434282818])
        self.assertEqual(d['diet_rates'], [62.22542821257332, 62.24199434282818])
        self.assertAlmostEqual(d['k3x_drift_percent'], 100 * (62.24199434282818 / 62.22542821257332 - 1), places=9)
        self.assertAlmostEqual(d['min_gain_vs_every_k3x_view_percent'], 100 * (62.22542821257332 / 62.24199434282818 - 1), places=9)
        self.assertLess(d['k3x_drift_percent'], 0.03)
        g = d['gateup_saving']
        self.assertLess(abs(g['rank0_A_us_per_layer']), 1.0); self.assertLess(abs(g['rank1_B_us_per_layer']), 1.0)
        self.assertEqual(d['kill_rules']['fired'], ['gateup_saving_us_per_layer'])
        self.assertTrue(11.8 < g['k3x_hit_A_ms'] < 12.1 and 11.8 < g['k3x_hit_B_ms'] < 12.1 and 1.4 < g['k3x_hit_Bd_ms'] < 1.6)
        self.assertTrue(13.4 < g['k3x_hit_elapsed_ms'] < 13.7 and 25.3 < g['k3x_miss_elapsed_ms'] < 25.8)

    def test_record_line_v3_views_as_candidate_are_not_a_winner(self):
        v = real_views()
        b = dict(kind='bracket', views=[dict(copy.deepcopy(x), variant=s.CONTROL if i % 2 == 0 else s.CANDIDATE) for i, x in enumerate([v[1], v[0], v[3], v[2], v[1]])])
        d = s.decide(SMOKE, b)
        self.assertFalse(d['screen_winner']); self.assertLess(d['min_gain_vs_every_k3x_view_percent'], -2.5)
        self.assertLess(d['gateup_saving']['rank0_A_us_per_layer'], -4.0)  # V3 pays the trims and layer 26 on rank 1: a negative "saving"
        self.assertIn('gateup_saving_us_per_layer', d['kill_rules']['fired'])

    def scaled(self, factor, saving_us=12.0):
        b = copy.deepcopy(self.null); top = max(v['rate'] for v in b['views'] if v['variant'] == s.CONTROL)
        for v in b['views']:
            if v['variant'] == s.CANDIDATE:
                v['rate'] = top * factor; inject_saving(v, saving_us)
        return b

    def test_two_and_a_half_percent_with_a_12us_saving_meets_the_chain_rule(self):
        d = s.decide(SMOKE, self.scaled(1.025))
        self.assertTrue(d['screen_winner'] and d['chain_rule_met']); self.assertGreaterEqual(d['slower_diet_rate'], s.RECORD_BAR)
        self.assertEqual(d['kill_rules']['fired'], [])
        g = d['gateup_saving'];self.assertTrue(11.0 < g['min_both_ranks_us_per_layer'] < 13.0)  # 12 us injected on top of the real view jitter
        self.assertAlmostEqual(g['priced_gain_percent_from_saving'], 132.0 * (g['rank0_A_us_per_layer'] + g['rank1_B_us_per_layer']) / 2000.0, places=9)  # 1.32 % per 0.01 ms

    def test_two_percent_over_k3x_above_the_record_bar_meets_the_chain_rule(self):
        d = s.decide(SMOKE, self.scaled(1.0215))  # 62.242 x 1.0215 = 63.580 < 63.592: below the record bar -> winner only
        self.assertTrue(d['screen_winner']); self.assertFalse(d['chain_rule_met'])
        d = s.decide(SMOKE, self.scaled(1.0220))  # 63.611 >= 63.592
        self.assertTrue(d['chain_rule_met'])

    def test_below_two_percent_is_winner_only(self):
        d = s.decide(SMOKE, self.scaled(1.015))
        self.assertTrue(d['screen_winner']); self.assertFalse(d['chain_rule_met'])

    def test_below_half_percent_is_not_a_winner(self):
        self.assertFalse(s.decide(SMOKE, self.scaled(1.004))['screen_winner'])

    def test_saving_rule_blocks_a_fast_but_unexplained_gain(self):
        d = s.decide(SMOKE, self.scaled(1.03, saving_us=3.0))
        self.assertFalse(d['screen_winner']); self.assertEqual(d['kill_rules']['fired'], ['gateup_saving_us_per_layer'])
        b = self.scaled(1.03)
        for v in b['views']:
            v['interval_stats'] = None
        d = s.decide(SMOKE, b)
        self.assertFalse(d['screen_winner']); self.assertEqual(d['kill_rules']['fired'], ['gateup_saving_unmeasured'])

    def test_drift_inexact_proposals_smoke_refuse(self):
        b = self.scaled(1.05); b['views'][4]['rate'] *= 1.006  # k3x drift 0.6 % > 0.5 %
        d = s.decide(SMOKE, b); self.assertFalse(d['screen_winner']); self.assertIn('k3x_drift_percent', d['kill_rules']['fired'])
        b = self.scaled(1.05); b['views'][1]['exact_count'] = 12
        d = s.decide(SMOKE, b); self.assertFalse(d['screen_winner']); self.assertIn('inexact_view', d['kill_rules']['fired'])
        b = self.scaled(1.05); b['views'][3]['draft_proposals'] = {'x': 1}
        d = s.decide(SMOKE, b); self.assertFalse(d['screen_winner']); self.assertIn('draft_proposals_differ', d['kill_rules']['fired'])
        b = self.scaled(1.05); b['views'][3]['acceptance_counts'] = [0]
        self.assertIn('acceptance_differs', s.decide(SMOKE, b)['kill_rules']['fired'])
        d = s.decide_or_incomplete(dict(SMOKE, exact=False), self.scaled(1.05))
        self.assertEqual(d['outcome'], 'INCOMPLETE: no decision')
        b = self.scaled(1.05); b['views'][1]['variant'] = 'k3trims'
        self.assertEqual(s.decide_or_incomplete(SMOKE, b)['outcome'], 'INCOMPLETE: no decision')

    def test_envelope_attribution_on_real_k3x_streams(self):
        env = stats(1)['envelope']
        self.assertTrue(11.3 < env['scopes_ms']['layer_body'] < 11.8 and 11.7 < env['scopes_ms']['half_total'] < 12.1)
        self.assertEqual(env['scope_counts']['token_history'], 0)  # staged view (rank0_prepare=async)
        self.assertTrue(1.3 < env['scopes_ms']['boundary_total'] < 1.6 and 0.0 < env['boundary_export_ms'] < 0.1)


class Packet190Real(unittest.TestCase):
    def test_record_constant_equals_the_chain_metric(self):
        stored = read(P190_SUMMARY)['class_balanced_tok_s_1_100_intervals_after_ttft']['median']
        self.assertEqual(stored, s.RECORD); self.assertEqual(s.RECORD_BAR, 1.02 * s.RECORD); self.assertAlmostEqual(s.RECORD_BAR, 63.592, places=3)

    def test_view_stats_reproduce_the_record_chain(self):
        oracle = STAGE / 'packet49-integrate/oracle/results'
        for prompt in PROMPTS:  # the chain receipts are exact against the packet49 oracle (checked here directly)
            r = read(P190 / 'repeat-1' / prompt / 'receipt.json')
            self.assertEqual(r['tokens'], read(oracle / prompt / 'result.json')['tokens'][:len(r['tokens'])])
            self.assertEqual((len(r['tokens']), r['cached_tokens']), (128, 0))
        st = s.view_stats(P190 / 'repeat-1', list(PROMPTS), 'k3x', require_exact=False)
        self.assertEqual(st['intervals'], 1188); self.assertGreater(st['hits'], 850); self.assertGreater(st['misses'], 200)
        self.assertTrue(13.3 < st['hit']['elapsed'] < 13.8 and 25.0 < st['miss']['elapsed'] < 26.0)
        self.assertTrue(1.4 < st['hit']['Bd'] < 1.6 and st['hit']['boundary_over_draft'] < 0.05)
        self.assertTrue(1.4 < st['hit']['D'] < 1.7 and st['hit']['D'] > st['hit']['D_op9'])  # async prepare: op 9 completes early, the wall is D


if __name__ == '__main__':
    unittest.main()
