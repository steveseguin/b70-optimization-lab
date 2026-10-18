#pragma once
#include "p60_math.hpp"
#include "p49d_small.hpp"
namespace p67hc {
// Four adjacent original SG32 leaves per physical lane. The local tree is
// exactly levels 1 and 2 of tree32, followed by the remaining adjacent tree8.
// Four streams share SG32; one subgroup produces one complete mixed output.
inline void host(p60::Bound b) {
 const auto rb=iq3::expanded::row_bytes(iq3::Type::Q8_0,320);
 for(unsigned k=0;k<2560;++k){uint16_t gates[4];
  for(unsigned s=0;s<4;++s){unsigned row=s*2560+k;
   float lanes[8];for(unsigned physical=0;physical<8;++physical)lanes[physical]=p49dvirtual::local_tree<4>(p49dvirtual::dense_chains<iq3::Type::Q8_0,320,4>(b.gate_w+row*rb,b.act,0,320,physical));
   for(unsigned width=1;width<8;width*=2)for(unsigned physical=0;physical<8;physical+=2*width)lanes[physical]=lanes[physical]+lanes[physical+width];
   gates[s]=iq3::bf16_bits(lanes[0]);b.gate[row]=gates[s];}
  p60::mix_output(b,k,gates);
 }
}
#ifndef OWN_RT_HOST_ONLY
inline sycl::event device(sycl::queue&q,p60::Bound b,const std::vector<sycl::event>&deps){
 const auto rb=iq3::expanded::row_bytes(iq3::Type::Q8_0,320);
 return q.submit([&](sycl::handler&h){h.depends_on(deps);
  h.parallel_for(sycl::nd_range<1>(2560*32,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),physical=lane%8,stream=lane/8,k=it.get_global_linear_id()/32,row=stream*2560+k;
   float value=p49dvirtual::local_tree<4>(p49dvirtual::dense_chains<iq3::Type::Q8_0,320,4>(b.gate_w+row*rb,b.act,0,320,physical));
   for(unsigned width=1;width<8;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
   uint16_t y=iq3::bf16_bits(value);if(!physical)b.gate[row]=y;
   // All lanes participate in the shuffles, including inactive/error cases.
   uint16_t gates[4];for(unsigned s=0;s<4;++s)gates[s]=sycl::select_from_group(sg,y,s*8);
   auto err=sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error);
   if(!lane&&*b.active&&!err.load()&&*b.position<b.capacity){
    float sum=0.f;for(unsigned s=0;s<4;++s)sum=sum+ng::sigmoid(p39::widen(gates[s]))*p60::get(b.norm,s*2560+k);
    b.mix[k]=iq3::bf16_bits(sum/4.f);
   }
  });
 });
}
#endif
}
