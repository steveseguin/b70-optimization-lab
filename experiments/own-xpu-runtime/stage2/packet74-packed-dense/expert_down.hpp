#pragma once
#include "performance.hpp"
namespace p29 {
// Fixed production K=640, R=2560. Native IQ4_NL bytes, unchanged v2 expression.
inline constexpr int8_t levels[16]={-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
inline float down_lane(const uint8_t* row,const uint16_t* x,unsigned lane){
 float sum=0;
 for(unsigned k=lane*8;k<640;k+=256){
  const uint8_t* block=row+(k/32)*18;
  const float scale=iq3::half(uint16_t(block[0])|(uint16_t(block[1])<<8));
  const unsigned offset=k%32;
  for(unsigned j=0;j<8;++j){
   const uint8_t code=block[2+(offset+j)%16];
   const int8_t level=levels[(code>>(4*((offset+j)/16)))&15];
   const float value=scale*float(level);
   const float input=iq3::bits_float(uint32_t(x[k+j])<<16);
   const float product=value*input;sum=sum+product;
  }
 }
 return sum;
}
void validate(ownrt::Device&,const std::vector<integrated::Matrix>&,const std::string&,bool,unsigned);
integrated::Launch submit(ownrt::Device&,const std::vector<integrated::Matrix>&,const std::string&,bool,unsigned);
}
