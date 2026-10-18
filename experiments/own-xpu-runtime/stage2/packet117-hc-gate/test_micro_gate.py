"""Synthetic parser tests; these are never device or performance evidence."""
import copy,json,tempfile,unittest
from pathlib import Path
import micro_gate as g
class Gate(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)
  comparisons=self.p/'comparisons.jsonl';comparisons.write_text(json.dumps(dict(equal=True,bytes=25600,sha256='0'*64))+'\n')
  (self.p/'exact-capture-manifest.json').write_text('[]\n')
  (self.p/'receipt.json').write_text(json.dumps(dict(schema='ownrt.packet117.layer.v1',passed=True,safe_to_exit=True,device_executed=True,cpu_mock=False,timing_pair_checks=100,checks=999,exact_output_identity=g.sha(comparisons))))
  self.rows=[]
  for layer in (3,4):
   for it in range(50):
    for mode in (('p117','production') if it%2==0 else ('production','p117')):
     dt=70 if mode=='p117' else 100
     events=[dict(id=i+1,**{'class':cls},start_ns=1000+i*1000,end_ns=1000+i*1000+dt) for i,cls in enumerate(('hc.a.gate','hc.f.gate'))]
     self.rows.append(dict(layer=layer,iteration=it,mode=mode,warmup=it<10,position=127,occupied_context=128,submissions=2,events=events,classes_ns={'hc.a.gate':dt,'hc.f.gate':dt},gpu_ns=2*dt))
 def tearDown(self):self.tmp.cleanup()
 def result(self):
  (self.p/'iterations.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in self.rows));return g.analyze(self.p)
 def test_threshold(self):self.assertTrue(self.result()['passed'])
 def test_one_order_fails(self):
  for r in self.rows:
   if r['mode']=='p117' and r['iteration']%2 and r['layer']==4:
    r['events'][0]['end_ns']+=1;r['classes_ns']['hc.a.gate']+=1;r['gpu_ns']+=1
  self.assertFalse(self.result()['passed'])
 def test_missing_pair(self):
  self.rows.pop()
  with self.assertRaises(ValueError):self.result()
 def test_duplicate(self):
  self.rows[-1]=copy.deepcopy(self.rows[-3])
  with self.assertRaises(ValueError):self.result()
 def test_reordered_pair(self):
  self.rows[0],self.rows[1]=self.rows[1],self.rows[0]
  with self.assertRaises(ValueError):self.result()
 def test_changed_class_total(self):
  self.rows[0]['classes_ns']['hc.a.gate']+=1
  with self.assertRaises(ValueError):self.result()
 def test_changed_comparisons(self):
  (self.p/'comparisons.jsonl').write_text('{}\n')
  with self.assertRaises(ValueError):self.result()
 def test_cpu_receipt_refused(self):
  f=self.p/'receipt.json';r=json.loads(f.read_text());r['cpu_mock']=True;f.write_text(json.dumps(r))
  with self.assertRaises(ValueError):self.result()
if __name__=='__main__':
 from build_engine import limits
 limits();unittest.main()
