"""CPU-only controller tests; helper subprocess only, no engine launch or device open."""
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
import controller as driver
import observer
import copy
import test_launch_plan as fixture
from datetime import datetime, timedelta, timezone


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
        for name in ('shared','file','sock','log'):
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



class PortableIdentityTests(unittest.TestCase):
    setUp=fixture.LaunchPlanTests.setUp
    pin=fixture.LaunchPlanTests.pin
    run_prepare=fixture.LaunchPlanTests.run_prepare
    generate=fixture.LaunchPlanTests.generate
    external_policy=fixture.LaunchPlanTests.external_policy
    def verify(self,plan):
        path=self.root/'plan.json';path.write_text(json.dumps(plan))
        return driver.verify_plan(path,driver.digest(path),self.sha,self.binding_sha,self.receipt_path,driver.digest(self.receipt_path))
    def test_regenerated_plan_accepts_and_modified_command_refuses(self):
        plan=self.generate()
        self.assertEqual(self.verify(plan),plan)
        plan['stages'][0]['environment']['LD_PRELOAD']='evil'
        with self.assertRaisesRegex(ValueError,'differ from trusted'):self.verify(plan)
    def test_mtp_wrong_receipt_and_changed_source_refuse(self):
        with self.assertRaisesRegex(ValueError,'target-only'):self.verify(self.generate('mtp'))
        plan=self.generate();plan['pins'][str(self.receipt_path)]='0'*64
        with self.assertRaisesRegex(ValueError,'receipt digest'):self.verify(plan)
    def test_selected_policy_survives_reconstruction_and_changed_policy_refuses(self):
        selected=self.external_policy(boundaries={'2':[0,24,48],'4':[0,12,24,36,48]})
        plan=self.generate(**selected)
        self.assertEqual(self.verify(plan),plan)
        selected['policy_path'].write_text('{}')
        with self.assertRaisesRegex(ValueError,'pinned artifact'):self.verify(plan)
    def test_admission_requires_code_and_explicit_authority(self):
        admission=dict(schema='ownrt.portable-run-admission.v1',owner_authorized=True,plan_sha256='test',
            controller_sha256=driver.digest(driver.__file__),observer_sha256=driver.digest(observer.__file__),
            observer_backend='sudo-n',expires_utc=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat(),
            limits=dict(memory_start_bytes=100*1024**3,memory_floor_bytes=8*1024**3,root_floor_bytes=27*10**9,evidence_floor_bytes=2*1024**3,grace_seconds=30))
        self.assertIn('memory_floor_bytes',driver.admit({},admission,'test'))
        for key,value in [('owner_authorized',False),('controller_sha256','0'*64),('observer_backend','fallback'),('plan_sha256','other')]:
            bad=dict(admission,**{key:value})
            with self.assertRaises(ValueError):driver.admit({},bad,'test')

class PhysicalAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.guard=driver.Guard.__new__(driver.Guard)
        self.guard.lock=threading.Lock();self.guard.identities={100:(22,'0000:23:00.0')}
        self.guard.targets={'0000:23:00.0':{'/dev/dri/card0','/dev/dri/renderD128'}}
        self.guard.plan=dict(memory_start_bytes=2,memory_floor_bytes=1,root_floor_bytes=1,evidence_floor_bytes=1,output='/tmp/no-run')
        self.row=dict(schema='ownrt.portable-observation.v1',observer_euid=0,device_opened=False,boot='boot',drm=['mapping'],kernel=dict(faults=[]),inventory=dict(errors=[],holders=[]),identity_races=[],memory=dict(MemAvailable=3),root_free_bytes=2,holders={})
        self.guard.baseline=copy.deepcopy(self.row)
    def test_current_known_holder_only_and_wrong_card_refused(self):
        self.row['inventory']['holders']=[dict(pid=100,node='/dev/dri/card0')]
        self.row['holders']={'100':dict(start_ticks=22)}
        self.guard.validate(self.row)
        with self.assertRaisesRegex(ValueError,'foreign'):self.guard.validate(self.row,initial=True)
        self.row['holders']['100']['start_ticks']=23
        with self.assertRaisesRegex(ValueError,'foreign'):self.guard.validate(self.row)
        self.row['inventory']['holders'][0]['node']='/dev/dri/card9'
        with self.assertRaisesRegex(ValueError,'non-target'):self.guard.validate(self.row)
    def test_fault_incomplete_inventory_or_identity_race_refuses(self):
        for key,value in [('identity_races',[123]),('inventory',dict(errors=['permission'],holders=[])),('kernel',dict(faults=['new fault'])),('boot','other')]:
            bad=copy.deepcopy(self.row);bad[key]=value
            with self.assertRaises(ValueError):self.guard.validate(bad)

