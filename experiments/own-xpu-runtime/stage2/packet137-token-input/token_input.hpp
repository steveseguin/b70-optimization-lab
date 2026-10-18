#pragma once
#include "../packet2/kernels/math.hpp"
#include <array>
#include <bit>
#include <cstdint>
#include <stdexcept>
namespace p137 {
inline constexpr size_t vocab=248320,width=2560,row_bytes=5120,table_bytes=vocab*row_bytes;
inline bool table_mode(const std::string& mode){return mode=="draft_table"||mode=="both";}
inline bool buffer_mode(const std::string& mode){return mode=="target_buffers"||mode=="both";}
// Keep every multiplication and BF16 boundary of iq3::element. Hoist only
// immutable block setup; exceptional scales deliberately use the scalar path.
inline void decode(iq3::Type type,const uint8_t* raw,size_t n,uint16_t* out){
 auto f=iq3::layout(type);
 if(n%f.elements)throw std::invalid_argument("p137 quant block extent");
 for(size_t base=0;base<n;base+=f.elements,raw+=f.bytes){
  if(type==iq3::Type::Q6_K){
   float d=iq3::half(iq3::u16(raw+208));
   for(unsigned g=0;g<16;++g){float scale=d*float(iq3::signed8(raw[192+g]));
    for(unsigned j=0;j<16;++j){unsigned i=g*16+j;
     int low=(raw[(i/128)*64+i%64]>>(4*((i%128)/64)))&15;
     int high=(raw[128+(i/128)*32+i%32]>>(2*((i%128)/32)))&3;
     out[base+i]=iq3::bf16_bits(std::isfinite(scale)?scale*float((low|(high<<4))-32):iq3::decode(type,raw,i));
    }
   }
  }else if(type==iq3::Type::IQ4_NL){
   constexpr int levels[]={-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
   float d=iq3::half(iq3::u16(raw));
   for(unsigned i=0;i<32;++i)out[base+i]=iq3::bf16_bits(std::isfinite(d)?d*float(levels[(raw[2+i%16]>>(4*(i/16)))&15]):iq3::decode(type,raw,i));
  }else for(unsigned i=0;i<f.elements;++i)out[base+i]=iq3::bf16_bits(iq3::decode(type,raw,i));
 }
}
inline void ple(int token,int64_t old0,int64_t old1,int eos,const int64_t* metadata,int64_t* ids){
 if(old1==eos)old0=eos;
 for(int n=2;n<=3;++n){
  uint64_t bits=uint64_t(token)*uint64_t(metadata[0]);
  bits^=uint64_t(old1)*uint64_t(metadata[1]);
  if(n==3)bits^=uint64_t(old0)*uint64_t(metadata[2]);
  int64_t v=std::bit_cast<int64_t>(bits);
  for(int h=0;h<8;++h){int i=(n-2)*8+h;auto size=metadata[3+i];
   if(size<=0)throw std::invalid_argument("PLE host size");
   ids[i]=(v%size+size)%size+metadata[19+i];
  }
 }
}
}
