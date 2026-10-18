"""CPU rehearsal uses the current build and still rejects stale/tampered bytes."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import coordinator_cpu_gate as c
class BuildIdentity(unittest.TestCase):
 def test_current_build(self):
  expected=json.loads((c.P/'build-gnu-host-receipt.json').read_text())['artifacts_sha256']
  self.assertEqual(c.current_host_artifacts(),expected)
 def check_bad(self,mutate):
  with tempfile.TemporaryDirectory(prefix='coordinator-identity-',dir=c.B) as directory:
   p=Path(directory);b=p/'build';(b/'gnu-host').mkdir(parents=True)
   names=('own-rt-iq3','nongemv-fixtures','k2-fixtures','p33-linked-fixtures','p39-merged-fixtures')
   for name in names:(b/'gnu-host'/name).write_bytes(b'host fixture bytes, never executed')
   row=dict(passed=True,device_executed=False,mode='gnu-host',artifacts_sha256={'gnu-host/'+n:c.pp.sha(b/'gnu-host'/n) for n in names})
   mutate(row,b);(p/'build-gnu-host-receipt.json').write_text(json.dumps(row))
   with patch.object(c,'P',p),patch.object(c,'B',b),patch.object(c,'assert_host_build') as verify:
    with self.assertRaises(AssertionError):c.current_host_artifacts()
    verify.assert_called_once_with(b/'gnu-host/own-rt-iq3')
 def test_old_hash(self):self.check_bad(lambda r,b:r['artifacts_sha256'].update({'gnu-host/k2-fixtures':'0'*64}))
 def test_changed_bytes(self):self.check_bad(lambda r,b:(b/'gnu-host/k2-fixtures').write_bytes(b'tampered'))
 def test_missing_fixture(self):self.check_bad(lambda r,b:r['artifacts_sha256'].pop('gnu-host/k2-fixtures'))
 def test_device_path(self):self.check_bad(lambda r,b:r['artifacts_sha256'].update({'device/k2-fixtures':'0'*64}))
 def test_device_mode(self):self.check_bad(lambda r,b:r.update(mode='device'))
 def test_unpassed(self):self.check_bad(lambda r,b:r.update(passed=False))
if __name__=='__main__':unittest.main()
