"""Hash-bound, fail-closed diagnostic threshold. Never a model-speed claim."""
import json,math,statistics
from pathlib import Path
from build_engine import P,ROOT,sha,save
CANDIDATES=('head-plane','head-transpose')
def require(ok,message):
 if not ok:raise ValueError(message)
def analyze(rows):
 require(sum(r.get('kind')=='summary' for r in rows)==1,'one complete micro summary required')
 end=rows[-1];require(end.get('kind')=='summary' and end.get('passed') is True and end.get('drained') is True and end.get('diagnostic_only') is True,'micro did not drain successfully')
 require((end.get('rows'),end.get('columns'))==(248320,2560),'full head shape required')
 correctness=[r for r in rows if r.get('kind')=='correctness']
 require([r.get('view') for r in correctness]==list(CANDIDATES),'both device correctness gates required')
 for r in correctness:
  require((r.get('rows'),r.get('columns'))==(248320,2560) and all(r.get(k) is True for k in ('fp32_exact','bf16_exact','argmax_exact')),'device head bytes differ')
 samples=[r for r in rows if r.get('kind')=='sample'];require(len(samples)==160,'complete 40 alternating pairs per candidate required')
 result={};qualified=[]
 for ci,name in enumerate(CANDIDATES):
  subset=samples[ci*80:(ci+1)*80];times={'production':[],name:[]};ratios=[]
  for rep in range(40):
   pair=subset[rep*2:rep*2+2]
   for pos,r in enumerate(pair):
    expected=name if pos^(rep&1) else 'production'
    require(r.get('pair')==name and r.get('view')==expected and r.get('repeat')==rep and r.get('position')==pos,'missing, duplicate or nonalternating sample')
    require((r.get('rows'),r.get('columns'),r.get('sg'),r.get('wg'))==(248320,2560,32,32) and r.get('diagnostic_only') is True,'wrong execution geometry')
    ns=r.get('event_ns');require(type(ns) in (int,float) and math.isfinite(ns) and ns>0,'invalid per-kernel event timing');times[expected].append(ns)
   values={r['view']:r['event_ns'] for r in pair};ratios.append(values[name]/values['production'])
  control=statistics.median(times['production']);candidate=statistics.median(times[name]);ratio=candidate/control
  # Stronger than throughput>=1.15: demand 15% less time. Both alternating
  # order halves must independently clear the same bar; no lucky ordering.
  by_order=[statistics.median(ratios[offset::2]) for offset in (0,1)]
  passed=ratio<=0.85 and max(by_order)<=0.85
  result[name]=dict(production_event_ns=control,candidate_event_ns=candidate,time_ratio=ratio,order_time_ratios=by_order,qualified=passed,pairs=40)
  if passed:qualified.append(name)
 return dict(schema='packet93.micro-qualification.v1',passed=True,diagnostic_only=True,threshold=dict(candidate_time_at_most_fraction=0.85,both_alternating_orders=True),candidates=result,qualified=qualified)
def measured(packet):
 packet=Path(packet);directory=packet/'evidence/micro-B';receipt=directory/'window.json';samples=directory/'samples.jsonl';build=packet/'evidence/microbench-build.json'
 for f in (receipt,samples,build):require(f.is_file(),'micro qualification pending: '+str(f))
 window=json.loads(receipt.read_text());identity=json.loads(build.read_text())
 require(all(window.get(k) is True for k in ('passed','device_executed','drained','lease_released')),'clean micro device window required')
 require(window.get('binary_sha256')==sha(packet/'build/microbench')==identity['artifacts']['build/microbench'],'micro binary changed')
 require(window.get('build_receipt_sha256')==sha(build) and window.get('samples_sha256')==sha(samples),'micro run evidence changed')
 require(identity.get('passed') is True and identity.get('device_executed') is False,'CPU-built micro identity required')
 for name,digest in identity['sources'].items():require(sha(ROOT/name)==digest,'micro source changed: '+name)
 result=analyze([json.loads(line) for line in samples.read_text().splitlines() if line.strip()])
 result['bindings']={str(f.relative_to(packet)):sha(f) for f in (receipt,samples,build,packet/'build-device-receipt.json',packet/'screen-jobs-seal.json',packet/'micro_gate.py')}
 return result
def evaluate(packet=P):
 result=measured(packet);save(Path(packet)/'evidence/micro-B/qualification.json',result);return result
def require_qualified(packet=P):
 packet=Path(packet);f=packet/'evidence/micro-B/qualification.json';require(f.is_file(),'micro qualification pending')
 saved=json.loads(f.read_text());fresh=measured(packet);require(saved==fresh,'micro qualification stale or altered');require(bool(fresh['qualified']),'no candidate passed 15% lower kernel time; screens refused')
 return tuple(fresh['qualified'])
