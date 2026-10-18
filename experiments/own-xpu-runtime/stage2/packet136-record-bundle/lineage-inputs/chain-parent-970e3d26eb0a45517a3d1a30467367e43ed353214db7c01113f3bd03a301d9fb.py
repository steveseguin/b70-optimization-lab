#!/usr/bin/env python3
"""CPU-only admission failures; no weights, native model or device execution."""
import contextlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import oracle_job as job
class Admission(unittest.TestCase):
 def test_pending_blocks_model(self):
  with tempfile.TemporaryDirectory() as t,patch.object(job,'RESULTS',Path(t)),contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(job.status(True),1);self.assertEqual(job.status(False),0)
 def test_failed_campaign_stays_blocked(self):
  with tempfile.TemporaryDirectory() as t,patch.object(job,'RESULTS',Path(t)),contextlib.redirect_stdout(io.StringIO()):
   job.save(Path(t)/'campaign.json',dict(status='failed',error='operator test'))
   self.assertEqual(job.status(True),1)
 def test_bad_completion_refused(self):
  with tempfile.TemporaryDirectory() as t,patch.object(job,'RESULTS',Path(t)),patch.object(job,'source_bindings'):
   job.save(Path(t)/'completion.json',dict(passed=True,arithmetic='old'))
   with self.assertRaisesRegex(RuntimeError,'invalid completion'):job.status(True)
 def test_complete_flag_without_binding_refused(self):
  with tempfile.TemporaryDirectory() as t,patch.object(job,'RESULTS',Path(t)),patch.object(job,'source_bindings'):
   job.save(Path(t)/'completion.json',dict(passed=True,arithmetic=job.IDENTITY,manifest_sha256='0'*64))
   job.save(Path(t)/'suite-manifest.json',dict(complete=True))
   with self.assertRaisesRegex(RuntimeError,'completion binding changed'):job.status(True)
 def test_runtime_identity_and_failure_refused(self):
  ck=job.checker()
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);job.save(p/'receipt.json',dict(schema='own-runtime.iq3.packet26.run.v1',passed=True,arithmetic='old',tokens=[1]))
   with self.assertRaisesRegex(ValueError,'wrong arithmetic'):ck.token_record(p)
   job.save(p/'receipt.json',dict(schema='own-runtime.iq3.packet26.run.v1',passed=False,arithmetic=job.IDENTITY,tokens=[1]))
   with self.assertRaisesRegex(ValueError,'runtime receipt failed'):ck.token_record(p)
 def test_missing_tail_fixture_refused(self):
  ck=job.checker()
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)
   for i in range(1,9):(p/f'step{i}').mkdir()
   with self.assertRaisesRegex(ValueError,'fixture step coverage'):ck.fixture_inventory(p,128)
if __name__=='__main__':unittest.main()
