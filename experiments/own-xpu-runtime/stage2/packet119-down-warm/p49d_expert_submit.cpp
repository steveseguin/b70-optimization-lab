#include "p49d_submit.hpp"
#include "p49d_expert.hpp"
#include "p65_expert.hpp"
#include "p90_expert.hpp"
#include "p95_expert.hpp"
#include "expert_down.hpp"
#include "p100_down.hpp"
#include "p119_warm.hpp"
namespace p49d {
using p39::Kind;using p39::Bindings;using iq3::Type;
template<Type T,unsigned K,Kind E,unsigned Split,unsigned Arm=0>integrated::Launch issue(ownrt::Device&d,const std::vector<integrated::Matrix>&m,const Bindings&b){
 const auto&a=m[0];const auto&peer=m.size()==2?m[1]:a;
 if constexpr(E==Kind::down_status)p29::validate(d,m,"p29.down.wg32",false,2);else
 p28::validate(d,m,E==Kind::expert_checks?"p28.paired.wg32":"p28.dense.wg32",E==Kind::expert_checks,(T==Type::Q6_K||T==Type::Q8_0?(Split==4?7:6):2));
 std::array<ownrt::Allocation,19> ids{a.w,peer.w,a.x,a.y,peer.y,a.routes?a.routes:a.x,a.status?a.status:a.y,peer.status?peer.status:peer.y,a.workspace,b.other?b.other:a.x,b.out?b.out:a.y,b.streams?b.streams:a.y,b.inject?b.inject:a.x,b.mixture?b.mixture:a.x,b.shared_gate?b.shared_gate:a.x,b.one?b.one:a.x,b.error,b.active,b.position};
 using OldCandidate=std::conditional_t<(Arm==11||Arm==12),p95exp::Kernel<T,K,64,false,true,0,Arm==12>,std::conditional_t<Arm==10,p90exp::Kernel<T,K,64,false,true>,std::conditional_t<Arm==0,p49dvirtual::Kernel<T,K,T==Type::IQ2_S?2:3>,p65::Kernel<T,K,Arm==2?128:64,Arm==3,Arm>=4,Arm>=5?Arm-4:0>>>>;using Candidate=std::conditional_t<Arm==119,p119::Kernel,std::conditional_t<(Arm==20||Arm==21),p100::Kernel<Arm-19>,OldCandidate>>;Candidate k;k.rows=a.rows;k.count=a.count;k.experts=a.experts;const auto rb=(Arm==10||Arm==12||Arm==119)?p90::expert_stride(K):p49bgemv::layout(T,K).row_bytes;
 // Validate complete live allocations and byte ranges before any compute hook.
 std::array<void*,19>p;for(size_t j=0;j<ids.size();++j){const auto&r=d.arena.row(ids[j]);if(!r.live||r.memory!=ownrt::Memory::device)throw std::invalid_argument("p39 dead/nondevice binding");p[j]=r.pointer;}
 if constexpr(Arm==21){if(a.rows%16||uintptr_t(p[0])%16)throw std::invalid_argument("p100 tile extent/alignment");}
 auto bound=k.bind(p);bound.position=static_cast<const uint32_t*>(p[18]);bound.capacity=b.capacity;if constexpr(Arm==10||Arm==12||Arm==119)p90exp::validate<T,K,E,Split>(bound);else p39::validate<T,K,E,Split>(bound);
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
 if constexpr(Arm==119){
  if(a.rows!=640||a.count!=10||a.experts!=512||!b.other)throw std::invalid_argument("p119 full expert shape/DOWN binding");
  extent(b.other,size_t(a.experts)*p119::expert_bytes);
  const auto lo=reinterpret_cast<uintptr_t>(p[9]),hi=lo+size_t(a.experts)*p119::expert_bytes;
  if(lo%4||hi<lo)throw std::invalid_argument("p119 DOWN alignment/range");
  for(unsigned index:{3u,4u,6u,7u,16u}){
   const auto& r=d.arena.row(ids[index]);auto other=reinterpret_cast<uintptr_t>(r.pointer);
   if(lo<other+r.bytes&&other<hi)throw std::invalid_argument("p119 DOWN/write alias");
  }
 }
 auto first=d.compute(k,ids,{});integrated::Launch result{first,first,1};

 return result;
}
template<unsigned Arm>integrated::Launch chosen_expert(ownrt::Device& d,const std::vector<integrated::Matrix>& m,p39::Kind kind,const p39::Bindings& b){
 if(m.empty())throw std::invalid_argument("p65 empty expert matrices");
 if(kind==Kind::expert_checks&&m.size()==2&&m[0].type==Type::IQ2_S&&m[0].columns==2560)return issue<Type::IQ2_S,2560,Kind::expert_checks,1,Arm>(d,m,b);
 if(kind==Kind::down_status&&m.size()==1&&m[0].type==Type::IQ4_NL&&m[0].columns==640)return issue<Type::IQ4_NL,640,Kind::down_status,1,Arm>=10?4:Arm>(d,m,b);
 throw std::invalid_argument("p65 unqualified expert shape");
}
integrated::Launch expert(ownrt::Device&d,const std::vector<integrated::Matrix>&m,p39::Kind kind,const p39::Bindings&b){return chosen_expert<0>(d,m,kind,b);}
integrated::Launch expert(ownrt::Device&d,const std::vector<integrated::Matrix>&m,p39::Kind kind,const p39::Bindings&b,std::string_view choice){return expert(d,m,kind,b,choice,"production");}
integrated::Launch expert(ownrt::Device&d,const std::vector<integrated::Matrix>&m,p39::Kind kind,const p39::Bindings&b,std::string_view choice,std::string_view down_warm){
 if(down_warm!="production"&&down_warm!="p119")throw std::invalid_argument("p119 unregistered warming selection");
 if(down_warm=="p119"&&kind==Kind::expert_checks){
  if(choice!="exp-halfcache+down-tile16")throw std::invalid_argument("p119 requires E1 and tile16");
  return chosen_expert<119>(d,m,kind,b);
 }
 if(kind==Kind::down_status){
  if(choice=="down-interleave"||choice.ends_with("+down-interleave"))return issue<Type::IQ4_NL,640,Kind::down_status,1,20>(d,m,b);
  if(p100::tiled(choice))return issue<Type::IQ4_NL,640,Kind::down_status,1,21>(d,m,b);
 }
 choice=p100::gate_choice(choice);
 if(choice=="exp-grid-prefetch+halfcache")return chosen_expert<12>(d,m,kind,b);
 if(choice=="exp-grid-prefetch")return chosen_expert<11>(d,m,kind,b);
 if(choice=="exp-halfcache")return chosen_expert<10>(d,m,kind,b);
 if(choice=="input-packed")return chosen_expert<7>(d,m,kind,b);
 if(choice=="gate-input-packed")return chosen_expert<8>(d,m,kind,b);
 if(choice=="down-input-packed")return chosen_expert<9>(d,m,kind,b);
 if(choice=="experts2-a")return chosen_expert<5>(d,m,kind,b);
 if(choice=="experts2-b")return chosen_expert<6>(d,m,kind,b);
 if(choice=="production")return chosen_expert<0>(d,m,kind,b);
 if(choice=="wg64")return chosen_expert<1>(d,m,kind,b);
 if(choice=="wg128")return chosen_expert<2>(d,m,kind,b);
 if(choice=="wide64")return chosen_expert<4>(d,m,kind,b);
 if(choice=="prefetch64")return chosen_expert<3>(d,m,kind,b);
 throw std::invalid_argument("p65 unregistered expert selection");
}
}
