#pragma once
// Scratch IQ3_XXS representation; no engine source/default changes.
// 98 packed bytes -> 266 bytes: original half, 8 scale nibbles, 256 signed codes.
// Keeps the exact original weight expression and lane/reduction order.
#include <bit>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>
#include "stage2/packet2/kernels/math.hpp"

namespace iq3_predecoded {
inline constexpr uint32_t packed_bytes=98, cached_bytes=266, block_elements=256;
inline size_t row_bytes(uint32_t columns) {
 if (!columns || columns%block_elements) throw std::invalid_argument("IQ3_XXS whole block columns required");
 return size_t(columns/block_elements)*cached_bytes;
}
inline void expand_block(const uint8_t* src,uint8_t* dst) {
 dst[0]=src[0];dst[1]=src[1];
 for (unsigned group=0;group<8;++group) {
  const auto word=iq3::u32(src+66+4*group);dst[2+group]=uint8_t(word>>28);
  for(unsigned lane=0;lane<32;++lane) {
   const auto code=(word>>(7*(lane/8)))&127;
   const auto mask=code|((std::popcount(code)%2)<<7);
   const auto magnitude=(iq3::iq3_grid[src[2+group*8+lane/4]]>>(8*(lane%4)))&255;
   if (!magnitude || magnitude>127) throw std::invalid_argument("signed code range");
   const int value=((mask>>(lane%8))&1)?-int(magnitude):int(magnitude);
   dst[10+group*32+lane]=uint8_t(value);
  }
 }
}
inline std::vector<uint8_t> expand(const uint8_t* src,size_t bytes,uint32_t columns) {
 const size_t old_row=size_t(columns/block_elements)*packed_bytes;
 const size_t new_row=row_bytes(columns);
 if (!bytes || bytes%old_row || bytes/old_row>std::numeric_limits<size_t>::max()/new_row)
  throw std::invalid_argument("IQ3_XXS expanded extent");
 std::vector<uint8_t> result((bytes/old_row)*new_row);
 for(size_t block=0;block<bytes/packed_bytes;++block)
  expand_block(src+block*packed_bytes,result.data()+block*cached_bytes);
 return result;
}
inline float element(const uint8_t* block,float d,unsigned group,unsigned lane) {
 const int code=iq3::signed8(block[10+group*32+lane]);
 const int magnitude=code<0?-code:code, sign=code<0?-1:1;
 // Do not fold sign into scale, reassociate multiplication, use FMA, or alter tree.
 return (((d*(0.5f+float(block[2+group])))*0.5f)*float(magnitude))*float(sign);
}
inline float packed_element(const uint8_t* block,float d,unsigned group,unsigned lane) {
 const auto word=iq3::u32(block+66+4*group),code=(word>>(7*(lane/8)))&127;
 const auto mask=code|((std::popcount(code)%2)<<7);
 const int sign=(mask>>(lane%8))&1?-1:1;
 const auto magnitude=(iq3::iq3_grid[block[2+group*8+lane/4]]>>(8*(lane%4)))&255;
 return (((d*(0.5f+float(word>>28)))*0.5f)*float(magnitude))*float(sign);
}
// Matches the active R4 kernel's aligned 16-bit loads, so the microbenchmark
// baseline does not regress to the older byte-load decoder.
inline float packed_element_words(const uint8_t* block,float d,unsigned group,unsigned lane) {
 const auto* halves=reinterpret_cast<const uint16_t*>(block+66+4*group);
 const uint32_t word=uint32_t(halves[0])|uint32_t(halves[1])<<16;
 const auto code=(word>>(7*(lane/8)))&127;
 const auto mask=code|((std::popcount(code)%2)<<7);
 const int sign=(mask>>(lane%8))&1?-1:1;
 const auto index=(uint32_t(reinterpret_cast<const uint16_t*>(block+2+group*8)[lane/8])>>(8*((lane/4)%2)))&255;
 const auto magnitude=(iq3::iq3_grid[index]>>(8*(lane%4)))&255;
 return (((d*(0.5f+float(word>>28)))*0.5f)*float(magnitude))*float(sign);
}
template<bool Cached>
inline float host_row(const uint8_t* weights,const float* x,uint32_t columns) {
 float lanes[32]{};
 for(unsigned lane=0;lane<32;++lane) for(uint32_t block=0;block<columns/256;++block) {
  const auto* p=weights+size_t(block)*(Cached?cached_bytes:packed_bytes);
  const float d=iq3::half(iq3::u16(p));
  for(unsigned group=0;group<8;++group) {
   const float w=Cached?element(p,d,group,lane):packed_element(p,d,group,lane);
   const float product=w*x[block*256+group*32+lane];lanes[lane]=lanes[lane]+product;
  }
 }
 for(unsigned width=1;width<32;width*=2)
  for(unsigned lane=0;lane<32;lane+=2*width) lanes[lane]=lanes[lane]+lanes[lane+width];
 return lanes[0];
}
}
