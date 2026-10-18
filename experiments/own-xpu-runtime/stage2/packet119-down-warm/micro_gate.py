"""Fail-closed paired-operator diagnostic; speed and exact bytes are separate gates."""
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
CANDIDATES=('p119',)
ROUTE_COUNT=384
THRESHOLD=.85
QUALIFICATION='evidence/micro-qualification.json'
def require(ok,message):
 if not ok:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def save(path,row):Path(path).write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
def verify_map(root,mapping):
 require(bool(mapping),'empty identity map')
 for name,digest in mapping.items():
  if isinstance(digest,dict):digest=digest['sha256']
  require(sha(Path(root)/name)==digest,'identity changed: '+name)
def positive(x):return type(x) in (float,int) and math.isfinite(x) and x>0

def analyze(rows):
 require(rows and sum(r.get('kind')=='summary' for r in rows)==1,'one complete native summary required')
 end=rows[-1]
 require(end.get('kind')=='summary' and all(end.get(k) is True for k in ('passed','drained','diagnostic_only')),'native run did not pass and drain')
 require(end.get('route_count')==ROUTE_COUNT and end.get('candidates')==list(CANDIDATES),'all384 routes required')
 correct,samples,cache={},{},{}
 device=None
 for row in rows[:-1]:
  kind=row.get('kind')
  if kind=='cache_device':
   require(device is None and row.get('capacity_measurement') is False and row.get('diagnostic_only') is True,'cache report mislabeled/duplicate')
   require(type(row.get('runtime_reported_global_cache_bytes')) is int and row['runtime_reported_global_cache_bytes']>0,'runtime cache size unavailable')
   device=row;continue
  if kind=='cache_probe':
   key=(row.get('bytes'),row.get('repeat'))
   require(key not in cache and key[0] in [x*1024**2 for x in (1,2,4,8,16,24,32,48,64)] and type(key[1]) is int and key[1] in range(8),'cache probe shape/duplicate')
   require(row.get('repetitions')==8 and row.get('scrub_bytes')==536870912 and row.get('stride_bytes')==64 and row.get('diagnostic_only') is True,'cache probe protocol')
   require(positive(row.get('cold_ns')) and positive(row.get('warm_ns')),'cache probe timing')
   cache[key]=row;continue
  route=row.get('route');require(type(route) is int and route in range(ROUTE_COUNT),'route out of range')
  if kind=='correctness':
   require(route not in correct and all(row.get(k) is True for k in ('all_bytes_exact','gate_exact','up_exact','activation_exact','down_exact','status_exact','control_exact')),'duplicate correctness or unequal output')
   correct[route]=row;continue
  require(kind=='sample','unknown native row')
  rep,pos=row.get('repeat'),row.get('position')
  require(type(rep) is int and rep in (0,1) and type(pos) is int and pos in (0,1),'alternating order index')
  require(row.get('view')==('p119' if pos^(rep&1) else 'production'),'wrong alternating order')
  require((row.get('rows_gate'),row.get('rows_down'),row.get('count'),row.get('experts'))==(640,2560,10,512),'wrong full-bank shape')
  require(row.get('scrub_bytes')==536870912 and row.get('scrub_between_operators') is False and row.get('diagnostic_only') is True,'cache protocol')
  require(row.get('all_bytes_exact') is True,'timed sample bytes differ')
  require(all(positive(row.get(k)) for k in ('gate_ns','activation_ns','down_ns','event_ns')),'bad timing')
  require(row['event_ns']==row['gate_ns']+row['down_ns'],'gate+down sum incorrect')
  key=route,rep,pos;require(key not in samples,'duplicate sample');samples[key]=row
 require(device is not None and len(cache)==72,'complete cache behavior probe missing')
 require(len(correct)==ROUTE_COUNT and len(samples)==ROUTE_COUNT*4,'missing route/order/bytes')
 order_ratios=[[],[]];ct=[];vt=[];actratios=[]
 for route in range(ROUTE_COUNT):
  for rep in (0,1):
   pair={samples[route,rep,pos]['view']:samples[route,rep,pos] for pos in (0,1)}
   a,b=pair['production'],pair['p119'];order_ratios[rep].append(b['event_ns']/a['event_ns']);ct.append(a['event_ns']);vt.append(b['event_ns'])
   actratios.append((b['event_ns']+b['activation_ns'])/(a['event_ns']+a['activation_ns']))
 order=[statistics.median(r) for r in order_ratios]
 aggregate=statistics.median(order_ratios[0]+order_ratios[1]);qualified=aggregate<=THRESHOLD and max(order)<=THRESHOLD
 cache_result=[]
 for size in sorted({k[0] for k in cache}):
  cold=statistics.median(cache[size,r]['cold_ns'] for r in range(8));warm=statistics.median(cache[size,r]['warm_ns'] for r in range(8))
  cache_result.append(dict(bytes=size,cold_median_ns=cold,warm_median_ns=warm,warm_cold_ratio=warm/cold))
 return dict(schema='packet119.micro-process-qualification.v1',passed=True,diagnostic_only=True,route_count=ROUTE_COUNT,
  qualified=['p119'] if qualified else [],candidates={'p119':dict(qualified=qualified,time_ratio=aggregate,order_time_ratios=order,production_event_ns=statistics.median(ct),candidate_event_ns=statistics.median(vt),including_activation_ratio_diagnostic=statistics.median(actratios))},
  threshold=dict(candidate_time_at_most_fraction=THRESHOLD,both_orders=True,all_routes_measured=True,aggregate='median matched route ratio of sum(expsgate+expsdown); each order also <=0.85'),
  cache=dict(device=device,behavior=cache_result,capacity_inferred=False,warm_budget=dict(lines_per_expert=min(14400,(device['runtime_reported_global_cache_bytes']//4*3)//10//64),bytes_per_token=min(14400,(device['runtime_reported_global_cache_bytes']//4*3)//10//64)*10*64,budget_rule='min(full DOWN footprint,75 percent of runtime-reported cache); rounded down to lines per10 experts',full_down_bytes_per_token=9216000,worst_two_token_union_bytes=18432000,execution='serial per-token gate/up then down; no simultaneously warm two-token union assumed')))

def validate_processes(windows):
 require(len(windows)==2,'two fresh process receipts required');identities=[]
 for repeat,row in enumerate(windows,1):
  require(row.get('repeat')==repeat and all(row.get(k) is True for k in ('passed','device_executed','drained','lease_released')),'clean numbered device window required')
  require(type(row.get('pid')) is int and row['pid']>0 and type(row.get('process_start_ticks')) is int and row['process_start_ticks']>0 and isinstance(row.get('boot_id'),str) and row['boot_id'],'process identity missing')
  require(type(row.get('started_utc_ns')) is int and type(row.get('finished_utc_ns')) is int and row['finished_utc_ns']>row['started_utc_ns'],'process wall interval missing')
  identities.append([row['boot_id'],row['pid'],row['process_start_ticks']])
 require(identities[0]!=identities[1],'same native process reused')
 require(windows[0]['finished_utc_ns']<=windows[1]['started_utc_ns'],'overlapping windows')
 return identities

def prerequisites(packet=P):
 packet=Path(packet);build=packet/'evidence/microbench-build.json'
 require(build.is_file(),'micro build pending');b=read(build)
 require(b.get('passed') is True and b.get('device_executed') is False,'micro build incomplete')
 verify_map(ROOT,b['sources']);verify_map(packet,b['artifacts'])
 require(b['artifacts'].get('build/microbench')==sha(packet/'build/microbench'),'unbound micro binary')
 cpu=packet/'evidence/cpu-byte-identity.json';isa=packet/'evidence/warm-isa.json'
 for path,label in ((cpu,'CPU bytes'),(isa,'retained warm ISA')):
  require(path.is_file(),label+' pending')
  report=read(path);require(report.get('passed') is True and report.get('device_executed') is False,label+' incomplete')
  verify_map(ROOT,report['sources'])
  if report.get('generated_sources'):verify_map(ROOT,report['generated_sources'])
 c=read(cpu);require(set(c.get('views',{}))=={'p119'},'CPU candidate coverage')
 view=c['views']['p119'];require(view.get('passed') is True and len(view.get('runs',[]))==4,'CPU four-process coverage')
 require({(r.get('compiler'),r.get('repeat')) for r in view['runs']}=={('GNU',1),('GNU',2),('Intel',1),('Intel',2)},'CPU compiler/repeat coverage')
 for run in view['runs']:
  require(run.get('passed') is True and run.get('device_executed') is False and run['expected_sha256']==run['candidate_sha256'],'CPU bytes differ')
  for key,digestkey in (('raw_evidence','raw_evidence_sha256'),('cases_path','cases_sha256'),('log_path','log_sha256')):require(sha(ROOT/run[key])==run[digestkey],'CPU evidence changed')
  require(hashlib.sha256(gzip.decompress((ROOT/run['raw_evidence']).read_bytes())).hexdigest()==run['candidate_sha256'],'CPU retained bytes changed')
 for compiler in c['compilers']:require(sha(ROOT/compiler['binary'])==compiler['binary_sha256'],'CPU binary changed')
 i=read(isa)
 if i.get('artifacts'):verify_map(packet,i['artifacts'])
 from route_inputs import read_inputs,MANIFEST,ROUTES
 route=read_inputs();require(route['micro_route_vectors']==ROUTE_COUNT and sha(ROUTES)==route['route_bytes_sha256'],'route capture changed')
 paths=(build,cpu,isa,Path(MANIFEST),Path(ROUTES),packet/'micro_gate.py',packet/'run_micro.py',packet/'route_inputs.py',packet/'drain_gate.py',packet/'exec_limits.py')
 return {str(path.relative_to(packet)):sha(path) for path in paths}

def one_process(packet,repeat,bindings):
 packet=Path(packet);directory=packet/f'evidence/micro-B-{repeat}';receipt,samples=directory/'window.json',directory/'samples.jsonl'
 require(receipt.is_file() and samples.is_file(),'micro process pending')
 window=read(receipt)
 require(window.get('repeat')==repeat and all(window.get(k) is True for k in ('passed','device_executed','drained','lease_released')),'clean window required')
 require(window.get('binary_sha256')==sha(packet/'build/microbench') and window.get('build_receipt_sha256')==bindings['evidence/microbench-build.json'],'micro build changed')
 require(window.get('prerequisite_bindings')==bindings and window.get('samples_sha256')==sha(samples),'run/source binding changed')
 result=analyze([json.loads(line) for line in samples.read_text().splitlines() if line.strip()]);result['bindings']={str(p.relative_to(packet)):sha(p) for p in (receipt,samples)};result['repeat']=repeat
 return result,window

def measured(packet=P):
 packet=Path(packet);bindings=prerequisites(packet);pairs=[one_process(packet,n,bindings) for n in (1,2)];identities=validate_processes([w for _,w in pairs]);results=[r for r,_ in pairs]
 qualified=['p119'] if all('p119' in r['qualified'] for r in results) else []
 for result in results:bindings.update(result['bindings'])
 return dict(schema='packet119.micro-qualification.v1',passed=True,diagnostic_only=True,qualified=qualified,processes=results,process_identities=identities,bindings=bindings)
def evaluate(packet=P,repeat=None):
 packet=Path(packet)
 if repeat is not None:
  result,_=one_process(packet,repeat,prerequisites(packet));save(packet/f'evidence/micro-B-{repeat}/qualification.json',result)
  if not all((packet/f'evidence/micro-B-{n}/window.json').is_file() for n in (1,2)):return dict(passed=False,pending=True,qualified=[],reason='second fresh process pending')
 result=measured(packet);save(packet/QUALIFICATION,result);return result
def require_qualified(packet=P):
 packet=Path(packet);path=packet/QUALIFICATION;require(path.is_file(),'two-process micro qualification pending')
 saved,fresh=read(path),measured(packet);require(saved==fresh,'qualification stale or altered');require(bool(fresh['qualified']),'p119 failed <=0.85 both orders/processes; v5 refused')
 return tuple(fresh['qualified'])

if __name__=='__main__':
 import argparse,resource
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--require-qualified',action='store_true',required=True)
 parser.parse_args()
 try:
  selected=require_qualified(P)
  print(json.dumps(dict(passed=True,qualified=list(selected))))
 except (ValueError,OSError,KeyError) as error:
  raise SystemExit('REFUSED: '+str(error))
