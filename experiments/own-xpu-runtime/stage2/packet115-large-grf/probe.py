"""Compile-only test of module-wide LARGE on BMG-G31, never open a device."""
import hashlib
import gzip
import json
import os
import resource
import subprocess
from pathlib import Path
from build_engine import P, limits
from compile_turn import turn

def main():
    limits()
    b=P/'build'; e=P/'evidence'; (b/'tmp').mkdir(exist_ok=True)
    compiler=Path('/opt/intel/oneapi/compiler/2026.0/bin/icpx')
    commands=[
        [str(compiler), '-fsycl', '-fsycl-device-only', '-O2', '-std=c++20', '-fno-fast-math', '-ffp-contract=off', '-fdenormal-fp-math=ieee', '-c', str(P/'probe.cpp'), '-o', str(b/'probe.bc')],
        [str(compiler.parent/'compiler/llvm-spirv'), '--spirv-ext=+all,-SPV_INTEL_runtime_aligned,-SPV_KHR_untyped_pointers,-SPV_KHR_fma', str(b/'probe.bc'), '-o', str(b/'probe.spv')],
    ]
    for mode in ('default', 'large'):
        cmd=['/usr/bin/ocloc','compile','-spirv_input','-file',str(b/'probe.spv'),'-device','bmg-g31','-options','-ze-fp32-correctly-rounded-divide-sqrt'+(' -ze-opt-large-register-file' if mode=='large' else ''),'-out_dir',str(b/mode)]
        commands.append(cmd)
    results=[]
    env={**os.environ,'TMPDIR':str(b/'tmp'),'OMP_NUM_THREADS':'1','OMP_THREAD_LIMIT':'1','IGC_ShaderDumpEnable':'1','IGC_DumpToCustomDir':str(b/'igc')}
    for i,cmd in enumerate(commands):
        env['IGC_DumpToCustomDir']=str(b/f'probe-igc-{i}')
        with turn(), (e/f'probe-{i}.log').open('w') as f:
            r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env,timeout=300)
        results.append(dict(command=cmd,returncode=r.returncode,log=f'probe-{i}.log'))
        print(i,r.returncode,(e/f'probe-{i}.log').read_text()[-4000:],flush=True)
        if r.returncode:break
    for i in (2,3):
        for f in (b/f'probe-igc-{i}').glob('*.asm'):
            (e/f'probe-{i}-{f.name}.gz').write_bytes(gzip.compress(f.read_bytes(),mtime=0))
    row=dict(schema='packet115.module-large-probe.v1',device_executed=False,results=results,source_sha256=hashlib.sha256((P/'probe.cpp').read_bytes()).hexdigest(),max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    (e/'probe.json').write_text(json.dumps(row,indent=2)+'\n')

if __name__=='__main__':main()
