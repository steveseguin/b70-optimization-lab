#pragma once
#include "p60_kernels.hpp"
namespace p86hc {
using namespace p60;
template<unsigned Mode>inline float lane_value(const uint8_t*w,const uint16_t*x,unsigned lane){
 float sum=0;
 for(unsigned k=lane*8;k<L;k+=256){
  uint32_t scale_bits=*reinterpret_cast<const volatile uint32_t*>(w+L+4*(k/32));
  uint32_t lo=p49c::load32(w+k),hi=p49c::load32(w+k+4);
#if defined(__SYCL_DEVICE_ONLY__)
  sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
  for(unsigned j=0;j<8;++j){unsigned raw=((j<4?lo:hi)>>(8*(j%4)))&255;float value;
   if constexpr(Mode==1)value=float(raw); // unsigned raw bytes, no scale/sign decode
   else {float scale=Mode==2?0.00390625f:iq3::bits_float(scale_bits);value=scale*float(iq3::signed8(uint8_t(raw)));}
#if defined(__SYCL_DEVICE_ONLY__)
   uint16_t bits=inputs[j];
#else
   uint16_t bits=x[k+j];
#endif
   float product=value*iq3::bits_float(uint32_t(bits)<<16);sum=sum+product;
  }
 }
 return sum;
}
template<unsigned Mode>inline void host(Bound b){
 const auto rb=iq3::expanded::row_bytes(Type::Q8_0,L);
 for(unsigned k=0;k<H;++k){uint16_t gates[S];for(unsigned s=0;s<S;++s){unsigned row=s*H+k;float lanes[32];for(unsigned l=0;l<32;++l)lanes[l]=lane_value<Mode>(b.gate_w+row*rb,b.act,l);gates[s]=iq3::bf16_bits(iq3::tree32(lanes));b.gate[row]=gates[s];}mix_output(b,k,gates);}
}
#ifndef OWN_RT_HOST_ONLY
template<unsigned Mode>inline sycl::event device(sycl::queue&q,Bound b,const std::vector<sycl::event>&deps){
 const size_t rb=iq3::expanded::row_bytes(Type::Q8_0,L);
 return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<uint16_t,1> gates(8,h);
  h.parallel_for(sycl::nd_range<1>((H/2)*256,256),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   unsigned local=it.get_local_linear_id(),sub=local/32,lane=local%32,k=it.get_group_linear_id()*2+sub/4,stream=sub%4,row=stream*H+k;
   float value=lane_value<Mode>(b.gate_w+row*rb,b.act,lane);value=tree(it.get_sub_group(),value);
   if(!lane){uint16_t y=iq3::bf16_bits(value);b.gate[row]=y;gates[sub]=y;}
   it.barrier(sycl::access::fence_space::local_space);
   if(local<2&&*b.active&&!failed(b)&&*b.position<b.capacity){unsigned out=it.get_group_linear_id()*2+local;float sum=0.f;for(unsigned s=0;s<S;++s)sum=sum+ng::sigmoid(p39::widen(gates[local*4+s]))*get(b.norm,s*H+out);b.mix[out]=iq3::bf16_bits(sum/4.f);}
  });
 });
}
#endif
}
