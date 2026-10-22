#!/usr/bin/env python3
"""Serial CPU-only qualification stages; stop at first failure, never retry."""
import os,subprocess,json,time,gzip,shutil,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
from storage import admit,digest
assert os.environ['OMP_NUM_THREADS']=='2' and os.getpriority(os.PRIO_PROCESS,0)==19
steps=[('owners',['cpu_gates.py']),('capture-guards',['capture_gate.py'])]
for mode in ('gnu-host','icpx-host','asan'):
 steps += [('mini-'+mode,['gates.py','mini',mode]),('mtp-'+mode,['mtp_gates.py',mode])]
steps += [('draft-auth',['draft_auth_gate.py']),('native-mini',['native_mini_gate.py','--binary',str(P/'build/gnu-host/own-rt-iq3'),'--output',str(P/'native-mini-cpu.json')]),('rollback',['capacity_cpu_gate.py','--phase','rollback']),('rollback-asan',['capacity_rollback_asan.py'])]
rows=[];stamp=str(time.time_ns());e=P/'evidence'/('remaining-cpu-'+stamp);e.mkdir(parents=True)
for name,args in steps:
 admit(200_000_000)
 log=e/(name+'.log');command=['nice','-n','19','ionice','-c','3','python3','-B',str(P/args[0]),*args[1:]]
 start=time.monotonic();print('START',name,flush=True)
 with log.open('w') as out:r=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT)
 raw_hash=digest(log);packed=log.with_suffix('.log.gz')
 admit(log.stat().st_size+1_000_000,build_extra=0)
 with log.open('rb') as inp,gzip.open(packed,'wb') as out:shutil.copyfileobj(inp,out)
 h=hashlib.sha256()
 with gzip.open(packed,'rb') as inp:
  for b in iter(lambda:inp.read(1048576),b''):h.update(b)
 assert h.hexdigest()==raw_hash;log.unlink()
 rows.append(dict(stage=name,passed=r.returncode==0,command=command,seconds=time.monotonic()-start,raw_sha256=raw_hash,archive=str(packed.relative_to(P)),archive_sha256=digest(packed)))
 (P/'remaining-cpu-gates.json').write_text(json.dumps(dict(passed=all(x['passed'] for x in rows) and len(rows)==len(steps),device_executed=False,rows=rows),indent=2)+'\n')
 print('PASS' if r.returncode==0 else 'FAIL',name,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
