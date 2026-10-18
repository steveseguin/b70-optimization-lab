"""Full-route, both-order 15% kernel-time gate; no model-speed claim."""
import json,math,statistics
from pathlib import Path
from build_engine import P,ROOT,sha,save
CANDIDATES=('down-interleave','down-tile16')
MICRO_DIRECTORY='evidence/micro-B'
def require(ok,message):
 if not ok:raise ValueError(message)
def analyze(rows,route_count):
 require(type(route_count) is int and 0<route_count<=1152,'real route count required')
 require(rows and rows[-1].get('kind')=='summary','complete summary required')
 end=rows[-1]
 require(sum(r.get('kind')=='summary' for r in rows)==1 and all(end.get(k) is True for k in ('passed','drained','diagnostic_only')),'clean drained micro required')
 require((end.get('rows'),end.get('columns'),end.get('count'),end.get('experts'),end.get('route_count'))==(2560,640,10,512,route_count),'full DOWN shape/route count required')
 cs=[r for r in rows if r.get('kind')=='correctness'];ss=[r for r in rows if r.get('kind')=='sample']
 require(len(cs)==2*route_count and len(ss)==160*route_count,'complete route correctness and timings required')
 groups={};seen=set()
 for r in cs:
  key=(r.get('route'),r.get('view'));require(key not in seen and key[0] in range(route_count) and key[1] in CANDIDATES,'duplicate/foreign correctness');seen.add(key)
  require(all(r.get(k) is True for k in ('fp32_exact','bf16_exact','status_exact')),'device bytes differ')
  require((r.get('rows'),r.get('columns'),r.get('count'),r.get('experts'))==(2560,640,10,512),'wrong correctness shape')
 for r in ss:
  key=(r.get('route'),r.get('pair'));require(key in seen,'sample lacks correctness')
  groups.setdefault(key,[]).append(r)
 results={};qualified=[]
 for name in CANDIDATES:
  strata=[];all_control=[];all_candidate=[]
  for route in range(route_count):
   subset=groups.get((route,name),[]);require(len(subset)==80,'40 complete alternating pairs per route required');times={'production':[],name:[]};ratios=[]
   for rep in range(40):
    pair=subset[2*rep:2*rep+2];values={}
    for pos,r in enumerate(pair):
     expected=name if pos^(rep&1) else 'production'
     require((r.get('repeat'),r.get('position'),r.get('view'))==(rep,pos,expected),'nonalternating/missing sample')
     require((r.get('rows'),r.get('columns'),r.get('count'),r.get('experts'),r.get('sg'),r.get('wg'),r.get('scrub_bytes'))==(2560,640,10,512,32,64,536870912) and r.get('diagnostic_only') is True,'wrong geometry or cache preparation')
     ns=r.get('event_ns');require(type(ns) in (int,float) and math.isfinite(ns) and ns>0,'invalid event time');values[expected]=ns;times[expected].append(ns)
    ratios.append(values[name]/values['production'])
   ratio=statistics.median(times[name])/statistics.median(times['production']);orders=[statistics.median(ratios[i::2]) for i in (0,1)]
   strata.append(dict(route=route,time_ratio=ratio,order_time_ratios=orders,qualified=ratio<=0.85 and max(orders)<=0.85))
   all_control+=times['production'];all_candidate+=times[name]
  ratio=statistics.median(all_candidate)/statistics.median(all_control);passed=ratio<=0.85 and all(s['qualified'] for s in strata)
  results[name]=dict(time_ratio=ratio,route_strata=strata,qualified=passed,pairs_per_route=40)
  if passed:qualified.append(name)
 return dict(schema='packet100.micro-qualification.v1',passed=True,diagnostic_only=True,threshold=0.85,candidates=results,qualified=qualified)
def measured(packet=P):
 import route_inputs
 packet=Path(packet);routes=route_inputs.require_ready();directory=packet/MICRO_DIRECTORY
 files=[directory/'window.json',directory/'samples.jsonl',packet/'evidence/microbench-build.json']
 for f in files:require(f.is_file(),'micro pending: '+str(f))
 window=json.loads(files[0].read_text());build=json.loads(files[2].read_text())
 require(all(window.get(k) is True for k in ('passed','device_executed','drained','lease_released')) and not window.get('stop_reasons') and not window.get('child_still_running'),'clean device window required')
 require(window['binary_sha256']==sha(packet/'build/microbench')==build['artifacts']['build/microbench'],'binary changed')
 require(window['build_receipt_sha256']==sha(files[2]) and window['samples_sha256']==sha(files[1]),'evidence changed')
 require(window['identity']['route_manifest_sha256']==sha(P/'evidence/route-inputs.json') and window['identity']['route_bytes_sha256']==routes['route_bytes_sha256'],'route identity changed')
 require(build['passed'] and not build['device_executed'],'CPU build required')
 for f,h in build['sources'].items():require(sha(ROOT/f)==h,'source changed: '+f)
 count=(P/'evidence/routes.bin').stat().st_size//120
 result=analyze([json.loads(l) for l in files[1].read_text().splitlines() if l.strip()],count)
 result['bindings']={str(f.relative_to(packet)):sha(f) for f in [*files,packet/'evidence/route-inputs.json',packet/'evidence/routes.bin',packet/'micro_gate.py',packet/'screen-jobs-seal.json']}
 return result
def evaluate(packet=P):
 result=measured(packet);save(Path(packet)/MICRO_DIRECTORY/'qualification.json',result);return result
def require_qualified(packet=P):
 f=Path(packet)/MICRO_DIRECTORY/'qualification.json';require(f.is_file(),'real-route micro qualification pending')
 result=measured(packet);require(json.loads(f.read_text())==result,'qualification changed');require(result['qualified'],'no candidate passes 15% lower time across every route and order');return tuple(result['qualified'])
