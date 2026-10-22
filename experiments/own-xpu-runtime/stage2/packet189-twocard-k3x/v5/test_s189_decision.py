"""s189_decision on REAL device data, read where packet188/packet187 retained it (never copied; the analysis gate pins
every file it reads by sha256).

* packet188 (2026-10-22, lane B, lanequeue-B35): its one-load V3/k3+trims/V3/k3+trims/V3 bracket (row 2), its fresh V3
  control (row 1) and its k3+trims smoke (row 0). With packet188's k3+trims views relabeled as the k3x candidate the rule
  must report packet188's measured numbers (rates 60.526/60.564/60.536/60.382/60.540, fresh 60.505, export 0.592 ms,
  boundary 2.005 ms, hit saving 0.071 ms, A trim 0.142 ms, D from the draft wall 1.586 -> 1.537 ms, boundary over the
  draft wall on 100 % of hits) and say NOT A SCREEN WINNER with the export, boundary, hit-saving and draft-window kill
  rules fired and the trims rule passed; scalings of the real numbers cover every branch.
* The fresh V3 reference is packet188 row 1, pinned by sha256 (s189_decision.FRESH_V3) and read in place.
* packet187 (2026-10-22, the record chain, WS128): view_stats on its 12 real request streams reproduces the record
  replay (hit 14.050, miss 25.750 ms, boundary 1.027 ms) and RECORD equals its stored metric.
* The lever-synthesis-3 replay (analysis/replay_k3x.py) reproduces the record 60.65951991975228 to 1e-9 from packet187's
  1,188 intervals, the measured k3+trims views through the draft-wall identity, and prices k3x at +2.7398524525334977 %
  (62.321501263968656 tok/s) on the record replay.
"""
import copy, importlib.util, json, unittest
from pathlib import Path
import s189_decision as s

P = Path(__file__).resolve().parent
STAGE = P.parents[1]
P188 = STAGE / 'packet188-twocard-k3-composite/v5/evidence'
BRACKET188 = P188 / 'device-row2-bracket-v3k-k3trims-B-p188'
CONTROL188 = P188 / 'device-row1-control-v3-B-p188/bracket-summary.json'
SMOKE188 = P188 / 'device-row0-smoke-k3trims-B-p188/bracket-summary.json'
P187 = STAGE / 'packet187-record-bundle-v3/build/device-cards01-p187-a/WS128/run'
P187_SUMMARY = STAGE / 'packet187-record-bundle-v3/evidence/device-cards01-p187-a/WS128/summary.json'
PROMPTS = ('incident-retrospective', 'code-review', 'customer-email', 'sql-debugging', 'release-plan', 'benchmark-analysis',
           'architecture-tradeoff', 'bug-report-synthesis', 'technical-guide', 'risk-register', 'performance-hypotheses', 'decision-memo')
K3X_PRICE = dict(rate=62.321501263968656, gain_pct=2.7398524525334977)  # lever synthesis 3, central k3x price on the record replay
READ = []
_STATS = {}


def read(path):
    READ.append(Path(path));return json.loads(Path(path).read_text())


def stats(index):
    """view_stats of packet188 row-2 view `index` (cached; the k3+trims views are relabeled k3x)."""
    if index not in _STATS:
        choice = 'candidate' if index % 2 else 'control'
        _STATS[index] = s.view_stats(BRACKET188 / 'run/views' / f'{index:02d}-{choice}', list(PROMPTS), 'k3x' if index % 2 else 'v3k')
    return _STATS[index]


def real_bracket():
    """packet188 row 2 as a packet189 bracket record: k3+trims relabeled k3x, interval_stats recomputed with D := draft wall."""
    rec = s.bracket_record(read(BRACKET188 / 'bracket-summary.json'))
    for i, v in enumerate(rec['views']):
        v['variant'] = 'k3x' if v['variant'] == 'k3trims' else v['variant']
        v['interval_stats'] = stats(i)
    return rec


