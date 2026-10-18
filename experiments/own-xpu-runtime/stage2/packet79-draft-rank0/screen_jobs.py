"""Shared pinned v4 screens; lane B admits only the exact best lane-A view."""
import json,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];WRAPPER=P.parent/'screen/v4-lanes'
sys.path.insert(0,str(WRAPPER))
from common import read,require,sha,verify_map
from cpu_seal import verify as verify_wrapper
from bootstrap import install
install()
VIEWS=('1','0-split23','0')
def verify():
 verify_wrapper();row=read(P/'screen-jobs-seal.json');verify_map(ROOT,row['sources'])
 require(row['wrapper_seal_sha256']==sha(WRAPPER/'wrapper-seal.json'),'shared wrapper changed')
 return row
def jobs(lane,choice=None):
 require(lane in ('A','B'),'lane')
 selected=list(VIEWS)+['1'] if lane=='A' else ['1',choice or '0-split23','1']
 require(lane=='A' or selected[1] in VIEWS[1:],'lane B candidate')
 result=[]
 for index,c in enumerate(selected):
  v=P/'selections'/(c+'--production')
  result.append(dict(out=f'p79-{lane}-{index}-{c}',choice=c,lineage=str(v),seal=str(v/'screen-seal.json'),binary=str(v/'build/device/own-rt-iq3'),dispatch=str(v/'dispatch-speed6.json'),placement=c))
 return result
def command(row,lane,review=None,plan=False):
 cmd=['/usr/bin/python3','-B',str(P/'run_screen.py'),'--profile','tp2','--lane',lane,'--placement',row['placement'],'--timing','token']
 for key in ('lineage','seal','binary','dispatch'):cmd+=['--'+key,row[key]]
 cmd+=['--output',str(WRAPPER/'evidence'/row['out'])]
 return cmd+(['--plan'] if plan else ['--fault-review',str(review),'--authorized-device-window'])
def choose(rows):
 require([r['choice'] for r in rows]==list(VIEWS)+['1'],'complete ordered lane A grid required')
 require(all(r['exact'] for r in rows),'all 13 requests on every A screen must match packet49')
 candidates=rows[1:-1];best=max(candidates,key=lambda r:r['rate'])
 require(best['rate']>max(rows[0]['rate'],rows[-1]['rate']),'no candidate beats both fresh controls; lane B withheld')
 return best
def winner():
 from compare import load
 return choose([load(r,'A') for r in jobs('A')])
