#!/usr/bin/env python3
"""Root's finite explicit remaining13 batches; one invocation per phase, no retry."""
from pathlib import Path
import hashlib,json,subprocess,time
P=Path(__file__).resolve().parents[1]; helper=P/'closed_coverage_bundles.py'
expected=json.loads((P/'evidence/preparation.json').read_text())['source_sha256']['experiments/own-xpu-runtime/gsq-rco-iq3s/storage/coverage-closed/closed_coverage_bundles.py']
assert hashlib.sha256(helper.read_bytes()).hexdigest()==expected
assert json.loads((P/'evidence/independent-review.json').read_text())['passed']
rows=[];start=time.time()
for batch in range(1,14):
 for phase in ('archive','prune-verified','offload-verified','release-local-verified'):
  cmd=['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(helper),'--'+phase,'--batch',str(batch)]
  log=Path('/home/steve/own-xpu-runtime-results')/f'gsq-coverage-bundle-{batch:02d}-{phase}.log'
  with log.open('x') as f:r=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
  rows.append(dict(batch=batch,phase=phase,returncode=r.returncode,log=str(log)))
  print(json.dumps(rows[-1]),flush=True)
  if r.returncode:raise SystemExit(r.returncode)
(P/'evidence/remaining-execution.json').write_text(json.dumps(dict(passed=True,phases=rows,elapsed_seconds=time.time()-start,helper_sha256=expected),indent=2)+'\n')
