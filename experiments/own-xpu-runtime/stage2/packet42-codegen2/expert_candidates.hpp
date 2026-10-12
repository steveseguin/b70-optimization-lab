#pragma once
#include "../packet33-codegen/candidates.hpp"
namespace p42expert {
using iq3::Type;
using p28::expert_format;
template<size_t N>consteval auto pack32(const std::array<uint8_t,N>& b){std::array<uint32_t,N/4>w{};for(size_t i=0;i<N;++i)w[i/4]|=uint32_t(b[i])<<(8*(i%4));return w;}
inline constexpr auto iq2_words=pack32(p28::iq2_bytes);
inline constexpr auto iq3_words=pack32(p28::iq3s_bytes);
template<Type T,bool Shared,class Tables,class Share>
inline void packed_decode8(const uint8_t* row,unsigned k,float (&values)[8],Tables tables,Share share) {
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
 uint32_t packed0=0,packed1=0;
 if constexpr(T==Type::IQ2_S){packed0=iq2_words[index0*2];packed1=iq2_words[index0*2+1];}
 else if constexpr(T==Type::IQ3_S){packed0=iq3_words[index0];packed1=iq3_words[index1];}
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
    if constexpr(T==Type::IQ2_S)mag=((j<4?packed0:packed1)>>(8*(j%4)))&255;
    else if constexpr(T==Type::IQ3_S)mag=((j<4?packed0:packed1)>>(8*(j%4)))&255;
    else mag=tables.iq3(j<4?index0:index1,j%4);
    values[j]=(scale*float(mag))*float((signs>>j)&1?-1:1);
   }
  } else {
   for(unsigned j=0;j<8;++j) {
    unsigned mag;
    if constexpr(T==Type::IQ2_S)mag=((j<4?packed0:packed1)>>(8*(j%4)))&255;
    else if constexpr(T==Type::IQ3_S)mag=((j<4?packed0:packed1)>>(8*(j%4)))&255;
    else mag=tables.iq3(j<4?index0:index1,j%4);
    const int q=(signs>>j)&1?-int(mag):int(mag);
    values[j]=scale*float(q);
   }
  }
 }
}
template<Type T,unsigned K>
inline std::array<float,2> gate_lane(const uint8_t* __restrict w,const uint8_t* __restrict peer,const uint16_t* __restrict x,unsigned begin,unsigned end,unsigned lane){
 static_assert(T==Type::IQ2_S||T==Type::IQ3_S);
 std::array<float,2> sum{};
 for(unsigned tile=begin;tile<end;tile+=256){unsigned k=tile+lane*8;float a[8]{},b[8]{};
 packed_decode8<T,false>(w,k<end?k:tile,a,p28::ExpertByteTables{},iq3::kopt3::HostShare{});
 packed_decode8<T,false>(peer,k<end?k:tile,b,p28::ExpertByteTables{},iq3::kopt3::HostShare{});
#if defined(__SYCL_DEVICE_ONLY__)
 sycl::vec<uint16_t,8> input;
 if(k+8<=end)input.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
 for(unsigned j=0;j<8;++j)if(k+j<end){uint16_t bits;
#if defined(__SYCL_DEVICE_ONLY__)
 bits=k+8<=end?input[j]:x[k+j];
#else
 bits=x[k+j];
#endif
 float v=iq3::bits_float(uint32_t(bits)<<16);float pa=a[j]*v;sum[0]=sum[0]+pa;float pb=b[j]*v;sum[1]=sum[1]+pb;}
 }return sum;
}
template<unsigned Mode,unsigned K=640>
inline float down_lane(const uint8_t* __restrict row,const uint16_t* __restrict x,unsigned lane) {
 static_assert(Mode<2 && K>0);
 float sum=0;
 for(unsigned k=lane*8;k<K;k+=256){
  const uint8_t* block=row+(k/32)*18;
  const float scale=iq3::half(uint16_t(block[0])|(uint16_t(block[1])<<8));
  const unsigned offset=k%32;
#if defined(__SYCL_DEVICE_ONLY__)
  // Production K640 has complete eight-weight lane tiles. Explicit vectors
  // request the same contiguous bytes the scalar path uses, with no overread.
  // Odd CPU diagnostic lengths retain their bounds-checked scalar spelling.
  sycl::vec<uint8_t,8> packed_codes;
  sycl::vec<uint16_t,8> packed_inputs;
  if constexpr(Mode==1 && K%8==0){
   packed_codes.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(block+2+offset%16));
   packed_inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
  }
#endif
  #pragma unroll
  for(unsigned j=0;j<8;++j)if(k+j<K){
   uint8_t code;
   uint16_t input_bits;
#if defined(__SYCL_DEVICE_ONLY__)
   if constexpr(Mode==1 && K%8==0){code=packed_codes[j];input_bits=packed_inputs[j];}
   else
#endif
   {code=block[2+(offset+j)%16];input_bits=x[k+j];}
   const unsigned q=(code>>(4*((offset+j)/16)))&15;
   const int level=Mode==0?p33::level_bank(q):p33::level_select(q);
   const float value=scale*float(level);
   const float input=iq3::bits_float(uint32_t(input_bits)<<16);
   const float product=value*input;sum=sum+product;
  }
 }
 return sum;
}
}
