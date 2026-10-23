"""packet58-onecard-diet-engine decision rule tests (synthetic rates on synthetic exact suites; never device data)."""
import copy, unittest
import suite_driver as D
from compare_bracket import compare, s58de_decision, RECORD_TOK_S, CHAIN_BAR_TOK_S, CONTROL_VIEW, CANDIDATE_VIEW

LABELS = ['A0', 'B0', 'A1', 'B1', 'A2']
RATE = 'class_balanced_tok_s_1_100_intervals_after_ttft'


def views(rates):
    manifest = D.oracle_inputs()
    out = []
    for i, r in enumerate(rates):
        reqs = [dict(prompt_id=e['prompt_id'], prompt_token_sha256='p' * 64, tokens=D.CHECK.token_record(D.ORACLE / 'results' / e['prompt_id'])[:128],
                     passed=True, exact_oracle=True, cached_tokens=0) for e in manifest['prompts']]
        out.append({'label': LABELS[i], 'view': CANDIDATE_VIEW if i % 2 else CONTROL_VIEW, 'passed': True, 'requests': reqs, RATE: dict(median=r)})
    return out


def readout(a_body, b_body, fills=13.457, b_fills=None, mb=26.68, b_mb=None):
    v = {}
    for l in LABELS:
        diet = l in ('B0', 'B1')
        v[l] = dict(fills_per_token=(b_fills if diet and b_fills is not None else fills), fill_mb_per_token=(b_mb if diet and b_mb is not None else mb),
                    layer_body_ms=b_body if diet else a_body, wait_ms=20.9, wall_ms=27.3, miss_read_regression=dict(unfilled_ms_per_next_fill_mb=0.033))
    return dict(views=v)


class Decision(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(RECORD_TOK_S, 36.602512)
        self.assertAlmostEqual(CHAIN_BAR_TOK_S, 37.335, places=3)
        self.assertAlmostEqual(CHAIN_BAR_TOK_S, 1.02 * RECORD_TOK_S, places=9)

    def test_screen_winner_not_chain(self):
        c = compare(views([36.58, 37.0, 36.60, 37.01, 36.59]))          # +1.1 %
        d = s58de_decision(c, readout(27.60, 27.00))                      # 12.5 us/layer
        self.assertTrue(d['screen_winner']); self.assertFalse(d['chain_rule']); self.assertEqual(d['kill_rules_fired'], [])
        self.assertTrue(d['fills_equal_across_arms']); self.assertAlmostEqual(d['gateup_saving_us_per_layer'], 12.5, places=6)
        self.assertEqual(d['per_view']['B0']['layer_body_ms'], 27.0)

    def test_screen_bar_boundary(self):
        base = [36.58, 0, 36.60, 0, 36.59]
        for b, win in ((36.60 * 1.005 + 1e-6, True), (36.60 * 1.005 - 1e-3, False)):
            r = list(base); r[1] = r[3] = round(b, 6)
            d = s58de_decision(compare(views(r)), readout(27.60, 27.00))
            self.assertEqual(d['screen_winner'], win, b)

    def test_chain_rule_needs_every_control_view_and_the_bar(self):
        d = s58de_decision(compare(views([36.58, 37.40, 36.60, 37.41, 36.59])), readout(27.60, 27.00))
        self.assertTrue(d['chain_rule'])
        d = s58de_decision(compare(views([36.70, 37.40, 36.60, 37.41, 36.59])), readout(27.60, 27.00))  # A0 = 36.70 -> 37.40 < 1.02 x 36.70
        self.assertFalse(d['chain_rule']); self.assertTrue(d['screen_winner'])
        d = s58de_decision(compare(views([36.58, 37.34, 36.60, 37.33, 36.59])), readout(27.60, 27.00))  # one view under 37.3346
        self.assertFalse(d['chain_rule'])

    def test_kill_rules(self):
        d = s58de_decision(compare(views([36.58, 37.0, 36.60, 37.01, 36.59])), readout(27.60, 27.40))   # 4.2 us/layer < 5
        self.assertFalse(d['screen_winner']); self.assertTrue(any('us per layer' in k for k in d['kill_rules_fired']))
        d = s58de_decision(compare(views([36.58, 37.0, 35.99, 37.01, 36.59])), readout(27.60, 27.00))  # warm floor
        self.assertFalse(d['screen_winner']); self.assertTrue(any('36.0' in k for k in d['kill_rules_fired']))
        d = s58de_decision(compare(views([36.58, 38.2, 36.60, 38.2, 35.40])), readout(27.60, 27.00))   # drift 3.4 %
        self.assertFalse(d['screen_winner']); self.assertTrue(any('drift' in k for k in d['kill_rules_fired']))
        d = s58de_decision(compare(views([36.58, 37.0, 36.60, 37.01, 36.59])), readout(27.60, 27.00, b_fills=13.0))  # fills differ
        self.assertFalse(d['screen_winner']); self.assertFalse(d['fills_equal_across_arms']); self.assertTrue(any('moved bytes' in k for k in d['kill_rules_fired']))
        d = s58de_decision(compare(views([36.58, 37.0, 36.60, 37.01, 36.59])), dict(available=False))
        self.assertFalse(d['screen_winner']); self.assertIsNone(d['fills_equal_across_arms']); self.assertIsNone(d['gateup_saving_us_per_layer'])

    def test_order_and_exactness_refusals(self):
        v = views([36.58, 37.0, 36.60, 37.01, 36.59]); v[1]['view'] = 'max23'
        with self.assertRaises(ValueError): compare(v)
        v = views([36.58, 37.0, 36.60, 37.01, 36.59]); v[0]['view'] = 'max'
        with self.assertRaises(ValueError): compare(v)
        v = views([36.58, 37.0, 36.60, 37.01, 36.59]); v[2]['requests'][0]['exact_oracle'] = False
        with self.assertRaises(ValueError): compare(v)
        v = views([36.58, 37.0, 36.60, 37.01, 36.59]); v[4]['requests'][-1]['tokens'][-1] += 1
        with self.assertRaises(ValueError): compare(v)


if __name__ == '__main__':
    unittest.main()
