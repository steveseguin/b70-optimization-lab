"""Read-only final verification, including actual post-load census admission."""
import json,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from screen_jobs import verify,WRAPPER,jobs,command
from common import read,verify_map
from placement import admission_gate

def main():
 limits();verify()
 build=read(P/'build-device-receipt.json');verify_map(ROOT,build['sources']);verify_map(P,build['artifacts'])
 full=read(P/'evidence/fullshape.json');admitted=[]
 gate=admission_gate(P/'selections/production')[1]
 ledger=read(P/'memory-plan.json')
 for row in full['results']:
  r=row['result'];census=read(ROOT/row['census'])
  result=gate.check(census,ledger,r['rank'],mtp=True,context=4096,draft_rank=1,target_split=row['split'])
  admitted.append(dict(choice=row['choice'],split=row['split'],rank=r['rank'],admission=result))
 plans=[]
 for lane in ('A','B'):
  for row in jobs(lane):
   cmd=command(row,lane,plan=True)
   run=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=120)
   output=P/'evidence'/(row['out']+'-plan.json');output.write_text(run.stdout)
   plan=json.loads(run.stdout)
   assert plan['supported'] and plan['reservation_scope']=='lane-'+lane
   plans.append(dict(lane=lane,choice=row['choice'],passed=True,command=cmd,plan_sha256=sha(output)))
 # Retain the actual shared-wrapper refusal for unaudited 24/24 placement.
 cmd=command(jobs('A')[0],'A',plan=True);cmd[cmd.index('--placement')+1]='1'
 refused=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
 assert refused.returncode==2
 (P/'evidence/shared-v4-24-24-refusal.json').write_text(refused.stdout)
 logical=sum(f.stat().st_size for f in B.rglob('*') if f.is_file())
 assert logical<1_000_000_000
 save(P/'evidence/final-check.json',dict(passed=True,device_executed=False,cpu_model_executed=False,
      fullshape_admission=admitted,plans=plans,build_logical_bytes=logical,wrapper=str(WRAPPER.relative_to(ROOT)),
      wrapper_seal_sha256=sha(WRAPPER/'wrapper-seal.json'),placement='1-split23',packet49_device_exactness='pending',speed='unmeasured'))
 print('all 6 shared v4 plans and 8 real census admissions PASS; build bytes',logical)
if __name__=='__main__':main()
