#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p49_qsa_submit.cpp"
// Packet47's qualified split32 arithmetic through the runtime owner API.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/build/checked/experiments/own-xpu-runtime/stage2/packet150-rank0-split/p49_qsa_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/build/checked/experiments/own-xpu-runtime/stage2/packet150-rank0-split/p49_qsa_reference.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/build/checked/experiments/own-xpu-runtime/stage2/packet150-rank0-split/p49_qsa_kernel.hpp"
#endif
namespace p49 {
#ifdef OWN_RT_HOST_ONLY
using Base=integrated::HostOperation;
#else
using Base=ownrt::SyclOperation;
#endif
template<int Stage>struct Attention final:Base {
 ng::Shape s;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {
  ng::Args a;std::copy_n(p.begin(),19,a.p.begin());
  if constexpr(Stage==0){
   if(!a.i(18)[0]||a.i(15)[0])return;
   if(a.i(17)[0]<0||a.i(17)[0]>ng::launch_extent(s)-s.tokens){a.i(15)[0]=1;return;}
   try{p47ref::cpu_split(s,a);}catch(const std::invalid_argument&){a.i(15)[0]=1;}
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const> p,const std::vector<sycl::event>&deps)const override {
  ng::Args a;std::copy_n(p.begin(),19,a.p.begin());
  auto counts=static_cast<int*>(p[19]);auto partial=reinterpret_cast<float*>(static_cast<uint8_t*>(p[19])+16);
  if constexpr(Stage==0)return p47::admit(q,s,a,counts,deps);
  if constexpr(Stage==1)return p47::tiles<true>(q,s,a,counts,partial,deps);
  if constexpr(Stage==2)return p47::combine<true>(q,s,a,counts,partial,deps);
 }
#endif
};
integrated::Launch attention(ownrt::Device&d,ng::Shape s,std::span<const ownrt::Allocation>a,ownrt::Allocation scratch,std::span<const ownrt::Event>deps){
 ng::validate(s);
 if(s.op!=ng::attention_score||s.tokens<1||s.tokens>2||a.size()!=19||s.budget!=2048)
  throw std::invalid_argument("packet49 split32 geometry/bindings");
 auto required=ng::required_bytes(s);required[16]=0;
 for(int j=0;j<19;++j){const auto&r=d.arena.row(a[j]);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<required[j])throw std::invalid_argument("packet49 attention extent/lifetime");}
 const auto&r=d.arena.row(scratch);
 if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<scratch_bytes(s)||uintptr_t(r.pointer)%4)throw std::invalid_argument("packet49 attention scratch bound");
 for(int j=0;j<19;++j)if(a[j]==scratch)throw std::invalid_argument("packet49 scratch alias");
 for(int j:{0,1,2,3,4,15,17,18})if(a[j]==a[5])throw std::invalid_argument("packet49 output alias");
 std::array<ownrt::Allocation,20>bound;std::copy(a.begin(),a.end(),bound.begin());bound[19]=scratch;
 integrated::Launch result{};
 auto issue=[&]<int Stage>(){Attention<Stage> op;op.s=s;std::array<ownrt::Event,1>after{result.last};auto e=d.compute(op,bound,result.last?std::span<const ownrt::Event>(after):deps);if(!result.first)result.first=e;result.last=e;++result.passes;};
 issue.template operator()<0>();issue.template operator()<1>();issue.template operator()<2>();return result;
}
}
