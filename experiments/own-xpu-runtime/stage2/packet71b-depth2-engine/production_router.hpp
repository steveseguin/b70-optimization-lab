#pragma once
// Production kopt3 constant-split4 F32 router: four SGs/WG, four global
// partials per output, adjacent reduction, BF16 once. Only add row accumulators.
#include "production_rows.hpp"
namespace p71b {
using p68c::Base;using iq3::Type;
struct Router final:Base {
 unsigned rows=512;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {
  auto b=p68c::production_bind(p);
  for(unsigned row=0;row<rows;++row){float partial[2][4];
   for(unsigned part=0;part<4;++part){auto bounds=iq3::kopt2::bounds(2560,part,4);float lanes[2][32];
    for(unsigned l=0;l<32;++l){auto v=p68c::production_lane<Type::F32,2560>(b.w+row*2560*4,b.x[0],b.x[1],bounds.first,bounds.second,l);for(unsigned r=0;r<2;++r)lanes[r][l]=v[r];}
    for(unsigned r=0;r<2;++r)b.scratch[r][row*4+part]=partial[r][part]=iq3::tree32(lanes[r]);
   }
   for(unsigned r=0;r<2;++r){auto v=partial[r];b.y[r][row]=iq3::bf16_bits((v[0]+v[1])+(v[2]+v[3]));}
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {
  auto b=p68c::production_bind(p);unsigned n=rows;
  return q.submit([&](sycl::handler&h){h.depends_on(deps);
   h.parallel_for(sycl::nd_range<1>(size_t(n)*128,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    unsigned row=it.get_group_linear_id(),part=it.get_local_linear_id()/32,lane=it.get_local_linear_id()%32;
    auto bounds=iq3::kopt2::bounds(2560,part,4);
    auto v=p68c::production_lane<Type::F32,2560>(b.w+row*2560*4,b.x[0],b.x[1],bounds.first,bounds.second,lane);
    for(unsigned r=0;r<2;++r){v[r]=p68c::tree(it.get_sub_group(),v[r]);if(!lane)b.scratch[r][row*4+part]=v[r];}
   });});
 }
#endif
};
struct RouterFinish final:Base {
 unsigned rows=512;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>)const override{} // primary finishes host bytes
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {
  auto b=p68c::production_bind(p);unsigned n=rows;
  return q.submit([&](sycl::handler&h){h.depends_on(deps);
   h.parallel_for(sycl::nd_range<1>(((n+127)/128)*128,128),[=](sycl::nd_item<1>it){unsigned row=it.get_global_linear_id();if(row<n)for(unsigned r=0;r<2;++r){auto v=b.scratch[r]+row*4;b.y[r][row]=iq3::bf16_bits((v[0]+v[1])+(v[2]+v[3]));}});});
 }
#endif
};
inline integrated::Launch router(ownrt::Device&d,const integrated::Matrix&a,const integrated::Matrix&b,unsigned variant){
 if(variant!=4||a.type!=Type::F32||b.type!=Type::F32||a.columns!=2560||b.columns!=2560||a.rows!=512||b.rows!=512||a.w!=b.w||a.count!=1||b.count!=1||a.experts!=1||b.experts!=1||a.routes||b.routes||a.activation!=Type::BF16||b.activation!=Type::BF16||a.output_type!=Type::BF16||b.output_type!=Type::BF16||a.fp32||b.fp32)throw std::invalid_argument("71b production router identity");
 std::array<ownrt::Allocation,15>ids{a.w,a.x,b.x,a.y,b.y,a.workspace,b.workspace,a.y,b.y,a.x,b.x,a.y,b.y,a.y,b.y};
 const size_t bytes[]={512*2560*4,2560*2,2560*2,512*2,512*2,512*4*4,512*4*4};
 for(unsigned i=0;i<7;++i){const auto&r=d.arena.row(ids[i]);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<bytes[i]||uintptr_t(r.pointer)%(i==0?64:16))throw std::invalid_argument("71b router extent/alignment");}
 for(unsigned i=3;i<7;++i)for(unsigned j=0;j<7;++j)if(i!=j&&ids[i]==ids[j])throw std::invalid_argument("71b router alias");
 Router op;auto first=d.compute(op,ids,{});RouterFinish finish;std::array after{first};auto last=d.compute(finish,ids,after);return {first,last,2};
}
}
