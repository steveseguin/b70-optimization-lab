"""CPU lifecycle regression: constructor-failed children remain accounted."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import dedicated_provider_lifecycle as life
class Guard:
    last=None
    def __init__(self,plan,admission,fd):
        Guard.last=self;self.plan=plan;self.tracked_processes=[];self.failed=None
        self.first_failure=self.failure_evidence_error=None
        self.signal_stop=NS(set=lambda:None);self.done=NS(set=lambda:None)
        self.obs=NS(observe=lambda:{})
        self.thread=NS(start=lambda:None,ident=None,is_alive=lambda:False)
    def check(self):
        if self.failed:raise RuntimeError(self.failed)
    def validate_or_stop(self,*args,**kwargs):pass
    def fail(self,error):self.failed=str(error)
class LifecycleTests(unittest.TestCase):
    def run_case(self,fail=False):
        with TemporaryDirectory() as tmp:
            out=Path(tmp)/'fresh';calls=[]
            specs=[dict(id=i,bdf=str(i),native_output=str(out/f'stage{i}'/'native')) for i in range(2)]
            provider=dict(id='provider',bdf='2',native_output=str(out/'stageprovider'/'native'))
            plan=dict(stages=specs,provider=provider,output=str(out),grace_seconds=0,speculative_depth=3,request_sha256='00'*32)
            admission=dict(schema='ownrt.pipeline-admission.v1',owner_authorized=True,expires_utc=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat())
            def stage(spec,plan,guard):
                guard.tracked_processes.append((spec['id'],NS(pid=100+len(guard.tracked_processes),poll=lambda:0)))
                if spec['id']=='provider' and fail:raise ValueError('constructor after Popen')
                return NS(stream_bytes=64,receive=lambda **kw:None,command=lambda op,**kw:calls.append((spec['id'],op)))
            def wrap(owner):
                return NS(stream_bytes=64,receive_ready=lambda **kw:None,control=lambda op:calls.append(('provider',op)))
            with patch.object(life.base,'Guard',Guard),patch.object(life.base,'validate_unit',return_value={}),patch.object(life.os,'getpriority',return_value=19),patch.object(life.base,'Stage',side_effect=stage),patch.object(life.bridge,'Stage',side_effect=stage),patch.object(life.bridge,'Provider',side_effect=wrap),patch.object(life.bridge,'drive',return_value=dict(output_ids=[7,8],scheduler_wall_seconds=.5)):
                if fail:
                    with self.assertRaisesRegex(ValueError,'constructor after Popen'):life.execute(plan,admission,'unit')
                else:life.execute(plan,admission,'unit')
            terminal=json.loads((out/'terminal.json').read_text());result=json.loads((out/'driver-result.json').read_text())
            self.assertEqual(len(Guard.last.plan['stages']),3)
            self.assertEqual(terminal['returncodes'],{'0':0,'1':0,'provider':0});self.assertEqual(terminal['live_pids'],[])
            if fail:self.assertFalse(terminal['passed']);self.assertEqual(calls,[])
            else:
                self.assertTrue(terminal['passed']);self.assertEqual(result['output_ids'],[7,8])
                self.assertEqual(calls,[(0,4),(1,4),('provider',4),(0,5),(1,5),('provider',5)])
    def test_success(self):self.run_case()
    def test_constructor_failure_retains_child(self):self.run_case(True)
if __name__=='__main__':unittest.main()
