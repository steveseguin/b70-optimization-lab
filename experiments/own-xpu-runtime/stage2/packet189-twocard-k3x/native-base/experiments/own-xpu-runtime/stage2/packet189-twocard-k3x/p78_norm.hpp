#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p78_norm.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/build/checked/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/prepared_submission.hpp"
#endif
#line 1
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/build/checked/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/p60_kernels.hpp"
namespace p78norm {
// Each lane owns one original 32-leaf subtree, then the subgroup reduces
// the original 80 roots padded to 128. Exactly the packet60 upper tree.
inline float chunk(p60::Bound b,unsigned stream,unsigned c){
  if(c>=80)return 0.f;
  return specialised::subtree(p60::H,c,[&](int k){float x=p60::get(b.x,stream*p60::H+k);return x*x;});
}
inline void host(p60::Bound b){
  if(!*b.active||*b.error)return;
  if(*b.position>=b.capacity){*b.error=1;return;}
  for(unsigned s=0;s<4;++s){
    float roots[4]{};
    for(unsigned group=0;group<3;++group){
      float values[32];for(unsigned lane=0;lane<32;++lane){unsigned c=group*32+lane;values[lane]=chunk(b,s,c);if(c<80)b.scratch[s*80+c]=values[lane];}
      roots[group]=iq3::tree32(values);
    }
    float total=(roots[0]+roots[1])+(roots[2]+roots[3]);
    float inv=detmath::rsqrt(total/float(p60::H)+1e-6f);
    for(unsigned k=0;k<p60::H;++k)p60::norm_output(b,s,k,inv);
  }
}
#ifndef OWN_RT_HOST_ONLY
inline sycl::event device(sycl::queue&q,p60::Bound b,const std::vector<sycl::event>&deps){
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(40*32,32)](sycl::handler& h){
    h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
      unsigned lane=it.get_local_linear_id(),stream=it.get_group_linear_id()/10,tile=it.get_group_linear_id()%10;auto sg=it.get_sub_group();
      // All control reads are broadcast before branching, including sticky error.
      uint32_t enabled=0;if(!lane)enabled=uint32_t(*b.active&&!p60::failed(b));
      enabled=sycl::group_broadcast(sg,enabled,0);if(!enabled)return;
      if(*b.position>=b.capacity){if(!lane&&!stream&&!tile)p60::fail(b);return;}
      float roots[4]{};
      for(unsigned group=0;group<3;++group){unsigned c=group*32+lane;float v=chunk(b,stream,c);if(!tile&&c<80)b.scratch[stream*80+c]=v;v=p60::tree(sg,v);roots[group]=sycl::group_broadcast(sg,v,0);}
      float total=(roots[0]+roots[1])+(roots[2]+roots[3]);
      float inv=detmath::rsqrt(total/float(p60::H)+1e-6f);
      for(unsigned k=tile*256+lane;k<(tile+1)*256;k+=32)p60::norm_output(b,stream,k,inv);
    }));
  });
}
#endif
}
