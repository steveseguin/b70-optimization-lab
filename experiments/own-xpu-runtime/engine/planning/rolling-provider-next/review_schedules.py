import sys,random,json
from pathlib import Path
from hashlib import sha256
_here=Path(__file__).resolve().parent
sys.path[:0]=[str(_here),str(_here.parent)]
from coordinator import RollingCoordinator
from test_coordinator import run
from test_ring_coordinator import Worker,reference
rng=random.Random(852771)
counted=0
for n in range(1000):
 count=rng.choice((2,3,4,6));plen=rng.choice((1,2,3,4,8,31,32,33,64));maximum=rng.choice((1,2,3,7,15,24));prompt=[rng.randrange(97) for _ in range(plen)];eos=(rng.randrange(97),);wire=rng.randrange(1000);stop=None if n%3 else rng.randrange(40)
 c=RollingCoordinator(stages=count,request=sha256(str(n).encode()).digest(),epoch=1,prompt=prompt,max_new=maximum,vocab=97,eos_token_ids=eos,context=128,initial_sequences=[wire]*count)
 workers=[Worker(i,count,1,prompt,wire) for i in range(count)]
 misses1=tuple(i for i in range(plen+maximum) if rng.random()<.4);misses2=tuple(i for i in range(plen+maximum) if rng.random()<.4)
 try:
  result=run(c,workers,random_seed=n,miss_first=misses1,miss_second=misses2,fresh_disagreement=n%7==0,stop_at_tick=stop)
  if not result['stopped']:
   inputs,outputs=reference(prompt,maximum,eos)
   assert c.emitted==outputs and c.provider.serial==len(inputs)-1
   assert all(w.ring.physical['history']==inputs for w in workers)
  counted+=1
 except Exception:
  print(json.dumps(dict(n=n,count=count,prompt=prompt,maximum=maximum,eos=eos,wire=wire,stop=stop,misses1=misses1,misses2=misses2)))
  raise
print(json.dumps({'passed':counted,'seed':852771,'scope':'CPU mocked arithmetic and event delivery only'}))
