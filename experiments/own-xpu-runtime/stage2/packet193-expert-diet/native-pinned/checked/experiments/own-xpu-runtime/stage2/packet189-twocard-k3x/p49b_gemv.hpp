#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet193-expert-diet/native-pinned/root/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p49b_gemv.hpp"
#pragma once
// Original packet48 layout and kernels. Read-only references supply the existing
// normative format tables and exact arithmetic oracle, never a new reduction.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet193-expert-diet/native-pinned/checked/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/p33_candidates.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet193-expert-diet/native-pinned/checked/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/p42_expert.hpp"
#include <cstring>
#include <stdexcept>

namespace p49bgemv {
using iq3::Type;
struct Layout { size_t codes=0,signs=0,high=0,scales=0,halves=0,row_bytes=0; };
constexpr size_t align16(size_t n){return (n+15)&~size_t(15);}
constexpr Layout layout(Type t,unsigned k){
 Layout l;size_t at=0;
 if(t==Type::IQ4_NL){at=k/2;l.halves=align16(at);at=l.halves+2*(k/32);}
 else if(t==Type::IQ2_S){at=k/4;l.high=align16(at);at=l.high+k/32;l.scales=align16(at);at=l.scales+k/32;l.halves=align16(at);at=l.halves+2*(k/256);}
 else if(t==Type::IQ3_S){at=k/4;l.signs=align16(at);at=l.signs+k/8;l.high=align16(at);at=l.high+k/32;l.scales=align16(at);at=l.scales+k/64;l.halves=align16(at);at=l.halves+2*(k/256);}
 else if(t==Type::Q6_K||t==Type::Q8_0){at=k;l.scales=align16(at);at=l.scales+4*(k/(t==Type::Q6_K?16:32));}
 else throw std::invalid_argument("p48 unsupported format");
 // IQ2/IQ4 production banks retain their original byte extent. All weight
 // vectorized reads are scalar 32/16-bit loads, so four-byte row alignment
 // suffices; activation vector loads are independent of this weight stride.
 l.row_bytes=(t==Type::IQ2_S||t==Type::IQ4_NL)?(at+3)&~size_t(3):align16(at);return l;
}
inline size_t source_row_bytes(Type t,unsigned k){
 auto f=iq3::layout(t);if(!k||k>17408||k%f.elements)throw std::invalid_argument("p48 row geometry");
 return t==Type::Q6_K||t==Type::Q8_0?iq3::expanded::row_bytes(t,k):k/f.elements*f.bytes;
}
// Destination is a distinct aligned row. Dense input is the current runtime's
// expanded row, not its GGUF row. Unused retained metadata is safely omitted.
inline void repack_row(Type t,unsigned k,const uint8_t* src,uint8_t* dst){
 auto source_bytes=source_row_bytes(t,k);auto l=layout(t,k);
 if(!src||!dst||uintptr_t(dst)%4)throw std::invalid_argument("p48 repack pointer/alignment");
 const uintptr_t a=uintptr_t(src),b=uintptr_t(dst);
 if(a<b+l.row_bytes&&b<a+source_bytes)throw std::invalid_argument("p48 repack overlap");
 // Compilers may select different operand payloads when two NaNs meet, despite
 // identical real-number arithmetic. Rejected packet48 evidence retains that
 // failure. Admit only finite WEIGHT scales; never alter a nonfinite payload or
 // partially write its destination. Nonfinite activations remain tested.
 if(t==Type::Q6_K||t==Type::Q8_0){unsigned group=t==Type::Q6_K?16:32;for(unsigned i=0;i<k/group;++i)if((iq3::u32(src+k+4*i)&0x7f800000u)==0x7f800000u)throw std::invalid_argument("p48 nonfinite weight scale");}
 else {auto f=iq3::layout(t);for(unsigned i=0;i<k/f.elements;++i)if((iq3::u16(src+i*f.bytes)&0x7c00u)==0x7c00u)throw std::invalid_argument("p48 nonfinite weight scale");}
 std::memset(dst,0,l.row_bytes);
 if(t==Type::Q6_K||t==Type::Q8_0){std::memcpy(dst,src,k);std::memcpy(dst+l.scales,src+k,4*(k/(t==Type::Q6_K?16:32)));return;}
 const auto f=iq3::layout(t);
 for(unsigned block=0;block<k/f.elements;++block){const auto* s=src+block*f.bytes;std::memcpy(dst+l.halves+block*2,s,2);
  if(t==Type::IQ4_NL)std::memcpy(dst+block*16,s+2,16);
  else if(t==Type::IQ2_S){for(unsigned lane=0;lane<32;++lane){dst[block*64+lane*2]=s[2+lane];dst[block*64+lane*2+1]=s[34+lane];}std::memcpy(dst+l.high+block*8,s+66,8);std::memcpy(dst+l.scales+block*8,s+74,8);}
  else {std::memcpy(dst+block*64,s+2,64);std::memcpy(dst+l.signs+block*32,s+74,32);std::memcpy(dst+l.high+block*8,s+66,8);std::memcpy(dst+l.scales+block*4,s+106,4);}
 }
}
inline uint32_t load32(const uint8_t* p){
#if defined(__SYCL_DEVICE_ONLY__)
 return *reinterpret_cast<const uint32_t*>(p);
#else
 uint32_t value;std::memcpy(&value,p,4);return value;
#endif
}
inline uint16_t load16(const uint8_t* p){
#if defined(__SYCL_DEVICE_ONLY__)
 return *reinterpret_cast<const uint16_t*>(p);
#else
 uint16_t value;std::memcpy(&value,p,2);return value;
#endif
}
// Every load32/16 below has a proved 4/2-byte address: each row is four-byte
// aligned, plane offsets are multiples of16, and routed strides preserve four.
template<Type T,unsigned K> inline void decode8(const uint8_t* __restrict row,unsigned k,float (&v)[8]){
 constexpr auto l=layout(T,K);
 if constexpr(T==Type::IQ4_NL){
  unsigned block=k/32,off=k%32;float d=iq3::half(load16(row+l.halves+2*block));
  const uint8_t* codes=row+16*block+off%16;const uint32_t a=load32(codes),b=load32(codes+4);
  for(unsigned j=0;j<8;++j){unsigned code=((j<4?a:b)>>(8*(j%4)))&255;unsigned q=(code>>(4*(off/16)))&15;v[j]=d*float(p33::level_bank(q));}
 }else if constexpr(T==Type::Q6_K||T==Type::Q8_0){
  constexpr unsigned group=T==Type::Q6_K?16:32;float scale=iq3::bits_float(load32(row+l.scales+4*(k/group)));
  const uint32_t a=load32(row+k),b=load32(row+k+4);
  for(unsigned j=0;j<8;++j){unsigned code=((j<4?a:b)>>(8*(j%4)))&255;v[j]=scale*float(iq3::signed8(uint8_t(code)));}
 }else{
  static_assert(T==Type::IQ2_S||T==Type::IQ3_S);
  unsigned block=k/256,i=k%256;float d=iq3::half(load16(row+l.halves+2*block));float scale;unsigned signs,index0,index1=0;
  if constexpr(T==Type::IQ2_S){unsigned q=i/8;unsigned pair=load16(row+block*64+q*2);index0=(pair&255)|(((row[l.high+block*8+q/4]>>(2*(q%4)))&3)<<8);signs=pair>>8;scale=(d*(0.5f+float((row[l.scales+block*8+i/32]>>(4*((i/16)%2)))&15)))*0.25f;}
  else {unsigned q=i/4;unsigned pair=load16(row+block*64+q);unsigned high=row[l.high+block*8+q/8];index0=(pair&255)|(((high>>(q%8))&1)<<8);index1=(pair>>8)|(((high>>((q+1)%8))&1)<<8);signs=row[l.signs+block*32+i/8];scale=d*float(1+2*((row[l.scales+block*4+i/64]>>(4*((i/32)%2)))&15));}
  uint32_t a,b;if constexpr(T==Type::IQ2_S){a=p42expert::iq2_words[index0*2];b=p42expert::iq2_words[index0*2+1];}else {a=p42expert::iq3_words[index0];b=p42expert::iq3_words[index1];}
  bool exceptional=(std::bit_cast<uint32_t>(d)&0x7fffffff)>=0x7f800000||(std::bit_cast<uint32_t>(scale)&0x7fffffff)>0x7f800000;
  for(unsigned j=0;j<8;++j){unsigned mag=((j<4?a:b)>>(8*(j%4)))&255;if(exceptional)v[j]=(scale*float(mag))*float((signs>>j)&1?-1:1);else {int q=(signs>>j)&1?-int(mag):int(mag);v[j]=scale*float(q);}}
 }
}
template<Type T,unsigned K> inline float lane(const uint8_t* __restrict w,const uint16_t* __restrict x,unsigned begin,unsigned end,unsigned lane_id){
 float sum=0;
 for(unsigned tile=begin+lane_id*8;tile<end;tile+=256){float v[8];decode8<T,K>(w,tile,v);
#if defined(__SYCL_DEVICE_ONLY__)
 sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+tile));
#endif
  for(unsigned j=0;j<8;++j)if(tile+j<end){
#if defined(__SYCL_DEVICE_ONLY__)
   const uint16_t bits=inputs[j];
#else
   const uint16_t bits=x[tile+j];
#endif
   float input=iq3::bits_float(uint32_t(bits)<<16);float product=v[j]*input;sum=sum+product;
  }
 }return sum;
}
// Same paired interleaving as p28: decoding is independent, input loaded once,
// each gate/up chain retains its original ordered multiply and add operations.
template<Type T,unsigned K> inline std::array<float,2> gate_lane(const uint8_t* __restrict w,const uint8_t* __restrict peer,const uint16_t* __restrict x,unsigned begin,unsigned end,unsigned lane_id){
 static_assert(T==Type::IQ2_S||T==Type::IQ3_S);std::array<float,2> sum{};
 for(unsigned tile=begin+lane_id*8;tile<end;tile+=256){float a[8],b[8];decode8<T,K>(w,tile,a);decode8<T,K>(peer,tile,b);
#if defined(__SYCL_DEVICE_ONLY__)
 sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+tile));
