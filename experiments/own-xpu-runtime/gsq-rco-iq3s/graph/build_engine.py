"""Compile/run only the metadata graph bridge under bounded GNU CPU limits."""
from pathlib import Path
import hashlib,json,os,resource,shlex,shutil,subprocess,sys,time,traceback,unittest
import prepare_overlay as O
import bridge as B
P=O.P;ROOT=O.ROOT
sha=O.sha
SOURCES=('prepare_overlay.py','bridge.py','bridge.cpp','build_engine.py','test_bridge.py','parent-pins.json')


def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'))
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    assert shutil.disk_usage(ROOT).free>=25_000_000_000+40*1024**2


def main():
    limits()
    if any((P/n).exists() for n in ('build-receipt.json','new-plan.json','old-plan.json')):
        raise ValueError('exclusive graph attempt outputs already exist')
    attempt=P/'evidence'/('cpu-'+str(time.time_ns()));attempt.mkdir(parents=True)
    before={n:sha(P/n) for n in SOURCES}
    for n in SOURCES:shutil.copyfile(P/n,attempt/n)
    result={'schema':'ownrt.gsq-rco.graph-cpu.v1','passed':False,'native_admitted':False,'device_executed':False,'numeric_execution':False,'source_sha256':before,'attempt':str(attempt.relative_to(P)),'compiler_sha256':sha('/usr/bin/g++')}
    try:
        overlay=O.overlay();result['overlay']=overlay
        old,new,roles=B.pinned_inputs()
        oldrows,newrows=B.admit(old,old,roles),B.admit(new,new,roles)
        B.export(oldrows,P/'old-directory.tsv');B.export(newrows,P/'new-directory.tsv')
        binary=P/'build/graph-bridge';dep=P/'build/graph-bridge.d'
        command=['/usr/bin/g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-MMD','-MF',str(dep),str(P/'bridge.cpp'),'-o',str(binary)]
        result['compile_command']=command
        sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'));from compile_turn import turn
        sys.modules['build_engine']=sys.modules[__name__]
        with turn(),(attempt/'compile.log').open('w') as log:
            compiled=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        result['compile_returncode']=compiled.returncode
        if compiled.returncode:raise RuntimeError('GNU graph compile failed')
        approved=dict(overlay['private_sha256']);approved[str((P/'bridge.cpp').relative_to(ROOT))]=before['bridge.cpp']
        dependencies={}
        for word in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):
            path=Path(word).resolve();name=str(path.relative_to(ROOT));actual=sha(path)
            if approved.get(name)!=actual:raise ValueError('unbound compiler dependency: '+name)
            dependencies[name]=actual
        result['repository_dependencies']=dependencies;result['binary_sha256']=sha(binary)
        for label,rows in [('old',oldrows),('new',newrows)]:
            directory=P/(label+'-directory.tsv')
            cmd=[str(binary),str(directory),str(directory),'4096']
            with (P/(label+'-plan.json')).open('x') as out,(attempt/(label+'-stderr.log')).open('w') as err:
                ran=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=20)
            result[label+'_command']=cmd
            if ran.returncode:raise RuntimeError(label+' graph refused')
        a,b=B.read(P/'old-plan.json'),B.read(P/'new-plan.json')
        result['topology_identical']=B.same_topology(a,b)
        oldaccount,newaccount=B.validate_graph(a,oldrows),B.validate_graph(b,newrows)
        (P/'accounting.json').write_text(json.dumps({'context':4096,'old':oldaccount,'new':newaccount},indent=2)+'\n')
        with (attempt/'tests.log').open('w') as log:
            suite=unittest.defaultTestLoader.discover(str(P),pattern='test_bridge.py')
            tests=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
        result['tests']=tests.testsRun
        if not tests.wasSuccessful():raise RuntimeError('graph admission tests failed')
        for name,want in before.items():
            if sha(P/name)!=want:raise ValueError('source drift')
        B.pinned_inputs()
        for name,want in dependencies.items():
            if sha(ROOT/name)!=want:raise ValueError('dependency drift')
        if sha(binary)!=result['binary_sha256'] or sha('/usr/bin/g++')!=result['compiler_sha256']:raise ValueError('binary/compiler drift')
        result.update(passed=True,launches=b['launch_count'],buffers=len(b['buffers']),tensor_count=len(newrows),per_card=newaccount['per_card'],host_file_backed_bytes=newaccount['host_file_backed_bytes'])
    except BaseException as exc:
        result['error']=repr(exc);(attempt/'failure.log').write_text(traceback.format_exc());raise
    finally:
        outputs=['overlay.patch','overlay.json','old-directory.tsv','new-directory.tsv','old-plan.json','new-plan.json','accounting.json']
        result['artifact_sha256']={str(f.relative_to(P)):sha(f) for f in [*(P/n for n in outputs),*attempt.iterdir()] if f.is_file()}
        (attempt/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
        if result['passed']:(P/'build-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    total=sum(p.stat().st_size for p in P.rglob('*') if p.is_file())
    if total>=40*1024**2:raise ValueError('artifact budget exceeded')
    print(json.dumps({'passed':True,'tests':result['tests'],'launches':result['launches'],'buffers':result['buffers'],'bytes_written':total,'per_card':result['per_card']}))


if __name__=='__main__':main()
