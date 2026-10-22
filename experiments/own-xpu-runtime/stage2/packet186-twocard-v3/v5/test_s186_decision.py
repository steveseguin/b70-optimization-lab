"""s186_decision on REAL device data (packet185 five fresh-load views, packet183 one-load bracket).

* packet185 (2026-10-22, lane B, bundle-8 line): its control views are exactly packet186's split-head
  control rows; its unsplit views are exactly packet186's U variant (full head on rank 1, rank 0 exports
  layer 23). With a "V3" equal to a real bundle-8 view the rule must say NOT A WINNER.
* packet183 (2026-10-22, lane B): its real one-load bracket, controls relabeled U and S1 metadata views
  relabeled V3 (-6.2 %), must say NOT A WINNER.
* Scalings of the real numbers cover every branch (winner+chain, winner below the 59.974 bar, below the
  +0.5 % screen bar, drift, inexact, missing smoke).
* The V3 interval extension: on 12 real packet183 request streams, inserting rank-0 boundary commands
  must reproduce the vendored packet85 accounting exactly when the boundary is absent and add it to the
  ready side when present; view_stats refuses a V3 view without boundary commands and vice versa.
"""
import copy, gzip, json, tempfile, unittest
from pathlib import Path
import s186_decision as s
from interval_model import intervals

P = Path(__file__).resolve().parent
OWN = P.parent / 'lineage-inputs'
P185 = OWN / 'packet185-own/v5/evidence'
P183 = OWN / 'packet183-own/v5/evidence/device-metadata-v5-B-p183/bracket-summary.json'
FIX = OWN / 'decision-fixtures/packet183-v5'
VIEWS185 = ['device-view0-production-B-p185', 'device-view1-unsplit-B-p185', 'device-view2-production-B-p185',
            'device-view3-unsplit-B-p185', 'device-view4-production-B-p185']


def summary185(i):
    return json.loads((P185 / VIEWS185[i] / 'bracket-summary.json').read_text())


def view185(i, variant):
    d = summary185(i);v = d['views'][0]
    return dict(variant=variant, rate=v['rate'], all_13_exact=v['all_13_exact'], exact_count=v['exact_count'], draft_proposals=v['draft_proposals'],
                acceptance_counts=v['acceptance_counts'], interval_stats=None)


def control185(i):
    return dict(view185(i, 'production'), kind='view')


SMOKE = dict(kind='smoke', passed=True, exact=True)


def bracket(u, v3):
    return dict(kind='bracket', views=[u[0], v3[0], u[1], v3[1], u[2]])


