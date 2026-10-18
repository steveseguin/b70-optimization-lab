"""Replay the actual failed packet145 bracket without writing a byte there."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import screen,p149_v5_compare as compare
from common import HERE,read,sha

class RetainedReport(unittest.TestCase):
 def test_real_retained_bracket(self):
  source=HERE.parent.parent/'packet145-router-gdnz-layout/v5/evidence/device-router-order600-v5-A'
  self.assertTrue(source.is_dir())
  proof=read(source/'run/bracket-inputs.json')
  self.assertEqual(len(proof['views']),5)
  self.assertFalse(list(source.glob('run/views/*/*/rank0/p105-transfers.jsonl')))
  before={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file() and p.suffix in ('.json','.jsonl')}
  with tempfile.TemporaryDirectory(prefix='p149-retained-report-') as temp:
   target=Path(temp)
   def save(path,row):
    relative=Path(path).relative_to(source);out=target/relative;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(row))
   with patch.object(screen,'save',save),patch.object(compare,'save',save):
    # Return uses the just-written report, so route only this output read.
    original=screen.read
    def read_report(p):
     return original(target/'bracket-summary.json') if p==source/'bracket-summary.json' else original(p)
    with patch.object(screen,'read',read_report):
     result=screen.report_completed(source,read(source/'window.json'),read(source/'identity.json'),read(source/'lane-coordination.json'))
   self.assertTrue(result['passed']);self.assertEqual(len(result['views']),5)
   self.assertTrue(all(r['miss_count']>0 and r['corrected_half']['mean_ms']>0 for r in result['views']))
   self.assertTrue(all(r['status']=='measured' for r in result['scheduling_costs']['views']))
   # This is only a regression replay of 145; never presented as packet149 device evidence.
   self.result=dict(passed=True,device_executed=False,source=str(source),views=[dict(index=r['index'],miss_count=r['miss_count'],corrected_half=r['corrected_half'],rate=r['rate']) for r in result['views']],retained_inputs_sha256=before)
  self.assertEqual(before,{str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file() and p.suffix in ('.json','.jsonl')})

if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 test=RetainedReport('test_real_retained_bracket');test.test_real_retained_bracket()
 from common import save
 save(HERE/'evidence/retained-report-regression.json',test.result)
 print('Retained packet145 full report PASS; original bytes unchanged')
