"""Packet193 report (s193_report): exact instruction-diet micro of the record expert kernels.

Device stream schema packet193.diet.v1 (micro.cpp): bytes rows (candidate, kernel, stratum, route, against
production|fixture, exactness_claim), sample rows (candidate, arm production|candidate, kernel, stratum, route,
pass 0 = order AB / pass 1 = order BA, repeat, warmup, start_ns, end_ns, event_ns, gateup_ns, act_ns, gap_ns) and a
summary. Per candidate and stratum: production and candidate medians (p10/p90) per order, ratios in both orders,
the <= 0.85 x verdict per stratum (coordinator ruling 2026-10-23 / packet100 micro gate), us per layer-equivalent
saved (cold stratum), projected record-line gains (two cards: +1.32 % per 0.01 ms per GDN layer on both ranks;
one card: 11.4 us/layer = +2 %). Kill rules (never ratio-corrected): any byte difference in an exactness stratum
withholds that candidate; production (control) cold/warm disagreement with packet192 > 10 % and any stratum
p90/median > 1.5 withhold the whole verdict. CPU (cpu_only) streams and packet192's stream are refused.
Never a speed result for the engine, never a record row.
"""
import hashlib,json,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
SCHEMA='packet193.diet.v1'
CANDIDATES={'exp-diet':'gateup','exp-act-epilogue':'gateup','down-diet':'down'}
TIMING={'gateup':('cold','warm','warm-real-layer0','warm-real-layer24'),'down':('cold','warm')}
EXACT={'gateup':('cold','warm','warm-real-layer0','warm-real-layer24','fixture-f0-valid','fixture-f0-invalid','fixture-f1-valid','fixture-f1-invalid','fixture-f2-valid','fixture-f2-invalid','exceptional'),
       'down':('cold','warm','fixture-f0-valid','fixture-f0-invalid','fixture-f1-valid','fixture-f1-invalid','fixture-f2-valid','fixture-f2-invalid','exceptional')}
EPILOGUE_EXTRA=('inactive','error-preset')
DIAGNOSTIC={('exp-act-epilogue','exceptional')}   # NaN payload-order diagnostic on the non-finite-scale bank (README 2.3)
ROUTES=384;COLD_REPEATS=20;WARM_REPEATS=200;PASSES=2;WARMUPS=5;ORDERS={0:'AB',1:'BA'}
GATE=0.85;CONTROL_LIMIT=0.10;DISTURBANCE_LIMIT=1.5
# packet192 evidence/issue-floor-B1/analysis.json (lane B, card 2, 2026-10-23): production control datums in us
PACKET192_US={'gateup':dict(cold=73.75,warm=46.354),'down':dict(cold=45.938,warm=33.75)}
ACT_US_PACKET110=5.41675
TWO_CARD_PCT_PER_US=1.32/10.0   # +1.32 % per 0.01 ms per GDN layer (both ranks)
ONE_CARD_PCT_PER_US=2.0/11.4    # 11.4 us/layer = +2 %
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)
def quantile(values,q):
 s=sorted(values);i=min(len(s)-1,max(0,int(round(q*(len(s)-1)))));return s[i]
def stats(ns):
 return dict(n=len(ns),median_ns=statistics.median(ns),p10_ns=quantile(ns,0.10),p90_ns=quantile(ns,0.90),mean_ns=statistics.fmean(ns),min_ns=min(ns),max_ns=max(ns),median_us=statistics.median(ns)/1000)
