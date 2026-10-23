"""Copy the record kernels' include closure from packet192's pinned copy into native-pinned/ (own-packet pins).

packet192 pinned the record engine's checked include tree (46 files, provenance in its native-provenance.json;
root `p90_expert.hpp` 17c976c4..., `p100_down.hpp` 329ff3d0..., byte-identical to packet103's record bundle).
This packet copies those bytes (never edits packet192's or packet189's trees), rewrites only the absolute
include paths to this packet, re-verifies every file against packet192's recorded digests and the record
headers against packet189's root files read in place. The pinned production sources are never edited:
candidates live in `p193_diet.hpp` beside them.
"""
import json,re,sys
from pathlib import Path
from build_engine import P,ROOT,P192,P189,NATIVE,EV,limits,sha,rel,read,parent
RECORD={'p90_expert.hpp':'17c976c49f71abeaafd08ad57f7c39251d39ba03ea947b75f7351e69f224e32b','p100_down.hpp':'329ff3d028f39159fc960408ad69025d31da4c95a899e3a6f6b9da7127fa4a19'}
def main():
 limits();EV.mkdir(exist_ok=True)
 prov=read(P192/'native-provenance.json');assert prov['schema']=='packet192.native-provenance.v1' and prov['file_count']==46
 src_root=P192/'native-pinned';assert src_root.is_dir()
 if NATIVE.exists():
  import shutil;shutil.rmtree(NATIVE)
 rows=[];old=str(src_root);new=str(NATIVE)
 for row in prov['files']:
  src=ROOT/row['path'];assert sha(src)==row['sha256'],'packet192 pinned file changed: '+row['path']
  dest=NATIVE/src.relative_to(src_root);dest.parent.mkdir(parents=True,exist_ok=True)
  body=src.read_text();rewritten=body.replace(old,new);dest.write_text(rewritten)
  rows.append(dict(origin=row['origin'],original_digest=row['original_digest'],packet192_path=row['path'],packet192_digest=row['sha256'],path=rel(dest),sha256=sha(dest),rewritten_includes=body!=rewritten))
 leftover=[l for r in rows for l in Path(ROOT/r['path']).read_text().split('\n') if '#include "'+old in l or '#include "'+str(P189) in l]
 assert not leftover,'absolute parent include survived: '+str(leftover[:3])
 record={}
 for name,digest in RECORD.items():
  root=P189/name;assert sha(root)==digest,'record header changed in packet189: '+name
  bundle=P189.parent/'packet103-record-bundle'/name
  record[name]=dict(root_digest=digest,packet189_root_verified_in_place=True,packet103_record_bundle_identical=bundle.is_file() and sha(bundle)==digest,
   checked_mirror_digest=prov['record_kernel_sources'][name]['checked_mirror_digest'],mirror_body_identical_to_root_modulo=prov['record_kernel_sources'][name]['mirror_body_identical_to_root_modulo'])
 out=dict(schema='packet193.native-provenance.v1',description='Private include closure of the record expert kernels, copied byte-for-byte from packet192/native-pinned (itself packet189 checked tree + root kernel_guard.hpp); only absolute include paths rewritten. Origins are provenance, never pins.',
  source_packet=rel(P192/'native-provenance.json'),source_provenance_digest=sha(P192/'native-provenance.json'),file_count=len(rows),files=rows,record_kernel_sources=record,
  parents=[parent('packet192 native provenance (provenance only)',P192/'native-provenance.json'),parent('packet189 root p90_expert.hpp (provenance only)',P189/'p90_expert.hpp'),parent('packet189 root p100_down.hpp (provenance only)',P189/'p100_down.hpp')])
 (P/'native-provenance.json').write_text(json.dumps(out,indent=1)+'\n')
 print('native closure copied:',len(rows),'files; record headers verified in place')
if __name__=='__main__':main()
