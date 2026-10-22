#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p93_kernel.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/build/checked/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/prepared_submission.hpp"
#endif
#line 1
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/build/checked/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/adapter.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/build/checked/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/p93_head.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace p93 {
#ifdef OWN_RT_HOST_ONLY
using Base=integrated::HostOperation;
#else
using Base=ownrt::SyclOperation;
#endif
template<unsigned Mode>struct Kernel final:Base {
 unsigned rows=0;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {auto*w=static_cast<const uint8_t*>(p[0]);auto*x=static_cast<const uint16_t*>(p[1]);auto*y=static_cast<uint16_t*>(p[2]);
  for(unsigned row=0;row<rows;++row){float lanes[32];for(unsigned l=0;l<32;++l)lanes[l]=lane<Mode>(w,size_t(rows)*10,row,x,0,K,l);y[row]=iq3::bf16_bits(iq3::tree32(lanes));}
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {
  auto*w=static_cast<const uint8_t*>(p[0]);auto*x=static_cast<const uint16_t*>(p[1]);auto*y=static_cast<uint16_t*>(p[2]);unsigned n=rows;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(n)*32,32)](sycl::handler& h){
   // Same SG32, WG32 and adjacent reduction as the shipped p33 target head.
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    unsigned row=it.get_group_linear_id(),l=it.get_local_linear_id();auto sg=it.get_sub_group();float v=lane<Mode>(w,size_t(n)*10,row,x,0,K,l);
    for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,v,(l+width)%32);if(l%(2*width)==0)v=v+rhs;}
    if(!l)y[row]=iq3::bf16_bits(v);
   }));
  });
 }
#endif
};
}
