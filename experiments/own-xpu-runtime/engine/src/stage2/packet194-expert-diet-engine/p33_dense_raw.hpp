#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
// p33.dense.segment over raw-size Q6_K / Q8_0 rows (OWNRT_DENSE_RAW=1, lab 2026-10-26, default off; layouts and value
// proof in dense_raw.hpp). F32 activations and outputs.
//
// Each output keeps the exact sequence of Kernel<0,T,K,1,true> on the expanded rows (dense_lane<T,K,true>): lane l of a
// 32-lane subgroup walks the tiles 8l, 8l+256, ... in order; per tile it takes the 8 values (the expanded values, bit
// for bit), product = value*x, sum = sum + product for the 8 columns in order; then the adjacent-pair tree over the 32
// lanes. Here a subgroup carries R rows (row bases subgroup-uniform), the words of U block pairs (Q6_K) / U tiles (Q8_0)
// are loaded before their in-order arithmetic, and the R trees are reduced together by the transposing butterfly of
// p33_dense_v2.hpp (every node = lower lane block + upper lane block, the same operands in the same order). Token rows:
// subgroup g serves row group g % groups of token g / groups (each token row is an independent single-row product).
#include "stage2/packet194-expert-diet-engine/dense_raw.hpp"
#include "stage2/packet194-expert-diet-engine/prefill_reuse2.hpp"
#include <sycl/sycl.hpp>
#include <cstdint>
namespace p33::raw {
inline void load8(const float* x,float (&out)[8]){
 const sycl::vec<float,4>*xv=reinterpret_cast<const sycl::vec<float,4>*>(x);const auto a0=xv[0],a1=xv[1];
 #pragma unroll
 for(unsigned j=0;j<4;++j){out[j]=a0[j];out[j+4]=a1[j];}
}
template<iq3::Type T,unsigned K,unsigned R,unsigned U>
inline void dense_rows(const uint8_t* W,const float* X,float* Y,uint32_t rows,uint32_t rb,uint32_t groups,uint32_t tokens,sycl::nd_item<1> it){
 static_assert((T==iq3::Type::Q6_K||T==iq3::Type::Q8_0)&&K%256==0&&(R==1||R==2||R==4||R==8)&&U>=1);
 constexpr unsigned LR=R==1?0:R==2?1:R==4?2:3;
 auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
 const uint32_t logical=uint32_t(it.get_group_linear_id())*uint32_t(it.get_local_range(0)/32)+uint32_t(sg.get_group_linear_id());
 if(logical>=groups*tokens)return; // whole subgroup; no barriers in this kernel
 const uint32_t token=logical/groups,row0=(logical%groups)*R;
 const float* x=X+size_t(token)*K;float* y=Y+size_t(token)*rows;
 const uint8_t* wr[R];
 #pragma unroll
 for(unsigned r=0;r<R;++r)wr[r]=W+size_t(row0+r<rows?row0+r:row0)*rb; // a missing row reads row0, never stored
 float A[R];
 #pragma unroll
 for(unsigned r=0;r<R;++r)A[r]=0.f;
 if constexpr(T==iq3::Type::Q6_K) {
  static_assert(K%512==0);constexpr uint32_t P=K/512;
  #pragma unroll 1
  for(uint32_t p0=0;p0<P;p0+=U){
   denseraw::Q6Pair words[U][R]; // the weight words first; x is loaded tile by tile at its use (register pressure)
   #pragma unroll
   for(unsigned u=0;u<U;++u)if(p0+u<P){
    #pragma unroll
    for(unsigned r=0;r<R;++r)words[u][r]=denseraw::q6_load_pair(wr[r],K,p0+u,lane);}
   #pragma unroll
   for(unsigned u=0;u<U;++u)if(p0+u<P){
    #pragma unroll
    for(unsigned o=0;o<2;++o){ // block 2p, then 2p+1: each row's tiles stay in ascending order
     float xs[8];load8(x+512*(p0+u)+256*o+lane*8,xs);
     #pragma unroll
     for(unsigned r=0;r<R;++r){float v[8];denseraw::q6_pair_values(words[u][r],o,v);
      #pragma unroll
      for(unsigned j=0;j<8;++j){const float product=v[j]*xs[j];A[r]=A[r]+product;}}}}
  }
 } else {
  #pragma unroll 1
  for(uint32_t base=0;base<K;base+=256*U){
   denseraw::Q8Words words[U][R];
   #pragma unroll
   for(unsigned u=0;u<U;++u)if(base+256*u<K){
    #pragma unroll
    for(unsigned r=0;r<R;++r)words[u][r]=denseraw::q8_load(wr[r],K,base/256+u,lane);}
   #pragma unroll
   for(unsigned u=0;u<U;++u)if(base+256*u<K){
    float xs[8];load8(x+base+256*u+lane*8,xs);
    #pragma unroll
    for(unsigned r=0;r<R;++r){float v[8];denseraw::q8_values(words[u][r],v);
     #pragma unroll
     for(unsigned j=0;j<8;++j){const float product=v[j]*xs[j];A[r]=A[r]+product;}}}
  }
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
// Kernel object: sub-group size 32 and the GRF mode (128 or 256 registers) as kernel properties.
template<iq3::Type T,unsigned K,unsigned R,unsigned U,unsigned GRF> struct RowsKernel {
 const uint8_t* w;const float* x;float* y;uint32_t rows,rb,groups,tokens;
 void operator()(sycl::nd_item<1> it) const {dense_rows<T,K,R,U>(w,x,y,rows,rb,groups,tokens,it);}
 auto get(sycl::ext::oneapi::experimental::properties_tag) const {
  if constexpr(GRF==256)return sycl::ext::oneapi::experimental::properties{sycl::ext::oneapi::experimental::sub_group_size<32>,sycl::ext::intel::experimental::grf_size<256>};
  else return sycl::ext::oneapi::experimental::properties{sycl::ext::oneapi::experimental::sub_group_size<32>};
 }
};
// Generation-2 prefill token-row tiles (prefill_reuse2.hpp) over raw rows: the same 8 values per lane chunk as above.
template<iq3::Type T> struct Reuse2Raw {
 static bool active(uint32_t k,uint32_t step,unsigned lane){return reuse2::chunk8_active(k,step,lane);}
 static void decode(const uint8_t* row,uint32_t k,uint32_t step,unsigned lane,float (&v)[8]){denseraw::decode8<T>(row,k,step,lane,v);}
 template<class G> static void inputs(G sg,const float* x,uint32_t step,unsigned lane,float (&in)[8]){reuse2::chunk8_inputs(sg,x,step,lane,in);}
};
// Kernel configuration RUG (three digits: R rows per subgroup, U block pairs (Q6_K) / tiles (Q8_0) of loads ahead, G = 1
// for 128 or 2 for 256 registers): OWNRT_DENSE_RAW_Q6=RUG / OWNRT_DENSE_RAW_Q8=RUG, else the measured default.
inline unsigned config(iq3::Type t,unsigned fallback){
 static const int q6=[]{const char* e=std::getenv("OWNRT_DENSE_RAW_Q6");return e?std::atoi(e):-1;}();
 static const int q8=[]{const char* e=std::getenv("OWNRT_DENSE_RAW_Q8");return e?std::atoi(e):-1;}();
 const int v=t==iq3::Type::Q6_K?q6:q8;return v>0?unsigned(v):fallback;
}
} // namespace p33::raw
