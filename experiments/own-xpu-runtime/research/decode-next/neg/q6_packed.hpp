#pragma once
// OWNRT_DECODE_NEXT dense8 (lab 2026-10-26): Q6_K decode-row body with packed logical lanes, shared by the engine kernel
// (kernels.cpp MultiplyQ6Packed) and the CPU-device test. Work-item t (0..7) of a row owns logical lanes 4t..4t+3 of
// Multiply's mapping (lane l: columns 8l+256i), i.e. elements 32t..32t+31 of Q6_K block i. Their 32 low-nibble bytes
// (ql), 32 high-bit bytes (qh), two sub-scales and d are read once; each logical lane keeps decode8's values
// scale*float((low|high<<4)-32) with scale = half_scale(d)*float(signed8(sc)), product then add over its 8 columns,
// chunks in order. Requires K % 256 == 0 and a 4-byte aligned row start.
#include "stage2/packet6-kopt/reference.hpp"
#include <cstdint>
namespace iq3::kopt::q6p {
// 32 bytes at p (p is 2-byte aligned; odd2 says p % 4 == 2) as 8 little-endian words.
inline void load32(const uint8_t* p,bool odd2,uint32_t (&w)[8]){
  const uint32_t* a=reinterpret_cast<const uint32_t*>(p-(odd2?2:0));
  uint32_t v[9];
  #pragma unroll
  for(unsigned e=0;e<8;++e)v[e]=a[e];
  v[8]=odd2?uint32_t(*reinterpret_cast<const uint16_t*>(p+30)):0u;
  #pragma unroll
  for(unsigned e=0;e<8;++e)w[e]=odd2?(v[e]>>16)|(v[e+1]<<16):v[e];
}
// Accumulate one block (256 columns starting at x, already offset to the block) of one row into acc[4].
inline void block(const uint8_t* b,bool odd2,unsigned t,const float* xv,float (&acc)[4]){
  uint32_t ql[8],qh[8];
  load32(b+(t/4)*64+32*(t%2),odd2,ql);
  load32(b+128+(t/4)*32,odd2,qh);
  const uint32_t scw=*reinterpret_cast<const uint16_t*>(b+192+2*t);
  const float d=half_scale(*reinterpret_cast<const uint16_t*>(b+208));
  const unsigned ls=4*((t%4)/2),hs=2*(t%4);
  #pragma unroll
  for(unsigned j=0;j<4;++j){
    const float scale=d*float(signed8(uint8_t((scw>>(8*(j/2)))&255u)));
    #pragma unroll
    for(unsigned jj=0;jj<8;++jj){
      const unsigned e=8*j+jj;
      const uint32_t lb=(ql[e/4]>>(8*(e%4)))&255u,hb=(qh[e/4]>>(8*(e%4)))&255u;
      const int low=int((lb>>ls)&15u),high=int((hb>>hs)&3u);
      const float value=scale*float((low|(high<<4))-32);
      const float product=value*xv[e];acc[j]=acc[j]+product;
    }
  }
}
}
