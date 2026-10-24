#!/usr/bin/env python3
"""Source-only exact19 dense Q6 overlay; no compiler, model or Device I/O."""
import difflib,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parent;A=L/'expert-iq3xxs-block/engine'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,m):
 if not v:raise ValueError(m)
def replace(s,a,b):
 need(s.count(a)==1,'unique anchor '+a[:80]);return s.replace(a,b)
def selected():
 g=json.loads((L/'graph/new-plan.json').read_text());c=json.loads((L/'metadata/new-census.json').read_text())['tensors'];out=[]
 expected={'.gdn.z':[1,4,10,17,20,21,24,25,26,28,29,33,40,45],'.qsa.qgate':[31,35,39,43,47]}
 for l in g['launches']:
  if not l['label'].endswith(tuple(expected)):continue
  t=c[l['weights'][0]]
  if t['type']!='Q6_K':continue
  n=6144 if l['label'].endswith('.gdn.z') else 12288
  need(l['op']=='gemv' and l['shape']==[1,n,2560] and len(l['weights'])==1 and t['shape']==[n,2560] and t['bytes']==n*2100,'exact dense Q6 geometry')
  out.append(dict(label=l['label'],weight=l['weights'][0],rows=n,columns=2560,card=l['card'],packed_bytes=n*2100,expanded_bytes=n*3380,delta_bytes=n*1280))
 need(len(out)==19 and {r['label'] for r in out}=={'blk.'+str(i)+suffix for suffix,ids in expected.items() for i in ids},'fixed19 sites');return out

