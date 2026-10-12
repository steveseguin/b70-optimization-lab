#pragma once
// Shared G4 bindings: host gate and device harness instantiate this same code.
#include "fused.hpp"
#include "../packet29-merged/arithmetic.hpp"
#include <vector>
using p39::Kind;using iq3::Type;
template<class Backend> struct Fixture {
 Backend& q;std::vector<void*> allocations;std::vector<std::pair<void*,std::vector<uint8_t>>> initial;
 p39::Bound b{};std::vector<const uint8_t*> weights,peers;size_t weight_bytes=0;unsigned rotations=1;
 template<class T>T* alloc(size_t n){auto p=q.template alloc<T>(n);if(!p)throw std::bad_alloc();allocations.push_back(p);return p;}
 template<class T>T* data(std::vector<T> v,bool reset=true){auto p=alloc<T>(v.size());q.copy(p,v.data(),v.size()*sizeof(T));if(reset){std::vector<uint8_t> bytes(v.size()*sizeof(T));std::memcpy(bytes.data(),v.data(),bytes.size());initial.push_back({p,std::move(bytes)});}return p;}
 void reset(){for(auto& [p,v]:initial)q.copy(p,v.data(),v.size());q.wait();}
 std::vector<uint8_t> snapshot(){std::vector<uint8_t> v;for(auto [p,n]:std::vector<std::pair<const void*,size_t>>{{b.y,size_t(b.rows)*b.count*2},{b.py,size_t(b.rows)*b.count*2},{b.out,size_t(b.rows)*b.count*2},{b.streams,size_t(b.rows)*4*2},{b.status,b.count*4},{b.peer_status,b.count*4},{b.error,4},{b.history,size_t(b.rows)*3*2}}){size_t offset=v.size();v.resize(offset+n);q.copy(v.data()+offset,p,n);}return v;}
 void release(){q.wait();for(auto p:allocations)q.free(p);allocations.clear();}
 Fixture(Backend& queue):q(queue){}
 // No implicit teardown before failure.json is durable. release() is explicit.
 template<Type T,unsigned K,Kind E>void init(unsigned rows){
  constexpr bool paired=E==Kind::expert_act||E==Kind::expert_checks,routed=paired||E==Kind::down_status;
  b.rows=rows;b.count=routed?10:1;b.experts=routed?512:1;
  b.rb=integrated::arithmetic::row_bytes(T,K,(T==Type::Q6_K||T==Type::Q8_0)?6:2);weight_bytes=size_t(b.rb)*b.rows*b.experts;
  rotations=weight_bytes*(paired?2:1)>8*1024*1024?8:1;
  // Entire production bank, not just selected expert rows; rotate complete banks.
  std::vector<uint8_t> host;
  if constexpr(!Backend::binding_only)host.resize(weight_bytes);uint32_t state=0x39c0ffee;
  for(auto& byte:host){state=state*1664525u+1013904223u;byte=uint8_t(state>>24);}
  unsigned block=T==Type::Q8_0||T==Type::IQ4_NL?32:256;
  unsigned block_bytes=b.rb/(K/block);
  if constexpr(!Backend::binding_only){
  if constexpr(T==Type::Q6_K||T==Type::Q8_0){constexpr unsigned group=T==Type::Q6_K?16:32;for(unsigned row=0;row<b.rows*b.experts;++row)for(unsigned j=0;j<K/group;++j){float scale=0.015625f;std::memcpy(host.data()+size_t(row)*b.rb+K+j*4,&scale,4);}}
  else for(size_t i=0;i<host.size();i+=block_bytes){host[i]=0;host[i+1]=0x24;}
  }
  for(unsigned j=0;j<rotations;++j){auto p=alloc<uint8_t>(weight_bytes);if constexpr(!Backend::binding_only)q.copy(p,host.data(),host.size());weights.push_back(p);}
  if(paired){for(auto& byte:host)byte^=0x35;for(size_t i=0;i<host.size();i+=block_bytes){host[i]=0;host[i+1]=0x24;}for(unsigned j=0;j<rotations;++j){auto p=alloc<uint8_t>(weight_bytes);if constexpr(!Backend::binding_only)q.copy(p,host.data(),host.size());peers.push_back(p);}}
  else peers=weights;
  b.w=weights[0];b.peer=peers[0];
  std::vector<uint16_t>x(static_cast<size_t>(K)*(E==Kind::down_status?b.count:1));for(size_t i=0;i<x.size();++i)x[i]=iq3::bf16_bits(float(int(i%17)-8)/32.f);
  b.x=data(x,true);size_t n=size_t(rows)*b.count;
  b.y=data(std::vector<uint16_t>(n,0x7e31));b.py=data(std::vector<uint16_t>(n,0x7e32));b.out=data(std::vector<uint16_t>(n,0x7e33));
  b.other=data(std::vector<uint16_t>(n,0x3e80),false);b.mixture=data(std::vector<uint16_t>(n,0x3f00),false);b.shared_gate=data(std::vector<uint16_t>(1,0x3e40),false);
  b.inject=data(std::vector<uint16_t>{0x3f00,0xbe80,0x3e00,0xbf00},false);b.streams=data(std::vector<uint16_t>(rows*4,0x3d80));
  b.status=data(std::vector<uint32_t>(b.count,0));b.peer_status=data(std::vector<uint32_t>(b.count,0));b.error=data(std::vector<uint32_t>(1,0));b.active=data(std::vector<uint32_t>(1,1));
  std::vector<iq3::Route> routes(b.count);for(unsigned i=0;i<b.count;++i)routes[i]={i*37,0,rows};b.routes=data(routes);
  std::vector<float> conv(size_t(rows)*4);for(size_t i=0;i<conv.size();++i)conv[i]=float(int(i%7)-3)/16.f;b.conv_weights=data(conv,false);std::vector<uint16_t> history(size_t(rows)*3);for(size_t i=0;i<history.size();++i)history[i]=iq3::bf16_bits(float(int(i%11)-5)/8.f);b.history=data(history);
  b.scratch=alloc<float>(n*8);b.one=data(std::vector<float>{1.f},false);b.position=data(std::vector<uint32_t>{0},true);
 }
};

