import copy,json,sys,tempfile,unittest
from pathlib import Path
import window as w
from diagnostic_mode import actual_artifacts,label_outputs,reject_nonqualifying
sys.path.insert(0,str(w.ROOT/'scripts'))
from receipt_qualification import require_qualifying
from submit_localmaxxing_results import preflight_payload
from promotion_evidence import validate_promotion_attestation
from qualify_realistic_window_metrics import qualify
class Diagnostic(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.addCleanup(self.tmp.cleanup)
  self.identity=dict(boot_id='boot',artifacts_sha256={'device/own-rt-iq3':'actual'},environment={},card=0,context=4096,draft_rank=0,build_receipt_sha256='old',diagnostic_unsealed=True,qualifying=False)
  self.row=dict(self.identity,window='K0',device_executed=True,passed=True,receipts={})
 def prereq(self,row):
  p=self.root/'window.json';p.write_text(json.dumps(row));return w.prerequisites(p,'K0',self.identity)
 def test_diagnostic_prerequisite(self):self.prereq(self.row)
 def test_reseal_during_diagnostic(self):
  self.row['build_receipt_sha256']='new';self.prereq(self.row)
 def test_qualified_cannot_feed_diagnostic(self):
  self.row.update(diagnostic_unsealed=False,qualifying=True)
  with self.assertRaisesRegex(ValueError,'diagnostic prerequisite'):self.prereq(self.row)
 def test_diagnostic_cannot_feed_qualified(self):
  self.identity.update(diagnostic_unsealed=False,qualifying=True)
  with self.assertRaisesRegex(ValueError,'diagnostic prerequisite'):self.prereq(self.row)
 def test_different_actual_binary(self):
  self.row['artifacts_sha256']={'device/own-rt-iq3':'changed'}
  with self.assertRaisesRegex(ValueError,'artifacts'):self.prereq(self.row)
 def test_different_boot(self):
  self.row['boot_id']='different'
  with self.assertRaisesRegex(ValueError,'boot'):self.prereq(self.row)
 def test_failed_exactness_refused(self):
  self.row['passed']=False
  with self.assertRaisesRegex(ValueError,'failed prerequisite'):self.prereq(self.row)
 def test_actual_hashes(self):
  (self.root/'device').mkdir();(self.root/'device/a').write_bytes(b'current')
  self.assertEqual(actual_artifacts({'artifacts_sha256':{'device/a':'stale'}},self.root,w.sha),{'device/a':w.sha(self.root/'device/a')})
 def test_labels_and_receipt_hashes(self):
  p=self.root/'receipt.json';p.write_text('{"passed":true}');row={'receipts':{'receipt.json':w.sha(p)}}
  label_outputs(self.root,row,w.sha)
  self.assertFalse(json.loads(p.read_text())['qualifying']);self.assertEqual(row['receipts']['receipt.json'],w.sha(p))
 def test_packet_promotion_guard(self):
  for marker in ({'diagnostic_unsealed':True},{'qualifying':False}):
   with self.assertRaisesRegex(ValueError,'cannot be'):reject_nonqualifying({'receipt':marker})
 def test_submission_never_override(self):
  for marker in ({'diagnostic_unsealed':True},{'qualifying':False}):
   self.assertIn('cannot be',preflight_payload({'receipt':marker},allow_non_headline=True)[0])
 def test_qualify_refuses(self):
  with self.assertRaisesRegex(ValueError,'cannot be'):qualify({'qualifying':False})
 def test_publication_attestation_refuses(self):
  p=self.root/'attestation.json';p.write_text('{"diagnostic_unsealed":true}')
  with self.assertRaisesRegex(ValueError,'cannot be'):validate_promotion_attestation(p,self.root/'not-read.json')
 def test_shell_reads_flag_before_clean_environment(self):
  text=(w.P/'coordinator_windows.sh').read_text();self.assertLess(text.index('PACKET45_DIAGNOSTIC_UNSEALED'),text.index('env -i'));self.assertEqual(text.count('"${packet45_diagnostic[@]}"'),2)
if __name__=='__main__':unittest.main()
