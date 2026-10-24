import contextlib,gzip,hashlib,importlib.util,io,json,os,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('canonical_test',P/'consolidate.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
class Consolidate(unittest.TestCase):
 def archive(self,path,rows):
  with tarfile.open(path,'w:gz') as t:
   for name,data in rows.items():
    m=tarfile.TarInfo(name);m.size=len(data);m.mode=0o640;m.mtime=123;m.uid=12;m.gid=34;m.uname='retained';t.addfile(m,io.BytesIO(data))
 def fixture(self,stack):
  usb=Path(stack.enter_context(tempfile.TemporaryDirectory(dir='/dev/shm')));nvme=Path(stack.enter_context(tempfile.TemporaryDirectory(dir='/home/steve/own-xpu-runtime-results')))
  original=usb/'original.tar.gz';canonical=usb/'canonical.tar.gz';self.archive(original,{'group/a.bin':b'exact'});self.archive(canonical,{'group/a.bin':b'exact','group/b.bin':b'extra'})
  expected={'group/a.bin':dict(bytes=5,sha256=hashlib.sha256(b'exact').hexdigest())};base={**expected,'group/b.bin':dict(bytes=5,sha256=hashlib.sha256(b'extra').hexdigest())}
  row=dict(original_archive=str(original),canonical_archive=str(canonical),original_archive_bytes=original.stat().st_size,canonical_archive_bytes=canonical.stat().st_size,original_archive_sha256=A.sha(original),canonical_archive_sha256=A.sha(canonical))
  for key,value in [('USB',usb),('USB_DEVICE',usb.stat().st_dev),('DEST',nvme/'metadata')]:stack.enter_context(patch.object(A,key,value))
  stack.enter_context(patch.object(A,'limits'));stack.enter_context(patch.object(A,'review',return_value='review'));stack.enter_context(patch.object(A,'authority',return_value=(row,expected,base)))
  return original,canonical,expected
 def test_two_filesystem_verify_release_and_metadata_restore(self):
  with contextlib.ExitStack() as stack:
   original,canonical,expected=self.fixture(stack);before=A.sha(canonical);v=A.verify(0);self.assertTrue(original.exists());self.assertTrue(v['passed'])
   with gzip.open(A.DEST/'batch-00/restore.json.gz','rt') as z:d=json.load(z)
   self.assertEqual(set(d['original_members']),set(expected));m=d['original_members']['group/a.bin']['tar_metadata'];self.assertEqual((m['mode'],m['uid'],m['gid'],m['mtime']),(0o640,12,34,123))
   self.assertTrue(A.release(0)['passed']);self.assertFalse(original.exists());self.assertEqual(A.sha(canonical),before)
   with self.assertRaises(ValueError):A.release(0)
 def test_canonical_change_refuses_release_preserves_original(self):
  with contextlib.ExitStack() as stack:
   original,canonical,_=self.fixture(stack);A.verify(0);canonical.write_bytes(b'changed')
   with self.assertRaises(ValueError):A.release(0)
   self.assertTrue(original.exists());self.assertFalse((A.DEST/'batch-00/release-start.json').exists())
 def test_bad_hash_cannot_publish_verified_redirect(self):
  with contextlib.ExitStack() as stack:
   original,_,_=self.fixture(stack);original.write_bytes(b'bad')
   with self.assertRaises(ValueError):A.verify(0)
   self.assertFalse((A.DEST/'batch-00/restore.json.gz').exists());self.assertFalse(json.loads((A.DEST/'batch-00/verified.json').read_text())['passed'])
 def test_wrong_device_and_symlink_refused(self):
  with contextlib.ExitStack() as stack:
   original,_,_=self.fixture(stack)
   with patch.object(A,'USB_DEVICE',-1),self.assertRaises(ValueError):A.held(original,original.stat().st_size)
   link=A.USB/'link.tar.gz';link.symlink_to(original)
   with self.assertRaises(ValueError):A.held(link,original.stat().st_size)
 def test_names_and_fixed_mapping_boundaries(self):
  for n in ('/a.bin','../a.bin','g/../a.bin','g//a.bin','g/./a.bin'):
   with self.assertRaises(ValueError):A.name_ok(n)
  for i in (-1,41,True,'0'):
   with self.assertRaises(ValueError):A.authority(i)
if __name__=='__main__':unittest.main(verbosity=2)
