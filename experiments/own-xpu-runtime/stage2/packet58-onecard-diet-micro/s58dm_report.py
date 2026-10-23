"""Packet58-onecard-diet-micro report (s58dm_report): exact instruction-diet micro of the ONE-card record gate/up kernel.

Device stream schema packet58dm.diet.v1 (micro.cpp): bytes rows (candidate, stratum, route, against
production|fixture|indirect|direct-permuted, exactness_claim / nan_claim / nan_equal), sample rows (candidate p58-diet
or control, arm production|candidate, stratum, route, pass 0 = order AB / pass 1 = order BA / order P for the fresh
production-only control, repeat, warmup, start_ns, end_ns, event_ns) and a summary. Per stratum: production and
candidate medians (p10/p90) per order, ratios in both orders, the <= 0.85 x verdict (coordinator ruling 2026-10-23);
us per layer saved (cold and warm); the one-card projection (11.4 us/layer = +2 %). Kill rules (never ratio-corrected):
any byte difference in a claimed stratum (value difference) withholds the candidate; a NaN-payload-order-only
difference on a NaN-only stratum is recorded, never a kill (packet193's lesson); production cold/warm disagreement
with the fresh production-only control pass > 10 % and any stratum p90/median > 1.5 withhold the whole verdict.
CPU (cpu_only) streams and packet193's two-card stream are refused. Never a speed result for the engine, never a
record row.
"""
import hashlib,json,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
SCHEMA='packet58dm.diet.v1'
CANDIDATE='p58-diet';CANDIDATES=[CANDIDATE]
TIMING=('cold','warm','warm-direct','warm-real-layer0','warm-real-layer24')
GATED=('cold','warm')                        # the ruling's bar: <= 0.85 x production cold AND warm, both orders
CONTROL=('cold','warm')                      # fresh production-only pass after the interleaved timing
EXACT=('cold','warm','warm-direct','slots-reverse','slots-shuffled','warm-real-layer0','warm-real-layer24','fixture-f0-valid','fixture-f0-invalid','fixture-f1-valid','fixture-f1-invalid')
NAN_ONLY=('fixture-f2-valid','fixture-f2-invalid','exceptional')   # compared by is-NaN per word; diagnostic, never bytes
ROUTES=384;COLD_REPEATS=20;WARM_REPEATS=200;PASSES=2;WARMUPS=5;SLOT_ROUTES=8;ORDERS={0:'AB',1:'BA'}
GATE=0.85;CONTROL_LIMIT=0.10;DISTURBANCE_LIMIT=1.5
ONE_CARD_PCT_PER_US=2.0/11.4    # coordinator: 11.4 us/layer = +2 % on the one-card record line (48 serial layer bodies)
PACKET193_TWO_CARD=dict(cold_ratio=0.784,warm_ratio=0.77,saved_us_cold=15.9,saved_us_warm=10.8)   # provenance only
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
 require(end.get('candidates')==CANDIDATES,'one declared candidate')
 cold_repeats,warm_repeats,routes=end.get('cold_repeats'),end.get('warm_repeats'),end.get('route_count')
 require(end.get('passes')==PASSES and type(cold_repeats) is int and cold_repeats>=1 and type(warm_repeats) is int and warm_repeats>=10 and type(routes) is int and SLOT_ROUTES<=routes<=ROUTES,'identity: routes, 2 passes, declared repeat counts')
 identity_as_proposed=(routes,cold_repeats,warm_repeats)==(ROUTES,COLD_REPEATS,WARM_REPEATS)
 require(all(r.get('kind') in ('start','allocation','bytes','sample','summary') for r in rows),'unknown stream row')
 start=[r for r in rows if r.get('kind')=='start'];require(len(start)==1 and start[0].get('mode')=='device','device start row')
 kills=[];warnings=[];candidate_kills=[]
 exact={}
 for r in (r for r in rows if r.get('kind')=='bytes'):
  require(r.get('candidate') in (CANDIDATE,'production') and r.get('kernel')=='gateup' and isinstance(r.get('stratum'),str) and r.get('against') in ('fixture','production','indirect','direct-permuted') and type(r.get('different_bytes')) is int and r.get('bytes_equal') is (r['different_bytes']==0) and type(r.get('exactness_claim')) is bool and type(r.get('nan_claim')) is bool and r['exactness_claim']!=r['nan_claim'] and type(r.get('nan_equal')) is bool,'bytes row format')
  require(r['nan_claim']==(r['stratum'] in NAN_ONLY),'claim label must follow the stratum')
  key=(r['candidate'],r['stratum'],r['route'],r['against']);require(key not in exact,'duplicate bytes row');exact[key]=r
 def keys_for(candidate,against):
  out=[]
  for stratum in EXACT+NAN_ONLY:
   if stratum=='cold':out+=[(candidate,stratum,i,against) for i in range(routes)]
   elif stratum.startswith('slots-'):out+=[(candidate,stratum,i,against) for i in range(SLOT_ROUTES)]
   else:out.append((candidate,stratum,-1,against))
  return out
 exactness={};payload_order=[]
 checks=[('production','fixture'),(CANDIDATE,'production'),(CANDIDATE,'fixture'),('production','indirect'),('production','direct-permuted')]
 for candidate,against in checks:
  if against=='indirect':keys=[('production','warm-direct',-1,'indirect')]
  elif against=='direct-permuted':keys=[('production',s,i,'direct-permuted') for s in ('slots-reverse','slots-shuffled') for i in range(SLOT_ROUTES)]
  else:keys=keys_for(candidate,against)
  missing=[k for k in keys if k not in exact];require(not missing,'exactness rows missing: '+str(missing[:3]))
  claimed=[k for k in keys if k[1] not in NAN_ONLY];nan=[k for k in keys if k[1] in NAN_ONLY]
  bad=[k for k in claimed if not exact[k]['bytes_equal']];nan_bad=[k for k in nan if not exact[k]['nan_equal']]
  payload_order+=[dict(candidate=candidate,against=against,stratum=k[1],nan_vs_nan_words=exact[k]['nan_vs_nan_words']) for k in nan if exact[k]['nan_equal'] and not exact[k]['bytes_equal']]
  exactness[candidate+'/'+against]=dict(rows=len(keys),claimed=len(claimed),equal=len(claimed)-len(bad),nan_rows=len(nan),nan_equal=len(nan)-len(nan_bad))
  for group,rule in ((bad,'byte difference in a claimed stratum (value difference)'),(nan_bad,'value difference or status/error byte in a NaN-only stratum')):
   if group:
    kill=dict(rule=rule,candidate=candidate,against=against,strata=sorted({k[1] for k in group})[:6],count=len(group))
    (kills if candidate=='production' else candidate_kills).append(kill)
 groups={}
 for r in (r for r in rows if r.get('kind')=='sample'):
  require(r.get('candidate') in (CANDIDATE,'control') and r.get('arm') in ('production','candidate') and r.get('kernel')=='gateup' and r.get('stratum') in TIMING and r.get('cpu_only') is False and r.get('diagnostic_only') is True and r.get('exact') is True,'sample row format')
  require(type(r.get('start_ns')) is int and type(r.get('end_ns')) is int and 0<r['start_ns']<r['end_ns'] and r.get('event_ns')==r['end_ns']-r['start_ns'] and r.get('pass') in (0,1),'event format')
  if r['candidate']=='control':require(r['arm']=='production' and r.get('order')=='P' and r['pass']==0 and r['stratum'] in CONTROL,'control rows are production-only, order P')
  else:require(r.get('order')==ORDERS[r['pass']],'order label')
  if r.get('warmup') is True:continue
  if r['stratum']=='cold':require(r.get('scrub_bytes')==536870912 and 0<=r['route']<routes,'cold samples need the 512 MiB scrub and a real route')
  else:require(r.get('scrub_bytes')==0 and r['route']==-1,'repeated strata have no scrub')
  groups.setdefault((r['candidate'],r['stratum'],r['arm'],r['pass']),[]).append(r)
 strata={}
 for stratum in TIMING:
  expected=routes*cold_repeats if stratum=='cold' else warm_repeats
  orders={}
  for p in (0,1):
   prod=groups.get((CANDIDATE,stratum,'production',p),[]);cand=groups.get((CANDIDATE,stratum,'candidate',p),[])
   require(len(prod)==expected and len(cand)==expected,f'{stratum}/{ORDERS[p]}: {expected} timed samples per arm required, got {len(prod)}/{len(cand)}')
   ps=stats([r['event_ns'] for r in prod]);cs=stats([r['event_ns'] for r in cand])
   row=dict(production=ps,candidate=cs,ratio=cs['median_ns']/ps['median_ns'],passed=cs['median_ns']<=GATE*ps['median_ns'])
   for arm,s in (('production',ps),('candidate',cs)):
    s['p90_over_median']=s['p90_ns']/s['median_ns']
    if s['p90_over_median']>DISTURBANCE_LIMIT:kills.append(dict(rule='p90/median > 1.5 (host disturbance)',stratum=stratum,order=ORDERS[p],arm=arm,p90_over_median=s['p90_over_median']))
   orders[ORDERS[p]]=row
  ratios=[orders[o]['ratio'] for o in ('AB','BA')]
  prod_med=statistics.fmean(orders[o]['production']['median_us'] for o in ('AB','BA'));cand_med=statistics.fmean(orders[o]['candidate']['median_us'] for o in ('AB','BA'))
  strata[stratum]=dict(orders=orders,ratio_AB=ratios[0],ratio_BA=ratios[1],worst_ratio=max(ratios),passed=all(orders[o]['passed'] for o in ('AB','BA')),gated=stratum in GATED,
   production_median_us=prod_med,candidate_median_us=cand_med,saved_us=prod_med-cand_med,bar_us=GATE*prod_med)
 control={}
 for stratum in CONTROL:
  expected=routes*cold_repeats if stratum=='cold' else warm_repeats
  ctl=groups.get(('control',stratum,'production',0),[]);require(len(ctl)==expected,f'control/{stratum}: {expected} production-only samples required, got {len(ctl)}')
  cs=stats([r['event_ns'] for r in ctl]);cs['p90_over_median']=cs['p90_ns']/cs['median_ns']
  if cs['p90_over_median']>DISTURBANCE_LIMIT:kills.append(dict(rule='p90/median > 1.5 (host disturbance)',stratum=stratum,order='P',arm='control',p90_over_median=cs['p90_over_median']))
  measured=strata[stratum]['production_median_us'];dev=abs(measured-cs['median_us'])/cs['median_us']
  control[stratum]=dict(interleaved_production_us=measured,control_us=cs['median_us'],control=cs,deviation=dev)
  if dev>CONTROL_LIMIT:kills.append(dict(rule='production cold/warm disagreement with the fresh production-only pass > 10 %',stratum=stratum,interleaved_us=measured,control_us=cs['median_us'],deviation=dev))
 gated_pass=all(strata[s]['passed'] for s in GATED)
 verdict=('withheld: '+'; '.join(k['rule'] for k in candidate_kills)) if candidate_kills else ('qualified: <= 0.85 x production cold and warm in both orders' if gated_pass else 'closed: above 0.85 x production in '+', '.join(f"{n} ({strata[n]['ratio_AB']:.3f}/{strata[n]['ratio_BA']:.3f})" for n in GATED if not strata[n]['passed']))
 ungated_note={n:('<= 0.85' if s['passed'] else 'above 0.85 (informational: not a gate stratum)') for n,s in strata.items() if not s['gated']}
 saved_cold=strata['cold']['saved_us'];saved_warm=strata['warm']['saved_us']
 candidate=dict(kernel='gateup',strata=strata,control_vs_fresh_production=control,kills=candidate_kills,verdict=verdict,ungated_strata=ungated_note,
  layer=dict(saved_us_cold=saved_cold,saved_us_warm=saved_warm,projected_one_card_pct_cold=saved_cold*ONE_CARD_PCT_PER_US,projected_one_card_pct_warm=saved_warm*ONE_CARD_PCT_PER_US,
   note='one gate/up launch per layer (48 serial layer bodies on the one-card record line); the ruling\'s 11.4 us/layer = +2 %; the engine screen (packet58-onecard-diet shape) decides, never this micro'))
 passed=not kills
 return dict(schema='packet58dm.diet-report.v1',diagnostic_only=True,model_output_claim=False,speed_claim=False,passed=passed,kills=kills,warnings=warnings,
  verdict=('withheld: '+'; '.join(sorted({k['rule'] for k in kills}))) if kills else 'measured',candidates={CANDIDATE:candidate if passed else dict(candidate,verdict='withheld')},
  exactness=exactness,nan_payload_order_rows=payload_order,
  rule=dict(gate=GATE,gated_strata=list(GATED),control_limit=CONTROL_LIMIT,disturbance_limit=DISTURBANCE_LIMIT,one_card_pct_per_us=ONE_CARD_PCT_PER_US,packet193_two_card_datum=PACKET193_TWO_CARD,
   source='coordinator ruling 2026-10-23 (packet58-onecard-diet-micro brief); packet100 micro gate 0.85; packet141 10 % control rule; packet193 NaN-payload lesson'),
  identity=dict(route_count=routes,cold_repeats=cold_repeats,warm_repeats=warm_repeats,passes=PASSES,warmups_excluded=WARMUPS,identity_as_proposed=identity_as_proposed,proposed=dict(routes=ROUTES,cold_repeats=COLD_REPEATS,warm_repeats=WARM_REPEATS),device=start[0].get('device'),device_peak_bytes=end.get('device_peak_bytes')))
