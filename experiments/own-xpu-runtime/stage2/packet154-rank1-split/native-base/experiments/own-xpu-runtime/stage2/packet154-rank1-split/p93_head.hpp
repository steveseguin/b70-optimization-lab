#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet154-rank1-split/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p93_head.hpp"
#pragma once
// Original lab mechanisms: word-parallel plane extraction and reversible SOA.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet154-rank1-split/build/checked/experiments/own-xpu-runtime/stage2/packet154-rank1-split/p74_packed.hpp"
namespace p93 {
constexpr unsigned K=2560;
inline std::vector<uint8_t> transpose(const uint8_t* raw,size_t blocks){
 std::vector<uint8_t> out(blocks*210);
 for(size_t b=0;b<blocks;++b){const auto* src=raw+b*210;
  for(unsigned lane=0;lane<32;++lane){uint32_t low=0;uint16_t high=0;
   for(unsigned j=0;j<8;++j){unsigned i=lane*8+j,h=i/128,s=(i%128)/32,l=i%32;
    unsigned ql=(src[h*64+(s%2)*32+l]>>(s>=2?4:0))&15;
    unsigned qh=(src[128+h*32+l]>>(2*s))&3;
    low|=ql<<(4*j);high|=qh<<(2*j);
   }
   std::memcpy(out.data()+b*128+lane*4,&low,4);
   std::memcpy(out.data()+blocks*128+b*64+lane*2,&high,2);
  }
  std::memcpy(out.data()+blocks*192+b*16,src+192,16);
  std::memcpy(out.data()+blocks*208+b*2,src+208,2);
 }return out;
}
inline std::vector<uint8_t> untranspose(const uint8_t* in,size_t blocks){
 std::vector<uint8_t> out(blocks*210);
 for(size_t b=0;b<blocks;++b){auto* dst=out.data()+b*210;
  for(unsigned lane=0;lane<32;++lane){uint32_t low=p74::word(in+b*128+lane*4);uint16_t high=p74::halfword(in+blocks*128+b*64+lane*2);
   for(unsigned j=0;j<8;++j){unsigned i=lane*8+j,h=i/128,s=(i%128)/32,l=i%32;
    dst[h*64+(s%2)*32+l]|=((low>>(4*j))&15)<<(s>=2?4:0);
    dst[128+h*32+l]|=((high>>(2*j))&3)<<(2*s);
   }
  }
  std::memcpy(dst+192,in+blocks*192+b*16,16);std::memcpy(dst+208,in+blocks*208+b*2,2);
 }return out;
}
template<unsigned Mode>inline void decode8(const uint8_t* w,size_t blocks,unsigned row,unsigned k,float (&v)[8]){
 static_assert(Mode==1||Mode==2);
 const size_t block=size_t(row)*10+k/256;unsigned i=k%256;
 uint32_t lo,hi;float scale;
 if constexpr(Mode==1){const auto*b=w+block*210;unsigned h=i/128,s=(i%128)/32,l=i%32;uint32_t a,bits,c,d;
  p74::load8(b+h*64+(s%2)*32+l,a,bits);p74::load8(b+128+h*32+l,c,d);
  // Four independent byte lanes decoded by each word operation, no carries.
  lo=((a>>(s>=2?4:0))&0x0f0f0f0fu)|(((c>>(2*s))&0x03030303u)<<4);
  hi=((bits>>(s>=2?4:0))&0x0f0f0f0fu)|(((d>>(2*s))&0x03030303u)<<4);
  scale=iq3::half(p74::halfword(b+208))*float(iq3::signed8(b[192+i/16]));
 }else{
  lo=p74::word(w+block*128+(i/8)*4);hi=p74::halfword(w+blocks*128+block*64+(i/8)*2);
  scale=iq3::half(p74::halfword(w+blocks*208+block*2))*float(iq3::signed8(w[blocks*192+block*16+i/16]));
 }
 #pragma unroll
 for(unsigned j=0;j<8;++j){int code;
  if constexpr(Mode==1)code=int(((j<4?lo:hi)>>(8*(j%4)))&255)-32;
  else code=int(((lo>>(4*j))&15)|(((hi>>(2*j))&3)<<4))-32;
  v[j]=scale*float(code);
 }
}
template<unsigned Mode>inline float lane(const uint8_t*w,size_t blocks,unsigned row,const uint16_t*x,unsigned begin,unsigned end,unsigned lane_id){
 float sum=0;
 for(unsigned k=begin+lane_id*8;k<end;k+=256){float v[8];decode8<Mode>(w,blocks,row,k,v);
#if defined(__SYCL_DEVICE_ONLY__)
  sycl::vec<uint16_t,8> input;input.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
  #pragma unroll
  for(unsigned j=0;j<8;++j)if(k+j<end){
#if defined(__SYCL_DEVICE_ONLY__)
   uint16_t bits=input[j];
#else
   uint16_t bits=x[k+j];
#endif
   float product=v[j]*iq3::bits_float(uint32_t(bits)<<16);sum=sum+product;
  }
 }return sum;
}
}
