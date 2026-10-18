import json,tempfile,unittest
from pathlib import Path
from qualification import evaluate
class Gate(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.p=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def owner(self,n,saving=90,context_saving=None):
  d=self.p/'evidence'/f'micro-B-{n}';(d/'native').mkdir(parents=True)
  (d/'window.json').write_text(json.dumps(dict(passed=True,drained=True,pid=n,start_ticks=n,process_start_ticks=n,identity={'binary':'same'})))
  (d/'native/receipt.json').write_text(json.dumps(dict(passed=True,safe_to_exit=True,device_executed=True,timing_pair_checks=100,exact_output_identity='same')))
  rows=[]
  for context in (128,4096):
   delta=saving if context==128 or context_saving is None else context_saving
   for i in range(50):
    for mode in (['current','specialized'] if i%2==0 else ['specialized','current']):
     ns=1_000_000 if mode=='current' else 1_000_000-int(delta*1000)
     rows.append(dict(layer=3,occupied_context=context,iteration=i,mode=mode,warmup=i<10,submissions=1,gpu_ns=ns,events=[dict(start_ns=1,end_ns=ns+1)]))
  (d/'native/iterations.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));return d
 def test_two_fresh_owners_required(self):
  self.owner(1);self.assertFalse(evaluate(self.p)['integration_allowed'])
 def test_boundary(self):
  self.owner(1,80);self.owner(2,80);self.assertTrue(evaluate(self.p)['integration_allowed'])
 def test_one_under_threshold(self):
  self.owner(1,120);self.owner(2,79.999);self.assertFalse(evaluate(self.p)['integration_allowed'])
 def test_long_context_cannot_rescue_short(self):
  self.owner(1,1,200);self.owner(2,1,200);self.assertFalse(evaluate(self.p)['integration_allowed'])
 def test_identity_drift(self):
  self.owner(1);d=self.owner(2);f=d/'window.json';r=json.loads(f.read_text());r['identity']['binary']='other';f.write_text(json.dumps(r))
  with self.assertRaises(AssertionError):evaluate(self.p)
 def test_inexact(self):
  d=self.owner(1);self.owner(2);f=d/'native/receipt.json';r=json.loads(f.read_text());r['passed']=False;f.write_text(json.dumps(r))
  with self.assertRaises(AssertionError):evaluate(self.p)
 def test_missing_pair(self):
  d=self.owner(1);self.owner(2);f=d/'native/iterations.jsonl';f.write_text('\n'.join(f.read_text().splitlines()[1:])+'\n')
  with self.assertRaises(AssertionError):evaluate(self.p)
 def test_event_accounting(self):
  d=self.owner(1);self.owner(2);f=d/'native/iterations.jsonl';rows=[json.loads(x) for x in f.read_text().splitlines()];rows[0]['gpu_ns']+=1;f.write_text(''.join(json.dumps(r)+'\n' for r in rows))
  with self.assertRaises(AssertionError):evaluate(self.p)
if __name__=='__main__':unittest.main()
