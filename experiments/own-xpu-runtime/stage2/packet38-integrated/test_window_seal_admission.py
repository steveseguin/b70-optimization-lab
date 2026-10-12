"""CPU no-launch rehearsal of final seal consumers and window admission branches.

A real completed seal is required. Prerequisite/host-health inputs are explicit
mock objects, never persisted as passing device receipts. Every launcher raises
before Popen/device contact, and every window result must be failed/unexecuted.
"""
import argparse,contextlib,hashlib,json,os,shutil,tempfile,time
from pathlib import Path
from unittest.mock import patch
import pipeline as pp
import window
import draft_window
P=Path(__file__).resolve().parent
B=P/'build'

class BlockedLaunch(RuntimeError):pass

class Watch:
    def __init__(self,*unused):self.launched=[];self.cancelled=[];self.last=0.;self.end=time.monotonic()+300
    def check(self):pass
    def poll_kernel(self):pass
    def mark_launched(self,pid):raise AssertionError('device contact is prohibited')
    def latch(self,reason):pass
    def postflight(self):raise AssertionError('blocked launch cannot pass postflight')

def contract(build):
    fields=('passed','sources','artifacts_sha256','official_manifest_sha256','memory_plan','input_sha256',
            'p33_linked_fixture_host_sha256','nongemv_fixture_host_sha256',
            'draft_capture_fixture_sha256','draft_capture_input_sha256')
    assert all(name in build for name in fields),['missing seal field',*[name for name in fields if name not in build]]
    assert build['passed'] is True and build['device_executed'] is False
    assert all(name in build['artifacts_sha256'] for name in ('gnu-host/own-rt-iq3','device/own-rt-iq3','device/p33-linked-fixtures','device/nongemv-fixtures','device/k2-fixtures','device/jit-smoke'))
    assert build['sources'] and build['memory_plan']
    for name in ('official_manifest_sha256','input_sha256','p33_linked_fixture_host_sha256','nongemv_fixture_host_sha256'):
        assert len(build[name])==64 and set(build[name])<=set('0123456789abcdef'),name
    for name in ('draft_capture_fixture_sha256','draft_capture_input_sha256'):
        assert build[name].get('incident-retrospective'),name
    return {name:build[name] for name in fields}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--build-receipt',type=Path,default=P/'build-receipt.json');a=ap.parse_args()
    assert a.build_receipt.resolve()==(P/'build-receipt.json').resolve(),'window.main reads the packet final seal'
    build=json.loads(a.build_receipt.read_text());consumed=contract(build)
    consumed_hash=hashlib.sha256(json.dumps(consumed,sort_keys=True).encode()).hexdigest()
    source_before={name:pp.sha(P/name) for name in ('window.py','fixture_support.py','draft_window.py','test_window_seal_admission.py')}
    root=Path(tempfile.mkdtemp(prefix='seal-admission-',dir=B));rows=[]
    ld=os.environ.get('LD_LIBRARY_PATH')
    env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'}
    if ld is not None:env['LD_LIBRARY_PATH']=ld
    seen=[]
    def blocked(*args,**kwargs):
        seen.append(True);raise BlockedLaunch('CPU admission rehearsal: launch intentionally blocked')
    def prerequisites(path,name,identity):
        # Only prerequisites are mocked; the real source/binary/input seal and
        # branch-specific consumer fields are read unchanged by window.main.
        assert path is not None
        return dict(identity,passed=True,window=name,pids=([101,102] if name=='K1a' else [103,104]),
                    candidate_dispatch_sha256=pp.sha(P/'dispatch-p38.json'),dispatch_sha256=pp.sha(P/'dispatch-p38.json'))
    try:
        for name in window.CONFIG:
            modes=('python','native') if name.startswith('W2') else ('native',) if name.startswith('WS') else ('python',)
            for controller in modes:
                out=root/(name+'-'+controller);seen.clear()
                argv=['window.py','--authorized-device-window','--window',name,'--card','0','--output',str(out),
                      '--controller',controller,'--input',str(B/'input'),'--oracle',str(root/'mock-oracle'),
                      '--dispatch',str(P/'dispatch-p38.json'),'--suite-manifest',str(P.parent/'suite-inputs-20261012/suite-manifest.json')]
                for key in ('k0','k1a','k1b','k2','w0p','kd'):argv.extend(['--'+key,str(root/('mock-'+key))])
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch.dict(os.environ,env,clear=True))
                    stack.enter_context(patch('sys.argv',argv))
                    stack.enter_context(patch.object(window.os,'getpriority',return_value=0 if name.startswith('W') else 19))
                    stack.enter_context(patch.object(window,'prerequisites',prerequisites))
                    stack.enter_context(patch.object(window,'foreign_engines',return_value={'cpu_mock':True}))
                    stack.enter_context(patch.object(window,'admit',return_value={'cpu_mock':True}))
                    stack.enter_context(patch.object(window,'memory_snapshot',return_value={'MemAvailable':128*1024**3}))
                    stack.enter_context(patch.object(window,'oracle_gate',return_value=({},[1]*64)))
                    stack.enter_context(patch.object(window,'Watch',Watch))
                    stack.enter_context(patch.object(window,'ldd_preflight',return_value={'cpu_mock':True}))
                    stack.enter_context(patch.object(window,'run_fixtures',blocked))
                    stack.enter_context(patch.object(window,'concurrency_canary',blocked))
                    stack.enter_context(patch.object(pp,'run',blocked))
                    # KD runs its actual retained-reference/hash admission, then
                    # Popen is blocked. No binary, including host binaries, runs.
                    stack.enter_context(patch('fixture_support.ldd_preflight',return_value={'cpu_mock':True}))
                    stack.enter_context(patch.object(draft_window,'admit',return_value={'cpu_mock':True}))
                    stack.enter_context(patch.object(draft_window.subprocess,'Popen',blocked))
                    rc=window.main()
                record=json.loads((out/'window.json').read_text())
                assert seen==[True] and rc==1 and record['passed'] is False and record['device_executed'] is False,(name,controller,record)
                assert 'launch intentionally blocked' in record['error'] and not record['launched_pids']
                rows.append(dict(window=name,controller=controller,admission_reached_blocked_launcher=True,device_executed=False,window_passed=False,
                                 prerequisite_and_host_health_inputs='explicit CPU mocks',retained_capture_admission_exercised=name=='KD'))
        assert source_before=={name:pp.sha(P/name) for name in source_before},'source changed during admission test'
        result=dict(passed=True,device_executed=False,gates=len(rows)+1,seal_fields=list(consumed),consumed_seal_sha256=consumed_hash,
                    source_sha256=source_before,rows=rows,meaning='CPU admission/field-contract test passed; every window remained failed and no launch executed')
        pp.save(P/'window-seal-admission-gates.json',result);print(json.dumps(result))
    finally:shutil.rmtree(root)
if __name__=='__main__':main()
