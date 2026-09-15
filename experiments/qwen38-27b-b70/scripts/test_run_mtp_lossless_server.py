#!/usr/bin/env python3
"""CPU-only ownership, snapshot and shutdown regression checks; no Docker calls."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest

path = Path(__file__).with_name('run-mtp-lossless-server.py')
spec = importlib.util.spec_from_file_location('mtp_server_under_test', path)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class ShutdownTests(unittest.TestCase):
    def scenario(self, *, running_after=False, stop_error=False, client_live=False, wrong_owner=False, absent=False, failure=None):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            state={'container_name':'owned','container_id':'immutable-id','image_id':server.CONTROL_IMAGE,'status':'ready'}
            before={'Name':'/owned','Id':'immutable-id','Image':server.CONTROL_IMAGE,'State':{'Running':True}}
            if wrong_owner: before['Image']='other-image'
            after=copy.deepcopy(before); after['State']['Running']=running_after
            inspections=iter([None] if absent else [before,after]); commands=[]
            def run(argv,**kwargs):
                commands.append(argv)
                if stop_error: raise subprocess.TimeoutExpired(argv,150)
                return types.SimpleNamespace(returncode=0,stdout='stopped',stderr='')
            helper=types.SimpleNamespace(now=lambda:'test-time',inspect_container=lambda _:next(inspections),run=run)
            def wait(timeout):
                if client_live: raise subprocess.TimeoutExpired(['docker'],timeout)
                return 0
            child=types.SimpleNamespace(poll=lambda:None if client_live else 0,wait=wait)
            confirmed=server.stop_owned_server(helper,child,out,state,failure)
            return confirmed,json.loads((out/'state.json').read_text()),json.loads((out/'stop.json').read_text()),commands,(out/'STOP_UNCONFIRMED').exists()

    def test_success_stops_immutable_id_once(self):
        ok,state,receipt,commands,latch=self.scenario()
        self.assertTrue(ok); self.assertEqual(state['status'],'stopped'); self.assertFalse(latch)
        self.assertEqual(commands,[['docker','stop','--time','120','immutable-id']])

    def test_running_container_never_reported_stopped(self):
        ok,state,_,commands,latch=self.scenario(running_after=True)
        self.assertFalse(ok); self.assertEqual(state['status'],'stop_unconfirmed'); self.assertTrue(latch); self.assertEqual(len(commands),1)

    def test_stop_timeout_retains_evidence(self):
        ok,state,receipt,commands,latch=self.scenario(running_after=True,stop_error=True)
        self.assertFalse(ok); self.assertTrue(receipt['errors']); self.assertTrue(latch); self.assertEqual(len(commands),1)

    def test_dead_container_live_client_unconfirmed(self):
        ok,state,_,_,latch=self.scenario(client_live=True)
        self.assertFalse(ok); self.assertEqual(state['status'],'stop_unconfirmed'); self.assertTrue(latch)

    def test_wrong_owner_not_stopped(self):
        ok,state,_,commands,latch=self.scenario(wrong_owner=True)
        self.assertFalse(ok); self.assertEqual(commands,[]); self.assertTrue(latch)

    def test_absent_container_live_client_unconfirmed(self):
        ok,state,_,commands,latch=self.scenario(absent=True,client_live=True)
        self.assertFalse(ok); self.assertEqual(commands,[]); self.assertTrue(latch)

    def test_failure_status_preserved_after_clean_stop(self):
        ok,state,_,_,latch=self.scenario(failure='prior fault')
        self.assertTrue(ok); self.assertEqual(state['status'],'failed'); self.assertTrue(state['stop_confirmed']); self.assertFalse(latch)

    def test_actual_controller_argv_preserves_qualified_ipc(self):
        tree=ast.parse(path.read_text())
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        node=next(n for n in ast.walk(main) if isinstance(n,ast.Assign)
                  and any(isinstance(t,ast.Name) and t.id=='cmd' for t in n.targets))
        namespace={'name':'test-owned','a':types.SimpleNamespace(port=18129),
                   'MODEL_DIR':server.MODEL_DIR,'out':Path('/test-state')}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])), '<actual-controller-argv>', 'exec'),namespace)
        argv=namespace['cmd']
        for flag,value in (('--cap-add','SYS_PTRACE'),('--network','bridge'),('--ipc','host')):
            self.assertEqual(argv[argv.index(flag)+1],value)
        self.assertNotIn('--privileged',argv)

    def test_snapshot_independent_of_repository_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'source';source.mkdir();out=root/'out';out.mkdir()
            for name in ('mtp_transfer_worker.py','mtp_native_metadata_gate.py'):(source/name).write_text('value = 1\n')
            (source/'unreviewed.py').write_text('raise RuntimeError()\n')
            snap,hashes=server.snapshot_extensions(source,out)
            try:
                (source/'mtp_transfer_worker.py').write_text('value = 2\n')
                self.assertEqual((snap/'mtp_transfer_worker.py').read_text(),'value = 1\n')
                self.assertEqual(set(p.name for p in snap.iterdir()),set(hashes))
                self.assertFalse((snap/'unreviewed.py').exists())
                self.assertEqual(snap.stat().st_mode & 0o777,0o555)
            finally:
                snap.chmod(0o755)
                for p in snap.iterdir():p.chmod(0o644)


class QualifiedEnvironmentTests(unittest.TestCase):
    def test_contract_gains_the_five_qualified_variables(self):
        env=server.qualified_env({'env':['VLLM_USE_V2_MODEL_RUNNER=0']})
        self.assertEqual({k:env[k] for k in server.QUALIFIED_ENV},server.QUALIFIED_ENV)
        self.assertEqual(env['VLLM_USE_V2_MODEL_RUNNER'],'0')

    def test_conflicting_contract_value_refused(self):
        with self.assertRaises(RuntimeError):
            server.qualified_env({'env':['PYTORCH_ALLOC_CONF=expandable_segments:False']})

    def test_actual_recorded_contract_merges_without_conflict(self):
        if not server.ORIGINAL.exists():self.skipTest('recorded contract unavailable')
        env=server.qualified_env(json.loads(server.ORIGINAL.read_text()))
        self.assertEqual(env['PYTORCH_ALLOC_CONF'],'expandable_segments:True')

    def test_actual_launch_env_comes_from_qualified_env(self):
        tree=ast.parse(path.read_text())
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        assigns=[n for n in ast.walk(main) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='env' for t in n.targets)]
        self.assertEqual(len(assigns),1)
        call=assigns[0].value
        self.assertTrue(isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='qualified_env')

    def test_client_expects_the_same_qualified_environment(self):
        spec=importlib.util.spec_from_file_location('client_env_check',path.with_name('run-mtp-metadata-client-campaign.py'))
        client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
        self.assertEqual(client.QUALIFIED_ENV,server.QUALIFIED_ENV)


if __name__=='__main__':unittest.main()
