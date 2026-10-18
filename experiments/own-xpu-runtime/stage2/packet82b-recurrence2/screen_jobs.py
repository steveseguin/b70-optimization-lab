"""Either lane runs the grid; the other confirms its exact improving winner."""
import sys,math
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];WRAPPER=P.parent/'screen/v4-lanes'
sys.path.insert(0,str(WRAPPER))
from common import read,require,sha,verify_map
from cpu_seal import verify as verify_wrapper
from bundle_selection import VIEWS,ELIGIBLE

def verify():
 verify_wrapper();row=read(P/'screen-jobs-seal.json');verify_map(ROOT,row['sources'])
 require(row['wrapper_seal_sha256']==sha(WRAPPER/'wrapper-seal.json'),'shared wrapper changed')
 return row

def jobs(lane,choice=None,mode='grid'):
 require(lane in ('A','B') and mode in ('grid','confirm'),'lane/mode')
 selected=list(VIEWS)+['production'] if mode=='grid' else ['production',choice or ELIGIBLE[0],'production']
 require(mode=='grid' or selected[1] in ELIGIBLE,'confirmation candidate')
 result=[]
 for index,c in enumerate(selected):
  v=P/'compat/packet64-record-bundle/selections'/c
  result.append(dict(out=f'p82b-{lane}-{mode}-{index}-{c}',choice=c,lineage=str(v),seal=str(v/'screen-seal.json'),binary=str(v/'build/device/own-rt-iq3'),dispatch=str(v/'dispatch-speed6.json'),placement='1'))
 return result

def command(row,lane,review=None,plan=False):
 cmd=['/usr/bin/python3','-B',str(WRAPPER/'screen.py'),'--profile','tp2','--lane',lane,'--placement','1','--timing','token']
 for key in ('lineage','seal','binary','dispatch'):cmd+=['--'+key,row[key]]
 cmd+=['--output',str(WRAPPER/'evidence'/row['out'])]
 return cmd+(['--plan'] if plan else ['--fault-review',str(review),'--authorized-device-window'])

def choose(rows):
 require([r['choice'] for r in rows]==list(VIEWS)+['production'],'complete ordered grid required')
 require(all(r['exact'] for r in rows),'all 13 requests on every screen must match packet49')
 require(all(0<=r['acceptance']<=1 for r in rows),'acceptance required per screen')
 require(all(math.isfinite(r["rate"]) and r["rate"]>0 for r in rows),"invalid rate")
 best=max((r for r in rows[1:-1] if r['choice'] in ELIGIBLE),key=lambda r:r['rate'])
 require(best['rate']>max(r['rate'] for r in rows if r['choice'] not in ELIGIBLE),'no candidate beats both controls; confirmation withheld')
 return best

def winner(source_lane):
 from compare import load
 return choose([load(r,source_lane) for r in jobs(source_lane)])
