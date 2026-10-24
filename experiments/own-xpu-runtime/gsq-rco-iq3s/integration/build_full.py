#!/usr/bin/env python3
"""Explicit all-source GNU/SYCL rebuild. No binary invocation at any point."""
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
def plan(mode,attempt):
    prep=json.loads((P/'preparation.json').read_text());native=mode=='native'
    compiler='/opt/intel/oneapi/compiler/2026.0/bin/icpx' if native else '/usr/bin/g++'
    flags=[compiler,'-std=gnu++20','-O2','-g0','-DP56X_SLEEP20=0','-Werror=return-type','-fno-fast-math','-ffp-contract=off','-ffunction-sections','-fdata-sections']
    flags+=['-fsycl','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-Werror=deprecated-this-capture'] if native else ['-DOWN_RT_HOST_ONLY','-fopenmp','-I'+str(P/'host-support')]
    sources={'entry':str((P/'native_main.cpp').relative_to(R)),**prep['full_rebuild_translation_units']}
    if not native:
        for n in ('packet194-expert-diet-engine/native.cpp','packet194-expert-diet-engine/single_device.cpp','packet2/kernels/device.cpp',*(f'packet{i}-{label}/kernels.cpp' for i,label in ((6,'kopt'),(7,'kopt2'),(8,'kopt3'),(9,'kopt4'),(10,'kopt5')))):sources.pop(n)
    commands=[];objects=[]
    for i,(name,path) in enumerate(sources.items()):
        obj=attempt/(str(i)+'.o');objects.append(str(obj));commands.append(flags+['-MMD','-MF',str(attempt/(str(i)+'.d')),'-c',str(R/path),'-o',str(obj)])
    link=[compiler,*(['-fsycl'] if native else ['-fopenmp']),'-Wl,--gc-sections',*objects,'-lcrypto','-o',str(attempt/'gsq-engine')]
    if native:link+=['-lze_loader','-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib:/usr/lib/x86_64-linux-gnu']
    return {'mode':mode,'sources':sources,'commands':commands+[link],'objects_reused':0,'binary':str(attempt/'gsq-engine'),'device_executed':False,'binary_invoked':False}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('host','native'),required=True);ap.add_argument('--plan',action='store_true');ap.add_argument('--build',action='store_true');a=ap.parse_args();assert a.plan!=a.build
    if a.plan:print(json.dumps(plan(a.mode,P/'build'/('full-'+a.mode+'-preview')),indent=2));return
    limits();prep=json.loads((P/'preparation.json').read_text());pins={**prep['source_sha256'],**prep['private_sha256']}
    for name in ('native_main.cpp','build_full.py','preparation.json','prepare.py','host-support/device_validation.hpp'):pins[str((P/name).relative_to(R))]=sha(P/name)
    path=R/'experiments/own-xpu-runtime/ops/compile_turn.py';pins[str(path.relative_to(R))]=sha(path)
    for f,h in pins.items():assert sha(R/f)==h,f
    attempt=P/'build'/('full-'+a.mode+'-'+str(time.time_ns()));attempt.mkdir(parents=True);receipt=plan(a.mode,attempt);receipt.update(passed=False,source_sha256=pins,compiler_sha256=sha(receipt['commands'][0][0]))
    for name in ('native_main.cpp','build_full.py','preparation.json','prepare.py'):shutil.copy2(P/name,attempt/name)
    shutil.copytree(P/'build/private',attempt/'private-snapshot')
    sys.modules['build_engine']=sys.modules[__name__];spec=importlib.util.spec_from_file_location('full_compile_turn',path);turn=importlib.util.module_from_spec(spec);spec.loader.exec_module(turn)
    try:
        for i,cmd in enumerate(receipt['commands']):
            with turn.turn(),(attempt/f'command-{i}.log').open('w') as log:
                result=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=1200 if a.mode=='native' else 300,cwd=R)
            if result.returncode:raise RuntimeError('full compile command failed '+str(i))
        deps={}
        for f in attempt.glob('*.d'):
            for name in f.read_text().replace('\\\n',' ').split(':',1)[1].split():
                path=Path(name).resolve();rel=str(path.relative_to(R));digest=sha(path);assert pins.get(rel)==digest,'unbound dependency '+str(path);deps[rel]=digest
        receipt['dependencies']=deps;receipt['binary_sha256']=sha(receipt['binary']);receipt['object_sha256']={str(p):sha(p) for p in attempt.glob('*.o')}
        symbols=subprocess.check_output(['/usr/bin/nm','-C','--defined-only',receipt['binary']],text=True,timeout=60);(attempt/'symbols.log').write_text(symbols)
        assert 'packet26_model_entry' in symbols and 'mtp36::DraftRuntime' in symbols
        if a.mode=='native':
            compiler_dir=Path('/opt/intel/oneapi/compiler/2026.0/bin/compiler');bundler=str(compiler_dir/'clang-offload-bundler');obj=attempt/'0.o'
            targets=subprocess.check_output([bundler,'-type=o','-list','-input='+str(obj)],text=True,timeout=60).splitlines();target=[x for x in targets if x.startswith('sycl-spir64')];assert len(target)==1
            bc=attempt/'entry-device.bc';subprocess.run([bundler,'-type=o','-unbundle','-targets='+target[0],'-input='+str(obj),'-output='+str(bc)],check=True,timeout=120)
            subprocess.run([str(compiler_dir/'sycl-post-link'),'-symbols','-split=source','-o',str(attempt/'kernel.table'),str(bc)],check=True,timeout=120)
            entries='\n'.join(p.read_text() for p in attempt.glob('kernel*.sym'))
            for t in (12,13,18,23,42):assert 'PackedKernelILj'+str(t)+'E' in entries,'missing GSQ kernel '+str(t)
            (attempt/'kernel-entries.log').write_text(entries)
            disassembly=subprocess.check_output(['/usr/bin/objdump','-d','--disassemble=main',receipt['binary']],text=True,timeout=60);(attempt/'main.asm').write_text(disassembly)
            receipt['offline']={'entry_device_sha256':sha(bc),'kernel_entries_sha256':sha(attempt/'kernel-entries.log'),'main_disassembly_sha256':sha(attempt/'main.asm'),'native_invoked':False}
        for f,h in pins.items():assert sha(R/f)==h,f
        assert sha(receipt['commands'][0][0])==receipt['compiler_sha256'];receipt['passed']=True
        dest=P/'evidence'/('full-'+a.mode+'-build.json');assert not dest.exists();dest.write_text(json.dumps(receipt,indent=2)+'\n')
    except BaseException as e:receipt['error']=type(e).__name__+': '+str(e);raise
    finally:(attempt/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'passed':True,'mode':a.mode,'receipt':str(attempt/'receipt.json')}))
if __name__=='__main__':main()
