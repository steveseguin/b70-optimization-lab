"""Read-only production snapshot schedule and write-set audit."""
import gzip,hashlib,json,math
from pathlib import Path
P=Path(__file__).resolve().parent;E=P/'evidence/speed4';LIMIT=134217728;WIDTH=32

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
 sweep=json.loads((P/'speed4-plan-gates.json').read_text())
 def read(p):
  raw=p.read_bytes();pins[str(p.relative_to(P))]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
 for dr,split in ((0,0),(1,0),(0,24)):
  root=P/(f'build/results-f912fdaf6/c4096-dr{dr}-gpu/WS128/run/ranks/rank0' if not split else 'build/speed3-c4096-dr0-s24-gpu/WS128/run/ranks/rank0')
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
  for context in (4096,32768):
   matches=[r for r in sweep['rows'] if r['plan']=='target' and r['rank']==0 and r['draft_rank']==dr and r['target_split']==split and r['context']==context]
   assert len(matches)==3
   bounds={r['write_set']['scratch_bound'] for r in matches};assert len(bounds)==1
   scratch_bound=bounds.pop();qsa={r['name']:r for r in matches[0]['write_set']['qsa_rows']}
   assert all(r['write_set']['qsa_rows']==matches[0]['write_set']['qsa_rows'] for r in matches)
   redo_banks={b['name']:b for b in matches[0]['write_set']['redo_banks']}
   assert all(r['write_set']['redo_banks']==matches[0]['write_set']['redo_banks'] for r in matches)
   current_outputs=[x for x in sources if not x['name'].startswith('card0:')]
   assert sum(qsa[x['name']]['allocation_bytes'] if x['kv'] else x['bytes'] for x in current_outputs)==matches[0]['write_set']['plan_output_bytes']
   assert len(current_outputs)==matches[0]['write_set']['plan_output_count']
   for position in (100,128,214):
    sizes=[];old_sizes=[];extent_rows=[]
    for source in sources:
     name=source['name'];full=source['bytes'];skip=0;covered=full;rule='full allocation; conservative union'
     if source['kv']:
      q=qsa[name];full=q['allocation_bytes'];skip=(position//4 if q['pooled'] else position)*q['row_bytes'];covered=q['row_bytes'];rule='single token QSA append; pooled row retained unconditionally'
     if name=='card0:operator-scratch':covered=scratch_bound;rule='union of all selectable parallel writer prefixes'
     assert 0<=skip<=full and 0<=covered<=full-skip
     sizes.append(covered);old_sizes.append(full-skip)
     first=writers.get(name)
     extent_rows.append(dict(name=name,allocation_bytes=full,offset=skip,captured_bytes=covered,rule=rule,first_writer_site=first[1] if first else ('plan scratch writers' if name=='card0:operator-scratch' else 'retained standalone owner'),coverage='superset of every possible write; untouched bytes not copied',redo_overwritten=name in redo_banks,redo_first_writer=redo_banks.get(name,{}).get('first_writer'),redo_covered_bytes=redo_banks.get(name,{}).get('bytes',0)))
    batches=schedule([n for n in sizes if n]);assert sum(map(sum,batches))==sum(sizes)
    proof.append(dict(target_split=split,draft_rank=dr,context=context,position=position,extents=extent_rows))
    omitted=sum(x['captured_bytes'] for x in extent_rows if x['redo_overwritten'])
    assert all(x['captured_bytes']==x['redo_covered_bytes'] for x in extent_rows if x['redo_overwritten'])
    redo_sizes=[x['captured_bytes'] for x in extent_rows if not x['redo_overwritten'] and x['captured_bytes']]
    rows.append(dict(target_split=split,redo_restore_bytes=sum(redo_sizes),redo_omitted_bytes=omitted,redo_restore_submissions=len(schedule(redo_sizes)),draft_rank=dr,context=context,position=position,capture_bytes=sum(sizes),restore_bytes=sum(sizes),old_capture_bytes=sum(old_sizes),
     old_submissions=len(schedule(old_sizes)),capture_submissions=len(batches),restore_submissions=len(batches),largest_submission_bytes=max(map(sum,batches)),
     validated_component_copies=sum(map(len,batches)),batches=batches,untouched_bytes_not_copied=sum(old_sizes)-sum(sizes),scratch_bound=scratch_bound))
 artifact=E/'redo-restore-proof.json.gz';artifact.write_bytes(gzip.compress(json.dumps(proof,sort_keys=True).encode(),mtime=0))
 row=dict(passed=True,device_executed=False,weight_bytes_read=0,input_sha256=pins,source_sha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ('strict_snapshot.hpp','speed4_snapshot_inventory.py','speed4_plan_gate.py')},
  rows=rows,writer_proof=dict(path=str(artifact.relative_to(P)),sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),extents=len(proof)),scope='Capture/full rollback unchanged. Confirmed same-position redo may omit fully overwritten physical spare banks only; abandonment restores deferred bytes before any other command.',
  plan_gate_sha256=hashlib.sha256((P/'speed4-plan-gates.json').read_bytes()).hexdigest(),production_sizing='Retained 4096 allocation metadata plus actual 4096/32768 plan construction; no arithmetic or tensor payload read')
 (P/'speed4-snapshot-inventory.json').write_text(json.dumps(row,indent=2)+'\n')
 print(json.dumps([{k:v for k,v in r.items() if k!='batches'} for r in rows],indent=2))
if __name__=='__main__':main()
