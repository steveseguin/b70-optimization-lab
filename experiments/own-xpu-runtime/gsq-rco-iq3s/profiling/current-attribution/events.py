"""Bounded join of existing packet65 event rows to exact graph/census weights."""
import collections,hashlib,json,re
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parents[1];R=L.parents[2]
def require(x,m):
 if not x:raise ValueError(m)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pinned_paths():return [R/f for f in json.loads((P/'source-pins.json').read_text())]
def mapping():
 for f,h in json.loads((P/'source-pins.json').read_text()).items():require(sha(R/f)==h,'attribution source/metadata drift')
 graph=json.loads((L/'graph/new-plan.json').read_text());tensors=json.loads((L/'metadata/new-census.json').read_text())['tensors'];result={}
 for site in graph['launches']:
  label=site['label'];require(label not in result,'duplicate graph label')
  result[label]=dict(op=site['op'],weights=[dict(name=w,type=tensors[w]['type'],dimensions=tensors[w]['dimensions']) for w in site['weights']])
 return result
def routed(label):
 return label.startswith('blk.') and not any(x in label for x in ('shexp','shared','hc.','norm','final.','merge.')) and any(x in label for x in ('gather','moe','exps','expert','router','route','ffn.'))
def aggregate(rows,rank,prompt_length,sites):
 require(rank in (0,1) and prompt_length==87,'fixed rank/prompt identity');halves={};events=[];seen=set()
 for row in rows:
  schema=row.get('schema');require(schema in ('packet65.event.v1','packet65.half.v1'),'unexpected attribution row')
  f=row['fixture'];pos=row['position'];half=row['half']
  require(type(f)is int and 9<=f<=16 and type(pos)is int and pos==prompt_length+f-2,'sample equation/positions')
  require(row['rank']==rank and row['speculative'] is False and type(half)is int and half>0,'target half identity')
  if schema=='packet65.half.v1':
   require(half not in halves and row['cancelled'] is False,'duplicate/cancelled half');halves[half]=(f,pos)
  else:
   eid=row['event'];require(type(eid)is int and eid>0 and eid not in seen,'duplicate/invalid event');seen.add(eid)
   require(row['diagnostic'] is True and row['class']=='moe_experts','original attribution schema')
   start=row['start_ns'];end=row['end_ns'];require(type(start)is int and type(end)is int and 0<start<=end and end-start<=4000000000,'event interval')
   label=row['label'];require(label in sites and routed(label),'unknown/nonrouted label');layer=int(label.split('.')[1]);require(rank*24<=layer<(rank+1)*24,'rank/layer ownership')
   events.append(row)
 require(len(halves)==8 and {x[0] for x in halves.values()}==set(range(9,17)),'all eight measured halves')
 by_label={};by_format={};coverage=set()
 for row in events:
  require(halves.get(row['half'])==(row['fixture'],row['position']),'event/half join');label=row['label'];s=sites[label];cl=label.split('.',2)[2];weights=s['weights'];fmt=weights[0]['type'] if len(weights)==1 else 'none' if not weights else 'mixed';key=(cl,fmt)
  duration=row['end_ns']-row['start_ns'];coverage.add((row['fixture'],label))
  for dest,k in ((by_label,label),(by_format,key)):
   if k not in dest:dest[k]=dict(event_count=0,device_ns=0)
   dest[k]['event_count']+=1;dest[k]['device_ns']+=duration
 for f in range(9,17):
  for layer in range(rank*24,(rank+1)*24):
   for cl in ('expsgate','expsup','expsdown'):require((f,f'blk.{layer}.{cl}') in coverage,'missing expert projection event')
 labels=[dict(label=k,**v,**sites[k],device_ms=v['device_ns']/1e6) for k,v in sorted(by_label.items())]
 formats=[dict(class_name=k[0],format=k[1],**v,device_ms=v['device_ns']/1e6) for k,v in sorted(by_format.items())]
 return dict(rank=rank,fixtures=list(range(9,17)),absolute_positions=list(range(94,102)),half_count=8,event_count=len(events),device_ns=sum(x['device_ns'] for x in by_label.values()),by_label=labels,by_class_format=formats,scope='Actual sampled routed event execution durations only; no prefill/full-decode/whole-request extrapolation')
def summarize(path,prompt_length):
 require(path.is_file() and not path.is_symlink() and path.stat().st_size<=32*1024**2,'bounded event stream');rank=int(path.parent.name.removeprefix('rank'));rows=[]
 with path.open() as f:
  for line in f:
   require(len(line)<=16384,'bounded event row');rows.append(json.loads(line));require(len(rows)<=100000,'bounded row count')
 return dict(path=str(path),sha256=sha(path),report=aggregate(rows,rank,prompt_length,mapping()))

def combine(reports):
 totals={}
 for value in reports.values():
  for row in value['report']['by_class_format']:
   key=(row['class_name'],row['format'])
   total=totals.setdefault(key,dict(event_count=0,device_ns=0))
   total['event_count']+=row['event_count'];total['device_ns']+=row['device_ns']
 return [dict(class_name=k[0],format=k[1],**v,device_ms=v['device_ns']/1e6) for k,v in sorted(totals.items())]
