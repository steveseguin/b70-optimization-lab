"""Real-parent regression and corruption tests; no synthetic speed evidence."""
import copy
import gzip
import json
import math
import unittest

import analyze as a
import scopes as s
from audit import guard


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.req,cls.originals=a.record()
        cls.r=next(iter(cls.originals.values()))
        bound=a.load(a.S/'packet156-draft-slack/evidence/bracket-bound.json')
        ent=next(e for e in bound['inputs'] if '/rank1/timings.jsonl' in e['source'])
        cls.raw=gzip.decompress(a.read(a.S/'packet156-draft-slack'/ent['retained'],ent['retained_sha256']))
        cls.stream=s.stream(cls.raw,1)

    def test_record_metric(self):
        self.assertAlmostEqual(a.aggregate(self.req,a.model),58.798108759182306,places=10)

    def test_exact_intervals(self):
        self.assertEqual(sum(len(rr) for _,rr in self.req),1188)
        self.assertTrue(all(abs(a.model(r)-r['elapsed_ms'])<1e-7 for _,rr in self.req for r in rr))

    def test_actual_hit_miss_dependencies(self):
        rows=[r for _,rr in self.req for r in rr]
        self.assertEqual(sum(r['ready_critical']=='draft' for r in rows),932)
        self.assertEqual(sum(r['race_critical']=='B_including_suffix' for r in rows),1188)

    def test_early_A_is_not_D_removal(self):
        self.assertEqual(a.scenario(self.req,lambda r:a.model(r,a=r['D']))['gain_percent'],0.)
        self.assertGreater(a.scenario(self.req,lambda r:a.model(r,d=r['D']))['gain_percent'],7.)

    def test_draft_is_hidden_on_miss(self):
        for _,rr in self.req:
            for r in rr:
                if not r['hit']:self.assertEqual(a.model(r,d=r['D']),a.model(r))

    def test_three_percent_threshold(self):
        self.assertAlmostEqual(a.threshold(self.req,'d'),.6284513455324676,places=10)

    def test_missing_class_refused(self):
        with self.assertRaises(ValueError):a.aggregate(self.req[:2],a.model)

    def test_cached_parent_refused(self):
        r=copy.deepcopy(self.r);r['cached_tokens']=1
        with self.assertRaises(ValueError):a.validate_request(r)

    def test_wrong_identity_refused(self):
        r=copy.deepcopy(self.r);r['arithmetic']='other'
        with self.assertRaises(ValueError):a.validate_request(r)

    def test_duplicate_command_refused(self):
        r=copy.deepcopy(self.r);r['rank_trace'].append(r['rank_trace'][0])
        with self.assertRaises(ValueError):a.validate_request(r)

    def test_nan_clock_refused(self):
        r=copy.deepcopy(self.r);r['generated_token_completion_timestamps'][0]=math.nan
        with self.assertRaises(ValueError):a.validate_request(r)

    def test_reversed_clock_refused(self):
        r=copy.deepcopy(self.r);r['rank_trace'][0]['rank_completed']=0.
        with self.assertRaises(ValueError):a.validate_request(r)

    def test_empty_scopes_refused(self):
        with self.assertRaises(ValueError):s.stream(b'',1)

    def test_missing_scope_refused(self):
        rows=[r for r in self.stream if r['p154_segment']!='draft_issue']
        with self.assertRaises(ValueError):s.stream(('\n'.join(json.dumps(r) for r in rows)).encode(),1)

    def test_duplicate_scope_refused(self):
        with self.assertRaises(ValueError):s.stream(self.raw+b'\n'+json.dumps(self.stream[0]).encode(),1)

    def test_wrong_rank_refused(self):
        with self.assertRaises(ValueError):s.stream(self.raw,0)

    def test_nested_partition_conserves_real_host_time(self):
        row=next(r for r in self.stream if r['p154_segment']=='b_issue')
        parts=s.partition(row['start'],row['end'],self.stream)
        self.assertAlmostEqual(sum(parts.values()),(row['end']-row['start'])*1000,places=8)

    def test_exchange_delta_from_actual_controls(self):
        d=a.inputs149()
        self.assertAlmostEqual(d['candidate_extra_ms'][0],7.685005538771399,places=9)
        self.assertAlmostEqual(d['candidate_extra_ms'][1],7.697146022155085,places=9)


if __name__=='__main__':
    guard()
    unittest.main()
