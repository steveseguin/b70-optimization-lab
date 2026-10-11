#!/usr/bin/env python3
"""Lifetime repair: cheap CPU gates only, compile-only device, no evidence cleanup."""
import hashlib, json, os, subprocess, time
from pathlib import Path
from build import source_hashes, COMPILER, PY
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BUILD=HERE/'build'
BEFORE=HERE/'evidence/20261011-lifetime-before'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(b): return hashlib.sha256(b).hexdigest()
def read(p): return json.loads(p.read_text())
def save(p,r): p.write_text(json.dumps(r,indent=2)+'\n')
def reuse_proof():
    previous=read(BEFORE/'build-receipt.json'); audit=read(HERE/'deadline-reuse.json')
    assert previous['passed'] and previous['deadline_only_gate_reuse']['audit_sha256']==sha(HERE/'deadline-reuse.json')
    neutral={}
    text=(HERE/'main.cpp').read_text()
    for after,before in [('#include "lifetime_mock.hpp"','#include "mock_device.hpp"'),
                        ('class Host final : public packet18::LifetimeMock {','class Host final : public ownrt::MockDevice {'),
                        ('auto e = LifetimeMock::copy(a, b, n, d);','auto e = MockDevice::copy(a, b, n, d);')]:
        assert text.count(after)==1
        text=text.replace(after,before,1)
    assert digest(text.encode())==sha(BEFORE/'main.cpp')
    neutral[str((HERE/'main.cpp').relative_to(ROOT))]=text
    extra='\nif(OWN_RT_HOST_ONLY)\n add_executable(lifetime-tests lifetime_test.cpp owner.cpp)\n target_include_directories(lifetime-tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${OWNER})\nendif()\n'
    cmake=(HERE/'CMakeLists.txt').read_text();assert cmake.endswith(extra)
    neutral[str((HERE/'CMakeLists.txt').relative_to(ROOT))]=cmake[:-len(extra)]
    for rel,text in neutral.items():assert digest(text.encode())==previous['sources'][rel]
    verified={}
    for rel,expected in audit['original_sources'].items():
        if rel.endswith('.py'):continue # Rebuilt/rerun host tooling, no model operations.
        path=ROOT/rel
        text=neutral.get(rel)
        if rel==audit['isolated_canary']['path']:
            assert sha(BEFORE/'canary.hpp')==audit['isolated_canary']['after_sha256']
            assert expected==audit['isolated_canary']['before_sha256']
            verified[rel]=dict(original=expected,current=sha(path),disposition='isolated canary; not a decode source');continue
        if rel in audit['approved_model_neutral_edits']:
            change=audit['approved_model_neutral_edits'][rel]
            text=text if text is not None else path.read_text()
            assert digest(text.encode())==change['after_sha256']
            for edit in change['edits']:
                assert text.count(edit['after'])==1
                text=text.replace(edit['after'],edit['before'],1)
        actual=digest(text.encode()) if text is not None else sha(path)
        assert actual==expected,rel
        verified[rel]=dict(original=expected,current=sha(path),reconstructed_original=actual)
    assert 'if(a.canary)return run_canary(a);' in (HERE/'main.cpp').read_text()
    receipts={}
    for name,expected in audit['retained_receipts'].items():
        path=BEFORE/name if name in ('sanitizer-mini.json','sanitizer-integration.json') else HERE/name
        assert sha(path)==expected,name
        receipts[str(path.relative_to(HERE))]=expected
    for path in HERE.glob('sanitizer-real-*.json'):receipts[path.name]=sha(path)
    old_san=read(BEFORE/'sanitizer-build-receipt.json')
    assert old_san==read(BUILD/'sanitized/build.json')
    assert sha(Path(old_san['binary']))==old_san['sha256']
    for name,expected in old_san['sources'].items():
        path=Path(name)
        if path.suffix=='.py':continue
        rel=str(path.relative_to(ROOT))
        if rel in verified or path.name=='canary.hpp' and path.parent==HERE:continue
        assert sha(path)==expected,name
    result=dict(passed=True,device_executed=False,previous_build_sha256=sha(BEFORE/'build-receipt.json'),
                previous_watchdog_reuse_sha256=sha(HERE/'deadline-reuse.json'),
                original_host_sha256=audit['original_host_sha256'],original_sanitizer_sha256=old_san['sha256'],
                retained_receipts=receipts,model_inputs=verified,
                statement='Only canary scope, wrapper and CPU instrumentation/test-target changes. Engine, adapter, native owner, peer backend, arithmetic and launch order unchanged. Long gates NOT rerun; original binary identities retained. Fresh device W1 is required.')
    save(HERE/'lifetime-reuse.json',result);return result

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
    assert 'idle' in subprocess.check_output(['ionice','-p',str(os.getpid())],text=True)
    (BUILD/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(BUILD/'tmp')
    r=dict(schema='own-runtime.iq3.packet18.build.v1',passed=False,device_executed=False,max_compile_jobs=2,numeric_threads=2,commands=[])
    def run(cmd,timeout=600):
        cmd=list(map(str,cmd));v=subprocess.run(cmd,capture_output=True,text=True,cwd=ROOT,timeout=timeout)
        r['commands'].append(dict(argv=cmd,returncode=v.returncode,stdout=v.stdout,stderr=v.stderr))
        print('PASS' if not v.returncode else 'FAIL',' '.join(cmd),flush=True)
        assert not v.returncode,(v.stdout,v.stderr)
        return v
    proof=reuse_proof();r['lifetime_gate_reuse']=dict(sha256=sha(HERE/'lifetime-reuse.json'),**proof)
    protected={str(f.relative_to(HERE)):sha(f) for d in ('w1-card3-a','w0-cards23-a') for f in (BUILD/d).rglob('*') if f.is_file()}
    latch=BUILD/'FAULT.json'
    if latch.exists():protected[str(latch.relative_to(HERE))]=sha(latch)
    try:
        for mode,compiler,host in [('host','/usr/bin/g++','ON'),('device',COMPILER,'OFF')]:
            run(['cmake','-S',HERE,'-B',BUILD/mode,f'-DCMAKE_CXX_COMPILER={compiler}',f'-DOWN_RT_HOST_ONLY={host}'])
            run(['cmake','--build',BUILD/mode,'-j2'])
        flags=['-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
        links=list((BUILD/'device').rglob('link.txt'));assert links
        r['device_link_commands']={str(p.relative_to(BUILD)):p.read_text() for p in links}
        assert all(all(f in s.split() for f in flags) for s in r['device_link_commands'].values())
        cmds=read(BUILD/'device/compile_commands.json')
        assert all(all(f in row['command'].split() for f in flags) for row in cmds)
        r['precision_compile_and_link_asserted']=flags
        r['device_ldd']=run(['ldd',BUILD/'device/own-rt-iq3']).stdout;assert 'not found' not in r['device_ldd']
        dynamic=run(['readelf','-d',BUILD/'host/own-rt-iq3']).stdout
        assert not any(s in dynamic.lower() for s in ('libsycl','libze_loader','libur_loader','libopencl'))
        units={n:run([BUILD/'host'/n]).stdout for n in ('authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests')}
        for mode in ('core','parallel'):
            run([PY,'-B',HERE/'test.py','--binary',BUILD/'host/own-rt-iq3','--scratch',BUILD/f'lifetime-integration-{mode}-{time.time_ns()}',
                 '--input',BUILD/'input','--receipt',HERE/f'cpu-mini-{mode}.json','--nongemv',mode])
        cli=[]
        for seconds in (None,300,1800,0,30,299,1801):
            out=BUILD/f'lifetime-cli-{time.time_ns()}'
            cmd=[str(BUILD/'host/own-rt-iq3'),'--canary','--cards','2','--card','0','--memory','resident','--output',str(out)]
            if seconds is not None:cmd+=['--seconds',str(seconds)]
            v=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
            assert (v.returncode==0)==(seconds in (None,300,1800))
            row=dict(seconds=seconds,argv=cmd,returncode=v.returncode,stderr=v.stderr)
            if not v.returncode:
                assert 'context lifetime PASS:' in v.stderr
                row['receipt']=read(out/'receipt.json');assert row['receipt']['passed']
            cli.append(row)
        save(HERE/'deadline-native-cli-tests.json',dict(passed=True,device_executed=False,tests=cli,binary_sha256=sha(BUILD/'host/own-rt-iq3')))
        r['canary_cpu_mock']=cli[0]['receipt'];r['context_lifetime_trace']=cli[0]['stderr']
        for name in ('test_window.py','test_mismatch.py','census.py'):run([PY,'-B',HERE/name])
        run([PY,'-B',HERE/'depcheck_build.py','--source',HERE,'--tag','lifetime-sanitized'])
        for gate in ('mini','integration'):run([PY,'-B',HERE/'sanitizer_gate.py',gate,'--tag','lifetime-sanitized'])
        r['sanitizer']=dict(fresh_gates=['mini','integration'],build=read(BUILD/'lifetime-sanitized/build.json'),
                            receipts={n:sha(HERE/n) for n in ('sanitizer-mini.json','sanitizer-integration.json')},real_gates='reused; see lifetime_gate_reuse')
        previous_cpu=read(BEFORE/'cpu-tests.json')
        cpu=dict(previous_cpu,binary_sha256=sha(BUILD/'host/own-rt-iq3'),units=units,window_protocol_tests=40,
                 integration={m:read(HERE/f'cpu-mini-{m}.json') for m in ('core','parallel')},
                 lifetime_gate_reuse=r['lifetime_gate_reuse'])
        cpu.pop('deadline_only_gate_reuse',None)
        save(HERE/'cpu-tests.json',cpu)
        from math_gate import check
        from queue_gate import check as queue_check
        r['platform_math_gate']=check();r['queue_isolation_gate']=queue_check()
        assert all(Path(row['file']).resolve() in {ROOT/n for n in r['platform_math_gate']['files']} for row in cmds)
        for rel,h in protected.items():assert sha(HERE/rel)==h,rel
        assert reuse_proof()==proof
        r.update(passed=True,real_model_qualified=False,arithmetic='iq3-p17-detmath-v2',
                 artifacts_sha256={f'{m}/own-rt-iq3':sha(BUILD/m/'own-rt-iq3') for m in ('host','device')},
                 cpu_tests_sha256=sha(HERE/'cpu-tests.json'),census_sha256=sha(HERE/'census.json'),input_sha256=sha(BUILD/'input/input.json'),
                 protected_evidence_sha256=protected,build_directory_removed=False)
    finally:
        r['sources']=source_hashes()
        for name in ('LIFETIME.md','lifetime-reuse.json'):
            r['sources'][str((HERE/name).relative_to(ROOT))]=sha(HERE/name)
        r['arithmetic_sources']={n:h for n,h in r['sources'].items() if n.endswith(('.cpp','.hpp'))}
        save(HERE/'build-receipt.json',r)
    print(json.dumps(r['artifacts_sha256'],indent=2))
if __name__=='__main__':main()
