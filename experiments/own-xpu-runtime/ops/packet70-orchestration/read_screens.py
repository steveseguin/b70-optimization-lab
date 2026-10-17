#!/usr/bin/env python3
"""Read packet65 quick compare.py's validated data, including its original exact token checks."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[4]
Q=ROOT/'experiments/own-xpu-runtime/stage2/packet65-expert-occupancy/screen/quick'
sys.path.insert(0,str(Q))
import compare as c

def collect():
    c.cpu_gate();c.verify()
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    lanes={};errors={};receipts={}
    for lane in 'AB':
        lanes[lane]=[]
        for index,job in enumerate(c.jobs(Q/('jobs-'+lane+'.txt'),lane)):
            key=lane+'/'+str(index)
            try:
                row=c.load(job,lane)
                root=c.HERE/'evidence'/job['out']
                c.require(c.read(root/'window.json')['boot_id']==boot,'screen belongs to another boot')
                row['exact_count']=13 if row['exact'] else 0
                lanes[lane].append(row)
                receipts[key]={str(f.relative_to(ROOT)):c.sha(f) for f in (root/'window.json',root/'run/summary.json',root/'lane-coordination.json')}
            except (OSError,ValueError,KeyError,TypeError) as error:
                errors[key]=str(error)
    return dict(boot_id=boot,lanes=lanes,errors=errors,receipts=receipts,
                source='packet65 screen/quick/compare.py load + checked_rate; mean of two production controls per lane')
if __name__=='__main__':print(json.dumps(collect()))
