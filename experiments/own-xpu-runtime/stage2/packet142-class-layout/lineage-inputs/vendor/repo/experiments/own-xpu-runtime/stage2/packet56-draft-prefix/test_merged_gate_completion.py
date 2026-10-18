"""A partial campaign never seals as passed, even with only passing rows."""
import unittest
from pathlib import Path
from unittest.mock import patch
from cpu_merged_gate import Campaign

class Completion(unittest.TestCase):
 def campaign(self):
  c=Campaign.__new__(Campaign)
  c.completed=False;c.campaign_error=None;c.rows=[dict(passed=True)]
  c.build={};c.source_pins={};c.affinity=[];c.peak_anon=0;c.anonymous_limit=8_000_000_000;c.receipt=Path('/not-written')
  return c
 def test_incomplete_and_interrupted(self):
  c=self.campaign()
  with patch('cpu_merged_gate.pipe.save'):
   self.assertFalse(c.seal()['passed'])
   c.campaign_error='stale source before next launch';r=c.seal()
   self.assertFalse(r['passed']);self.assertFalse(r['completed']);self.assertEqual(r['campaign_error'],c.campaign_error)
 def test_completed_cases_required(self):
  c=self.campaign();c.completed=True
  with patch('cpu_merged_gate.pipe.save'):
   self.assertTrue(c.seal()['passed'])
   c.rows.append(dict(passed=False));self.assertFalse(c.seal()['passed'])
   c.rows=[];self.assertFalse(c.seal()['passed'])
if __name__=='__main__':unittest.main()