SMOKE = dict(kind='smoke', passed=True, exact=True)


class Packet188Real(unittest.TestCase):
    def setUp(self):
        self.fresh = s.fresh_v3_record()
        self.bracket = real_bracket()

    def test_smoke_record_from_real_smoke(self):
        r = s.smoke_record(read(SMOKE188))
        self.assertTrue(r['passed'] and r['exact'])

    def test_fresh_reference_is_packet188_row_1_pinned(self):
        self.assertEqual(self.fresh['rate'], 60.50488520482965);self.assertEqual(self.fresh['sha256'], s.FRESH_V3['sha256'])
        self.assertTrue(self.fresh['all_13_exact'] and self.fresh['exact_count'] == 13 and self.fresh['read_in_place'])
        with self.assertRaises(s.Incomplete):s.fresh_v3_record(SMOKE188)  # a different summary fails the pin

    def test_measured_k3trims_is_not_a_screen_winner_and_reports_the_measured_numbers(self):
        d = s.decide(SMOKE, self.bracket, self.fresh)
        self.assertFalse(d['screen_winner'] or d['chain_rule_met']);self.assertIn('NOT A SCREEN WINNER', d['outcome'])
        self.assertTrue(d['every_view_exact'] and d['draft_proposals_identical'] and d['acceptance_identical'] and d['fresh_reference_proposals_and_acceptance_identical'])
        self.assertEqual(d['v3_rates'], [60.50488520482965, 60.526318491191034, 60.53639572746203, 60.53991753525172])
        self.assertEqual(d['k3x_rates'], [60.56435403407874, 60.38239534799434])
        self.assertAlmostEqual(d['min_gain_vs_every_v3_view_percent'], -0.26019557619261224, places=9)
        self.assertAlmostEqual(d['v3_drift_percent'], 0.05790000312118071, places=9)
        k = d['kill_rules']
        self.assertEqual(k['fired'], ['boundary_over_draft_wall_fraction', 'boundary_total_ms', 'handoff_export_ms', 'k3_hit_saving_ms'])
        self.assertAlmostEqual(k['handoff_export_ms'], 0.5922159452861953, places=9)      # the KioCopy export, 28.9 ns/byte
        self.assertAlmostEqual(k['boundary_total_ms'], 2.00502974368687, places=9)
        self.assertAlmostEqual(k['k3_hit_saving_ms'], 0.07090882325907266, places=9)
        self.assertEqual(k['boundary_over_draft_wall_fraction'], 1.0)
        self.assertAlmostEqual(k['trims_A_saving_ms'], 0.1424436472818975, places=9)       # the trims rule passes
        # D is the draft's observed wall (1.586 -> 1.537), never op 9 (1.608 -> 0.427, the model artifact)
        self.assertAlmostEqual(k['v3_hit_D_ms'], 1.5862900836909872, places=9);self.assertAlmostEqual(k['k3x_hit_D_ms'], 1.5377190954935622, places=9)
        self.assertAlmostEqual(k['v3_hit_D_op9_ms'], 1.6078596556784375, places=9);self.assertAlmostEqual(k['k3x_hit_D_op9_ms'], 0.4267274277047914, places=9)
        self.assertAlmostEqual(k['scope_boundary_body_ms']['delta'], 0.4595604636644217, places=9)   # layer-26 kernels
        self.assertAlmostEqual(k['scope_handoff_export_ms']['delta'], 0.5393762864758699, places=9)  # the export path
        self.assertAlmostEqual(k['v3_hit_elapsed_ms'], 14.059975594068971, places=9);self.assertAlmostEqual(k['k3x_miss_elapsed_ms'], 26.153771808594684, places=9)
        self.assertEqual(k['v3_hit_rank1_binds_emission'], 1.0);self.assertLess(k['k3x_hit_rank1_binds_emission'], 0.05)

    def test_v3_views_as_candidate_is_a_null(self):
        b = copy.deepcopy(self.bracket)
        for i in (1, 3):
            b['views'][i] = dict(b['views'][i - 1], variant='k3x')
        d = s.decide(SMOKE, b, self.fresh)
        self.assertFalse(d['screen_winner']);self.assertLessEqual(d['min_gain_vs_every_v3_view_percent'], 0)
        k = d['kill_rules'];self.assertLess(abs(k['k3_hit_saving_ms']), 0.01);self.assertLess(abs(k['trims_A_saving_ms']), 0.01)  # views 0/2 vs the mean of 0/2/4 (view jitter)
        self.assertEqual(k['fired'], ['k3_hit_saving_ms', 'trims_A_saving_ms']);self.assertLess(k['boundary_over_draft_wall_fraction'], 0.01)

    def scaled(self, factor):
        b = copy.deepcopy(self.bracket);top = max(max(v['rate'] for v in b['views'] if v['variant'] == 'v3k'), self.fresh['rate'])
        for v in b['views']:
            if v['variant'] == 'k3x':v['rate'] = top * factor
        return b

    def test_two_point_two_percent_over_v3_meets_the_chain_rule(self):
        d = s.decide(SMOKE, self.scaled(1.025), self.fresh)
        self.assertTrue(d['screen_winner'] and d['chain_rule_met']);self.assertGreaterEqual(d['slower_k3x_rate'], s.RECORD_BAR)

    def test_two_percent_over_v3_but_below_the_record_bar_is_winner_only(self):
        d = s.decide(SMOKE, self.scaled(1.021), self.fresh)  # 60.540 x 1.021 = 61.81 < 61.873
        self.assertTrue(d['screen_winner']);self.assertFalse(d['chain_rule_met'])

    def test_below_two_percent_is_winner_only(self):
        d = s.decide(SMOKE, self.scaled(1.015), self.fresh)
        self.assertTrue(d['screen_winner']);self.assertFalse(d['chain_rule_met'])

    def test_below_half_percent_is_not_a_winner(self):
        self.assertFalse(s.decide(SMOKE, self.scaled(1.004), self.fresh)['screen_winner'])

    def test_drift_inexact_proposals_smoke_refuse(self):
        f = dict(self.fresh);f['rate'] *= 1.04
        self.assertFalse(s.decide(SMOKE, self.scaled(1.05), f)['screen_winner'])
        b = self.scaled(1.05);b['views'][1]['exact_count'] = 12
        self.assertFalse(s.decide(SMOKE, b, self.fresh)['screen_winner'])
        b = self.scaled(1.05);b['views'][3] = copy.deepcopy(b['views'][3]);b['views'][3]['draft_proposals'] = {'x': 1}
        self.assertFalse(s.decide(SMOKE, b, self.fresh)['screen_winner'])
        d = s.decide_or_incomplete(dict(SMOKE, exact=False), self.scaled(1.05), fresh=self.fresh)
        self.assertEqual(d['outcome'], 'INCOMPLETE: no decision')
        b = self.scaled(1.05);b['views'][1]['variant'] = 'k3trims'
        self.assertEqual(s.decide_or_incomplete(SMOKE, b, fresh=self.fresh)['outcome'], 'INCOMPLETE: no decision')

    def test_envelope_attribution_on_real_streams(self):
        env = stats(0)['envelope']
        self.assertTrue(11.5 < env['scopes_ms']['layer_body'] < 11.8 and 11.9 < env['scopes_ms']['half_total'] < 12.2)
        self.assertTrue(0.2 < env['envelope_parts_ms']['snapshot'] < 0.4 and 0.0 < env['envelope_parts_ms']['token_history'] < 0.05)
        self.assertTrue(0.3 < env['rank0_half_envelope_ms'] < 0.6 and abs(env['envelope_unattributed_ms']) < 0.1)
        self.assertTrue(0.9 < env['scopes_ms']['boundary_total'] < 1.1 and 0.0 < env['boundary_export_ms'] < 0.1)
        k = stats(1)['envelope'];self.assertEqual(k['scope_counts']['token_history'], 0)  # staged view: no synchronous token_history scope
        self.assertTrue(1.9 < k['scopes_ms']['boundary_total'] < 2.1 and 0.5 < k['boundary_export_ms'] < 0.7)


