"""Either lane grids; the other admits only its exact improving winner."""
import json,sys,math
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];WRAPPER=P.parent/'screen/v4-lanes'
sys.path.insert(0,str(WRAPPER))
from common import read,require,sha,verify_map
from cpu_seal import verify as verify_wrapper
from bundle_selection import VIEWS
def verify():
 verify_wrapper();row=read(P/'screen-jobs-seal.json');verify_map(ROOT,row['sources'])
 require(row['wrapper_seal_sha256']==sha(WRAPPER/'wrapper-seal.json'),'shared wrapper changed')
 return row
DIRECTIONS=('A-grid','B-grid')
def lanes(direction='A-grid'):
 require(direction in DIRECTIONS,'direction')
 return ('A','B') if direction=='A-grid' else ('B','A')
def jobs(lane,choice=None,direction='A-grid'):
 require(lane in ('A','B'),'lane')
 source,confirm=lanes(direction)
 selected=list(VIEWS)+['production'] if lane==source else ['production',choice or 'exp-halfcache','production']
 require(lane==source or selected[1] in VIEWS[1:],'confirmation candidate')
 result=[]
 for index,c in enumerate(selected):
  v=P/'compat/packet64-record-bundle/selections'/c
  result.append(dict(out=f'p90-{direction}-{lane}-{index}-{c}',choice=c,lineage=str(v),seal=str(v/'screen-seal.json'),binary=str(v/'build/device/own-rt-iq3'),dispatch=str(v/'dispatch-speed6.json'),placement='1'))
 return result
def command(row,lane,review=None,plan=False):
 cmd=['/usr/bin/python3','-B',str(WRAPPER/'screen.py'),'--profile','tp2','--lane',lane,'--placement','1','--timing','token']
 for key in ('lineage','seal','binary','dispatch'):cmd+=['--'+key,row[key]]
 cmd+=['--output',str(WRAPPER/'evidence'/row['out'])]
 return cmd+(['--plan'] if plan else ['--fault-review',str(review),'--authorized-device-window'])
def choose(rows):
 require([r['choice'] for r in rows]==list(VIEWS)+['production'],'complete ordered source-lane grid required')
 require(all(r['exact'] for r in rows),'all 13 requests on every grid screen must match packet49')
 require(all(math.isfinite(r['rate']) and r['rate']>0 for r in rows),'invalid rate')
 require(all(r['acceptance_counts']==rows[0]['acceptance_counts'] for r in rows),'per-prompt target/draft acceptance changed; no winner')
 candidates=rows[1:-1];best=max(candidates,key=lambda r:r['rate'])
 require(best['rate']>max(rows[0]['rate'],rows[-1]['rate']),'no candidate beats both fresh controls; confirmation withheld')
 return best
def winner(direction='A-grid'):
 from compare import load
 source,_=lanes(direction)
 return choose([load(r,source) for r in jobs(source,direction=direction)])
