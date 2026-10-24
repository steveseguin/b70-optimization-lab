"""Focused preparation tests; no tokenizer/model/device/operational plan calls."""
import copy,importlib.util,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('expanded_once_test',P/'once.py');W=importlib.util.module_from_spec(s);s.loader.exec_module(W)
H=W.H;Q=H.Q;S=H.S;A=H.A;C=H.C
s=importlib.util.spec_from_file_location('expanded_fake_parent',H.L/'baseline/test_suite.py');F=importlib.util.module_from_spec(s);s.loader.exec_module(F)
class Tests(unittest.TestCase):
 def test_command_actual_only_native_startup_changes(self):
  p=dict(output='/private',evidence_output='/external',binary='/qualified',context=4096,seconds=7200,max_new=512,mini=False)
  for rank in (0,1):
   old=H.COMMAND(p,rank,31,32);new=H.command(p,rank,31,32);i=old.index('--max-new')+1;self.assertEqual(old[i],'512');old[i]='128';self.assertEqual(old,new)
  self.assertEqual(p['max_new'],512)
  with self.assertRaises(ValueError):H.command(dict(p,startup_max_new=512),0,31,32)
 def test_real_builder_before_distinction_fields(self):
  with tempfile.TemporaryDirectory() as td,patch.object(H,'review_sources',return_value={}):
   p=H.adapter_build(Path(td)/'control',evidence_output=Path(td)/'evidence')
   for argv in p['rank_argv']:self.assertEqual(argv[argv.index('--max-new')+1],'128')
   self.assertEqual((p['max_new'],p['startup_max_new'],p['measured_request_max_new']),(512,128,512))
   A.validate_plan(p)
 def test_actual_rpc_serialization_all26_caps(self):
  m=H.manifest()
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'native-result.json').write_text(json.dumps(dict(rank_trace=[],work_start=1,work_end=2,stats=dict(hits=0,guesses=0),decode_intervals=0,decode_wall_ms=0)))
   t=types.SimpleNamespace(shared_path=p/'shared.bin',trace=[],a=types.SimpleNamespace(draft_fault='none'),device=False,start=lambda *a:None,wait=lambda *a:None)
   cases=[(w['mode'],w['tokens'],8,()) for w in m['warmup']]+[(mode,row['tokens'],512,(248044,248046)) for row in m['prompts'] for mode in row['order']]
   caps=[]
   for mode,tokens,cap,eos in cases:
    A.BASE.NativeController(t,A.BASE.Draft(mode),True,False).run(tokens,cap,eos)
    fields=list(map(int,(p/'native-request.txt').read_text().split()));caps.append(fields[1]);self.assertEqual(fields[4],len(tokens));self.assertLessEqual(fields[1]+fields[4],4096)
   self.assertEqual(caps,[8,8]+[512]*24)
 def test_prefix_only_and_natural_eos(self):
  row=dict(name='prompt-00-none',mode='none',prompt_tokens=[1],requested_max_new=512,result={'tokens':[2]*512},state_sha256={'different512':'allowed'})
  ref=dict(mode='none',prompt_tokens=[1],result={'tokens':[2]*128},state_sha256={'old128':'notcompared'})
  with patch.object(C,'REFERENCES',{row['name']:ref}):
   H.check_prefix(row);bad=copy.deepcopy(row);bad['result']['tokens'][17]=3
   with self.assertRaises(ValueError):H.check_prefix(bad)
   ref['result']['tokens']=[2,248046];row['result']['tokens']=[2,248046];H.check_prefix(row)
   row['result']['tokens'].append(2)
   with self.assertRaises(ValueError):H.check_prefix(row)
 def test_full_schedule_uses_same_ack_budget_and_full_pair_states(self):
  m=H.manifest();refs={f'prompt-{i:02d}-{mode}':dict(mode=mode,prompt_tokens=p['tokens'],result={'tokens':[2]*128}) for i,p in enumerate(m['prompts']) for mode in p['order']}
  with tempfile.TemporaryDirectory() as td:
   t,reset,controller,dump=F.SuiteTests().fixture(td);plan=dict(lifetime_seconds=7200,manifest_sha256=H.sha(H.MANIFEST));decoded=[]
   with patch.object(Q,'RESET',reset),patch.object(Q,'DUMP',dump),patch.object(Q,'CLOSE',return_value=None),patch.object(Q,'check_space'),patch.object(A.BASE,'NativeController',controller),patch.object(C,'bind_references'),patch.object(C,'REFERENCES',refs),patch.object(C,'capture_stamp',return_value={}),patch.object(C,'verify_capture_stamps'),patch.object(H,'read_rubrics',return_value={}),patch.object(H,'retain_decoded',side_effect=lambda d,r,b:decoded.append(r['name'])):
    out=Q.run_attached(t,plan);Q.close(t,True)
   self.assertEqual(len(t.calls),26);self.assertEqual(len(t.resets),26);self.assertEqual(len(decoded),24)
   self.assertTrue(out['capture_budget']['finished']);self.assertEqual(out['capture_budget']['remaining_payload_bytes'],0);self.assertEqual(len(out['capture_budget']['events']),52)
   self.assertEqual(out['output_cap'],512);self.assertFalse(out['quality_qualified']);self.assertTrue(out['manual_full_output_review_required'])
   for pair in out['prompts']:
    self.assertTrue(pair['exact_final_target_state']);self.assertEqual([a['requested_max_new'] for a in pair['arms']],[512,512])
 def test_eos_cap_visible_and_private_exception_identity(self):
  self.assertIs(W.O.S,S);self.assertIs(W.O.S.A.RetainedOwner,A.RetainedOwner)
  for mod in (Q,Q.X,W.O,W.M):self.assertEqual(mod.CONTROL,W.CONTROL)
  self.assertEqual(W.UNIT,'gsq-quality-expanded-a.service')
  authority=H.actual_authority();self.assertEqual(authority['review_sha256'],'ccd77d4456f5c66eb0a64d7456a3abb8a23528ab390924c703b471deece6aced')
 def test_extra_initial_margin_and_unchanged_ongoing_reserves(self):
  b=Q.B.Budget();threshold=Q.B.EXTERNAL_FLOOR+Q.B.META+b.remaining+H.INITIAL_METADATA_MARGIN
  self.assertEqual(threshold,8933302060);H.initial_metadata_admission(threshold,b)
  with self.assertRaises(ValueError):H.initial_metadata_admission(threshold-1,b)
  b.reset();H.initial_metadata_admission(Q.B.EXTERNAL_FLOOR+Q.B.META+b.remaining,b)
  Q.B.check_free(Q.B.ROOT_FLOOR+Q.B.ROOT_CACHE,Q.B.EXTERNAL_FLOOR+Q.B.META+b.remaining,b)
  with self.assertRaises(ValueError):Q.B.check_free(Q.B.ROOT_FLOOR+Q.B.ROOT_CACHE,Q.B.EXTERNAL_FLOOR+Q.B.META+b.remaining-1,b)
if __name__=='__main__':unittest.main(verbosity=2)