class Packet187Real(unittest.TestCase):
    def test_record_constant_equals_the_chain_metric(self):
        stored = read(P187_SUMMARY)['class_balanced_tok_s_1_100_intervals_after_ttft']['median']
        self.assertEqual(stored, s.RECORD);self.assertEqual(s.RECORD_BAR, 1.02 * s.RECORD)

    def test_view_stats_reproduce_the_record_replay(self):
        oracle = STAGE / 'packet49-integrate/oracle/results'
        for prompt in PROMPTS:  # the chain receipts are exact against the packet49 oracle (checked here directly)
            r = read(P187 / 'repeat-1' / prompt / 'receipt.json')
            self.assertEqual(r['tokens'], read(oracle / prompt / 'result.json')['tokens'][:len(r['tokens'])])
            self.assertEqual((len(r['tokens']), r['cached_tokens']), (128, 0))
        st = s.view_stats(P187 / 'repeat-1', list(PROMPTS), 'v3', require_exact=False)
        self.assertEqual((st['hits'], st['misses'], st['intervals']), (932, 256, 1188))
        self.assertAlmostEqual(st['hit']['elapsed'], 14.04991732770877, places=9)
        self.assertAlmostEqual(st['miss']['elapsed'], 25.750204884843697, places=9)
        self.assertAlmostEqual(st['hit']['Bd'], 1.0269026522066989, places=9)
        self.assertEqual(st['hit']['boundary_over_draft'], 0.0);self.assertEqual(st['hit']['rank1_binds_emission'], 1.0)
        self.assertTrue(1.5 < st['hit']['D'] < 1.7 and st['hit']['D'] < st['hit']['D_op9'])


