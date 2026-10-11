#pragma once
// Thin fixture adapter around the frozen packet4 Core. No candidate arithmetic.
// One row per invocation bounds scratch and native single_task duration.
#include "kernels.hpp"
#include "../packet4/core.hpp"
namespace ng::reference {
inline constexpr size_t scratch_floats = 64ull * 1024 * 1024;
inline void row(Shape s, Args a, int r, float* scratch) {
 using integrated::Op;
 if (!a.i(15)[1] || a.i(15)[2]) return;
 int pos=a.i(15)[0];
 if(pos<0 || pos>s.capacity-s.tokens){a.i(15)[2]=1;return;}
 integrated::Core c;
 c.pool={scratch,0,scratch_floats,0};c.position=pos+r;
 c.g.context=s.capacity;c.g.budget=s.budget;c.packed_heads=s.flags&4;
 auto input=[&](int dst,int slot,int offset,int n,bool f32=false,bool i32=false){
  c.inputs[dst]=c.make(n);for(int j=0;j<n;++j)c.inputs[dst][j]=i32?float(a.i(slot)[offset+j]):f32?a.f(slot)[offset+j]:a.b(slot,offset+j);
 };
 auto output=[&](int src,int slot,int offset,bool f32=false,bool i32=false){
  if(c.failed||c.pool.failed){a.i(15)[2]=1;return;}
  for(size_t j=0;j<c.out(src).size();++j){float v=c.out(src)[j];if(i32)a.i(slot)[offset+j]=int32_t(v);else if(f32)a.f(slot)[offset+j]=v;else a.put(slot,offset+j,v);}
 };
 auto weight=[&](int dst,int slot,int n,bool unit=false,bool decay=false){
  auto w=c.make(n);
  for(int j=0;j<n;++j){float v=a.weight(slot,j,s.flags);if(decay)v=(s.flags&2)?a.f(slot)[j]:-std::exp(v);if(unit)v=v+float(bool(s.flags&1));w[j]=v;}
  c.weights[dst]={reinterpret_cast<const uint8_t*>(w.p),iq3::Type::F32,size_t(n)};
 };
 int W=s.width,H=s.heads;
 switch(s.op){
 case conv:{int hist=3*(s.extra?s.extra:1);c.op=Op::conv;c.s[0]=W;c.l.parameter=s.extra?s.extra:1;
  input(0,0,r*W,W);input(1,r?4:1,0,W*hist);weight(0,2,W*4);c.run();output(0,3,r*W);output(1,4,0);break;}
 case gdn:
  c.op=Op::gdn;c.s[0]=16;c.s[1]=48;c.s[2]=128;
  input(0,0,r*10240,10240);input(1,1,r*48,48);input(2,2,r*48,48);input(3,r?7:5,0,48*128*128);
  weight(0,3,48,false,true);weight(1,4,48);c.run();output(0,6,r*6144);output(1,7,0);break;
 case norm:
  c.op=Op::norm;c.s[1]=W;c.l.parameter=bool(s.flags&1);input(0,0,r*H*W,H*W);weight(0,1,H*W);c.run();output(0,2,r*H*W);break;
 case activation:
  c.op=s.extra?Op::silu_product:Op::silu_div4;input(0,0,r*W,W);if(s.extra)input(1,1,r*W,W);c.run();output(0,2,r*W);break;
 case mix:
  c.op=Op::hc_mix;c.s[1]=W;input(0,0,r*4*W,4*W);input(1,1,r*4*W,4*W);c.run();output(0,2,r*W);break;
 case combine_norm:
  c.op=Op::hc_combine;c.s[1]=W;input(0,0,r*H*W,H*W);input(1,1,r*W,W);input(2,2,r*H,H);c.run();output(0,4,r*H*W);
  c.in(0)=c.out(0);c.op=Op::norm;c.l.parameter=bool(s.flags&1);weight(0,3,H*W);c.run();output(0,5,r*H*W);break;
 case gated_norm:
  c.op=Op::gdn_norm_gate;c.s[0]=48;c.s[1]=128;input(0,0,r*6144,6144);input(1,1,r*6144,6144);weight(0,2,128,true);c.run();output(0,3,r*6144);break;
 case route_gather:
  c.op=Op::route;c.s[1]=s.extra;c.g.experts=W;c.g.top=s.extra;input(0,0,r*W,W);c.run();
  if(c.failed){a.i(15)[2]=1;return;}
  output(0,2,r*s.extra,false,true);output(1,3,r*s.extra,true);
  c.in(0)=c.out(0);input(1,1,r*2560,2560);c.op=Op::expert_gather;c.run();output(0,5,r*s.extra*3,false,true);output(1,6,r*s.extra*3,false,true);output(2,4,r*s.extra*2560);break;
 case moe_combine:
  c.op=Op::moe_combine;c.s[0]=s.extra;c.s[1]=W;input(0,0,r*s.extra*W,s.extra*W);input(1,1,r*s.extra,s.extra,true);input(2,2,r*W,W);input(3,3,r,1);c.run();output(0,4,r*W);break;
 case prepare:
  c.op=Op::qsa_prepare;input(0,0,r*24*512,24*512);input(1,1,r*512,512);input(2,2,r*512,512);
  weight(0,3,256,true);weight(1,4,256,true);weight(2,5,128,true);c.run();output(0,6,r*6144);output(1,7,r*6144);output(2,8,r*512);output(3,9,r*512);break;
 case pool:
  c.op=Op::qsa_append_pool;input(0,0,r*512,512);input(1,1,r*512,512);input(2,2,r*128,128);weight(0,3,128,true);
  for(int j=0;j<4;++j){int n=j<2?s.capacity*512:j==2?s.capacity*128:((s.capacity+3)/4)*128;c.out(j)=c.make(n);for(int k=0;k<n;++k)c.out(j)[k]=a.b(4+j,k);}
  c.run();for(int j=0;j<4;++j)output(j,4+j,0);break;
 case select:
  c.op=Op::qsa_select;input(0,0,r*512,512);input(1,1,0,((s.capacity+3)/4)*128);c.run();output(0,2,r*(s.budget+3),false,true);break;
 case attention_score:{
  c.op=Op::qsa_attention;int slots=s.budget+3;
  input(0,0,r*6144,6144);input(1,1,r*6144,6144);input(2,2,0,s.capacity*512);input(3,3,0,s.capacity*512);input(4,4,r*slots,slots,false,true);
  // Core::run supplies final bytes. Core::dot/tree supply exposed scratch
  // intermediates (the interpreter does not expose these as outputs).
  size_t mark=c.pool.used;
  for(int h=0;h<24;++h){c.pool.used=mark;auto scores=c.make();
   for(int j=0;j<std::min(s.capacity,slots);++j)a.f(6)[(r*24+h)*slots+j]=-INFINITY;
   for(float id:c.in(4))if(id>=0){if(id>=s.capacity||id>pos+r){a.i(15)[2]=1;return;}
    scores.push_back(c.dot(c.in(2).span().subspan((int(id)*2+h/12)*256,256),c.in(0).span().subspan(h*256,256))/std::sqrt(float(c.g.ad)));}
   for(size_t j=0;j<scores.size();++j)a.f(6)[(r*24+h)*slots+j]=scores[j];
   float m=*std::max_element(scores.begin(),scores.end());for(auto& v:scores)v=std::exp(v-m);float den=c.tree(scores);
   for(size_t j=0;j<scores.size();++j)a.f(7)[(r*24+h)*slots+j]=scores[j]/den;
  }
  c.pool.used=mark;c.run();output(0,5,r*6144);break;}
 default:a.i(15)[2]=1;
 }
 if(c.failed||c.pool.failed)a.i(15)[2]=1;
}
inline void cpu(Shape s,Args a){std::vector<float> scratch(scratch_floats);for(int r=0;r<s.tokens;++r)row(s,a,r,scratch.data());}
} // namespace ng::reference
