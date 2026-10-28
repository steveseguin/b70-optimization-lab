#!/usr/bin/env python3
"""CPU-only bounded profile of actual scheduler retained-prefix scans; no native/device IO.
Calls the real shared prefix-adoption implementation directly, not authentication:
this isolates scheduler cost, and does not claim a native adoption receipt.
"""
import cProfile, gc, hashlib, io, json, pathlib, pstats, sys, time
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'engine/planning'))
from rolling_provider.dedicated import DedicatedCoordinator
from rolling_provider.coordinator import RollingCoordinator
result={'scope':'CPU scheduler only; no native execution or authenticated adoption claim','runs':[]}
for arg in sys.argv[1:]:
 p=pathlib.Path(arg);plan=json.loads(p.read_text());prompt=plan['prompt_tokens']
 model=DedicatedCoordinator(stages=2,request=bytes.fromhex(plan['request_sha256']),epoch=0,
  prompt=prompt,max_new=plan['max_new'],context=plan['context'],vocab=plan['vocab'],
  eos_token_ids=plan['eos_token_ids'],stream_bytes=40960,speculative_depth=3)
 start=time.perf_counter();RollingCoordinator.adopt_prefill(model,len(prompt)-2);adopt=time.perf_counter()-start
 profile=cProfile.Profile();profile.enable()
 counts=[]
 for _ in range(10):counts.append(len(model.commands()))
 profile.disable();buf=io.StringIO();pstats.Stats(profile,stream=buf).sort_stats('cumulative').print_stats(18)
 result['runs'].append(dict(plan=str(p),plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
  prompt_rows=len(prompt),retained_rows=len(model.rows),adoption_seconds=adopt,
  command_counts=counts,profile=buf.getvalue()))
 del model;gc.collect()
print(json.dumps(result,indent=2))
