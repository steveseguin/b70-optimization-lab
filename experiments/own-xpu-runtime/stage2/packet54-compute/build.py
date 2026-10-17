#!/usr/bin/env python3
"""Serial CPU compilation; immutable baseline object reuse proved by relink."""
import argparse
import fcntl
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
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def run_locked(mode):
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0)) <= set(range(4,16))|set(range(20,32))
    from preparation import limits
    limits(300_000_000)
    out=HERE/'build'/mode;out.mkdir(parents=True,exist_ok=True)
    lock=(HERE/'build/compile.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    sys.path.insert(0,str(P46))
    try:
        parent=load('p54_parent_build',P46/'build_layer.py');parent.HERE=HERE
        mirror=load('p54_parent_mirror',P46/'mirror_inputs.py');mirror_hashes=mirror.validate_baseline_mirror()
        objects,inventory,closure,provenance=parent.baseline("device" if mode=="device" else "host")
    finally:sys.path.pop(0)
    source=out/'source';source.mkdir(exist_ok=True)
    originals={n:HERE/n for n in ('bench.cpp','recurrence.hpp','route.hpp','hc_ffn.hpp','recurrence_test.hpp','route_test.hpp','hc_ffn_test.hpp','cpu_identity_test.cpp')}
    for name,path in [('p51-bench.hpp','packet51-round2/layer_bench.cpp'),('p51-candidate.hpp','packet51-round2/candidate.hpp'),('p51-fixture.hpp','packet51-round2/fixture_bytes.hpp'),('p48b-candidate.hpp','packet48b-production/candidate.hpp'),('p48-gemv.hpp','packet48-gemv/gemv.hpp')]:originals[name]=HERE.parent/path
    closure.update(mirror_hashes)
    for p in [*originals.values(),HERE/'CMakeLists.txt',HERE/'build.py',HERE.parent/'packet51-round2/dispatch-baseline.json',HERE.parent/'packet34-replay-bench/directory.tsv',BASE/'rope.bf16',P46/'build_layer.py',P46/'mirror_inputs.py']:
        closure[str(p.relative_to(ROOT))]=sha(p)
    reverse={v.resolve():source/n for n,v in originals.items()}
    reverse[(HERE.parent/'packet48-gemv/gemv.hpp').resolve()]=source/'p48-gemv.hpp'
    checked=BASE/'build/checked'
    for name,path in originals.items():
        def replace(match):
            inc=match[1];resolved=(path.parent/inc).resolve()
            if not resolved.is_file() and (BASE/inc).is_file():resolved=(BASE/inc).resolve()
            if inc=='p51-bench.hpp':target=source/inc
            elif resolved in reverse:target=reverse[resolved]
            elif resolved.is_relative_to(BASE):target=checked/resolved.relative_to(ROOT)
            elif inc=='sycl_operation.hpp':target=checked/'experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp'
            else:return match[0]
            return '#include '+json.dumps(str(target))
        content=path.read_text()
        if name=='p51-bench.hpp':content=content.replace('int main(int argc,char**argv)','int packet51_unused_entry(int argc,char**argv)')
        content=re.sub(r'^\s*#include\s*"([^"\n]+)"',replace,content,flags=re.M)
        mirrored='#line 1 '+json.dumps(str(path))+'\n'+content
        if not (source/name).exists() or (source/name).read_text()!=mirrored:
            (source/name).write_text(mirrored)
    manifest=out/'baseline.cmake';manifest.write_text('set(P54_BASELINE_OBJECTS\n'+''.join(' '+json.dumps(str(p))+'\n' for p in objects)+')\n')
    compiler='/usr/bin/g++' if mode=='host' else '/opt/intel/oneapi/compiler/2026.0/bin/icpx'
    commands=[['cmake','-S',str(HERE),'-B',str(out),'-DCMAKE_CXX_COMPILER='+compiler,'-DOWN_RT_HOST_ONLY='+('OFF' if mode=='device' else 'ON'),'-DP54_BASELINE_MANIFEST='+str(manifest),'-DP54_SOURCE_MIRROR='+str(source)],['cmake','--build',str(out),'--parallel','1']]
    with (out/'build.log').open('w') as log:
        for cmd in commands:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    assert all(sha(ROOT/p)==h for p,h in closure.items()),'source drift'
    assert all(sha(ROOT/p)==r['sha256'] for p,r in inventory.items()),'object drift'
    build_bytes=sum(p.stat().st_size for p in (HERE/'build').rglob('*') if p.is_file());assert build_bytes<500_000_000,'build budget'
    binary=out/'compute-bench'
    artifacts={str(binary.relative_to(ROOT)):sha(binary)}
    if mode != 'device':
        proof=out/'cpu-identity-test';artifacts[str(proof.relative_to(ROOT))]=sha(proof)
    row=dict(schema='ownrt.packet54.build.v1',passed=True,device_executed=False,mode=mode,source_hashes=closure,baseline_provenance=provenance,baseline_objects=inventory,artifacts=artifacts,commands=commands,compiler=compiler,compiler_sha256=sha(compiler),nice=19,affinity=sorted(os.sched_getaffinity(0)),build_bytes=build_bytes)
    (HERE/f'build-{mode}.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(dict(passed=True,mode=mode,device_executed=False,build_bytes=build_bytes)))
def run(mode):
    from preparation import exclusive_cpu_work
    with exclusive_cpu_work(planned_write_bytes=300_000_000):
        run_locked(mode)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=['host','device','intel-host'],required=True);run(p.parse_args().kind)
