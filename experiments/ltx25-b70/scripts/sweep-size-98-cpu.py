#!/usr/bin/env python3
"""Sequential guarded CPU regression sweep; logs under the new packet98 evidence path.
Device discovery uses test doubles; GPU allocation, checkpoint reads and packet writes
are refused. Existing tests/helpers are never modified. Child interpreters use -B.
"""
import collections
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'data/size-98-offline'
SKIP={'test-graph-capture-packet-negative.py','test-graph-capture-packet-negative-direct.py','test-host-residency-packet-negative.py'}


def main():
    OUT.mkdir(exist_ok=True)
    results=[]
    with tempfile.TemporaryDirectory(prefix='size98-guard-') as temp:
        Path(temp,'sitecustomize.py').write_bytes((HERE/'cpu-guard-98.py').read_bytes())
        env=dict(os.environ,PYTHONPATH=temp,PYTHONDONTWRITEBYTECODE='1',ONEAPI_DEVICE_SELECTOR='opencl:cpu',ZE_AFFINITY_MASK='99',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
        for test in sorted(HERE.glob('test-*.py')):
            if test.name in SKIP:
                results.append({'test':test.name,'status':'skipped','reason':'packet-copying negative test; existing prepared paths protected'})
                continue
            try:
                p=subprocess.run([sys.executable,'-B',str(test)],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
                log=p.stdout;status='pass' if p.returncode==0 else 'fail';rc=p.returncode
            except subprocess.TimeoutExpired as e:
                log=e.stdout or '';log=log.decode() if isinstance(log,bytes) else log;status='timeout';rc=124
            (OUT/(test.stem+'.log')).write_text(log)
            results.append({'test':test.name,'status':status,'returncode':rc,'guard_refusal':'PACKET98_CPU_GUARD' in log})
            print(test.name,status,flush=True)
            (OUT/'sweep.json').write_text(json.dumps({'counts':dict(collections.Counter(r['status'] for r in results)),'results':results},indent=2)+'\n')
    print(json.dumps(dict(collections.Counter(r['status'] for r in results))))


if __name__=='__main__':main()
