#!/usr/bin/env python3
"""Receipt gates only: no journal, child process or device discovery."""
import json,tempfile,unittest
from pathlib import Path
import window
class Gates(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'build');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.inp=self.root/'input';self.inp.mkdir();(self.inp/'tokens.txt').write_text('1 2\n')
  self.run=self.root/'run';(self.run/'step1').mkdir(parents=True)
  hashes={}
  for i in range(48):
   f=self.run/f'step1/layer-{i:02}.bf16';f.write_bytes(bytes([i])*20480);hashes[f'step1/layer-{i:02}.bf16']=window.sha(f)
  self.record=dict(passed=True,cards=1,card=3,arithmetic='iq3-p13-r234-sg32-split4-bf16-v1',input_sha256=window.sha(self.inp/'tokens.txt'),stage='first-token',tokens=[4],layer_hashes=hashes)
  self.baseline=self.root/'window.json';self.save()
  (self.run/'receipt.json').write_text(json.dumps(dict(passed=True,teardown=[dict(safe_to_exit=True,live_bytes=0,in_flight=0)])))
  self.binary=self.root/'binary';self.binary.write_bytes(b'not an executable')
  self.gate=self.root/'gate.json'
  self.layer=dict(passed=True,oracle_exact=True,stage='layer',cards=2,card=2,baseline_sha256=window.sha(self.baseline),binary_sha256=window.sha(self.binary),input_sha256=window.sha(self.inp/'tokens.txt'),boot_id='boot')
  self.gate.write_text(json.dumps(self.layer))
 def save(self):self.baseline.write_text(json.dumps(self.record))
 def test_layer(self):self.assertEqual(len(window.baseline_gate(self.baseline,self.inp,'layer')[1]),1)
 def test_token(self):self.assertEqual(len(window.baseline_gate(self.baseline,self.inp,'first-token')[1]),48)
 def test_bad_arithmetic(self):
  self.record['arithmetic']='old';self.save()
  with self.assertRaises(SystemExit):window.baseline_gate(self.baseline,self.inp,'layer')
 def test_wrong_card(self):
  self.record['card']=2;self.save()
  with self.assertRaises(SystemExit):window.baseline_gate(self.baseline,self.inp,'layer')
 def test_incomplete_baseline_stage(self):
  self.record['stage']='layer';self.save()
  with self.assertRaises(SystemExit):window.baseline_gate(self.baseline,self.inp,'layer')
 def test_failed_baseline(self):
  self.record['passed']=False;self.save()
  with self.assertRaises(SystemExit):window.baseline_gate(self.baseline,self.inp,'layer')
 def test_changed_fixture(self):
  (self.run/'step1/layer-00.bf16').write_bytes(b'bad')
  with self.assertRaises(SystemExit):window.baseline_gate(self.baseline,self.inp,'layer')
 def test_wrong_prompt(self):
  (self.inp/'tokens.txt').write_text('3\n')
  with self.assertRaises(SystemExit):window.baseline_gate(self.baseline,self.inp,'layer')
 def test_unsafe(self):
  (self.run/'receipt.json').write_text(json.dumps(dict(passed=True,teardown=[dict(safe_to_exit=False)])))
  with self.assertRaises(SystemExit):window.baseline_gate(self.baseline,self.inp,'layer')
 def test_layer_required(self):
  with self.assertRaises(SystemExit):window.layer_gate(None,self.baseline,self.binary,self.inp,'boot')
 def test_layer_pass(self):window.layer_gate(self.gate,self.baseline,self.binary,self.inp,'boot')
 def test_layer_failed(self):
  self.layer['oracle_exact']=False;self.gate.write_text(json.dumps(self.layer))
  with self.assertRaises(SystemExit):window.layer_gate(self.gate,self.baseline,self.binary,self.inp,'boot')
 def test_layer_new_boot(self):
  with self.assertRaises(SystemExit):window.layer_gate(self.gate,self.baseline,self.binary,self.inp,'new')
 def test_layer_binary_changed(self):
  self.binary.write_bytes(b'changed')
  with self.assertRaises(SystemExit):window.layer_gate(self.gate,self.baseline,self.binary,self.inp,'boot')
if __name__=='__main__':unittest.main()
