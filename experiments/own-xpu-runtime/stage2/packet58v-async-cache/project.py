"""Conditional per-prompt overlap sensitivities, never measured speed."""
import json,statistics,resource
from pathlib import Path
P=Path(__file__).resolve().parent
BASE=P.parent/'packet58p-onecard-record/evidence/card0-58p-a/WS128'
def main():
    summary=json.loads((BASE/'summary.json').read_text())
    caches=[json.loads(x) for x in (BASE/'run/run/cache.jsonl').read_text().splitlines()]
    pos=0;prompts=[]
    for req in summary['requests']:
        folder=BASE/'run/run'/req['prompt_id']
        pre=[json.loads(x) for x in (folder/'prefill-timings.jsonl').read_text().splitlines()]
        gen=[json.loads(x) for x in (folder/'timings.jsonl').read_text().splitlines()]
        pos+=len(pre);selected=caches[pos+1:pos+100];pos+=len(gen)
        assert len(selected)==99
        stamps=req['token_timestamps']
        prompts.append(dict(prompt=req['prompt_id'],prompt_class=req['prompt_class'],duration_ms=(stamps[99]-stamps[0])*1000,
            cache_ms=sum(x['wall_ms'] for x in selected),fill_bytes=sum(x['fill_bytes'] for x in selected)))
    assert pos==len(caches)
    cases={}
    for name,cost in [('baseline',lambda p:0),('hide_fill_at_assumed_25_GB_s_minus_0.25ms_overhead',lambda p:max(0,p['fill_bytes']/25e6-99*.25)),
                      ('hide_half_cache_wall_minus_0.5ms_overhead',lambda p:max(0,p['cache_ms']*.5-99*.5)),
                      ('remove_entire_cache_wall_impossible_upper_bound',lambda p:p['cache_ms'])]:
        classes={}
        for p in prompts:classes.setdefault(p['prompt_class'],[]).append(99000/(p['duration_ms']-cost(p)))
        cases[name]=statistics.median(statistics.median(v) for v in classes.values())
    row=dict(passed=True,device_executed=False,projected_not_measured=True,prompts=prompts,conditional_tok_s=cases,
        gain_percent={k:(v/cases['baseline']-1)*100 for k,v in cases.items()},
        assumptions=['No added zero-copy misses or hit-rate loss from delayed publication',
                     'BCS fills overlap compute without bandwidth contention or driver serialization',
                     'CPU planning is hidden within already-enqueued compute',
                     'Publication overhead is the explicit assumed per-token deduction, not a measurement',
                     'No benefit is assigned to prompt/KV/response reuse; arithmetic unchanged'])
    (P/'evidence/projections.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps({k:round(v,5) for k,v in cases.items()}))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
