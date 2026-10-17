#pragma once
#include "recurrence.hpp"
#include <cstring>
#include <string>
#include <vector>
namespace p54test {
struct RecurrenceFixture {
 ng::Shape s{};std::array<std::vector<uint8_t>,19> bytes;
 bool alias=false;
 RecurrenceFixture(int flags,int tokens) {
  s.op=ng::gdn;s.flags=flags;s.tokens=tokens;s.capacity=128;
  for(auto& b:bytes)b.resize(4);
  bytes[0].resize(10240*2*2);bytes[1].resize(48*2*2);bytes[2].resize(48*2*2);
  bytes[3].resize(48*4);bytes[4].resize(48*4);
  bytes[5].resize(6144*128*2);bytes[6].resize(6144*2*2);bytes[7].resize(6144*128*2);
  for(unsigned slot:{0u,1u,2u,5u})for(size_t j=0;j<bytes[slot].size()/2;++j) {
   // Includes both signs, exact zeros, and many BF16 mantissas.
   uint16_t v=ng::Args::bits(float(int((j*37+slot*13)%257)-128)/512.f);
   std::memcpy(bytes[slot].data()+j*2,&v,2);
  }
  for(unsigned h=0;h<48;++h) {
   if(flags&2){float av=-0.125f-float(h)/512.f;std::memcpy(bytes[3].data()+h*4,&av,4);}
   else if(flags&8){float av=-1.f+float(h)/64.f;std::memcpy(bytes[3].data()+h*4,&av,4);}
   else {uint16_t av=ng::Args::bits(-1.f+float(h)/64.f);std::memcpy(bytes[3].data()+h*2,&av,2);}
   float dt=float(int(h%9)-4)/16.f;
   if(flags&8)std::memcpy(bytes[4].data()+h*4,&dt,4);
   else {uint16_t v=ng::Args::bits(dt);std::memcpy(bytes[4].data()+h*2,&v,2);}
  }
  std::fill(bytes[6].begin(),bytes[6].end(),0xa5);std::fill(bytes[7].begin(),bytes[7].end(),0x5a);
  set(18,1);set(17,31);
 }
 void set(unsigned slot,int32_t v){std::memcpy(bytes[slot].data(),&v,4);}
 ng::Args args(){ng::Args a;for(unsigned j=0;j<19;++j)a.p[j]=bytes[j].data();if(alias)a.p[7]=a.p[5];return a;}
};
// The unchanged production row equation, using specialised::dot128 rather than
// the candidate's tree helper or shared-input schedule. Only the row range is
// bounded here; the full-shape benchmark calls round2::gdn_host itself.
inline void recurrence_reference_rows(ng::Shape s,ng::Args a,unsigned first,unsigned count) {
 if(!a.i(18)[0]||a.i(15)[0])return;
 int pos=a.i(17)[0];if(pos<0||pos>s.capacity-s.tokens){a.i(15)[0]=1;return;}
 for(unsigned g=first;g<first+count;++g) {
  unsigned h=g/128,j=g%128,key=(s.flags&4)?h%16:h/3,state=g*128;
  for(int r=0;r<s.tokens;++r) {
   unsigned qb=r*10240+key*128,kb=qb+2048;
   float qn=detmath::sqrt(specialised::dot128([&](int x){float v=a.b(0,qb+x);return v*v;})+1e-6f);
   float kn=detmath::sqrt(specialised::dot128([&](int x){float v=a.b(0,kb+x);return v*v;})+1e-6f);
   float gate=a.b(1,r*48+h)+a.weight(4,h,s.flags);
   float sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;
   float av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));
   float decay=detmath::exp(av*sp),q[128],k[128],v[128];
   for(unsigned x=0;x<128;++x){q[x]=(a.b(0,qb+x)/qn)/detmath::sqrt(float(128));k[x]=a.b(0,kb+x)/kn;v[x]=a.b(r?7:5,state+x)*decay;}
   float pred=specialised::dot128([&](int x){return v[x]*k[x];});
   float delta=(a.b(0,r*10240+4096+h*128+j)-pred)*ng::sigmoid(a.b(2,r*48+h));
   for(unsigned x=0;x<128;++x)v[x]=v[x]+delta*k[x];
   float y=specialised::dot128([&](int x){return v[x]*q[x];});
   a.put(6,(r*48+h)*128+j,y);for(unsigned x=0;x<128;++x)a.put(7,state+x,v[x]);
  }
 }
}
inline unsigned test_recurrence(std::vector<uint8_t>& digest_bytes) {
 unsigned checks=0;
 auto compare=[&](RecurrenceFixture& a,RecurrenceFixture& b,unsigned first,unsigned count) {
  for(unsigned slot=0;slot<19;++slot) {
   if(a.bytes[slot]!=b.bytes[slot])throw std::runtime_error("p54 recurrence bytes differ in slot "+std::to_string(slot));
   ++checks;
  }
  // Hash each calculated state/output byte; avoid adding unchanged megabytes
  // from unused rows to the portable arithmetic digest.
  unsigned state=a.alias?5:7;
  digest_bytes.insert(digest_bytes.end(),a.bytes[state].begin()+first*128*2,a.bytes[state].begin()+(first+count)*128*2);
  for(int r=0;r<a.s.tokens;++r)digest_bytes.insert(digest_bytes.end(),a.bytes[6].begin()+(r*6144+first)*2,a.bytes[6].begin()+(r*6144+first+count)*2);
  digest_bytes.insert(digest_bytes.end(),a.bytes[15].begin(),a.bytes[15].end());
 };
 for(int flags:{0,2,4,6,8,10,12,14})for(int tokens:{1,2}) {
  RecurrenceFixture initial(flags,tokens);
  for(unsigned head:{0u,15u,16u,47u}) {
   unsigned first=head*128+8,count=8;
   auto ref=initial,c4=initial,c8=initial;
   recurrence_reference_rows(ref.s,ref.args(),first,count);
   p54::recurrence_host_rows<4>(c4.s,c4.args(),first,count);
   p54::recurrence_host_rows<8>(c8.s,c8.args(),first,count);
   compare(c4,ref,first,count);compare(c8,ref,first,count);
  }
 }
 // Bounds, preserved sticky codes, inactive input, exact end-of-capacity M2,
 // in-place state, denormals/signed zeros, infinities and one quiet-NaN source.
 for(unsigned which=0;which<10;++which) {
  RecurrenceFixture initial(6,2);
  if(which==0)initial.set(18,0);
  if(which==1)initial.set(15,17);
  if(which==2)initial.set(17,-1);
  if(which==3)initial.set(17,127);
  if(which==4)initial.set(17,126);
  if(which==5)initial.alias=true;
  if(which>=6) {
   uint16_t value=which==6?0x8000:which==7?0x0001:which==8?0x7f80:0x7fc1;
   std::memcpy(initial.bytes[0].data(),&value,2);
  }
  auto ref=initial,c4=initial,c8=initial;
  recurrence_reference_rows(ref.s,ref.args(),0,8);
  p54::recurrence_host_rows<4>(c4.s,c4.args(),0,8);
  p54::recurrence_host_rows<8>(c8.s,c8.args(),0,8);
  compare(c4,ref,0,8);compare(c8,ref,0,8);
 }
 return checks;
}
} // namespace p54test
