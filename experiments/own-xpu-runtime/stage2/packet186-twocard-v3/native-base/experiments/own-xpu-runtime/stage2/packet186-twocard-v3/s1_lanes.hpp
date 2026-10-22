#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet186-twocard-v3/kernel_guard.hpp"
#pragma once
// Packet183 S1 (packet177 PLAN section 5, "metadata-scale dense lane").
//
// Every expanded Q6_K row is: K int8 codes | K/16 FP32 scale words | per 256
// weights the retained original 18 bytes (fp16 d, then 16 int8 sub-scales)
// (packet10-kopt5 expanded.hpp, row_bytes = K + 4K/16 + 18K/256). The loader
// wrote each scale word as the single FP32 product half(d)*float(signed8(sc)).
// The production lanes read the 64 bytes of scale words per 256 weights; these
// lanes read the 18 retained bytes and recompute that same product.
//
// Exactness: iq3::half is the loader's own integer-only conversion; an 11-bit
// significand times an integer of magnitude <= 128 is exactly representable in
// FP32 (no rounding, no subnormal result for a nonzero product, signed zero by
// sign rule), and there is no add to contract. So the recomputed word equals the
// stored word bit for bit for every finite d. A non-finite d could differ in NaN
// sign/payload between host and device, so census_q6() counts them and the
// engine refuses to start on any non-finite d or any word mismatch.
//
// Everything else is the unchanged production expression of each lane family:
// code loads, input loads, products, add order, lane schedule, split bounds and
// reduction trees. Existing headers are not modified; these are new names, so
// inherited objects keep their exact production definitions (no ODR overlap).
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet186-twocard-v3/build/checked/experiments/own-xpu-runtime/stage2/packet186-twocard-v3/p33_candidates.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet186-twocard-v3/build/checked/experiments/own-xpu-runtime/stage2/packet186-twocard-v3/p49d_small.hpp"
#include <array>
#include <bit>
#include <cstdint>
#include <stdexcept>
namespace p183 {
using iq3::Type;
template<unsigned K> inline constexpr unsigned meta_offset=K+4*(K/16);
// Scale word of the 16-weight group that contains k (k%8==0, k%16 in {0,8}).
template<unsigned K> inline float q6_scale(const uint8_t* __restrict w,unsigned k){
 static_assert(K%256==0 && K>0 && K<=17408);
 const uint8_t* m=w+meta_offset<K>+18*(k/256);
#if defined(__SYCL_DEVICE_ONLY__)
 // Row strides (3380/8112/13520), meta_offset and 18*(k/256) are even.
 const uint32_t d=*reinterpret_cast<const uint16_t*>(m);
#else
 const uint32_t d=iq3::u16(m);
#endif
 return iq3::half(d)*float(iq3::signed8(m[2+(k%256)/16]));
}
// p33::dense_lane<Q6_K,K> with the metadata scale. Odd (non-256) begins keep
// packet28's production segmentation, exactly as p33 does.
template<unsigned K>
inline float p33_lane(const uint8_t* __restrict w,const uint16_t* __restrict x,
 unsigned begin,unsigned end,unsigned lane) {
 if(begin%256)return p28::dense_lane<Type::Q6_K,K>(w,x,begin,end,lane);
 float sum=0;
 for(unsigned tile=begin+lane*8;tile<end;tile+=256){
  const float scale=q6_scale<K>(w,tile);
  #pragma unroll
  for(unsigned j=0;j<8;++j)if(tile+j<end){
   float value=scale*float(iq3::signed8(w[tile+j]));
   float input=iq3::bits_float(uint32_t(x[tile+j])<<16);
   float product=value*input;sum=sum+product;
  }
 }
 return sum;
}
// p49c::dense_lane<Q6_K,K> with the metadata scale.
template<unsigned K>
inline float p49c_lane(const uint8_t* w,const uint16_t* x,unsigned begin,unsigned end,unsigned lane){
 float sum=0;
 for(unsigned k=begin+lane*8;k<end;k+=256){
#if defined(__SYCL_DEVICE_ONLY__)
  sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
  const float scale=q6_scale<K>(w,k);const uint32_t lo=p49c::load32(w+k),hi=p49c::load32(w+k+4);
  #pragma unroll
  for(unsigned j=0;j<8;++j){
   float value=scale*float(iq3::signed8(uint8_t(((j<4?lo:hi)>>(8*(j%4)))&255)));
#if defined(__SYCL_DEVICE_ONLY__)
   uint16_t bits=inputs[j];
#else
   uint16_t bits=x[k+j];
#endif
   float product=value*iq3::bits_float(uint32_t(bits)<<16);sum=sum+product;
  }
 }
 return sum;
}
// p49dvirtual::dense_chains<Q6_K,K,V> with the metadata scale.
template<unsigned K,unsigned V>
inline std::array<float,V> small_chains(const uint8_t*w,const uint16_t*x,unsigned begin,unsigned end,unsigned physical){
 std::array<float,V> sums{};
 for(unsigned step=begin;step<end;step+=256){
  #pragma unroll
  for(unsigned c=0;c<V;++c){unsigned k=step+8*(physical*V+c);if(k>=end)continue;
   const float scale=q6_scale<K>(w,k);const uint32_t lo=p49bgemv::load32(w+k),hi=p49bgemv::load32(w+k+4);
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
   #pragma unroll
   for(unsigned j=0;j<8;++j){float value=scale*float(iq3::signed8(uint8_t(((j<4?lo:hi)>>(8*(j%4)))&255)));
#if defined(__SYCL_DEVICE_ONLY__)
    uint16_t bits=inputs[j];
#else
    uint16_t bits=x[k+j];
#endif
    float product=value*iq3::bits_float(uint32_t(bits)<<16);sums[c]=sums[c]+product;
   }
  }
 }
 return sums;
}
// p49dvirtual::dense_host<Q6_K,K,Split,V> with the metadata chains.
template<unsigned K,unsigned Split,unsigned V>inline uint16_t small_host(const uint8_t*w,const uint16_t*x){
 float partial[Split]{};
 for(unsigned part=0;part<Split;++part){auto bounds=iq3::kopt2::bounds(K,part,Split);float lanes[32/V];
  for(unsigned p=0;p<32/V;++p)lanes[p]=p49dvirtual::local_tree<V>(small_chains<K,V>(w,x,bounds.first,bounds.second,p));
  for(unsigned width=1;width<32/V;width*=2)for(unsigned p=0;p<32/V;p+=2*width)lanes[p]=lanes[p]+lanes[p+width];partial[part]=lanes[0];}
 return iq3::bf16_bits(Split==1?partial[0]:(partial[0]+partial[1])+(partial[2]+partial[3]));
}
#ifndef OWN_RT_HOST_ONLY
// p49dvirtual::dense_device<Q6_K,K,Split,V,E> with the metadata chains.
template<unsigned K,unsigned Split,unsigned V,p39::Kind E>
inline void small_device(p39::Bound b,unsigned group,sycl::nd_item<1>it,float* scratch){
 constexpr unsigned P=32/V;auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32;
 unsigned within=lane/P,physical=lane%P,part=Split==4?sub:0;
 unsigned row=Split==4?group*V+within:(group*4+sub)*V+within;
 float value=0;auto bounds=iq3::kopt2::bounds(K,part,Split);
 if(row<b.rows)value=p49dvirtual::local_tree<V>(small_chains<K,V>(b.w+size_t(row)*b.rb,b.x,bounds.first,bounds.second,physical));
 for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
 if constexpr(Split==4){if(!physical)scratch[within*4+part]=value;it.barrier(sycl::access::fence_space::local_space);if(!part&&!physical){auto s=scratch+within*4;value=(s[0]+s[1])+(s[2]+s[3]);}}
 if(row<b.rows&&!physical&&!part){auto y=iq3::bf16_bits(value);b.y[row]=y;p49c::dense_tail_device<E>(b,row,y);}
}
#endif
// Host census of expanded Q6_K rows: every 16-weight group's stored FP32 word
// must equal the recomputed metadata product; every d must be finite.
struct Census { uint64_t rows=0,blocks=0,groups=0,nonfinite=0,mismatch=0; };
inline Census census_q6(const uint8_t* base,size_t rows,size_t K){
 if(!K||K%256||iq3::expanded::row_bytes(Type::Q6_K,K)!=K+4*(K/16)+18*(K/256))throw std::invalid_argument("p183 Q6 expanded geometry");
 const size_t rb=iq3::expanded::row_bytes(Type::Q6_K,K);Census c;
 for(size_t r=0;r<rows;++r){const uint8_t* w=base+r*rb;const uint8_t* meta=w+K+4*(K/16);
  for(size_t b=0;b<K/256;++b){const uint32_t d=iq3::u16(meta+18*b);if(((d>>10)&31)==31)++c.nonfinite;
   for(unsigned g=0;g<16;++g){const float s=iq3::half(d)*float(iq3::signed8(meta[18*b+2+g]));
    if(std::bit_cast<uint32_t>(s)!=iq3::u32(w+K+4*(b*16+g)))++c.mismatch;++c.groups;}
   ++c.blocks;}
  ++c.rows;}
 return c;
}
inline void census_add(Census& total,const Census& c){total.rows+=c.rows;total.blocks+=c.blocks;total.groups+=c.groups;total.nonfinite+=c.nonfinite;total.mismatch+=c.mismatch;}
} // namespace p183
