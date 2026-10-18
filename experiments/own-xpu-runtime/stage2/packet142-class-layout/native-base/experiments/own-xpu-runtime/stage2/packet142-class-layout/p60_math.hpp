#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p60_math.hpp"
#pragma once
// Packet60: independently written scheduling over the packet56 arithmetic.
// The build resolves these includes to packet56's sealed checked mirror.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/p49c_kernel.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/specialised.hpp"
namespace p60 {
constexpr unsigned H=2560, S=4, K=H*S, L=320;
using iq3::Type;
inline float get(const uint16_t* p,unsigned i){return iq3::bits_float(uint32_t(p[i])<<16);}
struct Bound {
 const uint16_t* x;
 const float* gain;
 const uint8_t *low_w,*gate_w,*inject_w;
 uint16_t *norm,*low,*act,*gate,*mix,*inject;
 float *scratch,*workspace;
 uint32_t *error;
 const uint32_t *active,*position;
 unsigned capacity=4096;
};
inline bool enabled(Bound b){return *b.active && !*b.error && *b.position<b.capacity;}
inline void norm_chunk(Bound b,unsigned stream,unsigned chunk){
 b.scratch[stream*80+chunk]=specialised::subtree(H,chunk,[&](int k){float x=get(b.x,stream*H+k);return x*x;});
}
inline void norm_output(Bound b,unsigned stream,unsigned k,float inv){
 unsigned i=stream*H+k;b.norm[i]=iq3::bf16_bits((get(b.x,i)*inv)*(b.gain[i]+0.f));
}
template<Type T,unsigned N,unsigned Split> inline float dot(const uint8_t*w,const uint16_t*x,float*saved=nullptr){
 float parts[Split];
 for(unsigned p=0;p<Split;++p){auto bounds=iq3::kopt2::bounds(N,p,Split);float lanes[32];
  for(unsigned lane=0;lane<32;++lane)lanes[lane]=p49c::dense_lane<T,N>(w,x,bounds.first,bounds.second,lane);
  parts[p]=iq3::tree32(lanes);if(saved)saved[p]=parts[p];
 }
 if constexpr(Split==1)return parts[0];else return (parts[0]+parts[1])+(parts[2]+parts[3]);
}
inline void low_output(Bound b,unsigned row,float value){
 b.low[row]=iq3::bf16_bits(value);
 if(enabled(b))b.act[row]=p39::hc_activation(b.low[row]);
}
inline void mix_output(Bound b,unsigned k,const uint16_t* gates){
 if(!enabled(b))return;
 float sum=0.f;
 for(unsigned s=0;s<S;++s)sum=sum+ng::sigmoid(get(gates,s))*get(b.norm,s*H+k);
 b.mix[k]=iq3::bf16_bits(sum/4.f);
}
inline void host_norm(Bound b){
 if(!*b.active||*b.error)return;
 if(*b.position>=b.capacity){*b.error=1;return;}
 for(unsigned s=0;s<S;++s){for(unsigned c=0;c<80;++c)norm_chunk(b,s,c);
  float roots[4];for(unsigned sg=0;sg<4;++sg){float lanes[32];for(unsigned l=0;l<32;++l)lanes[l]=sg*32+l<80?b.scratch[s*80+sg*32+l]:0.f;roots[sg]=iq3::tree32(lanes);}
  float total=(roots[0]+roots[1])+(roots[2]+roots[3]);
  float inv=detmath::rsqrt(total/float(H)+1e-6f);
  for(unsigned k=0;k<H;++k)norm_output(b,s,k,inv);
 }
}
inline void host_low_inject(Bound b){
 for(unsigned r=0;r<L;++r)low_output(b,r,dot<Type::Q8_0,K,4>(b.low_w+r*iq3::expanded::row_bytes(Type::Q8_0,K),b.norm));
 // Retain the production inject split scratch at row*8; slots 4..7 untouched.
 for(unsigned r=0;r<S;++r)b.inject[r]=iq3::bf16_bits(dot<Type::F32,K,4>(b.inject_w+r*K*4,b.norm,b.workspace+r*8));
}
inline void host_gate_mix(Bound b){
 for(unsigned k=0;k<H;++k){uint16_t gates[S];
  for(unsigned s=0;s<S;++s){unsigned r=s*H+k;gates[s]=iq3::bf16_bits(dot<Type::Q8_0,L,1>(b.gate_w+r*iq3::expanded::row_bytes(Type::Q8_0,L),b.act));b.gate[r]=gates[s];}
  mix_output(b,k,gates);
 }
}
} // namespace p60
