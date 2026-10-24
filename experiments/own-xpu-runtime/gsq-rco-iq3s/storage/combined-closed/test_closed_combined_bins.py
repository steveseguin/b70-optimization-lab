import copy,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import closed_combined_bins as A

class CombinedArchive(unittest.TestCase):
 def test_actual_closed_index_complete_partition(self):
  p=A.plan();self.assertFalse(p['operations_performed']);self.assertEqual(27,len(p['batches']));self.assertEqual(57051,p['files']);self.assertEqual(6248947500,p['bytes']);self.assertEqual(249800772,p['conservative_container_bytes']);self.assertEqual(256*1024**2,p['archive_quota_per_batch']);self.assertEqual(['initial','warmup-none','warmup-mtp'],[x['name'] for x in p['batches'][:3]])
 def test_job_is_exact_frozen_filesystem_implementation(self):
  rows=A.read_authority()
  with patch.object(A,'read_authority',return_value=rows):j=A.authority(26)
  self.assertIs(type(j),A.B.Job);self.assertEqual(2113,len(j.rows));self.assertEqual(231442500,sum(x['bytes'] for x in j.rows.values()));self.assertEqual('prompt-11-none',j.authority['name']);self.assertEqual(set(),j.preserve);self.assertEqual(256*1024**2,j.cap);self.assertEqual(27000000000+64*1024**2,j.floor)
 def test_invalid_batch_and_incomplete_group_refuse(self):
  for i in (-1,27,True):
   with self.assertRaises(ValueError):A.select_batch({},i)
   with self.assertRaises(ValueError):A.remote(i)
  with self.assertRaisesRegex(ValueError,'complete target'):A.select_batch({'unindexed/x.bin':{'bytes':1}},0)
 def test_changed_hash_authority_refuses(self):
  with patch.object(A.B,'sha',return_value='0'*64),self.assertRaisesRegex(ValueError,'immutable'):A.read_authority()
 def test_failed_or_retained_terminal_refuses(self):
  r=json.loads((A.AUDIT/'review.json').read_text());t=json.loads((A.CONTROL/'terminal.json').read_text());A.validate_closure(r,t)
  for key,value in [('passed',False),('children_exited',False),('target_descriptors_empty',False),('first_error','write failure'),('plan_sha256','0'*64)]:
   bad=copy.deepcopy(t);bad[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):A.validate_closure(r,bad)
  bad=copy.deepcopy(r);bad['owners'][0]['live_bytes']=1
  with self.assertRaisesRegex(ValueError,'safe native'):A.validate_closure(bad,t)
 def test_quota_overflow_before_any_write(self):
  b=A.B.Budget(Path('/irrelevant'),A.CAP,A.FLOOR)
  with patch.object(A.B.shutil,'disk_usage',return_value=types.SimpleNamespace(free=A.FLOOR+A.CAP)):
   b.before(A.CAP)
   with self.assertRaisesRegex(ValueError,'quota'):b.before(1)
  self.assertEqual(A.CAP,b.written)
 def test_previous_batch_must_be_released(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(A,'DEST',Path(tmp)/'fixed'):
   A.prepare_destination(0)
   with self.assertRaises(FileNotFoundError):A.prepare_destination(1)
   d=A.DEST/'chunk-00';d.mkdir();j=dict(passed=True,authority=dict(profile='combined',batch=0,helper_sha256=A.B.sha(A.__file__),filesystem_helper_sha256=A.HELPER_SHA,archive_quota=A.CAP,terminal_sha256=A.TERMINAL_SHA))
   (d/'local-release-verified.json').write_text(json.dumps(j));A.prepare_destination(1)
   j['authority']['terminal_sha256']='0'*64;(d/'local-release-verified.json').write_text(json.dumps(j))
   with self.assertRaisesRegex(ValueError,'prior batch'):A.prepare_destination(1)
if __name__=='__main__':unittest.main(verbosity=2)
