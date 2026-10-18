#!/usr/bin/env python3
from pathlib import Path
import json
P=Path(__file__).resolve().parent
assert not (P/'build-device-receipt.json').exists(),'historical creation helper; never modify a built packet'
def edit(name,a,b):
 p=P/name;s=p.read_text();assert a in s,(name,a);p.write_text(s.replace(a,b))
edit('p60_submit.hpp','int,unsigned);','int,unsigned,bool=false);')
edit('p60_submit.cpp','#include "p60_kernels.hpp"','#include "p60_kernels.hpp"\n#include "p67_hc.hpp"')
edit('p60_submit.cpp','template<int Stage>','template<int Stage,bool Candidate=false>')
edit('p60_submit.cpp','if constexpr(Stage==2)host_gate_mix(b);','if constexpr(Stage==2){if constexpr(Candidate)p67hc::host(b);else host_gate_mix(b);}')
edit('p60_submit.cpp','if constexpr(Stage==2)return gate_mix_kernel(q,b,deps);','if constexpr(Stage==2){if constexpr(Candidate)return p67hc::device(q,b,deps);else return gate_mix_kernel(q,b,deps);}')
edit('p60_submit.cpp','Kernel<Stage> op;','Kernel<Stage,Candidate> op;')
edit('p60_submit.cpp','int stage,unsigned capacity) {','int stage,unsigned capacity,bool candidate) {')
edit('p60_submit.cpp','case 2:return issue<2>(d,ids,capacity);','case 2:return candidate?issue<2,true>(d,ids,capacity):issue<2>(d,ids,capacity);')
edit('p49d_submit.hpp','{"hc","production"}}','{"hc","production"},{"hc_a_gate","production"},{"hc_f_gate","production"},{"recurrence_head","production"}}')
edit('p49d_submit.cpp','#include "p49d_small.hpp"','#include "p49d_small.hpp"\n#include "p67_recurrence.hpp"')
new='''Launch head_recurrence(Device&d,const Spec&s,IDs a,Allocation,Allocation,Allocation,Deps deps){
 auto b=p49drec::recurrence_bindings(s,a);recurrence_validate(d,s,a,b);
 if(b.shape.tokens!=1)throw std::invalid_argument("packet67 serial token geometry");
 auto scratch=a[s.ni+s.no+s.nw];const auto&r=d.arena.row(scratch);
 if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<p67rec::scratch_bytes||uintptr_t(r.pointer)%16)throw std::invalid_argument("packet67 head scratch extent/alignment");
 for(auto id:b.ids)if(scratch==id)throw std::invalid_argument("packet67 head scratch alias");
 std::array<Allocation,20> ids;std::copy(b.ids.begin(),b.ids.end(),ids.begin());ids[19]=scratch;
#ifdef OWN_RT_HOST_ONLY
 p67rec::HostKernel k;k.shape=b.shape;auto e=d.compute(k,ids,deps);return {e,e,1};
#else
 p67rec::Kernel<true> head;head.shape=b.shape;auto first=d.compute(head,ids,deps);
 p67rec::Kernel<false> update;update.shape=b.shape;std::array after{first};auto last=d.compute(update,ids,after);return {first,last,2};
#endif
}
'''
edit('p49d_submit.cpp','Submit resolve(std::string_view cls,std::string_view choice){',new+'''Submit resolve(std::string_view cls,std::string_view choice){
 if(cls=="hc_a_gate"||cls=="hc_f_gate"){if(choice=="production"||choice=="stream4")return production;}
 if(cls=="recurrence_head"){if(choice=="production")return recurrence<4>;if(choice=="head-once")return head_recurrence;}
''')
edit('p49d_submit.cpp','if(s.op==integrated::Op::gdn)return resolve("recurrence",choices.at("recurrence"));','if(s.op==integrated::Op::gdn)return resolve("recurrence_head",choices.at("recurrence_head"));')
edit('p49d_submit.cpp','values.size()!=4','values.size()!=7')
edit('p49d_submit.cpp','target_values.erase("miss");','target_values.erase("miss");target_values.erase("hc_a_gate");target_values.erase("hc_f_gate");target_values.erase("recurrence_head");')
edit('main.cpp','p60::submit(dev(c),ids,stage,p.g.context)','p60::submit(dev(c),ids,stage,p.g.context,sealed_selection.choices.at(tag.ends_with(".a")?"hc_a_gate":"hc_f_gate")=="stream4")')
s=json.loads((P/'selection.json').read_text());s['decision']=None;s['choices'].update(miss='control',hc_a_gate='production',hc_f_gate='production',recurrence_head='production')
s['draft']={k:'production' for k in s['draft']}
(P/'selection.json').write_text(json.dumps(s,indent=2)+'\n')
# Keep all unchanged objects hardlinked; compile only three changed TUs.
edit('build_engine.py','("p49d_expert_submit",mapping[P/"p49d_expert_submit.cpp"])','("p60_submit",mapping[P/"p60_submit.cpp"])')
edit('build_engine.py','elif arg.endswith("-p49d_expert_submit.cpp.o"):link[i]=str(dest/"p49d_expert_submit.o");replacements+=1','elif arg==str(BASE/"build"/mode/"p60_submit.o") or arg.endswith("-p60_submit.o"):link[i]=str(dest/"p60_submit.o");replacements+=1')
edit('build_engine.py','"p49d_expert_submit.o"','"p60_submit.o"')
edit('build_engine.py','packet65','packet67')
edit('build_engine.py','500_000_000','950_000_000')
print('integrated three selectable sites; production defaults preserved')
