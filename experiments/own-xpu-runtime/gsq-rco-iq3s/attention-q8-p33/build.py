#!/usr/bin/env python3
"""Bounded CPU proof or single native entry compile/link; no native invocation."""
import argparse,hashlib,importlib.util,json,os,resource,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parent;R=P.parents[3]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,m):
    if not v:raise ValueError(m)
def limits():
    require(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement')
    require(all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')),'two helper threads')
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    require(shutil.disk_usage(R).free>=27000000000+250*1024**2,'root floor plus250MiB forecast')
def admission():
    spec=importlib.util.spec_from_file_location('attention_prepare',P/'prepare.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    old=m.control();prep=json.loads((P/'preparation.json').read_text())
    for f,h in prep['source_sha256'].items():require(sha(f)==h,'prepared source changed')
    require(m.reuse(old)==prep['objects'],'per-TU reuse dependencies changed')
    return old,prep
def recipe(mode,d,old,prep):
    source=Path(prep['materialized_directory']);native=mode=='native'
    if native:
        cmd=list(old['commands'][0]);cmd[cmd.index('-c')+1]=str(source/'entry.cpp');cmd[cmd.index('-o')+1]=str(d/'entry.o');cmd[cmd.index('-MF')+1]=str(d/'entry.d')
        link=list(old['commands'][-1]);link[link.index(old['commands'][0][-1])]=str(d/'entry.o');link[link.index('-o')+1]=str(d/'gsq-engine')
        return [cmd,link],d/'gsq-engine'
    binary=d/'cpu-proof';return [['/usr/bin/g++','-std=gnu++20','-O2','-g0','-fno-fast-math','-ffp-contract=off','-DHOST_ONLY','-DOWN_RT_HOST_ONLY','-I'+str(source),'-MMD','-MF',str(d/'fixture.d'),str(P/'fixture.cpp'),'-o',str(binary)],[str(binary)]],binary
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('cpu','native'),required=True);g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--build',action='store_true');a=ap.parse_args()
    old,prep=admission();d=P/'build'/('preview-'+a.mode if a.plan else a.mode+'-'+str(time.time_ns()));commands,binary=recipe(a.mode,d,old,prep)
    if a.plan:print(json.dumps(dict(mode=a.mode,commands=commands,compiler_invoked=False,objects_reused=39 if a.mode=='native' else 0),indent=2));return
    limits()
    if a.mode=='native':
        cpu=json.loads((P/'evidence/cpu-proof.json').read_text());scales=json.loads((P/'evidence/scale-census.json').read_text())
        require(cpu['passed'] and cpu['proof']['passed'] and scales['passed'] and scales['all_scales_finite'],'CPU exactness/actual scale census prerequisites')
        require(cpu['preparation_sha256']==scales['preparation_sha256']==sha(P/'preparation.json'),'prerequisite source identity')
        require(sha(commands[0][0])==old['compiler_sha256'],'same native compiler required')
    d.mkdir(parents=True);pins=dict(old['source_sha256'])
    for f,h in prep['source_sha256'].items():pins[str(Path(f).relative_to(R))]=h
    for f in [P/'build.py',P/'fixture.cpp',P/'preparation.json',P/'control-pins.json',P/'scale_census.py']:
        pins[str(f.relative_to(R))]=sha(f);shutil.copy2(f,d/f.name)
    turnpath=R/'experiments/own-xpu-runtime/ops/compile_turn.py';pins[str(turnpath.relative_to(R))]=sha(turnpath)
    sys.modules['build_engine']=sys.modules[__name__];spec=importlib.util.spec_from_file_location('attention_compile_turn',turnpath);turn=importlib.util.module_from_spec(spec);spec.loader.exec_module(turn)
    receipt=dict(passed=False,mode=a.mode,commands=commands,binary=str(binary),source_sha256=pins,compiler_sha256=sha(commands[0][0]),preparation_sha256=sha(P/'preparation.json'),native_binary_invoked=False,objects_reused=39 if a.mode=='native' else 0)
    try:
        for i,cmd in enumerate(commands):
            with turn.turn(),(d/f'command-{i}.log').open('x') as log:
                r=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,cwd=R,timeout=1200 if a.mode=='native' else 180)
            require(r.returncode==0,'command failed '+str(i))
        deps={}
        for f in d.glob('*.d'):
            for name in f.read_text().replace('\\\n',' ').split(':',1)[1].split():
                path=Path(name).resolve();key=str(path.relative_to(R));require(pins.get(key)==sha(path),'unbound new compiler dependency '+key);deps[key]=sha(path)
        receipt['dependencies']=deps;receipt['binary_sha256']=sha(binary)
        if a.mode=='cpu':receipt['proof']=json.loads((d/'command-1.log').read_text());require(receipt['proof']['passed'],'CPU arithmetic mismatch')
        else:
            receipt['object_sha256']={r['object']:r['object_sha256'] for r in prep['objects'] if r['reuse']};receipt['object_sha256'][str(d/'entry.o')]=sha(d/'entry.o')
            receipt['reused_object_provenance']=prep['objects'];receipt['control_compilation_receipt_sha256']=sha(L/'integration/evidence/full-native-build.json')
            symbols=subprocess.check_output(['/usr/bin/nm','-C','--defined-only',str(binary)],text=True,timeout=60);(d/'symbols.log').write_text(symbols)
            require('packet26_model_entry' in symbols and 'p33::submit' in symbols and 'mtp36::DraftRuntime' in symbols,'native integrated symbols')
            compiler=Path('/opt/intel/oneapi/compiler/2026.0/bin/compiler');bundler=str(compiler/'clang-offload-bundler');obj=d/'entry.o'
            targets=subprocess.check_output([bundler,'-type=o','-list','-input='+str(obj)],text=True,timeout=60).splitlines();target=[x for x in targets if x.startswith('sycl-spir64')];require(len(target)==1,'one entry device image')
            bc=d/'entry-device.bc';subprocess.run([bundler,'-type=o','-unbundle','-targets='+target[0],'-input='+str(obj),'-output='+str(bc)],check=True,timeout=120)
            subprocess.run([str(compiler/'sycl-post-link'),'-symbols','-split=source','-o',str(d/'kernel.table'),str(bc)],check=True,timeout=120)
            entries='\n'.join(f.read_text() for f in d.glob('kernel*.sym'));(d/'kernel-entries.log').write_text(entries)
            for t in (12,13,18,23,42):require('PackedKernelILj'+str(t)+'E' in entries,'unchanged generic format entry')
            receipt['offline']={'entry_device_sha256':sha(bc),'kernel_entries_sha256':sha(d/'kernel-entries.log'),'symbols_sha256':sha(d/'symbols.log'),'p33_object_reused_unchanged':True}
            receipt['prerequisite_sha256']={str(P/'evidence'/n):sha(P/'evidence'/n) for n in ('cpu-proof.json','scale-census.json')}
        admission()
        for f,h in pins.items():require(sha(R/f)==h,'final source drift '+f)
        require(sha(commands[0][0])==receipt['compiler_sha256'],'compiler drift');receipt['passed']=True
        dest=P/'evidence'/('native-build.json' if a.mode=='native' else 'cpu-proof.json');dest.parent.mkdir(exist_ok=True)
        with dest.open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
    except BaseException as e:receipt['error']=repr(e);raise
    finally:(d/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'passed':True,'mode':a.mode,'receipt':str(dest),'receipt_sha256':sha(dest)}))
if __name__=='__main__':main()
