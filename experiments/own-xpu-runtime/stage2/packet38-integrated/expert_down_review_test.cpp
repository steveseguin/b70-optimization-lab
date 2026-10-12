// Independent CPU-only exactness probe. No SYCL/device entry or device discovery.
#include "expert_down.hpp"
#include <array>
#include <bit>
#include <cstdint>
#include <iostream>
#include <stdexcept>
namespace {
struct Counts {uint64_t checks=0,failures=0;};
Counts total,finite_counts,nonfinite,relations[3],finite_relations[3],nonfinite_relations[3];
uint64_t hash=1469598103934665603ULL,finite_hash=1469598103934665603ULL;
void equal(float a,float b,unsigned relation,const char* kind,unsigned fixture,unsigned lane,bool supported){
 auto aa=std::bit_cast<uint32_t>(a),bb=std::bit_cast<uint32_t>(b);bool differs=aa!=bb;
 for(auto* c:{&total,supported?&finite_counts:&nonfinite,&relations[relation],supported?&finite_relations[relation]:&nonfinite_relations[relation]}){++c->checks;c->failures+=differs;}
 hash^=aa;hash*=1099511628211ULL;if(supported){finite_hash^=aa;finite_hash*=1099511628211ULL;}
 if(differs&&total.failures<=16)std::cerr<<kind<<" fixture="<<fixture<<" lane="<<lane<<" supported_finite="<<supported<<" got="<<std::hex<<aa<<" expected="<<bb<<std::dec<<'\n';
}
void relation_report(const Counts (&counts)[3]){
 constexpr const char* names[]{"new_vs_r5","new_vs_scalar_v2","r5_vs_scalar_v2"};
 std::cout<<'{';for(unsigned i=0;i<3;++i){if(i)std::cout<<',';std::cout<<'"'<<names[i]<<"\":{\"checks\":"<<counts[i].checks<<",\"failures\":"<<counts[i].failures<<'}';}std::cout<<'}';
}
}
int main(){
 constexpr std::array<uint16_t,20> scales{0,0x8000,1,0x8001,0x03ff,0x83ff,0x0400,0x8400,0x3555,0xb555,0x3c00,0xbc00,0x7bff,0xfbff,0x7c00,0xfc00,0x7e01,0xfe01,0x7c01,0xfc01};
 constexpr std::array<uint16_t,16> inputs{0,0x8000,1,0x8001,0x7f,0x807f,0x80,0x8080,0x3f80,0xbf80,0x7f80,0xff80,0x7fc1,0xffc1,0x7f81,0xff81};
 unsigned fixture=0;
 for(unsigned sc=0;sc<scales.size();++sc)for(unsigned pattern=0;pattern<3;++pattern)for(unsigned im=0;im<18;++im){
  ++fixture;std::array<uint8_t,360>w{};std::array<uint16_t,640>x{};bool supported=true;
  for(unsigned block=0;block<20;++block){auto s=scales[pattern==2?(sc+block)%scales.size():sc];supported=supported&&((s&0x7c00)!=0x7c00);w[block*18]=uint8_t(s);w[block*18+1]=uint8_t(s>>8);for(unsigned c=0;c<16;++c)w[block*18+2+c]=uint8_t(((c+block)%16)|(((pattern==1?c:15-c)+block)%16<<4));}
  for(unsigned i=0;i<x.size();++i)x[i]=im<inputs.size()?inputs[im]:im==16?inputs[i%inputs.size()]:iq3::bf16_bits(float(int((i*17)%127)-63)/128.f);
  for(auto value:x)supported=supported&&((value&0x7f80)!=0x7f80);
  float newer[32]{},current[32]{},oracle[32]{};
  for(unsigned lane=0;lane<32;++lane){
   newer[lane]=p29::down_lane(w.data(),x.data(),lane);
   current[lane]=iq3::kopt3::dot<iq3::Type::IQ4_NL>(w.data(),x.data(),iq3::Type::BF16,0,640,lane,iq3::kopt3::ConstantTables{},iq3::kopt3::HostShare{});
   for(unsigned tile=lane*8;tile<640;tile+=256)for(unsigned j=0;j<8;++j){float value=iq3::element(iq3::Type::IQ4_NL,w.data(),tile+j);float input=iq3::bits_float(uint32_t(x[tile+j])<<16);float product=value*input;oracle[lane]=oracle[lane]+product;}
   equal(newer[lane],current[lane],0,"new/R5",fixture,lane,supported);equal(newer[lane],oracle[lane],1,"new/scalar-v2",fixture,lane,supported);equal(current[lane],oracle[lane],2,"R5/scalar-v2",fixture,lane,supported);
  }
  const float a=iq3::tree32(newer),b=iq3::tree32(current),c=iq3::tree32(oracle);
  equal(a,b,0,"tree/R5",fixture,0,supported);equal(a,c,1,"tree/scalar-v2",fixture,0,supported);equal(b,c,2,"tree/R5-scalar-v2",fixture,0,supported);
  const float ab=iq3::bits_float(uint32_t(iq3::bf16_bits(a))<<16),bb=iq3::bits_float(uint32_t(iq3::bf16_bits(b))<<16),cb=iq3::bits_float(uint32_t(iq3::bf16_bits(c))<<16);
  equal(ab,bb,0,"BF16/new-R5",fixture,0,supported);equal(ab,cb,1,"BF16/new-scalar-v2",fixture,0,supported);equal(bb,cb,2,"BF16/R5-scalar-v2",fixture,0,supported);
 }
 std::cout<<"{\"device_executed\":false,\"passed\":"<<(total.failures?"false":"true")<<",\"supported_finite_passed\":"<<(finite_counts.failures?"false":"true")<<",\"nonfinite_diagnostic_passed\":"<<(nonfinite.failures?"false":"true")<<",\"fixtures\":"<<fixture<<",\"checks\":"<<total.checks<<",\"failures\":"<<total.failures<<",\"finite_checks\":"<<finite_counts.checks<<",\"finite_failures\":"<<finite_counts.failures<<",\"nonfinite_checks\":"<<nonfinite.checks<<",\"nonfinite_failures\":"<<nonfinite.failures<<",\"nan_tolerance\":false,\"relations\":";relation_report(relations);std::cout<<",\"finite_relations\":";relation_report(finite_relations);std::cout<<",\"nonfinite_relations\":";relation_report(nonfinite_relations);std::cout<<",\"finite_hash\":\""<<std::hex<<finite_hash<<"\",\"hash\":\""<<hash<<"\"}\n";
 // Overall failure is preserved even if a mismatch is outside the finite_counts contract.
 return total.failures?1:0;
}
