#pragma once
#include "stage2/packet194-expert-diet-engine/prefill_experts.hpp"
#include "stage2/packet6-kopt/reference.hpp"
// Isolated intake only: SG32 contains four independent sets of eight lanes.
// Each physical lane owns four adjacent canonical lanes, preserving their sums.
namespace packed_group {
struct Kernel {
 const uint8_t* w;const float* x;float* y;const uint32_t* order;const uint32_t* tiles;const uint32_t* tile_count;
 uint32_t span,k,rb,G,rgroups,rl;sycl::local_accessor<float,1> lut;
 void operator()(sycl::nd_item<1> it)const {
  const unsigned li=it.get_local_linear_id();if(li<16)lut[li]=float(iq3::iq4_level(li));sycl::group_barrier(it.get_group());
  auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),set=lane/8,t=lane%8;
  const uint32_t logical=uint32_t(it.get_group(0))*4+sg.get_group_linear_id();if(logical>=rgroups*G)return;
  const uint32_t rg=logical%rgroups,first_tile=logical/rgroups;const float nan=iq3::bits_float(0x7fc00000);
  for(uint32_t tile=first_tile;tile<*tile_count;tile+=G){
   const uint32_t* d=tiles+tile*5;const uint32_t base=d[0],rcount=d[1],first=d[2],cnt=d[3],valid=d[4];
   for(uint32_t rr=0;rr<rl;++rr){const uint32_t row=(rg*rl+rr)*4+set;
    const bool live=valid&&row<span&&row<rcount;
    const uint8_t* rp=live?w+size_t(base+row)*rb:w;float acc[4][4];
    #pragma unroll
    for(unsigned s=0;s<4;++s)
     #pragma unroll
     for(unsigned j=0;j<4;++j)acc[s][j]=0.f;
    const bool odd=t&1;
    for(uint32_t b=t;live&&b*32u<k;b+=8u){
     const uint32_t* wp=reinterpret_cast<const uint32_t*>(rp+b*18u-(odd?2u:0u));
     const uint32_t w0=wp[0],w1=wp[1],w2=wp[2],w3=wp[3],w4=wp[4];
     const float scale=iq3::kopt::half_scale(odd?w0>>16:w0&65535u);
     uint32_t qw[4];qw[0]=odd?w1:(w0>>16)|(w1<<16);qw[1]=odd?w2:(w1>>16)|(w2<<16);qw[2]=odd?w3:(w2>>16)|(w3<<16);qw[3]=odd?w4:(w3>>16)|(w4<<16);
     float values[4][8];
     #pragma unroll
     for(unsigned j=0;j<4;++j)
      #pragma unroll
      for(unsigned z=0;z<8;++z){const unsigned bi=(8*j+z)%16,n=(qw[bi/4]>>(8*(bi%4)+4*(j/2)))&15u;values[j][z]=scale*lut[n];}
     #pragma unroll
     for(unsigned s=0;s<4;++s){if(s>=cnt)break;const float* xp=x+size_t(order[first+s])*k+b*32u;
      #pragma unroll
      for(unsigned j=0;j<4;++j)
       #pragma unroll
       for(unsigned z=0;z<8;++z){const float product=values[j][z]*xp[j*8+z];acc[s][j]=acc[s][j]+product;}
     }
    }
    #pragma unroll
    for(unsigned s=0;s<4;++s){float sum=(acc[s][0]+acc[s][1])+(acc[s][2]+acc[s][3]);
     #pragma unroll
     for(unsigned z=1;z<8;z*=2){const float rhs=sycl::select_from_group(sg,sum,set*8+(t+z)%8);if(t%(2*z)==0)sum=sum+rhs;}
     if(t==0&&s<cnt&&row<span)y[size_t(order[first+s])*span+row]=live?sum:nan;
    }
   }
  }
 }
 auto get(sycl::ext::oneapi::experimental::properties_tag)const{return sycl::ext::oneapi::experimental::properties{sycl::ext::oneapi::experimental::sub_group_size<32>};}
};
inline sycl::event launch(sycl::queue& q,const uint8_t*w,const float*x,float*y,const uint32_t*order,const uint32_t*tiles,const uint32_t*count,uint32_t span,uint32_t k,uint32_t rb,uint32_t n,uint32_t experts){
 const uint32_t bound=std::min(n,(n+3)/4+std::min(n,experts)),G=std::max(1u,(bound+3)/4),rl=4,rgroups=((span+3)/4+rl-1)/rl;
 Kernel ker{w,x,y,order,tiles,count,span,k,rb,G,rgroups,rl,{}};
 return q.submit([&](sycl::handler&h){ker.lut=sycl::local_accessor<float,1>(16,h);h.parallel_for(sycl::nd_range<1>(size_t((rgroups*G+3)/4)*128,128),ker);});
}
}
