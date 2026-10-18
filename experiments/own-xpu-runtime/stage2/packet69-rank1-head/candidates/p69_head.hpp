#pragma once
#include "p33_submit.hpp"
#include "p33_candidates.hpp"
namespace p69 {
// Expanded rows retain source metadata after the codes and F32 scales. The
// kernel reads 3,200 useful bytes, but the next row starts at byte 3,380.
inline size_t row_bytes(){return integrated::arithmetic::row_bytes(iq3::Type::Q6_K,2560,6);}
// Same eight products per lane, same K traversal, multiply then add, tree32.
// Only memory loads and the number of independent row subgroups change.
inline float lane(const uint8_t* __restrict w,const uint16_t* __restrict x,unsigned id){
 float sum=0;
 for(unsigned tile=id*8;tile<2560;tile+=256){
  const float scale=iq3::bits_float(iq3::u32(w+2560+4*(tile/16)));
#if defined(__SYCL_DEVICE_ONLY__)
  sycl::vec<uint8_t,8> codes;sycl::vec<uint16_t,8> inputs;
  codes.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(w+tile));
  inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+tile));
#else
  std::array<uint8_t,8>codes;std::array<uint16_t,8>inputs;
  std::memcpy(codes.data(),w+tile,8);std::memcpy(inputs.data(),x+tile,16);
#endif
  #pragma unroll
  for(unsigned j=0;j<8;++j){float value=scale*float(iq3::signed8(codes[j]));float input=iq3::bits_float(uint32_t(inputs[j])<<16);float product=value*input;sum=sum+product;}
 }
 return sum;
}
inline float row(const uint8_t*w,const uint16_t*x){float sums[32];for(unsigned i=0;i<32;++i)sums[i]=lane(w,x,i);return iq3::tree32(sums);}
integrated::Launch head(ownrt::Device&,const integrated::Matrix&,const std::string&);
}
