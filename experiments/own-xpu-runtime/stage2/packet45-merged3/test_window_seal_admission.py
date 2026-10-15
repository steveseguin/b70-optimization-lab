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
import suite
import storage
P=Path(__file__).resolve().parent
B=P/'build'

class BlockedLaunch(RuntimeError):pass

class Watch:
    def __init__(self,*unused):self.launched=[];self.cpu_children=[];self.cancelled=[];self.last=0.;self.end=time.monotonic()+300
    def check(self):pass
    def poll_kernel(self):pass
    def mark_launched(self,pid):raise AssertionError('device contact is prohibited')
    def latch(self,reason):pass
    def postflight(self):raise AssertionError('blocked launch cannot pass postflight')

def contract(build):
    fields=('passed','sources','artifacts_sha256','model_evidence_artifacts_sha256','fixture_delta_qualification','official_manifest_sha256','memory_plan','input_sha256',
            'p33_linked_fixture_host_sha256','nongemv_fixture_host_sha256',
            'draft_capture_fixture_sha256_by_context','draft_capture_input_sha256','cpu_tests_sha256','nongemv_fixture_host_sha256_by_context')
    assert all(name in build for name in fields),['missing seal field',*[name for name in fields if name not in build]]
    assert build['passed'] is True and build['device_executed'] is False
    assert all(name in build['artifacts_sha256'] for name in ('gnu-host/own-rt-iq3','device/own-rt-iq3','device/p33-linked-fixtures','device/nongemv-fixtures','device/k2-fixtures','device/jit-smoke'))
    assert build['sources'] and build['memory_plan']
    for name in ('official_manifest_sha256','input_sha256','p33_linked_fixture_host_sha256','nongemv_fixture_host_sha256'):
        assert len(build[name])==64 and set(build[name])<=set('0123456789abcdef'),name
    assert build['draft_capture_input_sha256'].get('incident-retrospective')
    for context in ('256','4096','32768'):
        assert build['draft_capture_fixture_sha256_by_context'].get(context)
        assert build['nongemv_fixture_host_sha256_by_context'].get(context)
    return {name:build[name] for name in fields}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--build-receipt',type=Path,default=P/'build-receipt.json');a=ap.parse_args()
    assert a.build_receipt.resolve() in {(P/'build-receipt.json').resolve(),(P/'build-admission-candidate.json').resolve()},'only packet final/candidate seal may be rehearsed'
    supplied=a.build_receipt.read_text();supplied_sha=hashlib.sha256(supplied.encode()).hexdigest()
    original_read_text=Path.read_text;original_sha=window.sha
    latch=B/'FAULT.json'
    latch_before=latch.read_bytes() if latch.exists() else None
    def seal_read(path,*args,**kwargs):
        # Rehearse post-recovery admission without touching a real boot latch.
        # All launchers remain blocked and all health inputs remain CPU mocks.
        if path==Path('/proc/sys/kernel/random/boot_id'):return 'cpu-no-launch-rehearsal'
        return supplied if path.resolve()==(P/'build-receipt.json').resolve() else original_read_text(path,*args,**kwargs)
    def seal_sha(path):
        return supplied_sha if Path(path).resolve()==(P/'build-receipt.json').resolve() else original_sha(path)
    build=json.loads(a.build_receipt.read_text());consumed=contract(build)
    consumed_hash=hashlib.sha256(json.dumps(consumed,sort_keys=True).encode()).hexdigest()
    source_before={name:pp.sha(P/name) for name in ('window.py','fixture_support.py','draft_window.py','suite.py','pipeline.py','suite_metrics.py','memory_gate.py','test_window_seal_admission.py')}
    storage.admit(256_000_000)
    root=Path(tempfile.mkdtemp(prefix='seal-admission-',dir=P/'evidence'));rows=[];input_rows=[]
    manifests={cap:P.parent/bundle/'suite-manifest.json' for cap,bundle in ((32,'long-inputs-20261012'),(64,'suite-inputs-20261012'),(128,'suite-inputs-20261012-cap128'))}
    oracle=suite.ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective'
    ld=os.environ.get('LD_LIBRARY_PATH')
    env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'}
    if ld is not None:env['LD_LIBRARY_PATH']=ld
    seen=[]
    def blocked(*args,**kwargs):
        seen.append(True);raise BlockedLaunch('CPU admission rehearsal: launch intentionally blocked')
    def prerequisites(path,kind,identity,*,cpu_rehearsal=False):
        # Only prerequisites are mocked; the real source/binary/input seal and
        # branch-specific consumer fields are read unchanged by window.main.
        assert path is not None and cpu_rehearsal is False
        selector='1-8,97-104' if cap==128 else '1-8'
        return dict(identity,passed=True,window=kind,pids=([101,102] if kind=='K1a' else [103,104]),
                    candidate_dispatch_sha256=pp.sha(P/'dispatch-p45.json'),dispatch_sha256=pp.sha(P/'dispatch-p45.json'),
                    controller=controller,max_new=cap,prompt_overlap='on',retain_steps=selector,
                    retained_steps=pp.retention_steps(selector,cap),diagnostic_for_speed=True,
                    expected_tokens=[1]*cap,suite_manifest_sha256=pp.sha(manifest))
    try:
        # Real immutable metadata and full checker admission, without model execution.
        for cap,manifest in manifests.items():
            data=json.loads(manifest.read_text());output=root/('input-cap'+str(cap));output.mkdir()
            snapshots=suite.admit_inputs(data['prompts'],output,suite.checker_for_cap(cap))
            input_rows.append(dict(token_cap=cap,manifest_sha256=pp.sha(manifest),prompts=len(snapshots),
                                   admission=json.loads((output/'input-admission.json').read_text())))
            shutil.rmtree(output)
        configurations=[]
        for context in (256,4096,32768):
            for draft_rank in (0,1):
                configurations.extend((context,draft_rank,name,'python',64) for name in ('K0','K1a','K1b','K2','W0p','KD'))
                configurations.extend((context,draft_rank,'W2m',controller,64) for controller in ('python','native'))
                configurations.extend((context,draft_rank,name,'native',cap) for name in ('WS','WSs') for cap in (32,64,128))
        configurations=[(*row,0) for row in configurations]
        configurations.extend((4096,0,name,'python',64,24) for name in ('K0','K1a','K1b','K2','W0p','KD'))
        configurations.extend((4096,0,'W2m',controller,64,24) for controller in ('python','native'))
        configurations.extend((4096,0,name,'native',cap,24) for name in ('WS','WSs') for cap in (32,64,128))
        configurations.extend((4096,dr,name,'native',128,split) for dr,split in ((0,0),(1,0),(0,24)) for name in ('WS128x','WS128'))
        for context,draft_rank,name,controller,cap,target_split in configurations:
                out=root/(f'{context}-dr{draft_rank}-s{target_split}-{name}-{controller}-cap{cap}');seen.clear()
                manifest=manifests[cap]
                companion=root/'mock-exactness';companion.write_text('{}')
                argv=['window.py','--authorized-device-window','--window',name,'--card','0','--context',str(context),'--draft-rank',str(draft_rank),'--target-split',str(target_split),'--retain-steps',('none' if name=='WS128' else '1-8,97-104' if name=='WS128x' else '1-8'),'--output',str(out),
                      '--controller',controller,'--input',str(B/'input'),'--oracle',str(oracle),
                      '--dispatch',str(P/'dispatch-p45.json'),'--suite-manifest',str(manifest),'--max-new',str(cap)]
                if name in window.SPEED_WINDOWS:argv.extend(['--exactness-window',str(companion)])
                for key in ('k0','k1a','k1b','k2','w0p','kd'):argv.extend(['--'+key,str(root/('mock-'+key))])
                with contextlib.ExitStack() as stack:
                    # CPU test only: inject the candidate at the fixed final-seal read.
                    # The production wrapper has no candidate option or bypass.
                    stack.enter_context(patch.object(Path,'read_text',seal_read))
                    stack.enter_context(patch.object(window,'sha',seal_sha))
                    stack.enter_context(patch.dict(os.environ,env,clear=True))
                    stack.enter_context(patch('sys.argv',argv))
                    stack.enter_context(patch.object(window.os,'getpriority',return_value=0 if name.startswith('W') else 19))
                    stack.enter_context(patch.object(window,'prerequisites',prerequisites))
                    stack.enter_context(patch.object(window,'foreign_engines',return_value={'cpu_mock':True}))
                    stack.enter_context(patch.object(window,'admit',return_value={'cpu_mock':True}))
                    stack.enter_context(patch.object(window,'memory_snapshot',return_value={'MemAvailable':128*1024**3}))
                    stack.enter_context(patch.object(window,'Watch',Watch))
                    stack.enter_context(patch.object(window,'ldd_preflight',return_value={'cpu_mock':True}))
                    stack.enter_context(patch.object(window,'run_fixtures',blocked))
                    stack.enter_context(patch.object(window,'concurrency_canary',blocked))
                    stack.enter_context(patch.object(pp,'run',blocked))
                    # KD runs its actual retained-reference/hash admission, then
                    # Popen is blocked. No binary, including host binaries, runs.
                    # Keep exact file hashing in process: fixture_support.sha uses
                    # CPU sha256sum, whose Popen would hit the global launch blockade.
                    # This substitutes the same SHA-256 operation, not its result.
                    stack.enter_context(patch('fixture_support.sha',side_effect=lambda path:pp.sha(Path(path))))
                    stack.enter_context(patch('fixture_support.ldd_preflight',return_value={'cpu_mock':True}))
                    stack.enter_context(patch.object(draft_window,'admit',return_value={'cpu_mock':True}))
                    stack.enter_context(patch.object(draft_window.subprocess,'Popen',blocked))
                    if cap==32 and context==256:
                        try:window.main()
                        except ValueError as error:
                            assert 'suite capacity must cover oracle capacity' in str(error),str(error)
                        else:raise AssertionError('long32 must refuse context256')
                        assert not seen and not out.exists()
                        rows.append(dict(window=name,context=context,draft_rank=draft_rank,target_split=target_split,controller=controller,token_cap=cap,
                                         expected_capacity_refusal=True,device_executed=False,window_passed=False))
                        continue
                    rc=window.main()
                record=json.loads((out/'window.json').read_text())
                assert seen==[True] and rc==1 and record['passed'] is False and record['device_executed'] is False,(name,controller,record)
                assert 'launch intentionally blocked' in record['error'] and not record['launched_pids']
                rows.append(dict(window=name,context=context,draft_rank=draft_rank,target_split=target_split,controller=controller,token_cap=cap,admission_reached_blocked_launcher=True,device_executed=False,window_passed=False,
                                 prerequisite_and_host_health_inputs='explicit CPU mocks',retained_capture_admission_exercised=name=='KD'))
        assert source_before=={name:pp.sha(P/name) for name in source_before},'source changed during admission test'
        assert (latch.read_bytes() if latch.exists() else None)==latch_before,'real fault latch changed during rehearsal'
        result=dict(simulated_boot='cpu-no-launch-rehearsal',real_fault_latch_unchanged=True,real_fault_latch_sha256=hashlib.sha256(latch_before).hexdigest() if latch_before is not None else None,passed=True,device_executed=False,gates=len(rows)+len(input_rows)+1,input_admissions=input_rows,real_capacity_refusals=sum(r.get('expected_capacity_refusal',False) for r in rows),rehearsed_seal=str(a.build_receipt.resolve().relative_to(P)),seal_fields=list(consumed),consumed_seal_sha256=consumed_hash,
                    source_sha256=source_before,rows=rows,meaning='CPU admission/field-contract test passed; every window remained failed and no launch executed')
        pp.save(P/'window-seal-admission-gates.json',result);print(json.dumps(result))
    finally:shutil.rmtree(root)
if __name__=='__main__':main()
