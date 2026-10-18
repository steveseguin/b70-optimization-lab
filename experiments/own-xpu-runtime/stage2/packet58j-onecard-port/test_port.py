import copy,json,tempfile,unittest
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
   cmds=Q.commands(Path('/tmp/never-launched'),'0' if False else 0,'2026-01-01T00:00:00Z','/lib',view)
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
if __name__=='__main__':unittest.main()
