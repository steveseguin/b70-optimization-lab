"""Reject incomplete, reordered-identity or malformed diagnostic evidence on CPU."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import p56_head_summary as summary
import p56_head_window as window

class HeadEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='p56-head-cpu-')
        self.path=Path(self.tmp.name)
        self.sizes=(32768,65536,98304,91392,248320)
        self.receipt=dict(schema='packet56.head-fixture.v1',passed=True,device_executed=True,card=0,
                          iterations=100,checks=540,full_rows=248320,chosen_rows=91392,
                          head_bytes=839321600,weight_copies=1,
                          teardown=dict(safe_to_exit=True,exit_code=0,in_flight=0))
        self.comparisons=[dict(iteration=i,rows=n,bytes_equal=True,argmax_equal=True,argmax=0,prefix_sha256='0'*64)
                          for i in range(108) for n in self.sizes]
        self.events=[dict(iteration=i,rows=n,head_us=10.,argmax_us=2.,total_us=12.,bytes_equal=True,argmax_equal=True)
                     for i in range(100) for n in self.sizes]
    def tearDown(self): self.tmp.cleanup()
    def run_summary(self):
        (self.path/'receipt.json').write_text(json.dumps(self.receipt))
        for name,rows in [('comparisons',self.comparisons),('events',self.events)]:
            (self.path/(name+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows))
        return summary.summarize(self.path)
    def test_complete(self):
        row=self.run_summary();self.assertTrue(row['passed']);self.assertEqual(len(row['rows']),5)
    def test_missing_event(self):
        self.events.pop()
        with self.assertRaises(ValueError):self.run_summary()
    def test_duplicate_event(self):
        self.events[-1]=self.events[0]
        with self.assertRaises(ValueError):self.run_summary()
    def test_suffix_wrong_rows(self):
        self.comparisons[0]['rows']=91391
        with self.assertRaises(ValueError):self.run_summary()
    def test_nan_time(self):
        self.events[0]['head_us']=float('nan')
        with self.assertRaises(ValueError):self.run_summary()
    def test_unsafe_teardown(self):
        self.receipt['teardown']['in_flight']=1
        with self.assertRaises(ValueError):self.run_summary()
    def test_wrong_argmax(self):
        self.comparisons[0]['argmax_equal']=False
        with self.assertRaises(ValueError):self.run_summary()
    def test_bad_component_sum(self):
        self.events[0]['total_us']=15.
        with self.assertRaises(ValueError):self.run_summary()
    def test_false_byte_identity(self):
        self.comparisons[0]['bytes_equal']=False
        with self.assertRaises(ValueError):self.run_summary()
    def test_authorization_before_device(self):
        with patch.object(window.SUPERVISION,'journal',side_effect=AssertionError('journal must not run')):
            with self.assertRaises((RuntimeError,ValueError)):
                window.main(['--card','0','--output',str(self.path/'never')])
        self.assertFalse((self.path/'never').exists())

if __name__=='__main__':unittest.main()
