"""s185_decision on REAL device data: packet183's one-load bracket and packet153's summary.

* packet183 (2026-10-22, lane B, bundle 8): its 60 real request streams (decision-fixtures)
  through view_stats; its controls are exactly packet185's split-head `production` view.
  The S1 views are relabeled `unsplit` only to exercise the rule on real numbers: S1 slowed
  rank 1 by ~0.97 ms, so the rule must CLOSE (u > 0.39).
* packet153 (2026-10-19, lane B): its real bracket summary carries no interval statistics and
  is a one-load C/X/C/X/C bracket, so the decision must refuse it (INCOMPLETE, never GO);
  its real first-request stream (timing-fixture-p153b) still yields 63 exact intervals.
* packet106b (2026-10-18, bundle-6 era): the only retained device evidence of the un-split
  head next to the split head (fresh-load v4 grid); arithmetic reference, no p150 scopes.
Perturbations of the real numbers cover every GO/CLOSE branch.
"""
import copy, gzip, json, tempfile, unittest
from pathlib import Path
import s185_decision as s
from interval_model import intervals

P = Path(__file__).resolve().parent
FIX = P.parent / 'lineage-inputs/decision-fixtures'
SUMMARY183 = P.parent / 'lineage-inputs/packet183-own/v5/evidence/device-metadata-v5-B-p183/bracket-summary.json'
SUMMARY153 = P.parent / 'lineage-inputs/packet153-own/v5/evidence/device-static-v5-B-p153b/bracket-summary.json'


