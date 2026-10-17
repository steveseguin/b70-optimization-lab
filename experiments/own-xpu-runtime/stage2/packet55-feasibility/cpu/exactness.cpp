#include "fixtures.hpp"
#include <iostream>
#include <iomanip>

using namespace p55cpu;
namespace {
uint64_t checks=0,hash=1469598103934665603ULL,exception_checks=0;
void check(bool ok,const char* message){++checks;if(!ok)throw std::runtime_error(message);}
template<Type T,unsigned K> void rows(const uint8_t* w,const uint16_t* x){
 alignas(32) float result[8],lanes[32*8];dot8<T,K>(w,x,result,lanes);
 const unsigned rb=K/iq3::layout(T).elements*iq3::layout(T).bytes;
 for(unsigned r=0;r<8;++r){auto expected=production_lanes<T,K>(w+r*rb,x);
  for(unsigned lane=0;lane<32;++lane)check(std::bit_cast<uint32_t>(lanes[lane*8+r])==std::bit_cast<uint32_t>(expected[lane]),"FP32 logical lane differs from packet49c production");
  const float reduced=iq3::tree32(expected.data());
  check(std::bit_cast<uint32_t>(result[r])==std::bit_cast<uint32_t>(reduced),"SG32 tree bytes differ");
  check(iq3::bf16_bits(result[r])==iq3::bf16_bits(reduced),"BF16 dot boundary differs");
 }
}
template<Type T> void format(){
 for(unsigned id:{0u,37u,333u}){
  auto e=fixture_expert(T,id);
  for(unsigned change:{0u,1u,7u}){
   auto x=fixture_input(change);Output got;uint32_t error=0;
   check(execute(e,x,got,error)&&!error,"finite expert rejected");const auto ref=oracle<T>(e,x);
   check(got.gate==ref.gate,"gate bytes differ");check(got.up==ref.up,"up bytes differ");
   check(got.activation==ref.activation,"detmath SiLU/BF16 bytes differ");check(got.down==ref.down,"down bytes differ");hash=digest(got,hash);
   rows<T,hidden>(e.gate.data()+8*e.stride(),x.data());rows<Type::IQ4_NL,intermediate>(e.down.data()+1272*360,got.activation.data());
  }
  for(unsigned mode=0;mode<2;++mode){auto x=fixture_input();constexpr uint16_t edge[]={0,0x8000,1,0x8001,0x007f,0x807f,0x0080,0x8080};
   for(unsigned i=0;i<hidden;++i)x[i]=edge[i%(mode?8:2)];rows<T,hidden>(e.gate.data(),x.data());
  }
  Output original;original.down.fill(0x5577);Output output=original;
  for(uint16_t bad:{uint16_t(0x7f80),uint16_t(0xff80),uint16_t(0x7fc1),uint16_t(0xffc2),uint16_t(0x7f81)}){
   auto x=fixture_input();x[3]=bad;uint32_t error=0;
   check(!execute(e,x,output,error)&&error==1&&output==original,"exception guard publishes output");
   // Arithmetic parity is also tested below the transaction boundary; no NaN
   // tolerance or canonicalization. Device status semantics remain separate.
   rows<T,hidden>(e.gate.data(),x.data());++exception_checks;
   std::array<uint16_t,intermediate> down_input{};for(unsigned i=0;i<intermediate;++i)down_input[i]=x[i];
   rows<Type::IQ4_NL,intermediate>(e.down.data(),down_input.data());++exception_checks;
  }
  auto x=fixture_input();uint32_t error=7;check(!execute(e,x,output,error)&&error==7&&output==original,"sticky error changed");
  error=0;check(!execute(e,x,output,error,false)&&!error&&output==original,"inactive changed output");
  auto broken=e;broken.gate.pop_back();error=0;check(!execute(broken,x,output,error)&&error==1&&output==original,"shape failure publishes output");
  e.gate[0]=1;e.gate[1]=0x7c;bool refused=false;try{e.validate();}catch(const std::invalid_argument&){refused=true;}check(refused,"nonfinite weights admitted");
 }
}
template<Type T,unsigned K> void scale_edges(){
 const auto fmt=iq3::layout(T);auto w=fixture_slice(T,K,8,17);
 constexpr uint16_t scales[]={0,0x8000,1,0x8001,0x03ff,0x83ff,0x0400,0x8400,0x7bff,0xfbff};
 constexpr uint16_t edges[]={0,0x8000,1,0x8001,0x007f,0x807f,0x0080,0x8080};
 for(auto scale:scales)for(unsigned mode=0;mode<3;++mode){
  for(size_t b=0;b<w.size();b+=fmt.bytes){w[b]=scale;w[b+1]=scale>>8;}
  std::array<uint16_t,K> x{};for(unsigned i=0;i<K;++i)x[i]=mode?edges[i%(mode==1?2:8)]:iq3::bf16_bits(float(int(i%17)-8)/32.f);
  rows<T,K>(w.data(),x.data());
 }
}
}
int main(){try{
 require_environment();format<Type::IQ2_S>();format<Type::IQ3_S>();
 // Same 18 complete G4 expert/input cases and byte concatenation as retained
 // packet46 evidence, providing an independent frozen output cross-check.
 check(hash==0x0ea0eeaa89bce627ULL,"existing packet46 fixture output digest differs");
 scale_edges<Type::IQ2_S,hidden>();scale_edges<Type::IQ3_S,hidden>();scale_edges<Type::IQ4_NL,intermediate>();
 std::cout<<"{\"schema\":\"p55.cpu-exactness.v1\",\"passed\":true,\"checks\":"<<checks
  <<",\"complete_experts\":18,\"complete_bf16_values\":80640,\"raw_exception_cases\":"<<exception_checks
  <<",\"ordinary_packet49c_production_exact\":true,\"layer2_packet49c_p28_exact\":true,\"packet46_frozen_digest_match\":true,\"nonfinite_transaction_rejected\":true,\"device_exception_status_qualified\":false,\"device_executed\":false,\"model_weights_read\":false,\"output_fnv64\":\""<<std::hex<<hash<<"\"}\n";
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
