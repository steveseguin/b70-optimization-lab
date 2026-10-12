#pragma once
#if defined(__SYCL_DEVICE_ONLY__)
#include <sycl/sycl.hpp>
#endif
#include "../packet29-merged/p28/expert.hpp"
#include "../packet29-merged/p28/dense.hpp"
#include "../packet29-merged/round2.hpp"
namespace p33 {
// No memory lookup and no 64-bit integer code word. Each selected bank has four
// signed bytes. C++20 unsigned-to-int8_t conversion is modulo 256, followed
// by sign extension to int; no signed right shift is used.
inline int level_bank(unsigned q) {
 const uint32_t lo=(q&4)?0xf6eaddcfu:0xbfad9881u;
 const uint32_t hi=(q&4)?0x71594535u:0x26190d01u;
 const uint32_t bank=(q&8)?hi:lo;
 const unsigned byte=(bank>>(8*(q&3)))&255;
 return int(int8_t(byte));
}
inline int level_select(unsigned q) {
 const int a=(q&1)?-104:-127,b=(q&1)?-65:-83;
 const int c=(q&1)?-35:-49,d=(q&1)?-10:-22;
 const int e=(q&1)?13:1,f=(q&1)?38:25;
 const int g=(q&1)?69:53,h=(q&1)?113:89;
 return (q&8)?((q&4)?((q&2)?h:g):((q&2)?f:e)):
               ((q&4)?((q&2)?d:c):((q&2)?b:a));
}
template<unsigned Mode,unsigned K=640>
inline float down_lane(const uint8_t* __restrict row,const uint16_t* __restrict x,unsigned lane) {
 static_assert(Mode<2 && K>0);
 float sum=0;
 for(unsigned k=lane*8;k<K;k+=256){
  const uint8_t* block=row+(k/32)*18;
  const float scale=iq3::half(uint16_t(block[0])|(uint16_t(block[1])<<8));
  const unsigned offset=k%32;
#if defined(__SYCL_DEVICE_ONLY__)
  // Production K640 has complete eight-weight lane tiles. Explicit vectors
  // request the same contiguous bytes the scalar path uses, with no overread.
  // Odd CPU diagnostic lengths retain their bounds-checked scalar spelling.
  sycl::vec<uint8_t,8> packed_codes;
  sycl::vec<uint16_t,8> packed_inputs;
  if constexpr(Mode==0 && K%8==0){
   packed_codes.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(block+2+offset%16));
   packed_inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
  }
#endif
  #pragma unroll
  for(unsigned j=0;j<8;++j)if(k+j<K){
   uint8_t code;
   uint16_t input_bits;
#if defined(__SYCL_DEVICE_ONLY__)
   if constexpr(Mode==0 && K%8==0){code=packed_codes[j];input_bits=packed_inputs[j];}
   else
#endif
   {code=block[2+(offset+j)%16];input_bits=x[k+j];}
   const unsigned q=(code>>(4*((offset+j)/16)))&15;
   const int level=Mode==0?level_bank(q):level_select(q);
   const float value=scale*float(level);
   const float input=iq3::bits_float(uint32_t(input_bits)<<16);
   const float product=value*input;sum=sum+product;
  }
 }
 return sum;
}
// The read-only operands must not overlap. No floating-point operation changes.
template<iq3::Type T,unsigned K,bool Paired>
inline auto expert_lane(const uint8_t* __restrict w,const uint8_t* __restrict peer,
 const uint16_t* __restrict x,unsigned begin,unsigned end,unsigned lane) {
 return p28::expert_lane<T,K,false,Paired>(w,peer,x,begin,end,lane,
  p28::ExpertByteTables{},iq3::kopt3::HostShare{});
}
// This candidate is qualified only for ranges aligned to 256 (or end==K).
// It removes the generic scale-segment loop; each lane tile occupies one group.
template<iq3::Type T,unsigned K>
inline float dense_lane(const uint8_t* __restrict w,const uint16_t* __restrict x,
 unsigned begin,unsigned end,unsigned lane) {
 static_assert(T==iq3::Type::Q6_K || T==iq3::Type::Q8_0);
 static_assert(K%iq3::layout(T).elements==0);
 constexpr unsigned group=T==iq3::Type::Q6_K?16:32;
 float sum=0;
 for(unsigned tile=begin+lane*8;tile<end;tile+=256){
  const float scale=iq3::bits_float(iq3::u32(w+K+4*(tile/group)));
  #pragma unroll
  for(unsigned j=0;j<8;++j)if(tile+j<end){
   // expanded::value is precisely scale * signed8 for these two formats,
   // including exceptional scales. Keep multiply argument order unchanged.
   float value=scale*float(iq3::signed8(w[tile+j]));
   float input=iq3::bits_float(uint32_t(x[tile+j])<<16);
   float product=value*input;sum=sum+product;
  }
 }
 return sum;
}
// Integer rank scheduling only: four comparisons before the early-exit test.
// Losing ranks can exceed Top, but only rank<Top writes any output.
template<unsigned N=512,unsigned Top=10>
inline unsigned route_rank(const float* __restrict probability,unsigned j){
 const float v=probability[j];unsigned rank=0;
 for(unsigned first=0;first<N && rank<Top;first+=4){
  #pragma unroll
  for(unsigned z=0;z<4;++z)if(first+z<N){
   unsigned k=first+z;float x=probability[k];rank+=x>v||(x==v&&k<j);
  }
 }
 return rank;
}
// Caller validates these dimensions before dispatch. All arithmetic and barriers
// are from the unchanged round2 body; specializing shape removes dynamic math.
template<ng::Op Code,int Stage,int Capacity,int Budget,int Tokens,class Team>
inline void qsa_group(ng::Shape s,ng::Args a,int group,float* global,Team t){
 s.op=Code;s.capacity=Capacity;s.budget=Budget;s.tokens=Tokens;
 round2::group<Code,Stage>(s,a,group,global,t);
}
} // namespace p33
