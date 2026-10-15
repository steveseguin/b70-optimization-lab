"""Replay snapshot extent formulas on retained metadata; no tensor bytes."""
import hashlib,json,math
from pathlib import Path
E=Path(__file__).resolve().parent;P=E.parents[1];out=[];hashes={}
def read(p):
 raw=p.read_bytes();hashes[str(p.relative_to(P))]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
for dr in (0,1):
 root=P/f'build/c4096-dr{dr}-gpu/WS128/run/ranks/rank0'
 allocations=read(root/'census.json')['allocations'];plan=read(root/'launch-plan.json')
 backup=next(x for x in allocations if x['label']=='card0:speculative-private-image')
 represented={'card0:'+x['name'] for x in plan['buffers']}|{x['label'] for x in allocations if x['label'].startswith('card0:alternate:')}
 outputs={'token','position','token_history'};kv=set()
 for launch in plan['launches']:
  outputs.update(launch['outputs'])
  if launch['op']=='qsa_append_pool':kv.update(launch['outputs'])
 sources=[dict(name=b['name'],bytes=b['bytes'],kv=b['name'] in kv,pooled=b['name'].endswith('.pooled')) for b in plan['buffers'] if b['name'] in outputs]
 standalone=[x for x in allocations if x['id']<backup['id'] and x['live'] and x['memory']=='device' and x['category']!='weights' and x['label'] not in represented and x['label']!='card0:mixture-one']
 sources.extend(dict(name=x['label'],bytes=x['bytes'],kv=False,pooled=False) for x in standalone)
 assert sum(x['bytes'] for x in sources)==backup['bytes']
 rows=[]
 for position in (100,128,214):
  sizes=[x['bytes']-((position//4 if x['pooled'] else position)*(x['bytes']//(1024 if x['pooled'] else 4096)) if x['kv'] else 0) for x in sources]
  rows.append(dict(position=position,payload_bytes=sum(sizes),copy_calls=sum(math.ceil(n/134217728) for n in sizes)))
 telemetry=[dict(path=str(f.relative_to(P)),receipt=read(f)) for f in sorted((P/f'build/c4096-dr{dr}-gpu/WS128/run/repeat-1').glob('*/rank0/speculative-snapshot.json'))]
 out.append(dict(draft_rank=dr,capacity_bytes=backup['bytes'],source_extents=len(sources),standalone=standalone,rows=rows,cumulative_snapshot_receipts=telemetry))
(E/'snapshots.json').write_text(json.dumps(dict(rows=out,input_hashes=hashes),indent=2)+'\n')
print(json.dumps([{k:v for k,v in r.items() if k not in ('standalone','cumulative_snapshot_receipts')} for r in out],indent=2))
