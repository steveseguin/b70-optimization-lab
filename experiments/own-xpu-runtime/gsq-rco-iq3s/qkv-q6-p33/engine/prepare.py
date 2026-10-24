#!/usr/bin/env python3
"""Add 22 exact Q6 QKV sites to the frozen attention entry; no compiler/device."""
import difflib,hashlib,importlib.util,json
from pathlib import Path
P=Path(__file__).resolve().parent;Q=P.parent;L=Q.parent;R=L.parents[2];A=L/'attention-q8-p33'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,m):
 if not v:raise ValueError(m)
def replace(s,a,b):
 require(s.count(a)==1,'unique anchor '+a[:100]);return s.replace(a,b)
def parent():
 for f,h in json.loads((P/'parent-pins.json').read_text()).items():require(sha(f)==h,'parent drift '+f)
 spec=importlib.util.spec_from_file_location('frozen_attention_prepare',A/'prepare.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 control=m.control();old=json.loads((A/'preparation.json').read_text())
 for f,h in old['source_sha256'].items():require(sha(f)==h,'attention prepared source drift '+f)
 require(m.reuse(control)==old['objects'],'unchanged per-TU dependency proof')
 return control,old
def selected():
 q=json.loads((Q/'selection.json').read_text());graph=json.loads((L/'graph/new-plan.json').read_text());tensors=json.loads((L/'metadata/new-census.json').read_text())['tensors'];rows=[]
 for l in graph['launches']:
  if l['op']!='gemv' or not l['label'].endswith('.gdn.qkv'):continue
  t=tensors[l['weights'][0]]
  if t['type']!='Q6_K':continue
  require(l['shape']==[1,10240,2560] and len(l['weights'])==1 and t['shape']==[10240,2560] and t['bytes']==21504000,'Q6 exact geometry')
  rows.append({'label':l['label'],'weight':l['weights'][0]})
 require(rows==[{'label':s['label'],'weight':s['weight']} for s in q['sites']] and len(rows)==22,'exact22 frozen Q6 sites')
 return rows
def policy(rows,attention):
 values=',\n'.join('{'+json.dumps(x['label'])+','+json.dumps(x['weight'])+'}' for x in rows)
 return attention+'''
// Additive fixed Q6 subset. All other QKV formats retain their existing path.
static constexpr std::array<std::pair<const char*,const char*>,22> qkv_q6_sites{{
'''+values+'''
}};
static bool qkv_q6_weight(const Weights&w,const Options&a,const std::string&name){
 if(!a.qkv_q6_p33)return false;
 for(auto [label,weight]:qkv_q6_sites)if(name==weight){
  const auto&t=w.directory.at(name);
  require(a.attention_q8_p33&&a.gsq_packed&&!a.mini&&flash::grid_type(t.grid)==iq3::Type::Q6_K&&t.shape==std::vector<int>({10240,2560})&&t.bytes==21504000,"QKV Q6 exact tensor");return true;
 }return false;
}
static bool qkv_q6_site(const Weights&w,const Options&a,const flash::Launch&l){
 if(!a.qkv_q6_p33)return false;
 for(auto [label,weight]:qkv_q6_sites)if(l.label==label||std::find(l.weights.begin(),l.weights.end(),weight)!=l.weights.end()){
  require(l.label==label&&l.op=="gemv"&&l.weights==std::vector<std::string>{weight}&&l.shape==std::vector<int>({1,10240,2560}),"QKV Q6 exact site");
  return qkv_q6_weight(w,a,weight);
 }return false;
}
static bool combined_site(const Weights&w,const Options&a,const flash::Launch&l){return attention_q8_site(w,a,l)||qkv_q6_site(w,a,l);}
static bool combined_weight(const Weights&w,const Options&a,const std::string&n){return attention_q8_weight(w,a,n)||qkv_q6_weight(w,a,n);}
static void combined_admit(const Weights&w,const Options&a,const flash::Plan&p){
 attention_q8_admit(w,a,p);if(!a.qkv_q6_p33)return;
 std::set<std::string> seen;for(const auto&l:p.launches)if(qkv_q6_site(w,a,l))require(seen.insert(l.label).second,"duplicate QKV Q6 site");
 require(seen.size()==22,"complete QKV Q6 plan");
}
'''
def main():
 control,old=parent();rows=selected();base=Path(old['materialized_directory']);dest=P/'build/source';require(not dest.exists(),'fresh source destination')
 s0=(base/'main.cpp').read_text();s=s0
 s=replace(s,'bool gsq_packed=false,attention_q8_p33=false;','bool gsq_packed=false,attention_q8_p33=false,qkv_q6_p33=false;')
 s=replace(s,'if(k=="--attention-q8-p33") a.attention_q8_p33=true;','if(k=="--qkv-q6-p33") a.qkv_q6_p33=true;\n    else if(k=="--attention-q8-p33") a.attention_q8_p33=true;')
 s=replace(s,'if(a.attention_q8_p33)require(','if(a.qkv_q6_p33)require(a.attention_q8_p33&&a.gsq_packed&&!a.mini,"QKV requires combined real GSQ mode");\n  if(a.attention_q8_p33)require(')
 s=replace(s,str(base/'policy.hpp'),str(dest/'policy.hpp'));s=replace(s,str(base/'generic_engine.hpp'),str(dest/'generic_engine.hpp'))
 for a,b in [('attention_q8_site(w,a,l)','combined_site(w,a,l)'),('attention_q8_weight(w,a,name)','combined_weight(w,a,name)'),('attention_q8_admit(w,a,candidate)','combined_admit(w,a,candidate)')]:
  require(a in s,'combined dispatch anchor');s=s.replace(a,b)
 g0=(base/'generic_engine.hpp').read_text();g=replace(g0,'  if(attention_q8_site(w,a,l)){','  if(qkv_q6_site(w,a,l)){require(m.type==iq3::Type::Q6_K&&m.rows==10240&&m.columns==2560&&variant(l)==6&&m.activation==iq3::Type::BF16&&m.output_type==iq3::Type::BF16&&!m.fp32&&!m.routes&&!m.status&&m.count==1&&m.experts==1&&(m.span==0||m.span==m.rows)&&dev(c).arena.row(m.w).bytes==34611200,"QKV Q6 variant6 only");finish(c,p33::submit(dev(c),{m},"p33.dense.segment",false,6),true);return;}\n  if(attention_q8_site(w,a,l)){')
 dest.mkdir(parents=True)
 (dest/'main.cpp').write_text(s);(dest/'generic_engine.hpp').write_text(g);(dest/'policy.hpp').write_text(policy(rows,(base/'policy.hpp').read_text()))
 entry='#define main packet26_model_entry\n#include "'+str(dest/'main.cpp')+'"\n#undef main\nint main(int argc,char**argv){bool gsq=false,attention=false,qkv=false;for(int i=1;i<argc;++i){std::string_view x(argv[i]);gsq|=x=="--gsq-packed";attention|=x=="--attention-q8-p33";qkv|=x=="--qkv-q6-p33";}if(!gsq||!attention||!qkv)return 64;return packet26_model_entry(argc,argv);}\n'
 (dest/'entry.cpp').write_text(entry)
 patch=''.join(difflib.unified_diff(s0.splitlines(True),s.splitlines(True),fromfile=str(base/'main.cpp'),tofile=str(dest/'main.cpp')))+''.join(difflib.unified_diff(g0.splitlines(True),g.splitlines(True),fromfile=str(base/'generic_engine.hpp'),tofile=str(dest/'generic_engine.hpp')))
 (P/'overlay.patch').write_text(patch)
 files=[P/'prepare.py',P/'parent-pins.json',P/'overlay.patch',*dest.iterdir()]
 receipt=dict(passed=True,schema='gsq.combined-attention-qkv.source.v1',materialized_directory=str(dest),source_sha256={str(f):sha(f) for f in files},attention_preparation_sha256=sha(A/'preparation.json'),sites=rows,objects=old['objects'],recompiled_objects=1,reused_objects=39,allocation_delta_vs_attention_bytes=288358400,per_rank_delta_vs_attention_bytes=[183500800,104857600],combined_device_forecast_bytes=[30947490698,29824495508],host_initial_forecast_increment_bytes=288358400,variant=6,split=1,compiler_invoked=False,device_executed=False)
 (P/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(sha(P/'preparation.json'))
if __name__=='__main__':main()