def policy(rows):
 values=',\n'.join('{'+json.dumps(r['label'])+','+json.dumps(r['weight'])+','+str(r['rows'])+'}' for r in rows)
 return '''#pragma once
struct DenseQ6Site {const char*label;const char*weight;unsigned rows;};
static constexpr std::array<DenseQ6Site,19> dense_q6_sites{{
'''+values+'''
}};
static bool dense_q6_weight(const Weights&w,const Options&a,const std::string&name){
 if(!a.dense_q6_p33)return false;
 for(auto s:dense_q6_sites)if(name==s.weight){
  require(a.gsq_packed&&a.attention_q8_p33&&a.qkv_q6_p33&&a.expert_iq3xxs_block&&!a.mini,"dense Q6 combined mode");
  const auto&t=w.directory.at(name);
  require(flash::grid_type(t.grid)==iq3::Type::Q6_K&&t.shape==std::vector<int>({int(s.rows),2560})&&t.bytes==size_t(s.rows)*2100,"dense Q6 exact tensor");return true;
 }return false;
}
static bool dense_q6_site(const Weights&w,const Options&a,const flash::Launch&l){
 if(!a.dense_q6_p33)return false;
 for(auto s:dense_q6_sites)if(l.label==s.label||std::find(l.weights.begin(),l.weights.end(),s.weight)!=l.weights.end()){
  require(l.label==s.label&&l.op=="gemv"&&l.weights==std::vector<std::string>{s.weight}&&l.shape==std::vector<int>({1,int(s.rows),2560}),"dense Q6 exact site");return dense_q6_weight(w,a,s.weight);
 }return false;
}
template<class Matrix>static void dense_q6_matrix(const Matrix&m,const flash::Launch&l,unsigned variant,size_t bytes){
 require(m.type==iq3::Type::Q6_K&&(m.rows==6144||m.rows==12288)&&l.shape.size()==3&&m.rows==unsigned(l.shape[1])&&m.columns==2560&&variant==6&&m.activation==iq3::Type::BF16&&m.output_type==iq3::Type::BF16&&!m.fp32&&!m.routes&&!m.status&&m.count==1&&m.experts==1&&(m.span==0||m.span==m.rows)&&bytes==size_t(m.rows)*3380,"dense Q6 variant6 exact matrix");
}
static void dense_q6_admit(const Weights&w,const Options&a,const flash::Plan&p){
 if(!a.dense_q6_p33)return;
 std::set<std::string>seen;for(const auto&l:p.launches)if(dense_q6_site(w,a,l))require(seen.insert(l.label).second,"duplicate dense Q6 site");
 require(seen.size()==19,"complete dense Q6 plan");
}
'''
def main():
 pins=json.loads((P/'parent-pins.json').read_text())
 for f,h in pins.items():need(sha(f)==h,'parent source drift '+f)
 old=json.loads((A/'preparation.json').read_text());base=Path(old['materialized_directory']);dest=P/'build/source';need(not dest.exists(),'fresh destination')
 for f,h in old['source_sha256'].items():need(sha(f)==h,'parent prepared drift '+f)
 rows=selected();oldmain=(base/'main.cpp').read_text();oldgeneric=(base/'generic_engine.hpp').read_text();oldentry=(base/'entry.cpp').read_text()
 main=replace(oldmain,'expert_iq3xxs_block=false;','expert_iq3xxs_block=false,dense_q6_p33=false;')
 main=replace(main,'if(k=="--expert-iq3xxs-block") a.expert_iq3xxs_block=true;','if(k=="--dense-q6-p33") a.dense_q6_p33=true;\n    else if(k=="--expert-iq3xxs-block") a.expert_iq3xxs_block=true;')
 main=replace(main,'  if(a.expert_iq3xxs_block)require(','  if(a.dense_q6_p33)require(a.expert_iq3xxs_block&&a.qkv_q6_p33&&a.attention_q8_p33&&a.gsq_packed&&!a.mini,"dense Q6 requires combined real GSQ mode");\n  if(a.expert_iq3xxs_block)require(')
 inc='#include "'+str(base/'policy.hpp')+'"';main=replace(main,inc,inc+'\n#include "'+str(dest/'policy.hpp')+'"')
 main=replace(main,'iq3_block_admit(w,a,candidate);return candidate;','iq3_block_admit(w,a,candidate);dense_q6_admit(w,a,candidate);return candidate;')
 need(main.count('combined_site(w,a,l)')==2 and main.count('combined_weight(w,a,name)')==2,'all storage/dispatch seams')
 main=main.replace('combined_site(w,a,l)','(combined_site(w,a,l)||dense_q6_site(w,a,l))').replace('combined_weight(w,a,name)','(combined_weight(w,a,name)||dense_q6_weight(w,a,name))')
 main=replace(main,str(base/'generic_engine.hpp'),str(dest/'generic_engine.hpp'))
 dispatch='  if(dense_q6_site(w,a,l)){dense_q6_matrix(m,l,variant(l),dev(c).arena.row(m.w).bytes);finish(c,p33::submit(dev(c),{m},"p33.dense.segment",false,6),true);return;}\n'
 generic=replace(oldgeneric,'  if(qkv_q6_site(w,a,l)){',dispatch+'  if(qkv_q6_site(w,a,l)){');entry=replace(oldentry,str(base/'main.cpp'),str(dest/'main.cpp'))
 changed={str(base/f) for f in ('main.cpp','generic_engine.hpp','entry.cpp')};reused=[o for o in old['objects'] if o['reuse']];need(len(reused)==39,'39 reused objects')
 for o in reused:need(not changed.intersection(o['dependencies']),'entry-only dependency boundary')
 dest.mkdir(parents=True);outputs={'main.cpp':main,'generic_engine.hpp':generic,'entry.cpp':entry,'policy.hpp':policy(rows)}
 for name,s in outputs.items():(dest/name).write_text(s)
 patch=''.join(''.join(difflib.unified_diff(before.splitlines(True),outputs[name].splitlines(True),fromfile='parent/'+name,tofile='candidate/'+name)) for name,before in [('main.cpp',oldmain),('generic_engine.hpp',oldgeneric),('entry.cpp',oldentry)])
 (P/'overlay.patch').write_text(patch);(P/'selection.json').write_text(json.dumps(dict(sites=rows,variant=6,split=1),indent=2)+'\n')
 delta=[sum(r['delta_bytes'] for r in rows if r['card']==i) for i in (0,1)];need(delta==[47185920,141557760],'exact rank delta')
 ledger=dict(parent_device_bytes=[30947490698,29824495508],delta_bytes=delta,device_forecast_bytes=[30947490698+delta[0],29824495508+delta[1]],initial_host_forecast_increment_bytes=sum(delta),new_workspace_bytes=0,actual_allocation_qualified=False)
 (P/'memory-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
 files=[P/'prepare.py',P/'PROPOSAL.md',P/'parent-pins.json',P/'overlay.patch',P/'selection.json',P/'memory-ledger.json',*dest.iterdir()]
 out=dict(schema='gsq.dense-q6.engine.source.v1',passed=True,materialized_directory=str(dest),source_sha256={str(f):sha(f) for f in files},parent_native_build_sha256=sha(A/'evidence/native-build.json'),parent_binary_sha256=json.loads((A/'evidence/native-build.json').read_text())['binary_sha256'],objects=old['objects'],reused_objects=39,recompiled_objects=1,sites=rows,ledger=ledger,compiler_invoked=False,device_executed=False)
 (P/'preparation.json').write_text(json.dumps(out,indent=2)+'\n');print(sha(P/'preparation.json'))
if __name__=='__main__':main()
