#!/usr/bin/env python3
"""CPU fixtures/build only. Never invokes the SYCL executable or enumerates cards."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];BUILD=HERE/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--rebuild-fixtures',action='store_true');a=p.parse_args()
    if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':raise SystemExit('nice19 and OMP_NUM_THREADS=2 required')
    if BUILD.is_symlink():raise SystemExit('build symlink refused')
    if (BUILD/'device-fault-latch.json').exists() or list(BUILD.glob('card3-*')):raise SystemExit('preserve existing device evidence; no rebuild')
    BUILD.mkdir(exist_ok=True)
    commands=[]
    def run(argv,allow_failure=False):
        r=subprocess.run(list(map(str,argv)),text=True,capture_output=True);commands.append(dict(argv=list(map(str,argv)),returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));print(r.stdout,end='');print(r.stderr,end='',file=sys.stderr)
        if r.returncode and not allow_failure:raise RuntimeError('build/tool failed')
        return r
    fixture_dir=BUILD/'fixtures'
    if a.rebuild_fixtures and fixture_dir.exists():shutil.rmtree(fixture_dir)
    if not fixture_dir.exists():run([sys.executable,'-B',HERE/'fixtures.py','--output',fixture_dir])
    run(['cmake','-S',HERE,'-B',BUILD/'host'])
    run(['cmake','--build',BUILD/'host','-j2'])
    run(['cmake','-S',HERE,'-B',BUILD/'native','-DNATIVE=ON','-DCMAKE_CXX_COMPILER=/opt/intel/oneapi/compiler/2026.0/bin/icpx'])
    run(['cmake','--build',BUILD/'native','-j2'])
    for name,binary in [('gnu',BUILD/'host/host-test'),('icpx',BUILD/'native/host-test')]:
        run([binary,fixture_dir,BUILD/(name+'-oracle.json'),'--generate-core'],allow_failure=True)
    results=[];failures=[]
    for name,binary in [('host',BUILD/'host/host-test'),('fresh',BUILD/'host/host-test'),('icpx',BUILD/'native/host-test'),('icpx-fresh',BUILD/'native/host-test')]:
        r=run([binary,fixture_dir,BUILD/(name+'.json')],allow_failure=True);failures.append(r.stderr);results.append(json.loads((BUILD/(name+'.json')).read_text()))
    for binary in (BUILD/'host/host-test',BUILD/'native/host-test'):
        dynamic=run(['readelf','-d',binary]).stdout
        if any(x in dynamic for x in ('libsycl','libze_loader','libOpenCL')):raise RuntimeError('CPU binary accelerator dependency')
    protocol_tests=[]
    for compiler in ('GNU','IntelLLVM'):
        tests=run([sys.executable,'-B',HERE/'test_window.py'])
        protocol_tests.append(dict(compiler_build=compiler,returncode=tests.returncode,output=tests.stderr))
    probe=run([sys.executable,'-B',HERE/'math_probe.py']);(HERE/'math-probe.json').write_text(probe.stdout)
    fixture_manifest=json.loads((fixture_dir/'manifest.json').read_text())
    fixture_manifest['authority']='frozen runtime arithmetic identity v1: packet4/core.hpp'
    fixture_manifest['packet1b_role']='pre-rebase diagnostic only; original expected bytes retained'
    for case in fixture_manifest['cases']:
        case['packet4_expected_sha256']={compiler:sha(fixture_dir/(case['name']+suffix)) for compiler,suffix in [('GNU','.core'),('IntelLLVM','.core.icpx')]}
    files=list(HERE.glob('*.hpp'))+list(HERE.glob('*.cpp'))+list(HERE.glob('*.py'))+[HERE/'CMakeLists.txt']
    owner=HERE.parent.parent/'stage1/packet3-prep/src'
    files += [owner/n for n in ('owner.hpp','owner.cpp','sycl_operation.hpp','sycl_device.cpp')]
    files += [HERE.parent/'packet4/core.hpp',HERE.parent/'packet4/kernels.hpp',HERE.parent/'packet3/kernels/api.hpp',HERE.parent/'packet2/kernels/math.hpp',HERE.parent/'packet2/kernels/grids.hpp',HERE.parent/'packet4/owner_retire.cpp',HERE.parent/'packet1b/reference.py',HERE.parent/'packet2/tests/device_window.py']
    files += list(fixture_dir.iterdir())+[BUILD/'native/device-test',BUILD/'host/host-test',BUILD/'native/host-test']
    hashes={str(f.relative_to(ROOT)):sha(f) for f in files}
    exact=all(r['passed'] for r in results) and results[0]==results[1] and results[2]==results[3]
    receipt=dict(schema='own-runtime.packet15.build.v1',compiled=True,cpu_exactness_passed=exact,device_executed=False,protocol_tests=protocol_tests,host_results=results,fixtures=fixture_manifest,hashes=hashes,commands=commands)
    (BUILD/'prepared.json').write_text(json.dumps(receipt,indent=2)+'\n')
    # Durable small evidence; generated fixtures and binaries remain ignored.
    small={k:v for k,v in receipt.items() if k not in ('commands','hashes')}
    small['hashes']={k:v for k,v in hashes.items() if '/build/' not in k}
    small['binary_sha256']={str(f.relative_to(BUILD)):sha(f) for f in (BUILD/'native/device-test',BUILD/'host/host-test',BUILD/'native/host-test')}
    small['commands']=[{k:v for k,v in c.items() if k not in ('stdout','stderr')} for c in commands]
    small['test_output']=tests.stderr;small['failure_output']=failures
    (HERE/'build-receipt.json').write_text(json.dumps(small,indent=2)+'\n')
    print(json.dumps(dict(compiled=True,cpu_exactness_passed=exact,checks=results[0]['checks'],device_executed=False)))
    return 0 if exact else 1
if __name__=='__main__':raise SystemExit(main())
