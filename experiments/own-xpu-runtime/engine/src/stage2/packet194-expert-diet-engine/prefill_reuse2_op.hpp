#pragma once
// Engine operation wrapper for the generation-2 prefill token-row kernels (prefill_reuse2.hpp). Bindings: weights,
// F32 activations (tokens x k), F32 outputs (tokens x rows).
#include "stage2/packet194-expert-diet-engine/prefill_reuse2.hpp"
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#include "stage1/packet3-prep/src/sycl_operation.hpp"
#include <span>
#include <stdexcept>
namespace reuse2 {
template<class F,unsigned RW,unsigned T,unsigned S,unsigned GRF,unsigned O> struct Op final:ownrt::SyclOperation {
 uint32_t rows=0,k=0,tokens=0,rb=0;
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
  if(p.size()<3||!rows||!k||!tokens||k%8)throw std::invalid_argument("reuse2 token-row geometry");
  const auto prepared=prepare<F,RW,T,S,GRF,O>(static_cast<const uint8_t*>(p[0]),static_cast<const float*>(p[1]),static_cast<float*>(p[2]),rows,k,tokens,rb);
  const auto kernel=prepared.kernel;const auto range=prepared.range;
  return ownrt::prepared_submit(q,[=](sycl::handler& h){h.depends_on(deps);h.parallel_for(range,packet26::checked(kernel));});
 }
};
// Configuration list entry: RW rows x T tokens per subgroup, S subgroups per work-group, GRF 128 or 256.
template<unsigned RW,unsigned T,unsigned S,unsigned GRF,unsigned O=0> struct Cfg {static constexpr unsigned rw=RW,t=T,s=S,grf=GRF,o=O;};
// Issue configuration `index` of the list Cs... for format F.
template<class F,class... Cs> ownrt::Event issue(ownrt::Device& d,unsigned index,std::span<const ownrt::Allocation> ids,uint32_t rows,uint32_t k,uint32_t tokens,uint32_t rb){
 ownrt::Event e{};bool done=false;unsigned i=0;
 auto one=[&]<class C>(C){if(i++!=index||done)return;Op<F,C::rw,C::t,C::s,C::grf,C::o> op;op.rows=rows;op.k=k;op.tokens=tokens;op.rb=rb;e=d.compute(op,ids,{});done=true;};
 (one(Cs{}),...);
 if(!done)throw std::invalid_argument("reuse2 configuration index");
 return e;
}
}
namespace reuse2 {
// The configuration list every family compiles: index = OWNRT_PREFILL_REUSE2_<FAMILY> (BLOCK, P33, KOPT, BF16), and
// config_count selects the family's canonical kernel; OWNRT_PREFILL_REUSE2_CYCLE=1 cycles chunk % (config_count+1).
// Cfg<RW rows, T tokens, S subgroups per work-group, GRF 128|256, O tile order>. The production list keeps the tiles
// that won at least one site class in the 2026-10-26 sweeps (2x8, 1x16, 2x16, 4x16, 2x4, 8x4 and 4x8 row-major order,
// and half-split 128-GRF variants, never won; RESULT.md). Build with -DREUSE2_EXPLORE for the wider sweep list.
#ifdef REUSE2_EXPLORE
#define REUSE2_CONFIGS reuse2::Cfg<1,32,4,256>,reuse2::Cfg<4,8,4,256>,reuse2::Cfg<1,4,4,128>,reuse2::Cfg<1,1,4,128>,reuse2::Cfg<2,16,4,256,1>,\
 reuse2::Cfg<2,8,4,128>,reuse2::Cfg<1,16,4,128>,reuse2::Cfg<2,16,4,256>,reuse2::Cfg<4,16,4,256>,reuse2::Cfg<2,4,4,128>,reuse2::Cfg<8,4,4,256>,\
 reuse2::Cfg<4,8,4,256,1>
inline constexpr unsigned config_count=12;
#else
#define REUSE2_CONFIGS reuse2::Cfg<1,32,4,256>,reuse2::Cfg<4,8,4,256>,reuse2::Cfg<1,4,4,128>,reuse2::Cfg<1,1,4,128>,reuse2::Cfg<2,16,4,256,1>
inline constexpr unsigned config_count=5;
#endif
// Measured defaults (rank 1, 32-row chunks; profiled cycle runs r2c/r2e/r2f 2026-10-26, ms per chunk in RESULT.md):
// dense blocks 2x16 row-tile-major (GRF 256); p33 expanded Q6_K/Q8_0 4x8 (GRF 256); kopt raw Q6_K/Q8_0 1x32 for <= 1024
// rows, else 2x16 row-tile-major; BF16 1x1 for <= 64 rows, 1x4 for <= 128 rows, the canonical lean kernel for k >= 8192
// (320 x 10240: 3.57 vs 3.82 ms best tile), else 4x8.
inline unsigned default_block(uint32_t,uint32_t){return 4;}
inline unsigned default_p33(uint32_t,uint32_t){return 1;}
inline unsigned default_kopt(uint32_t rows,uint32_t){return rows<=1024?0:4;}
inline unsigned default_bf16(uint32_t rows,uint32_t k){return rows<=64?3:rows<=128?2:k>=8192?config_count:1;}
inline bool aligned(ownrt::Device& d,ownrt::Allocation id,uintptr_t a){return reinterpret_cast<uintptr_t>(d.arena.row(id).pointer)%a==0;}
}