def analyze(rows):
 require(rows and isinstance(rows[-1],dict) and rows[-1].get('kind')=='summary','complete summary required')
 end=rows[-1];require(sum(r.get('kind')=='summary' for r in rows)==1,'one summary')
 require(end.get('schema')==SCHEMA,'stream schema is not '+SCHEMA)
 require(end.get('cpu_only') is False and end.get('mode')=='device','CPU (cpu_only) streams are never device evidence')
 require(all(end.get(k) is True for k in ('passed','drained','diagnostic_only','real_shapes')),'clean drained device stream with real shapes required')
 require(end.get('candidates')==list(CANDIDATES),'three declared candidates')
 cold_repeats,warm_repeats,routes=end.get('cold_repeats'),end.get('warm_repeats'),end.get('route_count')
 require(end.get('passes')==PASSES and type(cold_repeats) is int and cold_repeats>=1 and type(warm_repeats) is int and warm_repeats>=10 and type(routes) is int and 1<=routes<=ROUTES,'identity: routes, 2 passes, declared repeat counts')
 identity_as_proposed=(routes,cold_repeats,warm_repeats)==(ROUTES,COLD_REPEATS,WARM_REPEATS)   # the window gate (run_micro.native_summary) enforces 384/20/200 on device streams
 require(all(r.get('kind') in ('start','allocation','bytes','sample','summary') for r in rows),'unknown stream row')
 start=[r for r in rows if r.get('kind')=='start'];require(len(start)==1 and start[0].get('mode')=='device','device start row')
 kills=[];warnings=[];candidate_kills={c:[] for c in CANDIDATES}
 # exactness: every claimed row equal; the fixed expected row set must be complete
 exact={}
 for r in (r for r in rows if r.get('kind')=='bytes'):
  require(r.get('candidate') in list(CANDIDATES)+['production'] and r.get('kernel') in ('gateup','down') and isinstance(r.get('stratum'),str) and r.get('against') in ('fixture','production') and type(r.get('different_bytes')) is int and r.get('bytes_equal') is (r['different_bytes']==0) and type(r.get('exactness_claim')) is bool,'bytes row format')
  key=(r['candidate'],r['kernel'],r['stratum'],r['route'],r['against']);require(key not in exact,'duplicate bytes row');exact[key]=r
 def keys_for(candidate,kernel,against):
  out=[]
  for stratum in EXACT[kernel]:
   if candidate=='production' and against!='fixture':continue
   out+=[(candidate,kernel,stratum,i,against) for i in range(routes)] if stratum=='cold' else [(candidate,kernel,stratum,-1,against)]
  if candidate=='exp-act-epilogue' and against=='production':out+=[(candidate,kernel,s,-1,against) for s in EPILOGUE_EXTRA]
  return out
 exactness={}
 for candidate in ['production']+list(CANDIDATES):
  for kernel in (('gateup','down') if candidate=='production' else (CANDIDATES[candidate],)):
   for against in (('fixture',) if candidate=='production' else ('production','fixture')):
    keys=keys_for(candidate,kernel,against);missing=[k for k in keys if k not in exact];require(not missing,'exactness rows missing: '+str(missing[:3]))
    claimed=[k for k in keys if (candidate,k[2]) not in DIAGNOSTIC];bad=[k for k in claimed if not exact[k]['bytes_equal'] or exact[k]['exactness_claim'] is not True]
    payload_only=bool(bad) and all(exact[k].get('payload_order_only') is True for k in bad)
    diag=[dict(stratum=k[2],different_bytes=exact[k]['different_bytes'],compared_bytes=exact[k]['compared_bytes'],bytes_equal=exact[k]['bytes_equal']) for k in keys if (candidate,k[2]) in DIAGNOSTIC]
    for k in keys:
     if (candidate,k[2]) in DIAGNOSTIC:require(exact[k]['exactness_claim'] is False,'diagnostic row must not claim exactness')
    exactness.setdefault(candidate,{})[kernel+'/'+against]=dict(rows=len(keys),claimed=len(claimed),equal=len(claimed)-len(bad),diagnostic=diag)
    if bad:
     kill=dict(rule='byte difference in an exactness stratum'+(' (NaN payload order only: every differing word is NaN on both sides; no value difference)' if payload_only else ' (value difference)'),candidate=candidate,kernel=kernel,against=against,strata=sorted({k[2] for k in bad})[:6],count=len(bad),payload_order_only=payload_only)
     if candidate=='production':kills.append(kill)
     else:candidate_kills[candidate].append(kill)
 # timing
 groups={}
 for r in (r for r in rows if r.get('kind')=='sample'):
  require(r.get('candidate') in CANDIDATES and r.get('arm') in ('production','candidate') and r.get('kernel')==CANDIDATES[r['candidate']] and r.get('stratum') in TIMING[r['kernel']] and r.get('cpu_only') is False and r.get('diagnostic_only') is True and r.get('exact') is True,'sample row format')
  require(type(r.get('start_ns')) is int and type(r.get('end_ns')) is int and 0<r['start_ns']<r['end_ns'] and r.get('event_ns')==r['end_ns']-r['start_ns'] and r.get('pass') in (0,1) and r.get('order')==ORDERS[r['pass']],'event format')
  if r.get('warmup') is True:continue
  if r['stratum']=='cold':require(r.get('scrub_bytes')==536870912 and 0<=r['route']<routes,'cold samples need the 512 MiB scrub and a real route')
  else:require(r.get('scrub_bytes')==0 and r['route']==-1,'repeated strata have no scrub')
  groups.setdefault((r['candidate'],r['stratum'],r['arm'],r['pass']),[]).append(r)
 candidates={}
 for candidate,kernel in CANDIDATES.items():
  strata={}
  for stratum in TIMING[kernel]:
   expected=routes*cold_repeats if stratum=='cold' else warm_repeats
   orders={}
   for p in (0,1):
    prod=groups.get((candidate,stratum,'production',p),[]);cand=groups.get((candidate,stratum,'candidate',p),[])
    require(len(prod)==expected and len(cand)==expected,f'{candidate}/{stratum}/{ORDERS[p]}: {expected} timed samples per arm required, got {len(prod)}/{len(cand)}')
    ps=stats([r['event_ns'] for r in prod]);cs=stats([r['event_ns'] for r in cand])
    row=dict(production=ps,candidate=cs,ratio=cs['median_ns']/ps['median_ns'],passed=cs['median_ns']<=GATE*ps['median_ns'])
    if candidate=='exp-act-epilogue':
     row['production_parts_us']=dict(gateup=statistics.median([r['gateup_ns'] for r in prod])/1000,act=statistics.median([r['act_ns'] for r in prod])/1000,gap=statistics.median([r['gap_ns'] for r in prod])/1000)
    for arm,s in (('production',ps),('candidate',cs)):
     s['p90_over_median']=s['p90_ns']/s['median_ns']
     if s['p90_over_median']>DISTURBANCE_LIMIT:kills.append(dict(rule='p90/median > 1.5 (host disturbance)',candidate=candidate,stratum=stratum,order=ORDERS[p],arm=arm,p90_over_median=s['p90_over_median']))
    orders[ORDERS[p]]=row
   ratios=[orders[o]['ratio'] for o in ('AB','BA')]
   prod_med=statistics.fmean(orders[o]['production']['median_us'] for o in ('AB','BA'));cand_med=statistics.fmean(orders[o]['candidate']['median_us'] for o in ('AB','BA'))
   strata[stratum]=dict(orders=orders,ratio_AB=ratios[0],ratio_BA=ratios[1],worst_ratio=max(ratios),passed=all(orders[o]['passed'] for o in ('AB','BA')),
    production_median_us=prod_med,candidate_median_us=cand_med,saved_us=prod_med-cand_med,bar_us=GATE*prod_med)
  # control cross-check vs packet192 (plain gate/up for the gate/up candidates: the epilogue's control includes the act launch)
  control={}
  for stratum in ('cold','warm'):
   if candidate=='exp-act-epilogue':
    measured=statistics.fmean(strata[stratum]['orders'][o]['production_parts_us']['gateup'] for o in ('AB','BA'))
   else:measured=strata[stratum]['production_median_us']
   ref=PACKET192_US[kernel][stratum];dev=abs(measured-ref)/ref;control[stratum]=dict(measured_us=measured,packet192_us=ref,deviation=dev)
   if dev>CONTROL_LIMIT:kills.append(dict(rule='control disagreement with packet192 > 10 %',candidate=candidate,stratum=stratum,measured_us=measured,packet192_us=ref,deviation=dev))
  saved=strata['cold']['saved_us']
  verdict=('withheld: '+'; '.join(k['rule'] for k in candidate_kills[candidate])) if candidate_kills[candidate] else ('qualified: <= 0.85 x production in both orders and every stratum' if all(s['passed'] for s in strata.values()) else 'closed: above 0.85 x production in '+', '.join(f"{n} ({s['ratio_AB']:.3f}/{s['ratio_BA']:.3f})" for n,s in strata.items() if not s['passed']))
  candidates[candidate]=dict(kernel=kernel,strata=strata,control_vs_packet192=control,kills=candidate_kills[candidate],verdict=verdict,
   layer_equivalent=dict(saved_us_cold=saved,saved_us_warm=strata['warm']['saved_us'],projected_two_card_pct=saved*TWO_CARD_PCT_PER_US,projected_one_card_pct=saved*ONE_CARD_PCT_PER_US,
    note='one launch per layer per kernel; the epilogue saving counts the removed expsact launch (its event time and the inter-launch gap are reported in production_parts_us)'))
 best_gate=max(('exp-diet','exp-act-epilogue'),key=lambda c:candidates[c]['layer_equivalent']['saved_us_cold'] if 'qualified' in candidates[c]['verdict'] else float('-inf'))
 combo=sum(candidates[c]['layer_equivalent']['saved_us_cold'] for c in (best_gate,'down-diet') if 'qualified' in candidates[c]['verdict'])
 combined=dict(qualified=[c for c in CANDIDATES if 'qualified' in candidates[c]['verdict']],gateup_pick=best_gate if 'qualified' in candidates[best_gate]['verdict'] else None,saved_us_cold=combo,projected_two_card_pct=combo*TWO_CARD_PCT_PER_US,projected_one_card_pct=combo*ONE_CARD_PCT_PER_US)
 passed=not kills
 return dict(schema='packet193.diet-report.v1',diagnostic_only=True,model_output_claim=False,speed_claim=False,passed=passed,kills=kills,warnings=warnings,
  verdict=('withheld: '+'; '.join(sorted({k['rule'] for k in kills}))) if kills else 'measured',candidates=candidates if passed else {c:dict(candidates[c],verdict='withheld') for c in candidates},
  combined=combined if passed else dict(qualified=[],gateup_pick=None,saved_us_cold=0.0,projected_two_card_pct=0.0,projected_one_card_pct=0.0),exactness=exactness,
  rule=dict(gate=GATE,control_limit=CONTROL_LIMIT,disturbance_limit=DISTURBANCE_LIMIT,packet192_controls_us=PACKET192_US,act_us_packet110=ACT_US_PACKET110,two_card_pct_per_us=TWO_CARD_PCT_PER_US,one_card_pct_per_us=ONE_CARD_PCT_PER_US,
   source='coordinator ruling 2026-10-23 (packet193 brief); packet100 micro gate 0.85; packet141 10 % control rule'),
  identity=dict(route_count=routes,cold_repeats=cold_repeats,warm_repeats=warm_repeats,passes=PASSES,warmups_excluded=WARMUPS,identity_as_proposed=identity_as_proposed,proposed=dict(routes=ROUTES,cold_repeats=COLD_REPEATS,warm_repeats=WARM_REPEATS),device=start[0].get('device'),device_peak_bytes=end.get('device_peak_bytes')))
