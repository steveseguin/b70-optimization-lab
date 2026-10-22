"""s188_decision on REAL device data, read where packet186/packet187 retained it (never copied; the analysis gate pins
every file it reads by sha256).

* packet186 (2026-10-22, lane B): its one-load U/V3/U/V3/U bracket and its V3 smoke. With packet186's V3 views as BOTH
  the V3 controls and the k3+trims candidate (a null k3) the rule must say NOT A WINNER and fire every kill rule;
  with V3 as the candidate against packet186's U views relabeled as V3 controls (+4.66 %) it is a screen winner but
  NOT a chain (60.533 < 61.873, the record bar of the V3 line); scalings of the real numbers cover every branch.
* packet187 (2026-10-22, the record chain, WS128): view_stats on its 12 real request streams reproduces the record
  replay (hit 14.050, miss 25.750 ms, boundary 1.027 ms, Bd > D on 0 hits) and RECORD equals its stored metric.
* The envelope attribution on packet186's real V3 views reproduces half_total/layer_body/snapshot/token_history/
  token_prep from the p150 host scopes.
"""
import copy, json, unittest
from pathlib import Path
import s188_decision as s

P = Path(__file__).resolve().parent
STAGE = P.parents[1]
P186 = STAGE / 'packet186-twocard-v3/v5/evidence'
BRACKET186 = P186 / 'device-row2-bracket-u-v3-B-p186'
SMOKE186 = P186 / 'device-row0-smoke-v3-B-p186/bracket-summary.json'
P187 = STAGE / 'packet187-record-bundle-v3/build/device-cards01-p187-a/WS128/run'
P187_SUMMARY = STAGE / 'packet187-record-bundle-v3/evidence/device-cards01-p187-a/WS128/summary.json'
PROMPTS = ('incident-retrospective', 'code-review', 'customer-email', 'sql-debugging', 'release-plan', 'benchmark-analysis',
           'architecture-tradeoff', 'bug-report-synthesis', 'technical-guide', 'risk-register', 'performance-hypotheses', 'decision-memo')
READ = []


def read(path):
    READ.append(Path(path));return json.loads(Path(path).read_text())


def bracket186():
    return read(BRACKET186 / 'bracket-summary.json')


def view186(i, variant):
    v = bracket186()['views'][i]
    return dict(variant=variant, rate=v['rate'], all_13_exact=v['all_13_exact'], exact_count=v['exact_count'],
                draft_proposals=v['draft_proposals'], acceptance_counts=v['acceptance_counts'], interval_stats=None)


SMOKE = dict(kind='smoke', passed=True, exact=True)


def bracket(v3k, k3):
    return dict(kind='bracket', views=[v3k[0], k3[0], v3k[1], k3[1], v3k[2]])


