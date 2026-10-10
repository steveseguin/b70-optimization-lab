"""CPU integration tests: temp executables replace every operational command."""
import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import stream_ops as ops

ARGS = '145 frame 1 cone 1 1 fingerprint - eager-display 0 full xpu:3 -'.split()
ARM = {'LTX_TEXT_RESIDENCY': 'split36', 'LTX_CONE_GRAPH_MEMORY': 'text-shift',
       'LTX_GC_INTERVAL_SECONDS': '60', 'LTX_STORAGE_SCAN_MODE': 'background',
       'LTX_SNAPSHOT_DIGEST_CACHE': '1', 'LTX_MAINTENANCE_MODE': 'idle'}
MOCK = r'''import json, os, pathlib, sys
root = pathlib.Path(os.environ['MOCK_ROOT'])
mode = sys.argv[1]; args = sys.argv[2:]
cfg = json.loads((root/'config').read_text())
clock = float((root/'clock').read_text())
with (root/'calls').open('a') as f:
 f.write(json.dumps({'mode':mode,'args':args,'time':clock,'env':{k:v for k,v in os.environ.items() if k.startswith('LTX_')}})+'\n')
if mode == 'systemctl':
 if 'list-units' in args: print(cfg.get('units','ltx133b-stream-client-20261010.service loaded active running\nltx133b-stream-server-20261010.service loaded active running\nltx117-stream-sink.service loaded active running'))
 elif '--property=KillSignal,SendSIGKILL,KillMode' in args:
  print('KillSignal=2\nSendSIGKILL=yes\nKillMode=control-group' if cfg.get('unsafe_sink') and 'ltx117-stream-sink.service' in args else cfg.get('properties','KillSignal=2\nSendSIGKILL=no\nKillMode=control-group'))
 elif '--property=ActiveState,MainPID,ControlPID,TasksCurrent,ControlGroup' in args: print('ActiveState='+cfg.get('state','inactive')+'\nMainPID='+str(cfg.get('main_pid',0))+'\nControlPID=0\nTasksCurrent='+str(cfg.get('tasks',0))+'\nControlGroup=/mock')
 elif 'stop' in args and cfg.get('stop_fail'): sys.exit(1)
elif mode == 'journal':
 print(cfg.get('journal',''))
 if cfg.get('journal_fail'): sys.exit(1)
elif mode == 'health':
 if cfg.get('health_fail'): sys.exit(1)
 pathlib.Path(args[-1]).write_text('invalid' if cfg.get('health_malformed') else json.dumps({'passed':cfg.get('health_passed',True)}))
 (root/'clock').write_text(str(clock+cfg.get('health_duration',20)))
elif mode == 'launcher':
 if args[-1] == '--check-only':
  if cfg.get('check_fail'): sys.exit(2)
 else:
  if cfg.get('launch_fail'): sys.exit(2)
elif mode == 'curl':
 if cfg.get('startup_fault'): (root/'results/FAULT.json').write_text('{}')
 (root/'clock').write_text(str(clock+cfg.get('curl_duration',0)))
 countfile=root/'polls'; count=int(countfile.read_text()) if countfile.exists() else 0
 countfile.write_text(str(count+1))
 if count < cfg.get('connection_failures',0): sys.exit(7)
 if cfg.get('malformed_status'): print('not-json')
 else: print(json.dumps(cfg.get('status',{'phase':'stream_setup','halted':None,'fault':False,'packet':135,'receipt_dir':os.environ['MOCK_EXPECTED_RUN']+'/receipts'})))
elif mode in ('client','sink'):
 if cfg.get(mode+'_fail'): sys.exit(2)
'''

class FakeClock:
    def __init__(self, root):
        self.root, self.sleeps, self.on_sleep = root, [], None
    def monotonic(self):
        return float((self.root/'clock').read_text())
    def sleep(self, seconds):
        self.sleeps.append(seconds)
        (self.root/'clock').write_text(str(self.monotonic()+seconds))
        if self.on_sleep: self.on_sleep()
    def utc(self):
        return '2026-10-10T00:00:00+00:00'

