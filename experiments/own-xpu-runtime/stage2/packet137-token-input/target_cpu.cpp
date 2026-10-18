#include "token_input.hpp"
#include <iostream>
#include <vector>
#include <random>
#include <cstring>
int main(){try{
 std::mt19937 random(137);size_t cases=0;
 for(auto type:{iq3::Type::Q6_K,iq3::Type::IQ4_NL}){
  auto fmt=iq3::layout(type);std::vector<uint8_t> raw(fmt.bytes);std::vector<uint16_t> out(fmt.elements);
  // Exhaust all FP16 scale encodings, including signed zeros/subnormals/NaNs.
  for(unsigned scale=0;scale<65536;++scale){for(auto& b:raw)b=uint8_t(random());size_t off=type==iq3::Type::Q6_K?208:0;raw[off]=scale&255;raw[off+1]=scale>>8;
   p137::decode(type,raw.data(),fmt.elements,out.data());
   for(unsigned i=0;i<fmt.elements;++i)if(out[i]!=iq3::bf16_bits(iq3::element(type,raw.data(),i)))throw std::runtime_error("block byte mismatch");++cases;
  }
 }
 std::array<int64_t,35> m{};m[0]=std::bit_cast<int64_t>(uint64_t(0xd5a0f523e7e23495));m[1]=std::bit_cast<int64_t>(uint64_t(0xb1b3b5b7b9bbbdbf));m[2]=0x7123456789abcdef;
 for(int i=0;i<16;++i){m[3+i]=17+i*31;m[19+i]=i*10000;}
 int64_t history0=248044,history1=248044;std::array<int64_t,16> ids{},expected{};
 for(int step=0;step<4096;++step){int token=step%13==0?248044:int(random()%248320);auto saved0=history0,saved1=history1;
  p137::ple(token,history0,history1,248044,m.data(),ids.data());
  int64_t old0=history0,old1=history1;if(old1==248044)old0=248044;
  for(int n=2;n<=3;++n){uint64_t bits=uint64_t(token)*uint64_t(m[0]);bits^=uint64_t(old1)*uint64_t(m[1]);if(n==3)bits^=uint64_t(old0)*uint64_t(m[2]);int64_t v=std::bit_cast<int64_t>(bits);for(int h=0;h<8;++h){int i=(n-2)*8+h;expected[i]=(v%m[3+i]+m[3+i])%m[3+i]+m[19+i];}}
  if(ids!=expected)throw std::runtime_error("signed PLE mismatch");
  history0=history1;history1=token;
  if(step%3==0){history0=saved0;history1=saved1;p137::ple(token,history0,history1,248044,m.data(),ids.data());if(ids!=expected)throw std::runtime_error("rollback IDs");}
  if(step%71==0)history0=history1=248044;
 }
 std::cout<<"{\"passed\":true,\"block_cases\":"<<cases<<",\"history_steps\":4096,\"full_fp16_scale_domain\":true}"<<std::endl;
 }catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}}
