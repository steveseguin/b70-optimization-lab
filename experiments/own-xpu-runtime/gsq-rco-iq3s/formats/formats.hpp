#pragma once
// Original CPU format adapter. External format definitions are reference data,
// never an execution dependency; see source-pins.json and README.md.
#include "../../stage2/packet2/kernels/math.hpp"
#include <array>
#include <limits>
#include <span>
#include <stdexcept>
namespace gsq {
struct Layout {size_t elements,bytes;};
inline Layout layout(uint32_t type) {
 switch(type){case 12:return {256,144};case 13:return {256,176};case 23:return {256,136};case 42:return {64,18};default:break;}
 const auto old=iq3::layout(static_cast<iq3::Type>(type));
 if(!old.elements)throw std::invalid_argument("unsupported GSQ scalar type");
 return {old.elements,old.bytes};
}
inline size_t row_bytes(uint32_t type,size_t columns){
 const auto f=layout(type);
 if(!columns||columns%f.elements||columns/f.elements>std::numeric_limits<size_t>::max()/f.bytes)throw std::invalid_argument("GSQ scalar row extent");
 return columns/f.elements*f.bytes;
}
inline float element_unchecked(uint32_t type,const uint8_t*b,size_t i){
 if(type==42){const unsigned code=(b[2+i/4]>>(2*(i%4)))&3;return float(int(code)-1)*iq3::half(iq3::u16(b));}
 if(type==12||type==13){
  const unsigned group=i/32;const auto*s=b+4;
  const unsigned scale=group<4?s[group]&63:(s[group+4]&15)|((s[group-4]>>6)<<4);
  const unsigned minimum=group<4?s[group+4]&63:(s[group+4]>>4)|((s[group]>>6)<<4);
  const unsigned low_offset=type==12?16:48;
  unsigned code=(b[low_offset+(i/64)*32+i%32]>>(4*((i/32)%2)))&15;
  if(type==13)code|=((b[16+i%32]>>group)&1)<<4;
  const float factor=iq3::half(iq3::u16(b))*float(scale);
  const float offset=iq3::half(iq3::u16(b+2))*float(minimum);
  const float product=factor*float(code);return product-offset;
 }
 if(type==23){
  // Same original field equations as packet10-kopt5/expanded.hpp::quant/scale,
  // applied directly to packed bytes; no expanded whole-bank allocation.
  constexpr int levels[]{-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
  const unsigned group=i/32;
  const unsigned scale=((b[4+group/2]>>(4*(group%2)))&15)|(((iq3::u16(b+2)>>(2*group))&3)<<4);
  const unsigned code=(b[8+group*16+i%16]>>(4*((i%32)/16)))&15;
  const float factor=iq3::half(iq3::u16(b))*float(int(scale)-32);
  return factor*float(levels[code]);
 }
 return iq3::decode(static_cast<iq3::Type>(type),b,uint32_t(i));
}
inline float element(uint32_t type,std::span<const uint8_t>row,size_t columns,size_t index){
 const auto f=layout(type);
 if(row.size()!=row_bytes(type,columns)||index>=columns)throw std::invalid_argument("GSQ scalar element bounds");
 return element_unchecked(type,row.data()+(index/f.elements)*f.bytes,index%f.elements);
}
inline void decode_row(uint32_t type,std::span<const uint8_t>row,std::span<float>out){
 const auto f=layout(type);
 if(row.size()!=row_bytes(type,out.size()))throw std::invalid_argument("GSQ scalar decode extent");
 for(size_t i=0;i<out.size();++i)out[i]=element_unchecked(type,row.data()+(i/f.elements)*f.bytes,i%f.elements);
}
inline float row_gemv(uint32_t type,std::span<const uint8_t>row,std::span<const uint16_t>x){
 const auto f=layout(type);
 if(row.size()!=row_bytes(type,x.size()))throw std::invalid_argument("GSQ scalar GEMV extent");
 std::array<float,32>sums{};
 for(size_t lane=0;lane<32;++lane)for(size_t k=lane;k<x.size();k+=32){
  const float weight=element_unchecked(type,row.data()+(k/f.elements)*f.bytes,k%f.elements);
  const float product=weight*iq3::bits_float(uint32_t(x[k])<<16);
  sums[lane]=sums[lane]+product;
 }
 // The existing own-runtime logical SG32 ordered adjacent tree, not a library
 // reduction. This defines this CPU path; selected device trees need own gates.
 return iq3::tree32(sums.data());
}
} // namespace gsq