def read_rows(path):return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
def markdown(result):
 lines=['# s58dm_report: exact instruction-diet micro of the one-card record gate/up kernel (diagnostic, never an engine speed result)','',f"verdict: {result['verdict']}",'',
  '| stratum | gate | production us (p10/p90) | candidate us (p10/p90) | ratio A/B | ratio B/A | <= 0.85 |','|---|---|---|---|---|---|---|']
 for c,v in result['candidates'].items():
  for n,s in v['strata'].items():
   pa,ca=s['orders']['AB']['production'],s['orders']['AB']['candidate']
   lines.append(f"| {n} | {'yes' if s['gated'] else 'info'} | {s['production_median_us']:.2f} ({pa['p10_ns']/1000:.2f}/{pa['p90_ns']/1000:.2f}) | {s['candidate_median_us']:.2f} ({ca['p10_ns']/1000:.2f}/{ca['p90_ns']/1000:.2f}) | {s['ratio_AB']:.3f} | {s['ratio_BA']:.3f} | {'yes' if s['passed'] else 'no'} |")
  le=v['layer'];lines+=['',f"{c}: {v['verdict']}; saved {le['saved_us_cold']:.2f} us/layer cold, {le['saved_us_warm']:.2f} us/layer warm; one-card projection {le['projected_one_card_pct_cold']:+.2f} % (cold) / {le['projected_one_card_pct_warm']:+.2f} % (warm) at 2 % per 11.4 us"]
  for n,ctl in v.get('control_vs_fresh_production',{}).items():lines.append(f"- control {n}: interleaved production {ctl['interleaved_production_us']:.2f} us vs fresh production-only {ctl['control_us']:.2f} us ({ctl['deviation']*100:.1f} %)")
 if result['nan_payload_order_rows']:lines+=['',f"NaN payload-order-only rows on NaN-only strata (diagnostic, never a kill): {len(result['nan_payload_order_rows'])}"]
 if result['kills']:lines+=['','kill rules fired: '+json.dumps(result['kills'])]
 return '\n'.join(lines)+'\n'
