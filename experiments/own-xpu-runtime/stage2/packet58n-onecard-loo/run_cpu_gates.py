#!/usr/bin/env python3
"""Run only passive/mocked Python tests, capture their source-bound receipt."""
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import subprocess
P=Path(__file__).resolve().parent
ROOT=P.parents[3]

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    resource.setrlimit(resource.RLIMIT_AS,(8_000_000_000,8_000_000_000))
    inputs=[*P.glob('*.py'),P/'views.json',*list((P/'selections').glob('*.json')),
            P/'evidence/postload-census.json',P/'evidence/58c-kd/run/progress.jsonl']
    sources={str(f.relative_to(ROOT)):sha(f) for f in inputs}
    command=['/usr/bin/python3','-B','-m','unittest','discover','-s',str(P),'-v']
    result=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    log=P/'evidence/python-cpu-gates.log';log.write_text(result.stdout)
    unchanged=all(sha(ROOT/n)==h for n,h in sources.items())
    count=re.search(r'Ran (\d+) tests',result.stdout)
    row=dict(passed=result.returncode==0 and unchanged and bool(count),device_executed=False,
        tests=int(count.group(1)) if count else 0,source_unchanged=unchanged,
        sources=sources,log_sha256=sha(log),command=command,
        native_binaries_executed=False,services_started=False,live_queue_changed=False)
    (P/'evidence/python-cpu-gates.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:row[k] for k in ('passed','device_executed','tests','source_unchanged')}))
    return 0 if row['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
