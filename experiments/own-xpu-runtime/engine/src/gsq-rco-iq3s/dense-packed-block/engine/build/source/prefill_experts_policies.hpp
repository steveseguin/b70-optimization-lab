#pragma once
// Decode policies for the expert-grouped prefill tiles (prefill_experts.hpp): each returns, for its routed site class,
// exactly the values the existing routed kernel computes (the same functions, called the same way).
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prefill_experts.hpp"
#include "stage2/packet6-kopt/reference.hpp"
namespace xgroup {
// IQ3_XXS block sites (iq3block::BlockRowsOperation): 98-byte blocks, block_element_words with the block's half scale.
struct Iq3Words {static void decode(const uint8_t* row,uint32_t step,unsigned lane,unsigned gv,float (&v)[8]){
 const uint8_t* packed=row+step*98u;const float d=iq3::half(iq3::u16(packed));
 #pragma unroll
 for(unsigned g=0;g<8;++g)if(g<gv)v[g]=iq3block::block_element_words(packed,d,g,lane);}};
// gsqn packed routed rows (PackedRowsOperation / PackedOperation, types 12, 13, 18, 23, 42): gsq::element_unchecked at
// column k = 256*step + 32*g + lane of the row (Q2_0's dedicated loop computes the same float(code-1)*d).
template<unsigned T> struct Elem {static void decode(const uint8_t* row,uint32_t step,unsigned lane,unsigned gv,float (&v)[8]){
 constexpr uint32_t elements=T==42?64:256,bytes=T==42?18:T==12?144:T==13?176:T==23?136:98;
 #pragma unroll
 for(unsigned g=0;g<8;++g)if(g<gv){const uint32_t k=step*256u+g*32u+lane;v[g]=gsq::element_unchecked(T,row+(k/elements)*bytes,k%elements);}}};
// kopt routed rows (MultiplyBlockRows / Multiply): iq3::kopt::decode8<T> at the lane's 8-column chunk.
template<iq3::Type T> struct Kopt {static void decode8(const uint8_t* row,uint32_t k,float (&v)[8]){iq3::kopt::decode8<T>(row,k,v);}};
// Engine operations. Bucket bindings: routes, status, order, tiles, tile_count. Tiles bindings: weights, F32 slot inputs
// (slots x k), F32 outputs (slots x span), order, tiles, tile_count.
struct BucketOp final:ownrt::SyclOperation {
 uint32_t n=0,experts=0,rows=0,span=0,T=0;
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
  if(p.size()<5||!n||!T||!experts)throw std::invalid_argument("expert bucket geometry");
  const Bucket k{static_cast<const iq3::Route*>(p[0]),static_cast<uint32_t*>(p[1]),static_cast<uint32_t*>(p[2]),static_cast<uint32_t*>(p[3]),
                 static_cast<uint32_t*>(p[4]),n,experts,rows,span,T,{}};
  const uint32_t nn=n;
  return ownrt::prepared_submit(q,[=](sycl::handler& h){h.depends_on(deps);Bucket kk=k;kk.keys=sycl::local_accessor<uint32_t,1>(sycl::range<1>(nn),h);
   h.parallel_for(sycl::nd_range<1>(bucket_items,bucket_items),packet26::checked(kk));});
 }
};
template<class F,unsigned RW,unsigned T,unsigned S,unsigned GRF> struct TilesOp final:ownrt::SyclOperation {
 uint32_t span=0,k=0,rb=0,n=0,experts=0;
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
  if(p.size()<6||!span||!k||!n)throw std::invalid_argument("expert tiles geometry");
  const auto prepared=prepare<F,RW,T,S,GRF>(static_cast<const uint8_t*>(p[0]),static_cast<const float*>(p[1]),static_cast<float*>(p[2]),
   static_cast<const uint32_t*>(p[3]),static_cast<const uint32_t*>(p[4]),static_cast<const uint32_t*>(p[5]),span,k,rb,n,experts);
  const auto kernel=prepared.kernel;const auto range=prepared.range;
  return ownrt::prepared_submit(q,[=](sycl::handler& h){h.depends_on(deps);h.parallel_for(range,packet26::checked(kernel));});
 }
};
template<unsigned RW,unsigned T,unsigned S,unsigned GRF> struct Cfg {static constexpr unsigned rw=RW,t=T,s=S,grf=GRF;};
// The tile list (index = OWNRT_PREFILL_EXPERTS_<FAMILY>; config_count = the existing kernel). Cfg<RW rows, T slots, S
// subgroups per work-group, GRF>. Production keeps the two tiles that won the 2026-10-26 sweeps (RESULT.md); build with
// -DXGROUP_EXPLORE for the sweep list (4x2, 4x4, 4x8/256, 8x4/256 and 2x8 never won).
#ifdef XGROUP_EXPLORE
#define XGROUP_CONFIGS xgroup::Cfg<2,4,4,128>,xgroup::Cfg<1,4,4,128>,xgroup::Cfg<4,2,4,128>,xgroup::Cfg<4,4,4,128>,xgroup::Cfg<4,8,4,256>,\
 xgroup::Cfg<8,4,4,256>,xgroup::Cfg<2,8,4,128>
inline constexpr unsigned config_count=7;
#else
#define XGROUP_CONFIGS xgroup::Cfg<2,4,4,128>,xgroup::Cfg<1,4,4,128>
inline constexpr unsigned config_count=2;
#endif
// Defaults (80-row chunks, rows per subgroup loop 4, launch divisor 4): 1 row x 4 slots for IQ3_XXS block sites, gsqn
// packed rows and kopt IQ4_NL; 2 x 4 for the other kopt formats (IQ2_S, IQ3_S).
inline unsigned default_tile(int family,unsigned type){return family==2&&type!=20?0u:1u;}
// Bucket (with the configuration's T) then the configuration's tiles: two operations, events first..last.
template<class F,class... Cs> std::pair<ownrt::Event,ownrt::Event> issue(ownrt::Device& d,unsigned index,const std::array<ownrt::Allocation,8>& ids,
  uint32_t n,uint32_t experts,uint32_t rows,uint32_t span,uint32_t k,uint32_t rb){
 // ids: weights, x, y, routes, status, order, tiles, tile_count
 std::pair<ownrt::Event,ownrt::Event> r{};bool done=false;unsigned i=0;
 auto one=[&]<class C>(C){if(i++!=index||done)return;
  BucketOp b;b.n=n;b.experts=experts;b.rows=rows;b.span=span;b.T=C::t;std::array<ownrt::Allocation,5> bi{ids[3],ids[4],ids[5],ids[6],ids[7]};
  r.first=d.compute(b,bi,{});
  TilesOp<F,C::rw,C::t,C::s,C::grf> op;op.span=span;op.k=k;op.rb=rb;op.n=n;op.experts=experts;std::array<ownrt::Allocation,6> ti{ids[0],ids[1],ids[2],ids[5],ids[6],ids[7]};
  r.second=d.compute(op,ti,{});done=true;};
 (one(Cs{}),...);
 if(!done)throw std::invalid_argument("expert tile configuration index");
 return r;
}
}
#endif