class Packet185Real(unittest.TestCase):
    def setUp(self):
        self.c0, self.c1 = control185(0), control185(4)
        self.u = [view185(1, 'u'), view185(3, 'u'), view185(1, 'u')]

    def test_null_v3_equal_to_bundle8_is_not_a_winner(self):
        v3 = [view185(2, 'v3'), view185(2, 'v3')]
        d = s.decide(SMOKE, self.c0, bracket(self.u, v3), self.c1)
        self.assertTrue(d['every_view_exact'] and d['draft_proposals_identical'] and d['acceptance_identical'])
        self.assertAlmostEqual(d['split_drift_percent'], 100 * (58.62126550991157 / 58.60067319718018 - 1), places=9)
        self.assertLess(d['u_drift_percent'], 0.05)
        self.assertFalse(d['screen_winner'] or d['chain_rule_met'])
        self.assertLess(d['min_gain_vs_split_controls_percent'], 0)
        self.assertGreater(d['min_gain_vs_u_percent'], 1.0)  # bundle 8 beats the un-split U views by ~1.4 % (packet185)

    def scaled(self, factor):
        v3 = []
        for _ in range(2):
            row = view185(2, 'v3');row['rate'] = max(self.c0['rate'], self.c1['rate']) * factor;v3.append(row)
        return v3

    def test_projected_central_gain_meets_the_chain_rule(self):
        d = s.decide(SMOKE, self.c0, bracket(self.u, self.scaled(1.0264)), self.c1)  # analysis/price-v3-measured.json central
        self.assertTrue(d['screen_winner'] and d['chain_rule_met'])
        self.assertGreaterEqual(d['slower_v3_rate'], 59.974)

    def test_two_percent_below_record_bar(self):
        d = s.decide(SMOKE, self.c0, bracket(self.u, self.scaled(1.021)), self.c1)  # 59.85 < 59.974
        self.assertTrue(d['screen_winner']);self.assertFalse(d['chain_rule_met'])

    def test_record_bar_but_below_two_percent(self):
        c0, c1 = copy.deepcopy(self.c0), copy.deepcopy(self.c1);c0['rate'] = c1['rate'] = 59.0
        u = copy.deepcopy(self.u)
        for row in u:row['rate'] = 58.9
        v3 = self.scaled(1.0);[r.update(rate=60.0) for r in v3]  # +1.69 % over 59.0 although >= 59.974
        d = s.decide(SMOKE, c0, bracket(u, v3), c1)
        self.assertTrue(d['screen_winner']);self.assertFalse(d['chain_rule_met'])

    def test_below_screen_bar(self):
        d = s.decide(SMOKE, self.c0, bracket(self.u, self.scaled(1.004)), self.c1)
        self.assertFalse(d['screen_winner'] or d['chain_rule_met'])

    def test_u_view_counts_as_a_control(self):
        u = copy.deepcopy(self.u);u[1]['rate'] = 60.0  # one in-load U view faster than every V3 view
        d = s.decide(SMOKE, self.c0, bracket(u, self.scaled(1.006)), self.c1)
        self.assertFalse(d['screen_winner'])

    def test_drift(self):
        u = copy.deepcopy(self.u);u[2]['rate'] *= 0.96
        d = s.decide(SMOKE, self.c0, bracket(u, self.scaled(1.05)), self.c1)
        self.assertGreater(d['u_drift_percent'], 3.0);self.assertFalse(d['screen_winner'] or d['chain_rule_met'])
        c1 = copy.deepcopy(self.c1);c1['rate'] *= 0.965
        d = s.decide(SMOKE, self.c0, bracket(self.u, self.scaled(1.05)), c1)
        self.assertGreater(d['split_drift_percent'], 3.0);self.assertFalse(d['screen_winner'] or d['chain_rule_met'])

    def test_inexact_or_changed_proposals(self):
        v3 = self.scaled(1.05);v3[1]['exact_count'] = 12
        self.assertFalse(s.decide(SMOKE, self.c0, bracket(self.u, v3), self.c1)['screen_winner'])
        v3 = self.scaled(1.05);v3[0]['draft_proposals'] = dict(v3[0]['draft_proposals'], incident64={'rows': 1, 'sha256': '0' * 64})
        d = s.decide(SMOKE, self.c0, bracket(self.u, v3), self.c1)
        self.assertFalse(d['draft_proposals_identical'] or d['screen_winner'])

    def test_refusals(self):
        v3 = self.scaled(1.05)
        for smoke in (dict(SMOKE, passed=False), dict(SMOKE, exact=False), dict(kind='view')):
            d = s.decide_or_incomplete(smoke, self.c0, bracket(self.u, v3), self.c1)
            self.assertEqual(d['outcome'], 'INCOMPLETE: no decision');self.assertFalse(d['screen_winner'])
        wrong = bracket(self.u, v3);wrong['views'] = wrong['views'][::-1][1:] + wrong['views'][:1]
        self.assertEqual(s.decide_or_incomplete(SMOKE, self.c0, wrong, self.c1)['outcome'], 'INCOMPLETE: no decision')
        self.assertEqual(s.decide_or_incomplete(ValueError('missing row')), dict(schema='packet186.s186-decision.v1', screen_winner=False,
                         chain_rule_met=False, outcome='INCOMPLETE: no decision', reason='missing row', rule=s.RULE))


