#pragma once
#include "../packet29-merged/kernels.hpp"
#include "../packet29-merged/specialised.hpp"
#include "tiny_cooperative_core.hpp"
// Leaf statement bodies copied byte-for-byte from ng::group, except iteration
// wrapper: (group*128+lane) becomes global index. No arithmetic is changed.
namespace p42tiny {
using namespace ng;
template<ng::Op Code,class Guard> inline void element(ng::Shape s,ng::Args a,int index,Guard guard){
 s.op=Code;
 if(!a.i(18)[0]||guard.error(a))return;
 int pos=a.i(17)[0];if(pos<0||pos>s.capacity-s.tokens){if(index==0)guard.fail(a);return;}
 if constexpr(Code==ng::conv) {int ch=index;if(ch>=s.width)return;int dilation=s.extra?s.extra:1,hist=3*dilation;
   float history[9];for(int j=0;j<hist;++j)history[j]=a.b(1,ch*hist+j);
   for(int r=0;r<s.tokens;++r){float x=a.b(0,r*s.width+ch),acc=0;for(int tap=0;tap<4;++tap)acc=acc+(tap==3?x:history[tap*dilation])*a.weight(2,ch*4+tap,s.flags);
    a.put(3,r*s.width+ch,silu(dilation==3?Args::bf(acc):acc));for(int k=0;k<hist-1;++k)history[k]=history[k+1];history[hist-1]=x;}
   for(int j=0;j<hist;++j)a.put(4,ch*hist+j,history[j]);}
 else {int idx=index;if(idx>=s.tokens*s.width)return;int r=idx/s.width,k=idx%s.width;
   if(s.op==activation){float v=a.b(0,idx);a.put(2,idx,s.extra?silu(v)*a.b(1,idx):silu(v/4.f));}
   else if(s.op==mix){float sum=0;for(int h=0;h<4;++h)sum=sum+sigmoid(a.b(1,(r*4+h)*s.width+k))*a.b(0,(r*4+h)*s.width+k);a.put(2,idx,sum/4.f);}
   else{float sum=0;for(int e=0;e<s.extra;++e)sum=sum+a.b(0,(r*s.extra+e)*s.width+k)*a.f(1)[r*s.extra+e];a.put(4,idx,Args::bf(sum)+Args::bf(a.b(2,idx)*sigmoid(a.b(3,r))));}
  }
}
struct CpuGuard{int error(ng::Args a)const{return a.i(15)[0];}void fail(ng::Args a)const{a.i(15)[0]=1;}};
inline size_t elements(ng::Shape s){return s.op==ng::conv?s.width:s.tokens*s.width;}
template<int WG,class F> void mapping(size_t n,F f){for(size_t group=0;group<(n+WG-1)/WG;++group)for(int lane=0;lane<WG;++lane){size_t i=group*WG+lane;if(i<n)f(i);}}
template<ng::Op Code,int WG> void cpu(ng::Shape s,ng::Args a){mapping<WG>(elements(s),[&](size_t i){element<Code>(s,a,int(i),CpuGuard{});});}

// Team width changes only which work-item executes an existing each() leaf.
// All barrier boundaries, adjacent sum nodes and odd-tail additions remain.
template<int WG>struct CpuTeam{
 float*x;
 template<class F>void each(int n,F f)const{for(int lane=0;lane<WG;++lane)for(int j=lane;j<n;j+=WG)f(j);}
 void barrier()const{}
 int error(ng::Args a)const{return a.i(15)[0];}void fail(ng::Args a)const{a.i(15)[0]=1;}
 float sum(int n,int base=0)const{for(int stride=1;stride<n;stride*=2)each((n+2*stride-1)/(2*stride),[&](int j){int i=j*2*stride;x[base+i]=x[base+i]+(i+stride<n?x[base+i+stride]:0.f);});return x[base];}
};
template<int WG>void cooperative_cpu(ng::Shape s,ng::Args a){std::vector<float>x(ng::local_floats(s));for(int g=0;g<ng::groups(s);++g){auto t=CpuTeam<WG>{x.data()};if(s.op==ng::gated_norm)cooperative_group<ng::gated_norm>(s,a,g,t);else if(s.op==ng::prepare)cooperative_group<ng::prepare>(s,a,g,t);else if(s.op==ng::pool)cooperative_group<ng::pool>(s,a,g,t);else throw std::invalid_argument("cooperative op");}}
}
