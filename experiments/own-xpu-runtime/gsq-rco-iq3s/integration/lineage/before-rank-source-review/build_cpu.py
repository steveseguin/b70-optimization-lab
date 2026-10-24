#!/usr/bin/env python3
"""GNU entry syntax/object gate and shared actual-plan preflight. No device run."""
import argparse,hashlib,importlib.util,json,os,resource,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parents[3]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32))
    assert all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    assert shutil.disk_usage(R).free>=27_000_000_000+250*1024**2
def commands(attempt):
    prepared=json.loads((P/'preparation.json').read_text());entry=Path(prepared['entry'])
    loader=P/'build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet2/loader/gguf.cpp'
    flags=['/usr/bin/g++','-std=gnu++20','-O1','-g0','-fopenmp','-DOWN_RT_HOST_ONLY','-fno-fast-math','-ffp-contract=off','-ffunction-sections','-fdata-sections','-Werror=return-type']
    compile=[]
    for name,source in [('entry',entry),('preflight',P/'preflight.cpp'),('loader',loader)]:
        compile.append(flags+['-MMD','-MF',str(attempt/(name+'.d')),'-c',str(source),'-o',str(attempt/(name+'.o'))])
    compile.append(['/usr/bin/g++','-fopenmp','-Wl,--gc-sections',str(attempt/'preflight.o'),str(attempt/'loader.o'),'-lcrypto','-o',str(attempt/'preflight')])
    return compile
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--plan',action='store_true');ap.add_argument('--build',action='store_true');ap.add_argument('--synthetic',action='store_true');a=ap.parse_args()
    assert a.plan!=a.build and (not a.synthetic or a.build)
    if a.plan:print(json.dumps({'commands':commands(P/'build/preview'),'model_reads':False,'device_actions':False},indent=2));return
    limits();prepared=json.loads((P/'preparation.json').read_text())
    pins={**prepared['source_sha256'],**prepared['private_sha256']}
    for f in ('prepare.py','generic_engine.hpp','generic_host.hpp','preflight.cpp','build_cpu.py','preparation.json','overlay.patch'):pins[str((P/f).relative_to(R))]=sha(P/f)
    turnpath=R/'experiments/own-xpu-runtime/ops/compile_turn.py';pins[str(turnpath.relative_to(R))]=sha(turnpath)
    for path,want in pins.items():assert sha(R/path)==want,path
    attempt=P/'build'/('cpu-'+str(time.time_ns()));attempt.mkdir(parents=True)
    for f in ('prepare.py','generic_engine.hpp','generic_host.hpp','preflight.cpp','build_cpu.py','preparation.json','overlay.patch'):shutil.copy2(P/f,attempt/f)
    shutil.copytree(P/'build/private',attempt/'private-snapshot')
    receipt={'passed':False,'source_sha256':pins,'commands':commands(attempt),'device_executed':False,'model_payload_read':False,'real_headers_read':False,'compiler_sha256':sha('/usr/bin/g++'),'attempt':str(attempt.relative_to(R))}
    sys.modules['build_engine']=sys.modules[__name__]
    spec=importlib.util.spec_from_file_location('gsq_integration_compile_turn',turnpath);turn=importlib.util.module_from_spec(spec);spec.loader.exec_module(turn)
    try:
        for i,cmd in enumerate(receipt['commands']):
            with turn.turn(),(attempt/f'compile-{i}.log').open('w') as log:
                result=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=240,cwd=R)
            if result.returncode:raise RuntimeError('GNU command failed '+str(i))
        deps={}
        for f in attempt.glob('*.d'):
            for path in f.read_text().replace('\\\n',' ').split(':',1)[1].split():
                path=Path(path).resolve();rel=str(path.relative_to(R));digest=sha(path)
                assert pins.get(rel)==digest,'unbound dependency '+str(path);deps[rel]=digest
        receipt['dependencies']=deps;receipt['binary_sha256']=sha(attempt/'preflight');receipt['entry_object_sha256']=sha(attempt/'entry.o')
        if a.synthetic:
            with (attempt/'synthetic.stdout').open('w') as out,(attempt/'synthetic.stderr').open('w') as err:
                result=subprocess.run([str(attempt/'preflight'),'--synthetic'],stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=30)
            if result.returncode:raise RuntimeError('synthetic preflight failed')
            receipt['synthetic']=json.loads((attempt/'synthetic.stdout').read_text());assert receipt['synthetic']['passed']
        for path,want in pins.items():assert sha(R/path)==want,path
        assert sha('/usr/bin/g++')==receipt['compiler_sha256'];receipt['passed']=True
        evidence=P/'evidence';evidence.mkdir(exist_ok=True);target=evidence/'cpu-build.json';assert not target.exists();target.write_text(json.dumps(receipt,indent=2)+'\n')
    except BaseException as e:receipt['error']=type(e).__name__+': '+str(e);raise
    finally:(attempt/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'passed':True,'attempt':str(attempt),'binary':str(attempt/'preflight')}))
if __name__=='__main__':main()
