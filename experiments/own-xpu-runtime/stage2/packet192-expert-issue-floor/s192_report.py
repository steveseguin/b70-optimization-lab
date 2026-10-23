"""Packet192 report (s192_report): issue-floor decomposition of the record expert kernels.

Device stream schema packet192.issue-floor.v1 (micro.cpp): bytes rows (exactness, strata cold/warm/real),
alias_selftest rows, sample rows (kernel, stratum, route, pass, repeat, warmup, start_ns, end_ns) and a
summary. Per kernel and stratum: n, median, p10, p90, mean (ns), per-pass medians; ratios warm/cold,
noload/warm, noload/cold; verdict per the coordinator ruling of 2026-10-23:
  warm ~ no-load within 10 %  -> "instruction-issue bound: only an instruction diet can move the class"
  no-load <= 0.75 x warm      -> "load-latency exposed: LSC prefetch is the candidate"
  otherwise                   -> "mixed"
Kill rules (result withheld, never ratio-corrected): any byte difference in an exactness stratum;
cold/warm control disagreement > 10 % between the two passes; any stratum with p90/median > 1.5.
CPU (cpu_only) streams are refused as device evidence. Never a speed result, never a record row.
"""
import hashlib,json,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
SCHEMA='packet192.issue-floor.v1'
KERNELS=('gateup','down')
STRATA={'gateup':('cold','warm','warm-real-layer0','warm-real-layer24','noload'),'down':('cold','warm','noload')}
EXACT={'gateup':('cold','warm','warm-real-layer0','warm-real-layer24'),'down':('cold','warm')}
ROUTES=384;COLD_REPEATS=20;WARM_REPEATS=200;PASSES=2;WARMUPS=5
ISSUE_BAND=0.10;LATENCY_RATIO=0.75;DRIFT_LIMIT=0.10;DISTURBANCE_LIMIT=1.5;FOLLOW_ON_RATIO=0.85
FLOOR_US={'gateup':20.079925512104282,'down':17.28148975791434}   # packet110 roofline.json expsgate/expsdown copy floors (537 GB/s)
ACT_US=5.41675                                                       # packet110 expsact (the separate activation launch)
PARENT_DATUM_US={'gateup_warm_real':48.3,'down_cold_tile16':46.041}  # packet162b analysis (layer0 48.334, layer24 47.917); packet100b micro-B down-tile16 cold median
FOLLOW_ON={'exp-diet':('gateup',0.0),'exp-act-epilogue':('gateup',ACT_US),'down-diet':('down',0.0)}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)
def quantile(values,q):
 s=sorted(values);i=min(len(s)-1,max(0,int(round(q*(len(s)-1)))));return s[i]
def stats(ns):
 return dict(n=len(ns),median_ns=statistics.median(ns),p10_ns=quantile(ns,0.10),p90_ns=quantile(ns,0.90),mean_ns=statistics.fmean(ns),min_ns=min(ns),max_ns=max(ns))
