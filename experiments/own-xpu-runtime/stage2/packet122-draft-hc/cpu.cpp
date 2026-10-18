#include "p122_hc.hpp"
#include <fstream>
#include <filesystem>
#include <iostream>
#include <random>
// Keep the unchanged virtual operation at an opaque call boundary.
__attribute__((noinline)) void baseline(const p59::GateMix<320>&op,std::span<void*const> p){op.run(p);}
int main(int argc,char**argv){try{
 if(argc!=2)throw std::runtime_error("output required");std::filesystem::path out=argv[1];std::filesystem::create_directories(out);
 constexpr unsigned W=2560,K=320;std::vector<uint16_t>w(4*W*K),x(K),n(4*W),ey(4*W),ay(4*W),em(W),am(W);uint32_t seed=122;
 auto next=[&](){seed=1664525*seed+1013904223;return seed;};
 std::ofstream expected(out/"expected.bin",std::ios::binary),actual(out/"candidate.bin",std::ios::binary),cases(out/"cases.jsonl");
 p59::GateMix<K>ref;ref.width=W;p122::GateMix<K>alt;alt.width=W;
 for(unsigned test=0;test<16;++test){
  for(auto&v:w)v=iq3::bf16_bits(float(int(next()%63)-31)/128.f);
  for(auto&v:x)v=iq3::bf16_bits(float(int(next()%63)-31)/32.f);
  for(auto&v:n)v=iq3::bf16_bits(float(int(next()%127)-63)/32.f);
  if(test==1)std::fill(x.begin(),x.end(),0);
  if(test==2)std::fill(x.begin(),x.end(),0x8000);
  if(test==3)for(auto&v:x)v=(next()&1)?0x0001:0x8001;
  if(test>=4){const uint16_t vals[]={0x7fc1,0xffc2,0x7f81,0xff81,0x7f80,0xff80,0x7f7f,0xff7f,0x0080,0x8080,0x3f80,0xbf80};auto v=vals[test-4];if(test%3==0)x[1]=v;else if(test%3==1)w[2]=v;else n[3]=v;}
  std::array<void*,5>rp{w.data(),x.data(),ey.data(),n.data(),em.data()},ap{w.data(),x.data(),ay.data(),n.data(),am.data()};baseline(ref,rp);alt.run(ap);
  if(ey!=ay||em!=am)throw std::runtime_error("byte mismatch case "+std::to_string(test));
  for(auto*v:{&ey,&em})expected.write(reinterpret_cast<char*>(v->data()),v->size()*2);
  for(auto*v:{&ay,&am})actual.write(reinterpret_cast<char*>(v->data()),v->size()*2);
  cases<<"{\"case\":"<<test<<",\"gate_bytes\":20480,\"mix_bytes\":5120,\"exact\":true}\n";
 }
 std::ofstream receipt(out/"native.json");receipt<<"{\"passed\":true,\"device_executed\":false,\"cases\":16,\"output_status_checks\":32,\"gate_and_mix_bytes\":409600}";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
