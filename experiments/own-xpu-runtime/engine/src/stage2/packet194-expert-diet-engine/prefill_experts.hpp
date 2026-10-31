#pragma once
// Expert-grouped routed token rows for batched prefill (lab, 2026-10-26). Default off: OWNRT_PREFILL_EXPERTS=1 selects
// them for F32 routed sites of a prefill chunk; without it nothing here is ever launched.
//
// A chunk's routed site has n = rows x top slots, slot s reading input row x[s] and writing y[s*span + row] with route
// s = {expert, row_begin, row_count}. The existing kernels decode the expert's weights once per slot. Here:
//  1. Bucket (one work-group): status[s] = !valid(route) exactly as the existing kernels write it; slots with a valid
//     full route (row_begin 0, row_count rows) are grouped by expert in slot order and cut into tiles of at most T slots;
//     every other slot (invalid or partial route) gets a tile of its own with its own route. Integer work only.
//  2. Tile kernel: one 32-lane subgroup owns RW weight rows of one tile's expert and the tile's slots (<= T). Per
//     256-column step each lane decodes its 8 values of each row once, with the format's own decode expression, and
//     applies them to each slot of the tile. Output (slot, row) of lane l sees the single-row sequence of the existing
//     kernel for that format: steps ascending, the 8 values of a step ascending, product first, then sum = sum + product
//     (lanes whose chunk lies past the row end skip the step); then the adjacent-pair subgroup tree (as a butterfly
//     transpose, the same pairs in the same order: see prefill_reuse2.hpp). Rows past row_count, and every row of an
//     invalid route, are written as the same quiet NaN (0x7fc00000) as the existing kernels.
// Only which hardware thread performs an output's sequence changes.
#include <sycl/sycl.hpp>
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include "stage2/packet2/kernels/math.hpp"
#include "stage2/packet194-expert-diet-engine/prefill_reuse2.hpp"
namespace xgroup {
inline bool enabled(){static const bool on=[]{const char* e=std::getenv("OWNRT_PREFILL_EXPERTS");return e&&e[0]=='1';}();return on;}
// Tile configuration for one site family, 0..count-1, or count for the existing kernel: OWNRT_PREFILL_EXPERTS_<FAMILY>=i
// fixes it (default `fallback`); OWNRT_PREFILL_EXPERTS_CYCLE=1 (diagnostic) uses chunk % (count+1) (reuse2's chunk
// counter), so one profiled run times every configuration and the existing kernel side by side. All are exact.
inline unsigned config(const char* family,unsigned count,unsigned fallback){
 static const bool cycle=[]{const char* e=std::getenv("OWNRT_PREFILL_EXPERTS_CYCLE");return e&&e[0]=='1';}();
 if(cycle)return unsigned(reuse2::chunk_counter()%(count+1));
 char name[96]="OWNRT_PREFILL_EXPERTS_";size_t n=22;for(const char* p=family;*p&&n+1<sizeof(name);++p)name[n++]=*p;name[n]=0;
 const char* e=std::getenv(name);if(!e||!*e)return std::min(fallback,count);
 const int v=std::atoi(e);return v>=0&&unsigned(v)<=count?unsigned(v):std::min(fallback,count);
}
inline constexpr uint32_t desc_words=5; // tile: weight row base (expert*rows + row_begin), row_count, first, count, valid
inline constexpr uint32_t special=0xffffffffu;
// OWNRT_PREFILL_EXPERT_PARITY (2026-10-30, research/tp/prefill-tp-overhead-2026-10-30): a slot whose route is the skip route
// {skip_expert, 0, 0} (kopt::route_parity: another card computes it) gets no tile and no output write, and status 0.
// Route kernels never produce this expert id, so nothing changes for any other route.
inline constexpr uint32_t skip_expert=0xfffffffeu,skip_key=0xfffffffeu;
inline constexpr uint32_t bucket_items=512;
// Bucket: one work-group of bucket_items work-items. keys: local n words.
struct Bucket {
 const iq3::Route* routes;uint32_t* status;uint32_t* order;uint32_t* tiles;uint32_t* tile_count;
 uint32_t n,experts,rows,span,T;sycl::local_accessor<uint32_t,1> keys;
 void operator()(sycl::nd_item<1> it) const {
  const auto g=it.get_group();const uint32_t lid=uint32_t(it.get_local_linear_id());
  for(uint32_t i=lid;i<n;i+=bucket_items){
   const iq3::Route r=routes[i];const bool v=iq3::valid_route(r,experts,rows,span);
   const bool skip=r.expert_id==skip_expert&&r.row_begin==0u&&r.row_count==0u;
   status[i]=v||skip?0u:1u;keys[i]=skip?skip_key:v&&r.row_begin==0&&r.row_count==rows?r.expert_id:special;
  }
  sycl::group_barrier(g);
  uint32_t mine=0,mytiles=0,myspecial=0;
  for(uint32_t e=lid;e<experts;e+=bucket_items){uint32_t c=0;for(uint32_t i=0;i<n;++i)c+=keys[i]==e?1u:0u;mine+=c;mytiles+=(c+T-1)/T;}
  for(uint32_t i=lid;i<n;i+=bucket_items)myspecial+=keys[i]==special?1u:0u;
  const uint32_t slot_off=sycl::exclusive_scan_over_group(g,mine,sycl::plus<uint32_t>());
  const uint32_t tile_off=sycl::exclusive_scan_over_group(g,mytiles,sycl::plus<uint32_t>());
  const uint32_t special_off=sycl::exclusive_scan_over_group(g,myspecial,sycl::plus<uint32_t>());
  const uint32_t std_slots=sycl::reduce_over_group(g,mine,sycl::plus<uint32_t>());
  const uint32_t std_tiles=sycl::reduce_over_group(g,mytiles,sycl::plus<uint32_t>());
  const uint32_t specials=sycl::reduce_over_group(g,myspecial,sycl::plus<uint32_t>());
  uint32_t so=slot_off,to=tile_off;
  for(uint32_t e=lid;e<experts;e+=bucket_items){
   uint32_t c=0;
   for(uint32_t i=0;i<n;++i)if(keys[i]==e){
    if(c%T==0){uint32_t* d=tiles+(to+c/T)*desc_words;d[0]=e*rows;d[1]=rows;d[2]=so+c;d[3]=0;d[4]=1;}
    order[so+c]=i;++c;
   }
   for(uint32_t j=0;j*T<c;++j)tiles[(to+j)*desc_words+3]=std::min(T,c-j*T);
   so+=c;to+=(c+T-1)/T;
  }
  uint32_t k=special_off;
  for(uint32_t i=lid;i<n;i+=bucket_items)if(keys[i]==special){
   const iq3::Route r=routes[i];const bool v=iq3::valid_route(r,experts,rows,span);
   const uint32_t p=std_slots+k,t=std_tiles+k;order[p]=i;
   uint32_t* d=tiles+t*desc_words;d[0]=v?r.expert_id*rows+r.row_begin:0u;d[1]=v?r.row_count:0u;d[2]=p;d[3]=1;d[4]=v?1u:0u;++k;
  }
  if(lid==0)*tile_count=std_tiles+specials;
 }
};
// Lane-column formats. Stride32 (S32): lane l owns columns 256*step + 32*g + l, g = 0..7; a ragged last step has
// gv = (k - 256*step)/32 < 8 groups (k % 32 == 0). Chunk8 (C8): lane l owns columns 256*step + 8*l + j, j = 0..7; in a
// ragged last step only the lanes whose chunk fits run it.
// D::decode(row, step, lane, gv, v[8]) (S32) / D::decode8(row, column, v[8]) (C8) give the existing kernels' values.
template<class D> struct S32 {static constexpr bool chunk8=false;
 static void decode(const uint8_t* row,uint32_t step,unsigned lane,unsigned gv,float (&v)[8]){D::decode(row,step,lane,gv,v);}};
template<class D> struct C8 {static constexpr bool chunk8=true;
 static void decode(const uint8_t* row,uint32_t step,unsigned lane,unsigned,float (&v)[8]){D::decode8(row,step*256u+lane*8u,v);}};
template<class F,unsigned RW,unsigned T,unsigned S,unsigned GRF> struct Tiles {
 const uint8_t* w;const float* x;float* y;const uint32_t* order;const uint32_t* tiles;const uint32_t* tile_count;
 uint32_t span,k,rb,rtiles,G,rl,rgroups; // rl consecutive row tiles per subgroup, rgroups = ceil(rtiles / rl)
 void operator()(sycl::nd_item<1> it) const {
  const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
  const uint32_t logical=uint32_t(it.get_group(0))*S+uint32_t(sg.get_group_linear_id());
  if(logical>=rgroups*G)return; // whole subgroup: no barriers in this kernel
  const uint32_t rg=logical%rgroups,first_tile=logical/rgroups,ntiles=*tile_count;
  const float nan=iq3::bits_float(0x7fc00000);
  for(uint32_t tile=first_tile;tile<ntiles;tile+=G){
   const uint32_t* d=tiles+tile*desc_words;
   const uint32_t base=d[0],rcount=d[1],first=d[2],cnt=d[3],valid=d[4];
   const float* xt[T];
   #pragma unroll
   for(unsigned t=0;t<T;++t)xt[t]=x+size_t(order[first+std::min<uint32_t>(t,cnt-1u)])*k;
   for(uint32_t rr=0;rr<rl;++rr){
   const uint32_t row0=(rg*rl+rr)*RW;
   if(row0>=span)break;
   if(!valid||rcount==0){
    // Every row of an invalid route (or an empty row range) is NaN, as in the existing kernels.
    for(unsigned i=lane;i<RW*T;i+=32){const unsigned r=i/T,t=i%T;if(t<cnt&&row0+r<span)y[order[first+t]*span+row0+r]=nan;}
    continue;
   }
   const uint8_t* wr[RW];
   #pragma unroll
   for(unsigned r=0;r<RW;++r)wr[r]=w+size_t(base+std::min(row0+r,rcount-1u))*rb;
   float acc[RW][T];
   #pragma unroll
   for(unsigned r=0;r<RW;++r)
    #pragma unroll
    for(unsigned t=0;t<T;++t)acc[r][t]=0.f;
   auto step=[&](uint32_t s,unsigned gv){
    float v[RW][8];
    #pragma unroll
    for(unsigned r=0;r<RW;++r)F::decode(wr[r],s,lane,gv,v[r]);
    #pragma unroll
    for(unsigned t=0;t<T;++t){
     if(t>=cnt)break; // uniform: the tile's slot count
     float in[8];
     if constexpr(F::chunk8){
      const auto* p=reinterpret_cast<const sycl::vec<float,4>*>(xt[t]+(s*256u+lane*8u));const auto lo=p[0],hi=p[1];
      #pragma unroll
      for(unsigned j=0;j<4;++j){in[j]=lo[j];in[j+4]=hi[j];}
     } else if(gv==8){
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
      const auto b=sg.template load<8>(sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::yes>(xt[t]+s*256u));
#pragma clang diagnostic pop
      #pragma unroll
      for(unsigned j=0;j<8;++j)in[j]=b[j];
     } else {
      #pragma unroll
      for(unsigned j=0;j<8;++j)in[j]=j<gv?xt[t][s*256u+j*32u+lane]:0.f;
     }
     #pragma unroll
     for(unsigned r=0;r<RW;++r)
      #pragma unroll
      for(unsigned j=0;j<8;++j)if(j<gv){const float product=v[r][j]*in[j];acc[r][t]=acc[r][t]+product;}
    }
   };
   const uint32_t full=k/256u;
   for(uint32_t s=0;s<full;++s)step(s,8);
   if(full*256u<k){
    if constexpr(F::chunk8){if(full*256u+lane*8u+8u<=k)step(full,8);}
    else step(full,(k-full*256u)/32u);
   }
   // Reduction: the adjacent-pair tree, butterfly-transposed over groups of G accumulators (prefill_reuse2.hpp).
   constexpr unsigned N=RW*T,GA=N<32?N:32;
   static_assert((N&(N-1))==0,"tile size must be a power of two");
   float flat[N];
   #pragma unroll
   for(unsigned r=0;r<RW;++r)
    #pragma unroll
    for(unsigned t=0;t<T;++t)flat[r*T+t]=acc[r][t];
   #pragma unroll
   for(unsigned g0=0;g0<N;g0+=GA){
    float a[GA];
    #pragma unroll
    for(unsigned i=0;i<GA;++i)a[i]=flat[g0+i];
    #pragma unroll
    for(unsigned w=1,n=GA;n>1;w*=2,n/=2){
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
    for(unsigned w=GA;w<32;w*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+w)%32);if(((lane/GA)%(2*w/GA))==0)sum=sum+rhs;}
    if(lane<GA){const unsigned i=g0+lane,r=i/T,t=i%T;
     if(t<cnt&&row0+r<span)y[order[first+t]*span+row0+r]=row0+r<rcount?sum:nan;}
   }
   } // row tiles of this subgroup
  }
 }
 auto get(sycl::ext::oneapi::experimental::properties_tag) const {
#ifndef REUSE2_TEST_NO_GRF
  if constexpr(GRF==256)return sycl::ext::oneapi::experimental::properties{sycl::ext::oneapi::experimental::sub_group_size<32>,sycl::ext::intel::experimental::grf_size<256>};
  else
#endif
  return sycl::ext::oneapi::experimental::properties{sycl::ext::oneapi::experimental::sub_group_size<32>};
 }
};
// Launch geometry: rtiles row tiles x G tile slots; G bounds the tiles a bucket can produce for n slots (every tile has
// >= 1 slot; expert tiles <= ceil(n/T) + min(n, experts)); a subgroup loops over tiles g, g+G, ... below tile_count.
template<class F,unsigned RW,unsigned T,unsigned S,unsigned GRF> struct Prepared {Tiles<F,RW,T,S,GRF> kernel;sycl::nd_range<1> range;};
template<class F,unsigned RW,unsigned T,unsigned S,unsigned GRF>
Prepared<F,RW,T,S,GRF> prepare(const uint8_t* w,const float* x,float* y,const uint32_t* order,const uint32_t* tiles,const uint32_t* tile_count,
                               uint32_t span,uint32_t k,uint32_t rb,uint32_t n,uint32_t experts){
 // OWNRT_PREFILL_EXPERTS_GDIV=d launches 1/d of the bound; subgroups then loop over more tiles (default 4; measured
 // 2026-10-26 at 80 rows: d = 1/4/8/16 -> 1.81/1.75/1.75/1.83 ms per row of routed sites).
 static const uint32_t gdiv=[]{const char* e=std::getenv("OWNRT_PREFILL_EXPERTS_GDIV");const int v=e?std::atoi(e):4;return uint32_t(v<1?1:v>64?64:v);}();
 const uint32_t bound=std::min(n,(n+T-1)/T+std::min(n,experts));
 // OWNRT_PREFILL_EXPERTS_RLOOP=r: consecutive row tiles per subgroup (default 4; the tile setup is shared).
 static const uint32_t rloop=[]{const char* e=std::getenv("OWNRT_PREFILL_EXPERTS_RLOOP");const int v=e?std::atoi(e):4;return uint32_t(v<1?1:v>64?64:v);}();
 const uint32_t rtiles=(span+RW-1)/RW;
 Tiles<F,RW,T,S,GRF> kernel{w,x,y,order,tiles,tile_count,span,k,rb,rtiles,std::max(1u,(bound+gdiv-1)/gdiv),rloop,(rtiles+rloop-1)/rloop};
 const size_t groups=(size_t(kernel.rgroups)*kernel.G+S-1)/S;
 return {kernel,sycl::nd_range<1>(groups*S*32,S*32)};
}
} // namespace xgroup
