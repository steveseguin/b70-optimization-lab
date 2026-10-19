"""Passive sealed chain plan and disk budget; never capture faults or launch."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from seal import sha

P=Path(__file__).resolve().parent


def main():
    import queue_runner as Q
    output=P/'evidence/card0-58as-b'
    assert not output.exists()
    command=[sys.executable,'-B',str(P/'queue_runner.py'),'--plan','--card','0','--view','down-tile16',
        '--output-root',str(output),'--faults-reviewed-through','2026-01-01T00:00:00Z']
    env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH=json.loads((P/'library-path.json').read_text())['LD_LIBRARY_PATH'])
    run=subprocess.run(command,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
    (P/'evidence/chain-plan.log').write_text(run.stdout)
    for name in Q.ORDER:
        assert '# '+name+': whole-host' in run.stdout
    writes=sum(Q.W.WRITES['K1' if n.startswith('K1') else n] for n in Q.ORDER)
    free=shutil.disk_usage('/').free
    assert free>=27_000_000_000
    size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file())
    assert size<=300_000_000
    storage=dict(passed=True,device_executed=False,free_bytes=free,planned_write_bytes=writes,
        preparation_stop_floor_bytes=27_000_000_000,chain_disk_floor_bytes=25_000_000_000,
        chain_storage_admitted_now=free-writes>=25_000_000_000,
        chain_output_created=output.exists(),build_bytes=size)
    (P/'evidence/storage-plan.json').write_text(json.dumps(storage,indent=2)+'\n')
    row=dict(passed=True,device_executed=False,windows=list(Q.ORDER),output_created=output.exists(),
        fault_capture_created=False,command=command,storage=storage,
        build_receipt_sha256=sha(P/'build-receipt.json'),submission_pins_sha256=sha(P/'submission-pins.json'),
        plan_log_sha256=sha(P/'evidence/chain-plan.log'))
    (P/'evidence/plan-check.json').write_text(json.dumps(row,indent=2)+'\n')
    print('7 whole-host plan windows PASS; no chain output or fault review created')


if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    main()
