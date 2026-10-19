"""Private qualification; preserve the failed historical shared --report receipt."""
import json,subprocess,tempfile
from pathlib import Path
from build_engine import P,ROOT,limits,sha
import launch_env

def main():
 limits();ops=P.parents[1]/'ops';proposal=ops/'lane-queue/proposed-p166-micro-B.txt'
 receipts=[];outputs=[]
 with tempfile.TemporaryDirectory(prefix='packet166-plan-') as d:
  directory=Path(d);(directory/'queue-B.txt').write_bytes(proposal.read_bytes())
  commands=[('private-lanequeue-plan',['/usr/bin/python3','-B',str(ops/'lane-queue/lanequeue.py'),'plan','--lane','B','--directory',str(directory)]),
            ('private-entry-plan',['/usr/bin/python3','-B',str(P/'run_micro.py'),'--plan']),
            ('private-report-adapter',['/usr/bin/python3','-B',str(P/'report_adapter.py')])]
  for name,argv in commands:
   stdout=P/'evidence'/(name+'.stdout');stderr=P/'evidence'/(name+'.stderr');outputs += [stdout,stderr]
   with stdout.open('w') as out,stderr.open('w') as err:
    result=subprocess.run(argv,env=launch_env.environment(),stdin=subprocess.DEVNULL,stdout=out,stderr=err)
   receipts.append(dict(name=name,returncode=result.returncode,device_executed=False))
   if result.returncode:raise RuntimeError(name+' failed: '+str(stderr))
 outputs += [P/'evidence/private-report.json',P/'rehearse.py']
 row=dict(passed=True,proposal_sha256=sha(proposal),records=receipts,sources={str(p.relative_to(ROOT)):sha(p) for p in outputs})
 (P/'evidence/private-rehearsal.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(receipts,indent=2))
if __name__=='__main__':main()
