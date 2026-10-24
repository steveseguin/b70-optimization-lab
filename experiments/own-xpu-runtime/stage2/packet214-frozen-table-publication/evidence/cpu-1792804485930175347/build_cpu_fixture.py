"""Compile/run the bounded synthetic HOST_ONLY publication fixture, never native Engine."""
from pathlib import Path
import hashlib,json,os,resource,shlex,shutil,subprocess,sys,time,traceback
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'))
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
def main():
    limits();assert shutil.disk_usage(ROOT).free>=27_000_000_000+128*1024**2
    binding=P.parent/'packet210-host-cache-chunk/production-binding.json';spec=json.loads(binding.read_text());prior=P.parent/'packet213-production-prefill-control/evidence/cpu-build.json';older=json.loads(prior.read_text())
    for path,want in spec['object_sha256'].items():assert sha(path)==want,path
    for path,want in spec['source_sha256'].items():assert sha(ROOT/path)==want,path
    local=('build_cpu_fixture.py','publication_fixture.cpp','publication.hpp')
    before={str((P/f).relative_to(ROOT)):sha(P/f) for f in local}
    attempt=P/'evidence'/('cpu-'+str(time.time_ns()));attempt.mkdir(parents=True)
    for f in local:shutil.copyfile(P/f,attempt/f)
    approved=dict(json.loads((ROOT/'experiments/own-xpu-runtime/ops/packet201-window/actual-cpu-plan.json').read_text())['profile']['source_sha256']);approved.update(spec['source_sha256'])
    for plan in older['plans']:approved.update(plan['repository_dependencies'])
    approved.update(before)
    binary=P/'build/publication-fixture';binary.parent.mkdir(exist_ok=True);dep=binary.with_suffix('.d')
    command=['/usr/bin/g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-fopenmp','-DOWN_RT_HOST_ONLY','-MMD','-MF',str(dep),str(P/'publication_fixture.cpp'),*spec['object_sha256'],'-lcrypto','-o',str(binary)]
    row={'schema':'packet214.cpu-publication-build.v1','passed':False,'device_executed':False,'native_executed':False,'model_executed':False,'source_sha256':before,'parent_bindings':{str(binding.relative_to(ROOT)):sha(binding),str(prior.relative_to(ROOT)):sha(prior)},'object_sha256':spec['object_sha256'],'compile_command':command,'attempt':str(attempt.relative_to(ROOT)),'address_space_limit_bytes':4*1024**3}
    sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'));from compile_turn import turn
    sys.modules['build_engine']=sys.modules[__name__]
    try:
        with turn(),(attempt/'compile.log').open('w') as log:cp=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        row['compile_returncode']=cp.returncode;assert cp.returncode==0,'CPU compile failed'
        paths=[Path(x).resolve() for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1])];pins={}
        for path in paths:
            rel=str(path.relative_to(ROOT));digest=sha(path);assert digest==approved.get(rel),'unbound dependency '+rel;pins[rel]=digest
        row.update(repository_dependencies=pins,binary=str(binary.relative_to(ROOT)),binary_sha256=sha(binary),run_command=[str(binary)])
        for path,want in {**pins,**before}.items():assert sha(ROOT/path)==want,path
        with (attempt/'stdout.json').open('w') as out,(attempt/'stderr.log').open('w') as err:cp=subprocess.run(row['run_command'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=45)
        row['run_returncode']=cp.returncode;assert cp.returncode==0,'CPU publication fixture failed'
        proof=json.loads((attempt/'stdout.json').read_text());assert proof['passed'];row['checks']=len(proof['checks']);row['proof_sha256']=sha(attempt/'stdout.json')
        for path,want in pins.items():assert sha(ROOT/path)==want,path
        for path,want in spec['object_sha256'].items():assert sha(path)==want,path
        assert sha(binary)==row['binary_sha256'];row['passed']=True
        shutil.copyfile(attempt/'stdout.json',P/'evidence/publication-proof.json')
    except BaseException as exc:row['error']=repr(exc);(attempt/'failure.log').write_text(traceback.format_exc());raise
    finally:
        (attempt/'receipt.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
        if row['passed']:(P/'evidence/cpu-build.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'passed':True,'attempt':str(attempt),'checks':row['checks']}))
if __name__=='__main__':main()
