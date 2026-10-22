#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p74_packed.hpp"
#pragma once
// Original lab implementation. GGUF field definitions come from our pinned
// packet2 decoder; no external kernel code. Exact FP32 rounding, no FMA.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/build/checked/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/p33_candidates.hpp"
namespace p74 {
using iq3::Type;
constexpr size_t row_bytes(Type t,unsigned k){return k/iq3::layout(t).elements*iq3::layout(t).bytes;}
inline uint32_t word(const uint8_t* p){
#if defined(__SYCL_DEVICE_ONLY__)
 return *reinterpret_cast<const uint32_t*>(p);
#else
 uint32_t x;std::memcpy(&x,p,4);return x;
#endif
}
inline uint16_t halfword(const uint8_t* p){
#if defined(__SYCL_DEVICE_ONLY__)
 return *reinterpret_cast<const uint16_t*>(p);
#else
 uint16_t x;std::memcpy(&x,p,2);return x;
#endif
}
// Eight bytes, using an aligned eight-byte vector plus one word only for the
// alternating two-byte block alignment. Caller guarantees 10 readable bytes.
inline void load8(const uint8_t* p,uint32_t& lo,uint32_t& hi){
 const unsigned shift=unsigned(uintptr_t(p)&3)*8;const auto* a=p-(shift/8);
#if defined(__SYCL_DEVICE_ONLY__)
 sycl::vec<uint32_t,2> v;v.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(a)));
 uint32_t x=v[0],y=v[1];
#else
 uint32_t x=word(a),y=word(a+4);
#endif
 if(shift){lo=(x>>16)|(y<<16);hi=(y>>16)|(word(a+8)<<16);}else {lo=x;hi=y;}
}
template<Type T>inline void decode8(const uint8_t* row,unsigned k,float (&out)[8]){
 static_assert(T==Type::Q6_K||T==Type::Q8_0);
 if constexpr(T==Type::Q6_K){
  const auto* b=row+(k/256)*210;unsigned i=k%256,half=i/128,section=(i%128)/32,l=i%32;
  uint32_t lo,hi,hlo,hhi;load8(b+half*64+(section%2)*32+l,lo,hi);load8(b+128+half*32+l,hlo,hhi);
  float scale=iq3::half(halfword(b+208))*float(iq3::signed8(b[192+i/16]));
  #pragma unroll
  for(unsigned j=0;j<8;++j){unsigned low=((j<4?lo:hi)>>(8*(j%4)))&255,high=((j<4?hlo:hhi)>>(8*(j%4)))&255;
   int code=int(((low>>(section>=2?4:0))&15)|(((high>>(2*section))&3)<<4))-32;
   out[j]=scale*float(code);
  }
 }else{
  const auto* b=row+(k/32)*34;unsigned i=k%32;uint32_t lo,hi;
  // Last Q8 group may end at allocation boundary. Never read into next row.
  const auto* p=b+2+i;
  if(i==24){lo=uint32_t(halfword(p))|(uint32_t(halfword(p+2))<<16);hi=uint32_t(halfword(p+4))|(uint32_t(halfword(p+6))<<16);}
  else load8(p,lo,hi);
  float scale=iq3::half(halfword(b));
  #pragma unroll
  for(unsigned j=0;j<8;++j)out[j]=scale*float(iq3::signed8(uint8_t((j<4?lo:hi)>>(8*(j%4)))));
 }
}
template<Type T,unsigned K>inline float lane(const uint8_t* w,const uint16_t* x,unsigned begin,unsigned end,unsigned lane_id){
 float sum=0;
 for(unsigned k=begin+lane_id*8;k<end;k+=256){float v[8];decode8<T>(w,k,v);
#if defined(__SYCL_DEVICE_ONLY__)
 sycl::vec<uint16_t,8> input;input.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
  #pragma unroll
  for(unsigned j=0;j<8;++j)if(k+j<end){
#if defined(__SYCL_DEVICE_ONLY__)
   uint16_t bits=input[j];
#else
   uint16_t bits=x[k+j];
#endif
   float product=v[j]*iq3::bits_float(uint32_t(bits)<<16);sum=sum+product;
  }
 }return sum;
}
} // namespace p74
