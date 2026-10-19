#pragma once
// Derived from packet65 wide64: all raw loads and decode_tile calls unchanged.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/production65.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/build/checked/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/p90_expert.hpp"
namespace p68c {
using p65::RawTile;using p65::decode_tile;
template<Type T,unsigned K,unsigned V>inline std::array<std::array<float,V>,2> wide_pair(const uint8_t*w,const uint16_t*x0,const uint16_t*x1,unsigned physical){
 constexpr auto l=p49bgemv::layout(T,K);std::array<std::array<float,V>,2> sums{};
 for(unsigned step=0;step<(K+255)/256;++step){
  if constexpr(T==Type::IQ2_S){
   static_assert(V==8);unsigned first=step*256+8*physical*V;
   uint32_t codes[4];
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint32_t,4> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+step*64+physical*16)));
   #pragma unroll
   for(unsigned i=0;i<4;++i)codes[i]=words[i];
#else
   for(unsigned i=0;i<4;++i)codes[i]=p49bgemv::load32(w+step*64+physical*16+4*i);
#endif
   uint16_t high=p49bgemv::load16(w+l.high+step*8+physical*2);
   uint16_t scales=p49bgemv::load16(w+l.scales+step*8+physical*2);
   float decoded=iq3::bits_float(p49bgemv::load32(w+l.halves+4*step));
   #pragma unroll
   for(unsigned chain=0;chain<V;++chain){unsigned k=first+chain*8;RawTile t;t.a=(codes[chain/2]>>(16*(chain%2)))&65535;t.high=(high>>(8*(chain/4)))&255;t.scale=(scales>>(8*(chain/4)))&255;
    float values[8];p90exp::decode_tile<T>(t,k,values,decoded);
#if defined(__SYCL_DEVICE_ONLY__)
    sycl::vec<uint16_t,8> a,b;a.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x0+k));b.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x1+k));
#endif
    #pragma unroll
    for(unsigned j=0;j<8;++j){
#if defined(__SYCL_DEVICE_ONLY__)
     uint16_t bits0=a[j],bits1=b[j];
#else
     uint16_t bits0=x0[k+j],bits1=x1[k+j];
#endif
     float p0=values[j]*iq3::bits_float(uint32_t(bits0)<<16);sums[0][chain]=sums[0][chain]+p0;float p1=values[j]*iq3::bits_float(uint32_t(bits1)<<16);sums[1][chain]=sums[1][chain]+p1;
    }
   }
  }else{
   static_assert(V==16);
   #pragma unroll
   for(unsigned block_in_lane=0;block_in_lane<V/4;++block_in_lane){
    unsigned first=step*256+8*(physical*V+block_in_lane*4);if(first>=K)continue;
    unsigned block=first/32;uint32_t codes[4];
#if defined(__SYCL_DEVICE_ONLY__)
    sycl::vec<uint32_t,4> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+block*16)));
    #pragma unroll
    for(unsigned i=0;i<4;++i)codes[i]=words[i];
#else
    for(unsigned i=0;i<4;++i)codes[i]=p49bgemv::load32(w+block*16+4*i);
#endif
    uint16_t half=p49bgemv::load16(w+l.halves+2*block);
    #pragma unroll
    for(unsigned c=0;c<4;++c){unsigned chain=block_in_lane*4+c,k=first+8*c;RawTile t;t.a=codes[(c%2)*2];t.b=codes[(c%2)*2+1];t.half=half;
     float values[8];decode_tile<T>(t,k,values);
#if defined(__SYCL_DEVICE_ONLY__)
     sycl::vec<uint16_t,8> a,b;a.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x0+k));b.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x1+k));
#endif
     #pragma unroll
     for(unsigned j=0;j<8;++j){
#if defined(__SYCL_DEVICE_ONLY__)
      uint16_t bits0=a[j],bits1=b[j];
#else
      uint16_t bits0=x0[k+j],bits1=x1[k+j];
#endif
      float p0=values[j]*iq3::bits_float(uint32_t(bits0)<<16);sums[0][chain]=sums[0][chain]+p0;float p1=values[j]*iq3::bits_float(uint32_t(bits1)<<16);sums[1][chain]=sums[1][chain]+p1;
     }
    }
   }
  }
 }
 return sums;
}
}
