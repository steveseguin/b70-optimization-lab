#!/usr/bin/env python3
"""Root's finite fixed41 consolidation; no retry, copies redirects before release."""
from pathlib import Path
import hashlib,json,os,subprocess,time
P=Path(__file__).resolve().parents[1];H=P/'consolidate.py';C=Path('/home/steve/own-xpu-runtime-results/gsq-canonical-archives-a')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(H)=='64b4c0131eeb8ea0f87bb8fea29864b79dc0b6e9ffc4fb2a7be1e6e1e726ee33'
assert sha(P/'evidence/independent-review.json')=='425d26ce78399f188bd302aa7b3f66244fbaf1c9535c334f54bc36b083b71f02'
rows=[];start=time.time()
def copy(batch,names):
 src=C/f'batch-{batch:02d}';dest=P/f'evidence/batch-{batch:02d}';dest.mkdir(exist_ok=True)
 for n in names:
  b=(src/n).read_bytes()
  with (dest/n).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
  assert sha(dest/n)==hashlib.sha256(b).hexdigest()
 fd=os.open(dest,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
assert json.loads((C/'batch-00/released.json').read_text())['passed']
copy(0,('release-start.json','released.json'))
for batch in range(1,41):
 for phase in ('verify','release-verified'):
  cmd=['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(H),'--'+phase,'--batch',str(batch)]
  log=Path('/home/steve/own-xpu-runtime-results')/f'gsq-canonical-{phase}-{batch:02d}.log'
  with log.open('x') as f:r=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
  rows.append(dict(batch=batch,phase=phase,returncode=r.returncode,log=str(log)));print(json.dumps(rows[-1]),flush=True)
  if r.returncode:raise SystemExit(r.returncode)
  if phase=='verify':copy(batch,('restore.json.gz','verified.json'))
  else:copy(batch,('release-start.json','released.json'))
(P/'evidence/remaining-execution.json').write_text(json.dumps(dict(passed=True,phases=rows,elapsed_seconds=time.time()-start,helper_sha256=sha(H)),indent=2)+'\n')
