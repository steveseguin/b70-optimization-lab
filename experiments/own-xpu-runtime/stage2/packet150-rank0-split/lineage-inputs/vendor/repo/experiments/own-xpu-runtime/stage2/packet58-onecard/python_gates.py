#!/usr/bin/env python3
"""Run packet58 standard-library CPU gates; no model/device access."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32))
    names=sorted(p.name for p in P.glob('test_*.py') if p.name!='test_engine_reset.py')
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in P.glob('*.py')}
    run=subprocess.run([sys.executable,'-B','-m','unittest','-v',*[n[:-3] for n in names]],cwd=P,capture_output=True,text=True)
    out=P/'evidence';out.mkdir(exist_ok=True)
    (out/'python-cpu-gates.log').write_text(run.stdout+run.stderr)
    after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in P.glob('*.py')}
    row=dict(schema='own-runtime.packet58.python-cpu.v1',passed=run.returncode==0 and sources==after,
             device_executed=False,tests=names,sources=after,output=run.stdout+run.stderr)
    (out/'python-cpu-gates.json').write_text(json.dumps(row,indent=2)+'\n')
    print(run.stdout+run.stderr);return 0 if row['passed'] else 1
if __name__=='__main__':sys.exit(main())
