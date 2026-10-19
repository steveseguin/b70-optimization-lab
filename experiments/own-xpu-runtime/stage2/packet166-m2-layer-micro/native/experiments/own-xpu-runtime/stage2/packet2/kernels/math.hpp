#pragma once
#include <bit>
#include <cstddef>
#include <cstdint>
#include "grids.hpp"

// Original scalar equations from the lab's FORMAT.md, not ggml kernels.
// The generated tables are credited normative GGUF format data.
namespace iq3 {
enum class Type : uint32_t { F32=0,F16=1,Q8_0=8,Q3_K=11,Q6_K=14,
                            IQ3_XXS=18,IQ4_NL=20,IQ3_S=21,IQ2_S=22,BF16=30 };
struct Layout { uint32_t elements, bytes; };
inline constexpr Layout layout(Type t) {
  switch(t) {
    case Type::F32:return {1,4};
    case Type::F16:case Type::BF16:return {1,2};
    case Type::Q8_0:return {32,34}; case Type::Q3_K:case Type::IQ3_S:return {256,110};
    case Type::Q6_K:return {256,210}; case Type::IQ3_XXS:return {256,98};
    case Type::IQ4_NL:return {32,18}; case Type::IQ2_S:return {256,82};
  }
  return {0,0}; // admission rejects unknown types before submission
}
inline uint32_t u16(const uint8_t* b) {return uint32_t(b[0]) | uint32_t(b[1])<<8;}
inline uint32_t u32(const uint8_t* b) {return u16(b) | u16(b+2)<<16;}
inline int signed8(uint8_t b) {return b<128?int(b):int(b)-256;}
inline float bits_float(uint32_t b) {return std::bit_cast<float>(b);}
inline float half(uint32_t h) {
  uint32_t sign=(h&0x8000)<<16, e=(h>>10)&31, m=h&1023;
  if(e==31) return bits_float(sign|0x7f800000|(m?0x400000:0)); // Python struct canonical NaN
  if(e) return bits_float(sign|((e+112)<<23)|(m<<13));
  if(!m) return bits_float(sign);
  int exponent=-14;
  while(!(m&1024)) {m<<=1; --exponent;}
  return bits_float(sign|(uint32_t(exponent+127)<<23)|((m&1023)<<13));
}
inline uint16_t bf16_bits(float f) {
  uint32_t b=std::bit_cast<uint32_t>(f);
  if((b&0x7fffffff)>0x7f800000) return uint16_t((b>>16)|0x40);
  return uint16_t((b+0x7fff+((b>>16)&1))>>16);
}
inline uint32_t round_shift(uint32_t m,unsigned shift) {
  if(shift>31) return 0;
  uint32_t q=m>>shift, tail=m&((uint32_t(1)<<shift)-1), tie=uint32_t(1)<<(shift-1);
  return q+(tail>tie || (tail==tie && (q&1)));
}
inline uint16_t half_bits(float f) {
  uint32_t b=std::bit_cast<uint32_t>(f),sign=(b>>16)&0x8000,m=b&0x7fffff;
  int e=int((b>>23)&255)-127;
  if(e==128) return uint16_t(sign|0x7c00|(m?0x200:0));
  if(e>15) return uint16_t(sign|0x7c00);
  if(e< -25) return uint16_t(sign);
  if(e< -14) return uint16_t(sign|round_shift(m|0x800000,unsigned(-e-1)));
  uint32_t value=(uint32_t(e+15)<<10)+round_shift(m,13);
  return uint16_t(sign|value);
}
inline float decode(Type t,const uint8_t* b,uint32_t i) {
  // Build contract: no FMA contraction, reassociation, fast math or FTZ.
  if(t==Type::F32) return bits_float(u32(b));
  if(t==Type::F16) return half(u16(b));
  if(t==Type::BF16) {
    auto bits=u16(b)<<16;
    if((bits&0x7fffffff)>0x7f800000) bits|=0x400000; // Python float round trip
    return bits_float(bits);
  }
  if(t==Type::Q8_0) return half(u16(b))*float(signed8(b[2+i]));
  if(t==Type::Q3_K) {
    auto g=i/16;
    int sc=((b[96+g%8]>>(4*(g/8)))&15)|(((b[104+g%4]>>(2*(g/4)))&3)<<4);
    int q=((b[32+(i/128)*32+i%32]>>(2*((i%128)/32)))&3)-4*(1-((b[i%32]>>(i/32))&1));
    return (half(u16(b+108))*float(sc-32))*float(q);
  }
  if(t==Type::Q6_K) {
    int low=(b[(i/128)*64+i%64]>>(4*((i%128)/64)))&15;
    int high=(b[128+(i/128)*32+i%32]>>(2*((i%128)/32)))&3;
    return (half(u16(b+208))*float(signed8(b[192+i/16])))*float((low|(high<<4))-32);
  }
  if(t==Type::IQ4_NL) {
    constexpr int levels[]={-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
    return half(u16(b))*float(levels[(b[2+i%16]>>(4*(i/16)))&15]);
  }
  if(t==Type::IQ3_S) {
    auto q=i/4; auto ix=b[2+q]|(((b[66+q/8]>>(q%8))&1)<<8);
    auto mag=(iq3_s_grid[ix]>>(8*(i%4)))&255;
    int sign=(b[74+i/8]>>(i%8))&1?-1:1;
    auto sc=(b[106+i/64]>>(4*((i/32)%2)))&15;
    return ((half(u16(b))*float(1+2*sc))*float(mag))*float(sign);
  }
  if(t==Type::IQ2_S) {
    auto q=i/8; auto ix=b[2+q]|(((b[66+q/4]>>(2*(q%4)))&3)<<8);
    auto mag=(iq2_s_grid[ix]>>(8*(i%8)))&255;
    int sign=(b[34+q]>>(i%8))&1?-1:1;
    auto sc=(b[74+i/32]>>(4*((i/16)%2)))&15;
    return (((half(u16(b))*(0.5f+float(sc)))*0.25f)*float(mag))*float(sign);
  }
  if(t==Type::IQ3_XXS) {
    auto word=u32(b+66+4*(i/32)),code=(word>>(7*((i%32)/8)))&127;
    auto mask=code|((std::popcount(code)%2)<<7);
    int sign=(mask>>(i%8))&1?-1:1;
    auto mag=(iq3_grid[b[2+i/4]]>>(8*(i%4)))&255;
    return (((half(u16(b))*(0.5f+float(word>>28)))*0.5f)*float(mag))*float(sign);
  }
  return bits_float(0x7fc00000);
}
inline float element(Type t,const uint8_t* row,size_t i) {
  auto l=layout(t);return decode(t,row+(i/l.elements)*l.bytes,i%l.elements);
}
// 32 logical lanes independent of physical subgroup (16 or 32).
// lane l: columns l,l+32,...; ascending products/adds, then ascending
// adjacent-pair tree. Device and CPU call THESE functions, no library reduce.
inline float lane_dot(Type t,const uint8_t* row,const uint16_t* x,Type activation,
                      size_t columns,unsigned lane) {
  float sum=0;
  for(size_t k=lane;k<columns;k+=32) {
    float v=activation==Type::BF16?bits_float(uint32_t(x[k])<<16):half(x[k]);
    float product=element(t,row,k)*v;
    sum=sum+product;
  }
  return sum;
}
inline float tree32(float* s) {
  for(unsigned width=1;width<32;width*=2)
    for(unsigned i=0;i<32;i+=2*width) s[i]=s[i]+s[i+width];
  return s[0];
}
inline float gemv_row(Type t,const uint8_t* row,const uint16_t* x,Type activation,size_t columns) {
  float lanes[32];for(unsigned l=0;l<32;++l) lanes[l]=lane_dot(t,row,x,activation,columns,l);
  return tree32(lanes);
}
inline uint16_t output_bits(float f,Type output) {return output==Type::BF16?bf16_bits(f):half_bits(f);}
struct Route {uint32_t expert_id,row_begin,row_count;};
inline bool valid_route(Route r,uint32_t experts,uint32_t rows,uint32_t span) {
  return r.expert_id<experts && r.row_begin<=rows && r.row_count<=rows-r.row_begin && r.row_count<=span;
}
}
