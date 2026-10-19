"""Small CPU proof; shared compiler turn also guards synthetic full-shape work."""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import shlex

P=Path(__file__).resolve().parent
ROOT=P.parents[3]
sys.path.insert(0,str(P.parents[1]/'ops'))
from compile_turn import turn
from analyze import limits


def main():
    limits()
    b=P/'build'
    b.mkdir(exist_ok=True)
    results=[]
    for name,compiler in [('gnu','/usr/bin/g++'),('intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
        command=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off',
                 '-DOWN_RT_HOST_ONLY','-I'+str(P.parent/'packet136-record-bundle'),
                 '-I'+str(P.parent/'packet28-dense'),'-I'+str(P.parent/'packet131-snapshot-banks/build/checked/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks'),
                 '-MMD','-MF',str(b/(name+'.d')),
                 str(P/'cpu.cpp'),'-o',str(b/name)]
        with turn():
            limits()
            assert os.statvfs(P).f_bavail*os.statvfs(P).f_frsize >= 27_000_000_000
            with (P/f'evidence/{name}-build.log').open('w') as out:
                subprocess.run(command,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,check=True)
            # Same serialization/admission scope: no full-shape reads in a
            # protected whole-host timing window, and no real GGUF input.
            with (P/f'evidence/{name}-cpu.jsonl').open('w') as out:
                completed=subprocess.run([str(b/name)],stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,check=False)
        rows=[json.loads(s) for s in (P/f'evidence/{name}-cpu.jsonl').read_text().splitlines()]
        assert len(rows)==25 and completed.returncode in (0,2)
        deps=shlex.split((b/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)[1])
        pins={str(Path(p).resolve().relative_to(ROOT)):hashlib.sha256(Path(p).read_bytes()).hexdigest()
              for p in deps if Path(p).is_file() and Path(p).resolve().is_relative_to(ROOT)}
        results.append(dict(compiler=name,command=command,results=rows,returncode=completed.returncode,
                            source_hashes=pins,
                            binary_sha256=hashlib.sha256((b/name).read_bytes()).hexdigest()))
        print(name,'full-shape CPU',rows[-1]['passed'],flush=True)
    (P/'evidence/cpu-proof.json').write_text(json.dumps(dict(passed=all(r['returncode']==0 for r in results),
        device_executed=False,results=results,max_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),indent=2)+'\n')


if __name__=='__main__':
    main()