template<class Visitor> void g4_cases(Visitor visit){
 visit.template operator()<Type::IQ2_S,2560,Kind::expert_act,1>("expert-act-iq2",640,47,3);
 visit.template operator()<Type::IQ3_S,2560,Kind::expert_act,1>("expert-act-iq3",640,1,3);
 visit.template operator()<Type::IQ2_S,2560,Kind::expert_checks,1>("expert-checks-iq2",640,47,2);
 visit.template operator()<Type::IQ3_S,2560,Kind::expert_checks,1>("expert-checks-iq3",640,1,2);
 visit.template operator()<Type::IQ4_NL,640,Kind::down_status,1>("down-status",2560,48,1);
 visit.template operator()<Type::Q8_0,10240,Kind::silu_div4,4>("hc-low-act",320,97,1);
 visit.template operator()<Type::Q6_K,2560,Kind::shared_act,4>("shared-up-act-q6",640,47,1);
 visit.template operator()<Type::Q8_0,2560,Kind::shared_act,1>("shared-up-act-q8",640,1,1);
 visit.template operator()<Type::Q8_0,640,Kind::shared_combine,1>("shared-down-combine",2560,48,2);
 visit.template operator()<Type::Q6_K,2560,Kind::gdn_conv,1>("gdn-qkv-conv-q6",10240,35,1);
 visit.template operator()<Type::Q8_0,2560,Kind::gdn_conv,1>("gdn-qkv-conv-q8",10240,1,1);
 visit.template operator()<Type::Q6_K,6144,Kind::attention_combine,4>("attention-combine",2560,48,1);
}
