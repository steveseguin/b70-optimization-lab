"""CPU-only aggregation of measured specialised class events; no device execution."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE=Path(__file__).resolve().parent

CONTEXT_LENGTHS={256:(88,104,120,136,152,256),4096:(88,152,1024,2048,2049,4096),32768:(88,152,1024,2048,4096,8192,32767)}

def registry_for_context(context):
 if context not in CONTEXT_LENGTHS:raise ValueError('unsupported K2 capacity')
 classes=json.loads((HERE/'k2-class-registry.json').read_text())['classes']
 for name,suffix in (('qsa.attention',''),('qsa.prepare','-prepare'),('qsa.pool','-pool'),('qsa.select','-select')):
  classes[name]['workloads']=[f'qsa-c{context}-n{n}{suffix}' for n in CONTEXT_LENGTHS[context]]
  classes[name]['state_storage']='resident-overwrite'
  classes[name]['shape']=dict(capacity=context,budget=2048,tokens=1,context_lengths=list(CONTEXT_LENGTHS[context]))
  classes[name]['exactness_context_lengths']=list(CONTEXT_LENGTHS[context])
 return classes

def duration_plan(context):
 """Planning reservation, not a measured new-capacity result or speed claim.
 Base: packet38 repaired K2 approximately four minutes. Kernel p90s below
 come from receipts-cards01-20261012-chain/K2c/summary.json. Conservative
 operation-count scaling intentionally over-reserves the unknown long selector.
 """
 lengths=CONTEXT_LENGTHS[context]
 # 200 independent measurements per arm. Both selector arms are still timed.
 selection=200*2*13854e-9*sum(max(1,(n//4)/16)**2 for n in lengths)
 attention_pairs_ns=((474792,300625),(474479.1,246771),(474583,483542),(474592.6,607187.1))
 attention=200*sum(a+b for a,b in attention_pairs_ns)*1e-9*sum(max(1,(min(n//4,512)*4+n%4)/256) for n in lengths)
 prepare_pool=200*(7708+15416+7510.4+22615.3)*len(lengths)*1e-9
 total=math.ceil(480+selection*1.5+attention+prepare_pool*1.5)
 return dict(context=context,lengths=list(lengths),shapes_per_capacity=len(lengths),
  baseline_wall_seconds=480,selection_reservation_seconds=selection,
  attention_reservation_seconds=attention,prepare_pool_seconds=prepare_pool,
  expected_seconds=total,minimum_watchdog_seconds=4*(total+17),
  basis='packet38 measured p90 per-shape costs plus eight-minute wall allowance including added p42 arms and merged p39 chain fixtures; selector quadratic work reservation, attention admitted-slot reservation',
  new_capacity_measured=False,device_speed_claim=False)

def estimated_seconds(context):
 return duration_plan(context)['expected_seconds']

def percentile(values,p):
 values=sorted(values)
 if not values:return None
 where=(len(values)-1)*p;lo=int(where);hi=min(lo+1,len(values)-1)
 return values[lo]+(values[hi]-values[lo])*(where-lo)

def stats(values):
 return dict(count=len(values),median_ns=statistics.median(values) if values else None,p90_ns=percentile(values,.9))

def aggregate(rows,classes=None,repetitions=200):
 """Drop a whole repetition if any stage timestamp is bad; retain bad row count.
 This avoids comparing a partial new sequence with a complete reference sequence.
 """
 grouped={};bad=0;failures=[];durations={};seen_events=set();stage_sequences={}
 for i,row in enumerate(rows):
  name=row['class'];variant=row['variant'];variant='packet18' if variant=='packet18' else variant
  if variant not in ('packet18','specialised'):raise ValueError('unknown K2 variant')
  rep=row['repetition']
  if type(rep) is not int or not 0<=rep<repetitions:raise ValueError('invalid repetition index')
  if 'event' in row:
   event_key=(name,variant,rep,row.get('workload'),row['event'])
   if event_key in seen_events:failures.append('duplicate stage event: '+name+'/'+variant)
   seen_events.add(event_key)
  sequence_key=(name,variant,rep,row.get('workload'))
  stage_sequences.setdefault(sequence_key,[]).append(row.get('stage_count'))
  key=(name,variant,rep);bucket=grouped.setdefault(key,dict(total=0,valid=True,events=0))
  bucket['events']+=1
  start,end=row.get('start_ns'),row.get('end_ns')
  valid=type(start) in (int,float) and type(end) in (int,float) and math.isfinite(start) and math.isfinite(end) and end>start
  if not valid:bad+=1;bucket['valid']=False
  else:
   duration=end-start;bucket['total']+=duration;durations.setdefault((name,variant),[]).append(duration)
   if duration>4e9:failures.append('submission exceeds four seconds: '+name)
  if row.get('exact') is not True:failures.append('nonexact output: '+name)
 for (name,variant,rep,workload),counts in stage_sequences.items():
  # A recorded count is the complete arm submission count, including summed
  # sibling GEMVs. Do not accept a consistently truncated sequence as fast.
  if any(count is not None for count in counts):
   if any(type(count) is not int or count<1 for count in counts) or len(set(counts))!=1 or counts[0]!=len(counts):
    failures.append('declared stage coverage differs: '+name+'/'+variant)
 names=set(k[0] for k in grouped)
 if classes is not None and names!=set(classes):failures.append('class coverage differs from registered dispatch')
 registry=classes if isinstance(classes,dict) else {}
 if not rows:failures.append('empty event set')
 if rows and bad/len(rows)>.01:failures.append('more than one percent invalid event durations')
 result={};selection={}
 for name in sorted(names|set(registry)):
  variants={};counts={}
  for variant in ('packet18','specialised'):
   keys=[(name,variant,i) for i in range(repetitions)]
   if any(k not in grouped for k in keys):failures.append('missing repetitions: '+name+'/'+variant)
   observed=[grouped[k] for k in keys if k in grouped]
   # The number of events may differ between variants (a specialised stage can
   # replace several reference launches), but must be stable within each one.
   if len({r['events'] for r in observed})>1:failures.append('variable stage coverage: '+name+'/'+variant)
   sums=[r['total'] for r in observed if r['valid']]
   variants[variant]=dict(execution_sum=stats(sums),event=stats(durations.get((name,variant),[])),invalid_repetitions=sum(not r['valid'] for r in observed),repetitions=len(observed))
   if not sums:failures.append('no valid repetitions: '+name+'/'+variant)
  old=variants['packet18']['execution_sum']['median_ns'];new=variants['specialised']['execution_sum']['median_ns']
  available=registry.get(name,{}).get('candidate_available',True)
  candidate_rows=[r for r in rows if r['class']==name and r['variant']=='specialised']
  if name.startswith('gemv:'):available=bool(candidate_rows) and all(r.get('candidate_available') is True for r in candidate_rows)
  elif any(r.get('candidate_available') is False for r in candidate_rows):available=False
  rule=registry.get(name,{})
  workload_costs={}
  for workload in {r.get('workload') for r in rows if r['class']==name and r.get('workload') is not None}:
   totals={}
   for row in rows:
    if row['class']==name and row['variant']=='packet18' and row.get('workload')==workload:
     start,end=row.get('start_ns'),row.get('end_ns')
     if type(start) in (int,float) and type(end) in (int,float) and math.isfinite(start) and math.isfinite(end) and end>start:
      totals[row['repetition']]=totals.get(row['repetition'],0)+end-start
   if totals:workload_costs[workload]=statistics.median(totals.values())
  weights=rule.get('workload_groups_per_token')
  if weights:
   if set(workload_costs)!=set(weights):failures.append('workload frequency coverage differs: '+name)
   class_cost=sum(workload_costs.get(w,0)*n for w,n in weights.items())
  else:
   # Context lengths are alternate workloads, not multiple visits in one token.
   class_cost=(max(workload_costs.values()) if workload_costs else old or 0)*rule.get('groups_per_token',1)
  threshold=rule.get('threshold_override',.03 if class_cost>2e6 else .10)
  selected='specialised' if available and all(r.get('exact') is True for r in candidate_rows) and all((name,v,i) in grouped for v in ('packet18','specialised') for i in range(repetitions)) and old is not None and new is not None and new<(1-threshold)*old else 'packet18'
  workload_stats={}
  workload_names={r.get('workload') for r in rows if r['class']==name and r.get('workload') is not None}
  required=registry.get(name,{}).get('workloads')
  if required is not None and workload_names!=set(required):failures.append('workload coverage differs: '+name)
  # A table entry can cover several formats/shapes. Every one must win; a
  # fast format cannot hide a regression in another format of the same class.
  for workload in sorted(workload_names):
   subset=[{k:v for k,v in row.items() if k!='workload'} for row in rows if row['class']==name and row.get('workload')==workload]
   sub=aggregate(subset,{name:{'threshold_override':threshold}},repetitions)
   workload_stats[workload]=sub['classes'][name]
   for failure in sub['failures']:
    # Duration rejection threshold applies to the full event set. Missing
    # workload repetitions/stages and correctness failures still fail K2.
    if failure!='more than one percent invalid event durations':failures.append(workload+': '+failure)
   if not sub['passed'] or sub['selection'][name]!='specialised':selected='packet18'
  result[name]=dict(required_improvement=threshold,incumbent_class_ns_per_token=class_cost,variants=variants,workloads=workload_stats,selected=selected,candidate_available=available,ratio=new/old if old and new is not None else None)
  selection[name]=selected
 return dict(schema='packet26.k2.summary.v1',passed=not failures,diagnostic=True,device_speed_claim=False,
  repetitions=repetitions,event_rows=len(rows),invalid_duration_rows=bad,invalid_duration_fraction=bad/len(rows) if rows else None,
  invalid_rule='exclude invalid rows and their whole sequence repetition; fail only above 1 percent invalid rows',
  selection_rule='specialised only when exact and median execution sum is strictly improves by 3% for classes above 2 ms/token, otherwise 10%',
  classes=result,selection=selection,failures=sorted(set(failures)))

def resolve_fusions(dispatch, table, classes):
 """Compare measured fusion cost with the sum of selected members, by workload.
 Aliases in fusion_members describe dispatch coverage, not repeated operations.
 In particular small.hc executes one low and one inject GEMV per fusion site.
 Missing measurements fail closed instead of silently disabling a fusion.
 """
 from merge_dispatch import REGISTRY, conflicts, incompatible
 resolutions=[]
 by_key={(entry.get('dispatch_section'),key):name for name,entry in classes.items()
         for key in entry.get('dispatch_keys',[entry.get('dispatch_key')])}
 def measured(name, workload=None, force_candidate=None):
  row=table[name];candidate=force_candidate or row.get('selected_comparison')
  parts=[row['comparisons'][candidate]] if candidate else list(row['comparisons'].values())
  arm='specialised' if candidate else 'packet18'
  values=[]
  for part in parts:
   choices=part.get('workloads',{})
   selected=part
   if choices:
    matches=[v for k,v in choices.items() if workload and k.endswith('.'+workload.rsplit('.',1)[-1])]
    if len(matches)==1:selected=matches[0]
    elif len(choices)==1:selected=next(iter(choices.values()))
    else:raise ValueError('ambiguous fusion member workload: '+name+'/'+str(workload))
   value=selected['variants'][arm]['execution_sum']['median_ns']
   if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
    raise ValueError('missing fusion comparison timing: '+name)
   values.append(value)
  if not values:raise ValueError('missing fusion comparison: '+name)
  return statistics.median(values)
 targets={r[0] for r in conflicts(dispatch)} | {name.removeprefix('fusion:') for name in table if name.startswith('fusion:small.')}
 for fusion in sorted(targets):
  fusion_name=by_key.get(('fusions',fusion))
  if fusion_name not in table:raise ValueError('missing measured fusion: '+fusion)
  members=REGISTRY['fusion_members'][fusion]
  forced=None
  if fusion.startswith('small.'):
   viable=[(part['variants']['specialised']['execution_sum']['median_ns'],candidate) for candidate,part in table[fusion_name]['comparisons'].items() if part.get('bytes_equal') and not part.get('candidate_failures') and part['variants']['specialised']['execution_sum']['median_ns'] is not None]
   forced=min(viable)[1] if viable else 'round2'
  if forced:
   part=table[fusion_name]['comparisons'].get(forced,{})
   if not part.get('bytes_equal') or part.get('candidate_failures'):
    dispatch['fusions'][fusion]='packet18'
    resolutions.append(dict(fusion=fusion,selected='members',reason='fusion failed byte equality'))
    continue
  # hc.a and hc.f are separate sites with independently selected members.
  # hc.low aliases an explicit site; never count aliases as extra operations.
  sites={site:[('gemv',site+'.low'),('gemv',site+'.inject')] for site in ('hc.a','hc.f')} if fusion=='small.hc' else {
   fusion:[(section,key) for section,keys in members.items() for key in keys]}
  workloads=classes[fusion_name].get('workloads',[None]);comparison=[]
  for site,pairs in sites.items():
   member_names=[]
   for pair in pairs:
    name=by_key.get(pair)
    if name not in table:raise ValueError('missing measured fusion member: '+str(pair))
    if name not in member_names:member_names.append(name)
   for workload in workloads:
    costs={name:measured(name,workload) for name in member_names}
    comparison.append(dict(workload=workload,site=site,fusion_ns=measured(fusion_name,workload,forced),
                           selected_members_ns=sum(costs.values()),members_ns=costs))
  # One global dispatch controls all formats; every format must favour fusion.
  keep=all(row['fusion_ns']<row['selected_members_ns'] for row in comparison)
  resolutions.append(dict(fusion=fusion,selected='fusion' if keep else 'members',
   comparisons=comparison,rule='fusion strictly cheaper for every workload; ties select members',
   incumbent_cost_rule='median of same-run incumbent comparison medians when no candidate qualified'))
  if keep:
   if forced:dispatch['fusions'][fusion]=forced
   for section,keys in members.items():
    for key in keys:
     value=dispatch.get(section,{}).get(key)
     if value is not None and incompatible(section,key,value,dispatch['fusions'][fusion]):
      dispatch[section][key]='r5' if section=='gemv' else dispatch['fusions'][fusion] if key=='route' and dispatch['fusions'][fusion] in ('round2','p42.route.production_rank32') else 'specialised'
  else:dispatch['fusions'][fusion]='packet18'
 if list(conflicts(dispatch)):raise ValueError('unresolved fusion conflict')
 return resolutions

def summarize(root,identity=None,classes=None):
 root=Path(root);events=root/'events.jsonl'
 rows=[json.loads(s) for s in events.read_text().splitlines() if s.strip()]
 if classes is None:
  receipt=json.loads((root/'receipt.json').read_text()) if (root/'receipt.json').exists() else {}
  classes=registry_for_context(receipt.get('context',256))
 failure_file=root/'candidate-failures.jsonl'
 rejected=[json.loads(s) for s in failure_file.read_text().splitlines() if s.strip()] if failure_file.exists() else []
 dispatch=json.loads((HERE/'dispatch-default.json').read_text())
 fatal=[];table={};selection={};bad=0
 for name,entry in classes.items():
  cr=[r for r in rows if r['class']==name];incumbent=entry.get('incumbent','packet18')
  candidate_names=sorted({r.get('candidate','specialised') for r in cr})
  if not candidate_names:fatal.append('missing class: '+name)
  if 'candidates' in entry and set(candidate_names)!=set(entry['candidates']):fatal.append('candidate coverage differs: '+name)
  best=None;comparisons={}
  for candidate in candidate_names:
   all_pair=[r for r in cr if r.get('candidate','specialised')==candidate]
   modes=set(r.get('timing_mode','reread') for r in all_pair)
   required_modes=set(entry.get('timing_modes',[]))
   if required_modes and modes!=required_modes:fatal.append('timing mode coverage differs: '+name+'/'+candidate)
   if modes-{'rotated','reread'}:fatal.append('unknown timing mode: '+name+'/'+candidate)
   primary_mode='rotated' if 'rotated' in modes else 'reread'
   pair=[r for r in all_pair if r.get('timing_mode','reread')==primary_mode]
   reread=[r for r in all_pair if r.get('timing_mode','reread')=='reread']
   cache_report=aggregate(reread,{name:entry}) if primary_mode=='rotated' and reread else None
   heavy=entry.get('rotation_required',False)
   rotation_errors=[]
   if heavy and primary_mode!='rotated':rotation_errors.append('missing rotated measurements')
   if primary_mode=='rotated':
    for r in pair:
     copies=r.get('rotation_copies');copy=r.get('buffer_copy')
     if type(copies) is not int or copies<(8 if heavy else 1) or type(copy) is not int or copy!=(r['repetition']+(4 if r['variant']=='specialised' and copies>=8 else 0))%copies:
      rotation_errors.append('invalid buffer rotation')
     payload=r.get('payload_bytes');full=r.get('full_payload_bytes')
     if type(payload) is not int or payload<=0 or payload!=full:rotation_errors.append('timed payload is not full size')
    # Consecutive repetitions of each arm/workload cannot hit the same buffer.
    if heavy:
     for variant in ('packet18','specialised'):
      for workload in {r.get('workload') for r in pair}:
       copies={r['repetition']:r.get('buffer_copy') for r in pair if r['variant']==variant and r.get('workload')==workload}
       if any(copies[i]==copies.get(i-1) for i in copies if i>0):rotation_errors.append('consecutive repetitions reuse a buffer')
   fatal.extend(name+'/'+candidate+': '+f for f in sorted(set(rotation_errors)))
   # Every comparison has its own measured incumbent, never historical timings.
   result=aggregate(pair,{name:entry})
   part=result['classes'][name];part['incumbent']=incumbent
   part.update(selection_timing_mode=primary_mode,rotation_errors=sorted(set(rotation_errors)),
    rotated=part['variants'] if primary_mode=='rotated' else None,
    reread=cache_report['classes'][name]['variants'] if cache_report else (part['variants'] if primary_mode=='reread' else None))

   fatal.extend(f for f in result['failures'] if 'submission exceeds four seconds:' in f)
   for variant in ('packet18','specialised'):
    if any(len({r.get('implementation',incumbent if variant=='packet18' else candidate) for r in all_pair if r['variant']==variant and r.get('workload')==workload})>1 for workload in {r.get('workload') for r in pair}):fatal.append('implementation changed: '+name+'/'+candidate+'/'+variant)
   failures=[r for r in rejected if r['class']==name and r.get('candidate',r.get('implementation',candidate)) in (candidate,incumbent,'packet18','specialised')]
   old=[r for r in pair if r['variant']=='packet18'];new=[r for r in pair if r['variant']=='specialised']
   expected_incumbent=entry.get('baseline_implementation',incumbent)
   wrong_incumbent=any(r.get('implementation',expected_incumbent)!=expected_incumbent for r in all_pair if r['variant']=='packet18')
   if wrong_incumbent:fatal.append('wrong incumbent implementation: '+name+'/'+candidate)
   wrong_storage=bool(entry.get('state_storage')) and any(r.get('state_storage')!=entry['state_storage'] for r in all_pair)
   if wrong_storage:fatal.append('nonrepresentative state storage: '+name+'/'+candidate)
   def identities(arm):
    return sorted({r.get('kernel_identity',r.get('implementation',incumbent if r['variant']=='packet18' else candidate)) for r in arm})
   old_ids,new_ids=identities(old),identities(new)
   same_workloads={}
   for workload in {r.get('workload') for r in pair}:
    before=[r for r in old if r.get('workload')==workload];after=[r for r in new if r.get('workload')==workload]
    left,right=identities(before),identities(after)
    same_workloads[workload or '<single>']=bool(left) and left==right or any(r.get('same_kernel') is True for r in after)
   same=any(same_workloads.values())
   part.update(incumbent_kernel_identities=old_ids,candidate_kernel_identities=new_ids,same_kernel=same,same_kernel_by_workload=same_workloads,wrong_incumbent=wrong_incumbent,bytes_equal=not failures and bool(old) and bool(new) and all(r.get('exact') is True for r in old+new),candidate_failures=failures)
   for variant,data in part['variants'].items():
    for metric in ('execution_sum','event'):
     for stat in ('median','p90'):
      ns=data[metric][stat+'_ns'];data[metric][stat+'_us']=None if ns is None else ns/1000
   comparisons[candidate]=part
   bad+=result['invalid_duration_rows']+(cache_report['invalid_duration_rows'] if cache_report else 0)
   if failures:
    if any(r['variant']=='packet18' for r in failures):fatal.append('incumbent failed: '+name+'/'+candidate)
    control=aggregate(old+[dict(r,variant='specialised') for r in old],{name:entry})
    fatal.extend(name+'/'+candidate+': '+f for f in control['failures'] if f!='more than one percent invalid event durations')
    if cache_report:
     cached_old=[r for r in reread if r['variant']=='packet18']
     cached_control=aggregate(cached_old+[dict(r,variant='specialised') for r in cached_old],{name:entry})
     fatal.extend(name+'/'+candidate+'/reread: '+f for f in cached_control['failures'] if f!='more than one percent invalid event durations')
   else:
    fatal.extend(name+'/'+candidate+': '+f for f in result['failures'] if f!='more than one percent invalid event durations')
    if cache_report:fatal.extend(name+'/'+candidate+'/reread: '+f for f in cache_report['failures'] if f!='more than one percent invalid event durations')
   eligible=not rotation_errors and not failures and (cache_report is None or cache_report['passed']) and result['passed'] and part['selected']=='specialised' and not same and not wrong_incumbent and not wrong_storage
   if eligible:
    score=part['variants']['specialised']['execution_sum']['median_ns']
    implementation=entry.get('candidate_implementation',candidate)
    impl={r.get('implementation',implementation) for r in new}
    if len(impl)==1 and 'candidate_implementation' not in entry:implementation=next(iter(impl))
    if best is None or score<best[0]:best=(score,implementation,candidate)
   print(name,candidate,'same_kernel='+str(same),'bytes_equal='+str(part['bytes_equal']),
    'incumbent_us='+str(part['variants']['packet18']['execution_sum']['median_us']),
    'incumbent_p90_us='+str(part['variants']['packet18']['execution_sum']['p90_us']),
    'candidate_us='+str(part['variants']['specialised']['execution_sum']['median_us']),
    'candidate_p90_us='+str(part['variants']['specialised']['execution_sum']['p90_us']))
  selected=best[1] if best else incumbent;selection[name]=selected
  table[name]=dict(incumbent=incumbent,selected=selected,selected_comparison=best[2] if best else None,comparisons=comparisons)
  section=entry.get('dispatch_section')
  if section:
   for key in entry.get('dispatch_keys',[entry['dispatch_key']]):dispatch[section][key]=selected
 if any(r['class'] not in classes for r in rows+rejected):fatal.append('unregistered class')
 if rows and bad/len(rows)>.01:fatal.append('more than one percent invalid event durations')
 if not rows:fatal.append('empty event set')
 summary=dict(schema='packet37.k2.summary.v1',passed=not fatal,diagnostic=True,device_speed_claim=False,
  repetitions=200,event_rows=len(rows),invalid_duration_rows=bad,classes=table,selection=selection,
  selection_rule='exact, different kernel, every workload median improves by 3% for measured classes above 2 ms/token, otherwise 10%, against same-run incumbent; rotated required for heavy GEMVs, reread only for small classes',
  candidate_failures=rejected,failures=sorted(set(fatal)),events_sha256=hashlib.sha256(events.read_bytes()).hexdigest())
 # A conflict is resolved only with recorded same-run measurements.
 try:
  summary['fusion_conflict_resolutions']=resolve_fusions(dispatch,table,classes)
 except (KeyError,ValueError) as error:
  summary['passed']=False
  summary['failures'].append('fusion comparison failed: '+str(error))
 summary['final_dispatch']=dispatch
 summary['rank_dispatch_policy']='The one-card measured dispatch is identical for ranks 0 and 1; no cross-card speed equivalence is claimed.'
 (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 (root/'dispatch-measured.json').write_text(json.dumps(dispatch,indent=2)+'\n')
 for rank in (0,1):(root/f'dispatch-rank{rank}.json').write_text(json.dumps(dispatch,indent=2)+'\n')
 return summary

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path);parser.add_argument('--context',type=int,choices=tuple(CONTEXT_LENGTHS));a=parser.parse_args()
 raise SystemExit(0 if summarize(a.root,classes=registry_for_context(a.context) if a.context else None)['passed'] else 1)
