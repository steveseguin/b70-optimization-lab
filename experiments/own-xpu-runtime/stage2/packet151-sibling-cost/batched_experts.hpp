#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/batched_rows.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/production_expert_chains.hpp"
namespace p68c {
using ownrt::Allocation;
inline bool same_route(iq3::Route a,iq3::Route b){return a.expert_id==b.expert_id&&a.row_begin==b.row_begin&&a.row_count==b.row_count;}
// Stable multiset union. Production routes are unique; ordinal matching also
// gives every duplicate/partial/invalid fixture slot exactly one writer.
inline int matching_slot(const iq3::Route*from,const iq3::Route*to,unsigned slot,unsigned count){
 unsigned ordinal=0;for(unsigned j=0;j<slot;++j)ordinal+=same_route(from[j],from[slot]);
 for(unsigned j=0;j<count;++j)if(same_route(to[j],from[slot])){if(!ordinal)return int(j);--ordinal;}return -1;
}
struct UnionSlots {int a=-1,b=-1;};
inline UnionSlots union_slot(const iq3::Route*a,const iq3::Route*b,unsigned index,unsigned count){
 if(index<count)return {int(index),matching_slot(a,b,index,count)};
 unsigned j=index-count;return matching_slot(b,a,j,count)<0?UnionSlots{-1,int(j)}:UnionSlots{};
}
template<Type T,unsigned K,unsigned V>inline std::array<std::array<float,V>,2> expert_chains(const uint8_t*w,const uint16_t*x0,const uint16_t*x1,unsigned physical,bool live0,bool live1,size_t source){
 // Missing union rows have valid scratch/input bindings; only their stores
 // are masked. No divergent loop or changed weight/activation load geometry.
 return wide_pair<T,K,V>(w,x0,x1,physical,source);
}
struct ExpertBound {const uint8_t*w,*peer;const uint16_t*x[2];uint16_t*y[2],*py[2];const iq3::Route*routes[2];uint32_t*status[2],*ps[2],*error[2];const uint32_t*active[2];};
inline ExpertBound expert_bind(std::span<void*const>p){return {(const uint8_t*)p[0],(const uint8_t*)p[1],{(const uint16_t*)p[2],(const uint16_t*)p[3]},{(uint16_t*)p[4],(uint16_t*)p[5]},{(uint16_t*)p[6],(uint16_t*)p[7]},{(const iq3::Route*)p[8],(const iq3::Route*)p[9]},{(uint32_t*)p[10],(uint32_t*)p[11]},{(uint32_t*)p[12],(uint32_t*)p[13]},{(uint32_t*)p[14],(uint32_t*)p[15]},{(const uint32_t*)p[16],(const uint32_t*)p[17]}};}
template<Type T>struct ExpertKernel final:Base {
 static constexpr bool gate=T==Type::IQ2_S;
 static constexpr unsigned K=gate?2560:640,V=gate?8:16,P=32/V;
 unsigned rows=gate?640:2560,count=10,experts=512;
 static constexpr size_t rb=gate?p90::expert_stride(K):p49bgemv::layout(T,K).row_bytes;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=expert_bind(p);
  for(unsigned u=0;u<2*count;++u){auto pair=union_slot(b.routes[0],b.routes[1],u,count);int slots[2]={pair.a,pair.b};if(pair.a<0&&pair.b<0)continue;auto route=pair.a>=0?b.routes[0][pair.a]:b.routes[1][pair.b];bool ok=iq3::valid_route(route,experts,rows,rows);
   for(unsigned row=0;row<rows;++row){bool valid=ok&&row<route.row_count;
    for(unsigned stream=0;stream<(gate?2u:1u);++stream){float values[2][P]{};
     if(valid){size_t source=size_t(route.expert_id)*rows+route.row_begin+row;auto w=(stream?b.peer:b.w)+(gate?source*rb:0);const uint16_t*x0=b.x[0]+(!gate&&pair.a>=0?pair.a*K:0),*x1=b.x[1]+(!gate&&pair.b>=0?pair.b*K:0);
      for(unsigned physical=0;physical<P;++physical){auto v=expert_chains<T,K,V>(w,x0,x1,physical,pair.a>=0,pair.b>=0,source);for(unsigned r=0;r<2;++r)values[r][physical]=p49dvirtual::local_tree<V>(v[r]);}}
     for(unsigned r=0;r<2;++r)if(slots[r]>=0){for(unsigned width=1;width<P;width*=2)for(unsigned lane=0;lane<P;lane+=2*width)values[r][lane]=values[r][lane]+values[r][lane+width];(stream?b.py[r]:b.y[r])[slots[r]*rows+row]=iq3::bf16_bits(valid?values[r][0]:iq3::bits_float(0x7fc00000));if(!row){(stream?b.ps[r]:b.status[r])[slots[r]]=!ok;if(!ok&&*b.active[r]&&!*b.error[r])*b.error[r]=1;}}
    }
   }
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=expert_bind(p);unsigned nrows=rows,n=count,ne=experts,total=2*n*rows,groups=(total+(gate?1:2)*V-1)/((gate?1:2)*V);
  return q.submit([&](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(size_t(groups)*64,64),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,stream=gate?sub%2:0,physical=lane%P;
   unsigned logical=(it.get_group_linear_id()*(gate?1:2)+(gate?sub/2:sub))*V+lane/P;
   bool in_range=logical<total;unsigned row=logical%nrows,u=logical/nrows;UnionSlots pair;if(in_range)pair=union_slot(b.routes[0],b.routes[1],u,n);int slots[2]={pair.a,pair.b};
   iq3::Route route{};if(pair.a>=0)route=b.routes[0][pair.a];else if(pair.b>=0)route=b.routes[1][pair.b];bool ok=(pair.a>=0||pair.b>=0)&&iq3::valid_route(route,ne,nrows,nrows),valid=ok&&row<route.row_count;float value[2]{};
   if(valid){size_t source=size_t(route.expert_id)*nrows+route.row_begin+row;const uint16_t*x0=b.x[0]+(!gate&&pair.a>=0?pair.a*K:0),*x1=b.x[1]+(!gate&&pair.b>=0?pair.b*K:0);auto sums=expert_chains<T,K,V>((stream?b.peer:b.w)+(gate?source*rb:0),x0,x1,physical,pair.a>=0,pair.b>=0,source);for(unsigned r=0;r<2;++r)value[r]=p49dvirtual::local_tree<V>(sums[r]);}
   for(unsigned r=0;r<2;++r){for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,value[r],(lane+width)%32);if(physical%(2*width)==0)value[r]=value[r]+rhs;}
    if(!physical&&slots[r]>=0){(stream?b.py[r]:b.y[r])[slots[r]*nrows+row]=iq3::bf16_bits(valid?value[r]:iq3::bits_float(0x7fc00000));if(!row){(stream?b.ps[r]:b.status[r])[slots[r]]=!ok;if(!ok&&*b.active[r]){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error[r]).compare_exchange_strong(expected,1);}}}
   }
  });});
 }
