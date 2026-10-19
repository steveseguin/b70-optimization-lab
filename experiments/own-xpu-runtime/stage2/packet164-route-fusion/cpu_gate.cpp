#include "epilogue.hpp"
#include <fstream>
#include <iostream>
#include <limits>
#include <unistd.h>
extern "C" void p164_original(route42::Args);

struct State {
  std::array<int32_t,10> ids;
  std::array<float,10> probabilities;
  std::array<int32_t,30> up,down;
  std::array<float,1088> scratch;
  uint32_t error=0,active=1;
  State(){ids.fill(-7);probabilities.fill(-6);up.fill(-5);down.fill(-4);scratch.fill(-7.25f);}
  route42::Args args(void* input,flash::Scalar type,unsigned outputs) {
    route42::Args a{};a.input=input;a.input_type=type;a.n=512;a.top=10;a.mid=640;a.h=2560;a.no=outputs;
    a.output[0]=ids.data();a.output[1]=probabilities.data();a.output[2]=up.data();a.output[3]=down.data();
    a.output_type[0]=a.output_type[2]=a.output_type[3]=flash::Scalar::i32;a.output_type[1]=flash::Scalar::f32;
    a.scratch=scratch.data();a.error=&error;a.active=&active;return a;
  }
  std::vector<char> bytes(bool all=true)const {
    std::vector<char>b;
    auto add=[&](const auto&v){auto p=reinterpret_cast<const char*>(&v);b.insert(b.end(),p,p+sizeof(v));};
    add(ids);add(probabilities);add(up);add(down);
    if(all){add(scratch);add(error);add(active);}return b;
  }
};
void check(bool ok,const char*reason){if(!ok)throw std::runtime_error(reason);}
uint32_t next(uint32_t& x){x^=x<<13;x^=x>>17;x^=x<<5;return x;}
int main(int argc,char**argv){try{
  check(argc==2,"output path");std::ofstream out(argv[1],std::ios::binary);check(bool(out),"open");
  uint32_t seed=0x16478049;unsigned cases=0,nonfinite=0,invalid=0,ties=0,rounded_ties=0,invalid_routes=0;
  for(unsigned scenario=0;scenario<576;++scenario)for(auto type:{flash::Scalar::f32,flash::Scalar::bf16})for(unsigned no:{2u,4u}){
    std::array<float,512>x;std::array<uint16_t,512> xb;
    for(unsigned i=0;i<512;++i){
      float v=float(int(next(seed)%65537)-32768)/257.f;
      switch(scenario%16){
        case 0:v=0;break;case 1:v=float(i%7);break;
        case 2:v=i<502?-100.f:100.f;break;case 3:v=i==511?80.f:-80.f;break;
        case 4:v=std::bit_cast<float>(0x3f800000u+i%23);break;
        case 5:v=i%2?-0.f:0.f;break;case 6:v=std::bit_cast<float>(1u+i);break;
        case 7:v=float(511-i);break;case 8:v=float(i);break;
        case 9:v=float(int(next(seed)%5)-2);break;
        // Distinct subnormal logits collapse to identical probabilities.
        case 10:v=std::bit_cast<float>(1u+(511-i));break;
        default:break;
      }
      x[i]=v;xb[i]=iq3::bf16_bits(v);
    }
    bool bad=scenario>=512;
    if(bad){unsigned where=(scenario-512)*8+(scenario%8);
      uint32_t bits[]={0x7fc12345u,0x7f800000u,0xff800000u,0x7fa12345u};
      x[where]=std::bit_cast<float>(bits[scenario%4]);xb[where]=uint16_t(bits[scenario%4]>>16);++nonfinite;}
    State a,b;
    if(scenario==510)a.active=b.active=0;
    if(scenario==511)a.error=b.error=7;
    auto before=b.bytes(false);
    void* input=type==flash::Scalar::f32?static_cast<void*>(x.data()):xb.data();
    p164_original(a.args(input,type,no));p164::epilogue(b.args(input,type,no));
    check(a.bytes()==b.bytes(),"original/candidate byte mismatch");
    if(bad)check(b.error==1 && b.bytes(false)==before,"nonfinite publication");
    if(scenario<510&&(scenario%16==0||scenario%16==5||scenario%16==6||scenario%16==10)){
      for(unsigned i=0;i<10;++i)check(b.ids[i]==int(i),"lower ID tie rule");++ties;
      if(scenario%16==10)++rounded_ties;
    }
    auto bytes=b.bytes();out.write(bytes.data(),bytes.size());++cases;
  }
  for(unsigned n=0;n<18;++n){
    std::array<float,512>x{};State b;auto a=b.args(x.data(),flash::Scalar::f32,4);auto before=b.bytes();
    switch(n){
      case 0:a.n=511;break;case 1:a.top=9;break;case 2:a.mid=641;break;case 3:a.h=2559;break;
      case 4:a.no=3;break;case 5:a.input=nullptr;break;case 6:a.scratch=nullptr;break;
      case 7:a.error=nullptr;break;case 8:a.active=nullptr;break;case 9:a.input_type=flash::Scalar::i32;break;
      case 10:a.output_type[1]=flash::Scalar::bf16;break;case 11:a.output[0]=nullptr;break;
      case 12:a.output[1]=a.output[0];break;case 13:a.output[0]=x.data();break;
      case 14:a.output[0]=b.scratch.data();break;case 15:a.output[0]=&b.error;break;
      case 16:a.output[0]=reinterpret_cast<char*>(b.ids.data())+1;break;
      case 17:a.output[3]=b.up.data()+1;break;
    }
    bool refused=false;try{p164::epilogue(a);}catch(const std::invalid_argument&){refused=true;}
    check(refused&&b.bytes()==before,"invalid route ABI wrote output");++invalid;
  }
  for(unsigned n=0;n<5;++n){
    std::array<float,512>x{};State b;auto before=b.bytes();auto a=b.args(x.data(),flash::Scalar::f32,4);
    std::array<unsigned,11>ids{0,1,2,3,4,5,6,7,8,9,10};unsigned count=10;
    if(n==0)ids[9]=512;if(n==1)ids[9]=~0u;if(n==2)ids[9]=ids[0];if(n==3)count=9;if(n==4)count=11;
    bool refused=false;try{p164::publish(a,std::span<const unsigned>(ids.data(),count));}catch(const std::invalid_argument&){refused=true;}
    check(refused&&b.bytes()==before,"invalid selected route wrote output");++invalid_routes;
  }
  std::cout<<"{\"passed\":true,\"pid\":"<<getpid()<<",\"cases\":"<<cases
           <<",\"nonfinite\":"<<nonfinite<<",\"invalid_abi\":"<<invalid
           <<",\"tie_cases\":"<<ties<<",\"rounded_tie_cases\":"<<rounded_ties<<",\"invalid_selected_routes\":"<<invalid_routes
           <<",\"device_executed\":false,\"router_gemv_tested\":false}\n";
  return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
