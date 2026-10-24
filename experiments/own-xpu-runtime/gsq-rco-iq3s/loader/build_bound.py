"""One bounded GNU proof of the newly added immutable authority/read seam."""
from pathlib import Path
import hashlib,json,os,shlex,shutil,subprocess,sys,tempfile,time,traceback
from build_cpu import limits
import prepare_inputs as I
P=I.P;ROOT=I.ROOT;sha=I.sha

def main():
    limits();I.verify_pins()
    if (P/'bound-proof.json').exists():raise ValueError('proof already exists')
    bound=json.loads((P/'bound-authority.json').read_text())
    for name,digest in bound['source_sha256'].items():
        if sha(P/name)!=digest:raise ValueError('bound generator source drift')
    if sha(P/'bound.hpp')!=bound['bound_header_sha256']:raise ValueError('bound header drift')
    attempt=P/'evidence'/('bound-'+str(time.time_ns()));attempt.mkdir()
    sources={n:sha(P/n) for n in ('bound.hpp','bound_test.cpp','build_bound.py','bound-authority.json','build_cpu.py')}
    for name in sources:shutil.copyfile(P/name,attempt/name)
    result={'schema':'ownrt.gsq.bound-loader-cpu.v1','passed':False,'native_admitted':False,'model_reads':0,'source_sha256':sources,'attempt':str(attempt.relative_to(P)),'compiler_sha256':sha('/usr/bin/g++')}
    try:
        binary=P/'build/bound-test';dep=P/'build/bound-test.d'
        command=['/usr/bin/g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-I',str(P/'build/private'),'-MMD','-MF',str(dep),str(P/'bound_test.cpp'),'-o',str(binary)]
        result['compile_command']=command
        sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'));from compile_turn import turn
        sys.modules['build_engine']=sys.modules[__name__]
        with turn(),(attempt/'compile.log').open('w') as log:
            run=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        if run.returncode:raise RuntimeError('bound fixture compile failed')
        dependencies={}
        approved={str((P/'build/private'/n).relative_to(ROOT)):d for n,d in json.loads((P/'overlay.json').read_text())['private_sha256'].items()}
        approved.update({str((P/n).relative_to(ROOT)):sources[n] for n in ('bound.hpp','bound_test.cpp')})
        for word in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):
            path=Path(word).resolve();name=str(path.relative_to(ROOT));digest=sha(path)
            if approved.get(name)!=digest:raise ValueError('unexpected fixture dependency')
            dependencies[name]=digest
        result['repository_dependencies']=dependencies;result['binary_sha256']=sha(binary)
        with tempfile.TemporaryDirectory(prefix='gsq-bound-') as temp:
            command=[str(binary),temp];result['run_command']=command
            run=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
        (attempt/'stdout.log').write_text(run.stdout);(attempt/'stderr.log').write_text(run.stderr)
        if run.returncode:raise RuntimeError('bound fixture failed')
        proof=json.loads(run.stdout);assert proof['passed'];result['proof']=proof
        for n,d in sources.items():
            if sha(P/n)!=d:raise ValueError('source drift')
        for n,d in dependencies.items():
            if sha(ROOT/n)!=d:raise ValueError('dependency drift')
        if sha(binary)!=result['binary_sha256'] or sha('/usr/bin/g++')!=result['compiler_sha256']:raise ValueError('binary/compiler drift')
        result['passed']=True
    except BaseException as e:
        result['error']=repr(e);(attempt/'failure.log').write_text(traceback.format_exc());raise
    finally:
        result['artifact_sha256']={str(f.relative_to(P)):sha(f) for f in attempt.iterdir() if f.is_file()}
        (attempt/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
        if result['passed']:(P/'bound-proof.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['proof']))

if __name__=='__main__':main()
