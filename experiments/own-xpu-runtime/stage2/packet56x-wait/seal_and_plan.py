#!/usr/bin/env python3
"""Create separate lean seals and run screen v1 CPU-only plans; never a window."""
import os, subprocess, sys
from pathlib import Path
P=Path(__file__).resolve().parent
S=P.parent/'screen'
assert os.getpriority(os.PRIO_PROCESS,0)==19
assert set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32))
for mode in ('spin','sleep20'):
    binary=P/'build/device'/('own-rt-iq3' if mode=='spin' else 'own-rt-iq3-sleep20')
    seal=P/('screen-seal-'+mode+'.json')
    subprocess.run([sys.executable,'-B',str(S/'seal.py'),'--profile','tp2',
        '--lineage',str(P),'--build-receipt',str(P/('build-'+mode+'-receipt.json')),
        '--fixture',str(P/'fixture'/mode/'receipt.json'),'--binary',str(binary),
        '--dispatch',str(P/'dispatch-speed6.json'),'--output',str(seal)],check=True)
    command=[sys.executable,'-B',str(S/'screen.py'),'--profile','tp2',
        '--lineage',str(P),'--seal',str(seal),'--binary',str(binary),
        '--faults-reviewed-through','1970-01-01T00:00:00Z',
        '--output',str(S/'evidence'/('packet56x-'+mode+'-a')),'--plan']
    with (P/'evidence'/('screen-plan-'+mode+'.json')).open('w') as out:
        subprocess.run(command,stdout=out,check=True)
    print(mode,'seal and CPU plan PASS',flush=True)
