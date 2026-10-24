#!/usr/bin/env python3
"""Materialize the one-candidate entry overlay; never compile or invoke it."""
import argparse,difflib,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parent;R=P.parents[3];I=L/'integration'
PRIVATE=I/'build/private/source/diet-native';MAIN=PRIVATE/'native-src/main.cpp'
STAGE=PRIVATE/'native-base/experiments/own-xpu-runtime/stage2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,m):
    if not v:raise ValueError(m)
def replace(s,a,b):
    require(s.count(a)==1,'unique overlay anchor: '+a[:100]);return s.replace(a,b)
def control():
    pins=json.loads((P/'control-pins.json').read_text())
    for f,h in pins.items():require(sha(f)==h,'frozen control changed: '+f)
    b=json.loads((I/'evidence/full-native-build.json').read_text());require(b['passed'] and b['mode']=='native','native control proof')
    for f,h in b['source_sha256'].items():require(sha(R/f)==h,'control source drift: '+f)
    for f,h in b['object_sha256'].items():require(sha(f)==h,'control object drift: '+f)
    require(sha(b['binary'])==b['binary_sha256'],'control binary drift')
    return b
def rows():
    graph=json.loads((L/'graph/new-plan.json').read_text());census=json.loads((L/'metadata/new-census.json').read_text())['tensors'];out=[]
    for l in graph['launches']:
        if l['label'] not in {f'blk.{i}.attention' for i in range(48)}:continue
        require(l['op']=='gemv' and l['shape']==[1,2560,6144] and len(l['weights'])==1,'exact attention launch')
        name=l['weights'][0];t=census[name]
        require(t['type']=='Q8_0' and t['shape']==[2560,6144] and t['bytes']==16711680,'exact Q8 attention tensor')
        out.append(dict(label=l['label'],weight=name,type='Q8_0',shape=t['shape'],source_bytes=t['bytes'],stored_bytes=18677760,delta_bytes=1966080))
    require(len(out)==48 and len({r['weight'] for r in out})==48 and {r['label'] for r in out}=={f'blk.{i}.attention' for i in range(48)},'all48 unique attention sites')
    return out
def policy(rs):
    values=',\n'.join('{'+json.dumps(r['label'])+','+json.dumps(r['weight'])+'}' for r in rs)
    return '''#pragma once
// Names are compiled from hash-admitted graph/census. No data-dependent selection.
static constexpr std::array<std::pair<const char*,const char*>,48> attention_q8_sites{{
'''+values+'''
}};
static bool attention_q8_weight(const Weights&w,const Options&a,const std::string&name){
 if(!a.attention_q8_p33)return false;
 for(auto [label,weight]:attention_q8_sites)if(name==weight){
  const auto&t=w.directory.at(name);
  require(a.gsq_packed&&!a.mini&&flash::grid_type(t.grid)==iq3::Type::Q8_0&&t.shape==std::vector<int>({2560,6144})&&t.bytes==16711680,"attention Q8 exact tensor");return true;
 }return false;
}
static bool attention_q8_site(const Weights&w,const Options&a,const flash::Launch&l){
 if(!a.attention_q8_p33)return false;
 for(auto [label,weight]:attention_q8_sites)if(l.label==label||std::find(l.weights.begin(),l.weights.end(),weight)!=l.weights.end()){
  require(l.label==label&&l.op=="gemv"&&l.weights==std::vector<std::string>{weight}&&l.shape==std::vector<int>({1,2560,6144}),"attention Q8 exact site");
  return attention_q8_weight(w,a,weight);
 }return false;
}
static void attention_q8_admit(const Weights&w,const Options&a,const flash::Plan&p){
 if(!a.attention_q8_p33)return;
 std::set<std::string> seen;for(const auto&l:p.launches)if(attention_q8_site(w,a,l))require(seen.insert(l.label).second,"duplicate attention site");
 require(seen.size()==48,"complete attention Q8 plan");
}
'''
def materialize(dest,b):
    rs=rows();original=MAIN.read_text();s=original
    s=replace(s,'bool gsq_packed=false;','bool gsq_packed=false,attention_q8_p33=false;')
    s=replace(s,'if(k=="--gsq-packed") a.gsq_packed=true;','if(k=="--attention-q8-p33") a.attention_q8_p33=true;\n    else if(k=="--gsq-packed") a.gsq_packed=true;')
    s=replace(s,'if(a.gsq_packed){\n    require(a.dispatch', 'if(a.attention_q8_p33)require(a.gsq_packed&&!a.mini,"attention candidate requires real GSQ mode");\n  if(a.gsq_packed){\n    require(a.dispatch')
    s=replace(s,'static flash::Plan gsq_build_plan(Weights &w, const Options &a) {','#include "'+str(dest/'policy.hpp')+'"\nstatic flash::Plan gsq_build_plan(Weights &w, const Options &a) {')
    s=replace(s,'if(a.gsq_packed)return gsq_build_plan(w,a);','if(a.gsq_packed){auto candidate=gsq_build_plan(w,a);attention_q8_admit(w,a,candidate);return candidate;}')
    s=replace(s,'if(a.gsq_packed)return !a.mini&&l.weights.at(projection)=="output.weight"?6:0;','if(a.gsq_packed)return ((!a.mini&&l.weights.at(projection)=="output.weight")||attention_q8_site(w,a,l))?6:0;')
    s=replace(s,'l.weights[0]=="output.weight"&&!a.mini?std::string("p33.dense.segment")','((l.weights[0]=="output.weight"&&!a.mini)||attention_q8_site(w,a,l))?std::string("p33.dense.segment")')
    s=replace(s,'if(a.gsq_packed)return name=="output.weight"&&!a.mini?6:0;','if(a.gsq_packed)return ((name=="output.weight"&&!a.mini)||attention_q8_weight(w,a,name))?6:0;')
    s=replace(s,'if(a.gsq_packed&&(name!="output.weight"||a.mini)){gsq_load(c,name);return;}','if(a.gsq_packed&&(name!="output.weight"||a.mini)&&!attention_q8_weight(w,a,name)){gsq_load(c,name);return;}')
    old_include=str(I/'build/private/additive/generic_engine.hpp');s=replace(s,old_include,str(dest/'generic_engine.hpp'))
    generic=(I/'generic_engine.hpp').read_text();g=replace(generic,'  if(l.weights[0]=="output.weight"&&!a.mini) {','  if(attention_q8_site(w,a,l)){require(m.type==iq3::Type::Q8_0&&m.rows==2560&&m.columns==6144&&variant(l)==6&&m.activation==iq3::Type::BF16&&m.output_type==iq3::Type::BF16&&!m.fp32&&!m.routes&&!m.status&&m.count==1&&m.experts==1&&(m.span==0||m.span==m.rows)&&dev(c).arena.row(m.w).bytes==18677760,"attention Q8 variant6 only");finish(c,p33::submit(dev(c),{m},"p33.dense.segment",false,6),true);return;}\n  if(l.weights[0]=="output.weight"&&!a.mini) {')
    dest.mkdir(parents=True,exist_ok=False)
    (dest/'policy.hpp').write_text(policy(rs));(dest/'main.cpp').write_text(s);(dest/'generic_engine.hpp').write_text(g)
    entry='#define main packet26_model_entry\n#include "'+str(dest/'main.cpp')+'"\n#undef main\n'
    entry+='int main(int argc,char**argv){bool mode=false,candidate=false;for(int i=1;i<argc;++i){if(std::string_view(argv[i])=="--gsq-packed")mode=true;if(std::string_view(argv[i])=="--attention-q8-p33")candidate=true;}if(!mode||!candidate)return 64;return packet26_model_entry(argc,argv);}\n'
    (dest/'entry.cpp').write_text(entry)
    patch=''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile=str(MAIN),tofile=str(dest/'main.cpp')))+''.join(difflib.unified_diff(generic.splitlines(True),g.splitlines(True),fromfile=str(I/'generic_engine.hpp'),tofile=str(dest/'generic_engine.hpp')))
    (P/'overlay.patch').write_text(patch)
    # The scalar arithmetic authority is extracted byte-for-byte, not rewritten.
    p33=STAGE/'packet194-expert-diet-engine/p33_candidates.hpp';text=p33.read_text();a=text.index('template<iq3::Type T,unsigned K>\ninline float dense_lane(');z=text.index('// Integer rank scheduling',a);body=text[a:z]
    (dest/'fixture_math.hpp').write_text('#pragma once\n#include "'+str(STAGE/'packet6-kopt/reference.hpp')+'"\n#include "'+str(STAGE/'packet194-expert-diet-engine/p28/dense.hpp')+'"\nnamespace p33 {\n'+body+'\n}\n')
    return rs,body
