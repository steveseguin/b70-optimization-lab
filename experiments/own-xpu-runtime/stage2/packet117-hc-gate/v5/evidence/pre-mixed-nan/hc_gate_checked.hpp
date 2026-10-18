#ifndef OWN_RT_HOST_ONLY
#include "prepared_submission.hpp"
#endif
#line 1
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet111-record-bundle/build/checked/experiments/own-xpu-runtime/stage2/packet111-record-bundle/p73_hc.hpp"
namespace p117hc {
// Identical production paired-row chains; only independent epilogue placement changes.
using p73hc::chains;
inline void host(p60::Bound b){
 const auto rb=iq3::expanded::row_bytes(iq3::Type::Q8_0,320);
 for(unsigned k=0;k<2560;k+=2){uint16_t gates[2][4];float products[2][4];
  for(unsigned s=0;s<4;++s){unsigned r=s*2560+k;float lanes[2][32];
   for(unsigned lane=0;lane<32;++lane){auto v=chains(b.gate_w+r*rb,b.act,lane);for(unsigned row=0;row<2;++row)lanes[row][lane]=v[row];}
   for(unsigned row=0;row<2;++row){gates[row][s]=iq3::bf16_bits(iq3::tree32(lanes[row]));b.gate[r+row]=gates[row][s];if(p60::enabled(b))products[row][s]=ng::sigmoid(p39::widen(gates[row][s]))*p60::get(b.norm,s*2560+k+row);}
  }
  if(p60::enabled(b))for(unsigned row=0;row<2;++row){float sum=0.f;for(unsigned s=0;s<4;++s)sum=sum+products[row][s];b.mix[k+row]=iq3::bf16_bits(sum/4.f);}
 }
}
#ifndef OWN_RT_HOST_ONLY
inline sycl::event device(sycl::queue&q,p60::Bound b,const std::vector<sycl::event>&deps){
 const auto rb=iq3::expanded::row_bytes(iq3::Type::Q8_0,320);
 return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(640*256,256)](sycl::handler& h){sycl::local_accessor<float,1> products(16,h);
 h.parallel_for(p35_range0,[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  unsigned local=it.get_local_linear_id(),sub=local/32,lane=local%32,stream=sub%4,base=it.get_group_linear_id()*4+(sub/4)*2,r=stream*2560+base;auto sg=it.get_sub_group();
  auto sums=chains(b.gate_w+r*rb,b.act,lane);
  float v0=sums[0],v1=sums[1];
  for(unsigned s=1;s<32;s*=2){float rhs0=sycl::select_from_group(sg,v0,(lane+s)%32),rhs1=sycl::select_from_group(sg,v1,(lane+s)%32);if(lane%(2*s)==0){v0=v0+rhs0;v1=v1+rhs1;}}
  // Each paired row uses one existing lane for its independent expensive
  // sigmoid/product. Both broadcasts preserve the original leader's FP32 bits.
  float root0=sycl::select_from_group(sg,v0,0),root1=sycl::select_from_group(sg,v1,0);
  if(lane<2){uint16_t y=iq3::bf16_bits(lane==0?root0:root1);b.gate[r+lane]=y;
   auto error=sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error);
   if(*b.active&&!error.load()&&*b.position<b.capacity)
    products[(sub/4)*8+lane*4+stream]=ng::sigmoid(p39::widen(y))*p60::get(b.norm,r+lane);
  }
  it.barrier(sycl::access::fence_space::local_space);
  auto error=sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error);
  if(local<4&&*b.active&&!error.load()&&*b.position<b.capacity){unsigned out=it.get_group_linear_id()*4+local;float sum=0.f;for(unsigned s=0;s<4;++s)sum=sum+products[local*4+s];b.mix[out]=iq3::bf16_bits(sum/4.f);}
 });});
}
#endif
}