def evaluate(directory):
 directory=Path(directory);path=directory/'samples.jsonl';result=analyze(read_rows(path));result['samples_sha256']=sha(path)
 (directory/'analysis.json').write_text(json.dumps(result,indent=2)+'\n');(directory/'s58dm_report.md').write_text(markdown(result))
 rows=''.join(f"| 2026-10-23 | packet58-onecard-diet-micro {c} (one-card gate/up p58ag_exp diet) exact instruction-diet micro, lane B | {result['verdict']}; {v['verdict']}; cold ratio A/B {v['strata']['cold']['ratio_AB']:.3f} / B/A {v['strata']['cold']['ratio_BA']:.3f}, warm {v['strata']['warm']['ratio_AB']:.3f} / {v['strata']['warm']['ratio_BA']:.3f}, saved {v['layer']['saved_us_cold']:.2f} us/layer cold; evidence `{directory.name}/analysis.json` | qualified -> engine key expert_gateup=production|diet on the one-card record line (packet58-onecard-diet shape: K1a/K1b + one-load max23 bracket); closed -> do not repeat this diet form on the one-card kernel |\n" for c,v in result['candidates'].items())
 with (P/'DO-NOT-REPEAT.md').open('a') as f:f.write('\n## Packet58-onecard-diet-micro device measurement\n\n| Date | Candidate | Result | Follow-on |\n| --- | --- | --- | --- |\n'+rows)
 return result
