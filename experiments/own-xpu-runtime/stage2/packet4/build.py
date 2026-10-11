#!/usr/bin/env python3
"""Compile both targets; execute only CPU binaries; default removes build scratch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
PYTHON='/home/steve/.venvs/vllm-xpu/bin/python'
COMPILER='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--keep-build',action='store_true');p.add_argument('--real-layer',action='store_true');a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
    assert 'idle' in subprocess.check_output(['ionice','-p',str(os.getpid())],text=True)
    build=HERE/'build';assert not build.is_symlink()
    r=dict(schema='own-runtime.iq3.packet4.build.v1',passed=False,device_executed=False,nice=19,OMP_NUM_THREADS='2',max_build_jobs=2,commands=[])
    def run(args,allowed=(0,)):
        args=list(map(str,args));v=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
        r['commands'].append(dict(argv=args,returncode=v.returncode,stdout=v.stdout,stderr=v.stderr))
        print(v.stdout,end='',flush=True)
        if v.returncode not in allowed:raise RuntimeError(v.stderr+v.stdout)
        return v
    try:
        run([COMPILER,'--version'])
        for mode,compiler,enabled in [('host','/usr/bin/g++','ON'),('device',COMPILER,'OFF')]:
            run(['cmake','-S',HERE,'-B',build/mode,f'-DCMAKE_CXX_COMPILER={compiler}',f'-DOWN_RT_HOST_ONLY={enabled}'])
            run(['cmake','--build',build/mode,'-j2'])
        run([build/'host/owner-retirement-tests'])
        inp=build/'input'
        if not inp.exists():run([PYTHON,'-B',HERE/'prepare.py','--output',inp])
        run([PYTHON,'-B',HERE/'test.py','--binary',build/'host/own-rt-iq3','--scratch',build/f'tests-{time.time_ns()}','--input',inp,'--receipt',HERE/'cpu-tests.json'])
        if a.real_layer:
            out=build/f'real-{time.time_ns()}';m=json.loads((inp/'input.json').read_text())['model_dir']
            oracle=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/runs/official-sigmoid-20261011/incident-retrospective/step1'
            cmd=[build/'host/own-rt-iq3','--first-layer','--input',inp/'tokens.txt','--plan',inp/'plan.tsv','--identity',inp/'identity.tsv','--model-dir',m,'--output',out]
            if (oracle/'layer-00.bf16').exists():cmd+=['--oracle',oracle]
            run(cmd,allowed=(0,1))
            from real_check import compare
            real=compare(out,inp,HERE/'evidence/real-layer',oracle,build/'host/own-rt-iq3')
            r['real_layer_exact']=real['passed']
        run([sys.executable,'-B',HERE/'test_window.py'])
        r['artifacts_sha256']={str(p.relative_to(build)):sha(p) for p in [build/'host/own-rt-iq3',build/'device/own-rt-iq3']}
        r['cpu_tests_sha256']=sha(HERE/'cpu-tests.json')
        r['passed']=True  # compilation + synthetic integration; NOT real-model quality
        r['real_model_qualified']=False
    finally:
        paths=[]
        for folder in [HERE,HERE.parent/'packet2',HERE.parent/'packet3',HERE.parents[1]/'stage1/packet3-prep/src']:
            paths.extend(p for p in folder.rglob('*') if p.is_file() and 'build' not in p.relative_to(folder).parts and p.suffix in ('.cpp','.hpp','.py'))
        paths += [HERE/'CMakeLists.txt',HERE/'receipt.schema.json',ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/admission-receipt.json',ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json']
        r['sources']={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))}
        if not a.keep_build and build.exists():shutil.rmtree(build)
        r['build_directory_removed']=not build.exists()
        (HERE/'build-receipt.json').write_text(json.dumps(r,indent=2)+'\n')
if __name__=='__main__':main()