def read_rows(path):return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
def markdown(result):
 lines=['# s193_report: exact instruction-diet micro of the record expert kernels (diagnostic, never an engine speed result)','',f"verdict: {result['verdict']}",'',
  '| candidate | stratum | production us (p10/p90) | candidate us (p10/p90) | ratio A/B | ratio B/A | <= 0.85 |','|---|---|---|---|---|---|---|']
 for c,v in result['candidates'].items():
  for n,s in v['strata'].items():
   pa,ca=s['orders']['AB']['production'],s['orders']['AB']['candidate']
   lines.append(f"| {c} | {n} | {s['production_median_us']:.2f} ({pa['p10_ns']/1000:.2f}/{pa['p90_ns']/1000:.2f}) | {s['candidate_median_us']:.2f} ({ca['p10_ns']/1000:.2f}/{ca['p90_ns']/1000:.2f}) | {s['ratio_AB']:.3f} | {s['ratio_BA']:.3f} | {'yes' if s['passed'] else 'no'} |")
 lines+=['','| candidate | verdict | saved us/layer (cold) | two-card projection | one-card projection |','|---|---|---|---|---|']
 for c,v in result['candidates'].items():
  le=v['layer_equivalent'];lines.append(f"| {c} | {v['verdict']} | {le['saved_us_cold']:.2f} | {le['projected_two_card_pct']:+.2f} % | {le['projected_one_card_pct']:+.2f} % |")
 cb=result['combined'];lines+=['',f"combined (gate/up pick {cb['gateup_pick']} + down-diet, qualified only): {cb['saved_us_cold']:.2f} us/layer -> two cards {cb['projected_two_card_pct']:+.2f} %, one card {cb['projected_one_card_pct']:+.2f} %"]
 for c,v in result['candidates'].items():
  ctl=v.get('control_vs_packet192',{})
  if ctl:lines.append(f"- control {c}: cold {ctl['cold']['measured_us']:.2f} vs packet192 {ctl['cold']['packet192_us']:.2f} ({ctl['cold']['deviation']*100:.1f} %), warm {ctl['warm']['measured_us']:.2f} vs {ctl['warm']['packet192_us']:.2f} ({ctl['warm']['deviation']*100:.1f} %)")
 if result['kills']:lines+=['','kill rules fired: '+json.dumps(result['kills'])]
 if result['warnings']:lines+=['','warnings: '+json.dumps(result['warnings'])]
 return '\n'.join(lines)+'\n'
