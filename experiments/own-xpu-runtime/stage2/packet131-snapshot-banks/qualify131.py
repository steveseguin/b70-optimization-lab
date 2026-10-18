"""Serial CPU preparation, no automatic retry and no device execution.

Run limits131.py separately from an uncapped CPU shell after this succeeds;
then queue131.py and ready131.py. Runtime imports never set process limits.
"""
import argparse,datetime,subprocess,sys
from build131 import P,save,cpu_main,limits
STAGES=('build131','census131','state131','extra131','mini131','startup131','python131','extended_queue131','inherited_gate131','oracle131','seal131','arguments131')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--start',choices=STAGES,default=STAGES[0]);a=ap.parse_args()
 attempt=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 rows=[]
 for stage in STAGES[STAGES.index(a.start):]:
  limits();log=P/'evidence'/f'{attempt}-{stage}.log'
  with log.open('w') as stream:
   cp=subprocess.run([sys.executable,'-B',str(P/(stage+'.py'))],stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
  rows.append(dict(stage=stage,returncode=cp.returncode,log=str(log.relative_to(P))))
  save(P/'evidence'/f'{attempt}-serial.json',dict(passed=all(r['returncode']==0 for r in rows),complete=len(rows)==len(STAGES)-STAGES.index(a.start),device_executed=False,stages=rows))
  print(stage,cp.returncode,flush=True)
  if cp.returncode:raise SystemExit(cp.returncode)
if __name__=='__main__':cpu_main();main()