def analyze(rows):
 require(rows and isinstance(rows[-1],dict) and rows[-1].get('kind')=='summary','complete summary required')
 end=rows[-1];require(sum(r.get('kind')=='summary' for r in rows)==1,'one summary')
 require(end.get('schema')==SCHEMA,'stream schema is not '+SCHEMA)
 require(end.get('cpu_only') is False and end.get('mode')=='device','CPU (cpu_only) streams are never device evidence')
 require(all(end.get(k) is True for k in ('passed','drained','diagnostic_only','real_shapes')),'clean drained device stream with real shapes required')
 cold_repeats,warm_repeats=end.get('cold_repeats'),end.get('warm_repeats')
 require(end.get('route_count')==ROUTES and end.get('passes')==PASSES and type(cold_repeats) is int and cold_repeats>=1 and type(warm_repeats) is int and warm_repeats>=10,'identity: 384 routes, 2 passes, declared repeat counts')
 identity_as_proposed=(cold_repeats,warm_repeats)==(COLD_REPEATS,WARM_REPEATS)   # the window gate (run_micro.native_summary) enforces the proposed 20/200 on device streams
 require(all(r.get('kind') in ('start','allocation','bytes','alias_selftest','sample','summary') for r in rows),'unknown stream row')
 start=[r for r in rows if r.get('kind')=='start'];require(len(start)==1 and start[0].get('mode')=='device','device start row')
 kills=[];warnings=[]
 # exactness (kill rule 1): every exactness stratum byte-identical to the host-twin fixtures
 exact={}
 for r in (r for r in rows if r.get('kind')=='bytes'):
  require(r.get('kernel') in KERNELS and r.get('stratum') in STRATA[r['kernel']] and type(r.get('different_bytes')) is int and r.get('bytes_equal') is (r['different_bytes']==0),'bytes row format')
  key=(r['kernel'],r['stratum'],r['route']);require(key not in exact,'duplicate bytes row');exact[key]=r
 for kernel in KERNELS:
  for stratum in EXACT[kernel]:
   keys=[(kernel,stratum,i) for i in range(ROUTES)] if stratum=='cold' else [(kernel,stratum,-1)]
   missing=[k for k in keys if k not in exact];require(not missing,'exactness rows missing: '+str(missing[:3]))
   bad=[k for k in keys if not exact[k]['bytes_equal'] or exact[k].get('exactness_claim') is not True]
   if bad:kills.append(dict(rule='byte difference in an exactness stratum',kernel=kernel,stratum=stratum,routes=[k[2] for k in bad][:20],count=len(bad)))
  nl=exact.get((kernel,'noload',-1));require(nl is not None and nl.get('exactness_claim') is False,'no-load stratum must carry exactness_claim false')
  if nl['bytes_equal']:warnings.append(dict(note='no-load outputs equal production on a full route; alias had no effect?',kernel=kernel))
 alias={r['kernel']:r for r in rows if r.get('kind')=='alias_selftest'}
 for kernel in KERNELS:
  require(kernel in alias and alias[kernel].get('rows_per_route')==16,'alias self-test row required')
  if alias[kernel].get('bytes_equal') is not True:kills.append(dict(rule='alias self-test: no-load variant differs from production on a 16-row route',kernel=kernel))
 # timing
 groups={}
 for r in (r for r in rows if r.get('kind')=='sample'):
  require(r.get('kernel') in KERNELS and r.get('stratum') in STRATA[r['kernel']] and r.get('cpu_only') is False and r.get('diagnostic_only') is True,'sample row format')
  require(type(r.get('start_ns')) is int and type(r.get('end_ns')) is int and 0<r['start_ns']<r['end_ns'] and r.get('event_ns')==r['end_ns']-r['start_ns'],'event format')
  require(r.get('exact') is (r['stratum']!='noload'),'no-load samples must be marked exact false')
  if r.get('warmup') is True:continue
  if r['stratum']=='cold':require(r.get('scrub_bytes')==536870912 and 0<=r['route']<ROUTES,'cold samples need the 512 MiB scrub and a real route')
  else:require(r.get('scrub_bytes')==0 and r['route']==-1,'repeated strata have no scrub')
  groups.setdefault((r['kernel'],r['stratum'],r['pass']),[]).append(r['event_ns'])
 kernels={}
 for kernel in KERNELS:
  out={}
  for stratum in STRATA[kernel]:
   per_pass=[groups.get((kernel,stratum,p),[]) for p in range(PASSES)]
   expected=ROUTES*cold_repeats if stratum=='cold' else warm_repeats
   require(all(len(v)==expected for v in per_pass),f'{kernel}/{stratum}: {expected} timed samples per pass required, got {[len(v) for v in per_pass]}')
   allv=[x for v in per_pass for x in v];row=stats(allv);row['pass_median_ns']=[statistics.median(v) for v in per_pass]
   drift=abs(row['pass_median_ns'][0]-row['pass_median_ns'][1])/min(row['pass_median_ns']);row['pass_disagreement']=drift
   row['p90_over_median']=row['p90_ns']/row['median_ns'];row['median_us']=row['median_ns']/1000
   if stratum in ('cold','warm') and drift>DRIFT_LIMIT:kills.append(dict(rule='control disagreement > 10 % between the two passes',kernel=kernel,stratum=stratum,disagreement=drift))
   if row['p90_over_median']>DISTURBANCE_LIMIT:kills.append(dict(rule='p90/median > 1.5 (host disturbance)',kernel=kernel,stratum=stratum,p90_over_median=row['p90_over_median']))
   out[stratum]=row
  cold,warm,noload=(out[s]['median_ns'] for s in ('cold','warm','noload'))
  ratios=dict(warm_over_cold=warm/cold,noload_over_warm=noload/warm,noload_over_cold=noload/cold)
  if kernel=='gateup':ratios['real_layer0_over_warm']=out['warm-real-layer0']['median_ns']/warm;ratios['real_layer24_over_warm']=out['warm-real-layer24']['median_ns']/warm
  gap=abs(noload-warm)/warm
  verdict=('instruction-issue bound: only an instruction diet can move the class' if gap<=ISSUE_BAND else
           'load-latency exposed: LSC prefetch is the candidate' if noload<=LATENCY_RATIO*warm else 'mixed')
  decomposition=dict(dram_us=(cold-warm)/1000,load_latency_us=(warm-noload)/1000,issue_us=noload/1000,floor_us=FLOOR_US[kernel],excess_over_floor_us=cold/1000-FLOOR_US[kernel])
  kernels[kernel]=dict(strata=out,ratios=ratios,noload_vs_warm_gap=gap,verdict=verdict,decomposition_us=decomposition,
   follow_on_bars_us={name:dict(target='<= 0.85 x production in both A/B orders and every stratum (packet100 gate)',cold_bar_us=FOLLOW_ON_RATIO*(cold/1000+act),warm_bar_us=FOLLOW_ON_RATIO*(warm/1000+act),counted_against='kernel'+(' + expsact launch' if act else ''))
     for name,(k,act) in FOLLOW_ON.items() if k==kernel})
 layer=dict(gateup_cold_us=kernels['gateup']['strata']['cold']['median_us'],down_cold_us=kernels['down']['strata']['cold']['median_us'],
  class_cold_us=kernels['gateup']['strata']['cold']['median_us']+kernels['down']['strata']['cold']['median_us'],class_floor_us=FLOOR_US['gateup']+FLOOR_US['down'],act_us_packet110=ACT_US,
  note='one launch of each kernel per layer (both ranks run the same kernels); the activation launch is separate (packet110 expsact)')
 cross=dict(gateup_warm_real_layer0_over_packet162b=kernels['gateup']['strata']['warm-real-layer0']['median_us']/PARENT_DATUM_US['gateup_warm_real'],
  down_cold_over_packet100b_tile16=kernels['down']['strata']['cold']['median_us']/PARENT_DATUM_US['down_cold_tile16'],parent_datums_us=PARENT_DATUM_US)
 for k,v in list(cross.items())[:2]:
  if abs(v-1)>0.10:warnings.append(dict(note='harness disagrees with the parent datum by more than 10 % (informational, not a kill rule)',check=k,ratio=v))
 passed=not kills
 return dict(schema='packet192.issue-floor-report.v1',diagnostic_only=True,model_output_claim=False,speed_claim=False,passed=passed,kills=kills,warnings=warnings,
  verdict=('withheld: '+'; '.join(k['rule'] for k in kills)) if kills else 'measured',gateup_verdict=kernels['gateup']['verdict'] if passed else 'withheld',
  down_verdict=kernels['down']['verdict'] if passed else 'withheld',kernels=kernels,layer_equivalent_us=layer,cross_checks=cross,
  rule=dict(issue_band=ISSUE_BAND,latency_ratio=LATENCY_RATIO,drift_limit=DRIFT_LIMIT,disturbance_limit=DISTURBANCE_LIMIT,follow_on_ratio=FOLLOW_ON_RATIO,
   source='Expert kernel-floor study 2026-10-23 (coordinator ruling), packet100 micro gate 0.85, packet141 10 % control rule'),
  identity=dict(route_count=ROUTES,cold_repeats=cold_repeats,warm_repeats=warm_repeats,passes=PASSES,warmups_excluded=WARMUPS,identity_as_proposed=identity_as_proposed,proposed=dict(cold_repeats=COLD_REPEATS,warm_repeats=WARM_REPEATS),device=start[0].get('device'),device_peak_bytes=end.get('device_peak_bytes')))