#endif
  for(unsigned j=0;j<8;++j)if(tile+j<end){
#if defined(__SYCL_DEVICE_ONLY__)
   const uint16_t bits=inputs[j];
#else
   const uint16_t bits=x[tile+j];
#endif
   float input=iq3::bits_float(uint32_t(bits)<<16);float pa=a[j]*input;sum[0]=sum[0]+pa;float pb=b[j]*input;sum[1]=sum[1]+pb;
  }
 }return sum;
}
template<Type T,unsigned K> inline std::array<float,2> lanes2(const uint8_t* __restrict w,const uint16_t* __restrict x0,const uint16_t* __restrict x1,unsigned begin,unsigned end,unsigned lane_id){
 std::array<float,2> sum{};
 for(unsigned tile=begin+lane_id*8;tile<end;tile+=256){float v[8];decode8<T,K>(w,tile,v);
#if defined(__SYCL_DEVICE_ONLY__)
 sycl::vec<uint16_t,8> a,b;a.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x0+tile));b.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x1+tile));
#endif
  for(unsigned j=0;j<8;++j)if(tile+j<end){
#if defined(__SYCL_DEVICE_ONLY__)
   uint16_t bits0=a[j],bits1=b[j];
#else
   uint16_t bits0=x0[tile+j],bits1=x1[tile+j];
#endif
   float i0=iq3::bits_float(uint32_t(bits0)<<16),i1=iq3::bits_float(uint32_t(bits1)<<16);float p0=v[j]*i0;sum[0]=sum[0]+p0;float p1=v[j]*i1;sum[1]=sum[1]+p1;
  }
 }return sum;
}
} // namespace p49bgemv
