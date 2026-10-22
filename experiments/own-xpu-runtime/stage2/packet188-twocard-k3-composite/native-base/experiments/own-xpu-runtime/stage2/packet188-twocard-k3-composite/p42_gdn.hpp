#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p42_gdn.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/build/checked/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/kernels.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/build/checked/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/p28/submit.hpp"
namespace p42parallel {
inline void gdn_host(ng::Shape s,ng::Args a){
 if(s.tokens!=1)throw std::invalid_argument("gdn token1 gate");
 if(!a.i(18)[0]||a.i(15)[0])return;int pos=a.i(17)[0];if(pos<0||pos>s.capacity-1){a.i(15)[0]=1;return;}
 for(int g=0;g<6144;++g){int h=g/128,j=g%128,key=(s.flags&4)?h%16:h/3,state=g*128,qb=key*128,kb=qb+2048;float q[32][4],k[32][4],v[32][4],qs[32]{},ks[32]{},pred[32]{},y[32]{};
  for(int lane=0;lane<32;++lane)for(int z=0;z<4;++z){q[lane][z]=a.b(0,qb+4*lane+z);k[lane][z]=a.b(0,kb+4*lane+z);qs[lane]=qs[lane]+q[lane][z]*q[lane][z];ks[lane]=ks[lane]+k[lane][z]*k[lane][z];}
  float qn=detmath::sqrt(iq3::tree32(qs)+1e-6f),kn=detmath::sqrt(iq3::tree32(ks)+1e-6f);float gate=a.b(1,h)+a.weight(4,h,s.flags),sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate,av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));float decay=detmath::exp(av*sp);
  for(int lane=0;lane<32;++lane)for(int z=0;z<4;++z){q[lane][z]=(q[lane][z]/qn)/detmath::sqrt(float(128));k[lane][z]=k[lane][z]/kn;v[lane][z]=a.b(5,state+4*lane+z)*decay;pred[lane]=pred[lane]+v[lane][z]*k[lane][z];}
  float delta=(a.b(0,4096+h*128+j)-iq3::tree32(pred))*ng::sigmoid(a.b(2,h));
  for(int lane=0;lane<32;++lane)for(int z=0;z<4;++z){v[lane][z]=v[lane][z]+delta*k[lane][z];y[lane]=y[lane]+v[lane][z]*q[lane][z];}
  a.put(6,h*128+j,iq3::tree32(y));for(int lane=0;lane<32;++lane)for(int z=0;z<4;++z)a.put(7,state+4*lane+z,v[lane][z]);
 }
}
}