def read_rows(path):return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
def markdown(result):
 lines=['# s192_report: expert kernel issue-floor decomposition (diagnostic, never a speed result)','',f"verdict: {result['verdict']}",'',
  '| kernel | cold us | warm us | no-load us | warm/cold | no-load/warm | verdict |','|---|---|---|---|---|---|---|']
 for k,v in result['kernels'].items():
  s=v['strata'];lines.append(f"| {k} | {s['cold']['median_us']:.2f} | {s['warm']['median_us']:.2f} | {s['noload']['median_us']:.2f} | {v['ratios']['warm_over_cold']:.3f} | {v['ratios']['noload_over_warm']:.3f} | {v['verdict']} |")
 lines+=['',f"layer-equivalent (cold): gate/up {result['layer_equivalent_us']['gateup_cold_us']:.2f} + down {result['layer_equivalent_us']['down_cold_us']:.2f} = {result['layer_equivalent_us']['class_cold_us']:.2f} us vs copy floor {result['layer_equivalent_us']['class_floor_us']:.2f} us",'',
  'follow-on bars (candidate must be <= 0.85 x production in both orders and every stratum):']
 for k,v in result['kernels'].items():
  for name,bar in v['follow_on_bars_us'].items():lines.append(f"- {name} ({k}): cold bar {bar['cold_bar_us']:.2f} us, warm bar {bar['warm_bar_us']:.2f} us ({bar['counted_against']})")
 if result['kills']:lines+=['','kill rules fired: '+json.dumps(result['kills'])]
 if result['warnings']:lines+=['','warnings: '+json.dumps(result['warnings'])]
 return '\n'.join(lines)+'\n'
