"""Offline device event gate. CPU receipts can test parsing, never prove speed."""
import json,statistics,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
SHAPES=('layer0','layer24')

def check_bytes(rows,shapes=SHAPES):
 checks=[r for r in rows if r.get('kind')=='bytes']
 expected=[(s,f,b) for s in shapes for f in range(3) for b in range(2)]
 assert [(r.get('shape'),r.get('fixture'),r.get('invalid')) for r in checks]==expected,'byte stream incomplete/duplicate'
 for r in checks:
  assert type(r['different_bytes']) is int and 0<=r['different_bytes']<=25684
  assert r['bytes_equal'] is (r['different_bytes']==0)
 return all(r['bytes_equal'] for r in checks if r['fixture']<2),[r for r in checks if r['fixture']==2]

def analyze(rows):
 assert rows[-1]==dict(kind='summary',passed=True,drained=True,rows=640,columns=2560,diagnostic_only=True),'incomplete run'
 assert sum(r.get('kind')=='summary' for r in rows)==1
 assert all(r.get('kind') in ('summary','sample','bytes') for r in rows)
 exact,nan=check_bytes(rows);samples=[r for r in rows if r.get('kind')=='sample']
 assert len(samples)==2*2*200*2,'200 complete A/B pairs per shape/finite fixture required'
 result=[];i=0
 for shape in SHAPES:
  for fixture in range(2):
   times=[[],[]];ratios=[]
   for rep in range(200):
    for arm in range(2):
     r=samples[i];i+=1
     assert (r['shape'],r['fixture'],r['repeat'],r['arm'])==(shape,fixture,rep,arm),'A/B sequence'
     assert type(r['start_ns']) is int and type(r['end_ns']) is int and 0<r['start_ns']<r['end_ns'],'event format'
     times[arm].append(r['end_ns']-r['start_ns'])
    ratios.append(times[1][-1]/times[0][-1])
   ratio=statistics.median(times[1])/statistics.median(times[0])
   result.append(dict(shape=shape,fixture=fixture,production_median_ns=statistics.median(times[0]),candidate_median_ns=statistics.median(times[1]),median_device_time_ratio=ratio,paired_ratio_median=statistics.median(ratios)))
 fast=all(r['median_device_time_ratio']<=.85 for r in result)
 decision='reopen: NaN parity + full build' if fast and exact else 'close: device speed > 0.85' if not fast else 'blocked: finite output bytes differ'
 return dict(diagnostic_only=True,model_output_claim=False,finite_bytes_equal=exact,nan_input_behavior=nan,shapes=result,decision=decision,full_build_authorized=False)

def evaluate(directory):
 directory=Path(directory);path=directory/'samples.jsonl';result=analyze([json.loads(s) for s in path.read_text().splitlines()]);result['samples_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
 (directory/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
 if result['decision']=='close: device speed > 0.85':
  row='| 2026-10-19 | Packet162b 11-bit device decoder | Final closure: at least one complete finite stratum exceeds 0.85× production device time; NaN repair has no qualifying speed case. Evidence: `'+str((directory/'analysis.json').relative_to(P))+'` | Do not repeat this decoder. |\n'
  with (P/'DO-NOT-REPEAT.md').open('a') as f:f.write('\n## Packet162b final device decision\n\n| Date | Arm | Result | Revisit |\n| --- | --- | --- | --- |\n'+row)
 return result
if __name__=='__main__':
 import sys
 print(json.dumps(evaluate(sys.argv[1]),indent=2))
