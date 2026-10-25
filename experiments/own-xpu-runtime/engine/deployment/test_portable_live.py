"""Synthetic portable live recipe/lifecycle tests; no GPU or model payload work."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

import portable_live as adapter
import test_launch_plan as fixtures


class PortableLiveTests(unittest.TestCase):
    setUp=fixtures.LaunchPlanTests.setUp
    pin=fixtures.LaunchPlanTests.pin
    run_prepare=fixtures.LaunchPlanTests.run_prepare
    external_policy=fixtures.LaunchPlanTests.external_policy
    def config(self,**changes):
        self.receipt['sources']={name:'a'*64 for name in ('pipeline/layout.hpp','pipeline/wavefront.hpp','pipeline/checkpoint.hpp','pipeline/live_draft.hpp','pipeline/operator_state.hpp')}
        self.receipt_path.write_bytes(adapter.planner.prep.encoded(self.receipt))
        config=dict(schema='ownrt.portable-live-config.v1',deployment=str(self.out),profile_sha256=self.sha,binding_sha256=self.binding_sha,
                    build_receipt=str(self.receipt_path),build_receipt_sha256=adapter.planner.hash_file(self.receipt_path),
                    bdfs=['0000:23:00.0','0000:47:00.0'],library_dirs=[str(self.lib)],output=str(self.run),prompt_tokens=[1,2,3])
        config.update(changes)
        self.config_path=self.root/'portable-live-config.json';self.config_path.write_text(json.dumps(config))
        return self.config_path
    def test_plan_uses_portable_binding_and_never_lab_planners(self):
        path=self.config()
        with mock.patch.object(adapter.live,'make_plan',side_effect=AssertionError('lab planner')),mock.patch.object(adapter.live.wave,'make_plan',side_effect=AssertionError('lab wave planner')),mock.patch.object(adapter.live.base,'make_plan',side_effect=AssertionError('lab base planner')):
            plan=adapter.make_plan(path)
        self.assertFalse(plan['run_authorized']);self.assertFalse(plan['draft_training'])
        self.assertTrue(plan['verify_restore']);self.assertFalse(plan['draft_partition'])
        self.assertEqual(plan['eos_token_ids'],[248044,248046])
        for stage in plan['stages']:
            self.assertEqual('--draft-mtp' in stage['argv'],stage['first'])
            self.assertIn('--pipeline-live-draft',stage['argv'])
            self.assertNotIn('OWNRT_DRAFT_DEPTH_PROBE',stage['environment'])
            self.assertNotIn('OWNRT_DRAFT_DEPTH_VERIFY',stage['environment'])
            self.assertNotIn('observer',stage['environment'])
        self.assertIn(str(self.out/'draft-manifest.tsv'),plan['stages'][0]['argv'])
        self.assertTrue(all(str(adapter.ENGINE/p) in plan['pins'] for p in adapter.RUNTIME_FILES))
    def test_quad_partition_is_explicit_and_unknown_fields_refuse(self):
        plan=adapter.make_plan(self.config(bdfs=['0000:23:00.0','0000:27:00.0','0000:43:00.0','0000:47:00.0'],draft_partition=True,verify_restore=False))
        self.assertEqual(len(plan['stages']),4)
        self.assertTrue(all('--pipeline-draft-partition' in s['argv'] for s in plan['stages']))
        self.assertTrue(all('--pipeline-wavefront-verify-restore' not in s['argv'] for s in plan['stages']))
        with self.assertRaisesRegex(ValueError,'unknown portable'):adapter.make_plan(self.config(unsafe_override=True))
    def test_missing_native_live_capability_refuses(self):
        path=self.config();self.receipt['sources'].pop('pipeline/live_draft.hpp');self.receipt_path.write_bytes(adapter.planner.prep.encoded(self.receipt))
        config=json.loads(path.read_text());config['build_receipt_sha256']=adapter.planner.hash_file(self.receipt_path);path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError,'source capability'):adapter.make_plan(path)
    def test_live_recipe_uses_selected_policy_for_plan_and_provider(self):
        selected=self.external_policy(boundaries={'2':[0,24,48],'4':[0,12,24,36,48]})
        path=self.config(launch_policy=str(selected['policy_path']),launch_policy_sha256=selected['policy_sha256'])
        with mock.patch.object(adapter.planner,'PROFILE',self.root/'absent-builtin'):
            plan=adapter.make_plan(path)
            saved=self.root/'selected-plan.json';saved.write_text(json.dumps(plan))
            self.assertEqual(adapter.verify_plan(saved,adapter.planner.hash_file(saved),self.sha,self.binding_sha,
                                                adapter.planner.hash_file(self.receipt_path)),plan)
        self.assertEqual(plan['boundaries'],[0,24,48])
        self.assertEqual(plan['launch_policy']['sha256'],selected['policy_sha256'])
        with self.assertRaisesRegex(ValueError,'supplied together'):
            adapter.make_plan(self.config(launch_policy=str(selected['policy_path'])))
    def test_plan_rechecks_full_identity_and_independent_profile(self):
        plan=adapter.make_plan(self.config());path=self.root/'plan.json';path.write_text(json.dumps(plan));sha=adapter.planner.hash_file(path)
        self.assertEqual(adapter.verify_plan(path,sha,self.sha,self.binding_sha,adapter.planner.hash_file(self.receipt_path)),plan)
        with self.assertRaisesRegex(ValueError,'independent model'):
            adapter.verify_plan(path,sha,'0'*64,self.binding_sha,adapter.planner.hash_file(self.receipt_path))
        plan['stages'][0]['environment']['LD_PRELOAD']='bad';path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError,'identity changed'):
            adapter.verify_plan(path,adapter.planner.hash_file(path),self.sha,self.binding_sha,adapter.planner.hash_file(self.receipt_path))
    def test_live_admission_requires_adapter_digest(self):
        with mock.patch.object(adapter.controller,'admit') as admission:
            with self.assertRaisesRegex(ValueError,'live controller'):
                adapter.admit({},dict(live_controller_sha256='0'*64),'plan')
            admission.assert_not_called()
            adapter.admit({},dict(live_controller_sha256=adapter.planner.hash_file(adapter.__file__)),'plan')
            admission.assert_called_once()


class LifecycleTests(unittest.TestCase):
    def test_injected_portable_guard_and_one_shot_lifecycle(self):
        calls=[]
        class PortableGuard:
            def __init__(self,plan,admission,fd):
                self.failed=None;self.baseline={};self.initial_observation={};self.signal_stop=threading.Event();self.done=threading.Event()
                self.thread=mock.Mock();self.thread.is_alive.return_value=False;self.obs=mock.Mock();self.obs.observe.return_value={}
                self.tracked_processes=[]
            def check(self):
                if self.failed:raise RuntimeError(self.failed)
            def validate(self,row):pass
            def fail(self,reason):self.failed=self.failed or str(reason)
        class Stage:
            def __init__(self,spec,plan,guard):
                assert isinstance(guard,PortableGuard)
                self.spec=spec;self.stream_bytes=16;self.guard=guard
                guard.tracked_processes.append((spec['id'],mock.Mock(pid=100+spec['id'],poll=mock.Mock(return_value=0))))
                calls.append(('spawn',spec['id']))
            def receive(self,ready=False):calls.append(('ready',self.spec['id']))
            def command(self,op,**args):calls.append((op,self.spec['id']))
        with tempfile.TemporaryDirectory() as tmp:
            plan=dict(output=str(Path(tmp)/'run'),stages=[dict(id=0),dict(id=1)],grace_seconds=10)
            admission=dict(schema='ownrt.portable-run-admission.v1',owner_authorized=True,expires_utc=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat())
            with mock.patch.object(adapter.controller,'Guard',PortableGuard),mock.patch.object(adapter.live,'LiveStage',Stage),mock.patch.object(adapter.live,'drive',return_value=dict(output_ids=[3,4],input_position=4)),mock.patch.object(adapter.os,'getpriority',return_value=19),mock.patch.object(adapter.live.base,'Guard',side_effect=AssertionError('lab guard')),mock.patch.object(adapter.live.base,'load_module',side_effect=AssertionError('lab observer')),mock.patch.object(adapter.live.wave,'execute',side_effect=AssertionError('lab lifecycle')):
                result=adapter.execute(plan,admission,stop_fd=0)
            data=json.loads(result.read_text());self.assertTrue(data['passed']);self.assertFalse(data['speed_claim'])
            self.assertEqual(calls,[('spawn',0),('ready',0),('spawn',1),('ready',1),(4,0),(4,1),(5,0),(5,1)])
            self.assertTrue((Path(plan['output'])/'postflight.json').exists())
    def test_package_relative_imports_work_without_repository_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';(root/'deployment').mkdir(parents=True)
            for path in (adapter.ENGINE/'deployment').glob('*.py'):
                if not path.name.startswith('test_'):shutil.copyfile(path,root/'deployment'/path.name)
            for name in adapter.RUNTIME_FILES:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(adapter.ENGINE/name,path)
            result=subprocess.run([sys.executable,'-E','-s',str(root/'deployment/portable_live.py'),'--help'],cwd=tmp,env={'PATH':'/usr/bin:/bin'},capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('plan,check,run',result.stdout)


if __name__=='__main__':unittest.main()
