#!/usr/bin/env python3
"""Build host and device targets; run ONLY host programs; retain receipts.

Default cleanup removes this packet's ignored build tree. --keep-build is for
preparing the later native window; it NEVER runs the device binary.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OWNER=HERE.parents[1]/'stage1/packet3-prep'
PYTHON='/home/steve/.venvs/vllm-xpu/bin/python'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--keep-build',action='store_true');a=parser.parse_args()
    if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':raise SystemExit('Require nice19 OMP_NUM_THREADS=2')
    if 'idle' not in subprocess.check_output(['ionice','-p',str(os.getpid())],text=True):raise SystemExit('Require ionice -c3 for model fixture reads')
    build=HERE/'build'
    if build.is_symlink():raise SystemExit('Refuse symlink build tree')
    receipt=dict(schema='own-runtime.iq3.packet2.build.v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),host=platform.node(),nice=19,OMP_NUM_THREADS='2',max_build_jobs=2,device_executed=False,commands=[],passed=False,development_failures=['Initial C++ auto declarations mixed signed and unsigned types; split declarations.', 'SYCL does not support strict FP dynamic rounding/exceptions; explicit no-fast-math, contract-off and IEEE denormal flags replace strict mode.', 'icpx precise mode warns when contraction is separately disabled; use explicit independent FP controls.', 'Name-based placement check initially treated global PLE as layerless; census binds it to layer1, now explicit.'])
    def run(args):
        result=subprocess.run(list(map(str,args)),cwd=ROOT,capture_output=True,text=True)
        receipt['commands'].append(dict(argv=list(map(str,args)),returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        print(result.stdout,end='',flush=True);print(result.stderr,end='',file=sys.stderr,flush=True)
        if result.returncode:raise RuntimeError('validation command failed')
        return result.stdout
    try:
        run(['/opt/intel/oneapi/compiler/2026.0/bin/icpx','--version']);run(['cmake','--version']);run(['dpkg-query','-W','libze-dev','libze1'])
        for mode,enabled in [('host','OFF'),('device','ON')]:
            run(['cmake','-S',HERE,'-B',build/mode,'-DCMAKE_BUILD_TYPE=Release',f'-DIQ3_DEVICE={enabled}'])
            run(['cmake','--build',build/mode,'--clean-first','-j2'])
        # Regress the existing owner using its HOST-only configuration.
        run(['cmake','-S',OWNER,'-B',build/'owner-host','-DOWN_RT_HOST_ONLY=ON','-DOWN_RT_BUILD_NATIVE_SMOKE=OFF',f'-DPython3_EXECUTABLE={PYTHON}'])
        run(['cmake','--build',build/'owner-host','-j2'])
        run(['ctest','--test-dir',build/'owner-host','--output-on-failure'])
        run([PYTHON,'-B',HERE/'tests/run_cpu.py','--host',build/'host/host-tests','--scratch',build/'fixtures','--receipt',HERE/'cpu-receipt.json'])
        run([sys.executable,'-B',HERE/'tests/test_window.py'])
        from roofline import calculate
        assert json.loads((HERE/'roofline.json').read_text())==calculate()
        deps=run(['readelf','-d',build/'host/host-tests'])
        assert all(s not in deps.lower() for s in ('libsycl','libze_loader','libur_loader','libopencl'))
        receipt['compile_commands']={mode:json.loads((build/mode/'compile_commands.json').read_text()) for mode in ('host','device')}
        assert all('-fsycl' not in c['command'] for c in receipt['compile_commands']['host'])
        receipt['artifacts_sha256']={str(p.relative_to(build)):sha(p) for p in (build/'host/host-tests',build/'device/device-test',build/'device/libkernels.a')}
        receipt['cpu_receipt_sha256']=sha(HERE/'cpu-receipt.json')
        receipt['level_zero_header_sha256']=sha(Path('/usr/include/level_zero/ze_api.h'))
        receipt['passed']=True
    finally:
        source=list(HERE.rglob('*.cpp'))+list(HERE.rglob('*.hpp'))+list(HERE.rglob('*.py'))+[HERE/'CMakeLists.txt']+list((OWNER/'src').glob('*'))
        source=[p for p in source if p.is_file() and build not in p.parents]
        source+=[ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1'/name for name in ('tensor-census.json','admission-receipt.json')]
        source+=[HERE.parents[1]/'stage1/packet1b/loaders'/name for name in ('dequant.py','headers.py','FORMAT.md','iq3-grid.json','iq2-s-grid.json','iq3-s-grid.json')]
        receipt['source_sha256']={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(source))}
        if not a.keep_build and build.exists():shutil.rmtree(build)
        receipt['build_directory_removed']=not build.exists()
        (HERE/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
