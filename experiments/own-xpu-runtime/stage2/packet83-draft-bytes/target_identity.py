"""Target source/objects remain packet75; only draft registry/head differ."""
from build_engine import P,BASE,ROOT,sha,save,limits
import json

def main():
 limits();same={};deltas=[]
 for f in BASE.rglob('*'):
  if not f.is_file() or f.suffix not in ('.cpp','.hpp','.inc') or 'build' in f.relative_to(BASE).parts:continue
  g=P/f.relative_to(BASE)
  if not g.exists():continue
  if sha(f)==sha(g):same[str(g.relative_to(ROOT))]=sha(g)
  else:deltas.append(str(g.relative_to(P)))
 assert sorted(deltas)==['mtp.hpp','p59c_select.hpp'],deltas
 for n in ('main.cpp','rank.hpp','native_controller.hpp','arithmetic.hpp','p49d_submit.cpp','p49d_expert_submit.cpp','p74_submit.cpp','p60_submit.cpp','p49_qsa_kernel.hpp'):
  assert str((P/n).relative_to(ROOT)) in same
 build=json.loads((P/'evidence/object-identity.json').read_text());assert build['passed']
 for row in build['objects']:assert sha(ROOT/row['local'])==row['sha256']==sha(ROOT/row['source'])
 gate=json.loads((P/'evidence/cpu-gates.json').read_text());assert gate['passed'] and all(r['target_matches_parent'] for r in gate['views'].values())
 save(P/'evidence/target-identity.json',dict(passed=True,device_executed=False,sources={**same,str((P/'target_identity.py').relative_to(ROOT)):sha(P/'target_identity.py')},draft_only_modified_parent_files=deltas,inherited_object_count=len(build['objects']),scope='Packet75 target source bodies unchanged; inherited objects hash-identical; target bytes exact in miniature fresh processes. Shared draft selector is rebuilt; whole executable identity intentionally changes. Device target oracle remains mandatory.'))
if __name__=='__main__':main()
