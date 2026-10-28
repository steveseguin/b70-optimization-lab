"""CPU-only controller tests; no subprocess launch, device open or observer call."""
import hashlib
import json
import os
import threading
import time
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock
import pipeline_driver as driver


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binary = self.root / 'fake-engine'
        self.binary.write_bytes(b'CPU test fixture; not executable')
        receipt = self.root / 'receipt.json'
        receipt.write_text(json.dumps(dict(schema='ownrt.engine.build.v1', binary=str(self.binary), binary_sha256=driver.digest(self.binary), sources={'pipeline/layout.hpp':driver.digest(driver.HERE.parent/'src/pipeline/layout.hpp')})))
        placement = driver.ROOT / 'experiments/own-xpu-runtime/gsq-rco-iq3s/loader/placement.tsv'
        identity = self.root / 'auth.tsv'
        identity.write_text('test authority')
        argv = [str(self.binary), '--gsq-packed', '--rank', '0', '--draft-mtp', '--draft-fault', 'none', '--plan', str(placement), '--identity', str(identity), '--memory', 'resident', '--authorized-device-window', '--activations', 'f32', '--prefill-rows', '32', '--prefill-shared', '/not-used', '--draft-rank', '0', '--target-split', '23']
        adapter = self.root / 'adapter.json'
        adapter.write_text(json.dumps(dict(schema='ownrt.gsq.rank-adapter-plan.v1', binary=str(self.binary), rank_argv=[argv, argv], environment=[{'OMP_NUM_THREADS':'2'}, {'OMP_NUM_THREADS':'2'}])))
        self.config = dict(schema='ownrt.pipeline-driver-config.v1', adapter_plan=str(adapter), build_receipt=str(receipt), boundaries=[0,13,25,37,48], bdfs=['0000:23:00.0','0000:27:00.0','0000:43:00.0','0000:47:00.0'], output=str(self.root/'run'), prompt_tokens=[1,2,3], context=64, max_new=4, vocab=248320, eos=248044, seconds=1800, grace_seconds=60, memory_start_bytes=100*1024**3, memory_floor_bytes=8*1024**3, root_floor_bytes=27000000000, evidence_floor_bytes=2*1024**3)
        self.path = self.root / 'config.json'

    def plan(self):
        self.path.write_text(json.dumps(self.config))
        return driver.make_plan(self.path)

    def test_quad_plan_is_target_only_and_hash_bound(self):
        plan = self.plan()
        self.assertFalse((self.root/'run').exists())
        self.assertFalse(plan['device_execution_requested'])
        self.assertEqual(len(plan['stages']), 4)
        for i, stage in enumerate(plan['stages']):
            argv = stage['argv']
            self.assertEqual(driver.option(argv,'--output'),str(self.root/f'run/stage{i}/native'))
            self.assertEqual(stage['native_output'],driver.option(argv,'--output'))
            self.assertNotIn('--draft-mtp', argv)
            self.assertNotIn('--prefill-rows', argv)
            self.assertEqual(driver.option(argv,'--rank'), '0' if i == 0 else '1')
            self.assertEqual(driver.option(argv,'--pipeline-stage'),str(i))
            self.assertEqual(stage['environment']['FilterBdfPath'], self.config['bdfs'][i])
            self.assertLess(stage['packed_weight_bytes'], 31000000000)
        self.assertEqual(plan['pins'][str(self.binary)], driver.digest(self.binary))
        self.binary.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'binary differs'):
            self.plan()

    def test_admitted_topologies_and_no_fit_claim(self):
        for cuts in ([0,23,48],[0,8,16,24,32,40,48]):
            self.config['boundaries'] = cuts
            self.config['bdfs'] = [f'0000:{i:02x}:00.0' for i in range(len(cuts)-1)]
            self.assertEqual(len(self.plan()['stages']),len(cuts)-1)
        self.config['boundaries']=[0,48]
        self.config['bdfs']=['0000:23:00.0']
        with self.assertRaisesRegex(ValueError,'31 GB'):
            self.plan()

    def test_invalid_identity_or_extent_fails_closed(self):
        for key, value in [('boundaries',[0,13,13,37,48]),('bdfs',['x']*4),('boundaries',[0,13,25,37,47]),('context',2),('prompt_tokens',[248320]),('memory_floor_bytes',1)]:
            with self.subTest(key=key):
                old=self.config[key];self.config[key]=value
                with self.assertRaises(ValueError):self.plan()
                self.config[key]=old
        self.config['boundaries']=[0,1,25,37,48]
        with self.assertRaisesRegex(ValueError,'PLE'):
            self.plan()

    def test_preserves_numerical_flags_and_rejects_duplicate_option(self):
        result=driver.replace_options(['engine','--activations','bf16','--recurrent-f32'],{'--activations':'f32'})
        self.assertEqual(result,['engine','--activations','f32','--recurrent-f32'])
        with self.assertRaisesRegex(ValueError,'duplicate'):
            driver.replace_options(['--rank','0','--rank','1'],{'--rank':0})