class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ltx-ops-cpu-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lane, self.results, self.work_root = (self.root/x for x in ('lane','results','work'))
        for p in (self.lane/'stream', self.lane/'scripts', self.results, self.work_root, self.lane/'data/resume-20261008'):
            p.mkdir(parents=True)
        (self.root/'clock').write_text('1000'); (self.root/'config').write_text('{}')
        (self.root/'mock.py').write_text(MOCK)
        self.config = {}
        self.env = {k:v for k,v in os.environ.items() if not k.startswith('LTX_')}
        self.env.update(ARM, MOCK_ROOT=str(self.root))
        self.env['MOCK_EXPECTED_RUN']=str(self.results/ops.run_name('135',ARGS,self.env))
        self.clock = FakeClock(self.root)
        for name, mode in [('systemctl','systemctl'),('journalctl','journal'),('curl','curl'),('python','health')]:
            self.executable(self.root/name,mode)
        folder=self.lane/'recovery/20261010-continuation135-stream'; folder.mkdir(parents=True)
        self.executable(folder/'launch-135.sh','launcher','UNIT=ltx135-stream-server-20261010\n# '+ ' '.join(ARM)+'\n')
        self.executable(self.lane/'stream/start-client-135.sh','client')
        self.executable(self.work_root/'start-sink-117.sh','sink')
        self.paths=ops.Paths(lane=self.lane,results=self.results,work_root=self.work_root,
            sink=self.work_root/'start-sink-117.sh',python=str(self.root/'python'),
            systemctl=str(self.root/'systemctl'),journalctl=str(self.root/'journalctl'),curl=str(self.root/'curl'))
        self.operation=ops.Operation('135',self.work_root/'fresh',ARGS,self.env,paths=self.paths,clock=self.clock)
    def executable(self,path,mode,prefix=''):
        import shlex
        path.write_text('#!/bin/bash\nset -euo pipefail\n'+prefix+'exec '+shlex.join([sys.executable,'-B',str(self.root/'mock.py'),mode])+' "$@"\n')
        path.chmod(0o755)
    def configure(self,**kwargs):
        self.config.update(kwargs); (self.root/'config').write_text(json.dumps(self.config))
    def run_op(self,refused=None):
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            if refused:
                with self.assertRaisesRegex((ops.Refusal,ValueError),refused): self.operation.run()
            else: self.operation.run()
    def calls(self,mode=None):
        path=self.root/'calls'
        rows=[json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        return [c for c in rows if mode is None or c['mode']==mode]
    def no_launch(self):
        self.assertFalse([c for c in self.calls('launcher') if c['args'][-1]!='--check-only'])
        self.assertFalse(self.calls('client')); self.assertFalse(self.calls('sink'))
    def test_happy_path_order_environment_and_receipt(self):
        self.run_op()
        stops=[c['args'][-1] for c in self.calls('systemctl') if 'stop' in c['args']]
        self.assertEqual(stops,['ltx133b-stream-client-20261010.service','ltx133b-stream-server-20261010.service','ltx117-stream-sink.service'])
        self.assertEqual([c['mode'] for c in self.calls() if c['mode'] in ('health','launcher','client','sink')],['health','launcher','launcher','client','sink'])
        self.assertEqual(self.calls('client')[0]['args'],'145 1 cone 1 1 fingerprint none eager-display 0 full xpu:3'.split())
        for c in self.calls():
            self.assertEqual(c['env']['LTX_STREAM_WORKDIR'],str(self.work_root/'fresh'))
            self.assertEqual(c['env']['LTX_TEXT_RESIDENCY'],'split36')
        receipt=json.loads(self.operation.receipt.read_text())
        self.assertEqual(receipt['status'],'complete'); self.assertTrue(Path(receipt['health_receipt']).is_file())
    def test_gap_subtracts_health(self):
        self.run_op(); self.assertEqual(sum(self.clock.sleeps),285); self.assertEqual(self.calls('launcher')[-1]['time'],1305)
    def test_gap_already_elapsed(self):
        self.configure(health_duration=400); self.run_op(); self.assertEqual(self.clock.sleeps,[])
    def test_archive_categories_and_target_run(self):
        originals=[]
        for cat in ('output','output/validation','requests'):
            directory=self.results/cat; directory.mkdir(parents=True,exist_ok=True)
            for pkt in ('133b','135'):
                p=directory/f'stream{pkt}-same.json'; p.write_text(cat); originals.append(p)
            (directory/'unrelated.json').write_text('keep')
        oldrun=self.results/ops.run_name('135',ARGS,self.env); oldrun.mkdir(); (oldrun/'evidence').write_text('keep')
        self.run_op(); self.assertTrue(all(not p.exists() for p in originals))
        receipt=json.loads(self.operation.receipt.read_text()); self.assertEqual(len(receipt['moves']),7)
        self.assertEqual(Path(receipt['moves'][-1]['destination'],'evidence').read_text(),'keep')
        self.assertTrue(all((self.results/c/'unrelated.json').exists() for c in ('output','output/validation','requests')))
    def test_fault_before_any_command(self):
        (self.results/'FAULT.json').write_text('{}'); self.run_op('FAULT.json'); self.assertEqual(self.calls(),[])
        self.assertEqual(json.loads(self.operation.receipt.read_text())['status'],'refused')
    def test_unrequested_latch_preserved(self):
        p=self.results/'display-replica-120-refused.json'; p.write_text('{}'); self.run_op(); self.assertTrue(p.exists())
    def test_fault_during_gap(self):
        self.clock.on_sleep=lambda:(self.results/'FAULT.json').write_text('{}'); self.run_op('FAULT.json'); self.no_launch()
    def test_latch_during_gap(self):
        self.clock.on_sleep=lambda:(self.results/'decoder-graph-116-refused.json').write_text('{}'); self.run_op('decoder-graph'); self.no_launch()
    def test_health_exit_refusal(self):
        self.configure(health_fail=True); self.run_op('command refused'); self.no_launch(); self.assertFalse(self.calls('launcher'))
    def test_health_false_receipt(self):
        self.configure(health_passed=False); self.run_op('health receipt'); self.no_launch()
    def test_health_malformed_receipt(self):
        self.configure(health_malformed=True); self.run_op('Expecting value'); self.no_launch()
    def test_check_only_refusal(self):
        self.configure(check_fail=True); self.run_op('command refused'); self.no_launch(); self.assertEqual(len(self.calls('launcher')),1)
    def test_stop_refusal(self):
        self.configure(stop_fail=True); self.run_op('command refused'); self.no_launch(); self.assertFalse(self.calls('health'))
    def test_unsafe_stop_settings(self):
        self.configure(properties='KillSignal=2\nSendSIGKILL=yes'); self.run_op('SIGKILL')
        self.assertFalse([c for c in self.calls('systemctl') if 'stop' in c['args']])
    def test_last_unit_unsafe_causes_zero_stops(self):
        self.configure(unsafe_sink=True); self.run_op('SIGKILL')
        self.assertFalse([c for c in self.calls('systemctl') if 'stop' in c['args']])
    def test_wrong_signal(self):
        self.configure(properties='KillSignal=15\nSendSIGKILL=no'); self.run_op('SIGINT'); self.no_launch()
    def test_still_active(self):
        self.configure(state='deactivating'); self.run_op('still active'); self.no_launch()
    def test_failed_unit_with_live_process_refuses(self):
        self.configure(state='failed',main_pid=42,tasks=1); self.run_op('process drain'); self.no_launch()
    def test_kernel_fault(self):
        self.configure(journal='xe: Fault response'); self.run_op('kernel fault'); self.no_launch(); self.assertFalse(self.calls('health'))
    def test_journal_unavailable(self):
        self.configure(journal_fail=True); self.run_op('command refused'); self.no_launch()
    def test_ambiguous_units(self):
        self.configure(units='ltx133b-stream-server-20261010.service loaded active running\nltx135-stream-server-20261010.service loaded active running')
        self.run_op('ambiguous'); self.no_launch()
    def test_mismatched_units(self):
        self.configure(units='ltx133b-stream-client-20261010.service loaded active running\nltx135-stream-server-20261010.service loaded active running')
        self.run_op('mismatch'); self.no_launch()
    def test_no_units_after_halt(self):
        self.configure(units=''); self.run_op(); self.assertFalse([c for c in self.calls('systemctl') if 'stop' in c['args']])
    def test_launch_failure_never_retried(self):
        self.configure(launch_fail=True); self.run_op('command refused'); self.assertEqual(len(self.calls('launcher')),2); self.assertFalse(self.calls('client'))
    def test_halted_status(self):
        self.configure(status={'phase':'stream_setup','halted':'storage','fault':False}); self.run_op('halted'); self.assertFalse(self.calls('client')); self.assertEqual(len(self.calls('curl')),1)
    def test_fault_status(self):
        self.configure(status={'phase':'stream_setup','halted':None,'fault':True}); self.run_op('faulted'); self.assertFalse(self.calls('client'))
    def test_fault_appears_during_startup(self):
        self.configure(startup_fault=True); self.run_op('FAULT.json'); self.assertFalse(self.calls('client'))
        self.assertEqual(len(self.calls('launcher')),2)
    def test_missing_status_fields(self):
        self.configure(status={'phase':'stream_setup'}); self.run_op('explicit'); self.assertFalse(self.calls('client'))
    def test_malformed_status(self):
        self.configure(malformed_status=True); self.run_op('Expecting value'); self.assertFalse(self.calls('client'))
    def test_connection_wait_without_relaunch(self):
        self.configure(connection_failures=2); self.run_op(); self.assertEqual(len(self.calls('curl')),3); self.assertEqual(len(self.calls('launcher')),2)
    def test_status_timeout(self):
        self.configure(status={'phase':'loading','halted':None,'fault':False},curl_duration=100); self.run_op('deadline')
        self.assertLessEqual(len(self.calls('curl')),19); self.assertFalse(self.calls('client')); self.assertEqual(len(self.calls('launcher')),2)
    def test_client_failure_no_sink(self):
        self.configure(client_fail=True); self.run_op('command refused'); self.assertEqual(len(self.calls('client')),1); self.assertFalse(self.calls('sink'))
    def test_sink_failure_no_retry(self):
        self.configure(sink_fail=True); self.run_op('command refused'); self.assertEqual(len(self.calls('sink')),1)
    def test_existing_work(self):
        self.operation.work.mkdir(); self.run_op('work-dir already'); self.assertEqual(self.calls(),[])
    def test_unsafe_work_path(self):
        self.operation.work=self.work_root/'unsafe path'; self.run_op('paths must'); self.assertEqual(self.calls(),[])
    def test_invalid_launcher_argument_before_any_command(self):
        self.operation.args[6]='bad'; self.run_op('invalid launcher argument'); self.assertEqual(self.calls(),[])
    def test_receipt_overwrite(self):
        p=self.paths.receipts/'old.json'; p.write_text('keep'); self.operation.args[-1]=str(p)
        self.run_op('fresh path'); self.assertEqual(p.read_text(),'keep')
    def test_symlink_archive(self):
        out=self.results/'output'; out.mkdir(); (out/'stream135-link').symlink_to(self.root/'config'); self.run_op('symlink'); self.no_launch()
    def test_archive_destination_collision(self):
        out=self.results/'output'; out.mkdir(); (out/'stream135-a').write_text('source')
        dest=out/f'archive-stream135-{self.operation.tag}'/'output/stream135-a'; dest.parent.mkdir(parents=True); dest.write_text('keep')
        self.run_op('destination exists'); self.no_launch(); self.assertEqual(dest.read_text(),'keep')
    def test_concurrent_lock(self):
        with (self.paths.receipts/'stream-ops.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB); self.run_op('holds the lock')
        self.assertEqual(self.calls(),[])
    def test_dry_run_no_commands_writes_sleep(self):
        self.operation.dry=True; before=sorted(str(p) for p in self.root.rglob('*')); stdout=io.StringIO()
        with contextlib.redirect_stdout(stdout): self.operation.run()
        self.assertEqual(before,sorted(str(p) for p in self.root.rglob('*'))); self.assertEqual(self.calls(),[]); self.assertEqual(self.clock.sleeps,[])
        for text in ('stop','mv','check-four-card-health.py','--check-only','stop + 305','curl','start-client-135.sh','start-sink-117.sh'): self.assertIn(text,stdout.getvalue())
    def test_production_arm_same_chain_clears_ambient_ltx(self):
        path=self.root/'production.json'; path.write_text(json.dumps({'packet_id':'135','work_dir':str(self.operation.work),'launcher_args':ARGS,'env':ARM}))
        arm,env=ops.production(path,dict(self.env,LTX_UNEXPECTED='bad')); self.assertNotIn('LTX_UNEXPECTED',env)
        self.operation=ops.Operation(arm['packet_id'],arm['work_dir'],arm['launcher_args'],env,paths=self.paths,clock=self.clock)
        self.run_op(); self.assertEqual(len(self.calls('launcher')),2)
    def test_production_no_non_ltx_injection(self):
        path=self.root/'production.json'; path.write_text(json.dumps({'packet_id':'135','work_dir':str(self.operation.work),'launcher_args':ARGS,'env':{'PATH':'bad'}}))
        with self.assertRaisesRegex(ops.Refusal,'LTX_'): ops.production(path,self.env)
    def test_production_invalid_args(self):
        path=self.root/'production.json'; path.write_text(json.dumps({'packet_id':'135','work_dir':str(self.operation.work),'launcher_args':'echo bad','env':{}}))
        with self.assertRaisesRegex(ops.Refusal,'13 strings'): ops.production(path,self.env)
    def test_swap_cli_dispatch_uses_mock_chain(self):
        original=ops.Operation
        def factory(packet,work,args,env,dry):
            return original(packet,work,args,env,dry,paths=self.paths,clock=self.clock)
        with patch.object(ops,'Operation',side_effect=factory),patch.dict(os.environ,self.env,clear=True),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ops.main(['swap','135',str(self.work_root/'fresh'),'--',*ARGS]),0)
        self.assertEqual(len(self.calls('launcher')),2)
    def test_resume_cli_dispatch_uses_mock_chain(self):
        path=self.root/'production.json'; path.write_text(json.dumps({'packet_id':'135','work_dir':str(self.operation.work),'launcher_args':ARGS,'env':ARM}))
        original=ops.Operation
        def factory(packet,work,args,env,dry):
            return original(packet,work,args,env,dry,paths=self.paths,clock=self.clock)
        with patch.object(ops,'Operation',side_effect=factory),patch.dict(os.environ,self.env,clear=True),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ops.main(['resume',str(path)]),0)
        self.assertEqual(len(self.calls('launcher')),2)
    def test_wrappers_syntax_and_help_only(self):
        for name in ('swap-to-packet.sh','resume-production.sh'):
            path=Path(__file__).with_name(name); subprocess.run(['bash','-n',str(path)],check=True)
            result=subprocess.run(['bash',str(path),'--help'],check=True,text=True,capture_output=True); self.assertIn('--dry-run',result.stdout)
    def test_target_name_current_arm(self):
        self.assertEqual(ops.run_name('135',ARGS,ARM),'encoder-server-continuation-stream-135-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-gc60-ssbackground-sdc1-mi-cmtext-shift-textsplit36')
    def test_invalid_env_cannot_escape_archive_root(self):
        self.operation.env['LTX_CONE_GRAPH_MEMORY']='../../other'
        self.run_op('invalid LTX_CONE_GRAPH_MEMORY'); self.assertEqual(self.calls(),[])
    def test_unsupported_nondefault_option_refuses(self):
        self.operation.env['LTX_DISPLAY_WORKER']='parallel'
        self.run_op('does not support'); self.assertEqual(self.calls(),[])
    def test_stale_inactive_unit_does_not_block_live_pair(self):
        self.configure(units='ltx129-stream-server-20261010.service loaded failed failed\nltx133b-stream-client-20261010.service loaded active running\nltx133b-stream-server-20261010.service loaded active running')
        self.run_op()
        self.assertFalse([c for c in self.calls('systemctl') if 'stop' in c['args'] and 'ltx129' in c['args'][-1]])
    def test_sink_live_old_halted_packet_is_archived(self):
        self.configure(units='ltx133b-stream-server-20261010.service loaded failed failed\nltx133b-stream-client-20261010.service loaded inactive dead\nltx117-stream-sink.service loaded active running')
        output=self.results/'output'; output.mkdir(); old=output/'stream133b-old'; old.write_text('keep')
        self.run_op(); self.assertFalse(old.exists())
        self.assertEqual(len(json.loads(self.operation.receipt.read_text())['moves']),1)
    def test_wrong_status_identity_refuses(self):
        self.configure(status={'phase':'stream_setup','halted':None,'fault':False,'packet':129,'receipt_dir':'/wrong/receipts'})
        self.run_op('identity mismatch'); self.assertFalse(self.calls('client'))
    def test_production_generates_fresh_workdirs(self):
        path=self.root/'production.json'; path.write_text(json.dumps({'packet_id':'135','launcher_args':ARGS,'env':ARM}))
        a,_=ops.production(path,self.env); b,_=ops.production(path,self.env)
        self.assertNotEqual(a['work_dir'],b['work_dir'])
        self.assertEqual(Path(a['work_dir']).parent,ops.Paths().work_root)
    def test_packet134_chunk_arm_suffix(self):
        self.assertTrue(ops.run_name('134',ARGS,dict(ARM,LTX_CHUNK_ARM='split36-169')).endswith('-textsplit36-armsplit36-169'))

for latch in ['decoder-graph-116-refused.json','anchor-decode-117-refused.json','anchor-decode-118-refused.json','precompute-117-refused.json','precompute-118-refused.json','snapshot-118-refused.json','display-replica-120-refused.json']:
    def test(self,name=latch):
        if name.startswith('display'): self.operation.args[11]='xpu:2'
        (self.results/name).write_text('{}'); self.run_op(name); self.assertEqual(self.calls(),[])
    setattr(OperationsTests,'test_latch_'+latch.replace('-','_').replace('.','_'),test)

if __name__=='__main__': unittest.main()
