"""Strict packet151 cost reader. Missing evidence is a refusal, never zero cost."""
import argparse,json,math,statistics
from pathlib import Path
GATE_MS=1.952

def need(ok,message):
 if not ok:raise ValueError(message)
def positive(value,name):
 need(type(value) in (float,int) and math.isfinite(value) and value>0,'invalid '+name)
 return value

def lines(path):
 need(path.is_file(),'missing stream: '+str(path))
 rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
 need(bool(rows),'empty stream: '+str(path));return rows

def view_data(view):
 root=Path(view['output']);data={};rates={};intervals=[];cancelled=0
 need(view.get('passed') is True,'view quality failed')
 requests=view['requests'];need(len(requests)==12,'complete 12-prompt view required')
 need(len({r['prompt_id'] for r in requests})==12,'duplicate prompt')
 for request in requests:
  need(request.get('exact_oracle') is True and request.get('passed') is True and request.get('cached_tokens')==0,'oracle/cache gate failed')
  name=request['prompt_id'];directory=root/name
  timing=lines(directory/'rank0/timings.jsonl')
  halves=[r for r in timing if r.get('speculative') is True and not r.get('corrected')]
  need(halves,'missing speculative half A timings')
  expected={g['position'] for g in request['guess_rows']}
  need(len(halves)==len(expected) and {r['position'] for r in halves}==expected,'half A position coverage')
  candidate=view['choice']=='candidate'
  if candidate:
   siblings=lines(directory/'rank0/sibling-rows.jsonl')
   pairs={(r['position'],r['fixture']):r for r in siblings}
   need(len(pairs)==len(siblings),'duplicate sibling timing')
  for row in halves:
   need(row.get('p151_sibling') is candidate,'wrong sibling mode')
   positive(row.get('p151_device_ms'),'half device ms');positive(row.get('half_completion_ms'),'half wall ms')
   if candidate:
    sibling=pairs.get((row['position'],row['fixture']))
    need(sibling and sibling.get('discarded') is True,'missing discarded sibling row')
    need(sibling['paired_half_device_ms']==row['p151_device_ms'],'sibling clock mismatch')
    need(sibling['cancelled']==row['cancelled'],'sibling cancellation mismatch')
   if row['cancelled']:cancelled+=1;continue
   key=(name,row['position']);need(key not in data,'duplicate half');data[key]=row
  ts=request['token_timestamps'];n=100 if len(ts)>=100 else len(ts)
  need(n>=2 and all(math.isfinite(t) for t in ts) and all(b>a for a,b in zip(ts,ts[1:])),'invalid output timestamps')
  ms=(ts[n-1]-ts[0])*1000/(n-1);intervals.append(ms);rates.setdefault(request['prompt_class'],[]).append(1000/ms)
 need(data,'no complete half A samples')
 return dict(index=view['index'],choice=view['choice'],data=data,cancelled_halves=cancelled,interval_ms=statistics.mean(intervals),tok_s=statistics.median(statistics.median(x) for x in rates.values()),rate_definition='median across class medians; first 99 intervals (smoke: all 63)'),requests

def analyze(proof):
 kind=proof['kind'];views=proof['views'];need(proof.get('passed') is True,'incomplete proof')
 expected=['candidate'] if kind=='smoke' else ['control','candidate','control','candidate','control']
 need(kind in ('smoke','bracket') and [v['choice'] for v in views]==expected,'invalid bracket order')
 parsed=[view_data(v) for v in views];rows=[r for r,_ in parsed]
 # Keep the same complete positions in every view. Cancelled halves cannot stand in for full M=1/M=2 work.
 keys=set.intersection(*(set(r['data']) for r in rows));need(keys,'no matched complete half A positions')
 identities=[]
 for row,requests in parsed:
  identities.append([(r['prompt_id'],r['tokens'],r['guess_rows']) for r in requests])
  row['matched_complete_halves']=len(keys)
  row['rank0_half_A_device_ms']=statistics.mean(row['data'][k]['p151_device_ms'] for k in keys)
  row['rank0_half_A_ms']=statistics.mean(row['data'][k]['half_completion_ms'] for k in keys)
  row['sibling_prepare_ms']=statistics.mean(row['data'][k]['p151_sibling_prepare_ms'] for k in keys)
  del row['data']
 # Timing fields in guesses are deliberately excluded from identity.
 def identity(requests):return [(r['prompt_id'],r['tokens'],[(g['position'],g['guess'],g['actual'],g['hit']) for g in r['guess_rows']]) for r in requests]
 need(all(identity(q)==identity(parsed[0][1]) for _,q in parsed),'tokens/proposals/acceptance changed')
 result=dict(schema='packet151.sibling-cost.v1',passed=True,diagnostic=True,qualifying=False,device_measurement=True,kind=kind,views=rows,threshold_ms=GATE_MS,
   cost_definition='candidate minus adjacent controls, matched complete speculative halves; host completion includes sibling preparation and state copies; device event sums separately',
   decision='smoke-data-complete' if kind=='smoke' else None,policy_calibration='packet114 independent text only; never the 12-prompt suite')
 if kind=='bracket':
  controls=[r for r in rows if r['choice']=='control']
  for i in (1,3):
   rows[i]['extra_sibling_ms']=rows[i]['rank0_half_A_ms']-(rows[i-1]['rank0_half_A_ms']+rows[i+1]['rank0_half_A_ms'])/2
   rows[i]['extra_sibling_device_ms']=rows[i]['rank0_half_A_device_ms']-(rows[i-1]['rank0_half_A_device_ms']+rows[i+1]['rank0_half_A_device_ms'])/2
  cost=statistics.mean(rows[i]['extra_sibling_ms'] for i in (1,3))
  drift=max(r['rank0_half_A_ms'] for r in controls)-min(r['rank0_half_A_ms'] for r in controls)
  result.update(measured_extra_sibling_ms=cost,control_drift_ms=drift,control_drift_percent=100*drift/min(r['rank0_half_A_ms'] for r in controls),candidate_spread_ms=abs(rows[1]['extra_sibling_ms']-rows[3]['extra_sibling_ms']),decision='reopen-packet132' if cost<=GATE_MS else 'close-this-implementation')
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);ap.add_argument('--report',type=Path);a=ap.parse_args()
 proof=json.loads((a.output/'run/bracket-inputs.json').read_text());result=analyze(proof)
 raw=json.dumps(result,indent=2)+'\n'
 if a.report:a.report.write_text(raw)
 else:print(raw,end='')
if __name__=='__main__':main()
