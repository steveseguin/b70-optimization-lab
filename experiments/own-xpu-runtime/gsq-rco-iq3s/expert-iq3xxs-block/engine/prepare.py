#!/usr/bin/env python3
"""Source-only opt-in Engine overlay; never invokes compiler, Device or model I/O."""
import difflib,hashlib,json,re
from pathlib import Path
P=Path(__file__).resolve().parent;Q=P.parent;L=Q.parent;S=L/'state-bundle'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,m):
 if not v:raise ValueError(m)
def replace(s,a,b):
 need(s.count(a)==1,'unique anchor '+a[:100]);return s.replace(a,b)
def main():
 pins=json.loads((P/'parent-pins.json').read_text())
 for f,h in pins.items():need(sha(f)==h,'parent drift '+f)
 parent=json.loads((S/'preparation.json').read_text());base=Path(parent['materialized_directory']);dest=P/'build/source'
 need(not dest.exists(),'fresh source destination')
 sites=json.loads((Q/'selection.json').read_text())['sites'];graph=json.loads((L/'graph/new-plan.json').read_text())['launches'];census=json.loads((L/'metadata/new-census.json').read_text())['tensors']
 rows=[(s['label'],s['weight']) for s in sites]
 need(len(rows)==len(set(rows))==34,'exact34')
 need(re.findall(r'label=="([^"]+)"&&weight=="([^"]+)"',(Q/'selection.hpp').read_text())==rows,'same kernel selector')
 for label,weight in rows:
  launches=[x for x in graph if x['label']==label];need(len(launches)==1,'unique graph label');l=launches[0];t=census[weight]
  need(l['op']=='routed_gemv' and l['weights']==[weight] and l['shape']==[10,640,2560] and t['type_id']==18 and t['shape']==[512,640,2560] and t['bytes']==321126400,'exact graph/tensor')
  prefix=label.rsplit('.',1)[0]
  need(l['inputs']==[prefix+'.expert_input',prefix+'.routes','active','error'] and l['outputs']==[label,label+'.status'],'unchanged gather/route/status wiring')
 oldmain=(base/'main.cpp').read_text();oldentry=(base/'entry.cpp').read_text()
 generic=L/'qkv-q6-p33/engine/build/source/generic_engine.hpp';oldgeneric=generic.read_text()
 private=L/'integration/build/private/additive/packed.hpp'
 # The Engine already includes its checked facade; relocate includes only so
 # pragma-once cannot instantiate a second copy of gsqn under another path.
 original=(Q/'block.hpp').read_text();block=replace(original,'#include "../native-formats/packed.hpp"','#include "'+str(private)+'"')
 block=replace(block,'#include "selection.hpp"','#include "'+str(Q/'selection.hpp')+'"')
 need(block[block.index('namespace iq3block {'):]==original[original.index('namespace iq3block {'):],'byte-identical kernel/facade body')
 values=',\n'.join('{'+json.dumps(a)+','+json.dumps(b)+'}' for a,b in rows)
 policy='''#pragma once
static constexpr std::array<std::pair<const char*,const char*>,34> iq3_block_sites{{
'''+values+'''
}};
static bool iq3_block_site(const Weights&w,const Options&a,const flash::Launch&l){
 if(!a.expert_iq3xxs_block)return false;
 for(auto [label,weight]:iq3_block_sites)if(l.label==label||std::find(l.weights.begin(),l.weights.end(),weight)!=l.weights.end()){
  require(a.gsq_packed&&a.attention_q8_p33&&a.qkv_q6_p33&&!a.mini,"IQ3 block combined mode");
  require(l.label==label&&l.op=="routed_gemv"&&l.weights==std::vector<std::string>{weight}&&l.shape==std::vector<int>({10,640,2560})&&iq3block::selected(label,weight),"IQ3 block exact site");
  const auto&t=w.directory.at(weight);
  require(unsigned(flash::grid_type(t.grid))==18&&t.shape==std::vector<int>({512,640,2560})&&t.bytes==321126400,"IQ3 block exact packed tensor");
  const auto prefix=l.label.substr(0,l.label.rfind('.'));
  require(l.inputs==std::vector<std::string>{prefix+".expert_input",prefix+".routes","active","error"}&&l.outputs==std::vector<std::string>{l.label,l.label+".status"},"IQ3 block unchanged gathered wiring");return true;
 }return false;
}
static void iq3_block_admit(const Weights&w,const Options&a,const flash::Plan&p){
 if(!a.expert_iq3xxs_block)return;
 std::set<std::string>seen;for(const auto&l:p.launches)if(iq3_block_site(w,a,l))require(seen.insert(l.label).second,"duplicate IQ3 block site");
 require(seen.size()==34,"complete IQ3 block plan");
}
'''
 main=replace(oldmain,'bool gsq_packed=false,attention_q8_p33=false,qkv_q6_p33=false;','bool gsq_packed=false,attention_q8_p33=false,qkv_q6_p33=false,expert_iq3xxs_block=false;')
 main=replace(main,'if(k=="--qkv-q6-p33") a.qkv_q6_p33=true;','if(k=="--expert-iq3xxs-block") a.expert_iq3xxs_block=true;\n    else if(k=="--qkv-q6-p33") a.qkv_q6_p33=true;')
 main=replace(main,'  if(a.qkv_q6_p33)require(','  if(a.expert_iq3xxs_block)require(a.qkv_q6_p33&&a.attention_q8_p33&&a.gsq_packed&&!a.mini,"IQ3 block requires combined real GSQ mode");\n  if(a.qkv_q6_p33)require(')
 include='#include "'+str(private)+'"';main=replace(main,include,include+'\n#include "'+str(dest/'block.hpp')+'"')
 include='#include "'+str(L/'qkv-q6-p33/engine/build/source/policy.hpp')+'"';main=replace(main,include,include+'\n#include "'+str(dest/'policy.hpp')+'"')
 main=replace(main,'combined_admit(w,a,candidate);return candidate;','combined_admit(w,a,candidate);iq3_block_admit(w,a,candidate);return candidate;')
 main=replace(main,str(generic),str(dest/'generic_engine.hpp'))
 dispatch='  if(iq3_block_site(w,a,l)){require(m.activation==iq3::Type::BF16&&m.output_type==iq3::Type::BF16&&!m.fp32&&dev(c).arena.row(m.w).bytes==321126400,"IQ3 block exact matrix storage");finish(c,iq3block::submit(dev(c),m,l.label,l.weights.at(0),gsqn::InputMode::per_slot),true);return;}\n'
 newgeneric=replace(oldgeneric,'  if(qkv_q6_site(w,a,l)){',dispatch+'  if(qkv_q6_site(w,a,l)){')
 entry=replace(oldentry,str(base/'main.cpp'),str(dest/'main.cpp'))
 # Same executable supports the control when the opt-in flag is absent.
 # Only the entry TU consumes these headers; all original math/types stay frozen.
 changed={str(base/'main.cpp'),str(base/'entry.cpp'),str(generic)}
 reused=[o for o in parent['objects'] if o['reuse']]
 need(len(reused)==39,'exact39 inherited objects')
 for o in reused:need(not changed.intersection(o['dependencies']),'changed header used by reused object')
 dest.mkdir(parents=True)
 outputs={'main.cpp':main,'entry.cpp':entry,'generic_engine.hpp':newgeneric,'policy.hpp':policy,'block.hpp':block}
 for name,text in outputs.items():(dest/name).write_text(text)
 delta=''
 for name,before,after in [('main.cpp',oldmain,main),('entry.cpp',oldentry,entry),('generic_engine.hpp',oldgeneric,newgeneric),('block.hpp',original,block)]:
  delta+=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='parent/'+name,tofile='candidate/'+name))
 (P/'overlay.patch').write_text(delta)
 sources=[P/'prepare.py',P/'parent-pins.json',P/'overlay.patch',*dest.iterdir()]
 receipt=dict(schema='gsq.iq3xxs-block.engine.source.v1',passed=True,materialized_directory=str(dest),source_sha256={str(f):sha(f) for f in sources},parent_native_build_sha256=sha(S/'evidence/native-build.json'),parent_binary_sha256=json.loads((S/'evidence/native-build.json').read_text())['binary_sha256'],kernel_sha256=sha(Q/'block.hpp'),selection_sha256=sha(Q/'selection.hpp'),sites=rows,objects=parent['objects'],reused_objects=39,recompiled_objects=1,allocation_delta_bytes=0,kernel_body_byte_identical=True,compiler_invoked=False,device_executed=False,native_qualification_passed=False)
 (P/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(sha(P/'preparation.json'))
if __name__=='__main__':main()