def load_gz(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def materialize(view, root):
    """Rebuild <view>/<prompt>/receipt.json and rank0/timings.jsonl from the frozen real streams."""
    prompts = []
    for prompt in sorted((FIX / 'packet183-v5' / view).iterdir()):
        dest = root / view / prompt.name
        (dest / 'rank0').mkdir(parents=True)
        (dest / 'receipt.json').write_text(json.dumps(load_gz(prompt / 'receipt.json.gz')))
        records = load_gz(prompt / 'rank0-scopes.json.gz')['records']
        (dest / 'rank0/timings.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
        prompts.append(prompt.name)
    return root / view, prompts


class Packet183Real(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.summary = json.loads(SUMMARY183.read_text())
        cls.views = sorted(p.name for p in (FIX / 'packet183-v5').iterdir())
        cls.stats = []
        for view in cls.views:
            directory, prompts = materialize(view, root)
            cls.prompts = prompts
            cls.stats.append(s.view_stats(directory, prompts, True))
        cls.rows = []
        for index, (row, stats) in enumerate(zip(cls.summary['views'], cls.stats)):
            cls.rows.append(dict(index=index, variant=s.ORDER[index], rate=row['rate'], all_13_exact=row['all_13_exact'],
                                 exact_count=row['exact_count'], draft_proposals=row['draft_proposals'],
                                 acceptance_counts=row['acceptance_counts'], interval_stats=stats))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_real_split_head_numbers(self):
        self.assertEqual(self.views, ['00-control', '01-candidate', '02-control', '03-candidate', '04-control'])
        for i in (0, 2, 4):
            st = self.stats[i]
            self.assertEqual((st['intervals'], st['hits'], st['misses']), (1188, 932, 256))
            self.assertAlmostEqual(st['hit']['D'], 1.597, delta=0.01)
            self.assertAlmostEqual(st['hit']['A'], 12.49, delta=0.03)
            self.assertAlmostEqual(st['hit']['B'], 13.147, delta=0.01)
            self.assertAlmostEqual(st['hit']['B_minus_A'], 0.66, delta=0.02)
            self.assertAlmostEqual(st['sigma_rank0_service_ms'], 0.403, delta=0.005)
            self.assertAlmostEqual(st['head_service_per_cycle_ms']['suffix_head'], 0.310, delta=0.003)

    def test_real_rule_closes_on_s1_rows(self):
        d = s.decide(self.rows)
        self.assertFalse(d['v3_go'])
        self.assertTrue(d['every_view_exact'] and d['draft_proposals_identical'] and d['acceptance_identical'])
        self.assertAlmostEqual(d['control_drift_percent'], self.summary['control_drift_percent'], places=9)
        self.assertGreater(d['u_rank1_unsplit_cost_ms'], 0.9)
        self.assertTrue(d['u_resolved'] is False or d['u_rank1_unsplit_cost_ms'] > s.U_MAX_MS)

    def perturbed(self, u=None, ba=None, rate=None, proposals=False, exact=True):
        rows = copy.deepcopy(self.rows)
        control_b = sum(rows[i]['interval_stats']['hit']['B'] for i in (0, 2, 4)) / 3
        for i in (1, 3):
            hit = rows[i]['interval_stats']['hit']
            hit['D'] = sum(rows[j]['interval_stats']['hit']['D'] for j in (0, 2, 4)) / 3
            if u is not None:
                hit['B'] = control_b + u
            if ba is not None:
                hit['B_minus_A'] = ba
        if rate is not None:
            rows[2]['rate'] *= rate
        if proposals:
            rows[3]['draft_proposals'] = dict(rows[3]['draft_proposals'], incident64={'rows': 0, 'sha256': 'x'})
        if not exact:
            rows[1]['exact_count'] = 12
        return rows

    def test_go_branch(self):
        d = s.decide(self.perturbed(u=0.20, ba=0.80))
        self.assertTrue(d['v3_go'])
        self.assertAlmostEqual(d['u_rank1_unsplit_cost_ms'], 0.20, places=9)
        self.assertTrue(d['u_resolved'])

    def test_close_branches(self):
        for kwargs in (dict(u=0.40, ba=0.80), dict(u=0.20, ba=0.59), dict(u=0.20, ba=0.80, rate=1.031),
                       dict(u=0.20, ba=0.80, proposals=True), dict(u=0.20, ba=0.80, exact=False)):
            with self.subTest(**kwargs):
                self.assertFalse(s.decide(self.perturbed(**kwargs))['v3_go'])

    def test_incomplete_never_go(self):
        for rows in (self.rows[:4], list(reversed(self.rows)),
                     [dict(r, variant='production') for r in self.rows]):
            d = s.decide_or_incomplete(rows)
            self.assertFalse(d['v3_go'])
            self.assertTrue(d['outcome'].startswith('INCOMPLETE'))

    def test_view_stats_refusals(self):
        with tempfile.TemporaryDirectory() as t:
            directory, prompts = materialize('00-control', Path(t))
            with self.assertRaisesRegex(s.Incomplete, 'unsplit view must not run a rank-0 suffix service'):
                s.view_stats(directory, prompts, False)
            for prompt in prompts:
                path = directory / prompt / 'rank0/timings.jsonl'
                rows = [json.loads(x) for x in path.read_text().splitlines()]
                path.write_text(''.join(json.dumps(r) + '\n' for r in rows if r['p150_segment'] not in s.HEAD_SCOPES))
            self.assertIsNone(s.view_stats(directory, prompts, False)['sigma_rank0_service_ms'])
            with self.assertRaisesRegex(s.Incomplete, 'split view must record'):
                s.view_stats(directory, prompts, True)
            (directory / prompts[0] / 'receipt.json').unlink()
            with self.assertRaisesRegex(s.Incomplete, 'missing request receipt'):
                s.view_stats(directory, prompts, False)


class Packet153Real(unittest.TestCase):
    def test_real_summary_is_refused(self):
        summary = json.loads(SUMMARY153.read_text())
        self.assertTrue(summary['passed'])
        d = s.decide_or_incomplete(KeyError('interval_stats') if 'interval_stats' not in summary else [s.row_record(summary)])
        self.assertFalse(d['v3_go'])
        with self.assertRaises((KeyError, ValueError)):
            s.row_record(summary)

    def test_real_first_request_intervals(self):
        fixture = P.parent / 'lineage-inputs/timing-fixture-p153b/receipt.json.gz'
        r = load_gz(fixture)
        rows = intervals(r)
        self.assertEqual(len(rows), 63)
        self.assertTrue(all(x['B'] > 10 and x['D'] > 1 for x in rows))


class Packet106bReal(unittest.TestCase):
    def test_historical_fresh_load_unsplit_arithmetic(self):
        arms = {}
        for arm in sorted((FIX / 'packet106b-v4').iterdir()):
            rows, variant = [], None
            for prompt in sorted(arm.iterdir()):
                r = load_gz(prompt / 'receipt.json.gz')
                variant = r['variant']
                rows += intervals(r)
            hits = [x for x in rows if x['hit']]
            arms[arm.name] = (variant, dict(hit=dict(B=sum(x['B'] for x in hits) / len(hits), D=sum(x['D'] for x in hits) / len(hits),
                B_minus_A=sum(x['B'] - x['A'] for x in hits) / len(hits), B_minus_A_p10=0.,
                rank0_slack=sum(x['rank0_slack_ms'] for x in hits) / len(hits), elapsed=sum(x['elapsed_ms'] for x in hits) / len(hits)),
                miss=dict(elapsed=0.), sigma_rank0_service_ms=None, head_service_per_cycle_ms=dict(suffix_head=0.)))
        controls = [v for k, (variant, v) in arms.items() if variant == 'production']
        unsplit = [v for k, (variant, v) in arms.items() if variant == 'unsplit']
        self.assertEqual((len(controls), len(unsplit)), (1, 2))
        m = s.measure(controls, unsplit)
        # Split arm coupled at A + 0.48: u is only a lower bound on that line; un-split B-A ~0.53.
        self.assertGreater(m['u_rank1_unsplit_cost_ms'], 0.0)
        self.assertLess(m['u_rank1_unsplit_cost_ms'], 0.2)
        self.assertAlmostEqual(m['decoupled_B_minus_A_ms'], 0.525, delta=0.03)
        self.assertAlmostEqual(controls[0]['hit']['B_minus_A'], 0.480, delta=0.02)
        print('P106B_REFERENCE=' + json.dumps({k: m[k] for k in ('u_rank1_unsplit_cost_ms', 'u_draft_corrected_ms', 'decoupled_B_minus_A_ms', 'control_B_minus_A_ms')}))


if __name__ == '__main__':
    unittest.main()
