"""CPU decision and safety regressions; synthetic receipts never qualify devices."""
import copy,gzip,json,os,resource,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import bundle_selection as b
from memory_plans import plan
from memory_gate import configuration,check,ARENA_LIMIT_BYTES
P=Path(__file__).resolve().parent
class Packet127(unittest.TestCase):
 def test_three_views_only_head_changes(self):
  views=b.labelled_views();self.assertEqual(set(views),{'production','81920','122880'})
  production=b.selection(views['production'])
  for label,v in views.items():
   row=b.selection(v);head=row['choices'].pop('head');expected=copy.deepcopy(production);expected['choices'].pop('head')
   self.assertEqual(row,expected);self.assertGreaterEqual(248320-b.suffix_rows(v),80128)
  self.assertEqual(b.PLACEMENTS,{'1':(1,0,24)})
 def test_full_census_all_six(self):
  shape=json.loads((P/'evidence/full-shape.json').read_text());self.assertEqual(len(shape['runs']),6)
  for r in shape['runs']:
   v=b.views()[r['view']];f=P.parents[3]/r['artifacts']['census.json']['path'];c=json.loads(gzip.decompress(f.read_bytes()))
   check(c,plan(v),r['rank'],True,4096,1,0)
   self.assertGreaterEqual(ARENA_LIMIT_BYTES-c['totals']['device'],512*1024**2)
   c['totals']['device']-=1
   with self.assertRaisesRegex(ValueError,'differs'):check(c,plan(v),r['rank'],True,4096,1,0)
 def test_unsupported_context_and_placement(self):
  ledger=plan(b.labelled_views()['81920'])
  for args in ((32768,1,0),(4096,0,0),(4096,1,25)):
   with self.assertRaises(ValueError):configuration(ledger,*args)
 def test_both_controls_threshold(self):
  from bracket_report import gains_pass
  self.assertTrue(gains_pass([100,100*1.005,100]))
  for rates in ([100,100.49,100],[100,100.5,100.01],[0,101,100]):self.assertFalse(gains_pass(rates))
 def test_A_waits_before_launch(self):
  import screen_job,bracket_report,run_screen
  from screen_jobs import jobs,output
  with patch.object(screen_job,'verify'),patch.object(bracket_report,'bracket',return_value={'passed':False}),patch.object(run_screen,'main') as run:
   with self.assertRaisesRegex(AssertionError,'A waits'):
    screen_job.main(['--lane','A','--index','0','--output',str(output(jobs('A','81920')[0])),'--fault-review','unused','--authorized-device-window'])
   run.assert_not_called()
 def test_micro_gate_refuses_missing_before_grid(self):
  import screen_job,run_screen,device_gate
  from screen_jobs import jobs,output
  with patch.object(screen_job,'verify'),patch.object(device_gate,'require_micro',side_effect=AssertionError('micro pending')),patch.object(run_screen,'main') as run:
   with self.assertRaisesRegex(AssertionError,'micro pending'):
    screen_job.main(['--lane','B','--index','0','--output',str(output(jobs('B')[0])),'--fault-review','unused','--authorized-device-window'])
   run.assert_not_called()
 def test_grid_and_confirm_order(self):
  from screen_jobs import jobs
  self.assertEqual([r['choice'] for r in jobs('B')],['production','81920','122880','production'])
  for winner in ('81920','122880'):
   self.assertEqual([r['choice'] for r in jobs('A',winner)],['production',winner,'production'])
   self.assertEqual(jobs('A',winner)[1]['out'],'p127-A-confirm-1-winner')
 def test_imports_do_not_change_limits(self):
  from exec_limits import snapshot
  before=snapshot();import run_micro,screen_job,bracket_report,run_screen,runtime_worker
  self.assertEqual(snapshot(),before)
 def test_micro_uses_fixed_local_lifecycle(self):
  import run_micro,drain_gate,conditions,bootstrap
  self.assertEqual(Path(drain_gate.__file__).resolve(),P/'drain_gate.py')
  self.assertEqual(Path(conditions.__file__).resolve(),P/'conditions.py')
  self.assertIs(run_micro.DrainPermit,drain_gate.DrainPermit)
 def test_inherited_cap_refused(self):
  code='import resource;resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));import exec_limits;exec_limits.check(exec_limits.snapshot())'
  cp=subprocess.run([sys.executable,'-B','-c',code],cwd=P,stdin=subprocess.DEVNULL,capture_output=True,text=True)
  self.assertNotEqual(cp.returncode,0);self.assertIn('refuses finite RLIMIT_AS',cp.stderr)
 def test_stop_pipe_survives_receipt_failure(self):
  import chain_pipeline as pp
  r,w=os.pipe()
  try:
   t=pp.Transport.__new__(pp.Transport);t.stop_sent=False;t.closed=False;t.children=[];t.out=Path('/unused');t.stop_write=w;t.failure_hook=Mock(side_effect=OSError('hook unavailable'))
   with patch.object(pp,'save',side_effect=OSError('disk full')):t.stop('test')
   self.assertTrue(t.stop_sent);self.assertEqual(os.read(r,1),b'!');self.assertEqual(len(t.stop_errors),2)
  finally:os.close(r);os.close(w)
 def test_teardown_clock_crossing_fixed(self):
  import conditions
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);out=root/'output';out.mkdir();clock=iter((59.9,60.1,60.2,60.3,60.4));sleeps=[]
   permit=conditions.Teardown(out,root=root,now=lambda:next(clock),sleep=lambda n:sleeps.append(n))
   (root/'teardown-state.json').write_text(json.dumps(dict(boot_id=permit.boot,drained=True,completed_monotonic=0)))
   with permit:pass
   self.assertEqual(sleeps,[0.0])
if __name__=='__main__':unittest.main()
