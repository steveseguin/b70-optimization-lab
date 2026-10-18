import copy,json,tempfile,unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import views as V
import queue_runner as Q
import window as W
import campaign as C
import compare_bracket as B

class PortTests(unittest.TestCase):
 def test_all_eight_views(self):
  self.assertEqual(len(V.VIEWS),8)
  for view in V.VIEWS:
   row=json.loads(V.selection(view).read_text())
   self.assertEqual(set(row['choices']),{'route','recurrence','hc','down'})
   cmds=Q.commands(Path('/tmp/never-launched'),0,'2026-01-01T00:00:00Z','/lib',view)
   for cmd in cmds.values():self.assertEqual(cmd[cmd.index('--view')+1],view)
   self.assertTrue(all(W.A.window_scope(n)=='whole-host' for n in Q.ORDER))
  for bad in ('../port','E1','draft-attention',''):
   with self.assertRaises(ValueError):V.selection(bad)
 def test_k1_matches_down_layout(self):
  from argparse import Namespace
  for view in V.VIEWS:
   cmd=W.native_command(Namespace(window='K1',card=0,view=view),Path('/tmp/not-run'),None)
   self.assertEqual(cmd[cmd.index('--down-layout')+1],json.loads(V.selection(view).read_text())['choices']['down'])
 def test_bracket_order_fresh_folders(self):
  rows=C.commands('bracket',Path('/tmp/new'),'2026-01-01T00:00:00Z')
  self.assertEqual([n for n,_ in rows],['production-before','port','production-after'])
  self.assertEqual([a[a.index('--view')+1] for _,a in rows],['production','port','production'])
  self.assertEqual(len({a[a.index('--output-root')+1] for _,a in rows}),3)
 def test_plan_only_creates_nothing(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(W,'build_gate',return_value={}),patch.object(C,'P',Path(tmp)):
   out=Path(tmp)/'evidence/new'
   with patch.object(C.subprocess,'Popen',side_effect=AssertionError('must not launch')):
    self.assertEqual(C.main(['bracket','--output-root',str(out),'--plan','--faults-reviewed-through','2026-01-01T00:00:00Z']),0)
   self.assertFalse(out.exists())
 def test_record_requires_bracket(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(W,'build_gate',return_value={}),patch.object(C,'P',Path(tmp)):
   with self.assertRaisesRegex(ValueError,'completed bracket'):
    C.main(['record','--output-root',str(Path(tmp)/'evidence/new'),'--plan','--faults-reviewed-through','2026-01-01T00:00:00Z'])
 def test_campaign_preserves_losing_verdict(self):
  # Exercise the real campaign completion path with every device boundary mocked.
  for mode in ('bracket','record'):
   for wins in (False,True):
    with self.subTest(mode=mode,wins=wins),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
     root=Path(tmp);(root/'evidence').mkdir();out=root/'evidence/new'
     for obj,name,value in ((C,'P',root),(Q,'GAP_SECONDS',0)):
      stack.enter_context(patch.object(obj,name,value))
     for obj,name,value in ((W,'build_gate',{}),(W,'user_unit_gate',None),(W,'closed_environment',None),
                            (W.SUPPORT,'storage',{}),(C.os,'getpriority',0),(C.os,'sched_getaffinity',{0,1,2,3,16,17,18,19})):
      stack.enter_context(patch.object(obj,name,return_value=value))
     child=stack.enter_context(patch.object(C.subprocess,'Popen')).return_value
     child.wait.return_value=0
     stack.enter_context(patch.object(B,'compare',return_value=dict(passed=wins if mode=='bracket' else True,rates=[24.4,25,24.5])))
     fresh={B.METRIC:{'median':25 if wins else 24},'miss_path':'zero-copy'}
     stack.enter_context(patch.object(B,'verify_chain',return_value=(fresh,{},'boot')))
     args=[mode,'--output-root',str(out),'--faults-reviewed-through','2026-01-01T00:00:00Z','--authorized-device-window']
     if mode=='record':args+=['--bracket-root',str(root/'evidence/bracket')]
     self.assertEqual(C.main(args),0 if wins else 1)
     state=json.loads((out/'campaign.json').read_text())
     self.assertEqual(state['passed'],wins)
     self.assertNotIn('error',state)
 def rows(self,rates):return [{B.METRIC:{'median':x},'requests':[dict(prompt_id='a',prompt_token_sha256='x',tokens=[1,2])]} for x in rates]
 def test_improves_both_controls(self):
  self.assertTrue(B.decision(self.rows([24.4,25.0,24.5]))['passed'])
  for rates in ([24.4,24.4,24.4],[24.4,24.5,24.6],[23,25,24.4],[23.9,24,23.9]):self.assertFalse(B.decision(self.rows(rates))['passed'])
 def test_exact_output_required(self):
  rows=self.rows([24.4,25,24.5]);rows[1]['requests'][0]['tokens']=[1,3]
  with self.assertRaises(ValueError):B.decision(rows)
 def test_finite_rates(self):
  for x in (0,-1,float('nan'),float('inf'),True):
   with self.assertRaises(ValueError):B.decision(self.rows([24.4,x,24.5]))
 def test_cross_view_prerequisite_refuses(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'window.json'
   row=dict(schema='own-runtime.packet58.window.v1',passed=True,device_executed=True,child_still_running=False,window='K1',stop_reasons=[],qualifying=False,view='production',selection_sha256=V.digest('production'))
   path.write_text(json.dumps(row));identity=dict(row,view='port',selection_sha256=V.digest('port'))
   with patch.object(W.A,'verify'):
    with self.assertRaisesRegex(ValueError,'prerequisite differs: view'):W.prerequisite(path,'K1',identity)
 def test_seal_detects_input_mutation(self):
  import seal
  with tempfile.TemporaryDirectory(dir=V.P/'build') as tmp:
   root=Path(tmp);f=root/'input.json';f.write_text('{}')
   pins={'input.json':seal.sha(f)};seal.verify_files(root,pins)
   f.write_text('{"changed":true}')
   with self.assertRaisesRegex(ValueError,'changed immutable'):seal.verify_files(root,pins)
if __name__=='__main__':unittest.main()