def reuse(b):
    affected={MAIN.resolve(),(I/'build/private/additive/generic_engine.hpp').resolve(),(I/'native_main.cpp').resolve(),(PRIVATE/'native-src/entry-main.cpp').resolve()};result=[]
    for i,cmd in enumerate(b['commands'][:-1]):
        dep=Path(cmd[cmd.index('-MF')+1]);obj=Path(cmd[cmd.index('-o')+1]);deps={str(Path(f).resolve()):sha(f) for f in dep.read_text().replace('\\\n',' ').split(':',1)[1].split()}
        for f,h in deps.items():require(b['source_sha256'].get(str(Path(f).relative_to(R)))==h,'unbound original dependency')
        hit=sorted(set(map(Path,deps))&affected);require(bool(hit)==(i==0),'unexpected affected translation unit')
        result.append(dict(index=i,object=str(obj),object_sha256=sha(obj),depfile=str(dep),depfile_sha256=sha(dep),dependencies=deps,reuse=i!=0,affected=[str(x) for x in hit]))
    require(len(result)==40,'fixed40 object closure');return result
def main():
    argparse.ArgumentParser(description=__doc__).parse_args();b=control();d=P/'build/source-v2';rs,body=materialize(d,b);objects=reuse(b)
    files=[P/'prepare.py',P/'control-pins.json',P/'overlay.patch',*d.iterdir()]
    result=dict(materialized_directory=str(d),passed=True,schema='ownrt.gsq.attention-q8-source-plan.v1',control_binary=b['binary'],control_binary_sha256=b['binary_sha256'],control_build_sha256=sha(I/'evidence/full-native-build.json'),source_sha256={str(f):sha(f) for f in files},sites=rs,allocation_delta_bytes=94371840,per_rank_delta_bytes=47185920,variant=6,split=1,compiler_invoked=False,device_executed=False,objects=objects,recompiled_objects=1,reused_objects=39,p33_scalar_body_sha256=hashlib.sha256(body.encode()).hexdigest(),scope='exact48 attention Q8 projections only; unchanged p33 arithmetic/kernel and all other dispatch')
    (P/'preparation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':True,'preparation_sha256':sha(P/'preparation.json'),'reused_objects':39,'recompiled_objects':1}))
if __name__=='__main__':main()
