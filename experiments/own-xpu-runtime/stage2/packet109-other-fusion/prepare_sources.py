"""Packet109's explicit, reviewable delta over a frozen checked packet103 copy."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent; ROOT=P.parents[3]
BASE=P.parent/'packet103-record-bundle'
C=P/'sources'/BASE.relative_to(ROOT)
def once(t,a,b):
    assert t.count(a)==1,(a[:100],t.count(a))
    return t.replace(a,b,1)
def main():
    # Run once, never regenerate a source that has been qualified.
    assert not (P/'source-delta-applied.json').exists()
    f=C/'p49d_submit.cpp';t=f.read_text()
    t=once(t,'Submit resolve(std::string_view cls,std::string_view choice){',
        'Submit resolve(std::string_view cls,std::string_view choice){\n if(cls=="other_fusion"&&(choice=="production"||choice=="fused"))return production;')
    t=once(t,'values.size()!=10','values.size()!=11')
    t=once(t,'auto target_values=values;','auto target_values=values;target_values.erase("other_fusion");')
    f.write_text(t)
    f=C/'main.cpp';t=f.read_text()
    t=once(t,'class Engine final', '#include '+json.dumps(str(P/'p109_fusion.hpp'))+'\nclass Engine final')
    t=once(t,'  void execute_site(const flash::Launch& l) {int c=l.card;',
        '#include '+json.dumps(str(P/'engine_fusion.hpp'))+'\n  void execute_site(const flash::Launch& l) {int c=l.card;\n    if(other_fused_site(l)) { /* Preserve common BF16 writer invalidation. */ } else')
    f.write_text(t)
    # Copy route's exact body, adding only the independent shared activation
    # after all route phases and their guards have finished within this WG.
    t=(C/'p78_route.hpp').read_text().replace('namespace p78route {','namespace p109route {')
    t=t.replace('p78route::host(route42::bind(spec,p));',
        'p109route::host(route42::bind(spec,p.first(p.size()-3)));\n    auto a=route42::bind(spec,p.first(p.size()-3));\n    auto pos=static_cast<const uint32_t*>(p[spec.ni+spec.no+spec.nw+2]);\n    for(unsigned i=0;i<640;++i)activation(a,p.data()+p.size()-3,i,pos,spec.g.context);')
    t=once(t,'struct Kernel final:p49c::Base {',r'''
inline void activation(route42::Args a,void* const* p,unsigned i,const uint32_t* pos,unsigned capacity){
 if(!*a.active||a.failed())return;
 const int32_t position=std::bit_cast<int32_t>(*pos);
 if(position<0||unsigned(position)>=capacity){if(!i)a.fail();return;}
 auto gate=static_cast<const uint16_t*>(p[0]);auto up=static_cast<const uint16_t*>(p[1]);
 auto out=static_cast<uint16_t*>(p[2]);
 out[i]=iq3::bf16_bits(ng::silu(iq3::bits_float(uint32_t(gate[i])<<16))*iq3::bits_float(uint32_t(up[i])<<16));
}
struct Kernel final:p49c::Base {''')
    t=once(t,'auto a=route42::bind(spec,p);','auto a=route42::bind(spec,p.first(p.size()-3));\n    auto pos=static_cast<const uint32_t*>(p[spec.ni+spec.no+spec.nw+2]);unsigned capacity=spec.g.context;\n    std::array<void*,3> activation_args{p[p.size()-3],p[p.size()-2],p[p.size()-1]};')
    t=once(t,'if(!tid)route42::phase<4,512,10>(a,0);',
        'if(!tid)route42::phase<4,512,10>(a,0);\n        it.barrier(sycl::access::fence_space::global_and_local);\n        for(unsigned i=tid;i<640;i+=512)activation(a,activation_args.data(),i,pos,capacity);')
    # Public submission and exact extent validation live in p109_fusion.hpp.
    t=t[:t.index('inline integrated::Launch submit(')]+'}\n'
    (P/'p109_route.hpp').write_text(t)
    f=P/'native/engine_bracket.hpp';t=f.read_text()
    t=t.replace('if(key!="qsa_attention")','if(true)')
    t=t.replace('if(key!="route"&&key!="recurrence"&&key!="hc_gate")','if(key!="other_fusion")')
    t=once(t,'domain(selection->choices,"route",{"route-exp32-rank4","route-fast"});',
        'domain(selection->choices,"other_fusion",{"production","fused"});\n      domain(selection->choices,"route",{"route-fast"});')
    f.write_text(t)
    (P/'source-delta-applied.json').write_text(json.dumps({'parent':'packet103','device_executed':False})+'\n')
if __name__=='__main__':main()
