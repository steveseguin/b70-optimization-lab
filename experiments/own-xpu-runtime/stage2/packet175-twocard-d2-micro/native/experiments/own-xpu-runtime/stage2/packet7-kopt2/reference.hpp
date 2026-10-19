#pragma once
#include "../packet6-kopt/reference.hpp"
#include <array>
#include <algorithm>
namespace iq3::kopt2 {
// v1: split contiguous 256-column tiles; adjacent lane tree, then adjacent S tree.
// Wide variants preserve packet6 SG32 arithmetic, including its rounding points.
enum class Variant { split2, split4, wide32, wide64 };
inline const char* name(Variant v) {
  switch(v){case Variant::split2:return "splitk2_v1";case Variant::split4:return "splitk4_v1";
    case Variant::wide32:return "rows2_vec32_v1";case Variant::wide64:return "rows2_vec64_v1";}
  throw std::invalid_argument("variant");
}
inline unsigned splits(Variant v){name(v);return v==Variant::split2?2:v==Variant::split4?4:1;}
inline std::pair<size_t,size_t> bounds(size_t k,unsigned s,unsigned count) {
  size_t tiles=(k+255)/256;
  return {std::min(k,(tiles*s/count)*256),std::min(k,(tiles*(s+1)/count)*256)};
}
template<Type T> inline float lane_range(const uint8_t* w,const uint16_t* x,Type a,size_t begin,size_t end,unsigned lane) {
  float acc=0;
  for(size_t k=begin+lane*8;k<end;k+=256) {
    float values[8];
    if(k+8<=end)kopt::decode8<T>(w,k,values);
    else for(size_t j=0;j<end-k;++j)values[j]=element(T,w,k+j);
    #pragma unroll
    for(unsigned j=0;j<8;++j)if(k+j<end) {
      float input=a==Type::BF16?bits_float(uint32_t(x[k+j])<<16):half(x[k+j]);
      float product=values[j]*input;acc=acc+product;
    }
  }
  return acc;
}
inline float lane(Type t,const uint8_t* w,const uint16_t* x,Type a,size_t begin,size_t end,unsigned l) {
#define CASE(T) case Type::T:return lane_range<Type::T>(w,x,a,begin,end,l)
  switch(t){CASE(F32);CASE(F16);CASE(BF16);CASE(Q8_0);CASE(Q6_K);CASE(Q3_K);CASE(IQ3_XXS);CASE(IQ2_S);CASE(IQ3_S);CASE(IQ4_NL);}
#undef CASE
  return bits_float(0x7fc00000);
}
inline float row(Type t,const uint8_t* w,const uint16_t* x,Type a,size_t k,Variant v) {
  unsigned n=splits(v);float partial[4]{};
  for(unsigned s=0;s<n;++s) {
    auto [begin,end]=bounds(k,s,n);float sums[32]{};
    for(unsigned l=0;l<32;++l)sums[l]=lane(t,w,x,a,begin,end,l);
    for(unsigned width=1;width<32;width*=2)for(unsigned l=0;l<32;l+=width*2)sums[l]=sums[l]+sums[l+width];
    partial[s]=sums[0];
  }
  for(unsigned width=1;width<n;width*=2)for(unsigned s=0;s<n;s+=width*2)partial[s]=partial[s]+partial[s+width];
  return partial[0];
}
inline size_t stage_prefix(uintptr_t address,size_t n,unsigned bytes) {
  return std::min(n,(bytes-(address&(bytes-1)))&(bytes-1));
}
constexpr size_t stream_threads=32768;
inline uint32_t stream_word(size_t index,unsigned salt){return uint32_t(index)*1664525u+1013904223u+salt;}
inline uint64_t stream_sum(size_t words,size_t lane,unsigned salt) {
  uint64_t sum=0;
  for(size_t i=lane*4;i<words;i+=stream_threads*4)for(unsigned j=0;j<4;++j)sum+=stream_word(i+j,salt);
  return sum;
}
}
