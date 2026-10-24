#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet6-kopt/reference.hpp"
#include "policy.hpp"
#include <array>
#include <cstring>
#include <iostream>
#include <vector>
using namespace iq3;
size_t checks=0;
void need(bool v,const char* why){++checks;if(!v)throw std::runtime_error(why);}
uint32_t bits(float v){uint32_t x;std::memcpy(&x,&v,4);return x;}
// Literal scalar address simulation of the frozen cooperative stage_row. It
// validates byte coverage only; it does not claim CPU/SYCL vector equivalence.
void stage(const uint8_t* src,uint8_t* dst,size_t n){
 size_t prefix=(16-(reinterpret_cast<uintptr_t>(src)&15))&15;prefix=prefix<n?prefix:n;
 for(unsigned lane=0;lane<32;++lane){
  for(size_t i=lane;i<prefix;i+=32)dst[i]=src[i];
  size_t vectors=(n-prefix)/16;
  for(size_t j=lane;j<vectors;j+=32)for(unsigned i=0;i<16;++i)dst[prefix+j*16+i]=src[prefix+j*16+i];
  for(size_t i=prefix+vectors*16+lane;i<n;i+=32)dst[i]=src[i];
 }
}
float direct(const uint8_t* p,const uint16_t* x){return kopt::row_t<Type::IQ4_NL>(p,x,Type::BF16,640,32);}
int main(){try{
 constexpr size_t rb=360,k=640;
 std::array<uint16_t,k> x{};for(size_t i=0;i<k;++i)x[i]=uint16_t(0x3e00+(i%97));
 const uint16_t scales[]={0,0x8000,1,0x8001,0x03ff,0x0400,0x3c00,0xbc00,0x7bff,0xfbff,0x7c00,0xfc00,0x7e11,0xfe11,0x7c01,0xfc01};
 for(unsigned offset=0;offset<16;++offset)for(auto h:scales){
  alignas(16) std::array<uint8_t,rb+32> raw{};auto src=raw.data()+offset;
  for(unsigned b=0;b<20;++b){src[b*18]=h&255;src[b*18+1]=h>>8;for(unsigned j=2;j<18;++j)src[b*18+j]=uint8_t(b*17+j*13);}
  alignas(16) std::array<uint8_t,rb+32> local;local.fill(0xa5);stage(src,local.data()+16,rb);
  need(!std::memcmp(src,local.data()+16,rb),"stage exact row bytes");
  for(unsigned j=0;j<16;++j)need(local[j]==0xa5&&local[rb+16+j]==0xa5,"row staging bounds");
  for(unsigned lane=0;lane<32;++lane)need(bits(kopt::lane_dot<Type::IQ4_NL>(src,x.data(),Type::BF16,k,lane,32))==bits(kopt::lane_dot<Type::IQ4_NL>(local.data()+16,x.data(),Type::BF16,k,lane,32)),"lane bits");
  auto a=direct(src,x.data()),b=direct(local.data()+16,x.data());need(bits(a)==bits(b),"tree bits");need(output_bits(a,Type::BF16)==output_bits(b,Type::BF16),"BF16 bits");
 }
 // Compact backing geometry exercises identical routed byte addresses, mixed
 // groups, duplicate experts, invalid routes, zero-length valid and tails.
 constexpr unsigned rows=8,experts=3,span=8,count=10;
 std::vector<uint8_t> bank(experts*rows*rb);for(size_t i=0;i<bank.size();++i)bank[i]=uint8_t(i*13+7);
 std::array<Route,count> routes{{{0,0,8},{2,2,3},{1,8,0},{3,0,1},{0,7,2},{2,0,8},{2,0,8},{0,0,0},{UINT32_MAX,0,1},{1,1,7}}};
 std::array<uint32_t,count> status{};std::array<uint16_t,count*span+2> out{};out.fill(0x1357);
 for(unsigned group=0;group<(count*span+3)/4;++group)for(unsigned subgroup=0;subgroup<4;++subgroup){
  size_t logical=group*4+subgroup,slot=logical/span,row=logical%span;bool in_range=slot<count;
  Route r{0,0,rows};if(in_range)r=routes[slot];bool valid=in_range&&valid_route(r,experts,rows,span),active=valid&&row<r.row_count;
  if(in_range&&row==0)status[slot]=valid?0:1;
  float sum=0;if(active){size_t offset=(size_t(r.expert_id)*rows+r.row_begin+row)*rb;need(offset+rb<=bank.size(),"route extent");
   std::array<uint8_t,rb> local{};stage(bank.data()+offset,local.data(),rb);sum=direct(bank.data()+offset,x.data());need(bits(sum)==bits(direct(local.data(),x.data())),"routed staged/global equality");}
  if(in_range)out[1+logical]=output_bits(active?sum:bits_float(0x7fc00000),Type::BF16);
 }
 need(out.front()==0x1357&&out.back()==0x1357,"output bounds");
 for(unsigned slot=0;slot<count;++slot){bool valid=valid_route(routes[slot],experts,rows,span);need(status[slot]==unsigned(!valid),"status");for(unsigned row=0;row<span;++row)if(!valid||row>=routes[slot].row_count)need(out[1+slot*span+row]==0x7fc0,"tail/invalid NaN");}
 need(status[2]==0&&status[7]==0,"zero row_count valid status");
 std::array<size_t,10> good{20,512,2560,640,10,2560,30,30,32,0};
 auto admit=[](const auto& a){gsq_iq4_direct::policy(a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],a[9]);};
 admit(good);need(true,"actual geometry accepted");
 for(unsigned i=0;i<good.size();++i){auto bad=good;++bad[i];bool refused=false;try{admit(bad);}catch(const std::invalid_argument&){refused=true;}need(refused,"narrow geometry guard");}
 std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"scope\":\"CPU address/staging and inherited arithmetic; no native execution\"}\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
