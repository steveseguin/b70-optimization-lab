"""CPU-only preparation of the first measured winner; never queues or runs GPUs."""
import json,shutil,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent

def main():
 from build_engine import limits,sha,save
 limits()
 from bracket_job import micro_winner
 winner=micro_winner()  # No configuration write before both fresh micros qualify.
 from cpu_seal import verify
 from bracket_config import prepare
 candidate=P/'lineage/candidate.json'
 current=json.loads(candidate.read_text())['choices']['expert_kernels']
 if current==winner:
  try:
   verify()
   print('Measured winner already has its exact selected-view CPU seal:',winner)
   return 0
  except (ValueError,FileNotFoundError):pass
 archive=P/'evidence'/('prior-selected-'+sha(candidate)[:16])
 if not archive.exists():
  archive.mkdir(parents=True)
  for sub in ('lineage','configs'):
   if (P/sub).exists():shutil.copytree(P/sub,archive/sub)
  for name in ('build','full-shape','reset-bytes','protocol','queue-plan'):
   path=P/'evidence'/(name+'.json')
   if path.exists():shutil.copy2(path,archive/path.name)
 prepare(winner)
 commands=[]
 operator=P.parent/'evidence/cpu-byte-identity.json'
 for name,args in (('full_shape.py',[]),('reset_gate.py',[]),('protocol_gate.py',[]),
                   ('cpu_seal.py',['--operator-evidence',str(operator)]),('queue_plan.py',[])):
  limits();cmd=[sys.executable,'-B',str(P/name),*args]
  subprocess.run(cmd,stdin=subprocess.DEVNULL,check=True,timeout=1200)
  commands.append(cmd)
 save(P/'evidence/winner-preparation.json',dict(passed=True,device_executed=False,winner=winner,commands=commands,live_queue_modified=False,archive=str(archive)))
 print('Measured winner CPU-prepared and temporary plan checked:',winner)
 return 0

if __name__=='__main__':raise SystemExit(main())
