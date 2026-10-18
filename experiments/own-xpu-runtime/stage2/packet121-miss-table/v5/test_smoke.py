"""Negative smoke-admission tests. All fixtures stay in a private directory."""
import copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import smoke_gate as gate
from common import sha,save
P=Path(__file__).resolve().parent
class SmokeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='p121-smoke-test-');self.addCleanup(self.tmp.cleanup);self.out=Path(self.tmp.name)
  self.prompts=('architecture-tradeoff',)+tuple('prompt'+str(i) for i in range(11));self.tokens=[5]*64;self.tokens[30]=215495
  self.mock=SimpleNamespace(CHECK=SimpleNamespace(PROMPT_IDS=self.prompts,token_record=lambda path:self.tokens),ORACLE=self.out/'oracle')
  self.identity=dict(bracket=dict(views=[dict(choice=c,selection_sha256=c+'hash') for c in ('control','candidate','control')]))
  views=[]
  for i,selected in enumerate(self.identity['bracket']['views']):
   dest=self.out/'run/views'/f'{i:02d}-{selected["choice"]}';proof=[];rows=[]
   for rank in (0,1):
    row=dict(passed=True,total_reset=True,cached_tokens=0,selection_sha256=selected['selection_sha256'],weight_uploads_after_load=0,arena_descriptors_sha256='arena'+str(rank),weight_descriptors_sha256='weights'+str(rank))
    save(dest/'boundary'/f'boundary-rank{rank}.json',row);proof.append(row)
   for prompt in self.prompts:
    row=dict(prompt_id=prompt,passed=True,exact_oracle=True,cached_tokens=0,tokens=self.tokens,stats=dict(misses=5))
    save(dest/prompt/'receipt.json',row);rows.append(row)
   incident=dest/'incident64/receipt.json';save(incident,dict(passed=True,cached_tokens=0,tokens=self.tokens))
   views.append(dict(passed=True,index=i,choice=selected['choice'],selection_sha256=selected['selection_sha256'],output=str(dest),boundary=proof,requests=rows,incident64=dict(receipt_sha256=sha(incident))))
  self.proof=dict(passed=True,kind='smoke',views=views)
  save(self.out/'run/bracket-inputs.json',self.proof)
  # The original load output has zero counters, just as the actual first reset.
  save(self.out/'run/ranks/rank0/p121-restore-table.json',dict(mode='production',reused_restore_tables=0,restore_extent_guards_unchanged=True))
  self.counter=self.out/'run/views/01-candidate'/self.prompts[-1]/'rank0/p121-restore-table.json'
  save(self.counter,dict(mode='p121',reused_restore_tables=60,restore_extent_guards_unchanged=True))
 def check(self):
  with patch.object(gate,'D',self.mock):return gate.check_views(self.out,self.identity)
 def test_redirected_candidate_counter_and_all_views(self):self.assertTrue(self.check()['passed'])
 def test_missing_candidate_counter(self):
  self.counter.unlink()
  with self.assertRaises(FileNotFoundError):self.check()
 def test_zero_or_wrong_mode_counter(self):
  for row in (dict(mode='p121',reused_restore_tables=0,restore_extent_guards_unchanged=True),dict(mode='production',reused_restore_tables=99,restore_extent_guards_unchanged=True)):
   save(self.counter,row)
   with self.assertRaisesRegex(ValueError,'never exercised'):self.check()
 def test_every_token_and_order_required(self):
  for mutate in ('token','order','cache','miss','mode','selection','reset'):
   proof=copy.deepcopy(self.proof);view=proof['views'][1]
   if mutate=='token':view['requests'][5]['tokens'][20]=9
   if mutate=='order':view['requests'].reverse()
   if mutate=='cache':view['requests'][5]['cached_tokens']=1
   if mutate=='miss':
    for r in view['requests']:r['stats']['misses']=0
   if mutate=='mode':proof['kind']='bracket'
   if mutate=='selection':view['selection_sha256']='different'
   if mutate=='reset':view['boundary'][0]['total_reset']=False
   save(self.out/'run/bracket-inputs.json',proof)
   with self.subTest(mutation=mutate),self.assertRaises(ValueError):self.check()
 def test_raw_request_binding(self):
  save(self.out/'run/views/01-candidate'/self.prompts[1]/'receipt.json',{})
  with self.assertRaisesRegex(ValueError,'raw request'):self.check()
if __name__=='__main__':
 from build_engine import limits,save,ROOT,sha
 limits();result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(SmokeTests))
 save(P/'evidence/smoke-policy.json',dict(passed=result.wasSuccessful(),device_executed=False,tests=result.testsRun,sources={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),P/'smoke_gate.py')}))
 raise SystemExit(not result.wasSuccessful())
