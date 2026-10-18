"""Synthetic accounting fixtures only: exercise fail-closed gate rules."""
import copy,json,tempfile,unittest
from pathlib import Path
from qualification import evaluate
class Gate(unittest.TestCase):
 def fixture(self,p):
  def save(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj))
  for owner in (1,2):
   d=p/'evidence'/f'micro-B-{owner}'
   save(d/'window.json',dict(passed=True,drained=True,pid=owner,process_start_ticks=owner,identity={'sealed':'same'}))
   save(d/'native/receipt.json',dict(passed=True,safe_to_exit=True,device_executed=True,cpu_mock=False,timing_pair_checks=100,checks=500,arithmetic='iq3-p49-split32-v1',exact_output_identity='same'))
   (d/'native/comparisons.jsonl').write_text('{}\n');rows=[]
   for ctx in (128,4096):
    for i in range(50):
     for mode in (['production','p116'] if i%2==0 else ['p116','production']):
      dt=100 if mode=='production' else 50
      events=[dict(id=j+1,**{'class':cls},start_ns=1,end_ns=1+dt) for j,cls in enumerate(['qsa.attention','qsa.attention','qsa.select'])]
      rows.append(dict(layer=3,occupied_context=ctx,iteration=i,warmup=i<10,mode=mode,events=events,submissions=3,gpu_ns=dt*3,classes_ns={'qsa.attention':dt*2,'qsa.select':dt}))
   (d/'native/iterations.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
 def run_case(self,mutate):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);self.fixture(p);mutate(p);return evaluate(p,write=False)
 def test_complete(self):
  r=self.run_case(lambda p:None);self.assertTrue(r['integration_allowed']);self.assertEqual(r['owners'][0]['cases'][0]['ratio_of_medians'],.5)
 def test_missing_owner(self):
  r=self.run_case(lambda p:(p/'evidence/micro-B-2/window.json').unlink());self.assertFalse(r['passed'])
 def test_dropped_attention_event(self):
  def mutate(p):
   f=p/'evidence/micro-B-2/native/iterations.jsonl';rows=[json.loads(x) for x in f.read_text().splitlines()];rows[30]['events'].pop(0);f.write_text(''.join(json.dumps(r)+'\n' for r in rows))
  self.assertFalse(self.run_case(mutate)['passed'])
 def test_losing_second_process(self):
  def mutate(p):
   f=p/'evidence/micro-B-2/native/iterations.jsonl';rows=[json.loads(x) for x in f.read_text().splitlines()]
   for r in rows:
    if r['mode']=='p116':
     for e in r['events']:e['end_ns']=101
     r['gpu_ns']=300;r['classes_ns']={'qsa.attention':200,'qsa.select':100}
   f.write_text(''.join(json.dumps(r)+'\n' for r in rows))
  r=self.run_case(mutate);self.assertTrue(r['device_speed_measured']);self.assertFalse(r['integration_allowed'])
 def test_wrong_order(self):
  def mutate(p):
   f=p/'evidence/micro-B-2/native/iterations.jsonl';rows=f.read_text().splitlines();rows[0],rows[1]=rows[1],rows[0];f.write_text('\n'.join(rows)+'\n')
  self.assertFalse(self.run_case(mutate)['passed'])
 def test_long_context_is_reported_separately(self):
  def mutate(p):
   for owner in (1,2):
    f=p/'evidence'/f'micro-B-{owner}'/'native/iterations.jsonl';rows=[json.loads(x) for x in f.read_text().splitlines()]
    for r in rows:
     if r['occupied_context']==4096 and r['mode']=='p116':
      for e in r['events']:e['end_ns']=201
      r['gpu_ns']=600;r['classes_ns']={'qsa.attention':400,'qsa.select':200}
    f.write_text(''.join(json.dumps(r)+'\n' for r in rows))
  r=self.run_case(mutate);self.assertTrue(r['passed']);self.assertEqual(r['owners'][0]['cases'][1]['ratio_of_medians'],2)
 def test_reused_process_refused(self):
  def mutate(p):
   a=p/'evidence/micro-B-1/window.json';b=p/'evidence/micro-B-2/window.json';b.write_text(a.read_text())
  self.assertFalse(self.run_case(mutate)['passed'])
 def test_mismatched_binary_identity_refused(self):
  def mutate(p):
   f=p/'evidence/micro-B-2/window.json';r=json.loads(f.read_text());r['identity']['sealed']='changed';f.write_text(json.dumps(r))
  self.assertFalse(self.run_case(mutate)['passed'])
if __name__=='__main__':unittest.main()
