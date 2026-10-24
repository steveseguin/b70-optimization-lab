#!/usr/bin/env python3
"""Additive opt-in116-site Engine source overlay; no compiler/model/device I/O."""
from pathlib import Path
import hashlib,json,difflib
P=Path(__file__).resolve().parent;Q=P.parent;L=Q.parent;A=L/'dense-q6-p33'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,m):
 if not v:raise ValueError(m)
def replace(s,a,b):
 need(s.count(a)==1,'unique anchor '+a[:90]);return s.replace(a,b)
def main():
 for f,h in json.loads((P/'parent-pins.json').read_text()).items():need(sha(f)==h,'parent drift '+f)
 old=json.loads((A/'preparation.json').read_text());base=Path(old['materialized_directory']);dest=P/'build/source';need(not dest.exists(),'fresh source destination')
 for f,h in old['source_sha256'].items():need(sha(f)==h,'parent prepared source drift')
 sites=json.loads((Q/'selection.json').read_text())['sites'];graph=json.loads((L/'graph/new-plan.json').read_text())['launches'];census=json.loads((L/'metadata/new-census.json').read_text())['tensors']
 need(len(sites)==116 and len({s['label'] for s in sites})==116,'exact116 sites')
 for s in sites:
  found=[x for x in graph if x['label']==s['label']];need(len(found)==1,'one graph site');g=found[0];t=census[s['weight']]
  need(g['op']=='gemv' and g['shape']==[1,s['rows'],2560] and g['weights']==[s['weight']] and g['inputs']==[s['input'],'active','error'] and g['outputs']==[s['label']],'original dense shared wiring')
  need(t['type_id']==s['type_id'] and t['dimensions']==[2560,s['rows']] and t['bytes']==s['packed_bytes'],'exact packed tensor census')
 values=',\n'.join('{'+json.dumps(s['label'])+','+json.dumps(s['input'])+'}' for s in sites)
 policy='''#pragma once
#include "'''+str(Q/'selection.hpp')+'''"
static constexpr std::array<std::pair<const char*,const char*>,116> dense_block_inputs{{
'''+values+'''
}};
static bool dense_block_site(const Weights&w,const Options&a,const flash::Launch&l){
 if(!a.dense_packed_block)return false;
 for(const auto&s:denseblock::sites)if(l.label==s.label||std::find(l.weights.begin(),l.weights.end(),std::string(s.weight))!=l.weights.end()){
  require(a.gsq_packed&&a.attention_q8_p33&&a.qkv_q6_p33&&a.expert_iq3xxs_block&&a.dense_q6_p33&&!a.mini,"dense block requires current combined mode");
  require(l.label==s.label&&l.op=="gemv"&&l.weights==std::vector<std::string>{std::string(s.weight)}&&l.shape==std::vector<int>({1,int(s.rows),2560}),"dense block exact site");
  const auto&t=w.directory.at(std::string(s.weight));require(unsigned(flash::grid_type(t.grid))==s.type&&t.shape==std::vector<int>({int(s.rows),2560})&&t.bytes==s.bytes,"dense block exact raw tensor");
  auto input=std::find_if(dense_block_inputs.begin(),dense_block_inputs.end(),[&](auto x){return l.label==x.first;});require(input!=dense_block_inputs.end(),"dense block fixed input");
  require(l.inputs==std::vector<std::string>{input->second,"active","error"}&&l.outputs==std::vector<std::string>{l.label},"dense block original shared input/output wiring");return true;
 }return false;
}
static void dense_block_admit(const Weights&w,const Options&a,const flash::Plan&p){
 if(!a.dense_packed_block)return;
 std::set<std::string>seen;for(const auto&l:p.launches)if(dense_block_site(w,a,l))require(seen.insert(l.label).second,"duplicate dense block site");require(seen.size()==116,"complete dense block census");
}
'''
 oldmain=(base/'main.cpp').read_text();oldgeneric=(base/'generic_engine.hpp').read_text();oldentry=(base/'entry.cpp').read_text()
 private=L/'integration/build/private/additive/packed.hpp';original=(Q/'block.hpp').read_text();block=replace(original,'#include "../native-formats/packed.hpp"','#include "'+str(private)+'"');block=replace(block,'#include "selection.hpp"','#include "'+str(Q/'selection.hpp')+'"')
 need(block[block.index('// Included after frozen'):]==original[original.index('// Included after frozen'):],'all arithmetic/operation/facade body byte identical')
 main=replace(oldmain,'dense_q6_p33=false;','dense_q6_p33=false,dense_packed_block=false;')
 main=replace(main,'if(k=="--dense-q6-p33") a.dense_q6_p33=true;','if(k=="--dense-packed-block") a.dense_packed_block=true;\n    else if(k=="--dense-q6-p33") a.dense_q6_p33=true;')
 main=replace(main,'  if(a.dense_q6_p33)require(','  if(a.dense_packed_block)require(a.dense_q6_p33&&a.expert_iq3xxs_block&&a.qkv_q6_p33&&a.attention_q8_p33&&a.gsq_packed&&!a.mini,"dense block requires current combined real GSQ mode");\n  if(a.dense_q6_p33)require(')
 inc='#include "'+str(private)+'"';main=replace(main,inc,inc+'\n#include "'+str(dest/'block.hpp')+'"')
 inc='#include "'+str(base/'policy.hpp')+'"';main=replace(main,inc,inc+'\n#include "'+str(dest/'policy.hpp')+'"')
 main=replace(main,'dense_q6_admit(w,a,candidate);return candidate;','dense_q6_admit(w,a,candidate);dense_block_admit(w,a,candidate);return candidate;');main=replace(main,str(base/'generic_engine.hpp'),str(dest/'generic_engine.hpp'))
 dispatch='  if(dense_block_site(w,a,l)){const auto*s=denseblock::selected(l.label,l.weights.at(0));require(s&&variant(l)==0&&dev(c).arena.row(m.w).bytes==s->bytes,"dense block raw storage/variant");finish(c,denseblock::submit(dev(c),m,l.label,l.weights.at(0),gsqn::InputMode::shared),true);return;}\n'
 generic=replace(oldgeneric,'  if(iq3_block_site(w,a,l)){',dispatch+'  if(iq3_block_site(w,a,l)){');entry=replace(oldentry,str(base/'main.cpp'),str(dest/'main.cpp'))
 changed={str(base/n) for n in ('main.cpp','generic_engine.hpp','entry.cpp')};reused=[o for o in old['objects'] if o['reuse']];need(len(reused)==39,'exact39 unchanged objects')
 for o in reused:need(not changed.intersection(o['dependencies']),'entry-only change boundary')
 dest.mkdir(parents=True);outputs={'main.cpp':main,'generic_engine.hpp':generic,'entry.cpp':entry,'policy.hpp':policy,'block.hpp':block}
 for n,text in outputs.items():(dest/n).write_text(text)
 (P/'overlay.patch').write_text(''.join(''.join(difflib.unified_diff(before.splitlines(True),outputs[n].splitlines(True),fromfile='qualified-parent/'+n,tofile='candidate/'+n)) for n,before in [('main.cpp',oldmain),('generic_engine.hpp',oldgeneric),('entry.cpp',oldentry),('block.hpp',original)]))
 (P/'selection.json').write_bytes((Q/'selection.json').read_bytes());ledger=dict(parent_device_bytes=[30994676618,29966053268],delta_bytes=[0,0],device_forecast_bytes=[30994676618,29966053268],initial_host_forecast_increment_bytes=0,new_workspace_bytes=0,actual_allocation_qualified=False);(P/'memory-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
 files=[P/'prepare.py',P/'PROPOSAL.md',P/'parent-pins.json',P/'overlay.patch',P/'selection.json',P/'memory-ledger.json',*dest.iterdir()]
 receipt=dict(schema='gsq.dense-packed-block.engine.source.v1',passed=True,materialized_directory=str(dest),source_sha256={str(f):sha(f) for f in files},parent_native_build_sha256=sha(A/'evidence/native-build.json'),parent_binary_sha256=json.loads((A/'evidence/native-build.json').read_text())['binary_sha256'],kernel_sha256=sha(Q/'block.hpp'),kernel_body_byte_identical=True,objects=old['objects'],reused_objects=39,recompiled_objects=1,sites=sites,ledger=ledger,compiler_invoked=False,device_executed=False,native_qualification_complete=False)
 (P/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(sha(P/'preparation.json'))
if __name__=='__main__':main()
