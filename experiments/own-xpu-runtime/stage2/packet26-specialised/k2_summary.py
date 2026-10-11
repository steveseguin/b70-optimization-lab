"""CPU-only aggregation of measured specialised class events; no device execution."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE=Path(__file__).resolve().parent

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
 grouped={};bad=0;failures=[];durations={}
 for i,row in enumerate(rows):
  name=row['class'];variant=row['variant'];variant='packet18' if variant=='packet18' else variant
  if variant not in ('packet18','specialised'):raise ValueError('unknown K2 variant')
  rep=row['repetition']
  if type(rep) is not int or not 0<=rep<repetitions:raise ValueError('invalid repetition index')
  key=(name,variant,rep);bucket=grouped.setdefault(key,dict(total=0,valid=True,events=0))
  bucket['events']+=1
  start,end=row.get('start_ns'),row.get('end_ns')
  valid=type(start) in (int,float) and type(end) in (int,float) and math.isfinite(start) and math.isfinite(end) and end>start
  if not valid:bad+=1;bucket['valid']=False
  else:
   duration=end-start;bucket['total']+=duration;durations.setdefault((name,variant),[]).append(duration)
   if duration>4e9:failures.append('submission exceeds four seconds: '+name)
  if row.get('exact') is not True:failures.append('nonexact output: '+name)
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
  selected='specialised' if available and all(r.get('exact') is True for r in candidate_rows) and all((name,v,i) in grouped for v in ('packet18','specialised') for i in range(repetitions)) and old is not None and new is not None and new<.9*old else 'packet18'
  workload_stats={}
  workload_names={r.get('workload') for r in rows if r['class']==name and r.get('workload') is not None}
  required=registry.get(name,{}).get('workloads')
  if required is not None and workload_names!=set(required):failures.append('workload coverage differs: '+name)
  # A table entry can cover several formats/shapes. Every one must win; a
  # fast format cannot hide a regression in another format of the same class.
  for workload in sorted(workload_names):
   subset=[{k:v for k,v in row.items() if k!='workload'} for row in rows if row['class']==name and row.get('workload')==workload]
   sub=aggregate(subset,[name],repetitions)
   workload_stats[workload]=sub['classes'][name]
   for failure in sub['failures']:
    # Duration rejection threshold applies to the full event set. Missing
    # workload repetitions/stages and correctness failures still fail K2.
    if failure!='more than one percent invalid event durations':failures.append(workload+': '+failure)
   if not sub['passed'] or sub['selection'][name]!='specialised':selected='packet18'
  result[name]=dict(variants=variants,workloads=workload_stats,selected=selected,candidate_available=available,ratio=new/old if old and new is not None else None)
  selection[name]=selected
 return dict(schema='packet26.k2.summary.v1',passed=not failures,diagnostic=True,device_speed_claim=False,
  repetitions=repetitions,event_rows=len(rows),invalid_duration_rows=bad,invalid_duration_fraction=bad/len(rows) if rows else None,
  invalid_rule='exclude invalid rows and their whole sequence repetition; fail only above 1 percent invalid rows',
  selection_rule='specialised only when exact and median execution sum is strictly below 0.9 times packet18',
  classes=result,selection=selection,failures=sorted(set(failures)))

def summarize(root,identity=None,classes=None):
 root=Path(root);events=root/'events.jsonl'
 rows=[json.loads(s) for s in events.read_text().splitlines() if s.strip()]
 if classes is None:
  registry=HERE/'k2-class-registry.json'
  if not registry.is_file():raise ValueError('registered K2 classes missing')
  classes=json.loads(registry.read_text())['classes']
 failure_file=root/'candidate-failures.jsonl'
 rejected=[json.loads(s) for s in failure_file.read_text().splitlines() if s.strip()] if failure_file.exists() else []
 excluded={r['class'] for r in rejected}
 summary=aggregate(rows,classes)
 summary['candidate_failures']=rejected
 summary['excluded_classes']=sorted(excluded)
 # Excluded candidate arms are expected to have incomplete timing rows. Retain
 # their complete diagnostics but do not let them prevent unrelated measurements.
 fatal=[]
 for name,entry in classes.items():
  part=aggregate([r for r in rows if r['class']==name],{name:entry})
  if name in excluded:
   summary['selection'][name]='packet18'
   summary['classes'][name]['selected']='packet18'
   summary['classes'][name]['candidate_failures']=[r for r in rejected if r['class']==name]
   if any(r['variant']=='packet18' for r in rejected if r['class']==name):
    fatal.append('reference arm failed: '+name)
   # Check the surviving reference with a duplicate reference arm, so missing
   # reference workloads, bad bytes and budgets cannot hide behind exclusion.
   old=[r for r in rows if r['class']==name and r['variant']=='packet18']
   control=aggregate(old+[dict(r,variant='specialised') for r in old],{name:entry})
   fatal.extend(f for f in control['failures'] if f!='more than one percent invalid event durations')
  else:fatal.extend(f for f in part['failures'] if f!='more than one percent invalid event durations')
 if any(r['class'] not in classes for r in rows+rejected):fatal.append('unregistered class')
 for name in classes:
  if name.startswith('gemv:'):
   for variant in ('packet18','specialised'):
    implementations={r.get('implementation','r5') for r in rows if r['class']==name and r['variant']==variant}
    if len(implementations)>1:fatal.append('GEMV implementation identity changed: '+name+'/'+variant)
 # The duration budget is global and never waived by a candidate exclusion.
 fatal.extend(f for f in summary['failures'] if 'submission exceeds four seconds:' in f)
 if rows and summary['invalid_duration_rows']/len(rows)>.01:fatal.append('more than one percent invalid event durations')
 summary['excluded_arm_diagnostics']=summary['failures']
 summary['failures']=sorted(set(fatal));summary['passed']=not fatal
 summary['events_sha256']=hashlib.sha256(events.read_bytes()).hexdigest()
 (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 dispatch=dict(schema='packet26.dispatch.v1',classes={},fusions={},gemv={})
 for name,entry in classes.items():
  selected=summary['selection'][name]
  section=entry.get('dispatch_section');key=entry.get('dispatch_key')
  if section is None:continue
  if section=='gemv':
   implementations={r.get('implementation','r5') for r in rows if r['class']==name and r['variant']==selected}
   selected=implementations.pop() if len(implementations)==1 else 'r5'
  for target in entry.get('dispatch_keys',[key]):dispatch[section][target]=selected
 (root/'dispatch-measured.json').write_text(json.dumps(dispatch,indent=2)+'\n')
 return summary

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path);a=parser.parse_args()
 raise SystemExit(0 if summarize(a.root)['passed'] else 1)
