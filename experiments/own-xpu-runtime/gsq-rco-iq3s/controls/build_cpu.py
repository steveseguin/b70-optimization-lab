"""One bounded host conversion test; no devices, services or model payloads."""
import hashlib, importlib.util, json, os, resource, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
P=Path(__file__).resolve().parent
R=P.parents[3]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16))|set(range(24,32))
    assert shutil.disk_usage('/').free > 27_000_000_000+20*1024**2
def main():
    limits()
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(120,120))
    source=[P/'upload.hpp',P/'test_upload.cpp',P/'build_cpu.py',R/'experiments/own-xpu-runtime/stage2/packet2/kernels/math.hpp']
    pins={str(p.relative_to(R)):sha(p) for p in source}
    b=P/'build'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');b.mkdir(parents=True)
    graph=P.parent/'graph/new-plan.json';census=P.parent/'metadata/new-census.json'
    data=json.loads(census.read_text());g=json.loads(graph.read_text());roles={}
    for l in g['launches']:
        for w in l['weights']:roles.setdefault(w,set()).add(l['op'])
    controls={w:ops for w,ops in roles.items() if ops-{'gemv','routed_gemv','lookup'}}
    assert len(controls)==293
    rows=[]
    for w,ops in sorted(controls.items()):
        assert not ops&{'gemv','routed_gemv','lookup'}, w
        t=data['tensors'][w];assert t['type_id'] in (0,1,30)
        rows.append(dict(name=w,type_id=t['type_id'],elements=t['elements'],source_bytes=t['bytes'],upload_type_id=0,upload_bytes=t['elements']*4,ops=sorted(ops)))
    assert sum(x['type_id']==1 for x in rows)==1
    manifest=dict(graph_sha256=sha(graph),census_sha256=sha(census),rows=rows,source_bytes=sum(x['source_bytes'] for x in rows),upload_bytes=sum(x['upload_bytes'] for x in rows),native_integrated=False)
    (P/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    path=R/'experiments/own-xpu-runtime/ops/compile_turn.py'
    spec=importlib.util.spec_from_file_location('controls_compile_turn',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    command=['/usr/bin/g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-MMD','-MF',str(b/'deps.d'),str(P/'test_upload.cpp'),'-o',str(b/'test-upload')]
    compiler=sha(Path(command[0]).resolve())
    sys.modules["build_engine"]=sys.modules[__name__]
    with m.turn(),(b/'compile.log').open('w') as log:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    run=subprocess.run([str(b/'test-upload')],capture_output=True,text=True,check=True,timeout=30)
    (b/'test.log').write_text(run.stdout+run.stderr);result=json.loads(run.stdout)
    for p,h in pins.items():assert sha(R/p)==h,p
    assert sha(Path(command[0]).resolve())==compiler
    deps=(b/'deps.d').read_text().replace('\\\n',' ').split(':',1)[1].split()
    dependency_pins={str(Path(x).resolve().relative_to(R)):sha(Path(x)) for x in deps}
    result.update(command=command,compiler_sha256=compiler,sources=pins,dependencies=dependency_pins,binary_sha256=sha(b/'test-upload'),manifest_sha256=sha(P/'manifest.json'),attempt=str(b.relative_to(R)),native_integrated=False)
    (P/'cpu-proof.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
