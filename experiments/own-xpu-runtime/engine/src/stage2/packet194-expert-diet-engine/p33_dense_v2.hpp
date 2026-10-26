#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
// p33.dense.segment decode rows, expanded Q6_K / Q8_0 storage (int8 codes, then one F32 scale per 16 / 32 columns),
// F32 activations and outputs (lab 2026-10-26, OWNRT_DENSE_DECODE_V2=1, default off). Every output keeps the value of
// Kernel<0,T,K,1,true> (one 32-lane subgroup per row): lane l walks the tiles 8l, 8l+256, ... in order and, per tile,
// takes the tile's scale, value = scale*float(signed8(code)), product = value*x, sum = sum + product for the 8 columns
// in order (dense_lane<T,K,true>), then the adjacent-pair tree over the 32 lanes. Here a subgroup carries R rows (row
// bases subgroup-uniform), U tiles' loads are issued before their in-order arithmetic, and the R trees are reduced
// together by a transposing butterfly (node = lower lane block + upper lane block). Token rows (prefill) untouched.
#include "stage2/packet194-expert-diet-engine/p33_candidates.hpp"
#include <sycl/sycl.hpp>
#include <cstdint>
#include <cstdlib>
namespace p33::v2 {
inline bool enabled(){static const bool on=[]{const char* e=std::getenv("OWNRT_DENSE_DECODE_V2");return e&&e[0]=='1';}();return on;}
template<iq3::Type T,unsigned K,unsigned R,unsigned U> inline void dense_rows(const uint8_t* W,const float* x,float* y,uint32_t rows,uint32_t rb,sycl::nd_item<1> it){
 static_assert(T==iq3::Type::Q6_K||T==iq3::Type::Q8_0);static_assert(K%256==0&&(R==1||R==2||R==4));
 constexpr unsigned group=T==iq3::Type::Q6_K?16:32;constexpr unsigned LR=R==1?0:R==2?1:2;
 auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
 const uint32_t row0=(uint32_t(it.get_group_linear_id())*uint32_t(it.get_local_range(0)/32)+uint32_t(sg.get_group_linear_id()))*R;if(row0>=rows)return;
 const uint8_t* wr[R];
 #pragma unroll
 for(unsigned r=0;r<R;++r)wr[r]=W+size_t(row0+r<rows?row0+r:row0)*rb; // a missing row reads row0, never stored
 float A[R];
 #pragma unroll
 for(unsigned r=0;r<R;++r)A[r]=0.f;
 #pragma unroll 1
 for(uint32_t base=0;base<K;base+=256*U){
  float xs[U][8];uint32_t code[U][R][2];float scale[U][R];
  #pragma unroll
  for(unsigned u=0;u<U;++u){const uint32_t t=base+256*u+lane*8;if(base+256*u<K){
   const sycl::vec<float,4>*xv=reinterpret_cast<const sycl::vec<float,4>*>(x+t);const auto a0=xv[0],a1=xv[1];
   #pragma unroll
   for(unsigned j=0;j<4;++j){xs[u][j]=a0[j];xs[u][j+4]=a1[j];}
   #pragma unroll
   for(unsigned r=0;r<R;++r){const uint32_t* c=reinterpret_cast<const uint32_t*>(wr[r]+t);code[u][r][0]=c[0];code[u][r][1]=c[1];
    scale[u][r]=iq3::bits_float(*reinterpret_cast<const uint32_t*>(wr[r]+K+4*(t/group)));}}}
  #pragma unroll
  for(unsigned u=0;u<U;++u)if(base+256*u<K){
   #pragma unroll
   for(unsigned r=0;r<R;++r){
    #pragma unroll
    for(unsigned j=0;j<8;++j){const float value=scale[u][r]*float(int(int8_t(uint8_t(code[u][r][j/4]>>(8*(j%4))))));
     const float product=value*xs[u][j];A[r]=A[r]+product;}}}
 }
 #pragma unroll
 for(unsigned lv=0;lv<LR;++lv){const bool hi=((lane>>lv)&1u)!=0;
  #pragma unroll
  for(unsigned m=0;m<(R>>(lv+1));++m){const float lo_v=A[2*m],hi_v=A[2*m+1];const float send=hi?lo_v:hi_v,mine=hi?hi_v:lo_v;
   const float recv=sycl::permute_group_by_xor(sg,send,1u<<lv);A[m]=hi?recv+mine:mine+recv;}}
 #pragma unroll
 for(unsigned lv=LR;lv<5;++lv){const float o=sycl::permute_group_by_xor(sg,A[0],1u<<lv);A[0]=((lane>>lv)&1u)?o+A[0]:A[0]+o;}
 const uint32_t row=row0+(lane&(R-1));
 if(lane<R&&row<rows)y[row]=A[0];
}
}
