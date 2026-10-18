"""Host-clock scheduling costs; never infer missing device measurements."""
import json,statistics
from pathlib import Path
from common import require

def stats(values):
 require(bool(values),'missing scheduling samples')
 return dict(count=len(values),mean_us=statistics.mean(values),median_us=statistics.median(values))

def summarize(output,views):
 rows=[]
 for view in views:
  root=Path(view['output']);totals={}
  for request in view['requests']:
   dest=root/request['prompt_id']
   # CPU/GPU clocks are never mixed. Fixtures map rank0 k to rank1 k-1;
   # each native guess stores the rank0 position and hit outcome.
   guesses=request.get('guess_rows',request.get('guesses_detail',[]))
   native=dest/'native-result.json'
   if native.is_file():
    native=json.loads(native.read_text());guesses=native.get('guess_rows',guesses)
   if not isinstance(guesses,list):guesses=[]
   outcomes={int(g['position']):('hit' if g['hit'] else 'miss') for g in guesses if isinstance(g.get('hit'),bool)}
   samples=[]
   for rank in (0,1):
    path=dest/f'rank{rank}/p105-transfers.jsonl'
    require(path.is_file(),'missing suffix timing receipt: '+str(path))
    for line in path.read_text().splitlines():
     r=json.loads(line)
     if r['leg'] not in ('suffix-service','wait.head.suffix'):continue
     # suffix position is the verified rank1 position, guess position is next.
     outcome=outcomes.get(r['position']+1,'unclassified')
     keys=('host_us',) if rank else ('wait_ready_us','import_us','suffix_compute_and_scalars_us','service_us')
     for key in keys:totals.setdefault((rank,r['leg'],key,outcome),[]).append(r[key])
   path=dest/'rank0/timings.jsonl';require(path.is_file(),'missing rank0 half timing')
   for line in path.read_text().splitlines():
    r=json.loads(line)
    if not r.get('speculative'):continue
    require('half_completion_ms' in r,'missing rank0 completion clock')
    outcome=outcomes.get(r['position'],'unclassified')
    totals.setdefault((0,'speculative-half','host_us',outcome),[]).append(r['half_completion_ms']*1000)
  rows.append(dict(index=view['index'],choice=view['choice'],costs=[dict(rank=k[0],stage=k[1],metric=k[2],outcome=k[3],**stats(values)) for k,values in sorted(totals.items())]))
 return dict(definition='same-process host elapsed time; half includes fences and interleaved suffix, not pure GPU time',views=rows,unclassified='retained explicitly when no bound guess row is present; never guessed or filled with zero')
