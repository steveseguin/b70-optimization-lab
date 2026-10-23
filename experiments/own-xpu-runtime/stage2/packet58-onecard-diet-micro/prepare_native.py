"""Pin the one-card record gate/up kernel's include closure into native-pinned/ (own-packet pins; never edited).

The production kernel is `p58ag_exp::Kernel<IQ2_S,2560,64,false,true,0,Cached=true>` compiled by the record line
packet58-onecard-cache23 (engine 083e3853..., LocalMaxxing cmvkcqznb002lng01fsrhjn7t) from its generated header
`native/generated/p58ag_expert.hpp` (sha 89394237...; byte-identical to the compiled `build/native/` copy) over its
frozen one-card include tree `frozen-inputs/repo/...` (headers pinned by `lineage/path-rewrite.json` after_sha256).
This packet copies the generated header and the transitive closure of its absolute `#include "..."` lines (every
`#ifdef` branch followed, so host and device closures are both covered), rewrites ONLY the absolute path prefix
(`.../packet58-onecard-cache23/frozen-inputs/repo` -> `<this packet>/native-pinned/repo`, and the generated header's
own location) so every header has exactly one path (one `#pragma once` identity), verifies every source byte-for-byte
against packet58-onecard-cache23's own pins, and records provenance. The candidate lives in `p58ag_diet.hpp` beside it.
"""
import json,re,shutil
from pathlib import Path
from build_engine import P,ROOT,P58C23,P58J,NATIVE,EV,limits,sha,rel,read,parent
GEN=P58C23/'native/generated/p58ag_expert.hpp';SUBMIT=P58C23/'native/generated/p58ag_submit.cpp';MAIN=P58C23/'native/generated/main.cpp'
GEN_SHA='893942377cc85ea347cb58d4627a0326b958a15ca5ddcf4246f6090822d0849e'   # packet58-onecard-diet stride_proof pin (evidence/layout-mismatch.json)
OLD_FROZEN=str(P58C23/'frozen-inputs/repo');NEW_FROZEN=str(NATIVE/'repo')
OLD_NATIVE=str(P58C23/'build/native');NEW_NATIVE=str(NATIVE)
INC=re.compile(r'^\s*#\s*include\s+"([^"]+)"',re.M)
def closure(start):
 seen=[];todo=[start]
 while todo:
  f=todo.pop()
  if f in seen:continue
  seen.append(f)
  for inc in INC.findall(f.read_text()):
   q=Path(inc)
   if not q.is_absolute():q=(f.parent/inc).resolve()
   assert q.is_file(),'include not found: '+inc+' from '+str(f)
   assert str(q).startswith(OLD_FROZEN) or q==GEN,'include outside the frozen one-card tree: '+str(q)
   if q not in seen:todo.append(q)
 return seen
def main():
 limits();EV.mkdir(exist_ok=True)
 assert sha(GEN)==GEN_SHA and sha(P58C23/'build/native/p58ag_expert.hpp')==GEN_SHA,'production header changed'
 pins=read(P58C23/'lineage/path-rewrite.json')['frozen_inputs']['files']
 engine=read(P58C23/'evidence/build.json');assert engine['artifacts']['build/device/own-rt-iq3']=='083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a','record engine identity'
 files=closure(GEN)
 if NATIVE.exists():shutil.rmtree(NATIVE)
 rows=[]
 for src in files:
  if src==GEN:dest=NATIVE/'p58ag_expert.hpp';pinned=GEN_SHA;pin_source='packet58-onecard-diet stride_proof / packet58-onecard-cache23 build/native copy'
  else:
   dest=Path(str(src).replace(OLD_FROZEN,NEW_FROZEN));key=str(src.relative_to(P58C23))
   pinned=pins[key]['after_sha256'] if key in pins else None;pin_source='packet58-onecard-cache23 lineage/path-rewrite.json after_sha256' if key in pins else 'not in path-rewrite.json (kernel_guard or unrewritten header); digest recorded'
  assert pinned is None or sha(src)==pinned,'frozen one-card header changed: '+str(src)
  dest.parent.mkdir(parents=True,exist_ok=True)
  body=src.read_text();rewritten=body.replace(OLD_FROZEN,NEW_FROZEN).replace(OLD_NATIVE,NEW_NATIVE);dest.write_text(rewritten)
  rows.append(dict(origin_relpath=rel(src),origin_digest=sha(src),origin_pin=pinned,origin_pin_source=pin_source,path=rel(dest),sha256=sha(dest),rewritten_includes=body!=rewritten))
 leftover=[l for r in rows for l in (ROOT/r['path']).read_text().split('\n') if ('#include "'+OLD_FROZEN) in l or ('#include "'+OLD_NATIVE) in l or '#include "/home' in l and NEW_FROZEN not in l and NEW_NATIVE not in l]
 assert not leftover,'absolute parent include survived: '+str(leftover[:3])
 out=dict(schema='packet58dm.native-provenance.v1',description='Private include closure of the one-card record gate/up kernel (p58ag_exp), copied byte for byte from packet58-onecard-cache23 (generated header + frozen one-card tree); only the absolute include/#line prefixes are rewritten so each header has one path. Origins are provenance, never pins.',
  production_kernel='p58ag_exp::Kernel<IQ2_S,2560,64,false,true,0,Cached=true> via p58ag::expert (experts=wide64+halfcache), b.indirect=true on the record line (caching()), 820-B p49bgemv rows, halfcache table binding p[19]',
  generated_header_sha256=GEN_SHA,record_engine_sha256='083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a',file_count=len(rows),files=rows,
  parents=[parent('packet58-onecard-cache23 generated gate/up header (provenance only)',GEN),parent('packet58-onecard-cache23 generated dispatch p58ag_submit.cpp (provenance only; not compiled here)',SUBMIT),
   parent('packet58-onecard-cache23 generated entry main.cpp (halfcache fill, b.indirect=caching(); provenance only)',MAIN),parent('packet58-onecard-cache23 lineage/path-rewrite.json (frozen header pins)',P58C23/'lineage/path-rewrite.json'),
   parent('packet58-onecard-cache23 evidence/build.json (record engine identity)',P58C23/'evidence/build.json'),parent('packet58-onecard-diet evidence/layout-mismatch.json (STOP report pins)',P.parent/'packet58-onecard-diet/evidence/layout-mismatch.json')])
 (P/'native-provenance.json').write_text(json.dumps(out,indent=1)+'\n')
 print('native closure copied:',len(rows),'files;',sum(r['origin_pin'] is not None for r in rows),'verified against packet58-onecard-cache23 pins')
if __name__=='__main__':main()
