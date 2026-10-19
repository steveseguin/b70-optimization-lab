"""View-local correction clocks from the native controller, no head receipts.

rank_completed - rank_received is the same-process confirmed HALF interval;
busy_ms is the narrower Engine half time. Never substitute an absent sample.
"""
import json,statistics
from pathlib import Path
from common import require

def stats(values):
 return dict(count=len(values),mean_ms=statistics.mean(values) if values else None,
             median_ms=statistics.median(values) if values else None,total_ms=sum(values) if values else None)

def summarize(output,views):
 result=[]
 for view in views:
  root=Path(view['output']);halves=[];native_busy=[];misses=0;missing=[];requests=[];exchange_rows=[];native_half=[]
  for request in view['requests']:
   path=root/request['prompt_id']/'native-result.json'
   if path.is_file():
    native=json.loads(path.read_text())
   elif 'rank_trace' in request and 'guess_rows' in request:
    native=request
   else:
    missing.append(request['prompt_id']);continue
   guessed=native.get('guess_rows',[]);trace=native['rank_trace']
   positions=[int(g['position']) for g in guessed if g['hit'] is False]
   require(len(positions)==len(set(positions)),'duplicate miss positions')
   selected=[t for t in trace if t['rank']==0 and t['op']==1 and not t['speculative'] and t['position'] in positions]
   require(len(selected)==len(positions),'missing/duplicate corrected HALF trace')
   require({t['position'] for t in selected}==set(positions),'correction position mismatch')
   values=[]
   for t in selected:
    duration=1000*(t['rank_completed']-t['rank_received'])
    require(duration>0 and t['busy_ms']>0,'invalid corrected-half clock')
    values.append(duration);native_busy.append(t['busy_ms'])
   clock=root/request['prompt_id']/'rank0/timings.jsonl'
   if clock.is_file():
    clocks=[json.loads(line) for line in clock.read_text().splitlines() if line.strip()]
    measured=[r for r in clocks if r.get('corrected') is True]
    if measured:
     require({r['position'] for r in measured}==set(positions) and len(measured)==len(positions),'corrected engine clock mismatch')
     native_half.extend(r['half_completion_ms'] for r in measured)
     exchange_rows.extend(measured)
   misses+=len(positions);halves.extend(values)
   requests.append(dict(prompt_id=request['prompt_id'],miss_count=len(positions),corrected_half=stats(values)))
  result.append(dict(index=view['index'],choice=view['choice'],probe='off' if view['choice']=='control' else 'sibling',
     miss_count=misses if not missing else None,corrected_half=stats(native_half if len(native_half)==misses and misses else halves),
     corrected_half_clock='engine completion before reporting' if len(native_half)==misses and misses else 'native rank received/completed',
     native_command=stats(halves),engine_busy=stats(native_busy),
     exchange_audit=dict(covered_misses=len(exchange_rows),counts=sorted(set(r['probe_exchanges'] for r in exchange_rows)),send_bytes_per_miss=sorted(set(r['probe_send_bytes'] for r in exchange_rows)),receive_bytes_per_miss=sorted(set(r['probe_receive_bytes'] for r in exchange_rows))),
     missing_native_trace=missing,status='measured' if not missing else 'unavailable',requests=requests))
 controls=[r['corrected_half']['mean_ms'] for r in result if r['choice']=='control' and not r['missing_native_trace'] and r['miss_count']]
 for r in result:
  r['exchange_cost_per_miss_ms']=r['corrected_half']['mean_ms']-statistics.mean(controls) if controls and r['choice']=='candidate' and not r['missing_native_trace'] and r['miss_count'] else None
 return dict(definition='rank0 confirmed HALF host duration, including preparation, waits, exchanges and receipt work; rollback excluded; all generated misses (not only first 100)',
     comparison='candidate mean corrected-half ms minus mean of control-view means; control drift and per-prompt counts retained',
     half_busy_definition='Engine half busy_ms, narrower host interval; no GPU-only claim',views=result)
