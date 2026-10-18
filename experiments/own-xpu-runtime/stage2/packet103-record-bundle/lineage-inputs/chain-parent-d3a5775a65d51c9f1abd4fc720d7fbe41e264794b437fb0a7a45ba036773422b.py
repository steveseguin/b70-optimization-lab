"""Small synthetic ledger tests; no native binary or model is launched."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import real40_summary as summary
from storage import admit

class SummaryTests(unittest.TestCase):
 def setUp(self):
  admit(100000)
  self.temp=tempfile.TemporaryDirectory(prefix='summary40-test-',dir=summary.P/'build')
  self.addCleanup(self.temp.cleanup);self.p=Path(self.temp.name)
  (self.p/'build/icpx-host').mkdir(parents=True);(self.p/'evidence').mkdir()
  (self.p/'build/icpx-host/own-rt-iq3').write_bytes(b'synthetic CPU binary identity; never executable')
  for name in ('gates.py','real40_summary.py'):(self.p/name).write_text('# synthetic test source')
  self.binary=summary.sha(self.p/'build/icpx-host/own-rt-iq3');self.paths=[]
  for index,mode in enumerate(summary.MODES):
   name=f'real-icpx-host-{mode}.json'
   row=dict(passed=True,device_executed=False,mode=mode,binary_sha256=self.binary,token_matches=8,layer_matches=384,layer_total=384,fixture_sha256={'fixture':'hash'},controller_signature={'tokens':'hash'},root=str(self.p/'build'/mode),seconds=1)
   (self.p/name).write_text(json.dumps(row));log=self.p/'evidence'/f'{mode}.gz';log.write_bytes(b'synthetic log')
   ledger=dict(passed=True,device_executed=False,phase='real-icpx-host-'+mode,receipt_sha256={name:summary.sha(self.p/name)},source_sha256={'gates.py':'current'},binary_sha256={'icpx-host/own-rt-iq3':self.binary},returncode=0,problems=[],command=['nice','-n','19','ionice','-c','3',sys.executable,'-B',str(self.p/'gates.py'),'real',mode,'--compiler','icpx-host'],log=str(log.relative_to(self.p)),log_sha256=summary.sha(log),start_unix_ns=10*index+1,end_unix_ns=10*index+2)
   path=self.p/'evidence'/f'qualification-real-icpx-host-{mode}-1.json';path.write_text(json.dumps(ledger));self.paths.append(path)
  mocked=patch.object(summary,'execution_sources',return_value={'gates.py':'current'});mocked.start();self.addCleanup(mocked.stop)
 def run_summary(self):return summary.validate('icpx-host',packet=self.p)
 def corrupt(self,key,value):
  path=self.paths[1];row=json.loads(path.read_text());row[key]=value;path.write_text(json.dumps(row))
  with self.assertRaises(ValueError):self.run_summary()
 def test_accepts_five(self):self.assertEqual(self.run_summary()['modes'],5)
 def test_old_source(self):self.corrupt('source_sha256',{'gates.py':'old'})
 def test_old_binary(self):self.corrupt('binary_sha256',{'icpx-host/own-rt-iq3':'old'})
 def test_wrong_receipt_hash(self):self.corrupt('receipt_sha256',{'real-icpx-host-ngram.json':'wrong'})
 def test_wrong_log_hash(self):self.corrupt('log_sha256','wrong')
 def test_failed_ledger(self):self.corrupt('passed',False)
 def test_overlap(self):self.corrupt('start_unix_ns',1)
 def test_wrong_mode_command(self):
  command=json.loads(self.paths[1].read_text())['command'];command[10]='none';self.corrupt('command',command)
 def test_wrong_mode_receipt(self):
  path=self.p/'real-icpx-host-ngram.json';row=json.loads(path.read_text());row['mode']='none';path.write_text(json.dumps(row))
  ledger=json.loads(self.paths[1].read_text());ledger['receipt_sha256'][path.name]=summary.sha(path);self.paths[1].write_text(json.dumps(ledger))
  with self.assertRaises(ValueError):self.run_summary()
 def test_incomplete_fixture_count(self):
  path=self.p/'real-icpx-host-ngram.json';row=json.loads(path.read_text());row['layer_matches']=383;path.write_text(json.dumps(row))
  with self.assertRaises(ValueError):self.run_summary()
 def test_missing_mode(self):
  self.paths[2].unlink()
  with self.assertRaises(ValueError):self.run_summary()
 def test_duplicate_current_ledger(self):
  duplicate=self.paths[1].with_name('qualification-real-icpx-host-ngram-2.json');duplicate.write_bytes(self.paths[1].read_bytes())
  with self.assertRaises(ValueError):self.run_summary()

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(SummaryTests)
 result=unittest.TextTestRunner(verbosity=1).run(suite)
 summary.save(summary.P/'real40-summary-gates.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),device_executed=False,models_launched=0,
  source_sha256={name:summary.sha(summary.P/name) for name in ('real40_summary.py','test_real40_summary.py','seal40.py','storage.py')},scope='Synthetic positive and negative narrow-ledger admission, no native processes'))
 raise SystemExit(not result.wasSuccessful())
