"""Read existing packet77 event evidence; no device or benchmark launch."""
import json,statistics
from build_engine import P,ROOT,sha,save,limits
def main():
 limits();base=P.parent/'screen/v4-lanes/evidence/packet77-attribution-B-a/run';report=dict(device_executed=False,sources={},ranks={})
 for rank in (0,1):
  stages=[[] for _ in range(4)];calls=[];norm=[]
  for f in sorted((base/'attribution').glob(f'*/rank{rank}/sites.jsonl')):
   report['sources'][str(f.relative_to(ROOT))]=sha(f)
   records=[json.loads(x) for x in f.read_text().splitlines()]
   route=[r for r in records if r['label'].endswith('.route')]
   assert len(route)%4==0
   for offset in range(0,len(route),4):
    group=route[offset:offset+4];assert len({(r['label'],r['position'],r['speculative']) for r in group})==1
    values=[(r['end_ns']-r['start_ns'])/1000 for r in group];calls.append(sum(values))
    for i,v in enumerate(values):stages[i].append(v)
   norm += [(r['end_ns']-r['start_ns'])/1000 for r in records if r['label'].endswith(('.hc.a.norm','.hc.f.norm'))]
  report['ranks'][str(rank)]=dict(route_calls=len(calls),route_call_median_us=statistics.median(calls),route_stage_median_us=dict(zip(('max','exp','rank','renormalize'),map(statistics.median,stages))),hc_norm_event_median_us=statistics.median(norm))
 report['interpretation']='Existing instrumented event costs only. Four dependent route launches plus all-pairs ranking; estimates per half are not end-to-end speedups. New candidates unmeasured.'
 save(P/'evidence/structure.json',report);print(json.dumps(report['ranks'],indent=2))
if __name__=='__main__':main()
