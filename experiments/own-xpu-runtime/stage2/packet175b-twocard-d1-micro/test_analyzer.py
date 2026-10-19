"""Analyzer tests on complete synthetic packet175b streams (no device data)."""
import json, math, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import micro_analyze as a

ROW = {0: ['hc_norm', 'hc_low_inject', 'hc_gate_mix', 'projection', 'projection', 'small_tuple', 'conv', 'gdn_recurrence',
           'gdn_norm_gate', 'attention_projection', 'attention_projection'],
       3: ['hc_norm', 'hc_low_inject', 'hc_gate_mix', 'projection', 'projection', 'projection', 'projection', 'projection',
           'qsa_prepare', 'qsa_pool', 'qsa_select', 'qsa_select', 'qsa_attention', 'qsa_attention', 'attention_projection',
           'attention_projection']}
FFN = ['hc_norm', 'hc_low_inject', 'hc_gate_mix', 'small_tuple', 'route_shared_activation', 'expert_gate_up',
       'expert_activation', 'expert_down', 'shared_down_mix', 'combine']


def fixture(path, ratio, warm_in=(), change_order=False, summary=None):
    """Arm A dense events 100 us (+jitter) each; arm B dense events total ratio * A for each repeat."""
    lines, t = [], 1_000_000
    for layer in a.LAYERS:
        for rep in range(a.REPEATS):
            for j in range(2):
                arm = (rep + j) % 2
                lines.append(dict(kind='oracle', layer=layer, position=31, repeat=rep, arm=arm, passed=True, compared_buffers=60))
                events = []
                for row in range(2):
                    events.append(('evict', 400_000))
                    for cls in ROW[layer] + FFN:
                        if cls in a.DENSE:
                            if arm in warm_in:
                                events.append(('warm', 2_000))
                            events.append((cls, 100_000 + (rep % 7) * 100))
                        else:
                            events.append((cls, 50_000))
                if change_order and arm == 1:
                    events.reverse()
                if arm == 1:
                    n_dense = sum(1 for c, _ in events if c in a.DENSE)
                    a_total = sum(d for c, d in events if c in a.DENSE)
                    target = int(round(ratio * a_total))
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
             cpu_oracle_match=True, backend='device', variant=a.VARIANT)
    s.update(summary or {})
    lines.append(s)
    Path(path).write_text(''.join(json.dumps(x) + '\n' for x in lines))


class Analyzer(unittest.TestCase):
    def run_case(self, ratio, **kw):
        d = Path(tempfile.mkdtemp(prefix='p175b-test-'))
        (d / 'DO-NOT-REPEAT.md').write_text('test\n')
        out = d / 'out'; out.mkdir()
        fixture(out / 'samples.jsonl', ratio, **kw)
        with patch.object(a, 'P', d):
            return a.evaluate(out), out, d

    def test_boundary_097_is_eligible(self):
        r, out, d = self.run_case(0.97)
        self.assertTrue(r['eligible_combined_bundle9'])
        self.assertEqual(r['decision'], 'eligible for the combined bundle-9 candidate')
        self.assertTrue((out / 'COMBINED-BUNDLE9-ELIGIBLE.md').exists())
        self.assertNotIn('D1 same-bit', (d / 'DO-NOT-REPEAT.md').read_text())

    def test_just_above_closes(self):
        r, out, d = self.run_case(0.9705)
        self.assertFalse(r['eligible_combined_bundle9'])
        self.assertEqual(r['decision'], 'close D1')
        self.assertIn('D1 same-bit scale-word multicast', (d / 'DO-NOT-REPEAT.md').read_text())
        self.assertFalse((out / 'COMBINED-BUNDLE9-ELIGIBLE.md').exists())

    def test_regression_projection_and_spread(self):
        r, _, _ = self.run_case(1.2)
        self.assertEqual(r['decision'], 'close D1')
        self.assertTrue(math.isclose(r['weighted_b_over_a'], 1.2, rel_tol=1e-3))
        self.assertTrue(math.isclose(r['projected_census_saving_ms'], -0.2 * 11.532, rel_tol=1e-3))
        self.assertLess(r['projected_token_gain_percent'], 0)
        for layer in r['layers'].values():
            self.assertLessEqual(layer['paired_ratio_p10'], layer['paired_ratio_median'])
            self.assertLessEqual(layer['paired_ratio_median'], layer['paired_ratio_p90'])

    def test_gain_mapping(self):
        self.assertTrue(math.isclose(a.gain_percent(0.550), 2.0))
        self.assertTrue(math.isclose(a.gain_percent(0.278), 1.0))
        self.assertTrue(math.isclose(a.gain_percent(0.07), 0.25))

    def test_rejects_warm_ahead_stream(self):
        # A packet175 (D2) stream has warm events in arm B; it is not D1 evidence.
        with self.assertRaises(ValueError):
            self.run_case(0.9, warm_in=(1,))

    def test_rejects_changed_launch_order(self):
        with self.assertRaises(ValueError):
            self.run_case(0.9, change_order=True)

    def test_rejects_failed_oracle_without_tails(self):
        with self.assertRaises(ValueError) as e:
            self.run_case(0.9, summary=dict(cpu_oracle_match=False))
        self.assertIn('oracle gate', str(e.exception))

    def test_rejects_missing_variant(self):
        with self.assertRaises(ValueError) as e:
            self.run_case(0.9, summary=dict(variant=None))
        self.assertIn('variant', str(e.exception))


if __name__ == '__main__':
    unittest.main()
