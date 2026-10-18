"""Fail-closed two-process HC timing gate; synthetic diagnostic, never promotion."""
import hashlib,json,math,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
QUALIFICATION='evidence/micro-qualification.json'
def require(ok,why):
 if not ok:raise ValueError(why)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def analyze(native):
 native=Path(native); r=read(native/'receipt.json')
 require(r.get('schema')=='ownrt.packet117.layer.v1' and r.get('passed') is True and r.get('safe_to_exit') is True and r.get('device_executed') is True and r.get('cpu_mock') is False,'native exact/device/drain receipt required')
 require(r.get('timing_pair_checks')==100 and r.get('checks',0)>800,'complete QSA/GDN exact byte gates required')
 comparisons=native/'comparisons.jsonl'; require(sha(comparisons)==r['exact_output_identity'],'exact capture identity changed')
 checks=[json.loads(x) for x in comparisons.read_text().splitlines()]
 require(checks and all(x.get('equal') is True and x.get('bytes',0)>0 and x.get('sha256') for x in checks),'producer/full-state byte comparisons required')
 rows=[json.loads(x) for x in (native/'iterations.jsonl').read_text().splitlines()]
 require(len(rows)==200,'two layers, 50 paired iterations required')
 seen=set(); groups={}
 for index,row in enumerate(rows):
  layer,it,mode=row['layer'],row['iteration'],row['mode'];key=(layer,it,mode)
  require(key not in seen and layer in (3,4) and it in range(50) and mode in ('production','p117'),'duplicate or unknown sample')
  seen.add(key)
  require(row['warmup']==(it<10) and row['position']==127 and row['occupied_context']==128,'fixed context/warmup required')
  # Within each layer the first member alternates by iteration, independently
  # checked from file order. No one-order winner can qualify.
  expected='p117' if (index%2==0)==(it%2==0) else 'production'
  require(mode==expected,'paired arm order changed')
  events=row['events'];require(events and len(events)==row['submissions'],'complete event coverage')
  sums={}
  for e in events:
   dt=e['end_ns']-e['start_ns'];require(0<dt<=4_000_000_000,'invalid event duration')
   sums[e['class']]=sums.get(e['class'],0)+dt
  require(sums==row['classes_ns'] and sum(sums.values())==row['gpu_ns'],'class totals disagree with events')
  for cls in ('hc.a.gate','hc.f.gate'):
   # Class labels in Engine are unprefixed (same as packet110 roofline).
   require(cls in sums,'missing HC class')
   if it>=10:groups.setdefault((layer,cls,it%2,mode),[]).append(sums[cls])
 require(len(seen)==200,'sample completeness')
 results=[]
 for layer in (3,4):
  for cls in ('hc.a.gate','hc.f.gate'):
   for order in (0,1):
    control=groups[(layer,cls,order,'production')];candidate=groups[(layer,cls,order,'p117')]
    require(len(control)==len(candidate)==20,'20 samples per order required')
    a,b=statistics.median(control),statistics.median(candidate)
    results.append(dict(layer=layer,site=cls,order='p117-first' if order==0 else 'production-first',production_ns=a,p117_ns=b,ratio=b/a,passed=b<=.7*a))
 return dict(passed=all(x['passed'] for x in results),threshold=.7,diagnostic_only=True,rows=results,
  native_hashes={n:sha(native/n) for n in ('receipt.json','iterations.jsonl','comparisons.jsonl','exact-capture-manifest.json')})
def measured(packet=P):
 packet=Path(packet)
 # Local wrapper build_gate verifies frozen object, source, binary, CPU evidence,
 # wrapper and seal hashes again, independently of recorded passed booleans.
 import run_micro
 require(packet.resolve()==P,'only sealed local packet accepted')
 identity=run_micro.build_gate();processes=[];ids=[];bindings={}
 for repeat in (1,2):
  directory=packet/f'evidence/micro-B-{repeat}';window=read(directory/'window.json')
  require(all(window.get(k) is True for k in ('passed','device_executed','drained','lease_released')),'clean drained micro window required')
  require(window.get('owner')==str(repeat) and window.get('identity')==identity,'numbered process/build identity changed')
  require(window.get('samples_sha256')==sha(directory/'samples.jsonl'),'sample log changed')
  require(window.get('device_isolation',{}).get('passed') is True and window.get('physical_cards')==[2],'single-card B isolation required')
  result=analyze(directory/'native');require(window['native_summary']['hc_gate_analysis']==result,'native receipts changed after run')
  ids.append([window['boot_id'],window['pid'],window['process_start_ticks']]);processes.append(result)
  for n in ('window.json','samples.jsonl'):bindings[str((directory/n).relative_to(packet))]=sha(directory/n)
 require(ids[0]!=ids[1],'two fresh native processes required')
 return dict(schema='packet117.micro-qualification.v1',passed=all(x['passed'] for x in processes),qualified=['p117'] if all(x['passed'] for x in processes) else [],diagnostic_only=True,threshold=.7,processes=processes,process_identities=ids,bindings=bindings)
def evaluate(packet=P):
 packet=Path(packet)
 if not all((packet/f'evidence/micro-B-{r}/window.json').is_file() for r in (1,2)):return dict(passed=False,pending=True)
 result=measured(packet);(packet/QUALIFICATION).write_text(json.dumps(result,indent=2)+'\n');return result
def require_qualified(packet=P):
 packet=Path(packet);saved=read(packet/QUALIFICATION);fresh=measured(packet)
 require(saved==fresh,'micro qualification stale or altered')
 require(fresh['passed'] and fresh['qualified']==['p117'],'HC kill gate failed: v5 refused')
 return ('p117',)
if __name__=='__main__':
 import sys
 if sys.argv[1:]==['--require-qualified']:print(json.dumps(dict(passed=True,qualified=require_qualified())))
 elif not sys.argv[1:]:print(json.dumps(evaluate(),indent=2))
 else:raise SystemExit('usage: micro_gate.py [--require-qualified]')
