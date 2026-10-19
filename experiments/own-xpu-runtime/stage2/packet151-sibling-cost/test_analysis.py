import copy,json,tempfile,unittest
from pathlib import Path
from analyze import analyze
class Analysis(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.proof=dict(passed=True,kind='bracket',views=[])
  for i in range(5):
   choice='candidate' if i%2 else 'control';view=dict(index=i,choice=choice,passed=True,output=str(self.root/str(i)),requests=[]);self.proof['views'].append(view)
   for p in range(12):
    name='prompt'+str(p);d=Path(view['output'])/name/'rank0';d.mkdir(parents=True)
    row=dict(position=1,fixture=2,speculative=True,corrected=False,cancelled=False,p151_device_ms=10 if i%2==0 else 11,p151_sibling=i%2==1,p151_sibling_prepare_ms=0,half_completion_ms=10 if i%2==0 else 11.952)
    (d/'timings.jsonl').write_text(json.dumps(row)+'\n')
    if i%2:(d/'sibling-rows.jsonl').write_text(json.dumps(dict(position=1,fixture=2,paired_half_device_ms=11,cancelled=False,discarded=True))+'\n')
    view['requests'].append(dict(prompt_id=name,prompt_class='class'+str(p%4),passed=True,exact_oracle=True,cached_tokens=0,tokens=list(range(128)),token_timestamps=[x*.02 for x in range(128)],guess_rows=[dict(position=1,guess=3,actual=3,hit=True)]))
 def tearDown(self):self.tmp.cleanup()
 def test_threshold(self):self.assertEqual(analyze(self.proof)['decision'],'reopen-packet132')
 def test_above(self):
  for i in (1,3):
   for p in range(12):
    f=self.root/str(i)/('prompt'+str(p))/'rank0/timings.jsonl';r=json.loads(f.read_text());r['half_completion_ms']=12;f.write_text(json.dumps(r))
  self.assertEqual(analyze(self.proof)['decision'],'close-this-implementation')
 def test_missing_half(self):
  (self.root/'1/prompt0/rank0/timings.jsonl').unlink()
  with self.assertRaisesRegex(ValueError,'missing stream'):analyze(self.proof)
 def test_empty_sibling(self):
  (self.root/'1/prompt0/rank0/sibling-rows.jsonl').write_text('')
  with self.assertRaisesRegex(ValueError,'empty stream'):analyze(self.proof)
 def test_clock_mismatch(self):
  f=self.root/'1/prompt0/rank0/sibling-rows.jsonl';r=json.loads(f.read_text());r['paired_half_device_ms']=99;f.write_text(json.dumps(r))
  with self.assertRaisesRegex(ValueError,'clock mismatch'):analyze(self.proof)
 def test_changed_output(self):
  self.proof['views'][1]['requests'][0]['tokens'][0]=99
  with self.assertRaisesRegex(ValueError,'changed'):analyze(self.proof)
 def test_smoke_checks_data(self):
  self.proof.update(kind='smoke',views=[self.proof['views'][1]])
  self.assertEqual(analyze(self.proof)['decision'],'smoke-data-complete')
  (self.root/'1/prompt0/rank0/sibling-rows.jsonl').unlink()
  with self.assertRaisesRegex(ValueError,'missing stream'):analyze(self.proof)
 def test_nonfinite(self):
  f=self.root/'1/prompt0/rank0/timings.jsonl';r=json.loads(f.read_text());r['p151_device_ms']=float('nan');f.write_text(json.dumps(r))
  with self.assertRaisesRegex(ValueError,'invalid'):analyze(self.proof)
if __name__=='__main__':unittest.main()
