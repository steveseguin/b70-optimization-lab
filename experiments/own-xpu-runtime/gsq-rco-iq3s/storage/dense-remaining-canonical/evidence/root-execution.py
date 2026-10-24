#!/usr/bin/env python3
"""Root's fixed40-bundle verify/release sequence; no retry."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,time
P=Path(__file__).resolve().parents[1];H=P/'reuse.py';C=Path('/home/steve/own-xpu-runtime-results/gsq-dense-remaining-canonical-a');sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true',required=True);parser.add_argument('--review-sha256',required=True);args=parser.parse_args()
assert len(args.review_sha256)==64 and sha(P/'evidence/independent-review.json')==args.review_sha256
review=json.loads((P/'evidence/independent-review.json').read_text());assert review['passed'] is True

rows=[];start=time.time()
for i in range(40):
 for phase in ('verify','release-verified'):
  cmd=['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(H),'--'+phase,'--batch',str(i)];log=Path('/home/steve/own-xpu-runtime-results')/f'gsq-dense-remaining-raw-{i:02d}-{phase}.log'
  with log.open('x') as f:r=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
  rows.append(dict(batch=i,phase=phase,returncode=r.returncode,log=str(log)));print(json.dumps(rows[-1]),flush=True)
  if r.returncode:raise SystemExit(r.returncode)
  src=C/f'batch-{i:02d}';dst=P/f'evidence/batch-{i:02d}';dst.mkdir(exist_ok=True)
  for name in (('restore.json','verified.json') if phase=='verify' else ('release-start.json','released.json')):
   b=(src/name).read_bytes()
   with (dst/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
   assert sha(dst/name)==hashlib.sha256(b).hexdigest()
  fd=os.open(dst,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
(P/'evidence/execution.json').write_text(json.dumps(dict(passed=True,phases=rows,elapsed_seconds=time.time()-start,helper_sha256=sha(H)),indent=2)+'\n')