#endif
};
inline integrated::Launch experts(ownrt::Device&d,const std::vector<integrated::Matrix>&a,const std::vector<integrated::Matrix>&b,const std::array<Allocation,2>&error,const std::array<Allocation,2>&active){
 if(a.empty()||a.size()!=b.size())throw std::invalid_argument("68c expert pair count");bool gate=a[0].type==Type::IQ2_S;unsigned k=gate?2560:640;
 if((gate&&a.size()!=2)||(!gate&&(a.size()!=1||a[0].type!=Type::IQ4_NL)))throw std::invalid_argument("68c expert type");
 for(unsigned r=0;r<2;++r)for(auto m:r?b:a)if(m.columns!=k||m.type!=a[0].type||m.rows!=a[0].rows||m.count!=a[0].count||m.experts!=a[0].experts||!m.routes||!m.status||!m.count||m.count>10||m.activation!=Type::BF16||m.output_type!=Type::BF16)throw std::invalid_argument("68c expert geometry");
 for(unsigned i=0;i<a.size();++i)if(a[i].w!=b[i].w)throw std::invalid_argument("68c expert weights not shared");
 auto aa=gate?a[1]:a[0],bb=gate?b[1]:b[0];std::array<Allocation,18>ids{a[0].w,aa.w,a[0].x,b[0].x,a[0].y,b[0].y,aa.y,bb.y,a[0].routes,b[0].routes,a[0].status,b[0].status,aa.status,bb.status,error[0],error[1],active[0],active[1]};
 size_t rb=gate?p90::expert_stride(k):p49bgemv::layout(a[0].type,k).row_bytes,n=a[0].rows*a[0].count;size_t bytes[]={a[0].experts*a[0].rows*rb,a[0].experts*a[0].rows*rb,size_t(k)*(gate?1:a[0].count)*2,size_t(k)*(gate?1:a[0].count)*2,n*2,n*2,n*2,n*2,a[0].count*sizeof(iq3::Route),a[0].count*sizeof(iq3::Route),a[0].count*4,a[0].count*4,a[0].count*4,a[0].count*4,4,4,4,4};
 for(unsigned j=0;j<ids.size();++j){auto&r=d.arena.row(ids[j]);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<bytes[j])throw std::invalid_argument("68c expert extent");}
 ownrt::Event e;if(gate){ExpertKernel<Type::IQ2_S>op;op.rows=a[0].rows;op.count=a[0].count;op.experts=a[0].experts;e=d.compute(op,ids,{});}else {ExpertKernel<Type::IQ4_NL>op;op.rows=a[0].rows;op.count=a[0].count;op.experts=a[0].experts;e=d.compute(op,ids,{});}return {e,e,1};
}
}