class WireTests(unittest.TestCase):
    def setUp(self):
        self.a,self.b=socket.socketpair()
        self.addCleanup(self.a.close);self.addCleanup(self.b.close)
        self.a.settimeout(.1)
        self.stage=driver.Stage.__new__(driver.Stage)
        self.stage.sock=self.a;self.stage.guard=mock.Mock();self.stage.sequence=0
        self.stage.spec=dict(id=2,first=False,final=False)
        self.stage.plan=dict(seconds=1)

    def send(self,**changes):
        row=dict(status=0,token=0,error=0,bytes=40960,sequence=0,rank=1,stage=2,final=0)
        row.update(changes)
        self.b.sendall(driver.REPLY.pack(*row.values(),0,0,0,0))

    def test_ready_identity_and_f32_extent(self):
        self.send();self.stage.receive(ready=True)
        self.assertEqual(self.stage.stream_bytes,40960)

    def test_stale_head_stage_sequence_and_extent_rejected(self):
        for change in [dict(stage=1),dict(final=1),dict(sequence=4),dict(bytes=65540),dict(bytes=3),dict(error=1)]:
            with self.subTest(change=change):
                self.send(**change)
                with self.assertRaises(ValueError):self.stage.receive(ready=True)

    def test_finish_sends_explicit_stage_identity(self):
        self.stage.command(5)
        self.assertEqual(driver.REQUEST.unpack(self.b.recv(32)),(5,0,0,0,0,1,2,0))

    def test_coordinator_failure_prevents_any_command(self):
        self.stage.guard.check.side_effect=RuntimeError('coordinator stop')
        with self.assertRaisesRegex(RuntimeError,'coordinator stop'):
            self.stage.command(1)
        self.assertEqual(self.stage.sequence,0)


class LaunchOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.guard=driver.Guard.__new__(driver.Guard)
        self.guard.lock=threading.Lock();self.guard.failed=None;self.guard.signal_stop=threading.Event()
        self.guard.deadline=time.monotonic()+60;self.guard.stop_fd=None
        self.guard.stoppers=[];self.guard.tracked_processes=[];self.guard.identities={};self.guard.obs=mock.Mock()
        self.guard.obs.process_identity.return_value=None
        self.stage=driver.Stage.__new__(driver.Stage)
        native=str(Path(self.temp.name)/'stage0/native')
        self.spec=dict(id=0,first=True,final=False,bdf='0000:23:00.0',native_output=native,argv=['fake-engine','--output',native],environment={})
        self.addCleanup(self.cleanup_resources)

    def cleanup_resources(self):
        for name in ('shared','file','prefill','prefill_file','sock','log'):
            resource=getattr(self.stage,name,None)
            if resource is not None:resource.close()
        for fd in self.guard.stoppers:os.close(fd)

    def test_stop_between_outer_check_and_constructor_prevents_launch(self):
        self.guard.failed='observer fault just arrived'
        with mock.patch.object(driver.subprocess,'Popen') as popen:
            with self.assertRaisesRegex(ValueError,'cancelled before Popen'):
                self.stage.__init__(self.spec,dict(output=self.temp.name),self.guard)
            popen.assert_not_called()
        self.assertEqual(self.guard.tracked_processes,[])

    def test_native_output_is_absent_at_launch_while_ipc_parent_exists(self):
        proc=mock.Mock(pid=1234)
        self.guard.obs.process_identity.return_value={'start_ticks':100}
        def native_predevice_contract(argv, **kwargs):
            output=Path(driver.option(argv,'--output'))
            self.assertFalse(output.exists(), 'native main requires !fs::exists(a.output)')
            self.assertTrue(output.parent.is_dir())
            self.assertTrue((output.parent/'shared.bin').is_file())
            return proc
        with mock.patch.object(driver.subprocess,'Popen',side_effect=native_predevice_contract):
            self.stage.__init__(self.spec,dict(output=self.temp.name),self.guard)

    def test_native_prefill_map_exists_with_versioned_header_before_launch(self):
        self.spec['argv'] += ['--prefill-rows','2','--prefill-shared',str(Path(self.temp.name)/'stage0/prefill.bin')]
        proc=mock.Mock(pid=1234)
        self.guard.obs.process_identity.return_value={'start_ticks':100}
        plan=dict(output=self.temp.name,prefill_rows=2,prefill_stream_bytes=driver.PREFILL_STREAM_BYTES)
        with mock.patch.object(driver.subprocess,'Popen',return_value=proc) as popen:
            self.stage.__init__(self.spec,plan,self.guard)
        popen.assert_called_once()
        path=Path(self.temp.name)/'stage0/prefill.bin'
        self.assertEqual(path.stat().st_size,driver.PREFILL_HEADER+8*driver.PREFILL_STREAM_BYTES)
        self.assertEqual(self.stage.prefill[:16],driver.struct.pack('<4I',driver.PREFILL_MAGIC,1,2,driver.PREFILL_STREAM_BYTES))
        self.assertEqual(self.stage.prefill_rows,2)
        self.assertEqual(self.guard.tracked_processes,[(0,proc)])

    def test_old_shared_native_directory_refused_before_launch(self):
        self.spec['native_output']=str(Path(self.temp.name)/'stage0')
        self.spec['argv']=['fake-engine','--output',self.spec['native_output']]
        with mock.patch.object(driver.subprocess,'Popen') as popen:
            with self.assertRaisesRegex(ValueError,'native output path identity'):
                self.stage.__init__(self.spec,dict(output=self.temp.name),self.guard)
            popen.assert_not_called()

    def test_identity_failure_retains_child_for_cooperative_shutdown(self):
        proc=mock.Mock(pid=1234)
        with mock.patch.object(driver.subprocess,'Popen',return_value=proc):
            with self.assertRaisesRegex(ValueError,'PID identity absent'):
                self.stage.__init__(self.spec,dict(output=self.temp.name),self.guard)
        self.assertEqual(self.guard.tracked_processes,[(0,proc)])
        self.assertEqual(len(self.guard.stoppers),1)


class GuardTests(unittest.TestCase):
    def test_stop_is_one_cooperative_write_even_with_repeated_faults(self):
        read, write = os.pipe()
        self.addCleanup(os.close, read);self.addCleanup(os.close, write)
        os.set_blocking(read, False)
        guard = driver.Guard.__new__(driver.Guard)
        guard.lock=threading.Lock();guard.failed=None;guard.stoppers=[write]
        guard.fail('first GPU fault');guard.fail('later fault')
        self.assertEqual(guard.failed,'first GPU fault')
        self.assertEqual(os.read(read,10),b'!')
        with self.assertRaises(BlockingIOError):os.read(read,10)

    def test_signal_or_lifetime_prevents_work_without_external_fd(self):
        guard = driver.Guard.__new__(driver.Guard)
        guard.lock=threading.Lock();guard.failed=None;guard.stoppers=[]
        guard.signal_stop=threading.Event();guard.stop_fd=None
        guard.deadline=time.monotonic()+60
        guard.signal_stop.set()
        with self.assertRaisesRegex(RuntimeError,'signal stop'):guard.check()
        guard.failed=None;guard.signal_stop.clear();guard.deadline=0
        with self.assertRaisesRegex(RuntimeError,'lifetime'):guard.check()

    def test_unit_policy_binds_pid_invocation_and_no_restart(self):
        fields=f'MainPID={os.getpid()}\nInvocationID=abc\nRestart=no\nKillMode=process\nSendSIGKILL=no\n'
        with mock.patch.dict(os.environ,{'INVOCATION_ID':'abc'}), mock.patch.object(driver.subprocess,'run') as run:
            run.return_value=mock.Mock(returncode=0,stderr='',stdout=fields)
            self.assertEqual(driver.validate_unit('test.service')['Restart'],'no')
            run.return_value.stdout=fields.replace('Restart=no','Restart=always')
            with self.assertRaisesRegex(ValueError,'forbid restart'):driver.validate_unit('test.service')
            run.return_value.stdout=fields.replace('InvocationID=abc','InvocationID=other')
            with self.assertRaisesRegex(ValueError,'ownership'):driver.validate_unit('test.service')


if __name__=='__main__':unittest.main()
