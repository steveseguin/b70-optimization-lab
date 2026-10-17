#pragma once
#include "hc_ffn.hpp"
#include <cstring>

// Active gate: HC mix only. Closed norm/FFN tests and all their byte checks
// are retained verbatim in rejected_hc_ffn_test.hpp, with failed receipts.
// Mix keeps its full M=1/M=2 fixture, guards, scratch and four special leaves.
namespace p54hc_test {
struct ByteRange {std::string label;bool exceptional;size_t legacy_begin,legacy_end,begin,end;};
}
// Every active mix fixture still requires exact candidate/control bytes.
// Explicit nonfinite leaves retain their separate diagnostic digest.
inline unsigned test_hc_ffn(std::vector<uint8_t>&digest_bytes,std::vector<uint8_t>&exception_bytes,std::vector<p54hc_test::ByteRange>*ranges=nullptr){
 using integrated::Op;
 unsigned checks=0;std::string detail;bool exceptional=false;size_t legacy_offset=0;
 auto require_equal=[&](const void*a,const void*b,size_t n,const char*what){if(std::memcmp(a,b,n))throw std::runtime_error(std::string(what)+detail+" first="+std::to_string(*static_cast<const uint16_t*>(a))+"/"+std::to_string(*static_cast<const uint16_t*>(b)));++checks;auto p=static_cast<const uint8_t*>(a);auto&target=exceptional?exception_bytes:digest_bytes;size_t begin=target.size();target.insert(target.end(),p,p+n);if(ranges)ranges->push_back({std::string(what)+detail,exceptional,legacy_offset,legacy_offset+n,begin,target.size()});legacy_offset+=n;};
 for(auto kind:{p54hc::Kind::mix}){
  exceptional=false;detail=" kind="+std::to_string(int(kind));
  integrated::Spec s;s.special=integrated::Special::normal;s.g.context=4096;s.site.shape[0]=4;s.site.shape[1]=2560;s.no=1;
  s.op=Op::hc_mix;
  s.ni=2;s.nw=0;
  s.sizes[0]=s.sizes[1]=10240;s.sizes[s.ni]=2560;
  for(int i=0;i<s.ni+s.no;++i)s.types[i]=flash::Scalar::bf16;
  std::array<std::vector<uint16_t>,3>input;for(unsigned i=0;i<unsigned(s.ni);++i){input[i].resize(s.sizes[i]);for(unsigned k=0;k<input[i].size();++k)input[i][k]=iq3::bf16_bits(float(int((k*71+i*13)%257)-128)/64.f);}
  std::vector<float>gain(10240);for(unsigned i=0;i<gain.size();++i)gain[i]=float((i*7)%17+1)/16.f;
  // A row changes the stream state before the next serial row is evaluated.
  for(unsigned row=0;row<2;++row){
   std::vector<uint16_t>expected(s.sizes[s.ni],0x4a5b),actual=expected;
   std::array<float,320>scratch_a{},scratch_b{};uint32_t ea=0,eb=0,pos=4094+row,active=1;uint16_t rope=0;
   std::vector<void*>pa,pb;for(int i=0;i<s.ni;++i){pa.push_back(input[i].data());pb.push_back(input[i].data());}pa.push_back(expected.data());pb.push_back(actual.data());if(s.nw){pa.push_back(gain.data());pb.push_back(gain.data());}
   pa.insert(pa.end(),{scratch_a.data(),&ea,&pos,&active,&rope});pb.insert(pb.end(),{scratch_b.data(),&eb,&pos,&active,&rope});
   auto control=p54hc::control_mix;
   auto candidate=p54hc::candidate_mix;
   control(s,pa);candidate(s,pb);require_equal(expected.data(),actual.data(),actual.size()*2,"packet54 HC full output bytes");require_equal(scratch_a.data(),scratch_b.data(),sizeof(scratch_a),"packet54 HC scratch bytes");require_equal(&ea,&eb,4,"packet54 HC sticky bytes");
   if(actual.size()==input[0].size())input[0]=actual;
   // Inactive, sticky and invalid-position cases must retain exact sentinels.
   for(unsigned mode=0;mode<3;++mode){active=mode==0?0:1;ea=eb=mode==1?7:0;pos=mode==2?4096:0;std::fill(expected.begin(),expected.end(),0x4a5b);std::fill(actual.begin(),actual.end(),0x4a5b);scratch_a.fill(-17.25f);scratch_b.fill(-17.25f);control(s,pa);candidate(s,pb);require_equal(scratch_a.data(),scratch_b.data(),sizeof(scratch_a),"packet54 HC control scratch bytes");require_equal(expected.data(),actual.data(),actual.size()*2,"packet54 HC control output bytes");require_equal(&ea,&eb,4,"packet54 HC control sticky bytes");}
  }
  // Small vector fixtures cover signed zero, infinity and NaN payloads at
  // all nonlinear input sites without another full-shape sweep.
  {for(unsigned mode=0;mode<4;++mode){exceptional=mode>=1;detail=" kind="+std::to_string(int(kind))+" mode="+std::to_string(mode);for(unsigned stream=0;stream<4;++stream)for(unsigned k=0;k<4;++k)input[0][stream*2560+k]=mode==0?uint16_t(k%2?0x8000:0):mode==1?0x7f80:mode==2?0xff80:uint16_t(k%2?0x7fc1:0xffc5);for(int slot=1;slot<s.ni;++slot)for(unsigned k=0;k<input[slot].size();++k)input[slot][k]=mode==3?0x7fc3:iq3::bf16_bits(float(int(k%7)-3));std::vector<uint16_t>a(s.sizes[s.ni],0x4a5b),b=a;std::array<float,320>tmp{};uint32_t err=0,pos=0,active=1;uint16_t rope=0;std::vector<void*>pa,pb;for(int i=0;i<s.ni;++i){pa.push_back(input[i].data());pb.push_back(input[i].data());}pa.push_back(a.data());pb.push_back(b.data());pa.insert(pa.end(),{tmp.data(),&err,&pos,&active,&rope});pb.insert(pb.end(),{tmp.data(),&err,&pos,&active,&rope});auto ba=p54hc::bind(s,pa),bb=p54hc::bind(s,pb);{for(unsigned k=0;k<4;++k){float sum=0;for(unsigned h=0;h<4;++h)sum=sum+ng::sigmoid(ba.in(1).get(h*2560+k))*ba.in(0).get(h*2560+k);ba.out(0).put(k,sum/4.f);}p54hc::mix4(bb,0);}require_equal(a.data(),b.data(),8,"packet54 HC exceptional leaf bytes");}}
 }
 return checks;
}
