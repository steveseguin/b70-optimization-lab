"""Prove copied sources and immutable linked objects; retain the exact overlay."""
import difflib,json
from build_engine import P,ROOT,BASE,B,sha,save,limits,CHECKED
def main():
 limits();pins=json.loads((P/'source-copy-provenance.json').read_text())['packet103'];patch=[];deltas=[];unchanged=[]
 prefix=BASE/'build/checked'
 for name,digest in pins.items():
  original=ROOT/name;assert sha(original)==digest,name
  local=P/'sources'/original.relative_to(prefix)
  expected=original.read_text().replace(str(prefix),str(P/'sources'));actual=local.read_text()
  if expected==actual:unchanged.append(str(local.relative_to(ROOT)))
  else:
   assert local.name in ('main.cpp','p49d_submit.cpp','argument_block.hpp'),name
   deltas.append(str(local.relative_to(ROOT)))
   patch.extend(difflib.unified_diff(expected.splitlines(True),actual.splitlines(True),fromfile='packet103/'+local.name,tofile='p109/'+local.name))
 for name in ('main.cpp','rank.hpp','mtp.hpp'):
  patch.extend(difflib.unified_diff((CHECKED/name).read_text().splitlines(True),(B/'native'/name).read_text().splitlines(True),fromfile='copied/'+name,tofile='native/'+name))
 (P/'native-overlay.patch').write_text(''.join(patch))
 build=json.loads((P/'evidence/build.json').read_text())
 for name,digest in build['sources'].items():
  assert '/ops/' not in name and not name.endswith('/packet103-record-bundle/selection.json'),name
  assert sha(ROOT/name)==digest,name
 prior=json.loads((P/'lineage/parent-engine-commands.json').read_text());objects=[]
 for mode in ('gnu-host','device'):
  old=next(r['command'] for r in prior if r['name']==mode+'-link')
  new=next(r['command'] for r in build['commands'] if r['name']==mode+'-link')
  kept=lambda cmd:[x for x in cmd if x.endswith('.o') and not x.endswith(('/entry-main.o','/p49d_submit.o'))]
  assert kept(old)==kept(new)
  objects.extend(dict(mode=mode,path=str(__import__('pathlib').Path(x).relative_to(ROOT)),sha256=sha(x)) for x in kept(new))
 save(P/'evidence/native-source-audit.json',dict(passed=True,device_executed=False,unchanged_after_include_relocation=len(unchanged),deltas=deltas,unchanged_linked_objects=objects,overlay_sha256=sha(P/'native-overlay.patch'),sources={str((P/'audit_sources.py').relative_to(ROOT)):sha(P/'audit_sources.py')}))
 print('copied sources and all unchanged linked objects verified')
if __name__=='__main__':main()
