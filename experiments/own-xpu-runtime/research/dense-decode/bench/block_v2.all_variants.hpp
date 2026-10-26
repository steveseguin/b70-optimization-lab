#pragma once
// Dense packed-block decode GEMV, R rows per subgroup (lab 2026-10-26, OWNRT_DENSE_DECODE_V2=1, default off). Decode
// only: F32 activations/outputs, one dense matrix, shared input row. Every output keeps DenseBlockOperation's value:
// lane l accumulates sum = sum + block_element(...)*x[k] from 0.f over k = block*256 + group*32 + l in (block, group)
// order (block_lane_sum, same decode call and d/dmin conversion), then the adjacent-pair tree over the 32 lanes. Here
// a subgroup carries R consecutive rows: x[k] is loaded once for the R rows, and the R trees are reduced together by a
// transposing butterfly (lower lane block + upper lane block at every node, as the tree). Lane l ends with row
// row0 + (l & (R-1)). Prefill row kernels (DenseBlockRows, reuse2) are untouched.
#include <sycl/sycl.hpp>
#include <cstdint>
#include <cstdlib>
namespace denseblock::v2 {
inline bool enabled(){static const bool on=[]{const char* e=std::getenv("OWNRT_DENSE_DECODE_V2");return e&&e[0]=='1';}();return on;}
template<unsigned T,unsigned R> inline void rows(const uint8_t* W,const float* x,float* y,uint32_t nrows,uint32_t columns,uint32_t row_bytes,sycl::nd_item<1> it){
 static_assert(R==1||R==2||R==4||R==8);
 constexpr unsigned LR=R==1?0:R==2?1:R==4?2:3;
 constexpr uint32_t bytes=T==12?144:T==13?176:136;
 auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
 const uint32_t row0=uint32_t(it.get_global_linear_id()/32)*R;if(row0>=nrows)return;
 const uint8_t* w[R];
 #pragma unroll
 for(unsigned r=0;r<R;++r)w[r]=W+size_t(row0+r<nrows?row0+r:row0)*row_bytes; // a missing row reads row0, never stored
 float A[R];
 #pragma unroll
 for(unsigned r=0;r<R;++r)A[r]=0.f;
 for(uint32_t block=0;block<columns/256;++block){
  float d[R],dmin[R];
  #pragma unroll
  for(unsigned r=0;r<R;++r){const uint8_t* packed=w[r]+block*bytes;d[r]=iq3::half(iq3::u16(packed));dmin[r]=0;if constexpr(T==12||T==13)dmin[r]=iq3::half(iq3::u16(packed+2));}
  #pragma unroll
  for(unsigned group=0;group<8;++group){
   const uint32_t k=block*256+group*32+lane;const float input=x[k];
   #pragma unroll
   for(unsigned r=0;r<R;++r){const float weight=block_element<T>(w[r]+block*bytes,d[r],dmin[r],group,lane);const float product=weight*input;A[r]=A[r]+product;}
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
 if(lane<R&&row<nrows)y[row]=A[0];
}

// rows_fast: the same values as block_element, decoded with fewer memory messages. Per block: one header load (Q4_K /
// Q5_K: 16 bytes = d, dmin, the 12 scale bytes; IQ4_XS: 8 bytes = d, scales_h, scales_l), scale/min per group by
// block_element's bit expressions, factor = d*float(scale) and offset = dmin*float(minimum) (Q4_K/Q5_K) or
// factor = d*float(int(scale)-32) (IQ4_XS) exactly as there; per lane one qh byte (Q5_K) and one code byte per group
// pair (or per group, IQ4_XS); weight = factor*float(code) - offset, or factor*float(level) with level = iq4_level(code)
// (the same integers as block_element's table). Accumulation and tree as rows().
template<unsigned T,unsigned R> inline void rows_fast(const uint8_t* W,const float* x,float* y,uint32_t nrows,uint32_t columns,uint32_t row_bytes,sycl::nd_item<1> it){
 static_assert(R==1||R==2||R==4);
 constexpr unsigned LR=R==1?0:R==2?1:2;
 constexpr uint32_t bytes=T==12?144:T==13?176:136;
 auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
 // Subgroup index from the group id and the subgroup id (both uniform): row offsets, block headers and the per-group
 // scale arithmetic are then subgroup-uniform values.
 const uint32_t row0=(uint32_t(it.get_group_linear_id())*uint32_t(it.get_local_range(0)/32)+uint32_t(sg.get_group_linear_id()))*R;if(row0>=nrows)return;
 uint32_t off[R];
 #pragma unroll
 for(unsigned r=0;r<R;++r)off[r]=(row0+r<nrows?row0+r:row0)*row_bytes;
 float A[R];
 #pragma unroll
 for(unsigned r=0;r<R;++r)A[r]=0.f;
 for(uint32_t block=0;block<columns/256;++block){
  float xs[8];
  #pragma unroll
  for(unsigned g=0;g<8;++g)xs[g]=x[block*256+g*32+lane];
  #pragma unroll
  for(unsigned r=0;r<R;++r){
   const uint8_t* b=W+off[r]+block*bytes;
   if constexpr(T==12||T==13){
    const sycl::vec<uint32_t,4> h=*reinterpret_cast<const sycl::vec<uint32_t,4>*>(b);
    const float d=iq3::half(h[0]&0xffffu),dmin=iq3::half(h[0]>>16);
    uint8_t s[12];
    #pragma unroll
    for(unsigned i=0;i<12;++i)s[i]=uint8_t(h[1+i/4]>>(8*(i%4)));
    constexpr unsigned low_offset=T==12?16:48;
    uint32_t qh=0;if constexpr(T==13)qh=b[16+lane];
    uint32_t cb[4];
    #pragma unroll
    for(unsigned p=0;p<4;++p)cb[p]=b[low_offset+p*32+lane];
    #pragma unroll
    for(unsigned group=0;group<8;++group){
     const unsigned scale=group<4?s[group]&63:(s[group+4]&15)|((s[group-4]>>6)<<4);
     const unsigned minimum=group<4?s[group+4]&63:(s[group+4]>>4)|((s[group]>>6)<<4);
     unsigned code=(cb[group/2]>>(4*(group%2)))&15;
     if constexpr(T==13)code|=((qh>>group)&1)<<4;
     const float factor=d*float(scale);const float offset=dmin*float(minimum);
     const float product0=factor*float(code);const float weight=product0-offset;
     const float product=weight*xs[group];A[r]=A[r]+product;
    }
   }else{
    const sycl::vec<uint32_t,2> h=*reinterpret_cast<const sycl::vec<uint32_t,2>*>(b);
    const float d=iq3::half(h[0]&0xffffu);const uint32_t sh=h[0]>>16,sl=h[1];
    #pragma unroll
    for(unsigned group=0;group<8;++group){
     const unsigned scale=((sl>>(8*(group/2)+4*(group%2)))&15)|(((sh>>(2*group))&3)<<4);
     const unsigned code=(b[8+group*16+lane%16]>>(4*(lane/16)))&15;
     const float factor=d*float(int(scale)-32);
     const float weight=factor*float(iq3::iq4_level(code));
     const float product=weight*xs[group];A[r]=A[r]+product;
    }
   }
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
 if(lane<R&&row<nrows)y[row]=A[0];
}
}
