"""Copy the record kernels' include closure into native-pinned/ (own-packet pins only).

The record engine (packet189 v5 -> packet190 record) compiled its kernels against
packet189's checked include tree plus its root kernel_guard.hpp. Those are
cross-packet mutable files for the pin guard, so the exact bytes are copied here;
only absolute include paths are rewritten. Provenance (origin + digest) is kept
as data, not pins. The record headers are also checked byte-identical to the
record bundle (packet103) copies, as the study (section 0.2) states.
"""
import json,re,shlex,shutil,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,P189,NATIVE,BUILD,EV,limits,sha,rel,units_idle,parent
sys.path.insert(0,str(P.parents[1]/'ops'));from compile_turn import turn
CHECKED=P189/'build/checked';CHECKED_R=CHECKED.resolve();ICPX='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
RECORD=('p90_expert.hpp','p100_down.hpp','p65_expert.hpp','p90_layout.hpp','p49d_expert.hpp','p49b_gemv.hpp','p42_expert.hpp')
def normalized(mirror):
 """The checked mirror = kernel_guard include + #line preamble + absolutized includes around the root body."""
 lines=mirror.read_text().split('\n');i=0
 while i<len(lines) and (lines[i].startswith('#line') or lines[i].startswith('#include "/') or lines[i] in ('#ifndef OWN_RT_HOST_ONLY','#endif')):i+=1
 body=[]
 for line in lines[i:]:
  m=re.fullmatch(r'#include "/.*/packet189-twocard-k3x/(?:(?:build/checked|native-base)/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/)?(.+)"',line)
  body.append('#include "'+m.group(1)+'"' if m else line)
 return '\n'.join(body)
def mirror_transforms(mirror,root,name):
 """Allow exactly the checked-mirror rewrites: include absolutization (already normalized away) and the p35
 prepared-submission launch form (ownrt::prepared_submit + packet26::checked around the SAME kernel lambda)."""
 import difflib
 a=root.split('\n');b=mirror.split('\n');assert len(a)==len(b),name+' line count'
 kinds={}
 for x,y in zip(a,b):
  if x==y:continue
  if 'q.submit([&](sycl::handler&h){h.depends_on(deps);' in x and 'ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(' in y:k='p35_prepared_submit'
  elif 'h.parallel_for(sycl::nd_range<1>(' in x and 'h.parallel_for(p35_range0,packet26::checked(' in y:k='p35_checked_capture'
  elif any(y[i]==')' and y[:i]+y[i+1:]==x for i in range(len(y))):k='p35_close'
  else:raise AssertionError(name+': unexpected mirror difference: '+repr(x)[:120]+' vs '+repr(y)[:120])
  kinds[k]=kinds.get(k,0)+1
 return kinds
def main():
 limits();units=units_idle();BUILD.mkdir(exist_ok=True);EV.mkdir(exist_ok=True)
 probe=BUILD/'closure-probe.cpp';probe.write_text('#include "p90_expert.hpp"\n#include "p100_down.hpp"\nint main(){}\n')
 deps=BUILD/'closure-probe.d'
 cmd=[ICPX,'-std=gnu++20','-fsycl','-I'+str(CHECKED/'experiments/own-xpu-runtime/stage2/packet189-twocard-k3x'),'-I'+str(P189),'-MM','-MF',str(deps),str(probe.resolve())]
 with turn():subprocess.run(cmd,check=True,stdin=subprocess.DEVNULL,capture_output=True,timeout=600)
 text=deps.read_text().replace('\\\n',' ');files=[Path(t) for t in shlex.split(text.split(':',1)[1]) if t and Path(t).is_file()]
 files=[f.resolve() for f in files if f.resolve()!=probe.resolve()]
 assert all(f.is_relative_to(P189) for f in files),'closure outside packet189: '+str([str(f) for f in files if not f.is_relative_to(P189)])
 if NATIVE.exists():shutil.rmtree(NATIVE)
 rows=[];mapping={str(CHECKED):str(NATIVE/'checked'),str(CHECKED_R):str(NATIVE/'checked'),str(P189):str(NATIVE/'root')}
 for src in sorted(files):
  dest=NATIVE/'checked'/src.relative_to(CHECKED_R) if src.is_relative_to(CHECKED_R) else NATIVE/'root'/src.relative_to(P189)
  dest.parent.mkdir(parents=True,exist_ok=True)
  body=src.read_text();rewritten=body
  for old,new in mapping.items():rewritten=rewritten.replace(old,new)
  dest.write_text(rewritten)
  rows.append(dict(origin=rel(src),original_digest=sha(src),path=rel(dest),sha256=sha(dest),rewritten_includes=body!=rewritten))
 leftover=[l for r in rows for l in Path(ROOT/r['path']).read_text().split('\n') if l.startswith('#include "'+str(P189))]
 assert not leftover,'absolute parent include survived: '+str(leftover[:3])
 record={}
 for name in RECORD:
  checked=CHECKED/'experiments/own-xpu-runtime/stage2/packet189-twocard-k3x'/name;root=P189/name;bundle=P189.parent/'packet103-record-bundle'/name
  transforms=mirror_transforms(normalized(checked),root.read_text(),name)
  d=sha(root);record[name]=dict(root_digest=d,checked_mirror_digest=sha(checked),mirror_body_identical_to_root_modulo=transforms,packet103_record_bundle_identical=bundle.is_file() and sha(bundle)==d)
 assert record['p90_expert.hpp']['root_digest']=='17c976c49f71abeaafd08ad57f7c39251d39ba03ea947b75f7351e69f224e32b'
 assert record['p100_down.hpp']['root_digest']=='329ff3d028f39159fc960408ad69025d31da4c95a899e3a6f6b9da7127fa4a19'
 out=dict(schema='packet192.native-provenance.v1',description='Private include closure of the record expert kernels; only absolute include paths rewritten. Origins are provenance, not compile dependencies or pins.',
  closure_probe_command=cmd,file_count=len(rows),files=rows,record_kernel_sources=record,
  parents=[parent('packet189 checked include tree root (provenance only)',CHECKED/'experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/p90_expert.hpp')],units=units)
 (P/'native-provenance.json').write_text(json.dumps(out,indent=1)+'\n')
 print('native closure pinned:',len(rows),'files; record headers verified')
if __name__=='__main__':main()
