"""Analyzer tests on complete synthetic packet175 streams (no device data)."""
import json, math, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import micro_analyze as a

ROW = {0: ['hc_norm', '*hc_low_inject', '*hc_gate_mix', '*projection', '*projection', '*small_tuple', 'conv', 'gdn_recurrence',
           'gdn_norm_gate', '*attention_projection', '*attention_projection'],
       3: ['hc_norm', '*hc_low_inject', '*hc_gate_mix', '*projection', 'projection', '*projection', '*projection', '*projection',
           'qsa_prepare', 'qsa_pool', 'qsa_select', 'qsa_select', 'qsa_attention', 'qsa_attention', '*attention_projection',
           'attention_projection']}
FFN = ['hc_norm', '*hc_low_inject', '*hc_gate_mix', '*small_tuple', 'route_shared_activation', 'expert_gate_up',
       'expert_activation', 'expert_down', '*shared_down_mix', 'combine']


def fixture(path, reduction, warm_in_a=False, change_order=False, summary=None):
    """Arm A dense events 100 us each; arm B dense+warm totals (1-reduction) of A."""
    lines, t = [], 1_000_000
    for layer in a.LAYERS:
        for rep in range(a.REPEATS):
            for j in range(2):
                arm = (rep + j) % 2
                lines.append(dict(kind='oracle', layer=layer, position=31, repeat=rep, arm=arm, passed=True, compared_buffers=60))
                events = []
                for row in range(2):
                    events.append(('evict', 400_000))
                    for item in ROW[layer] + FFN:
                        warm_first = item.startswith('*')
                        cls = item.lstrip('*')
                        if cls in a.DENSE:
                            if warm_first and (arm == 1 or warm_in_a):
                                events.append(('warm', 2_000))
                            jitter = (rep % 7) * 100
                            events.append((cls, 100_000 + jitter if arm == 0 else 0))
                        else:
                            events.append((cls, 50_000))
                if change_order and arm == 1:
                    events.reverse()
                # Set B dense durations so (dense + warm) == (1 - reduction) * A for this repeat.
                if arm == 1:
                    n_dense = sum(1 for c, _ in events if c in a.DENSE)
                    warm = sum(d for c, d in events if c == 'warm')
                    a_total = sum(100_000 + (rep % 7) * 100 for c, _ in events if c in a.DENSE)
                    target = int(round((1 - reduction) * a_total)) - warm
                    base = target // n_dense
                    first = next(i for i, (c, _) in enumerate(events) if c in a.DENSE)
                    events = [(c, (base + (target - base * n_dense if i == first else 0)) if c in a.DENSE else d)
                              for i, (c, d) in enumerate(events)]
                for index, (cls, d) in enumerate(events):
                    lines.append(dict(kind='sample', layer=layer, position=31, repeat=rep, arm=arm, event=index, **{'class': cls},
                                      start_ns=t, end_ns=t + d))
                    t += d + 1_000
    lines.insert(0, dict(kind='bytes', layer=0, position=31, buffer='streams', compared_bytes=40960, different_bytes=0, sha256='0' * 64))
    s = dict(kind='summary', passed=True, drained=True, identity='iq3-p49-split32-v1', layer_complete=True,
             intermediate_checks_complete=True, zero_errors=True, finite_outputs=True, ab_byte_identical=True,
             cpu_oracle_match=True, backend='device')
    s.update(summary or {})
    lines.append(s)
    Path(path).write_text(''.join(json.dumps(x) + '\n' for x in lines))


class Analyzer(unittest.TestCase):
    def run_case(self, reduction, **kw):
        d = Path(tempfile.mkdtemp(prefix='p175-test-'))
        (d / 'DO-NOT-REPEAT.md').write_text('test\n')
        out = d / 'out'; out.mkdir()
        fixture(out / 'samples.jsonl', reduction, **kw)
        with patch.object(a, 'P', d):
            return a.evaluate(out), out, d

    def test_boundary_three_percent_is_eligible(self):
        r, out, d = self.run_case(0.03)
        self.assertTrue(r['eligible_combined_bundle9'])
        self.assertEqual(r['decision'], 'eligible for combined bundle-9')
        self.assertTrue((out / 'COMBINED-BUNDLE9-ELIGIBLE.md').exists())
        self.assertNotIn('D2 dense-weight', (d / 'DO-NOT-REPEAT.md').read_text())

    def test_just_below_closes(self):
        r, out, d = self.run_case(0.0295)
        self.assertFalse(r['eligible_combined_bundle9'])
        self.assertEqual(r['decision'], 'close D2')
        self.assertIn('D2 dense-weight L2 warm-ahead', (d / 'DO-NOT-REPEAT.md').read_text())
        self.assertFalse((out / 'COMBINED-BUNDLE9-ELIGIBLE.md').exists())

    def test_regression_and_projection(self):
        r, _, _ = self.run_case(-0.2)
        self.assertEqual(r['decision'], 'close D2')
        self.assertTrue(math.isclose(r['weighted_reduction'], -0.2, rel_tol=1e-3))
        self.assertTrue(math.isclose(r['projected_census_saving_ms'], -0.2 * 11.532, rel_tol=1e-3))
        self.assertLess(r['projected_token_gain_percent'], 0)
        for layer in r['layers'].values():
            self.assertGreater(layer['warm_b_prime_ms_per_row'], 0)

    def test_gain_mapping(self):
        self.assertTrue(math.isclose(a.gain_percent(0.550), 2.0))
        self.assertTrue(math.isclose(a.gain_percent(0.278), 1.0))
        self.assertTrue(math.isclose(a.gain_percent(0.07), 0.25))

    def test_rejects_warm_in_control(self):
        with self.assertRaises(ValueError):
            self.run_case(0.05, warm_in_a=True)

    def test_rejects_changed_launch_order(self):
        with self.assertRaises(ValueError):
            self.run_case(0.05, change_order=True)

    def test_rejects_failed_oracle_without_tails(self):
        with self.assertRaises(ValueError) as e:
            self.run_case(0.05, summary=dict(cpu_oracle_match=False))
        self.assertIn('oracle gate', str(e.exception))


if __name__ == '__main__':
    unittest.main()
