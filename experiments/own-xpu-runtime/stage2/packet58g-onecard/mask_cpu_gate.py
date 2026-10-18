#!/usr/bin/env python3
"""CPU proof of actual child environment, passive topology and failure boundaries."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import chain_devices as D
import window as W

P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32))
    topology=D.onecard_topology(cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix='mask58f-') as temporary:
        env=D.onecard_environment(W.closed_environment(dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',
            LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu')),Path(temporary)/'home')
        child=subprocess.run(['/usr/bin/python3','-B','-c','import os,json;print(json.dumps(dict(os.environ)))'],
            env=env,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
        actual=json.loads(child.stdout)
        assert all(actual.get(k)==v for k,v in D.onecard_mask().items())
        assert not list((Path(temporary)/'home').iterdir())
        actual['HOME']='<fresh empty private directory per window>'
    tests=subprocess.run([sys.executable,'-B','-m','unittest','-v','test_mask58f'],
        cwd=P,stdin=subprocess.DEVNULL,capture_output=True,text=True)
    (P/'evidence/mask-cpu.log').write_text(tests.stdout+tests.stderr)
    sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('mask_cpu_gate.py','test_mask58f.py',
        'test_admission58e.py','chain_devices.py','onecard_admission.py','window.py','drain_gate.py','lane_admission.py')}
    row=dict(schema='packet58f.mask-cpu.v1',passed=tests.returncode==0,device_executed=False,
        topology=topology,child_environment=actual,sources=sources,
        proof_scope='CPU child environment and passive single-BDF mapping; native driver FD proof awaits coordinator K1',
        render_access_policy='Only card-0 Xe FDs accepted; not an OS device sandbox; no DRM node opened by this gate')
    (P/'evidence/mask-cpu.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(dict(passed=row['passed'],topology=topology)))
    return tests.returncode
if __name__=='__main__':sys.exit(main())