class ObserverTests(unittest.TestCase):
    def test_nonroot_cannot_claim_complete_empty_inventory(self):
        with mock.patch.object(observer.os,'geteuid',return_value=1000):
            with self.assertRaisesRegex(ValueError,'requires root'):observer.observe()
    def test_sudo_backend_fixed_noninteractive_no_fallback(self):
        with mock.patch.object(observer,'bounded_command',side_effect=ValueError('refused')) as call:
            with self.assertRaisesRegex(ValueError,'refused'):observer.Backend('sudo-n').observe()
            self.assertEqual(call.call_args.args[0][:4],['/usr/bin/sudo','-n','--','/usr/bin/python3'])
    def test_target_requires_card_render_driver_and_vendor(self):
        rows=[dict(node='/dev/dri/card0',bdf='b',driver='xe',vendor='0x8086'),dict(node='/dev/dri/renderD128',bdf='b',driver='xe',vendor='0x8086')]
        self.assertEqual(len(observer.target_nodes(dict(drm=rows),'b')),2)
        rows[1]['vendor']='0xffff'
        with self.assertRaises(ValueError):observer.target_nodes(dict(drm=rows),'b')
    def test_journal_error_empty_boot_and_fault_identity(self):
        boot='12345678-1234-1234-1234-123456789abc'
        row={'_BOOT_ID':boot.replace('-',''),'MESSAGE':'engine reset fault','__CURSOR':'c','__MONOTONIC_TIMESTAMP':'10'}
        with mock.patch.object(observer,'bounded_command',return_value=json.dumps(row).encode()) as command:
            self.assertEqual(len(observer.kernel_faults(boot)['faults']),1)
            self.assertEqual(command.call_args.args[0],['/usr/bin/journalctl','-k','-b','--no-pager','-o','json'])
        for raw in (b'',b'notjson',json.dumps(dict(row,_BOOT_ID='other')).encode()):
            with mock.patch.object(observer,'bounded_command',return_value=raw):
                with self.assertRaises(ValueError):observer.kernel_faults(boot)


class BoundedObserverTests(unittest.TestCase):
    def test_helper_refusal_retains_bounded_error(self):
        with self.assertRaisesRegex(ValueError,'passive helper exit 2:.*fixture diagnostic') as raised:
            observer.bounded_command(['/usr/bin/python3','-c','import sys;sys.stderr.write("x"*3000+"fixture diagnostic");sys.exit(2)'])
        self.assertLess(len(str(raised.exception)),2200)

    def test_process_and_fd_census_caps_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc=Path(tmp)
            for pid in (100,101):
                p=proc/str(pid);p.mkdir();(p/'fd').mkdir()
                fields=['S']+['0']*18+['22']
                (p/'stat').write_text(str(pid)+' (test) '+' '.join(fields))
            with self.assertRaisesRegex(ValueError,'process inventory count'):
                observer.holder_inventory([],proc,max_processes=1)
            (proc/'100/fd/1').write_text('ordinary file')
            with self.assertRaisesRegex(ValueError,'FD inventory'):
                observer.holder_inventory([],proc,max_fds=0)
            with self.assertRaisesRegex(ValueError,'deadline'):
                observer.holder_inventory([],proc,deadline=0)
            with mock.patch.object(Path,'iterdir',side_effect=AssertionError('eager directory listing refused')):
                inventory,_,_=observer.holder_inventory([],proc)
                self.assertEqual(inventory['processes_scanned'],2)
    def test_wrapper_is_pinned_and_gets_only_packaged_observer_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrapper=Path(tmp)/'wrapper';wrapper.write_text('fixture only; never execute')
            backend=observer.Backend('external-wrapper',str(wrapper),driver.digest(wrapper))
            with mock.patch.object(observer,'bounded_command',return_value=b'{}') as call:
                backend.observe()
                self.assertEqual(call.call_args.args[0],[str(wrapper),str(Path(observer.__file__).resolve())])
            wrapper.write_text('changed')
            with self.assertRaisesRegex(ValueError,'digest mismatch'):backend.observe()

class TargetReplayTests(unittest.TestCase):
    def test_fixture_handoff_second_eos_and_final_dump(self):
        calls=[]
        class Guard:
            def __init__(self,plan,admission,fd):
                self.failed=None;self.baseline={};self.initial_observation={};self.tracked_processes=[]
                self.thread=mock.Mock();self.thread.is_alive.return_value=False
                self.done=threading.Event();self.signal_stop=threading.Event();self.obs=mock.Mock()
                self.obs.observe.return_value={}
            def check(self):pass
            def validate(self,row):pass
            def fail(self,reason):self.failed=str(reason)
        class Stage:
            def __init__(self,spec,plan,guard):
                self.spec=spec;self.stream_bytes=4;self.shared=bytearray(driver.SHARED)
            def receive(self,ready=False):pass
            def command(self,op,token=0,position=0,fixture=0):
                calls.append((self.spec['id'],op,token,position,fixture))
                if op==1:
                    if self.spec['final']:
                        if self.shared[driver.SLOT:driver.SLOT+4]!=bytes([token])*4:raise AssertionError('handoff differs')
                    else:self.shared[:4]=bytes([token])*4
                return (0,99 if self.spec['final'] else -1,0,0 if self.spec['final'] else 4,0,0,0,0,1.,0.,0.,0.)
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'run'
            plan=dict(output=str(output),seconds=60,grace_seconds=10,
                stages=[dict(id=0,first=True,final=False),dict(id=1,first=False,final=True)],
                prompt_tokens=[1,2,3],max_new=5,vocab=100,eos=98,eos_token_ids=[98,99])
            admission=dict(schema='ownrt.portable-run-admission.v1',owner_authorized=True,
                expires_utc=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat())
            with mock.patch.object(driver,'Guard',Guard),mock.patch.object(driver,'Stage',Stage),mock.patch.object(driver.os,'getpriority',return_value=19):
                driver.execute(plan,admission,stop_fd=0)
            result=json.loads((output/'result.json').read_text())
            self.assertEqual(result['output_ids'],[99]);self.assertEqual(result['input_position'],3)
            self.assertEqual([(x[2],x[4]) for x in calls if x[:2]==(0,1)],[(1,0),(2,0),(3,1)])
            self.assertEqual([x[:2] for x in calls[-4:]],[(0,4),(1,4),(0,5),(1,5)])
            self.assertTrue((output/'postflight.json').exists())
            self.assertFalse(result['speed_claim'])

if __name__=='__main__':unittest.main()
