#!/usr/bin/env python3
"""Hash original evidence; prove identical numerical files and schedule bodies."""
import hashlib,json,difflib
from pathlib import Path
P=Path(__file__).resolve().parent;S=P.with_name('packet21-fused');ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(t):return hashlib.sha256(t.encode()).hexdigest()
def function(t,start):
 a=t.index(start);b=t.index('{',a);depth=1;i=b+1
 # Selected functions contain no braces in string literals other than balanced ones.
 while depth:
  depth+=(t[i]=='{')-(t[i]=='}');i+=1
 return t[a:i]
def main():
 old=json.loads((S/'build-receipt.json').read_text());files={};changed={}
 for name,h in old['compile_sources_before_and_after'].items():
  original=Path(name);assert sha(original)==h, name
  target=P/original.relative_to(S) if original.is_relative_to(S) else original
  if original.name=='CMakeLists.txt':continue
  if sha(target)==h:files[str(target.relative_to(ROOT))]=h
  else:changed[original.name]=dict(before=h,after=sha(target))
 assert set(changed)=={'main.cpp','owner.cpp','owner.hpp','backend.hpp','canary.hpp','adapter.cpp','adapter_fixture.cpp','gemv_batch.cpp','gemv_fixture.cpp','nongemv_fixture.cpp','runtime_kernels.cpp'},changed
 before=(S/'main.cpp').read_text();after=(P/'main.cpp').read_text()
 sections={}
 for name,starts in {'adapter.cpp':['template<class Team> void tiny(', 'template<class Team> void simple(', 'template<class Team> void chain_body(', 'template<class Team> void rank_body('], 'gemv_batch.cpp':['PreparedBatch prepare_batch(']}.items():
  for start in starts:
   a=function((S/name).read_text(),start);b=function((P/name).read_text(),start);assert a==b,(name,start);sections[name+':'+start]=digest(a)
 for start in ['static flash::Plan plan(', 'unsigned variant(', 'unsigned weight_variant(', 'Matrix matrix(', 'void linear(', 'void make_schedule(', 'void fused_batch(', 'void fused_non_gemv(']:
  a=function(before,start);b=function(after,start);assert a==b,start;sections[start]=digest(a)
 # Binding helper changes only memoization, preserving all types, extents and arithmetic descriptors.
 a=function(before,'std::pair<Spec,std::vector<Allocation>> bind_site(')
 b=function(after,'std::pair<Spec,std::vector<Allocation>> bind_site(')
 b=b.replace('      if(a.cards==2){auto found=bound_sites.find(l.label);if(found!=bound_sites.end())return found->second;}\n','').replace('      if(a.cards==2)bound_sites.emplace(l.label,std::make_pair(s,bindings));\n','')
 assert a==b;sections['bind_site minus memoization']=digest(a)
 receipts={}
 for name in ['cpu-real-frozen.json','cpu-real-r5.json','sanitizer-real-short.json','sanitizer-real-full.json',*[f'sanitizer-real-short-{s}.json' for s in (0,1,17,73)]]:
  f=S/name;r=json.loads(f.read_text());assert r['passed'] and not r['device_executed'];receipts[str(f.relative_to(ROOT))]=dict(sha256=sha(f),binary_sha256=r.get('binary_sha256'),passed=True)
 out=dict(passed=True,device_executed=False,arithmetic='iq3-p17-detmath-v2',original_build_sha256=sha(S/'build-receipt.json'),byte_identical_files=files,byte_identical_main_regions=sections,changed_host_and_canary_files=changed,carried_receipts=receipts,parameter_storage_delta='Only descriptors and pointer arrays move from functor members to immutable owner-tracked USM blocks. Kernel arithmetic bodies, within-kernel phase order, barriers, BF16 stores and rounding expressions hash-identical. First-use metadata uploads add ordered completed copies, not model arithmetic. Imported packet6/7/8 overlays are exact string replacements in kernel_overlay.py. New real-eight.json is additional CPU oracle evidence; device equality remains K1/model gates.',scope='Frozen 64 tokens/384 layers, R5 8 tokens/384 layers, four-seed real short dependency sanitizer and full 87-position sanitizer. Original binary identities retained; no new long/resident run. Entire main.cpp is NOT byte-identical; numerical/schedule bodies are.')
 (P/'carryover-proof.json').write_text(json.dumps(out,indent=2)+'\n')
 (P/'host-plumbing.patch').write_text(''.join(''.join(difflib.unified_diff((S/n).read_text().splitlines(True),(P/n).read_text().splitlines(True),fromfile='packet21/'+n,tofile='packet23/'+n)) for n in changed))
if __name__=='__main__':main()
