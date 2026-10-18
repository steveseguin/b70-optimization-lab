#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p49b_expert_submit.cpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/p49b_expert_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/p49b_expert_kernel.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/expert_down.hpp"
namespace p49b {
using p39::Kind;using p39::Bindings;
template<Type T,unsigned K,Kind E,unsigned Split>integrated::Launch issue(ownrt::Device&d,const std::vector<integrated::Matrix>&m,const Bindings&b){
 const auto&a=m[0];const auto&peer=m.size()==2?m[1]:a;
 if constexpr(E==Kind::down_status)p29::validate(d,m,"p29.down.wg32",false,2);else
 p28::validate(d,m,E==Kind::expert_checks?"p28.paired.wg32":"p28.dense.wg32",E==Kind::expert_checks,(T==Type::Q6_K||T==Type::Q8_0?(Split==4?7:6):2));
 std::array<ownrt::Allocation,19> ids{a.w,peer.w,a.x,a.y,peer.y,a.routes?a.routes:a.x,a.status?a.status:a.y,peer.status?peer.status:peer.y,a.workspace,b.other?b.other:a.x,b.out?b.out:a.y,b.streams?b.streams:a.y,b.inject?b.inject:a.x,b.mixture?b.mixture:a.x,b.shared_gate?b.shared_gate:a.x,b.one?b.one:a.x,b.error,b.active,b.position};
 Kernel<T,K>k;k.rows=a.rows;k.count=a.count;k.experts=a.experts;const auto rb=p49bgemv::layout(T,K).row_bytes;
 // Validate complete live allocations and byte ranges before any compute hook.
 std::array<void*,19>p;for(size_t j=0;j<ids.size();++j){const auto&r=d.arena.row(ids[j]);if(!r.live||r.memory!=ownrt::Memory::device)throw std::invalid_argument("p39 dead/nondevice binding");p[j]=r.pointer;}
 auto bound=k.bind(p);bound.position=static_cast<const uint32_t*>(p[18]);bound.capacity=b.capacity;p39::validate<T,K,E,Split>(bound);
 if(uintptr_t(bound.w)%4||uintptr_t(bound.peer)%4)throw std::invalid_argument("p49b weight alignment");
 auto extent=[&](ownrt::Allocation id,size_t n){if(d.arena.row(id).bytes<n)throw std::invalid_argument("p39 allocation extent");};
 size_t n=size_t(a.rows)*a.count;extent(a.w,size_t(a.experts)*a.rows*rb);extent(a.x,size_t(K)*(E==Kind::down_status?a.count:1)*2);extent(a.y,n*2);extent(b.error,4);extent(b.active,4);extent(b.position,4);
 if constexpr(Split==4)extent(a.workspace,n*32);
 if constexpr(E==Kind::expert_checks){extent(peer.w,size_t(a.experts)*a.rows*rb);extent(peer.y,n*2);extent(a.routes,a.count*sizeof(iq3::Route));extent(a.status,a.count*4);extent(peer.status,a.count*4);}
 if constexpr(E==Kind::down_status){extent(a.routes,a.count*sizeof(iq3::Route));extent(a.status,a.count*4);}
 if constexpr(E==Kind::silu_div4||E==Kind::shared_act||E==Kind::shared_combine)extent(b.out,n*2);
 if constexpr(E==Kind::shared_act)extent(b.other,n*2);
 if constexpr(E==Kind::attention_combine||E==Kind::shared_combine){extent(b.streams,n*8);extent(b.inject,8);}
 if constexpr(E==Kind::shared_combine){extent(b.mixture,n*2);extent(b.shared_gate,2);extent(b.one,4);}
 auto first=d.compute(k,ids,{});integrated::Launch result{first,first,1};

 return result;
}
integrated::Launch submit(ownrt::Device& d,const std::vector<integrated::Matrix>& m,p39::Kind kind,const p39::Bindings& b){
 if(m.empty())throw std::invalid_argument("p49b empty expert matrices");
 if(kind==Kind::expert_checks&&m.size()==2&&m[0].type==Type::IQ2_S&&m[0].columns==2560)return issue<Type::IQ2_S,2560,Kind::expert_checks,1>(d,m,b);
 if(kind==Kind::down_status&&m.size()==1&&m[0].type==Type::IQ4_NL&&m[0].columns==640)return issue<Type::IQ4_NL,640,Kind::down_status,1>(d,m,b);
 throw std::invalid_argument("p49b unqualified expert shape");
}
}