class Packet186Real(unittest.TestCase):
    def setUp(self):
        self.v3 = [view186(1, 'v3k'), view186(3, 'v3k'), view186(1, 'v3k')]
        self.u = [view186(0, 'v3k'), view186(2, 'v3k'), view186(4, 'v3k')]

    def control(self, i=1):
        return dict(view186(i, 'v3'), kind='view')

    def test_smoke_record_from_real_smoke(self):
        r = s.smoke_record(read(SMOKE186))
        self.assertTrue(r['passed'] and r['exact'])

    def test_null_k3_equal_to_v3_is_not_a_winner(self):
        k3 = [view186(3, 'k3trims'), view186(1, 'k3trims')]
        d = s.decide(SMOKE, self.control(1), bracket(self.v3, k3))
        self.assertTrue(d['every_view_exact'] and d['draft_proposals_identical'] and d['acceptance_identical'])
        self.assertFalse(d['screen_winner'] or d['chain_rule_met'])
        self.assertLess(d['v3_drift_percent'], 0.1)
        self.assertLessEqual(d['min_gain_vs_every_v3_view_percent'], 0)

    def test_v3_over_u_is_a_winner_but_below_the_v3_record_bar(self):
        k3 = [view186(1, 'k3trims'), view186(3, 'k3trims')]
        d = s.decide(SMOKE, self.control(0), bracket(self.u, k3))
        self.assertTrue(d['screen_winner']);self.assertFalse(d['chain_rule_met'])
        self.assertGreater(d['min_gain_vs_every_v3_view_percent'], 4.5)
        self.assertLess(d['slower_k3trims_rate'], (1 + s.CHAIN_BAR) * s.RECORD)

    def scaled(self, factor):
        out = []
        for i in (1, 3):
            row = view186(i, 'k3trims');row['rate'] = max(v['rate'] for v in self.v3) * factor;out.append(row)
        return out

    def test_two_point_two_percent_over_v3_meets_the_chain_rule(self):
        d = s.decide(SMOKE, self.control(1), bracket(self.v3, self.scaled(1.022)))
        self.assertTrue(d['screen_winner'] and d['chain_rule_met'])
        self.assertGreaterEqual(d['slower_k3trims_rate'], 61.873)

    def test_below_two_percent_is_winner_only(self):
        d = s.decide(SMOKE, self.control(1), bracket(self.v3, self.scaled(1.015)))
        self.assertTrue(d['screen_winner']);self.assertFalse(d['chain_rule_met'])

    def test_below_half_percent_is_not_a_winner(self):
        d = s.decide(SMOKE, self.control(1), bracket(self.v3, self.scaled(1.004)))
        self.assertFalse(d['screen_winner'] or d['chain_rule_met'])

    def test_drift_inexact_proposals_smoke_refuse(self):
        c = self.control(1);c['rate'] *= 1.04
        self.assertFalse(s.decide(SMOKE, c, bracket(self.v3, self.scaled(1.05)))['screen_winner'])
        k3 = self.scaled(1.05);k3[0]['exact_count'] = 12
        self.assertFalse(s.decide(SMOKE, self.control(1), bracket(self.v3, k3))['screen_winner'])
        k3 = self.scaled(1.05);k3[1] = copy.deepcopy(k3[1]);k3[1]['draft_proposals'] = {'x': 1}
        self.assertFalse(s.decide(SMOKE, self.control(1), bracket(self.v3, k3))['screen_winner'])
        d = s.decide_or_incomplete(dict(SMOKE, exact=False), self.control(1), bracket(self.v3, self.scaled(1.05)))
        self.assertEqual(d['outcome'], 'INCOMPLETE: no decision')

    def test_kill_rules_on_real_v3_streams(self):
        views = BRACKET186 / 'run/views'
        v3 = [s.view_stats(views / '01-candidate', list(PROMPTS), 'v3k'), s.view_stats(views / '03-candidate', list(PROMPTS), 'v3k')]
        k = s.kill_rules(v3, v3)  # a null k3: every kill rule must fire
        self.assertEqual(k['fired'], ['k3_hit_saving_ms', 'trims_A_saving_ms'])
        self.assertAlmostEqual(k['k3_hit_saving_ms'], 0.0, places=12);self.assertAlmostEqual(k['trims_A_saving_ms'], 0.0, places=12)
        self.assertLess(k['boundary_over_draft_fraction'], 0.005)  # V3: Bd (1.03) exceeds D (1.60) on ~1 of 1,864 hits
        # the envelope attribution reproduces the real p150 host scopes (packet186 V3 views, decode cycles)
        env = v3[0]['envelope']
        self.assertTrue(11.5 < env['scopes_ms']['layer_body'] < 11.8 and 11.9 < env['scopes_ms']['half_total'] < 12.2)
        self.assertTrue(0.2 < env['envelope_parts_ms']['snapshot'] < 0.4 and 0.0 < env['envelope_parts_ms']['token_history'] < 0.05)
        self.assertTrue(0.3 < env['rank0_half_envelope_ms'] < 0.6 and abs(env['envelope_unattributed_ms']) < 0.1)
        self.assertTrue(0.9 < env['scopes_ms']['boundary_total'] < 1.1 and 0.0 < env['boundary_export_ms'] < 0.1)
        # a synthetic boundary overflow (Bd scaled past D on every hit) fires the draft-window rule
        fake = copy.deepcopy(v3);fake[0]['hit']['boundary_over_draft'] = fake[1]['hit']['boundary_over_draft'] = 0.2
        self.assertIn('boundary_over_draft_fraction', s.kill_rules(v3, fake)['fired'])


class Packet187Real(unittest.TestCase):
    def test_record_constant_equals_the_chain_metric(self):
        stored = read(P187_SUMMARY)['class_balanced_tok_s_1_100_intervals_after_ttft']['median']
        self.assertEqual(stored, s.RECORD)

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
        self.assertEqual(st['hit']['boundary_over_draft'], 0.0)
        self.assertEqual(st['hit']['rank1_binds_emission'], 1.0)


if __name__ == '__main__':
    unittest.main()
