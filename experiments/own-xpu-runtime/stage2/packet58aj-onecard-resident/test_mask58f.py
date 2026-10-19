"""CPU mask/FD and prelaunch/report failure regressions; temporary coordination only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import chain_devices as D
import onecard_admission as A
import window as W
import test_admission58e as fixtures

class MaskTests(unittest.TestCase):
    def topology(self, root):
        dri=root/'dev/dri'; by=dri/'by-path'; by.mkdir(parents=True)
        sys=root/'sys'; driver=root/'drivers/xe'; driver.mkdir(parents=True)
        for i,bdf in enumerate(D.LANES['A']+D.LANES['B']):
            node=dri/('renderD'+str(128+i));node.touch()
            (by/('pci-'+bdf+'-render')).symlink_to(node)
            device=root/'pci'/bdf;device.mkdir(parents=True)
            (device/'driver').symlink_to(driver)
            entry=sys/node.name;entry.mkdir(parents=True);(entry/'device').symlink_to(device)
        return dict(by_path=by,sys_drm=sys,dev_dri=dri,cwd=root)

    def test_real_child_env_while_A_and_B_leased(self):
        import lane_admission as L
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); kw=self.topology(root)
            proof=D.onecard_topology(**kw)
            self.assertEqual(proof['native_indices'],[0])
            self.assertEqual([r['pci'] for r in proof['nodes']],['0000:23:00.0'])
            with L.Reservation('B',root=root/'lanes') as b:
                b.complete(drained=True)  # 58j waits for whole-host gap even at K1
                with L.Reservation('A',window='K1',root=root/'lanes') as a:
                    env=D.onecard_environment(W.closed_environment({'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2', 'LD_LIBRARY_PATH':json.loads((W.HERE/'library-path.json').read_text())['LD_LIBRARY_PATH']}),root/'home')
                    code='import os,json; print(json.dumps(dict(os.environ)))'
                    child=subprocess.run(['/usr/bin/python3','-B','-c',code],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
                    actual=json.loads(child.stdout)
                    for k,v in D.onecard_mask().items():self.assertEqual(actual[k],v)
                    self.assertEqual(actual['HOME'],str(root/'home'))
                    self.assertEqual(actual['ZE_AFFINITY_MASK'],'0')
                    self.assertEqual(actual['ONEAPI_DEVICE_SELECTOR'],'level_zero:0')
                    self.assertEqual(actual['FilterBdfPath'],'0000:23:00.0')
                    self.assertNotIn('LD_PRELOAD',actual)
                    self.assertEqual(list((root/'home').iterdir()),[])
                    D.verify_onecard_environment(env)
                    for key in D.onecard_mask():
                        bad=dict(env);bad.pop(key)
                        with self.assertRaisesRegex(ValueError,'pre-open mask differs'):
                            D.verify_onecard_environment(bad)
                    a.complete(drained=True)

    def test_mapping_and_debug_override_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);kw=self.topology(root)
            (root/'igdrcl.config').write_text('FilterBdfPath=0000:2')
            with self.assertRaisesRegex(ValueError,'debug configuration'):D.onecard_topology(**kw)
            (root/'igdrcl.config').unlink()
            link=kw['by_path']/'pci-0000:23:00.0-render';link.unlink()
            link.symlink_to(kw['dev_dri']/'renderD129')
            with self.assertRaisesRegex(ValueError,'mapping differs'):D.onecard_topology(**kw)
        for key in ('FilterBdfPath','ZE_AFFINITY_MASK','ONEAPI_DEVICE_SELECTOR','LD_PRELOAD'):
            with self.assertRaisesRegex(ValueError,'closed/unmasked'):
                D.onecard_environment({key:'bad'},Path('/never-create-58f'))

    def test_all_foreign_render_fds_refused_and_retained(self):
        for bdf in ('0000:27:00.0','0000:43:00.0','0000:47:00.0',''):
            with self.subTest(bdf=bdf), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);proc=root/'proc';proc.mkdir();drain=root/'drain';drain.mkdir()
                with A.Admission('K1',root/'out',lambda:None,root=root/'lanes',drain_root=drain,proc=proc) as a:
                    a.before_launch()
                    fixtures.AdmissionTests().proc_owner(proc,42,bdf)
                    with self.assertRaisesRegex(ValueError,'another card'):a.observe({'processes':[{'pid':42}]})
                    self.assertEqual(a.owners['42']['fds'][0]['pci'],bdf)
                self.assertFalse(json.loads((drain/'teardown-state.json').read_text())['drained'])

    def test_prelaunch_failure_never_takes_shared_drain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);proc=root/'proc';proc.mkdir();drain=root/'drain';drain.mkdir()
            prior=drain/'teardown-state.json';prior.write_text('{"preserved":true}')
            with self.assertRaisesRegex(ValueError,'memory refused'):
                with A.Admission('K1',root/'out',lambda:None,root=root/'lanes',drain_root=drain,proc=proc) as a:
                    raise ValueError('memory refused')
            self.assertEqual(prior.read_text(),'{"preserved":true}')
            self.assertFalse((root/'lanes/active-lane-A.json').exists())
            self.assertFalse(a.record['passed'])

    def test_failure_after_permit_before_spawn_cleans_own_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);proc=root/'proc';proc.mkdir();drain=root/'drain';drain.mkdir()
            a=A.Admission('K1',root/'out',lambda:None,root=root/'lanes',drain_root=drain,proc=proc)
            with self.assertRaisesRegex(ValueError,'pre-spawn'):
                with a:
                    with patch.object(D,'admit_clients',side_effect=[{},ValueError('pre-spawn')]):a.before_launch()
            self.assertTrue(json.loads((drain/'teardown-state.json').read_text())['drained'])
            self.assertFalse((root/'lanes/active-lane-A.json').exists())

    def test_memory_recheck_after_drain_wait_cleans_unspawned_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);proc=root/'proc';proc.mkdir();drain=root/'drain';drain.mkdir()
            with self.assertRaisesRegex(ValueError,'memory changed while waiting'):
                with A.Admission('K1',root/'out',lambda:None,root=root/'lanes',drain_root=drain,proc=proc) as a:
                    def recheck():
                        self.assertFalse(json.loads((drain/'teardown-state.json').read_text())['drained'])
                        raise ValueError('memory changed while waiting')
                    a.before_launch(recheck)
            self.assertTrue(json.loads((drain/'teardown-state.json').read_text())['drained'])
            self.assertFalse(a.launch_attempted)
            self.assertFalse((root/'lanes/active-lane-A.json').exists())

    def test_report_failure_after_exit_drains_but_does_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);proc=root/'proc';proc.mkdir();drain=root/'drain';drain.mkdir()
            a=A.Admission('K1',root/'out',lambda:None,root=root/'lanes',drain_root=drain,proc=proc)
            with self.assertRaisesRegex(ValueError,'CPU report'):
                with a:
                    a.before_launch();owner=fixtures.AdmissionTests().proc_owner(proc,42,'0000:23:00.0')
                    a.observe({'processes':[{'pid':42}]})
                    with self.assertRaisesRegex(ValueError,'remains after drain'):a.devices_drained()
                    shutil.rmtree(owner)
                    from unittest.mock import Mock
                    child=Mock();child.poll.return_value=0
                    with self.assertRaisesRegex(ValueError,'postflight failed'):
                        W.finish_k1_devices(child,['postflight GPU fault signature'],a)
                    self.assertFalse(a.drained)
                    child.poll.return_value=None
                    with self.assertRaisesRegex(ValueError,'postflight failed'):
                        W.finish_k1_devices(child,[],a)
                    child.poll.return_value=0
                    W.finish_k1_devices(child,[],a);a.devices_drained()
                    with self.assertRaisesRegex(ValueError,'already attempted or drained'):a.before_launch()
                    raise ValueError('CPU report')
            self.assertTrue(json.loads((drain/'teardown-state.json').read_text())['drained'])
            self.assertFalse((root/'lanes/active-lane-A.json').exists())
            self.assertFalse(a.record['passed'])

class FullWindowTests(unittest.TestCase):
    def run_window(self, failure):
        from contextlib import ExitStack
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);packet=root/'packet';packet.mkdir()
            (packet/'build-receipt.json').write_text('{}')
            (packet/'build').mkdir();(packet/'evidence').mkdir()
            proc=root/'proc';proc.mkdir();drain=root/'drain';drain.mkdir()
            output=packet/'evidence/K1a';admission_type=A.Admission
            is_refusal=failure in ('refusal','refusal-fault','refusal-live')
            previous=root/'previous.json';previous.write_text('{}')
            child=Mock();child.pid=42;child.returncode=1 if is_refusal else 0;child.poll.return_value=child.returncode
            captured={}
            def make_admission(window, output, check):
                a=admission_type(window,output,check,root=root/'lanes',drain_root=drain,proc=proc)
                captured['admission']=a;return a
            def spawn(command, **kwargs):
                captured['environment']=kwargs['env']
                self.assertTrue((root/'lanes/active-lane-A.json').exists())
                self.assertFalse(json.loads((drain/'teardown-state.json').read_text())['drained'])
                owner=fixtures.AdmissionTests().proc_owner(proc,42,'0000:23:00.0')
                captured['admission'].observe({'processes':[{'pid':42}]})
                if failure!='refusal-live':shutil.rmtree(owner)
                if is_refusal:
                    from test_refusal58g import proof
                    (output/'run/run').mkdir(parents=True)
                    (output/'run/run/receipt.json').write_text(json.dumps(proof()))
                (output/'run').mkdir(exist_ok=True);(output/'run/k1.json').write_text('{}')
                (output/'run/k1-cases.jsonl').write_text('{}')
                return child
            def supervise(*args,**kwargs):
                if failure in ('postflight','refusal-fault'): args[4].append('postflight GPU fault signature')
                return dict(child_still_running=False,returncode=0)
            closed=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu')
            with ExitStack() as stack:
                mocks=[(W,'HERE',packet),(W,'user_unit_gate',lambda c:None),
                    (W,'closed_environment',lambda:closed),(W,'build_gate',lambda:dict(artifacts={})),
                    (W,'memory_fence',lambda:{}),(W,'selected_clients',lambda c:{}),
                    (W,'prerequisite',lambda *a:{}),(W,'selected_miss_path',lambda *a:'zero-copy'),
                    (W,'storage',lambda *a:{}),(W.SUPPORT,'process_start',lambda pid:123),
                    (W.S,'journal',lambda *a,**k:('',None)),(W.S,'supervise',supervise),
                    (W.M,'meminfo',lambda:{'MemAvailable':200*1024**3,'GPUActive':0}),
                    (A,'Admission',make_admission),(D,'onecard_topology',lambda:{}),
                    (W.subprocess,'Popen',spawn)]
                for obj,key,value in mocks:stack.enter_context(patch.object(obj,key,value))
                stack.enter_context(patch.object(W.S,'ldd_preflight',side_effect=ValueError('preflight refusal') if failure=='preflight' else None,return_value={}))
                stack.enter_context(patch.object(W,'k1_summary',side_effect=ValueError('CPU report failed') if failure=='report' else None,return_value={}))
                rc=W.main(['--window','KD' if is_refusal else 'K1','--previous',str(previous),'--card','0','--output',str(output),
                    '--faults-reviewed-through','2026-01-01T00:00:00Z','--authorized-device-window'])
            row=json.loads((output/'window.json').read_text())
            self.assertEqual(rc,0 if failure is None else 1)
            self.assertEqual(row['passed'],failure is None)
            self.assertEqual(row['qualifying'],False)
            if failure=='preflight':
                self.assertNotIn('environment',captured)
                self.assertFalse((drain/'teardown-state.json').exists())
            else:
                for key,value in D.onecard_mask().items():self.assertEqual(captured['environment'][key],value)
                self.assertEqual(captured['environment']['HOME'],str(output/'native-home'))
                self.assertEqual(row['native_environment'],captured['environment'])
                self.assertNotIn('HOME',row['environment'])
                self.assertEqual(json.loads((drain/'teardown-state.json').read_text())['drained'],failure not in ('postflight','refusal-fault','refusal-live'))
            self.assertEqual((root/'lanes/active-lane-A.json').exists(),failure in ('postflight','refusal-fault','refusal-live'))

    def test_actual_window_preflight_failure(self):self.run_window('preflight')
    def test_actual_window_report_failure(self):self.run_window('report')
    def test_actual_window_postflight_failure_retains_drain(self):self.run_window('postflight')
    def test_actual_window_success(self):self.run_window(None)
    def test_actual_window_refusal_releases(self):self.run_window('refusal')
    def test_actual_window_refusal_fault_retains(self):self.run_window('refusal-fault')
    def test_actual_window_refusal_live_owner_retains(self):self.run_window('refusal-live')

if __name__=='__main__':unittest.main()
