"""Keep actual shared-tool receipts, including refusals; temp queues only."""
import json,shutil,subprocess,tempfile
from pathlib import Path
from build_engine import P,ROOT,save,sha,limits
from package import VERSION
OPS=P.parents[1]/'ops'
def main():
    limits();results=[]
    for lane in ('B','A'):
        proposal=OPS/'lane-queue'/f'proposed-p168-body-census-{lane}-{VERSION}.txt'
        with tempfile.TemporaryDirectory(prefix='p168-lane-plan-')as tmp:
            directory=Path(tmp);shutil.copy2(proposal,directory/f'queue-{lane}.txt')
            for kind,cmd in [('plan',['/usr/bin/python3','-B',str(OPS/'lane-queue/lanequeue.py'),'plan','--lane',lane,'--directory',str(directory)]),
              ('rehearse',['/usr/bin/python3','-B',str(OPS/'rehearse_entry.py'),str(proposal),'--report','--json'])]:
                cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True)
                (P/'evidence'/f'shared-{kind}-{lane}-{VERSION}.stdout.log').write_text(cp.stdout)
                (P/'evidence'/f'shared-{kind}-{lane}-{VERSION}.stderr.log').write_text(cp.stderr)
                results.append(dict(lane=lane,kind=kind,returncode=cp.returncode,passed=cp.returncode==0))
                print(lane,kind,'PASS'if cp.returncode==0 else'REFUSED',flush=True)
    save(P/'evidence/shared-packaging.json',dict(passed=all(r['passed']for r in results),
      device_executed=False,temporary_queues_only=True,results=results))
if __name__=='__main__':main()
