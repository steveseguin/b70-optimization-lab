#!/usr/bin/env python3
"""Real one-card submissions, both DOWN layouts, all four pointer placements."""
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 binary=P/'build/gnu-host/p58-cache-fixtures';records=[]
 parent=json.loads((P.parent/'packet58g-onecard/k1-cpu.json').read_text())
 with tempfile.TemporaryDirectory(prefix='k1-58j-',dir=P/'build') as tmp:
  for layout in ('production','down-tile16'):
   out=Path(tmp)/layout
   run=subprocess.run([str(binary),'--output',str(out),'--iterations','1','--down-layout',layout],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=240,env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'})
   (P/'evidence'/f'k1-cpu-{layout}.log').write_text(run.stdout+run.stderr)
   assert run.returncode==0,run.stdout+run.stderr
   row=json.loads((out/'k1.json').read_text());assert row['passed'] and not row['device_executed'] and row['checks']==24
   assert row['exact_output_sha256']==parent['exact_output_sha256']
   records.append(dict(layout=layout,receipt=row));(P/'evidence'/f'k1-{layout}-cases.jsonl').write_bytes((out/'k1-cases.jsonl').read_bytes())
 row=dict(passed=True,device_executed=False,checks=48,exact_output_sha256=parent['exact_output_sha256'],binary_sha256=sha(binary),records=records,sources={str(f.relative_to(ROOT)):sha(f) for f in (Path(__file__),P.parent/'packet58j-onecard-port/p58_native_fixture.cpp',P.parent/'packet58g-onecard/k1-cpu.json')})
 (P/'k1-cpu.json').write_text(json.dumps(row,indent=2)+'\n');print('48 actual K1 byte checks PASS')
if __name__ == '__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    main()
