#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#if defined(SYCL_LANGUAGE_VERSION)
#include <sycl/sycl.hpp>
#endif
#include "stage2/packet2/kernels/math.hpp"
#include <stdexcept>

// Original lab arithmetic. Old lane_dot/tree32/gemv_row remain untouched.
namespace iq3::kopt {
// Block scale half -> float. On the device, the hardware conversion is exact for every non-NaN half; NaN patterns keep
// the reference conversion (canonical quiet NaN), so the result equals half() for all 65536 inputs. The software
// version's subnormal loop made it a large share of expert decode (IQ2_S microbench 69.7 -> 43.6 us).
inline float half_scale(uint32_t h) {
#if defined(__SYCL_DEVICE_ONLY__)
  if(((h>>10)&31)!=31)return float(sycl::bit_cast<sycl::half>(uint16_t(h)));
#endif
  return half(h);
}
// A contiguous group of eight amortizes scale/sign/codebook decoding. All
// multiplication boundaries match packet2 decode; never factor FP expressions.
// k is a 32-bit column index (rows are far below 2^32 columns): 64-bit index math is emulated on the B70.
template<Type T> inline void decode8(const uint8_t* row,uint32_t k,float* v) {
  constexpr auto l=layout(T);
  if constexpr(T==Type::IQ2_S) {
    auto b=row+(k/256)*82;unsigned i=k%256,q=i/8;
    unsigned ix=b[2+q]|(((b[66+q/4]>>(2*(q%4)))&3)<<8);
    uint64_t grid=iq2_s_grid[ix];unsigned signs=b[34+q];
    unsigned sc=(b[74+i/32]>>(4*((i/16)%2)))&15;
    float scale=(half_scale(u16(b))*(0.5f+float(sc)))*0.25f;
    // The byte goes through uint32_t before the conversion: the same value (0..255), but a 64-bit integer to float
    // conversion is emulated on the B70 and was most of this decoder's cost (microbench 80 -> 34 us with the lean loop).
    for(unsigned j=0;j<8;++j)v[j]=(scale*float(uint32_t((grid>>(8*j))&255)))*float((signs>>j)&1?-1:1);
  } else if constexpr(T==Type::IQ3_S) {
    auto b=row+(k/256)*110;unsigned i=k%256,q=i/4;
    unsigned signs=b[74+i/8],sc=(b[106+i/64]>>(4*((i/32)%2)))&15;
    float scale=half_scale(u16(b))*float(1+2*sc);
    for(unsigned g=0;g<2;++g) {
      unsigned qi=q+g,ix=b[2+qi]|(((b[66+qi/8]>>(qi%8))&1)<<8);
      uint32_t grid=iq3_s_grid[ix];
      for(unsigned j=0;j<4;++j)v[g*4+j]=(scale*float((grid>>(8*j))&255))*float((signs>>(g*4+j))&1?-1:1);
    }
  } else if constexpr(T==Type::Q6_K) {
    auto b=row+(k/256)*210;unsigned i=k%256;
    float scale=half_scale(u16(b+208))*float(signed8(b[192+i/16]));
    for(unsigned j=0;j<8;++j) {
      unsigned n=i+j;
      int low=(b[(n/128)*64+n%64]>>(4*((n%128)/64)))&15;
      int high=(b[128+(n/128)*32+n%32]>>(2*((n%128)/32)))&3;
      v[j]=scale*float((low|(high<<4))-32);
    }
  } else if constexpr(T==Type::IQ4_NL || T==Type::Q8_0) {
    auto b=row+(k/32)*l.bytes;unsigned i=k%32;
    float scale=half_scale(u16(b));
    // IQ4_NL levels via iq4_level (register words; the integer levels, and so every value, are unchanged).
    if constexpr(T==Type::IQ4_NL) {
      // The 8 weights at k (k%8==0) are bytes b[2+(i&15)] .. +7 of the block, all low (i<16) or all high nibbles,
      // i.e. exactly levels[(b[2+(i+j)%16]>>(4*((i+j)/16)))&15]. Read them as two 32-bit words (aligned, or the
      // covering aligned words with the last two bytes as one 16-bit load), never a byte outside the 8 needed ones.
      const uint8_t* q=b+2+(i&15);const uintptr_t at=reinterpret_cast<uintptr_t>(q);
      if(i%8==0&&(at&1)==0) {
        // Branchless: two words from q rounded down to 4 bytes plus the 16-bit word at q+6 (inside the 8 bytes), then a
        // select on the alignment; the same 8 bytes, and lanes no longer diverge (microbench 54.5 -> 53.2 us).
        const bool odd=(at&2)!=0;const uint32_t* w=reinterpret_cast<const uint32_t*>(q-(at&2));const uint32_t a=w[0],c=w[1];
        const uint32_t tail=*reinterpret_cast<const uint16_t*>(q+6);
        const uint32_t lo=odd?(a>>16)|(c<<16):a,hi=odd?(c>>16)|(tail<<16):c;
        const unsigned shift=(i/16)*4;
        for(unsigned j=0;j<8;++j){const unsigned n=((((j<4?lo:hi)>>(8*(j&3)))&255)>>shift)&15;v[j]=scale*float(iq4_level(n));}
        return;
      }
    }
    for(unsigned j=0;j<8;++j) {
      if constexpr(T==Type::Q8_0)v[j]=scale*float(signed8(b[2+i+j]));
      else {const unsigned q=(b[2+(i+j)%16]>>(4*((i+j)/16)))&15;v[j]=scale*float(iq4_level(q));}
    }
  } else {
    for(unsigned j=0;j<8;++j)v[j]=element(T,row,k+j);
  }
}
template<Type T> inline float lane_dot(const uint8_t* row,const uint16_t* x,Type activation,size_t columns,unsigned lane,unsigned subgroup) {
  float acc=0;
  if(activation==Type::F32) {
    // Same arithmetic as the loop below for F32 activations: fixed-trip unrolled full chunks, 32-bit index.
    const float* xf=reinterpret_cast<const float*>(x);const uint32_t k32=uint32_t(columns),step=subgroup*8u;uint32_t k=lane*8u;
    for(;k+8u<=k32;k+=step) {
      float values[8];decode8<T>(row,k,values);
      #pragma unroll
      for(unsigned j=0;j<8;++j){float product=values[j]*xf[k+j];acc=acc+product;}
    }
    if(k<k32) {
      float values[8];for(uint32_t j=0;k+j<k32;++j)values[j]=element(T,row,k+j);
      for(uint32_t j=0;k+j<k32;++j){float product=values[j]*xf[k+j];acc=acc+product;}
    }
    return acc;
  }
  for(size_t k=size_t(lane)*8;k<columns;k+=size_t(subgroup)*8) {
    float values[8];
    if(k+8<=columns)decode8<T>(row,k,values);
    else for(size_t j=0;j<columns-k;++j)values[j]=element(T,row,k+j);
    for(unsigned j=0;j<8 && k+j<columns;++j) {
      // F32: exact-mode activations, x reinterpreted as float (already offset in float elements by the caller).
      float input=activation==Type::BF16?bits_float(uint32_t(x[k+j])<<16):activation==Type::F32?reinterpret_cast<const float*>(x)[k+j]:half(x[k+j]);
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
