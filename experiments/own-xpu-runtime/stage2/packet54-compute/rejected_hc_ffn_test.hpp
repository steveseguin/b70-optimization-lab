#pragma once
#include "hc_ffn.hpp"
#include <cstring>

// Lean host gate: small upper-tree/element fixtures, one full production
// fixture per class with M=2 exercised as two serial state transitions.
namespace p54hc_test {
struct ByteRange {std::string label;bool exceptional;size_t legacy_begin,legacy_end,begin,end;};
}
// Every fixture still requires exact candidate/control bytes in its compiler.
// Explicit nonfinite fixtures get a separately retained digest: the bound
// historical dump proves only their existing production NaN payloads differ
// across compilers. This does not admit the rejected FFN device candidate.
inline unsigned test_hc_ffn(std::vector<uint8_t>&digest_bytes,std::vector<uint8_t>&exception_bytes,std::vector<p54hc_test::ByteRange>*ranges=nullptr){
 using integrated::Op;
 unsigned checks=0;std::string detail;bool exceptional=false;size_t legacy_offset=0;
 auto require_equal=[&](const void*a,const void*b,size_t n,const char*what){if(std::memcmp(a,b,n))throw std::runtime_error(std::string(what)+detail+" first="+std::to_string(*static_cast<const uint16_t*>(a))+"/"+std::to_string(*static_cast<const uint16_t*>(b)));++checks;auto p=static_cast<const uint8_t*>(a);auto&target=exceptional?exception_bytes:digest_bytes;size_t begin=target.size();target.insert(target.end(),p,p+n);if(ranges)ranges->push_back({std::string(what)+detail,exceptional,legacy_offset,legacy_offset+n,begin,target.size()});legacy_offset+=n;};
 // Finite upper roots retain the cooperative tree; exceptional upper roots
 // take the unchanged scalar fallback. The prior Intel multiple-NaN failure
 // remains in the failed receipt; this tests its repair, not a NaN tolerance.
 for(unsigned mode=0;mode<4;++mode){exceptional=mode>=2;detail=" upper_mode="+std::to_string(mode);float v[80];for(unsigned i=0;i<80;++i)v[i]=mode==0?float(int((i*37)%127)-63)/32.f:mode==1?iq3::bits_float(i%2?0x80000000:0):mode==2?iq3::bits_float(i==16?0x7f800000:i==64?0xff800000:0x3f800000):iq3::bits_float(i==33?0x7fc12345:i==57?0xffc54321:0x3f800000);float a=specialised::upper(v,80),b=p54hc::upper80_cpu(v);require_equal(&a,&b,4,"packet54 norm upper-tree/fallback bytes");}
 for(auto kind:{p54hc::Kind::norm,p54hc::Kind::mix,p54hc::Kind::combine}){
  exceptional=false;detail=" kind="+std::to_string(int(kind));
  integrated::Spec s;s.special=integrated::Special::normal;s.g.context=4096;s.site.shape[0]=4;s.site.shape[1]=2560;s.no=1;
  s.op=kind==p54hc::Kind::norm?Op::norm:kind==p54hc::Kind::mix?Op::hc_mix:Op::hc_combine;
  s.ni=kind==p54hc::Kind::norm?1:kind==p54hc::Kind::mix?2:3;s.nw=kind==p54hc::Kind::norm?1:0;s.grids[0]=iq3::Type::F32;
  s.sizes[0]=10240;if(kind==p54hc::Kind::mix)s.sizes[1]=10240;if(kind==p54hc::Kind::combine){s.sizes[1]=2560;s.sizes[2]=4;}s.sizes[s.ni]=kind==p54hc::Kind::mix?2560:10240;
  for(int i=0;i<s.ni+s.no;++i)s.types[i]=flash::Scalar::bf16;
  std::array<std::vector<uint16_t>,3>input;for(unsigned i=0;i<unsigned(s.ni);++i){input[i].resize(s.sizes[i]);for(unsigned k=0;k<input[i].size();++k)input[i][k]=iq3::bf16_bits(float(int((k*71+i*13)%257)-128)/64.f);}
  std::vector<float>gain(10240);for(unsigned i=0;i<gain.size();++i)gain[i]=float((i*7)%17+1)/16.f;
  // A row changes the stream state before the next serial row is evaluated.
  for(unsigned row=0;row<2;++row){
   std::vector<uint16_t>expected(s.sizes[s.ni],0x4a5b),actual=expected;
   std::array<float,320>scratch_a{},scratch_b{};uint32_t ea=0,eb=0,pos=4094+row,active=1;uint16_t rope=0;
   std::vector<void*>pa,pb;for(int i=0;i<s.ni;++i){pa.push_back(input[i].data());pb.push_back(input[i].data());}pa.push_back(expected.data());pb.push_back(actual.data());if(s.nw){pa.push_back(gain.data());pb.push_back(gain.data());}
   pa.insert(pa.end(),{scratch_a.data(),&ea,&pos,&active,&rope});pb.insert(pb.end(),{scratch_b.data(),&eb,&pos,&active,&rope});
   auto control=kind==p54hc::Kind::norm?p54hc::control_norm:kind==p54hc::Kind::mix?p54hc::control_mix:p54hc::control_combine;
   auto candidate=kind==p54hc::Kind::norm?p54hc::candidate_norm:kind==p54hc::Kind::mix?p54hc::candidate_mix:p54hc::candidate_combine;
   control(s,pa);candidate(s,pb);require_equal(expected.data(),actual.data(),actual.size()*2,"packet54 HC full output bytes");require_equal(scratch_a.data(),scratch_b.data(),sizeof(scratch_a),"packet54 HC scratch bytes");require_equal(&ea,&eb,4,"packet54 HC sticky bytes");
   if(actual.size()==input[0].size())input[0]=actual;
   // Inactive, sticky and invalid-position cases must retain exact sentinels.
   for(unsigned mode=0;mode<3;++mode){active=mode==0?0:1;ea=eb=mode==1?7:0;pos=mode==2?4096:0;std::fill(expected.begin(),expected.end(),0x4a5b);std::fill(actual.begin(),actual.end(),0x4a5b);scratch_a.fill(-17.25f);scratch_b.fill(-17.25f);control(s,pa);candidate(s,pb);require_equal(scratch_a.data(),scratch_b.data(),sizeof(scratch_a),"packet54 HC control scratch bytes");require_equal(expected.data(),actual.data(),actual.size()*2,"packet54 HC control output bytes");require_equal(&ea,&eb,4,"packet54 HC control sticky bytes");}
  }
  if(kind==p54hc::Kind::norm){
   exceptional=true;
   // One mixed complete fixture: multiple payload/sign NaNs in distinct
   // partials, an infinite stream, signed zero, and an unchanged finite
   // stream. Both output and materialized partial bytes are observable.
   for(unsigned k=0;k<10240;++k)input[0][k]=iq3::bf16_bits(float(int(k%17)-8)/32.f);
   input[0][33*32]=0x7fc1;input[0][57*32]=0xffc5;
   input[0][2560+16*32]=0x7f80;input[0][2560+64*32]=0xff80;
   for(unsigned k=0;k<2560;++k)input[0][2*2560+k]=k%2?0x8000:0;
   std::vector<uint16_t>a(10240,0x4a5b),b=a;std::array<float,320>sa{},sb{};uint32_t ea=0,eb=0,pos=0,active=1;uint16_t rope=0;
   std::vector<void*>pa{input[0].data(),a.data(),gain.data(),sa.data(),&ea,&pos,&active,&rope},pb{input[0].data(),b.data(),gain.data(),sb.data(),&eb,&pos,&active,&rope};
   p54hc::control_norm(s,pa);p54hc::candidate_norm(s,pb);
   require_equal(a.data(),b.data(),a.size()*2,"packet54 norm nonfinite full output bytes");require_equal(sa.data(),sb.data(),sizeof(sa),"packet54 norm nonfinite partial bytes");require_equal(&ea,&eb,4,"packet54 norm nonfinite sticky bytes");
   exceptional=false;
  }
  // Small vector fixtures cover signed zero, infinity and NaN payloads at
  // all nonlinear input sites without another full-shape sweep.
  if(kind!=p54hc::Kind::norm){for(unsigned mode=0;mode<4;++mode){exceptional=mode>=1;detail=" kind="+std::to_string(int(kind))+" mode="+std::to_string(mode);for(unsigned stream=0;stream<4;++stream)for(unsigned k=0;k<4;++k)input[0][stream*2560+k]=mode==0?uint16_t(k%2?0x8000:0):mode==1?0x7f80:mode==2?0xff80:uint16_t(k%2?0x7fc1:0xffc5);for(int slot=1;slot<s.ni;++slot)for(unsigned k=0;k<input[slot].size();++k)input[slot][k]=mode==3?0x7fc3:iq3::bf16_bits(float(int(k%7)-3));std::vector<uint16_t>a(s.sizes[s.ni],0x4a5b),b=a;std::array<float,320>tmp{};uint32_t err=0,pos=0,active=1;uint16_t rope=0;std::vector<void*>pa,pb;for(int i=0;i<s.ni;++i){pa.push_back(input[i].data());pb.push_back(input[i].data());}pa.push_back(a.data());pb.push_back(b.data());pa.insert(pa.end(),{tmp.data(),&err,&pos,&active,&rope});pb.insert(pb.end(),{tmp.data(),&err,&pos,&active,&rope});auto ba=p54hc::bind(s,pa),bb=p54hc::bind(s,pb);if(kind==p54hc::Kind::mix){for(unsigned k=0;k<4;++k){float sum=0;for(unsigned h=0;h<4;++h)sum=sum+ng::sigmoid(ba.in(1).get(h*2560+k))*ba.in(0).get(h*2560+k);ba.out(0).put(k,sum/4.f);}p54hc::mix4(bb,0);}else{for(unsigned i=0;i<4;++i)ba.out(0).put(i,ba.in(0).get(i)+ba.in(1).get(i%2560)*(2.f*ng::sigmoid(ba.in(2).get(i/2560)/4.f)));p54hc::combine4(bb,0);}require_equal(a.data(),b.data(),8,"packet54 HC exceptional leaf bytes");}}
 }
 return checks;
}