def evaluate(directory):
 directory=Path(directory);path=directory/'samples.jsonl';result=analyze(read_rows(path));result['samples_sha256']=sha(path)
 (directory/'analysis.json').write_text(json.dumps(result,indent=2)+'\n');(directory/'s193_report.md').write_text(markdown(result))
 rows=''.join(f"| 2026-10-23 | packet193 {c} ({v['kernel']}) exact instruction-diet micro, lane B | {result['verdict']}; {v['verdict']}; cold ratio A/B {v['strata']['cold']['ratio_AB']:.3f} / B/A {v['strata']['cold']['ratio_BA']:.3f}, saved {v['layer_equivalent']['saved_us_cold']:.2f} us/layer; evidence `{directory.name}/analysis.json` | qualified -> exact one-load v5 bracket on the record selection (study C chain of evidence); closed -> do not repeat this diet form |\n" for c,v in result['candidates'].items())
 with (P/'DO-NOT-REPEAT.md').open('a') as f:f.write('\n## Packet193 device measurement\n\n| Date | Candidate | Result | Follow-on |\n| --- | --- | --- | --- |\n'+rows)
 return result
def synthetic_fixture(output,spec):
 """Invented packet193 stream for report rehearsal; never device evidence. spec: per candidate the production and
 candidate medians in ns per stratum (candidate ratio), optional routes/cold_repeats/warm_repeats, byte_mismatch
 [[candidate,kernel,stratum]], disturb [candidate,stratum], control_scale (production scaled), cpu_only."""
 import random
 rng=random.Random(193);routes=spec.get('routes',ROUTES);cold_repeats=spec.get('cold_repeats',COLD_REPEATS);warm_repeats=spec.get('warm_repeats',WARM_REPEATS);cpu=spec.get('cpu_only',False)
 rows=[dict(kind='start',mode='device',device='synthetic',routes=routes,cold_repeats=cold_repeats,warm_repeats=warm_repeats,passes=PASSES,warmups=WARMUPS,candidates=list(CANDIDATES))]
 mism={tuple(m) for m in spec.get('byte_mismatch',[])};disturb=spec.get('disturb');scale=spec.get('control_scale',1.0)
 for kernel in ('gateup','down'):
  for stratum in EXACT[kernel]:
   for route in (range(routes) if stratum=='cold' else (-1,)):
    rows.append(dict(kind='bytes',candidate='production',kernel=kernel,stratum=stratum,route=route,against='fixture',different_bytes=0,compared_bytes=38484,bytes_equal=True,different_words=0,nan_vs_nan_words=0,other_bytes=0,payload_order_only=False,exactness_claim=True,cpu_only=cpu))
 for candidate,kernel in CANDIDATES.items():
  for stratum in EXACT[kernel]+(EPILOGUE_EXTRA if candidate=='exp-act-epilogue' else ()):
   for route in (range(routes) if stratum=='cold' else (-1,)):
    for against in ('production','fixture'):
     if stratum in EPILOGUE_EXTRA and against=='fixture':continue
     diag=(candidate,stratum) in DIAGNOSTIC;d=2334 if diag else (1 if (candidate,kernel,stratum) in mism else 0)
     rows.append(dict(kind='bytes',candidate=candidate,kernel=kernel,stratum=stratum,route=route,against=against,different_bytes=d,compared_bytes=38484,bytes_equal=d==0,different_words=d,nan_vs_nan_words=d if diag else 0,other_bytes=0,payload_order_only=bool(d) and diag,exactness_claim=not diag,cpu_only=cpu))
 t=1_000_000
 for candidate,kernel in CANDIDATES.items():
  for stratum in TIMING[kernel]:
   base=spec[candidate][stratum];prod_ns=int(base['production']*scale);cand_ns=int(prod_ns*base['ratio'])
   for p in (0,1):
    for route in (range(routes) if stratum=='cold' else (-1,)):
     reps=cold_repeats if stratum=='cold' else warm_repeats+WARMUPS
     for rep in range(reps):
      warm=stratum!='cold' and rep<WARMUPS
      for which in (0,1):
       arm='production' if (which==0)==(p==0) else 'candidate';med=prod_ns if arm=='production' else cand_ns
       ns=int(med*(1+rng.uniform(-0.02,0.02)))
       if disturb is not None and list(disturb)==[candidate,stratum] and rep%5==0:ns=int(ns*2.5)
       act=int(ns*0.07) if (candidate=='exp-act-epilogue' and arm=='production') else 0
       rows.append(dict(kind='sample',candidate=candidate,arm=arm,kernel=kernel,stratum=stratum,route=route,**{'pass':p},order=ORDERS[p],repeat=rep if warm else rep-(WARMUPS if stratum!='cold' else 0),warmup=warm,start_ns=t,end_ns=t+ns,event_ns=ns,gateup_ns=ns-act,act_ns=act,gap_ns=3000 if act else 0,scrub_bytes=536870912 if stratum=='cold' else 0,exact=True,cpu_only=cpu,diagnostic_only=True));t+=ns+1000
 rows.append(dict(kind='summary',schema=SCHEMA,passed=True,drained=True,diagnostic_only=True,mode='host' if cpu else 'device',cpu_only=cpu,route_count=routes,cold_repeats=cold_repeats,warm_repeats=warm_repeats,passes=PASSES,real_shapes=True,stress_rows=0,candidates=list(CANDIDATES),device_peak_bytes=1_130_000_000))
 Path(output).mkdir(parents=True,exist_ok=True);(Path(output)/'samples.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
if __name__=='__main__':
 import sys;print(json.dumps(evaluate(sys.argv[1]),indent=2))