class LeverSynthesis3Replay(unittest.TestCase):
    def test_replay_reproduces_the_record_and_prices_k3x(self):
        spec = importlib.util.spec_from_file_location('replay_k3x', P.parent / 'analysis/replay_k3x.py')
        m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        out, w = m.compute()
        self.assertLess(abs(w['base'] - s.RECORD), 1e-9)
        self.assertEqual([round(r, 9) for r in w['v3_rates']], [round(r, 9) for r in (60.526318491191034, 60.53639572746203, 60.53991753525172)])
        self.assertEqual([round(r, 9) for r in w['k3_rates']], [round(r, 9) for r in (60.56435403407874, 60.38239534799434)])
        central = next(p for p in w['P'] if p['label'].startswith('k3x: k3 + trims, boundary export on the copy engine (central)'))
        self.assertAlmostEqual(central['rate'], K3X_PRICE['rate'], places=9);self.assertAlmostEqual(central['gain_pct'], K3X_PRICE['gain_pct'], places=9)
        self.assertGreater(central['rate'], s.RECORD_BAR)
        pessimistic = next(p for p in w['P'] if p['label'].startswith('k3x: everything pessimistic'))
        self.assertGreater(pessimistic['rate'], s.RECORD_BAR)  # 62.04 > 61.873: the chain bar holds in the pessimistic corner
        A = w['A'];self.assertAlmostEqual(A['body']['d_hit'], 0.459, places=3);self.assertAlmostEqual(A['export']['d_hit'], 0.540, places=3)  # hit means: layer-26 kernels, export path
        for r in w['R']:  # the measured k3trims views are reproduced exactly through the draft-wall identity (D := draft_wall + 0.006)
            if r['variant'].startswith('k3trims as measured'):
                self.assertAlmostEqual(r['rate'], r['measured_rate'], places=9)


if __name__ == '__main__':
    unittest.main()
