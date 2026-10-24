import importlib.util,unittest
from pathlib import Path
from unittest.mock import patch
s=importlib.util.spec_from_file_location('gsq_class_profile_test',Path(__file__).with_name('profile.py'));P=importlib.util.module_from_spec(s);s.loader.exec_module(P)
class ProfileTests(unittest.TestCase):
 def test_only_timing_value_changes_for_both_ranks(self):
  plan=dict(output='/tmp/control/ranks',evidence_output='/tmp/evidence',binary='/fixed/native',context=4096,seconds=3600,max_new=128,mini=False)
  for rank in (0,1):
   before=P.TOKEN_COMMAND(plan,rank,11,12);after=P.command(plan,rank,11,12)
   self.assertEqual(len(before),len(after));self.assertEqual([i for i,(a,b) in enumerate(zip(before,after)) if a!=b],[before.index('--timing')+1])
   self.assertEqual(after[after.index('--timing')+1],'class');self.assertNotIn('--record',after)
   if rank==0:self.assertIn('--draft-mtp',after)
 def test_changed_frozen_dependency_refuses(self):
  with patch.object(P,'sha',return_value='wrong'):
   with self.assertRaisesRegex(ValueError,'dependency changed'):P.verify_sources()
 def test_actual_source_pins(self):P.verify_sources()
if __name__=='__main__':unittest.main()
