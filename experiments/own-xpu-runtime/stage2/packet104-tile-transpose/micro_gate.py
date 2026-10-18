"""Full-route, both-order 15% kernel-time gate; no model-speed claim."""
import json,math,statistics
from pathlib import Path
from build_engine import P,ROOT,sha,save
CANDIDATES=('target-gate-tile16','target-gate-halfcache-tile16','draft-gate-tile16','draft-down-tile16','shared-gate-up-tile16','shared-down-tile16','hc-gate-tile16')
MICRO_DIRECTORY='evidence/micro-B'
# rows, columns, count, experts, workgroup, number of strata (0 means routes)
SHAPES={
 'target-gate-tile16':(640,2560,10,512,64,0),
 'target-gate-halfcache-tile16':(640,2560,10,512,64,0),
 'draft-gate-tile16':(640,2560,10,512,128,0),
 'draft-down-tile16':(2560,640,10,512,128,0),
 'shared-gate-up-tile16':(640,2560,1,1,128,8),
 'shared-down-tile16':(2560,640,1,1,32,8),
 'hc-gate-tile16':(10240,320,1,1,256,8),
}
def require(ok,message):
 if not ok:raise ValueError(message)
def analyze(rows,route_count):
 require(type(route_count) is int and route_count==384,'real route count required')
 require(rows and rows[-1].get('kind')=='summary','complete summary required')
 end=rows[-1]
 require(sum(r.get('kind')=='summary' for r in rows)==1 and all(end.get(k) is True for k in ('passed','drained','diagnostic_only')),'clean drained micro required')
 require(end.get('candidate_count')==7 and end.get('route_count')==route_count,'complete candidate/route census required')
 cs=[r for r in rows if r.get('kind')=='correctness'];ss=[r for r in rows if r.get('kind')=='sample']
 expected=sum(v[5] or route_count for v in SHAPES.values());require(len(cs)==expected and len(ss)==80*expected,'complete correctness and timings required')
 groups={};seen=set()
 for r in cs:
  key=(r.get('route'),r.get('view'));require(key not in seen and key[1] in CANDIDATES and key[0] in range(SHAPES[key[1]][5] or route_count),'duplicate/foreign correctness');seen.add(key)
  require(all(r.get(k) is True for k in ('fp32_exact','bf16_exact','status_exact')),'device bytes differ')
  require((r.get('rows'),r.get('columns'),r.get('count'),r.get('experts'))==SHAPES[key[1]][:4],'wrong correctness shape')
 for r in ss:
  key=(r.get('route'),r.get('pair'));require(key in seen,'sample lacks correctness')
  groups.setdefault(key,[]).append(r)
 results={};qualified=[]
 for name in CANDIDATES:
  strata=[];all_control=[];all_candidate=[]
  for route in range(SHAPES[name][5] or route_count):
   subset=groups.get((route,name),[]);require(len(subset)==80,'40 complete alternating pairs per route required');times={'production':[],name:[]};ratios=[]
   for rep in range(40):
    pair=subset[2*rep:2*rep+2];values={}
    for pos,r in enumerate(pair):
     expected=name if pos^(rep&1) else 'production'
     require((r.get('repeat'),r.get('position'),r.get('view'))==(rep,pos,expected),'nonalternating/missing sample')
     require((r.get('rows'),r.get('columns'),r.get('count'),r.get('experts'),r.get('sg'),r.get('wg'),r.get('scrub_bytes'))==(*SHAPES[name][:4],32,SHAPES[name][4],536870912) and r.get('diagnostic_only') is True,'wrong geometry or cache preparation')
     ns=r.get('event_ns');require(type(ns) in (int,float) and math.isfinite(ns) and ns>0,'invalid event time');values[expected]=ns;times[expected].append(ns)
    ratios.append(values[name]/values['production'])
   ratio=statistics.median(times[name])/statistics.median(times['production']);orders=[statistics.median(ratios[i::2]) for i in (0,1)]
   strata.append(dict(route=route,time_ratio=ratio,order_time_ratios=orders,qualified=ratio<=0.85 and max(orders)<=0.85))
   all_control+=times['production'];all_candidate+=times[name]
  ratio=statistics.median(all_candidate)/statistics.median(all_control);passed=ratio<=0.85 and all(s['qualified'] for s in strata)
  results[name]=dict(time_ratio=ratio,route_strata=strata,qualified=passed,pairs_per_route=40)
  if passed and not name.startswith('draft-'):qualified.append(name)
 return dict(schema='packet104.micro-qualification.v1',draft_route_caveat='captured target routes replayed through draft; native draft-route qualification pending',passed=True,diagnostic_only=True,threshold=0.85,candidates=results,qualified=qualified)
