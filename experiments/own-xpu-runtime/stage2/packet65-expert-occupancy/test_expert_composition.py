"""Adversarial CPU fixtures for the in-composition class-screen gate."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import expert_composition as E


class CompositionTests(unittest.TestCase):
    def events(self, rank=0, duration=100):
        rows = []
        for fixture in E.FIXTURES:
            meta = dict(rank=rank, fixture=fixture, half=fixture, position=99+fixture, speculative=False)
            for layer in range(rank*24, (rank+1)*24):
                for component in E.COMPONENTS:
                    rows.append(dict(meta, schema='packet65.event.v1', label=f'blk.{layer}.{component}',
                                     event=len(rows)+1, start_ns=1, end_ns=duration+1, **{'class':'moe_experts'}))
            rows.append(dict(meta, schema='packet65.half.v1', cancelled=False))
        return rows

    def collect(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'sites.jsonl'
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            return E.collect_rank(path, 0)

    def test_complete_composition_and_cancelled_prefix(self):
        rows = self.events()
        # A later failed speculative prefix must never become a faster whole half.
        row = dict(rows[0], half=999, speculative=True, event=99999)
        rows += [row, dict(row, schema='packet65.half.v1', cancelled=True)]
        result = self.collect(rows)
        self.assertEqual(result['cancelled_half_count'], 1)
        self.assertEqual(result['selected'][9]['half'], 9)
        self.assertEqual(sum(result['sums'][9].values()), 24*7*100)

    def test_missing_component_and_duplicate_event_refuse(self):
        rows = self.events()
        with self.assertRaisesRegex(ValueError, 'missing/extra site'):
            self.collect([row for row in rows if row.get('label') != 'blk.0.moe'])
        with self.assertRaisesRegex(ValueError, 'duplicate event'):
            self.collect(rows+[dict(rows[0])])

    def test_last_complete_half_and_mismatched_position(self):
        rows = self.events()
        later = [dict(row, half=999, event=10000+i) for i,row in enumerate(rows)
                 if row['half'] == 9]
        result = self.collect(rows+later)
        self.assertEqual(result['selected'][9]['half'], 999)
        rows[0]['position'] += 1
        with self.assertRaisesRegex(ValueError, 'another half'):
            self.collect(rows)

    def run_fixture(self, choice='production', duration=100):
        prompts = ['prose','code','analysis','operations','documentation']
        attribution = {}
        for prompt in ['incident64']+prompts:
            ranks = {}
            for rank in (0,1):
                sums = {fixture:{f'blk.{layer}.{component}':duration
                    for layer in range(rank*24,(rank+1)*24) for component in E.COMPONENTS}
                    for fixture in E.FIXTURES}
                ranks[rank] = dict(sums=sums, signatures={fixture:{k:1 for k in rows} for fixture,rows in sums.items()},
                                   positions={fixture:100+fixture for fixture in E.FIXTURES})
            attribution[prompt] = ranks
        return dict(root=choice, selection=dict(choices=dict(experts=choice, hc='production'),draft={}),
            classes={p:p for p in prompts}, payloads={p:p for p in prompts}, attribution=attribution,
            identity=dict(placement={key:'same' for key in ('name','draft_rank','target_split','target_layers','context','memory_plan_sha256','rank_dispatch_sha256')},
                          binary_sha256='same',dispatch_sha256='same',memory_plan_sha256='same',profile='tp2',
                          timing='attribution',lane='A',conditions='same'),
            window=dict(boot_id='same',oracle_completion_sha256='same',environment={}), inputs_sha256={})

    def test_threshold_applies_broad_class_not_gemv_only(self):
        control = self.run_fixture()
        candidate = self.run_fixture('wg64', 70)
        self.assertTrue(E.compare(control,candidate)['passed'])
        self.assertFalse(E.compare(control,self.run_fixture('wg64',71))['passed'])
        candidate = self.run_fixture('wg64')
        for ranks in candidate['attribution'].values():
            for row in ranks.values():
                for labels in row['sums'].values():
                    for label in labels:
                        if label.endswith(('expsgate','expsdown')):
                            labels[label] = 50
        result = E.compare(control,candidate)
        self.assertFalse(result['passed'])
        self.assertAlmostEqual(result['latency_reduction_percent'],100/7)

    def test_unmatched_lane_or_outside_selection_change_refuses(self):
        control, candidate = self.run_fixture(), self.run_fixture('wg64', 60)
        candidate['identity']['lane'] = 'B'
        with self.assertRaisesRegex(ValueError, 'unmatched lane'):
            E.compare(control,candidate)
        candidate['identity']['lane'] = 'A'
        candidate['selection']['choices']['hc'] = 'other'
        with self.assertRaisesRegex(ValueError, 'outside experts'):
            E.compare(control,candidate)

    def test_partial_one_rank_gain_is_not_full_class_pass(self):
        control, candidate = self.run_fixture(), self.run_fixture('wg128', 50)
        for ranks in candidate['attribution'].values():
            for labels in ranks[1]['sums'].values():
                for label in labels:
                    labels[label] = 110
        self.assertFalse(E.compare(control,candidate)['passed'])


if __name__ == '__main__':
    unittest.main()
