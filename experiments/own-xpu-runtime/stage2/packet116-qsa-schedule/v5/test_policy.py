"""CPU refusal checks for the sole allowed runtime switch and kill gate."""
import copy,json,unittest
from unittest.mock import patch
from pathlib import Path
import bracket,bracket_job
from compare import qualify_rates
P=Path(__file__).resolve().parent
class Policy(unittest.TestCase):
 def setUp(self):
  self.a=json.loads((P/'lineage/selection.json').read_text())
  self.b=json.loads((P/'lineage/candidate.json').read_text())
 def test_only_schedule_changes(self):
  self.assertTrue(bracket.compatible([self.a,self.b,self.a,self.b,self.a]))
  self.b['choices']['qsa_schedule']='production';self.assertEqual(self.a,self.b)
 def test_foreign_target_fields_refuse(self):
  for field in self.a['choices']:
   if field=='qsa_schedule':continue
   b=copy.deepcopy(self.b);b['choices'][field]='changed'
   with self.subTest(field=field),self.assertRaises(Exception):bracket.compatible([self.a,b])
 def test_draft_changes_refuse(self):
  for field in self.a['draft']:
   b=copy.deepcopy(self.b);b['draft'][field]='changed'
   with self.subTest(field=field),self.assertRaises(Exception):bracket.compatible([self.a,b])
 def test_unregistered_schedule_refuses(self):
  self.b['choices']['qsa_schedule']='approximate'
  with self.assertRaises(Exception):bracket.compatible([self.a,self.b])
 def test_registered_five_views(self):
  c=bracket.load_config(P/'configs/bracket.json')
  self.assertEqual([v['choice'] for v in c['views']],['control','candidate','control','candidate','control'])
 def test_missing_micro_never_launches(self):
  with patch.object(bracket_job.subprocess,'run',side_effect=AssertionError('must refuse before identity child')):
   with self.assertRaises(Exception):bracket_job.micro_gate()
 def test_gain_boundary_and_stronger_control(self):
  self.assertTrue(qualify_rates([100.,100.,100.],[100.5,100.5])['candidate_qualified'])
  self.assertFalse(qualify_rates([100.,100.,100.],[100.49,101.])['candidate_qualified'])
  self.assertFalse(qualify_rates([100.,101.,100.],[101.,102.])['candidate_qualified'])
 def test_control_drift_and_invalid_rates_refuse(self):
  self.assertFalse(qualify_rates([100.,104.,100.],[110.,110.])['candidate_qualified'])
  with self.assertRaises(Exception):qualify_rates([100.,100.,100.],[float('nan'),110.])
if __name__=='__main__':
 from build_engine import limits
 limits();unittest.main()