class Packet183Real(unittest.TestCase):
    def test_real_s1_bracket_as_v3_is_not_a_winner(self):
        summary = json.loads(P183.read_text())
        rows = [dict(variant='u' if v['choice'] == 'control' else 'v3', rate=v['rate'], all_13_exact=v['all_13_exact'], exact_count=v['exact_count'],
                     draft_proposals=v['draft_proposals'], acceptance_counts=v['acceptance_counts']) for v in summary['views']]
        d = s.decide(SMOKE, control185(0), dict(kind='bracket', views=rows), control185(4))
        self.assertTrue(d['every_view_exact'] and d['draft_proposals_identical'] and d['acceptance_identical'])  # same line, same draft
        self.assertFalse(d['screen_winner'] or d['chain_rule_met'])
        self.assertLess(d['min_gain_vs_split_controls_percent'], -5.0)
        self.assertAlmostEqual(d['u_drift_percent'], summary['control_drift_percent'], places=9)


def materialize(view, root, boundary_ms=None):
    prompts = []
    for prompt in sorted((FIX / view).iterdir()):
        dest = root / view / prompt.name;(dest / 'rank0').mkdir(parents=True)
        r = json.loads(gzip.decompress((prompt / 'receipt.json.gz').read_bytes()))
        if boundary_ms is not None:  # one rank-0 boundary per position, right after its rank-0 half
            extra = {}
            for t in r['rank_trace']:
                if t['rank'] == 0 and t['op'] == 1 and t['position'] not in extra:
                    extra[t['position']] = dict(rank=0, op=15, token=t['token'], position=t['position'], fixture=t['fixture'], speculative=False,
                                                busy_ms=boundary_ms, sent=t['rank_completed'], rank_received=t['rank_completed'],
                                                rank_completed=t['rank_completed'] + boundary_ms / 1000)
            r['rank_trace'] = r['rank_trace'] + list(extra.values())
        (dest / 'receipt.json').write_text(json.dumps(r))
        records = json.loads(gzip.decompress((prompt / 'rank0-scopes.json.gz').read_bytes()))['records']
        (dest / 'rank0/timings.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in records))
        prompts.append(prompt.name)
    return root / view, prompts


class IntervalsV3(unittest.TestCase):
    def test_real_streams(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            directory, prompts = materialize('00-control', root)
            stats = s.view_stats(directory, prompts, 'production')  # real split-head control (bundle 8)
            self.assertEqual((stats['intervals'], stats['hits'], stats['misses'], stats['boundary_commands']), (1188, 932, 256, 0))
            self.assertAlmostEqual(stats['hit']['B'], 13.147, delta=0.01);self.assertEqual(stats['hit']['Bd'], 0.0)
            with self.assertRaisesRegex(ValueError, 'boundary commands present iff'):
                s.view_stats(directory, prompts, 'v3')
            for prompt in prompts:  # no boundary: the vendored accounting is reproduced exactly
                r = json.loads((directory / prompt / 'receipt.json').read_text())
                a, b = intervals(r), s.intervals_v3(r)
                for x, y in zip(a, b):
                    self.assertEqual(x['unresolved_control_gaps_ms'], y['unresolved_control_gaps_ms'])
                    self.assertEqual(x['prediction_without_gaps_ms'], y['prediction_without_gaps_ms'])
            # with a 1.2 ms boundary after each rank-0 half: ready = max(D, R + C + Bd)
            directory, prompts = materialize('00-control', root / 'v3', boundary_ms=1.2)
            r = json.loads((directory / prompts[0] / 'receipt.json').read_text())
            for x in s.intervals_v3(r):
                self.assertAlmostEqual(x['Bd'], 1.2, delta=1e-6)
                self.assertAlmostEqual(x['ready_v3_ms'], max(x['D'], x['R'] + x['C'] + x['Bd']), delta=1e-9)
            with self.assertRaisesRegex(ValueError, 'split-head view must record|boundary commands present iff'):
                s.view_stats(directory, prompts, 'production')


if __name__ == '__main__':
    unittest.main()
