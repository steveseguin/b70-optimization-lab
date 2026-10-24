"""GNU-only synthetic loader test; no Device, tensor slice or real GGUF open."""
from pathlib import Path
import hashlib,json,os,resource,shlex,shutil,subprocess,sys,time,traceback,unittest
import prepare_overlay as O
import prepare_inputs as I
P=O.P;ROOT=O.ROOT;sha=O.sha
SOURCES=('prepare_overlay.py','prepare_inputs.py','probe.cpp','test_loader.py','build_cpu.py','parent-pins.json')

def limits():
    if os.getpriority(os.PRIO_PROCESS,0)!=19 or not set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)):raise ValueError('helper placement')
    if not all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS')):raise ValueError('threads')
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    if shutil.disk_usage(ROOT).free<25_000_000_000+40*1024**2:raise ValueError('disk floor')

def main():
    limits()
    if (P/'cpu-proof.json').exists():raise ValueError('proof already exists; no replay')
    attempt=P/'evidence'/('cpu-'+str(time.time_ns()));attempt.mkdir(parents=True)
    before={n:sha(P/n) for n in SOURCES}
    for n in SOURCES:shutil.copyfile(P/n,attempt/n)
    result={'schema':'ownrt.gsq.loader-cpu.v1','passed':False,'native_admitted':False,'device_executed':False,'numeric_execution':False,'real_model_header_bytes_read':0,'real_model_payload_bytes_read':0,'source_sha256':before,'attempt':str(attempt.relative_to(P)),'compiler_sha256':sha('/usr/bin/g++')}
    try:
        overlay=O.prepare();result['overlay']=overlay;result['inputs']=I.prepare()
        private=P/'build/private';commands=[]
        for name,source in [('probe',P/'probe.cpp'),('gguf',private/'gguf.cpp')]:
            commands.append(['/usr/bin/g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-ffunction-sections','-fdata-sections','-I',str(private),'-MMD','-MF',str(P/f'build/{name}.d'),'-c',str(source),'-o',str(P/f'build/{name}.o')])
        binary=P/'build/loader-probe'
        commands.append(['/usr/bin/g++','-Wl,--gc-sections',str(P/'build/probe.o'),str(P/'build/gguf.o'),'-o',str(binary)])
        result['commands']=commands
        sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'));from compile_turn import turn
        sys.modules['build_engine']=sys.modules[__name__]
        with turn(),(attempt/'compile.log').open('w') as log:
            for command in commands:
                ran=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=120)
                if ran.returncode:raise RuntimeError('GNU compile/link failed')
        dependencies={};approved={str((private/name).relative_to(ROOT)):digest for name,digest in overlay['private_sha256'].items()};approved[str((P/'probe.cpp').relative_to(ROOT))]=before['probe.cpp']
        for dep in (P/'build').glob('*.d'):
            for word in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):
                path=Path(word).resolve();name=str(path.relative_to(ROOT));digest=sha(path)
                if approved.get(name)!=digest:raise ValueError('compiler dependency not admitted '+name)
                dependencies[name]=digest
        result['repository_dependencies']=dependencies;result['binary_sha256']=sha(binary)
        result['object_sha256']={name:sha(P/'build'/name) for name in ('probe.o','gguf.o')}
        with (attempt/'tests.log').open('w') as log:
            tests=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.discover(str(P),pattern='test_loader.py'))
        result['tests']=tests.testsRun
        if not tests.wasSuccessful():raise RuntimeError('loader tests failed')
        I.verify_pins()
        for name,digest in before.items():
            if sha(P/name)!=digest:raise ValueError('executed source changed')
        for name,digest in dependencies.items():
            if sha(ROOT/name)!=digest:raise ValueError('compiler input changed')
        if sha(binary)!=result['binary_sha256'] or sha('/usr/bin/g++')!=result['compiler_sha256']:raise ValueError('binary/compiler changed')
        result['passed']=True
    except BaseException as exc:
        result['error']=repr(exc);(attempt/'failure.log').write_text(traceback.format_exc());raise
    finally:
        for name in ('loader-probe','probe.o','gguf.o','probe.d','gguf.d'):
            source=P/'build'/name
            if source.exists():
                target=P/'build'/attempt.name;target.mkdir(exist_ok=True);shutil.copyfile(source,target/name)
        result['artifact_sha256']={str(f.relative_to(P)):sha(f) for f in [*(P/name for name in ('placement.tsv','shard-auth.tsv','inputs.json','overlay.patch','p195-loader.patch','overlay.json')),*attempt.iterdir()] if f.is_file()}
        (attempt/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
        if result['passed']:(P/'cpu-proof.json').write_text(json.dumps(result,indent=2)+'\n')
    size=sum(f.stat().st_size for f in P.rglob('*') if f.is_file())
    if size>40*1024**2:raise ValueError('artifact budget')
    print(json.dumps({'passed':True,'tests':result['tests'],'bytes':size,'input_summary':result['inputs']['bytes_card0_card1_host']}))

if __name__=='__main__':main()
