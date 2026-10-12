#pragma once
#include "specialised.hpp"
namespace round2 {
inline bool supported(ng::Shape s){return s.op==ng::gdn||s.op==ng::select||s.op==ng::attention_score||s.op==ng::attention_softmax||s.op==ng::attention_value;}
// Adjacent-tree arithmetic remains explicit. Every kernel has one compile-time
// operation; only capacity, token count and flags remain invocation parameters.
template<ng::Op Code,int Stage,class Team> void group(ng::Shape s,ng::Args a,int group,float* global,Team t){
 t.each(1,[&](int){t.x[0]=float(!a.i(18)[0]||t.error(a));});t.barrier();if(t.x[0])return;t.barrier();
 int pos=a.i(17)[0];if(pos<0||pos>s.capacity-s.tokens){if(group==0)t.each(1,[&](int){t.fail(a);});return;}
 if constexpr(Code==ng::select){
  int cap=(s.capacity+3)/4,S=s.budget+3;
  if constexpr(Stage==0){int r=group/cap,b=group%cap,n=(pos+r+1)/4;if(b>=n)return;
   float score=0.f;
   for(int h=0;h<4;++h){float d=ng::tree(t,128,[&](int k){return a.b(0,(r*4+h)*128+k)*a.b(1,b*128+k);});t.barrier();score=score+std::max(0.f,d);}
   t.each(1,[&](int){global[r*cap+b]=score/detmath::sqrt(float(128));});
  }else if constexpr(Stage==1){int r=group/cap,b=group%cap,n=(pos+r+1)/4,count=std::min(n,s.budget/4);
   bool finite=true;for(int k=0;k<n;++k)finite=finite&&std::isfinite(global[r*cap+k]);
   if(!finite){if(b==0){t.each(S,[&](int k){a.i(2)[r*S+k]=-1;});t.each(1,[&](int){t.fail(a);});}return;}
   // Selection and the -1 suffix have disjoint writers. No initialization
   // launch races with selected IDs, even under a shuffled host schedule.
   if(b==0)t.each(S-count*4-(pos+r+1-n*4),[&](int k){a.i(2)[r*S+count*4+(pos+r+1-n*4)+k]=-1;});
   if(b==0)t.each(pos+r+1-n*4,[&](int k){a.i(2)[r*S+count*4+k]=n*4+k;});
   if(b>=n)return;
   t.each(1,[&](int){int rank=0;float v=global[r*cap+b];
    for(int k=0;k<n;++k){float x=global[r*cap+k];rank+=x>v||(x==v&&k<b);}
    if(rank<count)for(int k=0;k<4;++k)a.i(2)[r*S+rank*4+k]=b*4+k;
   });
  }
 }else if constexpr(Code==ng::attention_score){
  int S=s.budget+3,L=std::min(s.capacity,S),slot=group%L,h=(group/L)%24,r=group/(L*24),id=a.i(4)[r*S+slot],offset=(r*24+h)*S+slot;
  if(id < -1||id>=s.capacity||id>pos+r){t.each(1,[&](int){t.fail(a);});return;}
  if(id<0){t.each(1,[&](int){a.f(6)[offset]=-INFINITY;});return;}
  float score=ng::tree(t,256,[&](int k){return a.b(2,(id*2+h/12)*256+k)*a.b(0,(r*24+h)*256+k);})/detmath::sqrt(float(256));t.barrier();t.each(1,[&](int){a.f(6)[offset]=score;});
 }else if constexpr(Code==ng::attention_softmax||Code==ng::attention_value){
  int S=s.budget+3,r=Code==ng::attention_softmax?group/24:group/6144,n=0;
  while(n<S&&a.i(4)[r*S+n]!=-1){int id=a.i(4)[r*S+n];if(id<0||id>=s.capacity||id>pos+r||n>=std::min(s.capacity,S)){t.each(1,[&](int){t.fail(a);});return;}++n;}
  if(!n)return;
  if constexpr(Code==ng::attention_softmax){
   // One finite maximum per head; each lane used to repeat this whole scan.
   t.each(1,[&](int){float m=-INFINITY;for(int k=0;k<n;++k)m=std::max(m,a.f(6)[group*S+k]);t.x[n]=m;});t.barrier();float m=t.x[n];t.barrier();
   t.each(n,[&](int k){float v=detmath::exp(a.f(6)[group*S+k]-m);t.x[k]=v;a.f(7)[group*S+k]=v;});t.barrier();float den=t.sum(n);t.barrier();t.each(n,[&](int k){a.f(7)[group*S+k]=a.f(7)[group*S+k]/den;});
  }else{
   int h=(group/256)%24,k=group%256;
   float value=ng::tree(t,n,[&](int j){int id=a.i(4)[r*S+j];return a.f(7)[(r*24+h)*S+j]*a.b(3,(id*2+h/12)*256+k);});t.barrier();
   t.each(1,[&](int){a.put(5,group,ng::Args::bf(value)*ng::sigmoid(a.b(1,group)));});
  }
 }
}
// Host emulation of the subgroup-private GDN path. The four terms of each
// logical lane retain left-to-right + from +0, followed by the same 32-leaf tree.
inline void gdn_host(ng::Shape s,ng::Args a){
 if(!a.i(18)[0]||a.i(15)[0])return;int pos=a.i(17)[0];if(pos<0||pos>s.capacity-s.tokens){a.i(15)[0]=1;return;}
 // CPU-only independent state-row scheduling; token recurrence stays serial.
#ifdef OWN_RT_HOST_ONLY
 #pragma omp parallel for num_threads(2) schedule(static)
#endif
 for(int g=0;g<6144;++g){int h=g/128,j=g%128,key=(s.flags&4)?h%16:h/3,state=g*128;
  for(int r=0;r<s.tokens;++r){int qb=r*10240+key*128,kb=qb+2048;
   float qn=detmath::sqrt(specialised::dot128([&](int k){float v=a.b(0,qb+k);return v*v;})+1e-6f),kn=detmath::sqrt(specialised::dot128([&](int k){float v=a.b(0,kb+k);return v*v;})+1e-6f);
   float gate=a.b(1,r*48+h)+a.weight(4,h,s.flags),sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate,av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));
   float decay=detmath::exp(av*sp),q[128],k[128],v[128];
   for(int x=0;x<128;++x){q[x]=(a.b(0,qb+x)/qn)/detmath::sqrt(float(128));k[x]=a.b(0,kb+x)/kn;v[x]=a.b(r?7:5,state+x)*decay;}
   float pred=specialised::dot128([&](int x){return v[x]*k[x];}),delta=(a.b(0,r*10240+4096+h*128+j)-pred)*ng::sigmoid(a.b(2,r*48+h));
   for(int x=0;x<128;++x)v[x]=v[x]+delta*k[x];
   float y=specialised::dot128([&](int x){return v[x]*q[x];});a.put(6,(r*48+h)*128+j,y);for(int x=0;x<128;++x)a.put(7,state+x,v[x]);
  }
 }
}
inline int groups(ng::Shape s){return s.op==ng::select?s.tokens*((s.capacity+3)/4):ng::groups(s);}
inline size_t scratch_floats(ng::Shape s){return s.op==ng::select?size_t(s.tokens)*((s.capacity+3)/4):1;}
inline int local_floats(ng::Shape s){return s.op==ng::attention_softmax?s.budget+4:s.op==ng::attention_value?s.budget+3:256;}
struct HostTeam:ng::HostTeam {};
template<ng::Op Code,int Stage> inline void cpu_stage(ng::Shape s,ng::Args a,float* global){std::vector<float> local(round2::local_floats(s));for(int g=0;g<round2::groups(s);++g)group<Code,Stage>(s,a,g,global,ng::HostTeam{local.data()});}
} // namespace round2
