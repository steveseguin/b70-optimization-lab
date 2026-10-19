#!/usr/bin/env python3
"""Small synthetic CPU-only cache and production-pointer gates; no model reads."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

P = Path(__file__).resolve().parent
ROOT = P.parents[3]

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run(output):
    output = Path(output)
    if output.exists():
        raise ValueError('new output path required')
    allowed = set(range(4,16)) | set(range(20,32))
    if not set(os.sched_getaffinity(0)) <= allowed or os.getpriority(os.PRIO_PROCESS,0) < 19:
        raise ValueError('run nice -n 19 taskset -c 4-15,20-31 python3 -B')
    env = {'PATH':'/usr/bin:/bin','HOME':str(Path.home()),'LANG':'C.UTF-8',
           'OMP_NUM_THREADS':'1','OMP_DYNAMIC':'FALSE','PYTHONDONTWRITEBYTECODE':'1'}
    flags = ['g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off',
             '-frounding-math','-fopenmp','-DOWN_RT_HOST_ONLY','-Wall','-Wextra',
             '-Wno-unknown-pragmas','-Wno-misleading-indentation','-MMD']
    records = []; dependencies = {P/'cpu_cache_gates.py'}
    started = time.time()
    P.joinpath('build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cache-gates-',dir=P/'build') as temporary:
        build = Path(temporary)
        for mode in ('normal','sanitized'):
            extra = [] if mode == 'normal' else ['-O1','-g1','-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie']
            for source in ('cache_table_test.cpp','expert_reference.cpp','expert_cache_test.cpp'):
                obj = build/(mode+'-'+source+'.o')
                include = P.parent/'packet49d-round3' if source == 'expert_reference.cpp' else P
                cmd = flags+extra+['-I'+str(include), '-I'+str(P.parent/'packet2/kernels'), '-I'+str(P.parent/'packet2/loader'), '-c',str(P/source),'-o',str(obj)]
                result = subprocess.run(cmd,env=env,capture_output=True,text=True)
                if result.returncode:
                    raise RuntimeError(result.stderr)
                dep = obj.with_suffix('.d')
                for name in dep.read_text().replace('\\\n',' ').split(':',1)[1].split():
                    dependencies.add(Path(name).resolve())
            for name,sources in (('state',('cache_table_test.cpp',)),('expert',('expert_reference.cpp','expert_cache_test.cpp'))):
                binary = build/(mode+'-'+name)
                cmd = flags[:-1]+extra+[str(build/(mode+'-'+s+'.o')) for s in sources]+['-o',str(binary)]
                result = subprocess.run(cmd,env=env,capture_output=True,text=True)
                if result.returncode:
                    raise RuntimeError(result.stderr)
                for repeat in range(2):
                    result = subprocess.run([str(binary)],env=env,capture_output=True,text=True)
                    if result.returncode:
                        raise RuntimeError(result.stdout+'\n'+result.stderr)
                    receipt = json.loads(result.stdout)
                    if receipt.get('passed') is not True or receipt.get('device_executed') is not False:
                        raise ValueError('CPU gate identity')
                    records.append({'mode':mode,'gate':name,'repeat':repeat,'binary_sha256':sha(binary),'receipt':receipt,'stderr':result.stderr})
        retained_build_bytes = sum(p.stat().st_size for p in build.iterdir())
    for name in ('state','expert'):
        receipts = [r['receipt'] for r in records if r['gate']==name]
        if any(r != receipts[0] for r in receipts):
            raise ValueError('fresh process/compiler-mode mismatch: '+name)
    evidence = {'schema':'packet58.cache-pointer-cpu-gates.v1','passed':True,
                'device_executed':False,'model_reads':False,'large_pinned_allocations':False,
                'compiler':subprocess.check_output(['g++','--version'],text=True).splitlines()[0],
                'compiler_flags':flags,'sanitizer_flags':['-O1','-g1','-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie'],
                'records':records,'scratch_peak_bytes':retained_build_bytes,'scratch_removed':True,
                'elapsed_seconds':time.time()-started,
                'dependencies':{str(p.relative_to(ROOT)):sha(p) for p in sorted(dependencies)}}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'passed':True,'output':str(output),'records':len(records),
                      'scratch_removed':True,'elapsed_seconds':evidence['elapsed_seconds']}))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
