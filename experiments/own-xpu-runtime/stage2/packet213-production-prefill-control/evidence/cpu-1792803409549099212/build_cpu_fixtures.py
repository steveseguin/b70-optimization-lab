"""Bounded synthetic CPU fixtures only; never invokes the production native executable."""
from pathlib import Path
import hashlib,json,os,resource,shlex,shutil,subprocess,sys,time,traceback
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
P212=P.parent/'packet212-production-prefill-integration';P210=P.parent/'packet210-host-cache-chunk'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'))
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
def main():
    limits();assert shutil.disk_usage(ROOT).free>=27_000_000_000+128*1024**2
    spec=json.loads((P210/'production-binding.json').read_text());old=json.loads((P212/'evidence/schedule-build.json').read_text())
    for path,want in spec['object_sha256'].items():assert sha(path)==want,path
    for path,want in spec['source_sha256'].items():assert sha(ROOT/path)==want,path
    fixture=Path(old['fixture']);assert sha(fixture)==old['fixture_sha256']
    local=['build_cpu_fixtures.py','production_control.hpp','cache_transition.hpp','schedule_control_fixture.cpp','cache_transition_fixture.cpp']
    before={str((P/f).relative_to(ROOT)):sha(P/f) for f in local}
    attempt=P/'evidence'/('cpu-'+str(time.time_ns()));attempt.mkdir(parents=True)
    for f in local:shutil.copyfile(P/f,attempt/f)
    shutil.copyfile(fixture,attempt/'schedule-inputs.tsv')
    receipt={'schema':'packet213.cpu-fixtures-build.v1','passed':False,'device_executed':False,'model_executed':False,'native_executed':False,'address_space_limit_bytes':4*1024**3,'source_sha256':before,'parent_bindings':{str((P210/'production-binding.json').relative_to(ROOT)):sha(P210/'production-binding.json'),str((P212/'evidence/schedule-build.json').relative_to(ROOT)):sha(P212/'evidence/schedule-build.json')},'plans':[],'attempt':str(attempt.relative_to(ROOT))}
    approved=dict(json.loads((ROOT/'experiments/own-xpu-runtime/ops/packet201-window/actual-cpu-plan.json').read_text())['profile']['source_sha256']);approved.update(spec['source_sha256']);approved.update(old['repository_dependencies']);approved.update(before)
    sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'));from compile_turn import turn
    sys.modules['build_engine']=sys.modules[__name__]
    try:
        for name,source,objects,args in [('schedule','schedule_control_fixture.cpp',{},[str(attempt/'schedule-inputs.tsv')]),('transition','cache_transition_fixture.cpp',spec['object_sha256'],[])]:
            binary=P/'build'/f'{name}-fixture';binary.parent.mkdir(exist_ok=True);dep=binary.with_suffix('.d')
            command=['/usr/bin/g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-MMD','-MF',str(dep)]
            if objects:command+=['-fopenmp','-DOWN_RT_HOST_ONLY']
            command +=[str(P/source),*objects,*(['-lcrypto'] if objects else []),'-o',str(binary)]
            plan={'name':name,'compile_command':command,'object_sha256':objects};receipt['plans'].append(plan)
            with turn(),(attempt/f'{name}-compile.log').open('w') as log:cp=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=180)
            plan['compile_returncode']=cp.returncode;assert cp.returncode==0,f'{name} compile failed'
            paths=[Path(x).resolve() for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1])];pins={}
            for path in paths:
                rel=str(path.relative_to(ROOT));digest=sha(path);assert digest==approved.get(rel),'unbound dependency '+rel;pins[rel]=digest
            plan.update(repository_dependencies=pins,binary=str(binary.relative_to(ROOT)),binary_sha256=sha(binary),run_command=[str(binary),*args])
            for path,want in {**pins,**before,**spec['source_sha256']}.items():assert sha(ROOT/path)==want,path
            with (attempt/f'{name}-stdout.json').open('w') as out,(attempt/f'{name}-stderr.log').open('w') as err:cp=subprocess.run(plan['run_command'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=30)
            plan['run_returncode']=cp.returncode;assert cp.returncode==0,f'{name} fixture failed'
            proof=json.loads((attempt/f'{name}-stdout.json').read_text());assert proof['passed'];plan['checks']=len(proof['checks']);plan['proof_sha256']=sha(attempt/f'{name}-stdout.json')
            for path,want in pins.items():assert sha(ROOT/path)==want,path
            for path,want in objects.items():assert sha(path)==want,path
            assert sha(binary)==plan['binary_sha256']
        receipt['passed']=True
        for plan in receipt['plans']:shutil.copyfile(attempt/f"{plan['name']}-stdout.json",P/'evidence'/f"{plan['name']}-proof.json")
    except BaseException as exc:receipt['error']=repr(exc);(attempt/'failure.log').write_text(traceback.format_exc());raise
    finally:
        (attempt/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
        if receipt['passed']:(P/'evidence/cpu-build.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'passed':True,'attempt':str(attempt),'checks':{p['name']:p['checks'] for p in receipt['plans']}}))
if __name__=='__main__':main()