def evaluate(directory):
 directory=Path(directory);path=directory/'samples.jsonl';result=analyze(read_rows(path));result['samples_sha256']=sha(path)
 (directory/'analysis.json').write_text(json.dumps(result,indent=2)+'\n');(directory/'s192_report.md').write_text(markdown(result))
 row=(f"| 2026-10-23 | packet192 issue-floor measurement (record gate/up + down kernels; cold/warm/no-load) | {result['verdict']}; gate/up: {result['gateup_verdict']}; down: {result['down_verdict']}; "
      f"evidence `{directory.name}/analysis.json` | per the study C: diet / LSC-prefetch candidate only as the verdict names; never a speed claim |\n")
 with (P/'DO-NOT-REPEAT.md').open('a') as f:f.write('\n## Packet192 device measurement\n\n| Date | Measurement | Result | Follow-on |\n| --- | --- | --- | --- |\n'+row)
 return result
def reference_data(parents):
 """Parent datums recomputed from the REAL parent streams read in place (packaging test; informational at device time)."""
 out={}
 for p in parents:
  path=P.parents[3]/p.get('parent_relpath','') if p.get('parent_relpath') else None
  if path is None or not path.is_file():continue
  if path.name=='samples.jsonl' and 'packet100b' in str(path):
   rows=read_rows(path);t=[r['event_ns'] for r in rows if r.get('kind')=='sample' and r.get('view')=='down-tile16'];tp=[r['event_ns'] for r in rows if r.get('kind')=='sample' and r.get('view')=='production']
   out['packet100b_down_tile16_cold_median_us']=statistics.median(t)/1000;out['packet100b_p65_production_cold_median_us']=statistics.median(tp)/1000;out['packet100b_samples']=len(t)+len(tp)
  if path.name=='analysis.json' and 'packet162' in str(path):
   d=json.loads(path.read_text());out['packet162b_gateup_warm_median_us']={s['shape']+'/'+str(s['fixture']):s['production_median_ns']/1000 for s in d['shapes']}
 return out
