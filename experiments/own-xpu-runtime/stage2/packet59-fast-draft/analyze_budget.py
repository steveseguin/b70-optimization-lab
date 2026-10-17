#!/usr/bin/env python3
"""Planning only: packet57 events plus explicit cross-format transfer assumptions."""
import collections,hashlib,json,statistics
from pathlib import Path
from suite_metrics import PROMPT_CLASSES
P=Path(__file__).resolve().parent
SRC=Path('/home/steve/own-xpu-runtime-results/packet57-attribution/build/device-cards01-a/W57-attribution/run/repeat-1')
# Ratios are hypotheses from owner's same-context target timings, not p59 data.
R={'draft.blk.0.qsa.qgate':77/126,'draft.blk.0.qsa.attention':44/113,
'draft.blk.0.expsgate':72/82,'draft.blk.0.attention':47/77,'draft.blk.0.expsdown':57/64,
'draft.blk.0.route':20/43,'draft.blk.0.hc.a.inject':13/48,'draft.blk.0.hc.f.inject':13/20,
'draft.merge.embedding_norm':.5,'draft.merge.hidden_norm':.5,'draft.merge.projected':.85}
for prefix in ('draft.blk.0.hc.a','draft.blk.0.hc.f','draft.final'):
 R[prefix+'.low']=11.5/22;R[prefix+'.gate']=15/27;R[prefix+'.norm']=.7
for name in ('draft.merge.add','draft.blk.0.expsact','draft.blk.0.shexpact','draft.blk.0.attn.combine'):
 R[name]=0
for prefix in ('draft.blk.0.hc.a','draft.blk.0.hc.f','draft.final'):
 R[prefix+'.act']=0;R[prefix+'.mix']=0
rows=[];sources={};bylabel=collections.defaultdict(list)
for path in sorted(SRC.glob('*/rank1/sites.jsonl')):
 sources[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest();cycles=collections.defaultdict(list)
 for line in path.open():
  r=json.loads(line)
  if r['label'].startswith('draft.') and r['end_ns']>r['start_ns']:cycles[(r['fixture'],r['position'])].append(r)
 timings=[]
 for key,events in cycles.items():
  labels=collections.defaultdict(float)
  for r in events:labels[r['label']]+=(r['end_ns']-r['start_ns'])/1000
  if 'draft.logits' not in labels:continue
  for label,us in labels.items():bylabel[label].append(us)
  span=(max(r['end_ns'] for r in events)-min(r['start_ns'] for r in events))/1000
  saving=sum(us*(1-R.get(label,1)) for label,us in labels.items())
  # No gap reduction credited, despite fewer physical kernels.
  timings.append((span,saving))
 assert timings,path
 rows.append({'prompt_id':path.parents[1].name,'prompt_class':PROMPT_CLASSES[path.parents[1].name],'observed_cycles':len(timings),'packet57_span_us':statistics.median(t[0] for t in timings),'projected_saving_us':statistics.median(t[1] for t in timings)})
classes=[]
for cls in sorted(set(r['prompt_class'] for r in rows)):
 subset=[r for r in rows if r['prompt_class']==cls];d=statistics.median(r['packet57_span_us'] for r in subset);s=statistics.median(r['projected_saving_us'] for r in subset)
 classes.append({'prompt_class':cls,'observed_packet57_span_us':d,'projected_saving_us':s,'projected_new_span_us':d-s,'conditional_total_speedup_percent':s/1000*3.8})
result={'schema':'packet59.planning-budget.v1','measured_packet59':False,'device_executed':False,'assumptions':'Ratios transfer target microtimings across incompatible draft weight formats, plus explicit unmeasured norm/merge fusion estimates. Acceptance held fixed; no launch-gap savings credited. No speed headline or lower bound. Final-head 15/27 ratio is approximate. Device screening decides.','sources_sha256':sources,'ratios':R,'per_prompt':rows,'per_prompt_class':classes,'per_kernel_class':[{'label':k,'observed_packet57_us':statistics.median(v),'projected_p59_us':statistics.median(v)*R.get(k,1),'projected_saving_us':statistics.median(v)*(1-R.get(k,1))}for k,v in sorted(bylabel.items())]}
(P/'budget.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(classes,indent=2))
