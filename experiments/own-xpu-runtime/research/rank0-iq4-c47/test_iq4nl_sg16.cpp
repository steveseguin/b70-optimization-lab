#include "stage2/packet6-kopt/reference.hpp"
#include <array>
#include <bit>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <random>
#include <vector>

using iq3::Route;
using iq3::Type;
constexpr unsigned K=640,RB=360;
static uint32_t word(const uint8_t* p){uint32_t v;std::memcpy(&v,p,4);return v;}

// CPU serialization of MultiplyIQ4NLPacked16. The even work-item's block load is shared with its
// peer; all floating-point statements and reduction operands match the device body and reference.
static void packed_sg16(const uint8_t* w,const float* x,float* y,const Route* routes,uint32_t* status,
                        uint32_t experts,uint32_t rows,uint32_t span,uint32_t count){
  for(uint32_t slot=0;slot<count;++slot){const Route r=routes[slot];const bool valid=iq3::valid_route(r,experts,rows,span);status[slot]=valid?0:1;
    for(uint32_t row=0;row<span;++row){
      const bool live=valid&&row<r.row_count;const uint8_t* rp=live?w+(size_t(r.expert_id)*rows+r.row_begin+row)*RB:w;
      float acc[16][2]{};
      for(unsigned t=0;t<8;++t)for(uint32_t b=t;b*32u<K;b+=8u){
        uint32_t qw[4]={0,0,0,0};float scale=0;
        if(live){
          const bool odd=t&1;const uint8_t* wp=rp+b*18u-(odd?2u:0u);
          const uint32_t w0=word(wp),w1=word(wp+4),w2=word(wp+8),w3=word(wp+12),w4=word(wp+16);
          const uint32_t sbits=odd?(w0>>16):(w0&0xffffu);
          qw[0]=odd?w1:(w0>>16)|(w1<<16);qw[1]=odd?w2:(w1>>16)|(w2<<16);
          qw[2]=odd?w3:(w2>>16)|(w3<<16);qw[3]=odd?w4:(w3>>16)|(w4<<16);scale=iq3::kopt::half_scale(sbits);
        }
        for(unsigned high=0;high<2;++high){const unsigned lane=2*t+high;float xv[16];std::memcpy(xv,x+size_t(slot)*K+b*32u+(high?16u:0u),sizeof(xv));
          for(unsigned j=0;j<2;++j)for(unsigned jj=0;jj<8;++jj){
            const unsigned bi=8*j+jj;const uint32_t n=(qw[bi/4]>>(8*(bi%4)+4*high))&15u;
            const float value=scale*float(iq3::iq4_level(n));const float product=value*xv[8*j+jj];acc[lane][j]=acc[lane][j]+product;
          }
        }
      }
      float sums[16];for(unsigned lane=0;lane<16;++lane)sums[lane]=acc[lane][0]+acc[lane][1];
      for(unsigned width=1;width<16;width*=2)for(unsigned lane=0;lane<16;lane+=2*width)sums[lane]=sums[lane]+sums[lane+width];
      y[size_t(slot)*span+row]=live?sums[0]:iq3::bits_float(0x7fc00000);
    }
  }
}

static void reference(const uint8_t* w,const float* x,float* y,const Route* routes,uint32_t* status,
                      uint32_t experts,uint32_t rows,uint32_t span,uint32_t count){
  for(uint32_t slot=0;slot<count;++slot){const Route r=routes[slot];const bool valid=iq3::valid_route(r,experts,rows,span);status[slot]=valid?0:1;
    for(uint32_t row=0;row<span;++row){const bool live=valid&&row<r.row_count;const uint8_t* rp=live?w+(size_t(r.expert_id)*rows+r.row_begin+row)*RB:w;
      y[size_t(slot)*span+row]=live?iq3::kopt::row_t<Type::IQ4_NL>(rp,reinterpret_cast<const uint16_t*>(x+size_t(slot)*K),Type::F32,K,32):iq3::bits_float(0x7fc00000);
    }
  }
}

int main(){
  constexpr uint32_t rows=96,span=96,count=10,experts=40;
  std::mt19937 gen(117);std::vector<uint8_t> weights(size_t(experts)*rows*RB);for(auto& b:weights)b=uint8_t(gen());
  for(size_t row=0;row<size_t(experts)*rows;++row)for(unsigned b=0;b<20;++b){
    static constexpr uint16_t special[]{0,0x8000,1,0x8001,0x03ff,0x7c00,0xfc00,0x7e00,0x7e01};
    const uint16_t h=(row%11==0)?special[(row/11+b)%9]:uint16_t(0x1000+(gen()&0x3fff));
    weights[row*RB+b*18]=uint8_t(h);weights[row*RB+b*18+1]=uint8_t(h>>8);
  }
  std::vector<float> x(count*K);for(auto& v:x)v=std::uniform_real_distribution<float>(-2.f,2.f)(gen);
  std::array<Route,count> routes{{{3,0,rows},{17,0,rows},{5,0,37},{29,0,0},{11,0,rows+1},{40,0,rows},{2,rows,1},{23,rows-3,4},{31,0,rows},{7,1,rows}}};
  std::vector<float> expected(count*span),actual(count*span);std::array<uint32_t,count> es{},as{};
  reference(weights.data(),x.data(),expected.data(),routes.data(),es.data(),experts,rows,span,count);
  packed_sg16(weights.data(),x.data(),actual.data(),routes.data(),as.data(),experts,rows,span,count);
  size_t mismatches=0;for(size_t i=0;i<actual.size();++i)if(std::bit_cast<uint32_t>(actual[i])!=std::bit_cast<uint32_t>(expected[i]))++mismatches;
  const bool status_equal=es==as;std::cout<<"SG16 packed CPU: outputs="<<actual.size()<<" mismatches="<<mismatches<<" status_equal="<<status_equal<<"\n";
  return mismatches||!status_equal;
}