def synthetic_fixture(output,spec):
 """Invented packet192 stream for report rehearsal; never device evidence. spec medians in ns per kernel/stratum."""
 import random
 rng=random.Random(192);cold_repeats=spec.get('cold_repeats',COLD_REPEATS);warm_repeats=spec.get('warm_repeats',WARM_REPEATS)
 rows=[dict(kind='start',mode='device',device='synthetic',routes=ROUTES,cold_repeats=cold_repeats,warm_repeats=warm_repeats,passes=PASSES,warmups=WARMUPS)]
 mism=spec.get('byte_mismatch_routes',[]);alias_ok=spec.get('alias_ok',True);disturb=spec.get('disturb_stratum');drift=spec.get('pass_drift',0.0);cpu=spec.get('cpu_only',False)
 for kernel in KERNELS:
  for stratum in EXACT[kernel]:
   for route in (range(ROUTES) if stratum=='cold' else (-1,)):
    d=1 if (kernel,stratum,route) in {tuple(m) for m in mism} else 0
    rows.append(dict(kind='bytes',kernel=kernel,stratum=stratum,route=route,different_bytes=d,compared_bytes=25684,bytes_equal=d==0,exactness_claim=True))
  rows.append(dict(kind='bytes',kernel=kernel,stratum='noload',route=-1,different_bytes=1234,compared_bytes=25684,bytes_equal=False,exactness_claim=False))
  rows.append(dict(kind='alias_selftest',kernel=kernel,different_bytes=0 if alias_ok else 7,bytes_equal=alias_ok,rows_per_route=16))
 t=1_000_000
 for kernel in KERNELS:
  for stratum in STRATA[kernel]:
   median=spec[kernel][stratum]
   for p in range(PASSES):
    scale=1+drift if p==1 else 1
    for route in (range(ROUTES) if stratum=='cold' else (-1,)):
     reps=cold_repeats if stratum=='cold' else warm_repeats+WARMUPS
     for rep in range(reps):
      warm=stratum!='cold' and rep<WARMUPS
      ns=int(median*scale*(1+rng.uniform(-0.02,0.02)))
      if disturb is not None and list(disturb)==[kernel,stratum] and rep%5==0:ns=int(ns*2.5)
      rows.append(dict(kind='sample',kernel=kernel,stratum=stratum,route=route,**{'pass':p},repeat=rep if warm else rep-(WARMUPS if stratum!='cold' else 0),warmup=warm,start_ns=t,end_ns=t+ns,event_ns=ns,scrub_bytes=536870912 if stratum=='cold' else 0,exact=stratum!='noload',cpu_only=cpu,diagnostic_only=True));t+=ns+1000
 rows.append(dict(kind='summary',schema=SCHEMA,passed=True,drained=True,diagnostic_only=True,mode='host' if cpu else 'device',cpu_only=cpu,route_count=ROUTES,cold_repeats=cold_repeats,warm_repeats=warm_repeats,passes=PASSES,real_shapes=True,device_peak_bytes=1_108_913_492))
 Path(output).mkdir(parents=True,exist_ok=True);(Path(output)/'samples.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
if __name__=='__main__':
 import sys;print(json.dumps(evaluate(sys.argv[1]),indent=2))
