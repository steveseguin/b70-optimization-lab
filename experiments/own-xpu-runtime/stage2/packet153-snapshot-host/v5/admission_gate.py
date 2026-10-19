"""Bind real full-shape censuses, class coverage and copied alias closure."""
import json,tarfile
from pathlib import Path
from p153_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

def main():
 limits();shape=P/'evidence/full-shape.json';proof=json.loads(shape.read_text());assert proof['passed'] and not proof['device_executed']
 rows=[]
 for run in proof['runs']:
  if run['fresh']:continue
  archive=ROOT/run['artifact']['path'];assert sha(archive)==run['artifact']['sha256']
  with tarfile.open(archive) as t:bank=json.loads(t.extractfile('class-layout.json').read())
  m=run['memory'];assert m['passed'] and 0<bank['bytes']<=600*1024**2
  maximum=m['planned_maximum_bytes'];actual=m['device_allocation_bytes'];ceiling=30*1024**3
  assert actual<=maximum<ceiling and m['planned_free_bytes']>=m['minimum_free_bytes']
  rows.append(dict(variant=bank['class_layout_bank'],rank=run['rank'],copied_weight_bytes=bank['bytes'],copied_weights=bank['weights'],actual_device_allocation_bytes=actual,planned_maximum_bytes=maximum,arena_ceiling_bytes=ceiling,arena_headroom_bytes=ceiling-actual,conservative_arena_headroom_bytes=ceiling-maximum,physical_capacity_bytes=m['capacity_bytes'],planned_physical_free_bytes=m['planned_free_bytes'],minimum_physical_free_bytes=m['minimum_free_bytes'],driver_residency_unmeasured=True))
 assert len(rows)==4
 aliases=json.loads((LOCAL/'lineage-inputs/current-aliases.json').read_text());original=json.loads((LOCAL/'lineage-inputs/vendor-origin.json').read_text())['symlinks']
 assert set(aliases)==set(original)
 for name,target in aliases.items():assert (LOCAL/name).is_symlink() and str((LOCAL/name).readlink())==target and (LOCAL/name).exists(),name
 binaries=json.loads((LOCAL/'lineage-inputs/packet136-history/copy142.json').read_text())['immutable_binaries'];binaries.update(json.loads((LOCAL/'immutable-binaries.json').read_text()));checked=set();oracle=0
 for f in LOCAL.rglob('*'):
  if not f.is_symlink():continue
  target=f.resolve();assert target.exists(),str(f)
  if target.is_relative_to(LOCAL):continue
  if target==LOCAL.parent/'packet49-integrate/oracle':oracle+=1;continue
  assert str(target) in binaries,'external non-allowlisted alias: '+str(f)
  if target not in checked:assert sha(target)==binaries[str(target)];checked.add(target)
 sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'admission_gate.py',shape,LOCAL/'immutable-binaries.json',LOCAL/'lineage-inputs/current-aliases.json',LOCAL/'lineage-inputs/packet136-history/copy142.json')}
 save(P/'evidence/admission.json',dict(passed=True,device_executed=False,rows=rows,host_required_available_bytes=97*1024**3+1200*1024**2,original_symlink_objects_preserved=len(aliases),external_binary_hashes_verified=len(checked),oracle_authority_aliases=oracle,sources=sources))
 print('Four rank/class admissions and all preserved aliases PASS')
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
