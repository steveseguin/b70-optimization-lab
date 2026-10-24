"""Partition total half-event duration only; class bins have no phase identity."""
import math
def need(v,m):
 if not v:raise ValueError(m)
def partition(result,classes,length):
 need(length==87 and len(result['tokens'])==128,'fixed prompt/output extent')
 need(all(result['stats'][k]==0 for k in ('guesses','hits','misses')),'target-only diagnostic')
 trace=result['rank_trace'];halves=[r for r in trace if r['op']==1];out={}
 for rank in (0,1):
  rows=[r for r in halves if r['rank']==rank];need(len(rows)==214,'all214 halves per rank')
  need([r['position'] for r in rows]==list(range(214)),'unique ordered complete target positions')
  for r in rows:
   need(r['fixture']==max(0,r['position']-length+2) and r['speculative'] is False,'fixture/position/no speculation')
   need(type(r['gpu_ms']) in (float,int) and math.isfinite(r['gpu_ms']) and r['gpu_ms']>=0,'finite half event duration')
  groups={}
  for name,lo,hi in [('prompt_only',0,86),('first_output',86,87),('later_decode',87,214)]:
   selected=[r for r in rows if lo<=r['position']<hi];groups[name]=dict(positions=[lo,hi-1],halves=len(selected),device_ms_sum=sum(r['gpu_ms'] for r in selected))
  total=sum(r['gpu_ms'] for r in rows);class_total=sum(r['device_ms'] for r in classes[str(rank)]['report']['classes'])
  need(math.isfinite(class_total) and class_total>=0,'finite class total')
  out[str(rank)]=dict(groups=groups,TTFT_positions_device_ms_sum=groups['prompt_only']['device_ms_sum']+groups['first_output']['device_ms_sum'],all_half_device_ms=total,whole_request_class_device_ms=class_total,class_minus_half_device_ms=class_total-total)
 need(len(halves)==428 and not any(r['op']==9 for r in trace),'only target halves; no draft operation')
 return dict(ranks=out,scope='Per-rank sum of profiled event durations in target half replies; class totals remain whole-request only. Residual retained, not forced to zero; no cross-rank clock comparison or speed claim.')
