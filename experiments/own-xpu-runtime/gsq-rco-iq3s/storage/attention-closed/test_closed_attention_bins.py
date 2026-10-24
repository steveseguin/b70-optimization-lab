import gzip,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import closed_attention_bins as A
B=A.B
class AttentionStorage(unittest.TestCase):
 def test_actual_authority_only_local_indices(self):
  p=A.plan();self.assertEqual(14,len(p['profiles']['prefix']['batches']));self.assertEqual(13,len(p['profiles']['completion']['batches']))
  self.assertEqual(29512,p['profiles']['prefix']['files']);self.assertEqual(27469,p['profiles']['completion']['files']);self.assertFalse(p['operations_performed'])
  self.assertEqual('prompt-06-mtp',p['profiles']['prefix']['batches'][-1]['name']);self.assertEqual('prompt-07-mtp',p['profiles']['completion']['batches'][3]['name'])
 def test_path_and_failed_group_refusals(self):
  with self.assertRaises(ValueError):A.normalize('prefix',dict(path='/mnt/usb-models/own-xpu-runtime-results/gsq-attention-p33-a-evil/x.bin'))
  with self.assertRaises(ValueError):A.normalize('completion',dict(root='evidence',path='../x.bin'))
  self.assertIsNone(A.normalize('completion',dict(root='control',path='x.bin')))
  self.assertIsNone(A.normalize('completion',dict(root='evidence',path='failure.json')))
  for n in (-1,14,True):
   with self.assertRaises(ValueError):A.select_batch('prefix',{},n)
  with self.assertRaises(ValueError):A.select_batch('prefix',{'prompt-07-mtp/rank0/state-2147483647/x.bin':dict(bytes=1,sha256='0'*64)},0)
 def test_bound_review_refuses_change(self):
  with patch.object(B,'sha',return_value='0'*64):
   with self.assertRaisesRegex(ValueError,'immutable'):A.read_authority('prefix')
 def fixture(self,tmp,source):
  source.mkdir();(source/'prompt/rank0').mkdir(parents=True);f=source/'prompt/rank0/x.bin';f.write_bytes(b'closed-state'*100);(source/'failure.json').write_text('keep');(source/'unindexed.bin').write_bytes(b'partial-preserve')
  rows={'prompt/rank0/x.bin':dict(bytes=f.stat().st_size,sha256=B.sha(f))}
  return B.Job(source,tmp/'archive',rows,set(),cap=1024**2,floor=0,authority={'fixed':'fixture'})
 def test_real_tiny_archive_prune_preserves_unindexed(self):
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp);j=self.fixture(tmp,tmp/'source');r=j.archive();self.assertEqual(1,r['entries']);r=j.prune();self.assertEqual(1,r['removed']);self.assertEqual(b'partial-preserve',(j.source/'unindexed.bin').read_bytes());self.assertEqual('keep',(j.source/'failure.json').read_text())
   with self.assertRaisesRegex(ValueError,'no prune retry'):j.prune()
 def test_actual_two_filesystem_offload_release(self):
  with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory(dir='/dev/shm') as other:
   tmp=Path(tmp);other=Path(other);self.assertNotEqual(tmp.stat().st_dev,other.stat().st_dev)
   j=self.fixture(tmp,other/'source');j.archive();j.prune();usb=other/'verified.tar.gz';j.offload(usb,reserve=0);r=j.release_local(usb);self.assertTrue(r['passed']);self.assertTrue(usb.is_file());self.assertFalse((j.dest/'state-bins.tar.gz').exists())
 def test_wrong_filesystem_offload_refuses_before_create(self):
  with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory(dir='/dev/shm') as other:
   tmp=Path(tmp);j=self.fixture(tmp,Path(other)/'source');j.archive();j.prune();bad=tmp/'wrong.tar.gz'
   with self.assertRaisesRegex(ValueError,'expected source filesystem'):j.offload(bad,reserve=0)
   self.assertFalse(bad.exists());self.assertFalse((j.dest/'offload-start.json').exists());self.assertTrue((j.dest/'state-bins.tar.gz').exists())
if __name__=='__main__':unittest.main(verbosity=2)
