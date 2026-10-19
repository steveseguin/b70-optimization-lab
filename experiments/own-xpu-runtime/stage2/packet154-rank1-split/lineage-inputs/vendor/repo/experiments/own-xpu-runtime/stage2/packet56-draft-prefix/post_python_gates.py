#!/usr/bin/env python3
"""Final serial Python and mocked-window regressions; no device execution."""
import os,subprocess,json,gzip,hashlib,time,shutil
from pathlib import Path
P=Path(__file__).resolve().parent
from storage import admit,digest
assert os.environ['OMP_NUM_THREADS']=='2' and os.getpriority(os.PRIO_PROCESS,0)==19
scripts=['math_gate.py','queue_gate.py','test_state_machine.py','test_mtp_controller.py','test_submission_overlay.py','test_cleanup_paths.py','test_state_retention.py','test_suite_warmup.py']
e=P/'evidence'/('final-python-'+str(time.time_ns()));e.mkdir(parents=True);rows=[]
for name in scripts:
 log=e/(name+'.log');admit(10_000_000)
 with log.open('w') as out:r=subprocess.run(['nice','-n','19','ionice','-c','3','python3','-B',str(P/name)],stdout=out,stderr=subprocess.STDOUT)
 h=digest(log);packed=log.with_suffix('.log.gz')
 with log.open('rb') as inp,gzip.open(packed,'wb') as out:shutil.copyfileobj(inp,out)
 assert hashlib.sha256(gzip.decompress(packed.read_bytes())).hexdigest()==h;log.unlink()
 rows.append(dict(script=name,returncode=r.returncode,raw_sha256=h,archive=str(packed.relative_to(P)),source_sha256=digest(P/name)))
 if r.returncode:raise RuntimeError(str(packed))
(P/'inherited-python-gates.json').write_text(json.dumps(dict(passed=True,device_executed=False,rows=rows),indent=2)+'\n')
subprocess.run(['python3','-B',str(P/'context_window_gate.py')],check=True)
run=subprocess.run(['python3','-B','-m','unittest','test_window'],cwd=P,text=True,capture_output=True)
packed=e/'test_window.log.gz';packed.write_bytes(gzip.compress((run.stdout+run.stderr).encode()))
assert run.returncode==0,run.stdout+run.stderr
import re
n=int(re.search(r'Ran (\d+) tests',run.stderr)[1])
(P/'window-mocked-inherited-tests.json').write_text(json.dumps(dict(passed=True,tests=n,device_executed=False,excluded=None,scope='inherited mocks plus actual host-only class diagnostic contract',archive=str(packed.relative_to(P)),raw_sha256=hashlib.sha256((run.stdout+run.stderr).encode()).hexdigest()),indent=2)+'\n')
print('Final Python and all inherited window tests pass',n,flush=True)
