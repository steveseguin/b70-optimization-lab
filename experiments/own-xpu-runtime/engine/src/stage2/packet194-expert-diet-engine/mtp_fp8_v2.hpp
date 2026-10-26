#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
// OWNRT_DRAFT_EXPERTS_V2=1 (rank0-lab 2026-10-26, default off): FP8 draft expert rows (mtp_kernels.cpp lane<K,2>) with the
// same per-lane sequence: lane l walks the 8-column chunks l*8, l*8+256, ... in order and, for each column k of a chunk,
// value = bits_float(scale word of k/128) * fp8 value of the code, product = value * bf16(x[k]), sum = sum + product;
// then the same adjacent-pair subgroup tree, NaN for an invalid route, the same status writes. Changed: the chunk's 8
// codes are two aligned 32-bit loads, its scale word one aligned 32-bit load (the 8 columns share k/128), its 8 inputs
// one 16-byte load shared by both rows of a pair.
#include "stage2/packet2/kernels/math.hpp"
#include "stage2/packet194-expert-diet-engine/p28/expert.hpp"
#include <sycl/sycl.hpp>
#include <cstdint>
namespace mtp36::fp8v2 {
// Exact E4M3 (bias 7) decode by bit construction: mtp_kernels.cpp fp8_value, unchanged.
inline float value(uint8_t b){
 uint32_t e=(b>>3)&15,m=b&7;
 float x=e?iq3::bits_float(((e+120)<<23)|(m<<20)):float(m)*0x1p-9f;
 return b&128?-x:x;
}
struct Rows {const uint8_t *w,*peer;const uint16_t *x;uint16_t *y,*py;const iq3::Route *route;uint32_t *status,*ps;unsigned rows,batch,experts;};
template<unsigned K,bool Pair> inline void rows(const Rows& b,size_t n,sycl::nd_item<1> it){
 static_assert(K%128==0);constexpr size_t rb=K+4*(K/128);
 auto sg=it.get_sub_group();const unsigned l=sg.get_local_linear_id();const size_t i=it.get_global_linear_id()/32;if(i>=n)return;
 const unsigned slot=unsigned(i/b.rows),row=unsigned(i%b.rows);
 auto r=b.route?b.route[slot]:iq3::Route{0,0,b.rows};const bool valid=iq3::valid_route(r,b.experts,b.rows,b.rows)&&row<r.row_count;float sum=0,peer=0;
 if(valid){const size_t off=(size_t(r.expert_id)*b.rows+r.row_begin+row)*rb;const uint8_t* w=b.w+off;const uint8_t* pw=Pair?b.peer+off:w;const uint16_t* x=b.x+(Pair?0:size_t(slot)*K);
  for(unsigned tile=l*8;tile<K;tile+=256){
   const sycl::vec<uint16_t,8> xb=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(x+tile);
   const uint32_t c0=*reinterpret_cast<const uint32_t*>(w+tile),c1=*reinterpret_cast<const uint32_t*>(w+tile+4);
   const float scale=iq3::bits_float(*reinterpret_cast<const uint32_t*>(w+K+(tile/128)*4));
   uint32_t p0=0,p1=0;float pscale=0;
   if constexpr(Pair){p0=*reinterpret_cast<const uint32_t*>(pw+tile);p1=*reinterpret_cast<const uint32_t*>(pw+tile+4);pscale=iq3::bits_float(*reinterpret_cast<const uint32_t*>(pw+K+(tile/128)*4));}
   #pragma unroll
   for(unsigned j=0;j<8;++j){const float input=iq3::bits_float(uint32_t(xb[j])<<16);
    {const float v=scale*value(uint8_t((j<4?c0:c1)>>(8*(j&3))));const float product=v*input;sum=sum+product;}
    if constexpr(Pair){const float v=pscale*value(uint8_t((j<4?p0:p1)>>(8*(j&3))));const float product=v*input;peer=peer+product;}}
  }}
 for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,sum,(l+width)%32);float pr=sycl::select_from_group(sg,peer,(l+width)%32);if(l%(2*width)==0){sum=sum+rhs;peer=peer+pr;}}
 if(l==0){b.y[i]=iq3::bf16_bits(valid?sum:iq3::bits_float(0x7fc00000));if constexpr(Pair)b.py[i]=iq3::bf16_bits(valid?peer:iq3::bits_float(0x7fc00000));if(row==0&&b.route){b.status[slot]=!valid;if constexpr(Pair)b.ps[slot]=!valid;}}
}
inline bool enabled(){static const bool on=[]{const char* e=std::getenv("OWNRT_DRAFT_EXPERTS_V2");return e&&e[0]=='1';}();return on;}
}
