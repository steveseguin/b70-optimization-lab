"""Read-only prerequisite: no other work remains in either two-card queue."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
QUEUE=P.parents[1]/'ops/lane-queue'
def check(directory=QUEUE):
    for lane in 'AB':
        inflight=Path(directory)/('inflight-'+lane+'.json')
        if inflight.exists():
            row=json.loads(inflight.read_text())
            if row.get('job',{}).get('name')!='packet58ai-census-A':
                raise ValueError('other lane job still in flight: '+lane)
        p=Path(directory)/('queue-'+lane+'.txt')
        if not p.is_file():raise ValueError('queue state unavailable: '+lane)
        for line in p.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#'):continue
            row=json.loads(line)
            if row.get('name')!='packet58ai-census-A':raise ValueError('both two-card queues must be empty before census')
    return dict(passed=True,queues_drained=True,device_executed=False)
