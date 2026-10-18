"""CPU safety/admission regressions for a topology-changing v4 bracket."""
import copy,json,os,resource,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import bundle_selection as b
from memory_plans import plan
from memory_gate import configuration,check,ARENA_LIMIT_BYTES
from bracket_report import gains_pass
P=Path(__file__).resolve().parent
class Packet120(unittest.TestCase):
 def ledger(self):return plan(b.views()['25-23'])
 def test_exact_two_placements_one_arithmetic(self):
  self.assertEqual(set(b.views()),{'production','25-23'})
  self.assertEqual(b.selection(b.views()['production']),b.selection(b.views()['25-23']))
  self.assertEqual(b.PLACEMENTS,{'1':(1,0,24),'25-23':(1,25,25)})
  self.assertEqual(len(b.configurations()),2)
 def test_vram_exact_and_headroom(self):
  row=self.ledger()
  actual=configuration(row,4096,1,25)['ranks']
  self.assertEqual([r['arena_device_bytes'] for r in actual],[29276806152,30296914384])
  self.assertTrue(all(r['arena_headroom_bytes']>=512*1024**2 for r in actual))
 def test_disallowed_topologies(self):
  for context,rank,split in [(32768,1,25),(4096,0,25),(256,1,25),(4096,1,26)]:
   with self.assertRaises(ValueError):configuration(self.ledger(),context,rank,split)
 def test_candidate_arena_reserve_is_binding(self):
  value=self.ledger();r=value['placements']['25-23']['capacities']['4096']['ranks'][0]
  delta=ARENA_LIMIT_BYTES-512*1024**2+1-r['arena_device_bytes']
  for k in ('target_modeled_allocations_bytes','target_total_bytes','total_with_mtp_bytes','arena_device_bytes'):r[k]+=delta
  r['free_with_mtp_bytes']-=delta;r['arena_headroom_bytes']-=delta
  with self.assertRaisesRegex(ValueError,'0.5 GiB'):configuration(value,4096,1,25)
 def test_census_inconsistency_refuses(self):
  import gzip
  census=json.loads(gzip.decompress((P/'evidence/census-first-25-23-rank0.json.gz').read_bytes()))
  check(census,self.ledger(),0,True,4096,1,25)
  census['totals']['device']-=1
  with self.assertRaisesRegex(ValueError,'differs'):check(census,self.ledger(),0,True,4096,1,25)
 def test_threshold_both_controls(self):
  self.assertTrue(gains_pass([100,100*1.005,100]))
  self.assertFalse(gains_pass([100,100.49,100]))
  self.assertFalse(gains_pass([100,100.5,100.01]))
  self.assertFalse(gains_pass([0,101,100]))
 def test_imports_preserve_limits(self):
  from exec_limits import snapshot
  before=snapshot()
  import screen_job,bracket_report,run_screen,runtime_worker
  self.assertEqual(snapshot(),before)
 def test_old_cap_refused_in_isolated_process(self):
  code="import resource;resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));import exec_limits;exec_limits.check(exec_limits.snapshot())"
  result=subprocess.run([sys.executable,'-B','-c',code],cwd=P,stdin=subprocess.DEVNULL,capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0);self.assertIn('refuses finite RLIMIT_AS',result.stderr)
 def test_stop_pipe_survives_receipt_and_hook_failure(self):
  import chain_pipeline as pp
  read_fd,write_fd=os.pipe()
  try:
   t=pp.Transport.__new__(pp.Transport);t.stop_sent=False;t.closed=False;t.children=[];t.out=Path('/unused');t.stop_write=write_fd
   t.failure_hook=Mock(side_effect=OSError('hook unavailable'))
   with patch.object(pp,'save',side_effect=OSError('disk full')):t.stop('test')
   self.assertTrue(t.stop_sent);self.assertEqual(os.read(read_fd,1),b'!');self.assertEqual(len(t.stop_errors),2)
   t.stop('again');self.assertEqual(t.failure_hook.call_count,1)
  finally:os.close(read_fd);os.close(write_fd)
 def test_no_device_parser_switch_in_place(self):
  from run_screen import packet_parser
  parser=packet_parser();action=next(a for a in parser._actions if a.dest=='placement')
  self.assertEqual(action.choices,('1','25-23'))
 def test_memory_requires_real_rank_counters(self):
  from memory_observation import clients,validate
  pci=['0000:43:00.0','0000:47:00.0'];admission={'ranks':[]};observation=dict(phase='ready',device_nodes_opened=False,ranks=[])
  for rank in (0,1):
   raw=dict(pid=100+rank,phase='ready',drm_fdinfo={'13':[f'drm-pdev: {pci[rank]}',f'drm-client-id: {rank+1}','drm-total-vram0: 28 GiB','drm-resident-vram0: 27 GiB']})
   admission['ranks'].append(dict(rank=rank,device_allocation_bytes=123,process={'pid':100+rank}))
   observation['ranks'].append(dict(rank=rank,allocator_device_bytes=123,process=raw,unique_clients=clients(raw)))
  self.assertTrue(validate(observation,'ready',admission,pci))
  for mutation in ('empty','pid','phase','rank','allocator','counter'):
   bad=copy.deepcopy(observation)
   if mutation=='empty':bad['ranks'][0]['process']['drm_fdinfo']={};bad['ranks'][0]['unique_clients']=[]
   if mutation=='pid':bad['ranks'][0]['process']['pid']=999
   if mutation=='phase':bad['phase']='after-suite'
   if mutation=='rank':bad['ranks'][0]['rank']=1
   if mutation=='allocator':bad['ranks'][0]['allocator_device_bytes']=124
   if mutation=='counter':
    bad['ranks'][0]['process']['drm_fdinfo']['13']=bad['ranks'][0]['process']['drm_fdinfo']['13'][:2]
    bad['ranks'][0]['unique_clients']=clients(bad['ranks'][0]['process'])
   with self.subTest(mutation=mutation),self.assertRaises(AssertionError):validate(bad,'ready',admission,pci)
 def test_duplicate_drm_fds_do_not_double_count(self):
  from memory_observation import clients
  lines=['drm-pdev: 0000:43:00.0','drm-client-id: 1','drm-total-vram0: 28 GiB','drm-resident-vram0: 27 GiB']
  rows=clients({'drm_fdinfo':{'13':lines,'14':lines}})
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['bytes']['drm-resident-vram0'],27*1024**3)
 def test_A_waits_before_launch(self):
  import screen_job,bracket_report
  from screen_jobs import jobs,output
  with patch.object(screen_job,'verify'),patch.object(bracket_report,'bracket',return_value={'passed':False}),patch('run_screen.main') as run:
   with self.assertRaisesRegex(AssertionError,'lane A waits'):
    screen_job.main(['--lane','A','--index','0','--output',str(output(jobs('A')[0])),'--fault-review','unused','--authorized-device-window'])
   run.assert_not_called()
if __name__=='__main__':unittest.main()
