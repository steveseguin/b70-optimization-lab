#!/usr/bin/env python3
"""Serial CPU compilation, verified read-only reuse of packet45 dependencies."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BASE=HERE.parent/'packet45-merged3'
P46=HERE.parent/'packet46-specialized'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0)) <= set(range(4,16))|set(range(20,32))
    assert shutil.disk_usage(HERE).free > 9_000_000_000

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def run_locked(mode):
    limits()
    # Packet46 already proves read-only object reuse by byte-identical relink.
    # Re-run that proof into this new packet, never into the sealed source tree.
    sys.path.insert(0,str(P46))
    try:
        parent=load('p48b_parent_build',P46/'build_layer.py')
        parent.HERE=HERE
        mirror=load('p48b_parent_mirror',P46/'mirror_inputs.py')
        mirror_hashes=mirror.validate_baseline_mirror()
        objects,inventory,closure,provenance=parent.baseline(mode)
    finally:sys.path.pop(0)
    out=HERE/'build'/mode;out.mkdir(parents=True,exist_ok=True)
    source=out/'source';source.mkdir(exist_ok=True)
    own=['layer_bench.cpp','candidate.hpp','fixture_bytes.hpp']+(['candidate_cpu_test.cpp'] if mode=='host' else [])
    originals={n:HERE/n for n in own}
    originals['p48b-candidate.hpp']=HERE.parent/'packet48b-production/candidate.hpp'
    originals['p48-gemv.hpp']=HERE.parent/'packet48-gemv/gemv.hpp'
    checked=BASE/'build/checked'
    for name,path in originals.items():
        def replace(match):
            inc=match[1]
            if inc in own:target=source/inc
            elif inc=='../packet48b-production/candidate.hpp':target=source/'p48b-candidate.hpp'
            elif inc=='../packet48-gemv/gemv.hpp':target=source/'p48-gemv.hpp'
            elif inc=='sycl_operation.hpp':target=checked/'experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp'
            elif inc.startswith('../packet45-merged3/'):
                target=checked/(BASE/inc.split('../packet45-merged3/',1)[1]).relative_to(ROOT)
            else:return match[0]
            return '#include '+json.dumps(str(target))
        text=re.sub(r'^\s*#include\s*"([^"\n]+)"',replace,path.read_text(),flags=re.M)
        rendered='#line 1 '+json.dumps(str(path))+'\n'+text
        target=source/name
        if not target.exists() or target.read_text()!=rendered:target.write_text(rendered)
    manifest=out/'baseline.cmake'
    manifest.write_text('set(P51_BASELINE_OBJECTS\n'+''.join('  '+json.dumps(str(p))+'\n' for p in objects)+')\n')
    compiler='/usr/bin/g++' if mode=='host' else '/opt/intel/oneapi/compiler/2026.0/bin/icpx'
    commands=[['cmake','-S',str(HERE),'-B',str(out),'-DCMAKE_CXX_COMPILER='+compiler,
               '-DOWN_RT_HOST_ONLY='+('ON' if mode=='host' else 'OFF'),
               '-DP51_BASELINE_MANIFEST='+str(manifest),'-DP51_SOURCE_MIRROR='+str(source)],
              ['cmake','--build',str(out),'--parallel','1']]
    closure.update(mirror_hashes)
    for p in [*originals.values(),HERE/'CMakeLists.txt',HERE/'build.py',HERE/'dispatch-baseline.json',HERE/'preparation.py',HERE.parent/'packet34-replay-bench/directory.tsv',BASE/'rope.bf16',P46/'build_layer.py',P46/'mirror_inputs.py']:
        closure[str(p.relative_to(ROOT))]=sha(p)
    with (out/'build.log').open('w') as log:
        for cmd in commands:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    assert all(sha(ROOT/p)==h for p,h in closure.items()),'source drift'
    assert all(sha(ROOT/p)==r['sha256'] for p,r in inventory.items()),'object drift'
    from preparation import limits as final_limits
    final_limits(0)
    binary=out/'layer-bench'
    row=dict(schema='ownrt.packet51.build.v1',passed=True,device_executed=False,mode=mode,
             source_hashes=closure,baseline_provenance=provenance,baseline_objects=inventory,
             artifacts={str(q.relative_to(ROOT)):sha(q) for q in ([binary,out/'candidate-cpu-test'] if mode=='host' else [binary])},commands=commands,
             compiler=compiler,compiler_sha256=sha(compiler),nice=19,affinity=sorted(os.sched_getaffinity(0)))
    (HERE/f'build-layer-{mode}.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(dict(passed=True,mode=mode,device_executed=False)))

def run(mode):
    from preparation import exclusive_cpu_work
    with exclusive_cpu_work(planned_write_bytes=400_000_000):
        run_locked(mode)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=['host','device'],required=True);run(p.parse_args().kind)
