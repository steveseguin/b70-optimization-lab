#!/usr/bin/env python3
"""Wait for the serial CPU matrix, then run draft capture and the static seal once."""
import fcntl,gzip,json,os,subprocess,time
from pathlib import Path
from storage import admit,digest
P=Path(__file__).resolve().parent;B=P/'build'
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
# Sleeping on this lock consumes no CPU slot. Never start after a partial or failed matrix.
with (B/'capacity-cpu.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 matrix=json.loads((P/'capacity-cpu-gates.json').read_text())
 if matrix.get('passed') is not True:raise RuntimeError('Full CPU matrix did not pass; no next stage launched')
rows=[]
for script,args in [('capacity_draft_gate.py',['--run']),('seal_context.py',[])]:
 admit(10_000_000)
 raw=P/'evidence'/('finish-'+script+'-'+str(time.time_ns())+'.log')
 with raw.open('w') as output:
  result=subprocess.run(['nice','-n','19','ionice','-c','3','python3','-B',str(P/script),*args],stdout=output,stderr=subprocess.STDOUT)
 digest_raw=digest(raw);archive=raw.with_suffix('.log.gz');archive.write_bytes(gzip.compress(raw.read_bytes(),mtime=0));raw.unlink()
 rows.append(dict(script=script,returncode=result.returncode,raw_sha256=digest_raw,archive=str(archive.relative_to(P))))
 receipt=dict(passed=result.returncode==0 and len(rows)==2,device_executed=False,rows=rows)
 (P/'finish-cpu-gates.json').write_text(json.dumps(receipt,indent=2)+'\n')
 if result.returncode:raise RuntimeError('CPU stage failed: '+str(archive))
 print('PASS',script,flush=True)
