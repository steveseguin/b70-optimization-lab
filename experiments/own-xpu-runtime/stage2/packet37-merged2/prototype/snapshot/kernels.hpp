#include "detmath.hpp"
#include "rope.hpp"
#pragma once
// Original lab non-GEMV kernels. No runtime implementation imported.
#include <array>
#include <algorithm>
#include <bit>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>
namespace ng {
enum Op { conv, gdn, norm, activation, mix, combine_norm, route_gather,
          moe_combine, gated_norm, prepare, pool, select, attention_score,
          attention_softmax, attention_value };
// All floating tensors are BF16 except F32 routing probabilities and scratch.
// Buffer slots are documented in README. Position/active/error are device data.
struct Shape { int op, tokens=1, width=2560, heads=4, extra=0, flags=0, capacity=128, budget=2048; };
struct Args {
  std::array<void*,16> p{};
  float b(int slot,size_t i) const { return std::bit_cast<float>(uint32_t(static_cast<uint16_t*>(p[slot])[i])<<16); }
  static uint16_t bits(float x) { auto u=std::bit_cast<uint32_t>(x); if((u&0x7fffffff)>0x7f800000)return uint16_t((u>>16)|64); return uint16_t((u+0x7fff+((u>>16)&1))>>16); }
  static float bf(float x){return std::bit_cast<float>(uint32_t(bits(x))<<16);}
  void put(int slot,size_t i,float x) const {static_cast<uint16_t*>(p[slot])[i]=bits(x);}
  float weight(int slot,size_t index,int flags)const{return (flags&8)?f(slot)[index]:b(slot,index);}
  float* f(int slot)const{return static_cast<float*>(p[slot]);}
  int32_t* i(int slot)const{return static_cast<int32_t*>(p[slot]);}
};
inline float sigmoid(float x){return 1.f / (1.f + detmath::exp(-x));}
inline float silu(float x){return x * sigmoid(x);}
inline int groups(Shape s){
 switch(s.op){
 case conv:return (s.width+127)/128;
 case gdn:return 48*128;
 case norm:case combine_norm:return s.tokens*s.heads;
 case activation:case mix:case moe_combine:return (s.tokens*s.width+127)/128;
 case route_gather:return s.tokens;
 case gated_norm:return s.tokens*48;
 case prepare:return s.tokens*30; // Q24 + K2 + index Q4
 case pool:return (s.capacity+3)/4+1; // last group appends KV/raw
 case select:return s.tokens;
 case attention_score:return s.tokens*24*std::min(s.capacity,s.budget+3);
 case attention_softmax:return s.tokens*24;
 case attention_value:return s.tokens*24*256;
 default:throw std::invalid_argument("unknown op");
 }
}
inline int local_floats(Shape s){
 if(s.op==gdn)return 512;
 if(s.op==route_gather)return 2048;
 if(s.op==select)return 3*((s.capacity+3)/4)+256;
 if(s.op==norm||s.op==combine_norm)return s.width;
 if(s.op==attention_softmax||s.op==attention_value)return s.budget+3;
 return 1024;
}
inline void validate(Shape s){
 if(s.op<conv||s.op>attention_value||s.tokens<1||s.tokens>87||s.width<1||s.width>10240||s.heads<1||s.heads>48||s.capacity<s.tokens||s.capacity>4096||s.budget<4||s.budget>2048||s.budget%4)throw std::invalid_argument("shape outside registered limits");
 if(s.op==conv&&s.extra!=0&&s.extra!=1&&s.extra!=3)throw std::invalid_argument("conv dilation");
 if((s.op==norm||s.op==combine_norm)&&s.width>4096)throw std::invalid_argument("norm width");
 if(s.op==route_gather&&(s.width<1||s.width>512||s.extra<1||s.extra>s.width))throw std::invalid_argument("route geometry");
}
// Validate allocation extents before submission; no device read is needed.
inline std::array<size_t,16> required_bytes(Shape s) {
 std::array<size_t,16> n{};n.fill(4);n[15]=12;
 size_t T=s.tokens,W=s.width,H=s.heads,C=s.capacity,S=s.budget+3;
 auto b=[&](int slot,size_t values){n[slot]=values*2;};
 auto f=[&](int slot,size_t values){n[slot]=values*4;};
 auto weight=[&](int slot,size_t values){n[slot]=values*((s.flags&8)?4:2);};
 switch(s.op){
 case conv:b(0,T*W);b(1,W*3*(s.extra?s.extra:1));weight(2,W*4);n[3]=n[0];n[4]=n[1];break;
 case gdn:b(0,T*10240);b(1,T*48);n[2]=n[1];n[3]=48*((s.flags&10)?4:2);weight(4,48);b(5,48*128*128);b(6,T*6144);n[7]=n[5];break;
 case norm:b(0,T*H*W);weight(1,H*W);n[2]=n[0];break;
 case activation:b(0,T*W);if(s.extra)n[1]=n[0];n[2]=n[0];break;
 case mix:b(0,T*4*W);n[1]=n[0];b(2,T*W);break;
 case combine_norm:b(0,T*H*W);b(1,T*W);b(2,T*H);weight(3,H*W);n[4]=n[5]=n[0];break;
 case route_gather:b(0,T*W);b(1,T*2560);f(2,T*s.extra);n[3]=n[2];b(4,T*s.extra*2560);f(5,T*s.extra*3);n[6]=n[5];break;
 case moe_combine:b(0,T*s.extra*W);f(1,T*s.extra);b(2,T*W);b(3,T);n[4]=n[2];break;
 case gated_norm:b(0,T*6144);n[1]=n[0];weight(2,128);n[3]=n[0];break;
 case prepare:b(0,T*24*512);b(1,T*512);b(2,T*512);weight(3,256);weight(4,256);weight(5,128);b(6,T*6144);n[7]=n[6];n[8]=n[1];n[9]=n[2];break;
 case pool:b(0,T*512);n[1]=n[0];b(2,T*128);weight(3,128);b(4,C*512);n[5]=n[4];b(6,C*128);b(7,((C+3)/4)*128);break;
 case select:b(0,T*512);b(1,((C+3)/4)*128);f(2,T*S);break;
 case attention_score:case attention_softmax:case attention_value:b(0,T*6144);n[1]=n[0];b(2,C*512);n[3]=n[2];f(4,T*S);n[5]=n[0];f(6,T*24*S);n[7]=n[6];break;
 }
 return n;
}
struct HostTeam {
 float* x;
 template<class F> void each(int n,F f)const {for(int j=0;j<n;++j)f(j);}
 void barrier()const{}
 int error(Args a)const{return a.i(15)[2];}
 void fail(Args a)const{a.i(15)[2]=1;}
 float sum(int n,int base=0)const {
  for(int stride=1;stride<n;stride*=2)for(int i=0;i<n;i+=2*stride)x[base+i]=x[base+i]+(i+stride<n?x[base+i+stride]:0.f);
  return x[base];
 }
};
// Adjacent tree and dot128 are explicit, never implementation-selected reductions.
template<class Team,class F> float dot128(Team t,F product,int base=384){
 t.each(32,[&](int lane){float v=0;for(int k=0;k<4;++k)v=v+product(4*lane+k);t.x[base+lane]=v;});t.barrier();return t.sum(32,base);
}
template<class Team,class F> float tree(Team t,int n,F value,int base=0){t.each(n,[&](int j){t.x[base+j]=value(j);});t.barrier();return t.sum(n,base);}
// Normalized row is BF16 BEFORE rotary; tables themselves round BF16.
template<class Team,class Get,class Put> void norm_rope(Team t,Get get,Put put,const Args& a,int gain,int width,int position,int flags){
 float inv=detmath::rsqrt(tree(t,width,[&](int j){float v=get(j);return v*v;})/float(width)+1e-6f);
 t.barrier();t.each(width,[&](int j){t.x[j]=Args::bf((get(j)*inv)*(a.weight(gain,j,flags)+float(flags&1)));});t.barrier();
 t.each(width,[&](int j){float v=t.x[j];if(j<64){int k=j%32;constexpr int rotary=64;float c=rope_constants::cos(position,k),z=rope_constants::sin(position,k);v=j<32?t.x[k]*c-t.x[k+32]*z:t.x[k+32]*c+t.x[k]*z;}put(j,v);});t.barrier();
}
template<class Team> void group(Shape s,Args a,int group,Team t){
 // control = {position, active, sticky_error}; no host readback.
 t.each(1,[&](int){t.x[0]=float(!a.i(15)[1]||t.error(a));});t.barrier();
 if(t.x[0])return;
 t.barrier();
 int pos=a.i(15)[0];
 if(pos<0||pos>s.capacity-s.tokens){if(group==0)t.each(1,[&](int){t.fail(a);});return;}
 bool unit=s.flags&1;
 if(s.op==gdn){
  int h=group/128,j=group%128,key=(s.flags&4)?h%16:h/3;
  for(int row=0;row<s.tokens;++row){
   size_t qbase=size_t(row)*10240+key*128,kbase=qbase+2048;
   float qn=detmath::sqrt(dot128(t,[&](int k){float v=a.b(0,qbase+k);return v*v;})+1e-6f);t.barrier();
   float kn=detmath::sqrt(dot128(t,[&](int k){float v=a.b(0,kbase+k);return v*v;})+1e-6f);t.barrier();
   float gate=a.b(1,row*48+h)+a.weight(4,h,s.flags),sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;
   float av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));float decay=detmath::exp(av*sp);
   int state=(h*128+j)*128;
   t.each(128,[&](int k){t.x[k]=(a.b(0,qbase+k)/qn)/detmath::sqrt(float(128));t.x[128+k]=a.b(0,kbase+k)/kn;t.x[256+k]=a.b(row?7:5,state+k)*decay;});t.barrier();
   float pred=dot128(t,[&](int k){return t.x[256+k]*t.x[128+k];});t.barrier();
   float delta=(a.b(0,row*10240+4096+h*128+j)-pred)*sigmoid(a.b(2,row*48+h));
   t.each(128,[&](int k){t.x[256+k]=t.x[256+k]+delta*t.x[128+k];});t.barrier();
   float y=dot128(t,[&](int k){return t.x[256+k]*t.x[k];});t.barrier();
   t.each(1,[&](int){a.put(6,(row*48+h)*128+j,y);});
   t.each(128,[&](int k){a.put(7,state+k,t.x[256+k]);});t.barrier();
  }
 }else if(s.op==conv){
  t.each(128,[&](int lane){int ch=group*128+lane;if(ch>=s.width)return;int dilation=s.extra?s.extra:1,hist=3*dilation;
   float history[9];for(int j=0;j<hist;++j)history[j]=a.b(1,ch*hist+j);
   for(int r=0;r<s.tokens;++r){float x=a.b(0,r*s.width+ch),acc=0;for(int tap=0;tap<4;++tap)acc=acc+(tap==3?x:history[tap*dilation])*a.weight(2,ch*4+tap,s.flags);
    a.put(3,r*s.width+ch,silu(dilation==3?Args::bf(acc):acc));for(int k=0;k<hist-1;++k)history[k]=history[k+1];history[hist-1]=x;}
   for(int j=0;j<hist;++j)a.put(4,ch*hist+j,history[j]);});
 }else if(s.op==norm||s.op==combine_norm||s.op==gated_norm){
  int width=s.op==gated_norm?128:s.width,stream=group%s.heads,base=group*width;
  auto value=[&](int k){if(s.op!=combine_norm)return a.b(0,base+k);return Args::bf(a.b(0,base+k)+a.b(1,(group/s.heads)*width+k)*(2.f*sigmoid(a.b(2,group)/4.f)));};
  float inv=detmath::rsqrt(tree(t,width,[&](int k){float x=value(k);return x*x;})/float(width)+1e-6f);t.barrier();
  t.each(width,[&](int k){float x=value(k);int wslot=s.op==combine_norm?3:s.op==gated_norm?2:1;
   float y=(x*inv)*(a.weight(wslot,(s.op==gated_norm?0:stream*width)+k,s.flags)+float(unit));
   if(s.op==gated_norm)y=y*sigmoid(a.b(1,base+k));
   a.put(s.op==combine_norm?5:s.op==gated_norm?3:2,base+k,y);if(s.op==combine_norm)a.put(4,base+k,x);});
 }else if(s.op==activation||s.op==mix||s.op==moe_combine){
  t.each(128,[&](int lane){int idx=group*128+lane;if(idx>=s.tokens*s.width)return;int r=idx/s.width,k=idx%s.width;
   if(s.op==activation){float v=a.b(0,idx);a.put(2,idx,s.extra?silu(v)*a.b(1,idx):silu(v/4.f));}
   else if(s.op==mix){float sum=0;for(int h=0;h<4;++h)sum=sum+sigmoid(a.b(1,(r*4+h)*s.width+k))*a.b(0,(r*4+h)*s.width+k);a.put(2,idx,sum/4.f);}
   else{float sum=0;for(int e=0;e<s.extra;++e)sum=sum+a.b(0,(r*s.extra+e)*s.width+k)*a.f(1)[r*s.extra+e];a.put(4,idx,Args::bf(sum)+Args::bf(a.b(2,idx)*sigmoid(a.b(3,r))));}
  });
 }else if(s.op==route_gather){
  int r=group,n=s.width,top=s.extra;float maximum=-INFINITY;
  bool finite=true;for(int j=0;j<n;++j){float v=a.b(0,r*n+j);finite=finite&&std::isfinite(v);maximum=std::max(maximum,v);}
  if(!finite){t.each(1,[&](int){t.fail(a);});return;}
  t.each(n,[&](int j){t.x[j]=detmath::exp(a.b(0,r*n+j)-maximum);t.x[512+j]=t.x[j];});t.barrier();float den=t.sum(n);t.barrier();
  t.each(n,[&](int j){t.x[512+j]=t.x[512+j]/den;});t.barrier();
  t.each(n,[&](int j){int rank=0;float v=t.x[512+j];for(int k=0;k<n;++k)rank+=t.x[512+k]>v||(t.x[512+k]==v&&k<j);
   if(rank<top){a.i(2)[r*top+rank]=j;t.x[1024+rank]=v;a.i(5)[(r*top+rank)*3]=j;a.i(5)[(r*top+rank)*3+1]=0;a.i(5)[(r*top+rank)*3+2]=640;
    a.i(6)[(r*top+rank)*3]=j;a.i(6)[(r*top+rank)*3+1]=0;a.i(6)[(r*top+rank)*3+2]=2560;}});t.barrier();
  t.each(top,[&](int j){t.x[1536+j]=t.x[1024+j];});t.barrier();float selected=t.sum(top,1536);t.barrier();
  t.each(top,[&](int j){a.f(3)[r*top+j]=t.x[1024+j]/selected;});
  t.each(top*2560,[&](int j){a.put(4,r*top*2560+j,a.b(1,r*2560+j%2560));});
 }else if(s.op==prepare){
  int r=group/30,h=group%30,position=pos+r;
  if(h<24){norm_rope(t,[&](int k){return a.b(0,(r*24+h)*512+k);},[&](int k,float v){a.put(6,(r*24+h)*256+k,v);a.put(7,(r*24+h)*256+k,a.b(0,(r*24+h)*512+256+k));},a,3,256,position,s.flags);}
  else if(h<26){h-=24;norm_rope(t,[&](int k){return a.b(1,(r*2+h)*256+k);},[&](int k,float v){a.put(8,(r*2+h)*256+k,v);},a,4,256,position,s.flags);}
  else{h-=26;norm_rope(t,[&](int k){return a.b(2,(r*4+h)*128+k);},[&](int k,float v){a.put(9,(r*4+h)*128+k,v);},a,5,128,position,s.flags);}
 }else if(s.op==pool){
  int blocks=(s.capacity+3)/4;
  if(group==blocks){t.each(s.tokens*512,[&](int j){a.put(4,pos*512+j,a.b(0,j));a.put(5,pos*512+j,a.b(1,j));});t.each(s.tokens*128,[&](int j){a.put(6,pos*128+j,a.b(2,j));});}
  else if(group>=pos/4&&group<(pos+s.tokens)/4){
   auto pooled=[&](int k){float x=0;for(int j=0;j<4;++j){int r=group*4+j;x=x+(r<pos?a.b(6,r*128+k):a.b(2,(r-pos)*128+k));}return Args::bf(x/4.f);};
   norm_rope(t,pooled,[&](int k,float v){a.put(7,group*128+k,v);},a,3,128,group*4,s.flags);
  }
 }else if(s.op==select){
  int r=group,position=pos+r,n=(position+1)/4,cap=(s.capacity+3)/4,base=3*cap;
  for(int h=0;h<4;++h){
   // Parallel blocks; each block dot uses a fixed local private tree. Only 128 values.
   t.each(n,[&](int b){float v[128];for(int k=0;k<128;++k)v[k]=a.b(0,(r*4+h)*128+k)*a.b(1,b*128+k);for(int stride=1;stride<128;stride*=2)for(int k=0;k<128;k+=2*stride)v[k]=v[k]+v[k+stride];t.x[b]=(h?t.x[b]:0.f)+std::max(0.f,v[0]);});t.barrier();
  }
  (void)base;t.each(n,[&](int b){t.x[b]=t.x[b]/detmath::sqrt(float(128));});t.barrier();
  int count=std::min(n,s.budget/4),slots=s.budget+3;
  t.each(slots,[&](int j){a.i(2)[r*slots+j]=-1;});t.barrier();
  t.each(n,[&](int b){int rank=0;for(int k=0;k<n;++k)rank+=t.x[k]>t.x[b]||(t.x[k]==t.x[b]&&k<b);if(rank<count)for(int j=0;j<4;++j)a.i(2)[r*slots+rank*4+j]=b*4+j;});
  t.each(position+1-n*4,[&](int j){a.i(2)[r*slots+count*4+j]=n*4+j;});
 }else if(s.op==attention_score){
  int slots=s.budget+3,launch_slots=std::min(s.capacity,slots),slot=group%launch_slots,h=(group/launch_slots)%24,r=group/(launch_slots*24),id=a.i(4)[r*slots+slot];
  int offset=(r*24+h)*slots+slot;
  if(id>=s.capacity||id>pos+r){t.each(1,[&](int){t.fail(a);});return;}
  if(id<0){t.each(1,[&](int){a.f(6)[offset]=-INFINITY;});return;}
  float score=tree(t,256,[&](int k){return a.b(2,(id*2+h/12)*256+k)*a.b(0,(r*24+h)*256+k);})/detmath::sqrt(float(256));t.barrier();t.each(1,[&](int){a.f(6)[offset]=score;});
 }else if(s.op==attention_softmax){
  int slots=s.budget+3,r=group/24,n=0;while(n<slots&&a.i(4)[r*slots+n]>=0)++n;
  if(!n)return;float m=-INFINITY;for(int k=0;k<n;++k)m=std::max(m,a.f(6)[group*slots+k]);
  t.each(n,[&](int k){float v=detmath::exp(a.f(6)[group*slots+k]-m);t.x[k]=v;a.f(7)[group*slots+k]=v;});t.barrier();float den=t.sum(n);t.barrier();
  t.each(n,[&](int k){a.f(7)[group*slots+k]=a.f(7)[group*slots+k]/den;});
 }else if(s.op==attention_value){
  int k=group%256,h=(group/256)%24,r=group/(256*24),slots=s.budget+3,n=0;while(n<slots&&a.i(4)[r*slots+n]>=0)++n;
  if(!n)return;float value=tree(t,n,[&](int j){int id=a.i(4)[r*slots+j];return a.f(7)[(r*24+h)*slots+j]*a.b(3,(id*2+h/12)*256+k);});t.barrier();
  t.each(1,[&](int){a.put(5,group,Args::bf(value)*sigmoid(a.b(1,group)));});
 }
}
inline void cpu(Shape s,Args a){validate(s);std::vector<float> scratch(local_floats(s));for(int g=0;g<groups(s);++g)group(s,a,g,HostTeam{scratch.data()});}
}
