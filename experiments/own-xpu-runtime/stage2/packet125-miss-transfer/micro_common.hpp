#pragma once
#include "../packet58j-onecard-port/p49d_expert.hpp"
#include "../packet58j-onecard-port/p100_down.hpp"
#include "iq3_kernel.hpp"
struct Case {uint32_t token,layer,mask;iq3::Route routes[10];};
static_assert(sizeof(Case)==132);
constexpr size_t DOWN=921600,ALIGN=65536,SCRUB=512ull*1024*1024;
static size_t align_up(size_t n){return (n+ALIGN-1)&~(ALIGN-1);}
static size_t gate_bytes(const Case&c){return c.layer==2?704000:524800;}
static unsigned misses(const Case&c){return std::popcount(c.mask);}
static const char* modes[]={"production","tile16","bcs_serial3","bcs_inflight3","bcs_contiguous","bcs_aligned","bcs_pipeline3"};
static std::vector<uint8_t> fixture(iq3::Type t,unsigned rows,unsigned K,unsigned seed){
 auto l=iq3::layout(t);size_t rawstride=K/l.elements*l.bytes,stride=t==iq3::Type::IQ3_S?rawstride:p49bgemv::layout(t,K).row_bytes;
 std::vector<uint8_t> out(rows*stride),raw(rawstride);uint32_t rng=seed;
 for(unsigned r=0;r<rows;++r){for(auto&v:raw){rng=rng*1664525+1013904223;v=rng>>24;}
  for(size_t at=0;at<raw.size();at+=l.bytes){uint16_t scale=0x1400+(r+at)%1024;std::memcpy(raw.data()+at,&scale,2);}
  if(t==iq3::Type::IQ3_S)std::memcpy(out.data()+r*stride,raw.data(),stride);else p49bgemv::repack_row(t,K,raw.data(),out.data()+r*stride);
 }return out;
}
