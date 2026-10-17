#pragma once
#include "route.hpp"
#include <cstring>
#include <stdexcept>
#include <vector>

namespace p54route_test {
struct Fixture {
  std::array<uint16_t,512> input{};
  std::array<int32_t,10> ids{};
  std::array<float,10> probability{};
  std::array<int32_t,30> gate{},down{};
  std::array<float,1088> scratch{};
  uint32_t error=0,active=1;
  Fixture() {
    ids.fill(-7);probability.fill(-6.f);gate.fill(-5);down.fill(-4);
    scratch.fill(-7.25f);
  }
  route42::Args args() {
    route42::Args a{};a.input=input.data();a.input_type=flash::Scalar::bf16;
    a.output[0]=ids.data();a.output[1]=probability.data();
    a.output[2]=gate.data();a.output[3]=down.data();
    a.output_type[0]=flash::Scalar::i32;a.output_type[1]=flash::Scalar::f32;
    a.output_type[2]=a.output_type[3]=flash::Scalar::i32;
    a.scratch=scratch.data();a.error=&error;a.active=&active;
    a.n=512;a.top=10;a.mid=640;a.h=2560;a.no=4;return a;
  }
};

template<class T>inline void same(const T& a,const T& b,unsigned& checks) {
  if(std::memcmp(&a,&b,sizeof(T))) throw std::runtime_error("p54 route CPU byte mismatch");
  ++checks;
}
inline void compare(const Fixture& a,const Fixture& b,unsigned& checks) {
  same(a.input,b.input,checks);same(a.ids,b.ids,checks);
  same(a.probability,b.probability,checks);same(a.gate,b.gate,checks);
  same(a.down,b.down,checks);same(a.scratch,b.scratch,checks);
  same(a.error,b.error,checks);same(a.active,b.active,checks);
}
inline void fill(Fixture& a,unsigned test,unsigned row) {
  for(unsigned j=0;j<512;++j) {
    float value=test==0?0.f:test==1?float(j%4):test==2?float(j%2)*-200.f:
      float(int((j*109+row*73+test*11)%1025)-512)/16.f;
    a.input[j]=iq3::bf16_bits(value);
  }
  if(test==3) a.input[237]=0x7fc1;
  if(test==4) a.input[511]=0x7f80;
  if(test==5) a.input[0]=0xff80;
  if(test==6) a.active=0;
  if(test==7) a.error=5;
  if(test==8) for(unsigned j=0;j<512;++j) a.input[j]=j%2?0x8000:0;
}
template<class T>inline void append(std::vector<uint8_t>& bytes,const T& value) {
  auto p=reinterpret_cast<const uint8_t*>(&value);bytes.insert(bytes.end(),p,p+sizeof(value));
}
inline void append_fixture(std::vector<uint8_t>& bytes,const Fixture& a) {
  append(bytes,a.ids);append(bytes,a.probability);append(bytes,a.gate);append(bytes,a.down);
  append(bytes,a.scratch);append(bytes,a.error);append(bytes,a.active);
}
inline unsigned run(std::vector<uint8_t>& digest_bytes) {
  unsigned checks=0;
  // One fixed full production shape (512 experts/top10). M2 is two serial
  // row calls with fresh inputs; controls and output/scratch persist exactly.
  for(unsigned test=0;test<10;++test) for(unsigned m: {1u,2u}) {
    Fixture baseline,rank4,exp32;
    for(unsigned row=0;row<m;++row) {
      fill(baseline,test,row);fill(rank4,test,row);fill(exp32,test,row);
      p54route::control_host(baseline.args());
      p54route::host<4,256>(rank4.args());
      p54route::host<4,32>(exp32.args());
      compare(baseline,rank4,checks);compare(baseline,exp32,checks);
      append_fixture(digest_bytes,rank4);append_fixture(digest_bytes,exp32);
    }
  }
  // A direct rank-stage adversary: raw exponents differ, but their rounded
  // normalized values underflow to equal zeros. Rank must prefer index zero.
  Fixture baseline;baseline.scratch.fill(0.f);
  baseline.scratch[32]=3e30f;baseline.scratch[64]=1e-30f;
  baseline.scratch[65]=2e-30f;
  auto candidate=baseline;
  p51::route_rank_host(baseline.args());p54route::rank_host<4>(candidate.args());
  compare(baseline,candidate,checks);append_fixture(digest_bytes,candidate);
  if(candidate.ids[0]!=0) throw std::runtime_error("p54 route normalized-tie ordering");
  ++checks;
  return checks;
}
} // namespace p54route_test

inline unsigned test_route(std::vector<uint8_t>& digest_bytes) {return p54route_test::run(digest_bytes);}
