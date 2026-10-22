#!/usr/bin/env python3
"""Packet185 seal + proposal (CPU only). Never queues, never launches.

Order (memory lesson "plan after seal"): gates -> package_rows (this) -> check_queue_rows
(plan + rehearse on the sealed state) -> final_checks -> final_checks --ready.

  1. v5/p185_v5_queue_plan.py --stage   write the packet mirror proposals/proposed-p185-two-card-B.txt
  2. v5/cpu_seal.py --seal              seal the source/build/gate closure (it includes the mirror)
  3. copy the mirror to ops/lane-queue/proposed-p185-two-card-B.txt (the proposal file; queue
     files and PAUSE latches are never touched)
  4. evidence/package-rows.json        seal and proposal digests
Run from the repository root: nice -n 19 taskset -c 8-15,24-31 python3 -B <this> </dev/null
"""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];V5=HERE/'v5'
NAME='proposed-p185-two-card-B.txt';LIVE=HERE.parents[1]/'ops/lane-queue'/NAME;MIRROR=HERE/'proposals'/NAME
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def step(*args):
    r=subprocess.run([sys.executable,'-B',*map(str,args)],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=1800)
    if r.returncode:sys.exit(f'{args[0]} failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')
    return r.stdout
def main():
    ready=HERE/'READY-FOR-DEVICE.json'
    if ready.exists():sys.exit('READY-FOR-DEVICE.json exists: withdraw it (rename to evidence/withdrawn-ready-<ts>.json) before repackaging')
    step(V5/'p185_v5_queue_plan.py','--stage')
    step(V5/'cpu_seal.py','--seal')
    shutil.copyfile(MIRROR,LIVE)
    assert sha(LIVE)==sha(MIRROR)
    rows=[json.loads(l) for l in LIVE.read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]
    receipt=dict(passed=True,device_executed=False,queued=False,live_queue_modified=False,
        proposal=str(LIVE.relative_to(ROOT)),proposal_sha256=sha(LIVE),mirror=str(MIRROR.relative_to(ROOT)),
        cpu_seal=str((V5/'cpu-seal.json').relative_to(ROOT)),cpu_seal_sha256=sha(V5/'cpu-seal.json'),
        rows=[dict(job=r['name'],lane=r['lane'],depends_on=r.get('depends_on',[]),expected_seconds=r['plan']['expected_seconds'],
                   watchdog_seconds=r['plan']['watchdog_seconds'],host_required_available_bytes=r['plan']['host_required_available_bytes'],
                   planned_writes=r['plan']['planned_writes']) for r in rows])
    (V5/'evidence/package-rows.json').write_text(json.dumps(receipt,indent=1)+'\n')
    print('package_rows: sealed; proposal',LIVE.relative_to(ROOT),sha(LIVE)[:16],'rows',[r['name'] for r in rows])
if __name__=='__main__':main()
