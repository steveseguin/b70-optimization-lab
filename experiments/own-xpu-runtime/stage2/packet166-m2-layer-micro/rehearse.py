"""Real proposal plan/rehearsal in a private directory; no live queue edits."""
import json,subprocess,tempfile
from pathlib import Path
from build_engine import P,ROOT,limits,sha
import launch_env

def main():
 limits();ops=P.parents[1]/'ops';proposal=ops/'lane-queue/proposed-p166-micro-B.txt'
 receipts=[]
 with tempfile.TemporaryDirectory(prefix='packet166-plan-') as d:
  directory=Path(d);(directory/'queue-B.txt').write_bytes(proposal.read_bytes())
  commands=[('lanequeue-plan',['/usr/bin/python3','-B',str(ops/'lane-queue/lanequeue.py'),'plan','--lane','B','--directory',str(directory)]),('shared-rehearsal',['/usr/bin/python3','-B',str(ops/'rehearse_entry.py'),str(proposal),'--report','--json'])]
  for name,argv in commands:
   with (P/'evidence'/(name+'.stdout')).open('w') as out,(P/'evidence'/(name+'.stderr')).open('w') as err:
    result=subprocess.run(argv,env=launch_env.environment(),stdin=subprocess.DEVNULL,stdout=out,stderr=err)
   receipts.append(dict(name=name,returncode=result.returncode,proposal_sha256=sha(proposal),stdout_sha256=sha(P/'evidence'/(name+'.stdout')),stderr_sha256=sha(P/'evidence'/(name+'.stderr')),device_executed=False))
 (P/'evidence/rehearsal.json').write_text(json.dumps(dict(passed=all(r['returncode']==0 for r in receipts),records=receipts),indent=2)+'\n');print(json.dumps(receipts,indent=2))
if __name__=='__main__':main()
