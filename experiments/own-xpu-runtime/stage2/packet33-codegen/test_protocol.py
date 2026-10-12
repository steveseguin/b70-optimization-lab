#!/usr/bin/env python3
import json,tempfile,unittest,shutil
from pathlib import Path
import summarize
P=Path(__file__).resolve().parent
class Protocol(unittest.TestCase):
 def setUp(self):
  self.root=Path(tempfile.mkdtemp(prefix='test-',dir=P/'build'))
  (self.root/'receipt.json').write_text(json.dumps(dict(passed=True,reference_exact=True)))
  self.rows=[];eid=1
  for (c,k),ws in summarize.EXPECTED.items():
   for w in ws:
    for arm in ('packet18','specialised'):
     for rep in range(200):
      for stage in range(summarize.expected_stages(c,arm)):
       self.rows.append(dict(klass=c,**{'class':c},candidate=k,workload=w,variant=arm,repetition=rep,event=eid,stage_count=summarize.expected_stages(c,arm),start_ns=100,end_ns=100100 if arm=='packet18' else 25100,exact=True,full_payload_bytes=9000000 if c.startswith('gemv:') else 0,timing_mode='rotated'));eid+=1
 def tearDown(self):shutil.rmtree(self.root)
 def runrows(self):
  (self.root/'events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in self.rows));return summarize.summarize(self.root)
 def test_success(self):
  d=self.runrows();self.assertEqual(len(d['table']),7);self.assertTrue(all(r['selected'] for r in d['table']));self.assertTrue((self.root/'dispatch-measured.json').exists())
 def test_extra_rep(self):self.rows.append(dict(self.rows[0],repetition=200));self.assertRaises(ValueError,self.runrows)
 def test_extra_arm(self):self.rows.append(dict(self.rows[0],variant='extra'));self.assertRaises(ValueError,self.runrows)
 def test_self_reported_stage(self):
  self.rows=[r for r in self.rows if not (r['class']=='route' and r['variant']=='packet18' and r['event']%5!=0)]
  for r in self.rows:
   if r['class']=='route' and r['variant']=='packet18':r['stage_count']=1
  self.assertRaises(ValueError,self.runrows)
 def test_missing_rep(self):self.rows.pop();self.assertRaises(ValueError,self.runrows)
 def test_partial_stage(self):self.rows[0]['stage_count']=2;self.assertRaises(ValueError,self.runrows)
 def test_bad_timestamp(self):self.rows[0]['end_ns']=0;self.assertRaises(ValueError,self.runrows)
 def test_not_exact(self):self.rows[0]['exact']=False;self.assertRaises(ValueError,self.runrows)
 def test_reread_refused(self):self.rows[0]['timing_mode']='reread';self.assertRaises(ValueError,self.runrows)
 def test_failure_file(self):(self.root/'candidate-failures.jsonl').write_text('{}\n');self.assertRaises(ValueError,self.runrows)
 def test_receipt_not_exact(self):(self.root/'receipt.json').write_text('{"passed":true,"reference_exact":false}');self.assertRaises(ValueError,self.runrows)
 def test_missing_candidate(self):self.rows=[r for r in self.rows if r['candidate']!='p33.down.select'];self.assertRaises(ValueError,self.runrows)
 def test_duplicate_event(self):self.rows.append(self.rows[0]);self.assertRaises(ValueError,self.runrows)
if __name__=='__main__':unittest.main()
