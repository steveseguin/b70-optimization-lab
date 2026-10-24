import contextlib,hashlib,importlib.util,io,json,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('raw_reuse_test',P/'reuse.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
class Reuse(unittest.TestCase):
 def fixture(self,stack):
  usb=Path(stack.enter_context(tempfile.TemporaryDirectory(dir='/dev/shm')));local=Path(stack.enter_context(tempfile.TemporaryDirectory(dir='/home/steve/own-xpu-runtime-results')));rawroot=usb/'raw';name=A.NAMES[0];raw=rawroot/name;raw.parent.mkdir(parents=True);raw.write_bytes(b'exact original bytes');archive=usb/'canonical.tar.gz'
  with tarfile.open(archive,'w:gz') as tar:
   member=tarfile.TarInfo(name);member.size=raw.stat().st_size;tar.addfile(member,io.BytesIO(raw.read_bytes()))
  row=dict(relative_path=name,bytes=raw.stat().st_size,raw_sha256=A.sha(raw),canonical_archive=str(archive),canonical_archive_bytes=archive.stat().st_size,canonical_archive_sha256=A.sha(archive))
  for obj,key,value in [(A,'RAW',rawroot),(A.C,'USB',usb),(A.C,'USB_DEVICE',usb.stat().st_dev),(A.C,'DEST',local/'metadata')]:stack.enter_context(patch.object(obj,key,value))
  stack.enter_context(patch.object(A,'authority',return_value=row));stack.enter_context(patch.object(A,'review_pin',return_value='review'));stack.enter_context(patch.object(A.C,'limits'))
  return raw,archive
 def test_verify_then_release_only_raw_preserves_restore(self):
  with contextlib.ExitStack() as stack:
   raw,archive=self.fixture(stack);before=A.sha(archive);v=A.verify(0);self.assertTrue(v['passed']);self.assertTrue(raw.exists());rest=json.loads((A.C.DEST/'batch-00/restore.json').read_text());self.assertEqual(rest['original_path'],str(raw));self.assertEqual(rest['canonical_member']['sha256'],A.sha(raw));self.assertTrue(A.release(0)['passed']);self.assertFalse(raw.exists());self.assertEqual(A.sha(archive),before)
   with self.assertRaises(ValueError):A.release(0)
 def test_changed_canonical_refuses_release(self):
  with contextlib.ExitStack() as stack:
   raw,archive=self.fixture(stack);A.verify(0);archive.write_bytes(b'changed')
   with self.assertRaises(ValueError):A.release(0)
   self.assertTrue(raw.exists());self.assertFalse((A.C.DEST/'batch-00/release-start.json').exists())
 def test_pending_and_scope_refused(self):
  with patch.object(A,'BINDING_SHA',None):
   with self.assertRaisesRegex(ValueError,'pending'):A.authority(0)
  for batch in (-1,4,True):
   with self.assertRaisesRegex(ValueError,'fixed batch'):A.authority(batch)
  with contextlib.ExitStack() as stack:
   raw,_=self.fixture(stack);extra=raw.with_name('state.json');extra.write_bytes(b'keep')
   with self.assertRaises(ValueError):A.raw_held(extra,4)
   with patch.object(A.C,'USB_DEVICE',-1),self.assertRaises(ValueError):A.raw_held(raw,raw.stat().st_size)
if __name__=='__main__':unittest.main(verbosity=2)
