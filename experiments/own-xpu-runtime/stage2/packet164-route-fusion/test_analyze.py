"""Corrupt actual retained event streams; synthetic times never qualify the packet."""
import copy
import json
import unittest
from analyze import events_report, jsonl, read, price


class Events(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=jsonl('p141-events.jsonl')
        cls.plan=json.loads(read('probe-plan.json'))
        cls.halves=jsonl('p141-halves.jsonl')
        cls.actual=jsonl('p141-touch-plan.jsonl')

    def report(self, rows=None, plan=None, halves=None, actual=None):
        return events_report(rows if rows is not None else self.rows,
                             plan if plan is not None else self.plan,
                             halves if halves is not None else self.halves,
                             actual if actual is not None else self.actual)

    def test_real_stream(self):
        r=self.report()
        self.assertAlmostEqual(r['aggregate']['a']['route_ms'],.792448)
        self.assertEqual(len(r['declared_actual_plan_mismatches']),31)
        self.assertTrue(r['diagnostic_only'])
        self.assertFalse(r['original_p141_analyzer_passed'])
        self.assertTrue(all(v is None for v in r['phase_ms'].values()))
        self.assertEqual(len(r['samples']),24)

    def test_missing_event(self):
        with self.assertRaisesRegex(ValueError,'sequence'):self.report(self.rows[1:])

    def test_duplicate_event(self):
        with self.assertRaises(ValueError):self.report([self.rows[0]]+self.rows)

    def test_bad_label(self):
        rows=copy.deepcopy(self.rows);rows[0]['label']='blk.0.route'
        with self.assertRaisesRegex(ValueError,'label'):self.report(rows)

    def test_reversed_clock(self):
        rows=copy.deepcopy(self.rows);rows[0]['end_ns']=rows[0]['start_ns']-1
        with self.assertRaisesRegex(ValueError,'clocks'):self.report(rows)

    def test_missing_half(self):
        with self.assertRaisesRegex(ValueError,'coverage'):self.report([r for r in self.rows if not(r['block']==0 and r['arm']=='natural')])

    def test_wrong_warmup(self):
        rows=copy.deepcopy(self.rows)
        next(r for r in rows if r['arm']=='b' and r['repeat']==0)['warmup']=False
        with self.assertRaisesRegex(ValueError,'flags'):self.report(rows)

    def test_failed_equality(self):
        halves=copy.deepcopy(self.halves);halves[0]['routes_equal']=False
        with self.assertRaisesRegex(ValueError,'equality'):self.report(halves=halves)

    def test_route_extra_launch(self):
        actual=copy.deepcopy(self.actual)
        route=next(r['site'] for r in self.plan['sites'] if r['class']=='route')
        next(r for r in actual if r['site']==route)['kernel_count']=2
        with self.assertRaisesRegex(ValueError,'sequence'):self.report(actual=actual)

    def test_price_real_records(self):
        result=price(.792448,.535729)
        self.assertAlmostEqual(result['onecard_baseline_tok_s'],31.966819787781944)
        self.assertAlmostEqual(result['twocard_baseline_tok_s'],58.798108759182306)
        scenario=next(x for x in result['scenarios'] if x['assumption']=='all_route_and_fused_router_vanish' and x['transfer']==.2)
        self.assertLess(scenario['onecard_gain_percent'],2)
        self.assertFalse(result['measured_speed_claim'])


if __name__=='__main__':unittest.main()
