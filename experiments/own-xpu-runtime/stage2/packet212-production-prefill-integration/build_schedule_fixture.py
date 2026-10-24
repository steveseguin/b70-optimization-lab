"""Compile/run only a pure CPU metadata selector; never link or launch the runtime."""
from pathlib import Path
import hashlib
import json
import os
import resource
import shlex
import subprocess
import sys
import time
import traceback

P=Path(__file__).resolve().parent
ROOT=P.parents[3]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert all(os.environ.get(x)=='2' for x in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))

def run():
    limits()
    assert __import__('shutil').disk_usage(ROOT).free>=27_000_000_000+32*1024**2
    import prepare_fixture
    actual=prepare_fixture.extract();expected=json.loads((P/'schedule-inputs.json').read_text());assert actual==expected,'retained fixture drift'
    attempt=P/'evidence'/('schedule-'+str(time.time_ns()));attempt.mkdir(parents=True)
    local=('production_schedule.hpp','schedule_fixture.cpp','prepare_fixture.py','schedule-inputs.json','build_schedule_fixture.py')
    pins={str((P/name).relative_to(ROOT)):sha(P/name) for name in local}
    for name in local:(attempt/name).write_bytes((P/name).read_bytes())
    rows=[]
    for site in expected['sites']:
        assert site['card']==0
        t=site.get('projection')
        tail=[t['name'],{14:'Q6_K',8:'Q8_0'}[t['type_code']],t['rows'],t['columns'],t['stored_bytes'],t['variant']] if t else ['-','-',0,0,0,0]
        row=[site['index'],site['label'],site['op'],site['recorded_prepared_commands'],*tail]
        assert all('\t' not in str(x) and '\n' not in str(x) for x in row)
        rows.append('\t'.join(map(str,row)))
    fixture=attempt/'schedule-inputs.tsv';fixture.write_text('\n'.join(rows)+'\n')
    out=P/'build/schedule-fixture';out.parent.mkdir(parents=True,exist_ok=True);dep=out.with_suffix('.d')
    command=['/usr/bin/g++','-std=c++20','-O2','-MMD','-MF',str(dep),str(P/'schedule_fixture.cpp'),'-o',str(out)]
    receipt={'schema':'packet212.schedule-fixture-build.v1','passed':False,'runtime_executed':False,'device_executed':False,'model_executed':False,'source_sha256':pins,'input_sources_sha256':expected['source_sha256'],'compile_command':command,'fixture_sha256':sha(fixture),'fixture':str(fixture),'attempt':str(attempt)}
    sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'))
    from compile_turn import turn
    sys.modules['build_engine']=sys.modules[__name__]
    try:
        with turn(),(attempt/'compile.log').open('w') as log:
            cp=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=90)
        receipt['compile_returncode']=cp.returncode
        assert cp.returncode==0,'pure schedule compile failed'
        paths=[Path(x).resolve() for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1])]
        assert set(paths)=={P/'production_schedule.hpp',P/'schedule_fixture.cpp'},paths
        receipt['repository_dependencies']={str(x.relative_to(ROOT)):sha(x) for x in paths}
        receipt['binary_sha256']=sha(out);receipt['binary']=str(out)
        command=[str(out),str(fixture)];receipt['run_command']=command
        with (attempt/'stdout.json').open('w') as stdout,(attempt/'stderr.log').open('w') as stderr:
            cp=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,timeout=30)
        receipt['run_returncode']=cp.returncode
        assert cp.returncode==0,'pure schedule fixture failed'
        proof=json.loads((attempt/'stdout.json').read_text());assert proof['passed'] and not proof['runtime_executed']
        for name,want in pins.items():assert sha(ROOT/name)==want,name
        receipt['passed']=True;receipt['proof_sha256']=sha(attempt/'stdout.json')
        (P/'evidence/schedule-proof.json').write_bytes((attempt/'stdout.json').read_bytes())
    except BaseException as exc:
        receipt['error']=repr(exc)
        (attempt/'failure.log').write_text(traceback.format_exc())
        raise
    finally:
        (attempt/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
        if receipt['passed']:(P/'evidence/schedule-build.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'passed':True,'checks':len(proof['checks']),'proof_sha256':receipt['proof_sha256'],'attempt':str(attempt)}))

if __name__=='__main__':run()
