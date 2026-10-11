#pragma once
#include "../packet8-kopt3/decode.hpp"
#include <array>
namespace iq3::kopt6 {
enum class Variant { baseline, registers, slm_pair, packed_pipeline };
inline constexpr const char* names[]={"experts_sg32","register_grid","slm_pair","packed_pipeline"};
inline Variant variant(const std::string& s) {
 for(unsigned i=0;i<4;++i)if(s==names[i])return Variant(i);
 throw std::invalid_argument("unknown round6 variant");
}
// Packed magnitude octet; two int32 words, one sign byte and exact FP32 scale.
// Float8 is std::array on CPU and sycl::float8 in the device specialization.
template<class Float8> struct Octet {uint32_t lo,hi,sign;float scale;bool exceptional;Float8 x;};
template<Type T,class Float8,class Tables,class Share>
inline Octet<Float8> fetch(const uint8_t* w,const uint16_t* x,Type a,size_t k,Tables tables,Share share) {
 static_assert(T==Type::IQ2_S || T==Type::IQ3_S);
 Octet<Float8> v{};const auto b=w+(k/256)*layout(T).bytes;unsigned lane=(k%256)/8;
 #pragma unroll
 for(unsigned j=0;j<8;++j)v.x[j]=a==Type::BF16?bits_float(uint32_t(x[k+j])<<16):half(x[k+j]);
 float d=share(0,[&](unsigned){return half(u16(b));});
 v.exceptional=(std::bit_cast<uint32_t>(d)&0x7f800000)==0x7f800000;
 if constexpr(T==Type::IQ2_S) {
  v.scale=share(lane/2*2,[&](unsigned){return (d*(0.5f+float((b[74+lane/4]>>(4*((lane/2)%2)))&15)))*0.25f;});
  unsigned ix=b[2+lane]|(((b[66+lane/4]>>(2*(lane%4)))&3)<<8);
  auto grid=tables.iq2(ix);v.lo=uint32_t(grid);v.hi=uint32_t(grid>>32);v.sign=b[34+lane];
 } else {
  v.scale=share(lane/4*4,[&](unsigned){return d*float(1+2*((b[106+lane/8]>>(4*((lane/4)%2)))&15));});
  unsigned q=lane*2,hi=b[66+q/8];
  v.lo=tables.iq3s(b[2+q]|(((hi>>(q%8))&1)<<8));
  v.hi=tables.iq3s(b[3+q]|(((hi>>((q+1)%8))&1)<<8));v.sign=b[74+lane];
 }
 return v;
}
template<Type T,class Float8> inline float consume(const uint8_t* w,size_t k,const Octet<Float8>& v,float sum) {
 #pragma unroll
 for(unsigned j=0;j<8;++j) {
  int mag=int(((j<4?v.lo:v.hi)>>(8*(j%4)))&255);
  int q=(v.sign>>j)&1?-mag:mag;
  float weight=v.exceptional?element(T,w,k+j):v.scale*float(q);
  float product=weight*v.x[j];sum=sum+product; // separate rounding, NOT FMA
 }
 return sum;
}
template<Type T,Variant V,class Float8=std::array<float,8>,class Tables,class Share>
inline float dot(const uint8_t* w,const uint16_t* x,Type a,size_t begin,size_t end,unsigned lane,Tables tables,Share share) {
 if constexpr(T==Type::IQ4_NL || V==Variant::baseline || V==Variant::registers)
  return kopt3::dot<T>(w,x,a,begin,end,lane,tables,share);
 else {
  float sum=0;if(begin==end)return sum;
  if constexpr(V==Variant::slm_pair) {
   for(size_t tile=begin;tile<end;tile+=512) {
    size_t k=tile+lane*8;auto first=fetch<T,Float8>(w,x,a,k,tables,share);
    if(tile+256<end) {
     auto second=fetch<T,Float8>(w,x,a,k+256,tables,share);
     sum=consume<T>(w,k,first,sum);sum=consume<T>(w,k+256,second,sum);
    } else sum=consume<T>(w,k,first,sum);
   }
  } else {
   size_t k=begin+lane*8;auto current=fetch<T,Float8>(w,x,a,k,tables,share);
   for(size_t tile=begin+256;tile<end;tile+=256) {
    auto next=fetch<T,Float8>(w,x,a,tile+lane*8,tables,share);
    sum=consume<T>(w,k,current,sum);current=next;k=tile+lane*8;
   }
   sum=consume<T>(w,k,current,sum);
  }
  return sum;
 }
}
// CPU scheduling mirror, checked against packet9/scalar independent oracle.
inline float candidate_row(Type t,const uint8_t* w,const uint16_t* x,Type a,size_t k,unsigned split,Variant v) {
 float parts[4]{};
 for(unsigned s=0;s<split;++s) {
  auto b=kopt2::bounds(k,s,split);float lanes[32]{};
  for(unsigned lane=0;lane<32;++lane) {
#define RUN(T,V) dot<Type::T,Variant::V>(w,x,a,b.first,b.second,lane,kopt3::ConstantTables{},kopt3::HostShare{})
#define TYPE(T) case Type::T: switch(v){case Variant::baseline:lanes[lane]=RUN(T,baseline);break;case Variant::registers:lanes[lane]=RUN(T,registers);break;case Variant::slm_pair:lanes[lane]=RUN(T,slm_pair);break;case Variant::packed_pipeline:lanes[lane]=RUN(T,packed_pipeline);break;}break
   switch(t){TYPE(IQ2_S);TYPE(IQ3_S);TYPE(IQ4_NL);default:throw std::invalid_argument("expert type");}
#undef TYPE
#undef RUN
  }
  for(unsigned stride=1;stride<32;stride*=2)for(unsigned l=0;l<32;l+=2*stride)lanes[l]=lanes[l]+lanes[l+stride];
  parts[s]=lanes[0];
 }
 return split==1?parts[0]:(parts[0]+parts[1])+(parts[2]+parts[3]);
}
}
