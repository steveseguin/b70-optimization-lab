"""packet58-cache23 decision rule tests (synthetic rates on synthetic exact suites; never device data)."""
import copy, unittest
import suite_driver as D
from compare_bracket import compare, s58c23_decision, RECORD_TOK_S, CHAIN_BAR_TOK_S

LABELS = ['A0', 'B0', 'A1', 'B1', 'A2']
RATE = 'class_balanced_tok_s_1_100_intervals_after_ttft'


def views(rates):
    manifest = D.oracle_inputs()
    out = []
    for i, r in enumerate(rates):
        reqs = [dict(prompt_id=e['prompt_id'], prompt_token_sha256='p' * 64, tokens=D.CHECK.token_record(D.ORACLE / 'results' / e['prompt_id'])[:128],
                     passed=True, exact_oracle=True, cached_tokens=0) for e in manifest['prompts']]
        out.append({'label': LABELS[i], 'view': 'max23' if i % 2 else 'max', 'passed': True, 'requests': reqs, RATE: dict(median=r)})
    return out


def readout(a_fills, b_fills):
    v = {}
    for l in LABELS:
        f = b_fills if l in ('B0', 'B1') else a_fills
        v[l] = dict(fills_per_token=f, fill_mb_per_token=round(f * 1.983, 3), miss_read_regression=dict(unfilled_ms_per_next_fill_mb=0.032))
    return dict(views=v)


class Decision(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(RECORD_TOK_S, 35.926720)
        self.assertAlmostEqual(CHAIN_BAR_TOK_S, 36.645, places=2)
        self.assertAlmostEqual(CHAIN_BAR_TOK_S, 1.02 * RECORD_TOK_S, places=9)

    def test_screen_winner_not_chain(self):
        c = compare(views([35.9, 36.2, 35.93, 36.21, 35.92]))
        d = s58c23_decision(c, readout(15.45, 13.9))
        self.assertTrue(d['screen_winner']); self.assertFalse(d['chain_rule']); self.assertEqual(d['kill_rules_fired'], [])
        self.assertTrue(d['fills_reduced_8pct']); self.assertFalse(d['capacity_closed_at_23gb'])
        self.assertEqual(d['per_view']['B0']['fills_per_token'], 13.9)

    def test_screen_bar_boundary(self):
        base = [35.9, 0, 35.93, 0, 35.92]
        for b, win in ((35.93 * 1.005 + 1e-6, True), (35.93 * 1.005 - 1e-3, False)):
            r = list(base); r[1] = r[3] = round(b, 6)
            d = s58c23_decision(compare(views(r)), readout(15.45, 13.9))
            self.assertEqual(d['screen_winner'], win, b)

    def test_chain_rule_needs_every_max_view_and_the_bar(self):
        d = s58c23_decision(compare(views([35.9, 36.70, 35.93, 36.71, 35.92])), readout(15.45, 13.9))
        self.assertTrue(d['chain_rule'])
        d = s58c23_decision(compare(views([36.0, 36.70, 35.93, 36.71, 35.92])), readout(15.45, 13.9))  # A0 = 36.0 -> 36.70 < 1.02 x 36.0
        self.assertFalse(d['chain_rule']); self.assertTrue(d['screen_winner'])
        d = s58c23_decision(compare(views([35.9, 36.66, 35.93, 36.64, 35.92])), readout(15.45, 13.9))  # one view under 36.645
        self.assertFalse(d['chain_rule'])

    def test_kill_rules(self):
        d = s58c23_decision(compare(views([35.9, 36.2, 35.93, 36.21, 35.92])), readout(15.45, 14.3))  # 7.4 % < 8 %
        self.assertFalse(d['screen_winner']); self.assertTrue(d['capacity_closed_at_23gb'])
        d = s58c23_decision(compare(views([35.9, 36.2, 35.19, 36.21, 35.92])), readout(15.45, 13.9))  # warm floor
        self.assertFalse(d['screen_winner']); self.assertTrue(any('35.2' in k for k in d['kill_rules_fired']))
        d = s58c23_decision(compare(views([35.9, 37.4, 35.93, 37.4, 34.80])), readout(15.45, 13.9))   # drift 3.2 %
        self.assertFalse(d['screen_winner']); self.assertTrue(any('drift' in k for k in d['kill_rules_fired']))
        d = s58c23_decision(compare(views([35.9, 36.2, 35.93, 36.21, 35.92])), dict(available=False))
        self.assertFalse(d['screen_winner']); self.assertIsNone(d['fills_reduced_8pct'])

    def test_order_and_exactness_refusals(self):
        v = views([35.9, 36.2, 35.93, 36.21, 35.92]); v[1]['view'] = 'spin-kio'
        with self.assertRaises(ValueError): compare(v)
        v = views([35.9, 36.2, 35.93, 36.21, 35.92]); v[2]['requests'][0]['exact_oracle'] = False
        with self.assertRaises(ValueError): compare(v)
        v = views([35.9, 36.2, 35.93, 36.21, 35.92]); v[4]['requests'][-1]['tokens'][-1] += 1
        with self.assertRaises(ValueError): compare(v)


if __name__ == '__main__':
    unittest.main()
