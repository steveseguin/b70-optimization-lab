#!/usr/bin/env python3
"""Rebuild the instrumentation translation unit only; CPU compilation, no GPU."""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
B = P / 'build'
BASE = P.parent / 'packet64-record-bundle'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, value):
    p.write_text(json.dumps(value, indent=2) + '\n')

def limits():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32))
    assert os.environ.get('OMP_NUM_THREADS') == '2'
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))

def main():
    limits()
    assert not (P/'build-device-receipt.json').exists(), 'fresh build only'
    (B/'tmp').mkdir(exist_ok=True)
    os.environ['TMPDIR'] = str(B/'tmp')
    sources, artifacts, commands, inherited = {}, {}, [], []
    def bind(f): sources[str(f.relative_to(ROOT))] = sha(f)
    def run(command, name):
        command = list(map(str, command))
        commands.append(dict(name=name, command=command, cwd=str(ROOT)))
        with (B/(name+'.log')).open('w') as log:
            subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        print(name, 'PASS', flush=True)
    parent = json.loads((BASE/'build-device-receipt.json').read_text())
    for name, digest in parent['sources'].items(): assert sha(ROOT/name) == digest, name
    sources.update(parent['sources'])
    bind(BASE/'build-device-receipt.json')
    from kernel_gate import mirror
    from math_gate import closure, check
    check()
    mapping = mirror()
    for f in closure(): bind(f); bind(mapping[f])
    local = B/'engine'
    local.mkdir(exist_ok=True)
    entry = local/'entry-main.cpp'
    entry.write_text('#define main packet26_model_entry\n#include '+json.dumps(str(mapping[P/'main.cpp']))+'\n#undef main\n')
    prior = json.loads((BASE/'engine-commands.json').read_text())
    for mode in ('gnu-host', 'device'):
        dest = B/mode
        dest.mkdir(exist_ok=True)
        cc = next(r['command'] for r in prior if r['name'] == mode+'-entry-main')
        cc = [x.replace(str(BASE), str(P)) if x.startswith('-I') else x for x in cc[:cc.index('-o')]]
        run([*cc, '-o', dest/'entry-main.o', '-c', entry], mode+'-entry-main')
        link = list(next(r['command'] for r in prior if r['name'] == mode+'-link'))
        link[link.index('-o')+1] = str(dest/'own-rt-iq3')
        for i, arg in enumerate(link):
            if not arg.endswith('.o'): continue
            if arg == str(BASE/'build'/mode/'entry-main.o'):
                link[i] = str(dest/'entry-main.o')
            else:
                src = Path(arg)
                bind(src)
                target = dest/'inherited'/(hashlib.sha256(str(src).encode()).hexdigest()[:12]+'-'+src.name)
                target.parent.mkdir(exist_ok=True)
                if target.exists():
                    assert sha(target) == sha(src)
                else:
                    os.link(src, target)
                inherited.append(dict(parent=str(src.relative_to(ROOT)), current=str(target.relative_to(ROOT)), sha256=sha(src)))
                link[i] = str(target)
        run(link, mode+'-link')
        artifacts[str((dest/'own-rt-iq3').relative_to(P))] = sha(dest/'own-rt-iq3')
    for f in (entry, P/'build_engine.py', P/'parent-source-manifest.json', P/'kernel_gate.py', P/'math_gate.py', P/'kernel_overlay.py', P/'submission_overlay.py', P/'kernel_guard.hpp'): bind(f)
    save(P/'engine-commands.json', commands)
    bind(P/'engine-commands.json')
    save(P/'evidence/object-identity.json', dict(passed=True, device_executed=False, objects=inherited, rebuilt=['entry-main.o']))
    bind(P/'evidence/object-identity.json')
    save(P/'build-device-receipt.json', dict(schema='packet64.attribution.cpu-build.v1', passed=True,
         device_executed=False, sources=sources, artifacts=artifacts,
         peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
         nice=19, cpu_affinity=sorted(os.sched_getaffinity(0))))

if __name__ == '__main__': main()
