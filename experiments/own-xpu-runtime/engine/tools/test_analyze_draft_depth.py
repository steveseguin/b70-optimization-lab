import unittest

from analyze_draft_depth import analyze


def fixture():
    prompt, tokens = [10, 11], [20, 21, 22, 23]
    guesses = [[20, 21, 99], [99, 22, 23], [22, 23, 24], [23, 24, 25]]
    native = dict(tokens=tokens, draft_rows=[dict(position=i + 2, guess=g[0], actual=tokens[i], provider_error=0)
                                           for i, g in enumerate(guesses)])
    rows = [dict(schema='ownrt.draft-depth.cycle.v1', request_output='request/rank0', rank=0,
                 confirmed_position=i + 1, confirmed_token=(prompt + tokens)[i + 1], d1_position=i + 2,
                 requested_depth=3, guesses=g, extra_pass_wall_ms=[1.0, 2.0], snapshot_ms=0.1,
                 restore_ms=0.2, probe_total_ms=3.3, snapshot_bytes=1024,
                 restored_position=i + 1, restored_extent=32, mutable_bytes_verified=True,
                 discarded=True, diagnostic_only=True) for i, g in enumerate(guesses)]
    return prompt, native, rows


class DepthAnalysisTests(unittest.TestCase):
    def test_conditional_rates_and_censoring(self):
        result = analyze(*fixture(), require_verified=True)
        first, second, third = [result['conditional_depth'][str(i)] for i in (1, 2, 3)]
        self.assertEqual((first['eligible'], first['accepted']), (4, 3))
        self.assertEqual((second['eligible'], second['accepted'], second['prior_rejected'], second['censored']), (2, 2, 1, 1))
        self.assertEqual((third['eligible'], third['accepted'], third['prior_rejected'], third['censored']), (1, 0, 1, 2))
        self.assertEqual(result['mutable_bytes_verified_cycles'], 4)

    def test_missing_duplicate_or_shifted_rows_refuse(self):
        prompt, native, rows = fixture()
        for broken in (rows[:-1], rows + rows[:1]):
            with self.assertRaises(ValueError):
                analyze(prompt, native, broken)
        rows[0]['d1_position'] += 1
        with self.assertRaises(ValueError):
            analyze(prompt, native, rows)

    def test_mismatched_prefix_and_controller_refuse(self):
        for field, value in [('confirmed_token', 999), ('confirmed_position', 99),
                             ('restored_position', 99), ('snapshot_bytes', 33 * 1024**2),
                             ('extra_pass_wall_ms', [float('nan'), 1]), ('request_output', 'other-request')]:
            prompt, native, rows = fixture()
            rows[0][field] = value
            with self.assertRaises(ValueError, msg=field):
                analyze(prompt, native, rows)
        prompt, native, rows = fixture()
        native['draft_rows'][0]['guess'] = 777
        with self.assertRaises(ValueError):
            analyze(prompt, native, rows)

    def test_partial_capacity_and_depth_two(self):
        prompt, native, rows = fixture()
        for row in rows:
            row['requested_depth'] = 2
            row['guesses'] = row['guesses'][:2]
            row['extra_pass_wall_ms'] = [1]
        rows[-1]['guesses'] = rows[-1]['guesses'][:1]
        rows[-1]['extra_pass_wall_ms'] = []
        result = analyze(prompt, native, rows)
        self.assertEqual(result['conditional_depth']['3']['unavailable'], 4)
        self.assertEqual(result['conditional_depth']['2']['unavailable'], 1)

    def test_restoration_verification_can_be_required(self):
        prompt, native, rows = fixture()
        rows[0]['mutable_bytes_verified'] = False
        self.assertEqual(analyze(prompt, native, rows)['mutable_bytes_verified_cycles'], 3)
        with self.assertRaises(ValueError):
            analyze(prompt, native, rows, require_verified=True)

    def test_output_only_join_is_explicit_and_requires_complete_positions(self):
        prompt, native, rows = fixture()
        del native['draft_rows']
        with self.assertRaises(ValueError):
            analyze(prompt, native, rows)
        result = analyze(prompt, native, rows, allow_output_only=True)
        self.assertEqual(result['alignment'], 'request-position-and-output-only')
        self.assertEqual(result['conditional_depth']['2']['accepted'], 2)
        with self.assertRaises(ValueError):
            analyze(prompt, native, rows[:-1], allow_output_only=True)


if __name__ == '__main__':
    unittest.main()
