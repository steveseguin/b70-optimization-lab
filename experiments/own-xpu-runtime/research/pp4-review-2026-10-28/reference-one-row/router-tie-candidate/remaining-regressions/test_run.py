import importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('remaining_run',Path(__file__).with_name('run.py'));M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
class Tests(unittest.TestCase):
 def test_exact_authorities_and_repeat(self):
  rows=M.cases();self.assertEqual([len(r['prompt'])for r in rows],[244,330,489,531,541,527,244]);self.assertEqual(rows[0]['prompt'],rows[-1]['prompt']);self.assertEqual([r['saved_cpu_argmax']for r in rows],[16568,15,13662,5427,82459,35239,16568])
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'reg.json';data=json.loads(M.REG.read_text());data['cases'][1]['prefix_le_i32_sha256']='0'*64;p.write_text(json.dumps(data))
   with patch.object(M,'REG',p),self.assertRaisesRegex(ValueError,'exact forced prefix'):M.cases()
 def test_full_byte_comparison_refuses_changed_or_shorter(self):
  with tempfile.TemporaryDirectory()as d:
   a,b=[Path(d)/x for x in ['a','b']];a.write_bytes(b'a'*(1024**2+3));b.write_bytes(a.read_bytes());self.assertEqual(M.exact_files(a,b),1024**2+3)
   b.write_bytes(b'a'*(1024**2+2)+b'b')
   with self.assertRaisesRegex(ValueError,'byte mismatch'):M.exact_files(a,b)
   b.write_bytes(b'a')
   with self.assertRaisesRegex(ValueError,'extent'):M.exact_files(a,b)
 def test_equal_payload_cannot_hide_renamed_canonical_source(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);a=root/'a';b=root/'b';a.mkdir();b.mkdir();(a/'state.bundle').write_bytes(b'123');(b/'state.bundle').write_bytes(b'123')
   left=dict(path=str(a),sources={'original.bin':'hash'});right=dict(path=str(b),sources={'original.bin':'hash'});self.assertEqual(M.compare_states(left,right),3)
   right['sources']={'renamed.bin':'hash'}
   with self.assertRaisesRegex(ValueError,'source mapping'):M.compare_states(left,right)
 def test_actual_outer_sequence_gap_refuses(self):
  with tempfile.TemporaryDirectory()as d:
   t=NS(seq=[8,19]);t.start=lambda rank,*a,**k:t.seq.__setitem__(rank,t.seq[rank]+1);M.install_sequence_audit(t,Path(d)/'wire.jsonl');t.start(1,11);t.start(0,4);self.assertEqual(t.seq,[9,20]);self.assertEqual([json.loads(x)['sequence']for x in (Path(d)/'wire.jsonl').read_text().splitlines()],[20,9])
   bad=NS(seq=[8,19]);bad.start=lambda rank,*a,**k:bad.seq.__setitem__(rank,0);M.install_sequence_audit(bad,Path(d)/'bad.jsonl')
   with self.assertRaisesRegex(ValueError,'continuity'):bad.start(0,11)
 def test_partial_reset_never_admitted_or_retried(self):
  calls=[];t=NS(seq=[10,20],pending=[False,False]);a=NS()
  def partial(t,d):calls.append(d);t.seq[0]+=1;raise RuntimeError('second owner reset failed')
  a.reset=partial
  with self.assertRaisesRegex(RuntimeError,'second owner'):M.reset(a,t,Path('/unused'))
  self.assertEqual(len(calls),1)
 def test_reset_receipt_and_global_sequences(self):
  with tempfile.TemporaryDirectory()as d:
   dest=Path(d);t=NS(seq=[10,20],pending=[False,False]);a=NS()
   def reset(t,d):
    t.seq=[11,21];t.request_output=d
    for rank in [0,1]:
     p=d/f'rank{rank}';p.mkdir();(p/'reset.json').write_text(json.dumps(dict(passed=True,allocation_ids_preserved=True,allocations=17,bytes=900)))
   a.reset=reset;r=M.reset(a,t,dest);self.assertEqual(r['sequence_after'],[11,21]);self.assertEqual(len(r['receipts']),2)
   t.seq=[10,20];a.reset=lambda t,d:setattr(t,'request_output',d)
   with self.assertRaisesRegex(ValueError,'preserves/increments'):M.reset(a,t,dest)
 def test_journal_missing_or_wrong_tie_weight_refuses(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);p=root/'rank0';p.mkdir();f=p/'router-tie-diagnostic.jsonl';t=NS(request_output=root);plan={'stages':[{'id':0,'begin':3,'end':4}]}
   row=dict(position=0,layer=3,schema='ownrt.router-tie-diagnostic.v1',verified_upload=True,weights_before_sha256='a',weights_after_sha256='a',old_ids=list(range(10)),new_ids=list(range(9))+[12],changed_slots=1,changed_raw_words=[dict(slot=9,old_word=42,new_word=42)])
   f.write_text(json.dumps(row)+'\n');self.assertEqual(M.journals(t,plan,1)[0]['rows'],1)
   row['changed_raw_words'][0]['new_word']=43;f.write_text(json.dumps(row)+'\n')
   with self.assertRaisesRegex(ValueError,'equal raw'):M.journals(t,plan,1)
   row['changed_raw_words'][0]['new_word']=42;row['weights_after_sha256']='b';f.write_text(json.dumps(row)+'\n')
   with self.assertRaisesRegex(ValueError,'unchanged weight'):M.journals(t,plan,1)
   f.write_text('')
   with self.assertRaisesRegex(ValueError,'complete actual'):M.journals(t,plan,1)
 def test_only_two_source_proven_cache_extents_may_differ(self):
  initial=dict(launch_extent=32,alternate_launch_extent=32,loaded_layer=[-1],fp32_cache=[{'source':None,'extent':0}],history0=248044,history1=248044,bank_parity=0,standalone_target_mutable={'scratch':{'bytes':4,'sha256':'a'}})
  actual=dict(initial,launch_extent=576,alternate_launch_extent=544);proof=M.compare_inventory(initial,actual);self.assertTrue(proof['fields']['launch_extent']['changed'])
  for key,value in [('loaded_layer',[3]),('fp32_cache',[{'source':'changed','extent':1}]),('history0',0),('standalone_target_mutable',{})]:
   with self.assertRaisesRegex(ValueError,'non-cache'):M.compare_inventory(initial,dict(actual,**{key:value}))
  for bad in [0,31,33,4097,True]:
   with self.assertRaisesRegex(ValueError,'geometry'):M.compare_inventory(initial,dict(actual,launch_extent=bad))
 def test_forced_positions_cannot_omit_or_speculate(self):
  a=NS(BASE=NS(HALF=1));r={'tokens':[7],'stats':{'guesses':0},'rank_trace':[dict(rank=rank,op=1,position=p,speculative=False)for rank in [0,1]for p in range(3)]};M.validate_trace(r,3,a)
  r['rank_trace'].pop()
  with self.assertRaisesRegex(ValueError,'every actual'):M.validate_trace(r,3,a)
if __name__=='__main__':unittest.main()
