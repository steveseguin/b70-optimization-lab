import importlib.util,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('coverage_b_test',P/'once.py');W=importlib.util.module_from_spec(s);s.loader.exec_module(W)
class Launch(unittest.TestCase):
 def plan(self):return dict(output='/private',evidence_output='/external',binary='/qualified',context=4096,seconds=7200,max_new=512,mini=False,startup_max_new=128,request_max_new_by_case=[512,512,128])
 def test_actual_command_only_startup_value_changes(self):
  p=self.plan()
  for rank in (0,1):
   old=W.original_command(p,rank,31,32);new=W.command(p,rank,31,32);i=old.index('--max-new')+1
   self.assertEqual(old[i],'512');self.assertEqual(new[i],'128');old[i]='128';self.assertEqual(old,new)
  self.assertEqual(p['max_new'],512)
 def test_actual_controller_writes_unchanged_rpc_counts(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);result=dict(rank_trace=[],work_start=1,work_end=2,stats=dict(hits=0,guesses=0),decode_intervals=0,decode_wall_ms=0)
   (p/'native-result.json').write_text(json.dumps(result))
   b=types.SimpleNamespace(shared_path=p/'shared.bin',trace=[],a=types.SimpleNamespace(draft_fault='none'),device=False,start=lambda *args:None,wait=lambda *args:None)
   observed=[]
   for case in W.S.manifest()['cases']:
    for mode in case['order']:
     W.A.BASE.NativeController(b,W.A.BASE.Draft(mode),True,False).run(case['tokens'],case['max_new'],(248044,248046))
     fields=list(map(int,(p/'native-request.txt').read_text().split()));observed.append(fields[1]);self.assertEqual(fields[4],len(case['tokens']));self.assertLessEqual(fields[1]+fields[4],4096)
   self.assertEqual(observed,[512,512,512,512,128,128])
 def test_all_plan_layers_bind_correction(self):
  pins={'correction':'test'}
  with patch.object(W,'correction_pins',return_value=pins),patch.object(W,'original_adapter_plan',return_value=dict(max_new=512,mini=False,source_sha256={})),patch.object(W,'original_suite_plan',return_value=dict(source_sha256={})),patch.object(W,'original_outer_plan',return_value=dict(source_sha256={})):
   for p in [W.adapter_plan(),W.suite_plan(),W.build_plan()]:
    self.assertEqual(p['startup_max_new'],128);self.assertEqual(p['request_max_new_by_case'],[512,512,128]);self.assertEqual(p['source_sha256'],pins)
 def test_globals_retained_owner_and_bad_startup_refusal(self):
  self.assertIs(W.O.S,W.S);self.assertIs(W.O.S.A.RetainedOwner,W.A.RetainedOwner)
  for m in (W.Q,W.O,W.M):self.assertEqual(m.CONTROL,W.CONTROL);self.assertEqual(m.EVIDENCE,W.EVIDENCE);self.assertEqual(m.UNIT,W.UNIT)
  p=self.plan();p['startup_max_new']=512
  with self.assertRaisesRegex(ValueError,'startup/request'):W.command(p,0,31,32)
if __name__=='__main__':unittest.main(verbosity=2)
