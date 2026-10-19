"""Read-only prerequisite: no other work remains in either two-card queue."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
QUEUE=P.parents[1]/'ops/lane-queue'
PROPOSAL=QUEUE/'proposed-p58ai-census-A.txt'

def proposal_jobs(proposal=PROPOSAL):
    jobs=[json.loads(line) for line in Path(proposal).read_text().splitlines()
          if line.strip() and not line.lstrip().startswith('#')]
    if not jobs:raise ValueError('current census proposal is empty')
    for job in jobs:
        identity(job)
    return jobs

def identity(job):
    argv=job.get('argv',[])
    if (not job.get('name') or job.get('lane')!='A'
            or argv.count('--output')!=1
            or len(argv)<3 or Path(argv[2]).name!='queue_runner.py'):
        raise ValueError('invalid census job identity')
    repo=P.parents[3]
    if (repo/argv[2]).resolve()!=P/'queue_runner.py':
        raise ValueError('foreign census entry')
    try:output=(repo/argv[argv.index('--output')+1]).resolve()
    except IndexError:raise ValueError('missing census output') from None
    if not output.is_relative_to(P/'evidence'):
        raise ValueError('foreign census output')
    return job['name'],job['lane'],str(output)

def output_root(proposal=PROPOSAL):
    roots={Path(identity(job)[2]).parent for job in proposal_jobs(proposal)}
    if len(roots)!=1:raise ValueError('census proposal must share one output root')
    return roots.pop()

def check(directory=QUEUE,proposal=PROPOSAL):
    own={identity(job) for job in proposal_jobs(proposal)}
    def is_own(job,lane):
        try:return lane=='A' and identity(job) in own
        except ValueError:return False
    for lane in 'AB':
        inflight=Path(directory)/('inflight-'+lane+'.json')
        if inflight.exists():
            row=json.loads(inflight.read_text())
            if not is_own(row.get('job',{}),lane):
                raise ValueError('other lane job still in flight: '+lane)
        p=Path(directory)/('queue-'+lane+'.txt')
        if not p.is_file():raise ValueError('queue state unavailable: '+lane)
        for line in p.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#'):continue
            row=json.loads(line)
            if not is_own(row,lane):raise ValueError('both two-card queues must be empty before census')
    return dict(passed=True,queues_drained=True,device_executed=False)
