#pragma once
// Packet192 DIAGNOSTIC-ONLY no-load variants of the two record expert kernels.
// NOT exact by construction: every row address is aliased into one 16-row slab
// ((source) & 15) so that every weight load is an L1/L2 hit while the instruction
// stream of the K loop is the production kernel's (p90exp::wide_chains /
// p100::tile_chains unchanged). The only added instruction is one AND per
// work-item outside the K loop. Outputs are discarded; never an exactness claim.
// Launch form mirrors the checked (compiled) record headers: prepared_submit +
// packet26::checked around the same lambda shape.
#include "p90_expert.hpp"
#include "p100_down.hpp"
namespace p192noload {
using iq3::Type;
inline constexpr unsigned alias_rows=16;
struct GateUp final:p49b::Base {
 using Production=p90exp::Kernel<Type::IQ2_S,2560,64,false,true>;
 static constexpr unsigned K=2560,WG=64,V=Production::V,P=Production::P,SG=Production::SG,RowsPerGroup=Production::RowsPerGroup;
 static_assert(V==8&&P==4&&SG==2&&RowsPerGroup==8);
 unsigned rows=640,count=10,experts=512;
 p39::Bound bind(std::span<void*const>p)const{Production base;base.rows=rows;base.count=count;base.experts=experts;return base.bind(p);}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  for(unsigned group=0;group<groups;++group)for(unsigned sub=0;sub<SG;++sub)for(unsigned rr=0;rr<V;++rr){
   unsigned logical=Production::logical_row(group,sub,rr*P);if(logical>=total)continue;
   unsigned row=logical%rows,slot=logical/rows,stream=sub%2;
   auto route=b.routes[slot];bool ok=iq3::valid_route(route,experts,rows,rows),valid=ok&&row<route.row_count;
   float values[P]{};if(valid){size_t source=(size_t(route.expert_id)*rows+route.row_begin+row)&(alias_rows-1);
    for(unsigned lane=0;lane<P;++lane)values[lane]=p49dvirtual::local_tree<V>(Production::chains((stream?b.peer:b.w)+source*b.rb,b.x,lane));
   }
   for(unsigned width=1;width<P;width*=2)for(unsigned lane=0;lane<P;lane+=2*width)values[lane]=values[lane]+values[lane+width];
   (stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?values[0]:iq3::bits_float(0x7fc00000));
   if(!row){(stream?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active&&!*b.error)*b.error=1;}
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;(void)deps;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(groups)*WG,WG)](sycl::handler& h){
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,physical=lane%P,stream=sub%2;
    unsigned logical=Production::logical_row(it.get_group_linear_id(),sub,lane),row=logical%b.rows,slot=logical/b.rows;bool in_range=logical<total;
    iq3::Route route{};if(in_range)route=b.routes[slot];bool ok=in_range&&iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;
    float value=0;if(valid){size_t source=(size_t(route.expert_id)*b.rows+route.row_begin+row)&(alias_rows-1);
     value=p49dvirtual::local_tree<V>(Production::chains((stream?b.peer:b.w)+source*b.rb,b.x,physical));
    }
    for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
    if(in_range&&!physical){(stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?value:iq3::bits_float(0x7fc00000));
     if(!row){(stream?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).compare_exchange_strong(expected,1);}}
    }
   }));
  });
 }
#endif
};
struct Down final:p49b::Base {
 using Production=p100::Kernel<2>;
 static constexpr unsigned K=640,WG=64,V=Production::V,P=Production::P,SG=Production::SG,RowsPerGroup=Production::RowsPerGroup;
 static_assert(V==16&&P==2&&SG==2&&RowsPerGroup==32);
 unsigned rows=2560,count=10,experts=512;
 p39::Bound bind(std::span<void*const>p)const{Production base;base.rows=rows;base.count=count;base.experts=experts;return base.bind(p);}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  for(unsigned group=0;group<groups;++group)for(unsigned sub=0;sub<SG;++sub)for(unsigned rr=0;rr<V;++rr){
   unsigned logical=Production::logical_row(Production::mapped_group(group,rows,count),sub,rr*P);if(logical>=total)continue;
   unsigned row=logical%rows,slot=logical/rows;
   auto route=b.routes[slot];bool ok=iq3::valid_route(route,experts,rows,rows),valid=ok&&row<route.row_count;
   float values[P]{};if(valid){size_t source=(size_t(route.expert_id)*rows+route.row_begin+row)&(alias_rows-1);
    for(unsigned lane=0;lane<P;++lane)values[lane]=p49dvirtual::local_tree<V>(Production::chains(b.w,source,b.x+slot*K,lane));
   }
   for(unsigned width=1;width<P;width*=2)for(unsigned lane=0;lane<P;lane+=2*width)values[lane]=values[lane]+values[lane+width];
   b.y[logical]=iq3::bf16_bits(valid?values[0]:iq3::bits_float(0x7fc00000));
   if(!row){b.status[slot]=!ok;if(!ok&&*b.active&&!*b.error)*b.error=1;}
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;(void)deps;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(groups)*WG,WG)](sycl::handler& h){
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,physical=lane%P;
    unsigned logical=Production::logical_row(Production::mapped_group(it.get_group_linear_id(),b.rows,b.count),sub,lane),row=logical%b.rows,slot=logical/b.rows;bool in_range=logical<total;
    iq3::Route route{};if(in_range)route=b.routes[slot];bool ok=in_range&&iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;
    float value=0;if(valid){size_t source=(size_t(route.expert_id)*b.rows+route.row_begin+row)&(alias_rows-1);
     value=p49dvirtual::local_tree<V>(Production::chains(b.w,source,b.x+slot*K,physical));
    }
    for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
    if(in_range&&!physical){b.y[logical]=iq3::bf16_bits(valid?value:iq3::bits_float(0x7fc00000));
     if(!row){b.status[slot]=!ok;if(!ok&&*b.active){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).compare_exchange_strong(expected,1);}}
    }
   }));
  });
 }
#endif
};
}