def synthetic_fixture(output,spec):
 """Invented packet58dm stream for report rehearsal; never device evidence. spec: per stratum the production median
 (ns) and the candidate ratio, optional routes/cold_repeats/warm_repeats, byte_mismatch [[stratum, against]],
 nan_value_mismatch [stratum], nan_payload [stratum], nan_value_mismatch [stratum] (candidate rows; nan_value_on_production extends it to production), disturb stratum, control_scale (the fresh control scaled), cpu_only."""
 import random
 rng=random.Random(58);routes=spec.get('routes',ROUTES);cold_repeats=spec.get('cold_repeats',COLD_REPEATS);warm_repeats=spec.get('warm_repeats',WARM_REPEATS);cpu=spec.get('cpu_only',False)
 rows=[dict(kind='start',mode='device',device='synthetic',routes=routes,cold_repeats=cold_repeats,warm_repeats=warm_repeats,passes=PASSES,warmups=WARMUPS,candidates=CANDIDATES),dict(kind='allocation',phase='gateup',device_live_bytes=1_106_000_000,device_peak_bytes=1_106_000_000)]
 mism={tuple(m) for m in spec.get('byte_mismatch',[])};nan_value=set(spec.get('nan_value_mismatch',[]));nan_payload=set(spec.get('nan_payload',[]));disturb=spec.get('disturb');scale=spec.get('control_scale',1.0)
 def brow(candidate,stratum,route,against):
  nan=stratum in NAN_ONLY;d=0;nvn=0;other=0
  if (stratum,against) in mism and candidate==CANDIDATE:d=2;other=0 if nan else 2
  if nan and stratum in nan_payload:d=2340;nvn=1170
  if nan and stratum in nan_value and (candidate==CANDIDATE or spec.get('nan_value_on_production')):d=2340;nvn=1169;other=2
  words=nvn+(1 if (other and nan) else 0)+(1 if (d and not nan) else 0)
  return dict(kind='bytes',candidate=candidate,kernel='gateup',stratum=stratum,route=route,against=against,different_bytes=d,compared_bytes=25684,bytes_equal=d==0,different_words=words,nan_vs_nan_words=nvn,other_bytes=other,payload_order_only=bool(d) and words==nvn and other==0,exactness_claim=not nan,nan_claim=nan,nan_equal=(other==0 and words==nvn),cpu_only=cpu)
 for stratum in EXACT+NAN_ONLY:
  for route in (range(routes) if stratum=='cold' else range(SLOT_ROUTES) if stratum.startswith('slots-') else (-1,)):
   rows.append(brow('production',stratum,route,'fixture'));rows.append(brow(CANDIDATE,stratum,route,'production'));rows.append(brow(CANDIDATE,stratum,route,'fixture'))
   if stratum.startswith('slots-'):rows.append(brow('production',stratum,route,'direct-permuted'))
   if stratum=='warm-direct':rows.append(brow('production',stratum,route,'indirect'))
 t=1_000_000
 for stratum in TIMING:
  base=spec[stratum];prod_ns=int(base['production']);cand_ns=int(prod_ns*base['ratio'])
  for p in (0,1):
   for route in (range(routes) if stratum=='cold' else (-1,)):
    reps=cold_repeats if stratum=='cold' else warm_repeats+WARMUPS
    for rep in range(reps):
     warm=stratum!='cold' and rep<WARMUPS
     for which in (0,1):
      arm='production' if (which==0)==(p==0) else 'candidate';med=prod_ns if arm=='production' else cand_ns
      ns=int(med*(1+rng.uniform(-0.02,0.02)))
      if disturb is not None and disturb==stratum and rep%5==0 and arm=='production':ns=int(ns*2.5)
      rows.append(dict(kind='sample',candidate=CANDIDATE,arm=arm,kernel='gateup',stratum=stratum,route=route,**{'pass':p},order=ORDERS[p],repeat=rep if warm else rep-(WARMUPS if stratum!='cold' else 0),warmup=warm,start_ns=t,end_ns=t+ns,event_ns=ns,scrub_bytes=536870912 if stratum=='cold' else 0,exact=True,cpu_only=cpu,diagnostic_only=True));t+=ns+1000
 for stratum in CONTROL:
  prod_ns=int(spec[stratum]['production']*scale)
  for route in (range(routes) if stratum=='cold' else (-1,)):
   reps=cold_repeats if stratum=='cold' else warm_repeats+WARMUPS
   for rep in range(reps):
    warm=stratum!='cold' and rep<WARMUPS;ns=int(prod_ns*(1+rng.uniform(-0.02,0.02)))
    rows.append(dict(kind='sample',candidate='control',arm='production',kernel='gateup',stratum=stratum,route=route,**{'pass':0},order='P',repeat=rep if warm else rep-(WARMUPS if stratum!='cold' else 0),warmup=warm,start_ns=t,end_ns=t+ns,event_ns=ns,scrub_bytes=536870912 if stratum=='cold' else 0,exact=True,cpu_only=cpu,diagnostic_only=True));t+=ns+1000
 rows.append(dict(kind='summary',schema=SCHEMA,passed=True,drained=True,diagnostic_only=True,mode='host' if cpu else 'device',cpu_only=cpu,route_count=routes,cold_repeats=cold_repeats,warm_repeats=warm_repeats,passes=PASSES,real_shapes=True,stress_rows=0,candidates=CANDIDATES,device_peak_bytes=1_106_000_000))
 Path(output).mkdir(parents=True,exist_ok=True);(Path(output)/'samples.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
if __name__=='__main__':
 import sys;print(json.dumps(evaluate(sys.argv[1]),indent=2))
