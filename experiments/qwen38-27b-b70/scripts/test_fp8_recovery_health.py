"""CPU-only recovery admission/ownership/fault regression tests; no Docker calls."""
import builtins
import copy
import importlib.util
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

PATH=Path(__file__).with_name('run-fp8-recovery-health.py')
spec=importlib.util.spec_from_file_location('recovery_test',PATH)
controller=importlib.util.module_from_spec(spec);spec.loader.exec_module(controller)


class RecoveryGuards(unittest.TestCase):
    def fixture_admission(self,root):
        old=root/'old';old.mkdir();fault=old/'FAULT.json';fault.write_text('{"historical":true}')
        original=root/'control.json';original.write_text(json.dumps({'image':controller.IMAGE,'env':[
            'ONEAPI_DEVICE_SELECTOR=level_zero:0,1','ZE_AFFINITY_MASK=0,1','CCL_ZE_IPC_EXCHANGE=pidfd',
            'CCL_ATL_TRANSPORT=ofi','CCL_TOPO_P2P_ACCESS=1']}))
        reference=root/'container.json';reference.write_text(json.dumps({'Image':controller.IMAGE,'HostConfig':{
            'NetworkMode':'bridge','IpcMode':'host','CapAdd':['CAP_SYS_PTRACE'],'Privileged':False}}))
        return mock.patch.multiple(controller,OLD_FAULT=fault,ORIGINAL=original,HOST_REFERENCE=reference)

    def test_admission_exact_image_and_old_fault_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.fixture_admission(root):
                _,_,receipt=controller.admission(root/'new/health',180)
                self.assertEqual(receipt['image_id'],controller.IMAGE)
                self.assertEqual(json.loads(controller.OLD_FAULT.read_text()),{'historical':True})
                value=json.loads(controller.ORIGINAL.read_text());value['image']='wrong';controller.ORIGINAL.write_text(json.dumps(value))
                with self.assertRaises(RuntimeError):controller.admission(root/'new/health',180)

    def test_old_campaign_new_fault_and_existing_out_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.fixture_admission(root):
                with self.assertRaises(RuntimeError):controller.admission(root/'old/health',180)
                out=root/'new/health';out.parent.mkdir();(out.parent/'FAULT.json').write_text('{}')
                with self.assertRaises(RuntimeError):controller.admission(out,180)
                (out.parent/'FAULT.json').unlink();out.mkdir()
                with self.assertRaises(RuntimeError):controller.admission(out,180)

    def test_timeout_and_selector_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.fixture_admission(root):
                for timeout in (0,181):
                    with self.assertRaises(RuntimeError):controller.admission(root/'new/health',timeout)
                value=json.loads(controller.ORIGINAL.read_text());value['env'][0]='ONEAPI_DEVICE_SELECTOR=level_zero:0'
                controller.ORIGINAL.write_text(json.dumps(value))
                with self.assertRaises(RuntimeError):controller.admission(root/'new/health',180)

    def test_fault_and_failure_latches_never_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'health';out.mkdir()
            helper=types.SimpleNamespace(now=lambda:'now',FAULT=re.compile('GPU fault'))
            self.assertTrue(controller.latch_fault(helper,'GPU fault observed',out))
            first=(root/'FAULT.json').read_bytes()
            controller.latch_failure(helper,out,'timeout after fault')
            self.assertEqual((root/'FAULT.json').read_bytes(),first)
            self.assertTrue((out/'FAILURE.json').exists())
            self.assertFalse(controller.latch_fault(helper,'normal log',out))

    def test_non_gpu_failure_also_closes_recovery_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'health';out.mkdir()
            controller.latch_failure(types.SimpleNamespace(now=lambda:'now'),out,'deadline exceeded')
            receipt=json.loads((root/'FAULT.json').read_text())
            self.assertFalse(receipt['gpu_fault_confirmed']);self.assertTrue(receipt['no_retry'])

    def test_cleanup_uses_only_owned_id_and_preserves_uncertainty(self):
        for wrong,running_after in ((False,False),(False,True),(True,False)):
            with tempfile.TemporaryDirectory() as tmp:
                out=Path(tmp);state={'container_id':'id','container_name':'owned'}
                before={'Id':'id','Name':'/owned','Image':'wrong' if wrong else controller.IMAGE,'State':{'Running':True}}
                after=copy.deepcopy(before);after['State']['Running']=running_after
                inspections=iter([before,after]);commands=[]
                helper=types.SimpleNamespace(now=lambda:'now',inspect_container=lambda _:next(inspections),
                    run=lambda command,**kwargs:(commands.append(command) or types.SimpleNamespace(returncode=0,stdout='',stderr='')))
                confirmed=controller.finish_owned(helper,types.SimpleNamespace(wait=lambda timeout:0),out,state)
                self.assertEqual(confirmed,not wrong and not running_after)
                self.assertEqual(commands,[] if wrong else [['docker','stop','--time','30','id']])
                self.assertEqual((out/'STOP_UNCONFIRMED').exists(),not confirmed)

    def test_cleanup_timeout_preserves_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);info={'Id':'id','Name':'/owned','Image':controller.IMAGE,'State':{'Running':True}}
            def timeout(*args,**kwargs):raise subprocess.TimeoutExpired(['docker'],45)
            helper=types.SimpleNamespace(now=lambda:'now',inspect_container=lambda _:info,run=timeout)
            self.assertFalse(controller.finish_owned(helper,None,out,{'container_id':'id','container_name':'owned'}))
            self.assertTrue(json.loads((out/'stop.json').read_text())['errors'])

    def test_worker_check_only_never_imports_torch(self):
        original=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name=='torch' or name.startswith('torch.'):raise AssertionError('Torch import forbidden')
            return original(name,*args,**kwargs)
        with mock.patch.object(sys,'argv',[str(controller.WORKER),'--out','/unused','--check-only']),mock.patch('builtins.__import__',guarded):
            runpy.run_path(str(controller.WORKER),run_name='__main__')


if __name__=='__main__':unittest.main()
