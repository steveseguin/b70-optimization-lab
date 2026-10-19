"""Private qualification: lanequeue plan on temp copies (A and B), real entry plans, report adapter."""
import json,subprocess,tempfile
from pathlib import Path
from build_engine import P,ROOT,limits,sha
import launch_env
import run_micro


def main():
 limits();ops=P.parents[1]/'ops'
 receipts=[];outputs=[]
 with tempfile.TemporaryDirectory(prefix='packet175b-plan-') as d:
  commands=[]
  for lane,proposal in run_micro.PROPOSALS.items():
   directory=Path(d)/lane;directory.mkdir();(directory/('queue-'+lane+'.txt')).write_bytes(proposal.read_bytes())
   commands.append(('private-lanequeue-plan-'+lane,['/usr/bin/python3','-B',str(ops/'lane-queue/lanequeue.py'),'plan','--lane',lane,'--directory',str(directory)]))
   commands.append(('private-entry-plan-'+lane,['/usr/bin/python3','-B',str(P/'run_micro.py'),'--plan','--lane',lane]))
  commands.append(('private-report-adapter',['/usr/bin/python3','-B',str(P/'report_adapter.py')]))
  for name,argv in commands:
   stdout=P/'evidence'/(name+'.stdout');stderr=P/'evidence'/(name+'.stderr');outputs += [stdout,stderr]
   with stdout.open('w') as out,stderr.open('w') as err:
    result=subprocess.run(argv,env=launch_env.environment(),stdin=subprocess.DEVNULL,stdout=out,stderr=err)
   receipts.append(dict(name=name,returncode=result.returncode,device_executed=False))
   if result.returncode:raise RuntimeError(name+' failed: '+str(stderr))
 outputs += [P/'evidence/private-report.json',P/'rehearse.py']
 digests={lane:sha(path) for lane,path in run_micro.PROPOSALS.items()}
 row=dict(passed=True,proposal_sha256=digests,records=receipts,sources={str(p.relative_to(ROOT)):sha(p) for p in outputs})
 (P/'evidence/private-rehearsal.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(receipts,indent=2))
if __name__=='__main__':main()
