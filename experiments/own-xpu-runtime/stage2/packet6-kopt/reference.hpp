#pragma once
#include "../packet2/kernels/math.hpp"
#include <stdexcept>

// Original lab arithmetic. Old lane_dot/tree32/gemv_row remain untouched.
namespace iq3::kopt {
// A contiguous group of eight amortizes scale/sign/codebook decoding. All
// multiplication boundaries match packet2 decode; never factor FP expressions.
template<Type T> inline void decode8(const uint8_t* row,size_t k,float* v) {
  constexpr auto l=layout(T);
  if constexpr(T==Type::IQ2_S) {
    auto b=row+(k/256)*82;unsigned i=k%256,q=i/8;
    unsigned ix=b[2+q]|(((b[66+q/4]>>(2*(q%4)))&3)<<8);
    uint64_t grid=iq2_s_grid[ix];unsigned signs=b[34+q];
    unsigned sc=(b[74+i/32]>>(4*((i/16)%2)))&15;
    float scale=(half(u16(b))*(0.5f+float(sc)))*0.25f;
    for(unsigned j=0;j<8;++j)v[j]=(scale*float((grid>>(8*j))&255))*float((signs>>j)&1?-1:1);
  } else if constexpr(T==Type::IQ3_S) {
    auto b=row+(k/256)*110;unsigned i=k%256,q=i/4;
    unsigned signs=b[74+i/8],sc=(b[106+i/64]>>(4*((i/32)%2)))&15;
    float scale=half(u16(b))*float(1+2*sc);
    for(unsigned g=0;g<2;++g) {
      unsigned qi=q+g,ix=b[2+qi]|(((b[66+qi/8]>>(qi%8))&1)<<8);
      uint32_t grid=iq3_s_grid[ix];
      for(unsigned j=0;j<4;++j)v[g*4+j]=(scale*float((grid>>(8*j))&255))*float((signs>>(g*4+j))&1?-1:1);
    }
  } else if constexpr(T==Type::Q6_K) {
    auto b=row+(k/256)*210;unsigned i=k%256;
    float scale=half(u16(b+208))*float(signed8(b[192+i/16]));
    for(unsigned j=0;j<8;++j) {
      unsigned n=i+j;
      int low=(b[(n/128)*64+n%64]>>(4*((n%128)/64)))&15;
      int high=(b[128+(n/128)*32+n%32]>>(2*((n%128)/32)))&3;
      v[j]=scale*float((low|(high<<4))-32);
    }
  } else if constexpr(T==Type::IQ4_NL || T==Type::Q8_0) {
    auto b=row+(k/32)*l.bytes;unsigned i=k%32;
    float scale=half(u16(b));
    constexpr int levels[]={-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
    for(unsigned j=0;j<8;++j) {
      if constexpr(T==Type::Q8_0)v[j]=scale*float(signed8(b[2+i+j]));
      else v[j]=scale*float(levels[(b[2+(i+j)%16]>>(4*((i+j)/16)))&15]);
    }
  } else {
    for(unsigned j=0;j<8;++j)v[j]=element(T,row,k+j);
  }
}
template<Type T> inline float lane_dot(const uint8_t* row,const uint16_t* x,Type activation,size_t columns,unsigned lane,unsigned subgroup) {
  float acc=0;
  for(size_t k=size_t(lane)*8;k<columns;k+=size_t(subgroup)*8) {
    float values[8];
    if(k+8<=columns)decode8<T>(row,k,values);
    else for(size_t j=0;j<columns-k;++j)values[j]=element(T,row,k+j);
    for(unsigned j=0;j<8 && k+j<columns;++j) {
      float input=activation==Type::BF16?bits_float(uint32_t(x[k+j])<<16):half(x[k+j]);
      float product=values[j]*input;acc=acc+product;
    }
  }
  return acc;
}
template<Type T> inline float row_t(const uint8_t* row,const uint16_t* x,Type a,size_t k,unsigned sg) {
  float sums[32];for(unsigned l=0;l<sg;++l)sums[l]=lane_dot<T>(row,x,a,k,l,sg);
  for(unsigned width=1;width<sg;width*=2)
    for(unsigned l=0;l<sg;l+=2*width)sums[l]=sums[l]+sums[l+width];
  return sums[0];
}
inline float gemv_row(Type t,const uint8_t* row,const uint16_t* x,Type a,size_t k,unsigned sg) {
  if(sg!=16 && sg!=32)throw std::invalid_argument("kopt subgroup");
#define KOPT_CASE(T) case Type::T:return row_t<Type::T>(row,x,a,k,sg)
  switch(t) {
    KOPT_CASE(F32);KOPT_CASE(F16);KOPT_CASE(BF16);KOPT_CASE(Q8_0);KOPT_CASE(Q6_K);
    KOPT_CASE(Q3_K);KOPT_CASE(IQ3_XXS);KOPT_CASE(IQ2_S);KOPT_CASE(IQ3_S);KOPT_CASE(IQ4_NL);
  }
#undef KOPT_CASE
  throw std::invalid_argument("kopt type");
}
}
