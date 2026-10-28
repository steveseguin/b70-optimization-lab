#!/usr/bin/env python3
"""CPU-only real scheduler paired profile; no model/device/socket work."""
import cProfile,gc,hashlib,importlib.util,io,json,pathlib,pstats,sys,time
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'engine/planning'))
import ring_coordinator as core
from rolling_provider.dedicated import DedicatedCoordinator
from rolling_provider.coordinator import RollingCoordinator
spec=importlib.util.spec_from_file_location('bounded_profile_candidate',HERE/'ring_coordinator.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
original=core.Coordinator._live_count
result={'scope':'CPU-only real scheduler; direct shared adoption is not native authentication; cProfile overhead included; not predicted GPU speedup','runs':[]}
for arg in sys.argv[1:]:
 p=pathlib.Path(arg);plan=json.loads(p.read_text());pair={}
 for mode,method in [('original',original),('candidate',m.Coordinator._live_count)]:
  c=DedicatedCoordinator(stages=2,request=bytes.fromhex(plan['request_sha256']),epoch=0,
   prompt=plan['prompt_tokens'],max_new=plan['max_new'],context=plan['context'],vocab=plan['vocab'],
   eos_token_ids=plan['eos_token_ids'],stream_bytes=40960,speculative_depth=3)
  RollingCoordinator.adopt_prefill(c,len(c.prompt)-2)
  profile=cProfile.Profile();counts=[];commands=[]
  with patch.object(core.Coordinator,'_live_count',method):
   start=time.perf_counter();profile.enable()
   for _ in range(10):
    emitted=c.commands();counts.append(len(emitted));commands.extend(emitted)
   profile.disable();elapsed=time.perf_counter()-start
  buf=io.StringIO();stats=pstats.Stats(profile,stream=buf).sort_stats('cumulative');stats.print_stats(18)
  pair[mode]={'seconds':elapsed,'profile':buf.getvalue(),'counts':counts,'commands':repr(commands),
   'events':repr(c.events),'frontier':c.frontier,'retained_rows':len(c.rows)}
  del c;gc.collect()
 assert all(pair['original'][k]==pair['candidate'][k] for k in ['counts','commands','events','frontier','retained_rows'])
 result['runs'].append({'plan':str(p),'plan_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
    'prompt_rows':len(plan['prompt_tokens']),'modes':pair,'identical_commands_events_state':True})
print(json.dumps(result,indent=2))
