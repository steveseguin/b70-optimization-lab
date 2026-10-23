// Source-pinned production arithmetic, HOST_ONLY fixture only.
#pragma once
#ifndef OWN_RT_HOST_ONLY
#error CPU fixture requires OWN_RT_HOST_ONLY
#endif
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p33_candidates.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet10-kopt5/expanded.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/round2.hpp"
namespace p202_selected {
inline float recurrence_tree(const float* leaves) {
 float v[32];std::copy_n(leaves,32,v);
 for(unsigned stride=1;stride<32;stride*=2)
  for(unsigned i=0;i<32;i+=2*stride)v[i]=v[i]+v[i+stride];
 return v[0];
}
template<unsigned RowsPerWG> inline void recurrence_host_rows(ng::Shape s,ng::Args a,
 unsigned first,unsigned count,uint16_t* row0_snapshot=nullptr) {
 static_assert(RowsPerWG==4||RowsPerWG==8);
 if(!a.i(18)[0]||a.i(15)[0])return;
 int pos=a.i(17)[0];if(pos<0||pos>s.capacity-s.tokens){a.i(15)[0]=1;return;}
 if(first%RowsPerWG||count%RowsPerWG||first+count>6144)throw std::invalid_argument("p54 recurrence row tile");
 for(unsigned base=first;base<first+count;base+=RowsPerWG) {
  const unsigned h=base/128,key=(s.flags&4)?h%16:h/3;
  for(int r=0;r<s.tokens;++r) {
   const unsigned qb=r*10240+key*128,kb=qb+2048;
   float q[128],k[128],qs[32]{},ks[32]{};
   for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z) {
    unsigned x=lane*4+z;q[x]=a.b(0,qb+x);k[x]=a.b(0,kb+x);
    qs[lane]=qs[lane]+q[x]*q[x];ks[lane]=ks[lane]+k[x]*k[x];
   }
   const float qn=detmath::sqrt(recurrence_tree(qs)+1e-6f);
   const float kn=detmath::sqrt(recurrence_tree(ks)+1e-6f);
   const float gate=a.b(1,r*48+h)+a.weight(4,h,s.flags);
   const float sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;
   const float av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));
   const float decay=detmath::exp(av*sp),beta=ng::sigmoid(a.b(2,r*48+h));
   for(unsigned x=0;x<128;++x) {
    q[x]=(q[x]/qn)/detmath::sqrt(float(128));k[x]=k[x]/kn;
   }
   for(unsigned row=0;row<RowsPerWG;++row) {
    const unsigned g=base+row,j=g%128,state=g*128;
    float v[128],pred[32]{},y[32]{};
    for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z) {
     unsigned x=lane*4+z;v[x]=a.b(r?7:5,state+x)*decay;
     pred[lane]=pred[lane]+v[x]*k[x];
    }
    const float delta=(a.b(0,r*10240+4096+h*128+j)-recurrence_tree(pred))*beta;
    for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z) {
     unsigned x=lane*4+z;v[x]=v[x]+delta*k[x];y[lane]=y[lane]+v[x]*q[x];
    }
    a.put(6,(r*48+h)*128+j,recurrence_tree(y));
    for(unsigned x=0;x<128;++x){a.put(7,state+x,v[x]);if(row0_snapshot&&r==0)row0_snapshot[state+x]=ng::Args::bits(v[x]);}
   }
  }
 }
}
}
