#pragma once
// Batched-prefill dense token-row kernels, generation 2 (lab, 2026-10-26). Default off: OWNRT_PREFILL_REUSE2=1 selects
// them for F32 dense token rows (tokens > 1); without it nothing here is ever launched.
//
// One 32-lane subgroup owns a register tile of RW weight rows x T token rows. Per 256-column step every lane decodes its
// 8 weight values of each of the RW rows once (the format's own decode expression) and applies them to each of the T
// tokens. Accumulator (row, token) of lane l sees exactly the single-row sequence of the format's existing kernel:
// steps in ascending order, the 8 values of a step in ascending order, product computed first, then sum = sum + product;
// then the explicit adjacent-pair subgroup tree (width 1..16, lane%(2w)==0 adds lane+w). Lanes whose chunk lies past the
// row end skip the step (their sum is unchanged), as in the single-row loop. Only which hardware thread performs an
// output's sequence changes. Index math is 32-bit (64-bit integer math is emulated on the B70), except one 64-bit
// row/token base per pointer, formed once per subgroup.
//
// Formats (F): static bool active(uint32_t k,uint32_t step,unsigned lane);
//              static void decode(const uint8_t* row,uint32_t k,uint32_t step,unsigned lane,float (&v)[8]);
//              static void inputs(sub_group sg,const float* x,uint32_t step,unsigned lane,float (&in)[8]);
#include <sycl/sycl.hpp>
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include "stage2/packet2/kernels/math.hpp"
namespace reuse2 {
inline bool enabled(){static const bool on=[]{const char* e=std::getenv("OWNRT_PREFILL_REUSE2");return e&&e[0]=='1';}();return on;}
// Batched-prefill chunk counter (diagnostic config cycling): prefill_chunk advances it once per chunk.
inline uint64_t& chunk_counter(){static uint64_t n=0;return n;}
// Tile configuration index for one kernel family, 0..count-1, or count for the family's existing (canonical) kernel:
// OWNRT_PREFILL_REUSE2_<FAMILY>=i fixes it (default: `fallback`); OWNRT_PREFILL_REUSE2_CYCLE=1 (diagnostic) uses
// chunk % (count+1) instead, so one profiled run times every configuration and the canonical kernel side by side. Every
// configuration is exact; the choice changes only speed.
inline unsigned config(const char* family,unsigned count,unsigned fallback){
 static const bool cycle=[]{const char* e=std::getenv("OWNRT_PREFILL_REUSE2_CYCLE");return e&&e[0]=='1';}();
 if(cycle)return unsigned(chunk_counter()%(count+1));
 char name[96]="OWNRT_PREFILL_REUSE2_";size_t n=21;for(const char* p=family;*p&&n+1<sizeof(name);++p)name[n++]=*p;name[n]=0;
 const char* e=std::getenv(name);if(!e||!*e)return std::min(fallback,count);
 const int v=std::atoi(e);return v>=0&&unsigned(v)<=count?unsigned(v):std::min(fallback,count);
}
// Lane chunks of 8 consecutive columns: lane l owns columns 256*step + 8*l + j (kopt / p33 dense lanes).
inline bool chunk8_active(uint32_t k,uint32_t step,unsigned lane){return step*256u+lane*8u+8u<=k;}
template<class G> inline void chunk8_inputs(G,const float* x,uint32_t step,unsigned lane,float (&in)[8]){
 const auto* p=reinterpret_cast<const sycl::vec<float,4>*>(x+(step*256u+lane*8u));const auto lo=p[0],hi=p[1];
 #pragma unroll
 for(unsigned j=0;j<4;++j){in[j]=lo[j];in[j+4]=hi[j];}
}
// Lane columns of stride 32: lane l owns columns 256*step + 32*g + l, g = 0..7 (dense packed blocks).
inline bool stride32_active(uint32_t k,uint32_t step,unsigned){return step*256u<k;}
// One subgroup block read of 8 x 32 floats (16-byte aligned rows; the caller checks): lane l receives
// x[256*step + 32*g + l] as element g, the same values as eight lane loads.
template<class G> inline void stride32_inputs(G sg,const float* x,uint32_t step,unsigned,float (&in)[8]){
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
 const auto v=sg.template load<8>(sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::yes>(x+step*256u));
#pragma clang diagnostic pop
 #pragma unroll
 for(unsigned g=0;g<8;++g)in[g]=v[g];
}
// Dense packed blocks Q4_K/Q5_K/IQ4_XS (T = 12/13/23, 256-column blocks): the values of block_lane_sum /
// DenseBlockRows, block = step and group g = 0..7; E::element<T> is denseblock::block_element<T>.
template<unsigned T,class E> struct Block32 {
 static bool active(uint32_t k,uint32_t step,unsigned lane){return stride32_active(k,step,lane);}
 static void decode(const uint8_t* row,uint32_t,uint32_t step,unsigned lane,float (&v)[8]){
  constexpr uint32_t bytes=T==12?144:T==13?176:136;
  const uint8_t* packed=row+step*bytes;const float d=iq3::half(iq3::u16(packed));
  float dmin=0;if constexpr(T==12||T==13)dmin=iq3::half(iq3::u16(packed+2));
  #pragma unroll
  for(unsigned g=0;g<8;++g)v[g]=E::template element<T>(packed,d,dmin,g,lane);
 }
 template<class G> static void inputs(G sg,const float* x,uint32_t step,unsigned lane,float (&in)[8]){stride32_inputs(sg,x,step,lane,in);}
};
// Dense packed blocks with the decode of gsqn::v2::rows_fast (dense_decode_v2.hpp, OWNRT_DENSE_DECODE_V2, the one-row
// decode kernel of these sites), 2026-10-30, research/multirow-verify-2026-10-30, small-row tiles only: the same values as
// Block32 (block_element's field equations; IQ4_XS levels by iq3::iq4_level, the same integers as block_element's table)
// with one header load per block (Q4_K/Q5_K: 16 bytes; IQ4_XS: 8 bytes) and the code bytes per lane. The row base and
// the block size keep the header loads aligned (rows_fast's fits<T>: row bytes and base 16-byte aligned for Q4_K/Q5_K,
// 8 for IQ4_XS; the caller checks).
template<unsigned T> struct BlockV2 {
 static constexpr uint32_t bytes=T==12?144:T==13?176:136;
 static bool active(uint32_t k,uint32_t step,unsigned lane){return stride32_active(k,step,lane);}
 static void decode(const uint8_t* row,uint32_t,uint32_t step,unsigned lane,float (&v)[8]){
  const uint8_t* b=row+step*bytes;
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
    const float product0=factor*float(code);v[group]=product0-offset;
   }
  }else{
   const sycl::vec<uint32_t,2> h=*reinterpret_cast<const sycl::vec<uint32_t,2>*>(b);
   const float d=iq3::half(h[0]&0xffffu);const uint32_t sh=h[0]>>16,sl=h[1];
   #pragma unroll
   for(unsigned group=0;group<8;++group){
    const unsigned scale=((sl>>(8*(group/2)+4*(group%2)))&15)|(((sh>>(2*group))&3)<<4);
    const unsigned code=(b[8+group*16+lane%16]>>(4*(lane/16)))&15;
    const float factor=d*float(int(scale)-32);
    v[group]=factor*float(iq3::iq4_level(code));
   }
  }
 }
 template<class G> static void inputs(G sg,const float* x,uint32_t step,unsigned lane,float (&in)[8]){stride32_inputs(sg,x,step,lane,in);}
};
// p33 expanded rows (variant 6: k signed bytes, then one F32 scale per Group columns; Q6_K Group 16, Q8_0 32): the
// values of p33::dense_lane / DenseRows, value = scale*float(signed8(code)). Rows and k are multiples of 4 bytes (the
// caller checks), so the 8 code bytes and the scale are read as aligned 32-bit words; the same bytes, the same values.
template<unsigned Group> struct Expanded8 {
 static bool active(uint32_t k,uint32_t step,unsigned lane){return chunk8_active(k,step,lane);}
 static void decode(const uint8_t* w,uint32_t k,uint32_t step,unsigned lane,float (&v)[8]){
  const uint32_t tile=step*256u+lane*8u;
  const float scale=iq3::bits_float(*reinterpret_cast<const uint32_t*>(w+k+4u*(tile/Group)));
  const uint32_t* codes=reinterpret_cast<const uint32_t*>(w+tile);const uint32_t lo=codes[0],hi=codes[1];
  #pragma unroll
  for(unsigned j=0;j<8;++j){const uint8_t code=uint8_t(((j<4?lo:hi)>>(8*(j&3)))&255u);v[j]=scale*float(int(int8_t(code)));} // int(int8_t(b)) == iq3::signed8(b) for every byte
 }
 template<class G> static void inputs(G sg,const float* x,uint32_t step,unsigned lane,float (&in)[8]){chunk8_inputs(sg,x,step,lane,in);}
};
// Raw BF16 rows (16-byte aligned, the caller checks): kopt MultiplyRowsLean's values, bits << 16 with no NaN-quiet
// test (as the decode path's F32 fast loop).
struct BF16x8 {
 static bool active(uint32_t k,uint32_t step,unsigned lane){return chunk8_active(k,step,lane);}
 static void decode(const uint8_t* row,uint32_t,uint32_t step,unsigned lane,float (&v)[8]){
  const auto bits=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(row+(step*256u+lane*8u)*2u);
  #pragma unroll
  for(unsigned j=0;j<8;++j)v[j]=iq3::bits_float(uint32_t(bits[j])<<16);
 }
 template<class G> static void inputs(G sg,const float* x,uint32_t step,unsigned lane,float (&in)[8]){chunk8_inputs(sg,x,step,lane,in);}
};
// Raw quantized blocks decoded 8 columns at a time (D::decode8 is iq3::kopt::decode8<T>, as kopt MultiplyRows).
template<class D> struct Decode8 {
 static bool active(uint32_t k,uint32_t step,unsigned lane){return chunk8_active(k,step,lane);}
 static void decode(const uint8_t* row,uint32_t,uint32_t step,unsigned lane,float (&v)[8]){D::decode8(row,step*256u+lane*8u,v);}
 template<class G> static void inputs(G sg,const float* x,uint32_t step,unsigned lane,float (&in)[8]){chunk8_inputs(sg,x,step,lane,in);}
};
template<class F,unsigned RW,unsigned T,unsigned S,unsigned GRF,unsigned O=0> struct Tile {
 const uint8_t* w;const float* x;float* y;uint32_t rows,k,tokens,rb,ttiles,total;
 void operator()(sycl::nd_item<1> it) const {
  const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
  const uint32_t logical=uint32_t(it.get_group(0))*S+uint32_t(sg.get_group_linear_id());
  if(logical>=total)return; // whole subgroup: no barriers in this kernel
  // O = 0: token tiles of one row tile are adjacent (a work-group shares weight rows); O = 1: row tiles adjacent.
  const uint32_t rtiles=total/ttiles;
  const uint32_t row0=(O==0?logical/ttiles:logical%rtiles)*RW,tok0=(O==0?logical%ttiles:logical/rtiles)*T;
  const uint8_t* wr[RW];const float* xt[T];
  #pragma unroll
  for(unsigned r=0;r<RW;++r)wr[r]=w+size_t(std::min(row0+r,rows-1u))*rb;
  #pragma unroll
  for(unsigned t=0;t<T;++t)xt[t]=x+size_t(std::min(tok0+t,tokens-1u))*k;
  float acc[RW][T];
  #pragma unroll
  for(unsigned r=0;r<RW;++r)
   #pragma unroll
   for(unsigned t=0;t<T;++t)acc[r][t]=0.f;
  // Every lane is active in the first k/256 steps (branch-free, unrolled U times so loads can be scheduled early);
  // a ragged last step (k % 256, chunk8 formats only) runs only on the lanes whose chunk lies inside the row.
  auto step=[&](uint32_t s){
   float v[RW][8];
   #pragma unroll
   for(unsigned r=0;r<RW;++r)F::decode(wr[r],k,s,lane,v[r]);
   #pragma unroll
   for(unsigned t=0;t<T;++t){
    float in[8];F::inputs(sg,xt[t],s,lane,in);
    #pragma unroll
    for(unsigned r=0;r<RW;++r)
     #pragma unroll
     for(unsigned j=0;j<8;++j){const float product=v[r][j]*in[j];acc[r][t]=acc[r][t]+product;}
   }
  };
  constexpr unsigned U=RW*T<=8?4:RW*T<=16?2:1;
  const uint32_t full=k/256u;
  #pragma unroll U
  for(uint32_t s=0;s<full;++s)step(s);
  if(full*256u<k&&F::active(k,full,lane))step(full);
  // Reduction: for every output the adjacent-pair tree of the single-row kernels (width w = 1, 2, .., 16: the partial of
  // lanes [l, l+w) plus the partial of lanes [l+w, l+2w), lower range on the left). Groups of G = min(RW*T, 32)
  // accumulators share the shuffles: at width w < G, lanes with bit w clear keep the even-position accumulators and
  // lanes with bit w set the odd ones, each adding the same two partials in the same order (a butterfly transpose).
  // After log2(G) levels lane l owns accumulator l % G; the remaining widths add lane l+w into lane l. Lanes 0..G-1
  // then hold the G results and store them with one instruction.
  // T that is not a power of two (2026-10-30, small-row tiles: T = 3) is padded to Tp in the reduction only: the padding
  // accumulators are zero, never stored, and no real output's additions involve them (each butterfly addition combines
  // the same output's two lane partials). For a power-of-two T, Tp == T and nothing changes.
  constexpr unsigned Tp=T<=1?1:T<=2?2:T<=4?4:T<=8?8:T<=16?16:32;
  constexpr unsigned N=RW*Tp,G=N<32?N:32;
  static_assert((N&(N-1))==0,"tile size must be a power of two");
  float flat[N];
  #pragma unroll
  for(unsigned r=0;r<RW;++r)
   #pragma unroll
   for(unsigned t=0;t<Tp;++t)flat[r*Tp+t]=t<T?acc[r][t<T?t:0]:0.f;
  #pragma unroll
  for(unsigned g0=0;g0<N;g0+=G){
   float a[G];
   #pragma unroll
   for(unsigned i=0;i<G;++i)a[i]=flat[g0+i];
   #pragma unroll
   for(unsigned w=1,n=G;n>1;w*=2,n/=2){
    const bool upper=(lane&w)!=0;
    #pragma unroll
    for(unsigned i=0;i<n/2;++i){
     const float send=upper?a[2*i]:a[2*i+1];
     const float recv=sycl::permute_group_by_xor(sg,send,w);
     const float left=upper?recv:a[2*i],right=upper?a[2*i+1]:recv;
     a[i]=left+right;
    }
   }
   float sum=a[0];
   #pragma unroll
   for(unsigned w=G;w<32;w*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+w)%32);if(((lane/G)%(2*w/G))==0)sum=sum+rhs;}
   if(lane<G){const unsigned i=g0+lane,r=i/Tp,t=i%Tp;if(t<T&&row0+r<rows&&tok0+t<tokens)y[(tok0+t)*rows+(row0+r)]=sum;}
  }
 }
 auto get(sycl::ext::oneapi::experimental::properties_tag) const {
#ifndef REUSE2_TEST_NO_GRF // CPU-device tests only: OpenCL CPU rejects the large-GRF build option
  if constexpr(GRF==256)return sycl::ext::oneapi::experimental::properties{sycl::ext::oneapi::experimental::sub_group_size<32>,sycl::ext::intel::experimental::grf_size<256>};
  else
#endif
  return sycl::ext::oneapi::experimental::properties{sycl::ext::oneapi::experimental::sub_group_size<32>};
 }
};
// Kernel object and range for y[token*rows + row] over tokens x rows outputs (F32 activations x[token*k + column]).
template<class F,unsigned RW,unsigned T,unsigned S,unsigned GRF,unsigned O=0> struct Prepared {Tile<F,RW,T,S,GRF,O> kernel;sycl::nd_range<1> range;};
template<class F,unsigned RW,unsigned T,unsigned S,unsigned GRF,unsigned O=0>
Prepared<F,RW,T,S,GRF,O> prepare(const uint8_t* w,const float* x,float* y,uint32_t rows,uint32_t k,uint32_t tokens,uint32_t rb){
 Tile<F,RW,T,S,GRF,O> kernel{w,x,y,rows,k,tokens,rb,(tokens+T-1)/T,0};
 kernel.total=((rows+RW-1)/RW)*kernel.ttiles;const size_t groups=(kernel.total+S-1)/S;
 return {kernel,sycl::nd_range<1>(groups*S*32,S*32)};
}
} // namespace reuse2
