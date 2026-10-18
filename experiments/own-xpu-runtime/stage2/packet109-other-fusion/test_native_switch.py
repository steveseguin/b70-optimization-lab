"""The Python admission matches the new, strictly narrower native switch."""
import copy,unittest
from unittest.mock import patch
import bracket
from common import HERE,read
class NativeSwitchTests(unittest.TestCase):
 def setUp(self):self.base=read(HERE/'lineage/selection.json')
 def test_only_registered_fusion_switch(self):
  for value in ('production','fused'):
   row=copy.deepcopy(self.base);row['choices']['other_fusion']=value
   self.assertTrue(bracket.compatible([self.base,row,self.base]))
 def test_every_other_field_fixed(self):
  for section in ('choices','draft'):
   for key in self.base[section]:
    row=copy.deepcopy(self.base);row[section][key]='unknown'
    with self.subTest(section=section,key=key),self.assertRaises(ValueError):bracket.compatible([self.base,row])
 def test_registered_five_views(self):
  config=bracket.load_config(HERE/'configs/bracket.json')
  self.assertEqual([r['choice'] for r in config['views']],['control','candidate','control','candidate','control'])
  for view in config['views']:
   row=read(view['selection']);self.assertEqual(row['choices']['experts'],'exp-halfcache+down-tile16')
 def test_lane_a_refuses_before_worker(self):
  import bracket_job
  with patch('cpu_seal.verify'),patch.object(bracket_job.screen,'main') as launch:
   with self.assertRaisesRegex(ValueError,'lane B only'):bracket_job.main(['--lane','A','--output','/unused','--plan'])
   launch.assert_not_called()
 def test_device_needs_authorization(self):
  import bracket_job
  with patch('cpu_seal.verify'),patch.object(bracket_job.screen,'main') as launch:
   with self.assertRaisesRegex(ValueError,'authorization'):bracket_job.main(['--lane','B','--output','/unused'])
   launch.assert_not_called()
 def test_plan_no_device_receipt_needed(self):
  import bracket_job
  with patch('cpu_seal.verify'),patch.object(bracket_job.screen,'main',return_value=0) as launch:
   self.assertEqual(bracket_job.main(['--lane','B','--output','/unused','--plan']),0)
   self.assertIn('--plan',launch.call_args.args[0])
if __name__=='__main__':unittest.main()
