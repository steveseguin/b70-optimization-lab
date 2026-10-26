#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
// Dense decode GEMV, raw BF16 weights, F32 activations and outputs (lab 2026-10-26, OWNRT_DENSE_DECODE_V2=1, default
// off). Same value for every output as kopt Multiply (one 32-lane subgroup per row): lane l owns the 8-element chunks
// starting at 8l, 8l+256, ... and accumulates acc = acc + w*x from 0.f in chunk and element order; the 32 lane sums
// are added by the adjacent-pair tree (strides 1..16, node = lower lane block + upper lane block); lane 0 stores.
// Here one subgroup carries R consecutive rows: every lane runs the unchanged per-row chunk loop for each of its R
// rows (loads of U chunks issued before their in-order accumulation), and the R trees are reduced together by a
// transposing butterfly (at the first log2(R) levels lanes l and l^z exchange the half of their pending rows the other
// keeps; at the remaining levels both lanes hold the same row and add lower + upper). Lane l ends with row
// row0 + (l & (R-1)). No local memory and no work-group barrier (raw rows were never staged).
// Requirements (checked by the caller): k % 8 == 0 handled generally (ragged chunk as Multiply), rows of 16-byte
// aligned BF16 (rb % 16 == 0, base aligned), x 16-byte aligned: Multiply's aligned F32 branch is taken for every
// chunk there, so its ragged-chunk path is the only other one and is reproduced.
#include <sycl/sycl.hpp>
#include <array>
#include <cstdint>
#include <cstdlib>
namespace iq3::kopt::dense_v2 {
inline float bf16f(uint16_t v){return sycl::bit_cast<float>(uint32_t(v)<<16);}
template<unsigned R,unsigned U> inline void bf16_rows(const uint8_t* W,const float* x,float* y,uint32_t rows,uint32_t k,uint32_t rb,sycl::nd_item<1> it,uint32_t sgid){
 static_assert(R==1||R==2||R==4||R==8||R==16||R==32);
 constexpr unsigned LR=R==1?0:R==2?1:R==4?2:R==8?3:R==16?4:5;
 auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
 const uint32_t row0=sgid*R;if(row0>=rows)return;
 float A[R];
 #pragma unroll
 for(unsigned r=0;r<R;++r)A[r]=0.f;
 uint32_t base=lane*8u;
 // Full chunks, U at a time: loads first, then the products and adds in Multiply's order (chunk, element).
 for(;base+(U-1)*256u+8u<=k;base+=U*256u){
  float wide[U][8];
  #pragma unroll
  for(unsigned u=0;u<U;++u){const sycl::vec<float,4>*xv=reinterpret_cast<const sycl::vec<float,4>*>(x+base+u*256u);const auto a0=xv[0],a1=xv[1];
   #pragma unroll
   for(unsigned j=0;j<4;++j){wide[u][j]=a0[j];wide[u][j+4]=a1[j];}}
  #pragma unroll
  for(unsigned r=0;r<R;++r){
   const uint32_t row=row0+r<rows?row0+r:row0; // a missing row reads row0 and is never stored
   sycl::vec<uint16_t,8> w[U];
   #pragma unroll
   for(unsigned u=0;u<U;++u)w[u]=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(W+size_t(row)*rb+size_t(base+u*256u)*2u);
   #pragma unroll
   for(unsigned u=0;u<U;++u){
    #pragma unroll
    for(unsigned j=0;j<8;++j){const float product=bf16f(w[u][j])*wide[u][j];A[r]=A[r]+product;}}
  }
 }
 // Remaining full chunks one at a time, then the ragged chunk (Multiply's tail), same order.
 for(;base+8u<=k;base+=256u){
  float wide[8];
  {const sycl::vec<float,4>*xv=reinterpret_cast<const sycl::vec<float,4>*>(x+base);const auto a0=xv[0],a1=xv[1];
   #pragma unroll
   for(unsigned j=0;j<4;++j){wide[j]=a0[j];wide[j+4]=a1[j];}}
  #pragma unroll
  for(unsigned r=0;r<R;++r){const uint32_t row=row0+r<rows?row0+r:row0;
   const auto w=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(W+size_t(row)*rb+size_t(base)*2u);
   #pragma unroll
   for(unsigned j=0;j<8;++j){const float product=bf16f(w[j])*wide[j];A[r]=A[r]+product;}}
 }
 if(base<k){
  #pragma unroll
  for(unsigned r=0;r<R;++r){const uint32_t row=row0+r<rows?row0+r:row0;const uint16_t* wr=reinterpret_cast<const uint16_t*>(W+size_t(row)*rb);
   float values[8],wide[8];
   for(unsigned j=0;base+j<k;++j){values[j]=bf16f(wr[base+j]);wide[j]=x[base+j];}
   for(unsigned j=0;base+j<k;++j){const float product=values[j]*wide[j];A[r]=A[r]+product;}}
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
// Quantized rows (Q8_0, Q6_K): kopt lane_dot's F32 branch per row (chunk k = 8l + 256i: decode8<T> values, then
// acc = acc + value*x in element order; ragged chunk through element()), read straight from global memory instead of
// the local-memory copy Multiply stages (same bytes, same values), R rows per subgroup, the same butterfly as above.
template<iq3::Type T,unsigned R> inline void quant_rows(const uint8_t* W,const float* x,float* y,uint32_t rows,uint32_t k,uint32_t rb,sycl::nd_item<1> it,uint32_t sgid){
 static_assert(R==1||R==2||R==4||R==8||R==16||R==32);
 constexpr unsigned LR=R==1?0:R==2?1:R==4?2:R==8?3:R==16?4:5;
 auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
 const uint32_t row0=sgid*R;if(row0>=rows)return;
 float A[R];
 #pragma unroll
 for(unsigned r=0;r<R;++r)A[r]=0.f;
 uint32_t c=lane*8u;
 for(;c+8u<=k;c+=256u){
  float xs[8];
  #pragma unroll
  for(unsigned j=0;j<8;++j)xs[j]=x[c+j];
  #pragma unroll
  for(unsigned r=0;r<R;++r){const uint32_t row=row0+r<rows?row0+r:row0;float values[8];iq3::kopt::decode8<T>(W+size_t(row)*rb,c,values);
   #pragma unroll
   for(unsigned j=0;j<8;++j){const float product=values[j]*xs[j];A[r]=A[r]+product;}}
 }
 if(c<k){
  #pragma unroll
  for(unsigned r=0;r<R;++r){const uint32_t row=row0+r<rows?row0+r:row0;const uint8_t* wr=W+size_t(row)*rb;
   float values[8];for(uint32_t j=0;c+j<k;++j)values[j]=iq3::element(T,wr,c+j);
   for(uint32_t j=0;c+j<k;++j){const float product=values[j]*x[c+j];A[r]=A[r]+product;}}
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
// Up to four dense matrices in one launch (kopt fused siblings): subgroups are partitioned by first_sub, and every
// matrix's rows run bf16_rows unchanged.
struct Mat {const uint8_t* w;const float* x;float* y;uint32_t rows,k,rb,first_sub;};
template<unsigned R,unsigned U> inline void bf16_multi(const std::array<Mat,4>& m,unsigned count,sycl::nd_item<1> it){
 const uint32_t gsub=uint32_t(it.get_global_linear_id()/32);unsigned j=0;
 for(unsigned t=1;t<count;++t)if(gsub>=m[t].first_sub)j=t;
 const Mat d=m[j];
 bf16_rows<R,U>(d.w,d.x,d.y,d.rows,d.k,d.rb,it,gsub-d.first_sub);
}
template<iq3::Type T,unsigned R> inline void quant_multi(const std::array<Mat,4>& m,unsigned count,sycl::nd_item<1> it){
 const uint32_t gsub=uint32_t(it.get_global_linear_id()/32);unsigned j=0;
 for(unsigned t=1;t<count;++t)if(gsub>=m[t].first_sub)j=t;
 const Mat d=m[j];
 quant_rows<T,R>(d.w,d.x,d.y,d.rows,d.k,d.rb,it,gsub-d.first_sub);
}
inline bool enabled(){static const bool on=[]{const char* e=std::getenv("OWNRT_DENSE_DECODE_V2");return e&&e[0]=='1';}();return on;}
}
