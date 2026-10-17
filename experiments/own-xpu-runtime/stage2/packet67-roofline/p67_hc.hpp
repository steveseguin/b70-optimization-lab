#pragma once
#include "p60_math.hpp"
#include "p49d_small.hpp"
namespace p67hc {
// Four adjacent original SG32 leaves per physical lane. The local tree is
// exactly levels 1 and 2 of tree32, followed by the remaining adjacent tree8.
// Four streams share SG32; one subgroup produces one complete mixed output.
inline void host(p60::Bound b) {
 // Keep production's exceptional-value operand selection as well as its
 // finite arithmetic. No NaN payload canonicalization or tolerance.
 for(unsigned j=0;j<320;++j)if((b.act[j]&0x7f80)==0x7f80){p60::host_gate_mix(b);return;}
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
   bool exceptional=false;for(unsigned j=lane;j<320;j+=32)exceptional|=(b.act[j]&0x7f80)==0x7f80;
   exceptional=sycl::any_of_group(sg,exceptional);
   uint16_t y;
   if(exceptional){
    uint16_t gates[4];for(unsigned s=0;s<4;++s){unsigned r=s*2560+k;
     float v=p49c::dense_lane<iq3::Type::Q8_0,320>(b.gate_w+r*rb,b.act,0,320,lane);
     for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,v,(lane+width)%32);if(lane%(2*width)==0)v=v+rhs;}
     gates[s]=sycl::select_from_group(sg,iq3::bf16_bits(v),0);if(!lane)b.gate[r]=gates[s];
    }
    y=gates[stream];
   }else{
    float value=p49dvirtual::local_tree<4>(p49dvirtual::dense_chains<iq3::Type::Q8_0,320,4>(b.gate_w+row*rb,b.act,0,320,physical));
    for(unsigned width=1;width<8;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
    y=iq3::bf16_bits(value);if(!physical)b.gate[row]=y;
   }
   // The four independent sigmoid/products run on their stream's leader.
   // Shuffling their FP32 results changes no arithmetic. Lane zero retains
   // the original +0, stream0, stream1, stream2, stream3 sum and final /4.
   auto err=sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error);
   bool enabled=*b.active&&!err.load()&&*b.position<b.capacity;float term=0.f;
   if(!physical&&enabled)term=ng::sigmoid(p39::widen(y))*p60::get(b.norm,stream*2560+k);
   float sum=0.f;for(unsigned s=0;s<4;++s){float value=sycl::select_from_group(sg,term,s*8);sum=sum+value;}
   if(!lane&&enabled)b.mix[k]=iq3::bf16_bits(sum/4.f);
  });
 });
}
#endif
}
