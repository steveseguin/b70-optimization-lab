"""Prove that only split admission changes in the production C++ closure."""
import difflib,json,gzip,collections
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits

def main():
 limits();original=json.loads((P/'copy-lineage.json').read_text());changed=[];sources={}
 for n,h in original['source_hashes'].items():
  if Path(n).suffix not in ('.cpp','.hpp','.inc') or n.startswith('lineage-inputs/'):continue
  path=P/n;sources[str(path.relative_to(ROOT))]=sha(path)
  if sha(path)!=h:changed.append(n)
 assert set(changed)=={'main.cpp','rank.hpp'},changed
 patches=[]
 for n in changed:
  old=P/'lineage-inputs'/('p118-'+n);new=P/n
  assert sha(old)==original['source_hashes'][n]
  # Every changed production line must be an admission predicate. Neither
  # split's existing boundary/filter nor any per-layer operation is rewritten.
  before=old.read_text().splitlines(True);after=new.read_text().splitlines(True)
  delta=list(difflib.unified_diff(before,after,fromfile='p118/'+n,tofile='p120/'+n));patches+=delta
  for line in delta:
   if line.startswith(('+','-')) and not line.startswith(('+++','---')):
    assert 'require(' in line and 'target_split' in line,line
  sources[str(old.relative_to(ROOT))]=sha(old)
 (P/'placement.patch').write_text(''.join(patches))
 shape=json.loads((P/'evidence/full-shape.json').read_text());plans={}
 for r in shape['runs']:
  art=r['artifacts']['native-plan.json'];f=ROOT/art['path'];assert sha(f)==art['sha256'];sources[art['path']]=sha(f)
  plans[(r['placement'],r['rank'])]=json.loads(gzip.decompress(f.read_bytes()))
 for rank in (0,1):
  before=plans['1',rank];after=plans['25-23',rank]
  def without24(rows):return [r for r in rows if not r.get('label',r.get('name','')).startswith('blk.24.')]
  assert without24(before['tensor_owners'])==without24(after['tensor_owners'])
  assert without24(before['launch_census'])==without24(after['launch_census'])
 for key,field in [('tensor_owners','name'),('launch_census','label')]:
  old=[r for r in plans['1',1][key] if r[field].startswith('blk.24.')]
  new=[r for r in plans['25-23',0][key] if r[field].startswith('blk.24.')]
  assert old and old==new,'moved layer operation/storage changed'
  assert not any(r[field].startswith('blk.24.') for r in plans['1',0][key])
  assert not any(r[field].startswith('blk.24.') for r in plans['25-23',1][key])
 save(P/'evidence/source-audit.json',dict(passed=True,device_executed=False,changed_cpp=changed,moved_layer=24,other_layers_unchanged=True,moved_layer_operations_and_storage_identical=True,device_model_output_pending=True,sources=sources))
 print('Only admission guards changed; every real-shape layer operation/storage identity preserved')
if __name__=='__main__':main()
