#pragma once
#include "../../packet8-kopt3/decode.hpp"
#include <array>
#include <stdexcept>

namespace p28 {
using iq3::Type;
// Compile-time translation of credited normative FORMAT data. Wide words occur
// only during constant evaluation: device accessors below perform byte loads.
template<class Word, size_t N>
consteval auto byte_grid(const Word (&words)[N]) {
 std::array<uint8_t,N*sizeof(Word)> out{};
 for(size_t i=0;i<N;++i)for(unsigned j=0;j<sizeof(Word);++j)
  out[i*sizeof(Word)+j]=uint8_t(words[i]>>(8*j));
 return out;
}
inline constexpr auto iq2_bytes=byte_grid(iq3::iq2_s_grid);
inline constexpr auto iq3s_bytes=byte_grid(iq3::iq3_s_grid);
inline constexpr auto iq3xxs_bytes=byte_grid(iq3::iq3_grid);
inline constexpr std::array<int8_t,16> iq4_bytes={-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
struct ExpertByteTables {
 uint8_t iq2(unsigned entry,unsigned byte)const{return iq2_bytes[entry*8+byte];}
 uint8_t iq3s(unsigned entry,unsigned byte)const{return iq3s_bytes[entry*4+byte];}
 uint8_t iq3(unsigned entry,unsigned byte)const{return iq3xxs_bytes[entry*4+byte];}
 int8_t iq4(unsigned entry)const{return iq4_bytes[entry];}
};
static_assert(sizeof(ExpertByteTables)<=1);
inline constexpr bool expert_format(Type t) {
 return t==Type::IQ2_S || t==Type::IQ3_S || t==Type::IQ3_XXS || t==Type::IQ4_NL;
}
inline void validate_expert_range(Type t,unsigned k,unsigned begin,unsigned end,unsigned lane) {
 if(!expert_format(t) || !k || k>17408 || k%iq3::layout(t).elements || begin%256 || begin>end || end>k || (end!=k && end%256) || lane>=32)
  throw std::invalid_argument("packet28 expert shape/range/lane");
}
// All admitted rows are complete format blocks. Tiles and split boundaries are
// multiples of 256, lanes begin at 8*l, and scale groups are 16 or 32, both
// divisible by 8. Consequently no active lane tile straddles a scale group.
// IQ4 K=640 has 16 active lanes in its final tile, never a partial 8-weight lane.
template<Type T,bool Shared,class Tables,class Share>
inline void expert_decode8(const uint8_t* row,unsigned k,float (&values)[8],Tables tables,Share share) {
 using namespace iq3;
 static_assert(expert_format(T));
 constexpr unsigned block=layout(T).elements, bytes=layout(T).bytes;
 const uint8_t* b=row+(k/block)*bytes;
 const unsigned i=k%block,lane=(k%256)/8;
 float d;
 if constexpr(Shared) d=share(block==32?(lane/4)*4:0,[=](unsigned){return half(u16(b));});
 else d=half(u16(b));
 float scale=d;unsigned signs=0,index0=0,index1=0;
 if constexpr(T==Type::IQ2_S) {
  const unsigned q=i/8;
  index0=b[2+q]|(((b[66+q/4]>>(2*(q%4)))&3)<<8);
  signs=b[34+q];
  auto scale_fn=[=](unsigned){return (d*(0.5f+float((b[74+i/32]>>(4*((i/16)%2)))&15)))*0.25f;};
  if constexpr(Shared)scale=share(lane/2*2,scale_fn);else scale=scale_fn(lane);
 } else if constexpr(T==Type::IQ3_S) {
  signs=b[74+i/8];unsigned q=i/4;
  index0=b[2+q]|(((b[66+q/8]>>(q%8))&1)<<8);++q;
  index1=b[2+q]|(((b[66+q/8]>>(q%8))&1)<<8);
  auto scale_fn=[=](unsigned){return d*float(1+2*((b[106+i/64]>>(4*((i/32)%2)))&15));};
  if constexpr(Shared)scale=share(lane/4*4,scale_fn);else scale=scale_fn(lane);
 } else if constexpr(T==Type::IQ3_XXS) {
  unsigned word;
  if constexpr(Shared)word=share(lane/4*4,[=](unsigned){return u32(b+66+4*(i/32));});
  else word=u32(b+66+4*(i/32));
  auto scale_fn=[=](unsigned){return (d*(0.5f+float(word>>28)))*0.5f;};
  if constexpr(Shared)scale=share(lane/4*4,scale_fn);else scale=scale_fn(lane);
  unsigned code=(word>>(7*((i%32)/8)))&127;
  signs=code|((std::popcount(code)%2)<<7);
  index0=b[2+i/4];index1=b[2+i/4+1];
 }
 // Current decode8 tests NaN scale for every weight and recomputes element()
 // for infinite block scales. Hoisting both tests retains its exact equations.
 const bool exceptional=((std::bit_cast<uint32_t>(d)&0x7fffffff)>=0x7f800000) ||
                        ((std::bit_cast<uint32_t>(scale)&0x7fffffff)>0x7f800000);
 if constexpr(T==Type::IQ4_NL) {
  // The scalar fallback is the identical expression even for NaN/inf d.
  for(unsigned j=0;j<8;++j) {
   unsigned n=i+j;
   const uint8_t code=b[2+n%16];
   values[j]=scale*float(tables.iq4((code>>(4*(n/16)))&15));
  }
 } else {
  if(exceptional) {
   // Keep original magnitude-then-sign rounding/order; no sign folding for NaN.
   for(unsigned j=0;j<8;++j) {
    unsigned mag;
    if constexpr(T==Type::IQ2_S)mag=tables.iq2(index0,j);
    else if constexpr(T==Type::IQ3_S)mag=tables.iq3s(j<4?index0:index1,j%4);
    else mag=tables.iq3(j<4?index0:index1,j%4);
    values[j]=(scale*float(mag))*float((signs>>j)&1?-1:1);
   }
  } else {
   for(unsigned j=0;j<8;++j) {
    unsigned mag;
    if constexpr(T==Type::IQ2_S)mag=tables.iq2(index0,j);
    else if constexpr(T==Type::IQ3_S)mag=tables.iq3s(j<4?index0:index1,j%4);
    else mag=tables.iq3(j<4?index0:index1,j%4);
    const int q=(signs>>j)&1?-int(mag):int(mag);
    values[j]=scale*float(q);
   }
  }
 }
}
template<Type T,unsigned K,bool Shared,bool Paired,Type Activation=Type::BF16,class Tables,class Share>
inline std::array<float,2> expert_lane(const uint8_t* w,const uint8_t* peer,const uint16_t* x,
 unsigned begin,unsigned end,unsigned lane,Tables tables,Share share) {
 using namespace iq3;
 static_assert(K && K<=17408 && K%layout(T).elements==0);
 static_assert(Activation==Type::BF16 || Activation==Type::F16);
 std::array<float,2> sum{};
 for(unsigned tile=begin;tile<end;tile+=256) {
  unsigned k=tile+lane*8;
  float values[8]{},other[8]{};
  // Inactive lanes still execute all shared operations on a safe packed block.
  expert_decode8<T,Shared>(w,k<end?k:tile,values,tables,share);
  if constexpr(Paired)expert_decode8<T,Shared>(peer,k<end?k:tile,other,tables,share);
  for(unsigned j=0;j<8;++j)if(k+j<end) {
   const float input=Activation==Type::BF16?bits_float(uint32_t(x[k+j])<<16):half(x[k+j]);
   const float product=values[j]*input;sum[0]=sum[0]+product;
   if constexpr(Paired){const float other_product=other[j]*input;sum[1]=sum[1]+other_product;}
  }
 }
 return sum;
}
} // namespace p28
