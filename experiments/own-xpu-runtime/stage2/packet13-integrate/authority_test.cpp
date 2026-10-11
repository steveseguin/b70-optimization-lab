#include "arithmetic.hpp"
#include <bit>
#include <cstring>
#include <iostream>
#include <vector>
using namespace iq3;
float recursive(const std::vector<float>& v,size_t begin,size_t n) {
  if(n==1)return v[begin];
  float left=recursive(v,begin,n/2),right=recursive(v,begin+n/2,n/2);
  return left+right;
}
int main() {
  unsigned checks=0;
  for(auto& shape:kopt4::dispatch_table) {
    auto t=Type(shape.type);size_t k=shape.k;auto fmt=layout(t);
    if(k%fmt.elements)continue;
    std::vector<uint8_t> w(k/fmt.elements*fmt.bytes);
    std::vector<uint16_t> x(k);
    uint32_t seed=1729;
    for(auto& b:w){seed=seed*1664525u+1013904223u;b=seed>>24;}
    if(t==Type::F32)for(size_t i=0;i<k;++i){float f=float(int(i%31)-15)/128;std::memcpy(w.data()+i*4,&f,4);}
    else for(size_t off=0;off<w.size();off+=fmt.bytes) {
      size_t scale=off+(t==Type::Q6_K?208:0);
      w[scale]=0;w[scale+1]=0x24; // finite small scale
    }
    unsigned variant=integrated::arithmetic::variant(t,shape.rows,k,shape.experts,false);
    if(variant!=(shape.experts>1?2:shape.variant))throw std::runtime_error("dispatch selection");
    unsigned splits=variant==1 || variant>=4?4:1;
    for(unsigned mutation=0;mutation<3;++mutation) {
      for(size_t i=0;i<k;++i)x[i]=bf16_bits(mutation==2?(i%2?-0.f:0.f):float(int(i%19)-9)*(mutation?-1.f:1.f));
      std::vector<float> parts(splits);
      for(unsigned s=0;s<splits;++s) {
        size_t tiles=(k+255)/256,lo=std::min(k,(tiles*s/splits)*256),hi=std::min(k,(tiles*(s+1)/splits)*256);
        std::vector<float> lanes(32,0);
        for(unsigned lane=0;lane<32;++lane)
          for(size_t start=lo+8*lane;start<hi;start+=256)
            for(size_t i=start;i<std::min(start+8,hi);++i) {
              float product=element(t,w.data(),i)*bits_float(uint32_t(x[i])<<16);
              lanes[lane]=lanes[lane]+product;
            }
        parts[s]=recursive(lanes,0,32);
      }
      float expected=recursive(parts,0,splits),actual=integrated::arithmetic::row(t,w.data(),x.data(),k,variant);
      if(std::bit_cast<uint32_t>(actual)!=std::bit_cast<uint32_t>(expected))throw std::runtime_error("authority row mismatch");
      ++checks;
    }
  }
  bool refused=false;try{integrated::arithmetic::variant(Type::F32,99,123,1,false);}catch(const std::invalid_argument&){refused=true;}
  if(!refused)throw std::runtime_error("unknown production shape accepted");
  std::cout<<checks<<" independent production-shape arithmetic comparisons; unknown shape refused\n";
}
