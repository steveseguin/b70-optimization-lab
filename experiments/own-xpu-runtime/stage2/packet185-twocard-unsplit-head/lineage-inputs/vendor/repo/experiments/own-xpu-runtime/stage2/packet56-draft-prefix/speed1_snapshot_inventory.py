"""Read-only production snapshot schedule and exclusion-proof audit."""
import gzip,hashlib,json,math
from pathlib import Path
P=Path(__file__).resolve().parent;E=P/'evidence/speed1';LIMIT=134217728;WIDTH=32

def schedule(sizes):
 lengths=sorted(min(LIMIT,n-off) for n in sizes for off in range(0,n,LIMIT))
 batches=[];cursor=0
 while cursor<len(lengths):
  items=[]
  while cursor<len(lengths) and len(items)<WIDTH and sum(items)+lengths[cursor]<=LIMIT:
   items.append(lengths[cursor]);cursor+=1
  assert items and 0<sum(items)<=LIMIT;batches.append(items)
 return batches

def main():
 pins={};rows=[];proof=[]
 def read(p):
  raw=p.read_bytes();pins[str(p.relative_to(P))]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
 for dr in (0,1):
  root=P/f'build/results-f912fdaf6/c4096-dr{dr}-gpu/WS128/run/ranks/rank0'
  allocations=read(root/'census.json')['allocations'];plan=read(root/'launch-plan.json')
  backup=next(x for x in allocations if x['label']=='card0:speculative-private-image')
  represented={'card0:'+x['name'] for x in plan['buffers']}|{x['label'] for x in allocations if x['label'].startswith('card0:alternate:')}
  outputs={'token','position','token_history'};kv=set();writers={};readers={}
  for i,site in enumerate(plan['launches']):
   outputs.update(site['outputs'])
   if site['op']=='qsa_append_pool':kv.update(site['outputs'])
   for name in site['inputs']:readers.setdefault(name,(i,site['label']))
   for name in site['outputs']:writers.setdefault(name,(i,site['label']))
  sources=[dict(name=b['name'],bytes=b['bytes'],kv=b['name'] in kv,pooled=b['name'].endswith('.pooled')) for b in plan['buffers'] if b['name'] in outputs]
  standalone=[x for x in allocations if x['id']<backup['id'] and x['live'] and x['memory']=='device' and x['category']!='weights' and x['label'] not in represented and x['label']!='card0:mixture-one']
  sources.extend(dict(name=x['label'],bytes=x['bytes'],kv=False,pooled=False) for x in standalone)
  assert sum(x['bytes'] for x in sources)==backup['bytes']
  for source in sources:
   name=source['name'];first=writers.get(name);read_first=readers.get(name)
   proof.append(dict(draft_rank=dr,extent=name,allocation_bytes=source['bytes'],first_writer_site=first[1] if first else None,
    first_reader_site=read_first[1] if read_first else None,writer_precedes_first_reader=bool(first and (not read_first or first[0]<read_first[0])),
    full_write_coverage_proven=False,coverage_bytes_proven_by_inputs_outputs_metadata=None,
    excluded=False,reason='Cancelled prefixes may end before this writer; overwritten old bytes remain observable at terminal rollback. Standalone kernel workspace subranges are not described by plan inputs/outputs.'))
  for position in (100,128,214):
   sizes=[x['bytes']-((position//4 if x['pooled'] else position)*(x['bytes']//(1024 if x['pooled'] else 4096)) if x['kv'] else 0) for x in sources]
   batches=schedule(sizes);assert sum(map(sum,batches))==sum(sizes)
   rows.append(dict(draft_rank=dr,position=position,capture_bytes=sum(sizes),restore_bytes=sum(sizes),old_copy_calls=sum(math.ceil(n/LIMIT) for n in sizes),
    capture_submissions=len(batches),restore_submissions=len(batches),largest_submission_bytes=max(map(sum,batches)),
    validated_component_copies=sum(map(len,batches)),batches=batches,excluded_bytes=0))
 artifact=E/'writer-proof.json.gz';artifact.write_bytes(gzip.compress(json.dumps(proof,sort_keys=True).encode(),mtime=0))
 row=dict(passed=True,device_executed=False,weight_bytes_read=0,input_sha256=pins,source_sha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ('strict_snapshot.hpp','speed1_snapshot_inventory.py')},
  rows=rows,writer_proof=dict(path=str(artifact.relative_to(P)),sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),extents=len(proof)),excluded_extents=[],scope='Exact existing full-state extent set, fewer submissions; no unsupported exclusion or byte-reduction claim',
  production_sizing='Retained allocation/plan metadata at context 4096; no arithmetic or tensor payload read')
 (P/'speed1-snapshot-inventory.json').write_text(json.dumps(row,indent=2)+'\n')
 print(json.dumps([{k:v for k,v in r.items() if k!='batches'} for r in rows],indent=2))
if __name__=='__main__':main()
