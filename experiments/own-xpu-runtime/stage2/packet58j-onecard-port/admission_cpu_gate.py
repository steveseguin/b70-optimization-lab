#!/usr/bin/env python3
"""Full-shape admission/protocol dry run. All coordination uses temporary roots."""
import json
import os
from pathlib import Path
import subprocess
import sys
import memory_plan as M
import queue_runner as Q

P=Path(__file__).resolve().parent
ROOT=P.parents[3]


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32))
    gate=json.loads((P/'evidence/postload-allocation-cpu.json').read_text())
    assert gate['passed'] and not gate['device_executed'] and gate['expert_banks']==144
    assert gate['postload_allocations']==3 and gate['negative_cases']==2
    paths=[P/n for n in ('admission_cpu_gate.py','test_refusal58g.py','test_admission58e.py','test_mask58f.py','window.py',
        'memory_plan.py','queue_runner.py','onecard_admission.py','lane_admission.py',
        'chain_devices.py','drain_gate.py','evidence/postload-allocation-cpu.json')]
    paths.extend((P/'evidence/58c-supervisor').glob('*'))
    sources={str(p.relative_to(ROOT)):M.sha(p) for p in paths}
    run=subprocess.run([sys.executable,'-B','-m','unittest','-v','test_admission58e','test_mask58f','test_refusal58g'],
        cwd=P,stdin=subprocess.DEVNULL,capture_output=True,text=True)
    (P/'evidence/admission-cpu.log').write_text(run.stdout+run.stderr)
    row=dict(schema='packet58g.admission-cpu.v1',passed=run.returncode==0,
        device_executed=False,model_reads=False,production_coordination_entered=False,
        sources=sources,windows={n:dict(scope=Q.W.A.window_scope(n),
            plan=M.window_plan(n),gap_seconds=Q.GAP_SECONDS) for n in Q.ORDER},
        complete_device_postload_measurement_available=False,
        postload_regression=dict(expert_banks=144,cache_bytes=M.CACHE_BYTES,
            postload_allocations=gate['postload_allocations'],negative_cases=gate['negative_cases'],
            backing_bytes=gate['backing_bytes']))
    assert all(M.sha(ROOT/n)==v for n,v in sources.items())
    (P/'evidence/admission-cpu.json').write_text(json.dumps(row,indent=2)+'\n')
    print(run.stdout+run.stderr,end='')
    return run.returncode


if __name__=='__main__':sys.exit(main())
