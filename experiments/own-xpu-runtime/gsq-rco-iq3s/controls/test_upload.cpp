#include "upload.hpp"
#include <bit>
#include <cmath>
#include <iostream>
#include <limits>
static void check(bool b){if(!b)throw std::runtime_error("control upload test");}
int main(){
  std::vector<uint8_t> raw(65536*2);
  for(unsigned h=0;h<65536;++h){raw[2*h]=h&255;raw[2*h+1]=h>>8;}
  auto half=gsq::controls::upload_f32(1,raw),bf=gsq::controls::upload_f32(30,raw);
  for(unsigned h=0;h<65536;++h){
    uint32_t actual,bits;std::memcpy(&actual,half.data()+h*4,4);std::memcpy(&bits,bf.data()+h*4,4);
    check(bits==h<<16);
    unsigned exponent=(h>>10)&31, fraction=h&1023;
    float ref;
    if(exponent==31)ref=fraction?std::numeric_limits<float>::quiet_NaN():std::numeric_limits<float>::infinity();
    else ref=exponent?std::ldexp(float(1024+fraction),int(exponent)-25):std::ldexp(float(fraction),-24);
    ref=std::copysign(ref,h&32768?-1.f:1.f);
    if(exponent==31 && fraction)check(std::isnan(std::bit_cast<float>(actual)));
    else check(actual==std::bit_cast<uint32_t>(ref));
  }
  check(gsq::controls::upload_f32(0,half)==half);
  unsigned refused=0;
  for(auto [type,size]:{std::pair<unsigned,size_t>{8,2},{1,1},{0,2},{1,0},{1,4*1024*1024+2}}){
    try {std::vector<uint8_t> in(size);gsq::controls::upload_f32(type,in);}catch(const std::invalid_argument&){++refused;}
  }
  check(refused==5);
  std::cout<<"{\"passed\":true,\"half_encodings\":65536,\"bf16_encodings\":65536,\"f32_bytes_preserved\":262144,\"refusals\":5,\"device_executed\":false}\n";
}
