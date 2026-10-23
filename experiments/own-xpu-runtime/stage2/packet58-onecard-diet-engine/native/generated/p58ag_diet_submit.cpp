#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/build/native/p58ag_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/build/native/p58ag_expert.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/build/native/p58ag_diet.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/expert_down.hpp"
namespace p58ag {
using p39::Kind;using p39::Bindings;using iq3::Type;
// packet58-onecard-diet-engine: the exact instruction diet of the ONE-card record gate/up kernel, p58ag_diet::GateUp
// (packet58-onecard-diet-micro, qualified 0.78x cold / 0.75x warm, byte-identical on device), registered in its OWN
// translation unit so that p58ag_submit.cpp's device code stays exactly the record kernel set (per-kernel SPIR-V identity).
// issue_diet is the production p58ag::issue<IQ2_S,2560,expert_checks,1,Tile=false,Cached=true> body VERBATIM (the same 20
// bindings incl. the halfcache table p[19], the same p39::validate, extents and half-table alias checks) with the kernel
// object replaced by p58ag_diet::GateUp (which binds through the production Kernel::bind). Reached only from
// p58ag::expert(..., gateup="diet") on the halfcache layout (experts=wide64+halfcache).
template<Type T,unsigned K,Kind E,unsigned Split,bool Tile=false,bool Cached=true>integrated::Launch issue_diet(ownrt::Device&d,const std::vector<integrated::Matrix>&m,const Bindings&b,ownrt::Allocation halfcache){
 static_assert(T==Type::IQ2_S&&K==2560&&E==Kind::expert_checks&&Split==1&&!Tile&&Cached,"the diet is a diet of the halfcache gate/up kernel only");
 const auto&a=m[0];const auto&peer=m.size()==2?m[1]:a;
 if(!b.indirect){ if constexpr(E==Kind::down_status)p29::validate(d,m,"p29.down.wg32",false,2);else
 p28::validate(d,m,E==Kind::expert_checks?"p28.paired.wg32":"p28.dense.wg32",E==Kind::expert_checks,(T==Type::Q6_K||T==Type::Q8_0?(Split==4?7:6):2));
 }
 std::array<ownrt::Allocation,20> ids{a.w,peer.w,a.x,a.y,peer.y,a.routes?a.routes:a.x,a.status?a.status:a.y,peer.status?peer.status:peer.y,a.workspace,b.other?b.other:a.x,b.out?b.out:a.y,b.streams?b.streams:a.y,b.inject?b.inject:a.x,b.mixture?b.mixture:a.x,b.shared_gate?b.shared_gate:a.x,b.one?b.one:a.x,b.error,b.active,b.position,halfcache};
 p58ag_diet::GateUp k;
 if constexpr(Tile)if(a.rows%16)throw std::invalid_argument("p58j tile rows");k.indirect=b.indirect;k.rows=a.rows;k.count=a.count;k.experts=a.experts;const auto rb=p49bgemv::layout(T,K).row_bytes;
 // Validate complete live allocations and byte ranges before any compute hook.
 std::array<void*,20>p;for(size_t j=0;j<ids.size();++j){const auto&r=d.arena.row(ids[j]);if(!r.live||r.memory!=ownrt::Memory::device)throw std::invalid_argument("p39 dead/nondevice binding");p[j]=r.pointer;}
 auto bound=k.bind(p);bound.position=static_cast<const uint32_t*>(p[18]);bound.capacity=b.capacity;p39::validate<T,K,E,Split>(bound);
 if(uintptr_t(bound.w)%(Tile?16:4)||uintptr_t(bound.peer)%(Tile?16:4))throw std::invalid_argument("p49b weight alignment");
 auto extent=[&](ownrt::Allocation id,size_t n){if(d.arena.row(id).bytes<n)throw std::invalid_argument("p39 allocation extent");};
 extent(halfcache,65536*4);
 if(uintptr_t(p[19])%4)throw std::invalid_argument("half table alignment");
 for(unsigned j:{3u,4u,6u,7u,8u,16u}){auto lo=uintptr_t(p[j]),hi=lo+d.arena.row(ids[j]).bytes,t=uintptr_t(p[19]);if(lo<t+65536*4&&t<hi)throw std::invalid_argument("half table write alias");}

 size_t n=size_t(a.rows)*a.count;extent(a.w,b.indirect?size_t(a.experts)*sizeof(p58::Pointer):size_t(a.experts)*a.rows*rb);extent(a.x,size_t(K)*(E==Kind::down_status?a.count:1)*2);extent(a.y,n*2);extent(b.error,4);extent(b.active,4);extent(b.position,4);
 if constexpr(Split==4)extent(a.workspace,n*32);
 if constexpr(E==Kind::expert_checks){extent(peer.w,b.indirect?size_t(a.experts)*sizeof(p58::Pointer):size_t(a.experts)*a.rows*rb);extent(peer.y,n*2);extent(a.routes,a.count*sizeof(iq3::Route));extent(a.status,a.count*4);extent(peer.status,a.count*4);}
 if constexpr(E==Kind::down_status){extent(a.routes,a.count*sizeof(iq3::Route));extent(a.status,a.count*4);}
 if constexpr(E==Kind::silu_div4||E==Kind::shared_act||E==Kind::shared_combine)extent(b.out,n*2);
 if constexpr(E==Kind::shared_act)extent(b.other,n*2);
 if constexpr(E==Kind::attention_combine||E==Kind::shared_combine){extent(b.streams,n*8);extent(b.inject,8);}
 if constexpr(E==Kind::shared_combine){extent(b.mixture,n*2);extent(b.shared_gate,2);extent(b.one,4);}
 auto first=d.compute(k,ids,{});integrated::Launch result{first,first,1};

 return result;
}
integrated::Launch expert_diet(ownrt::Device& d,const std::vector<integrated::Matrix>& m,const Bindings& b,ownrt::Allocation halfcache){
 if(m.size()!=2||m[0].type!=Type::IQ2_S||m[0].columns!=2560)throw std::invalid_argument("p58ag expert shape");
 if(!b.indirect)throw std::invalid_argument("p58ag expert_gateup=diet requires the indirect expert-cache slot path");
 return issue_diet<Type::IQ2_S,2560,Kind::expert_checks,1,false,true>(d,m,b,halfcache);
}
}
