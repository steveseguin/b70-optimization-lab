#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p39_submit.cpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/build/checked/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/p39_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/build/checked/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/expert_down.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/build/checked/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/p39_sycl.hpp"
#endif
namespace p39 {
template<Type T,unsigned K,Kind E,unsigned Split,unsigned Stage=0>struct Kernel final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 Bound shape;
 Bound bind(std::span<void*const> p)const {auto b=shape;b.w=static_cast<const uint8_t*>(p[0]);b.peer=static_cast<const uint8_t*>(p[1]);b.x=static_cast<const uint16_t*>(p[2]);b.y=static_cast<uint16_t*>(p[3]);b.py=static_cast<uint16_t*>(p[4]);b.routes=static_cast<const iq3::Route*>(p[5]);b.status=static_cast<uint32_t*>(p[6]);b.peer_status=static_cast<uint32_t*>(p[7]);b.scratch=static_cast<float*>(p[8]);b.other=static_cast<const uint16_t*>(p[9]);b.out=static_cast<uint16_t*>(p[10]);b.streams=static_cast<uint16_t*>(p[11]);b.inject=static_cast<const uint16_t*>(p[12]);b.mixture=static_cast<const uint16_t*>(p[13]);b.shared_gate=static_cast<const uint16_t*>(p[14]);b.one=static_cast<const float*>(p[15]);b.error=static_cast<uint32_t*>(p[16]);b.active=static_cast<const uint32_t*>(p[17]);b.position=static_cast<const uint32_t*>(p[18]);return b;}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {auto b=bind(p);host_gemv<T,K,E,true,Split>(b);}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {return gemv<T,K,E,true,Split,Stage>(q,bind(p),deps).back();}
#endif
};
template<Type T,unsigned K,Kind E,unsigned Split>integrated::Launch issue(ownrt::Device&d,const std::vector<integrated::Matrix>&m,const Bindings&b){
 const auto&a=m[0];const auto&peer=m.size()==2?m[1]:a;
 if constexpr(E==Kind::down_status)p29::validate(d,m,"p29.down.wg32",false,2);else
 p28::validate(d,m,E==Kind::expert_checks?"p28.paired.wg32":"p28.dense.wg32",E==Kind::expert_checks,(T==Type::Q6_K||T==Type::Q8_0?(Split==4?7:6):2));
 std::array<ownrt::Allocation,19> ids{a.w,peer.w,a.x,a.y,peer.y,a.routes?a.routes:a.x,a.status?a.status:a.y,peer.status?peer.status:peer.y,a.workspace,b.other?b.other:a.x,b.out?b.out:a.y,b.streams?b.streams:a.y,b.inject?b.inject:a.x,b.mixture?b.mixture:a.x,b.shared_gate?b.shared_gate:a.x,b.one?b.one:a.x,b.error,b.active,b.position};
 Kernel<T,K,E,Split>k;k.shape.rb=integrated::arithmetic::row_bytes(T,K,Split==4?7:(T==Type::Q6_K||T==Type::Q8_0?6:2));k.shape.rows=a.rows;k.shape.count=a.count;k.shape.experts=a.experts;k.shape.capacity=b.capacity;
 // Validate complete live allocations and byte ranges before any compute hook.
 std::array<void*,19>p;for(size_t j=0;j<ids.size();++j){const auto&r=d.arena.row(ids[j]);if(!r.live||r.memory!=ownrt::Memory::device)throw std::invalid_argument("p39 dead/nondevice binding");p[j]=r.pointer;}
 auto bound=k.bind(p);validate<T,K,E,Split>(bound);
 auto extent=[&](ownrt::Allocation id,size_t n){if(d.arena.row(id).bytes<n)throw std::invalid_argument("p39 allocation extent");};
 size_t n=size_t(a.rows)*a.count;extent(a.w,size_t(a.experts)*a.rows*k.shape.rb);extent(a.x,size_t(K)*(E==Kind::down_status?a.count:1)*2);extent(a.y,n*2);extent(b.error,4);extent(b.active,4);extent(b.position,4);
 if constexpr(Split==4)extent(a.workspace,n*32);
 if constexpr(E==Kind::expert_checks){extent(peer.w,size_t(a.experts)*a.rows*k.shape.rb);extent(peer.y,n*2);extent(a.routes,a.count*sizeof(iq3::Route));extent(a.status,a.count*4);extent(peer.status,a.count*4);}
 if constexpr(E==Kind::down_status){extent(a.routes,a.count*sizeof(iq3::Route));extent(a.status,a.count*4);}
 if constexpr(E==Kind::silu_div4||E==Kind::shared_act||E==Kind::shared_combine)extent(b.out,n*2);
 if constexpr(E==Kind::shared_act)extent(b.other,n*2);
 if constexpr(E==Kind::attention_combine||E==Kind::shared_combine){extent(b.streams,n*8);extent(b.inject,8);}
 if constexpr(E==Kind::shared_combine){extent(b.mixture,n*2);extent(b.shared_gate,2);extent(b.one,4);}
 auto first=d.compute(k,ids,{});integrated::Launch result{first,first,1};
#ifndef OWN_RT_HOST_ONLY
 if constexpr(Split==4&&E!=Kind::silu_div4&&E!=Kind::shared_act){Kernel<T,K,E,Split,1>f;f.shape=k.shape;std::array after{first};result.last=d.compute(f,ids,after);result.passes=2;}
#endif
 return result;
}
integrated::Launch submit(ownrt::Device&d,const std::vector<integrated::Matrix>&m,Kind kind,const Bindings&b){
 if(m.empty())throw std::invalid_argument("p39 matrices");auto t=m[0].type;
 if(kind==Kind::expert_checks&&m.size()==2&&m[0].columns==2560){if(t==Type::IQ2_S)return issue<Type::IQ2_S,2560,Kind::expert_checks,1>(d,m,b);if(t==Type::IQ3_S)return issue<Type::IQ3_S,2560,Kind::expert_checks,1>(d,m,b);}
 if(kind==Kind::down_status&&t==Type::IQ4_NL&&m[0].columns==640)return issue<Type::IQ4_NL,640,Kind::down_status,1>(d,m,b);
 if(kind==Kind::silu_div4&&t==Type::Q8_0&&m[0].columns==10240)return issue<Type::Q8_0,10240,Kind::silu_div4,4>(d,m,b);
 if(kind==Kind::attention_combine&&t==Type::Q6_K&&m[0].columns==6144)return issue<Type::Q6_K,6144,Kind::attention_combine,4>(d,m,b);
 if(kind==Kind::shared_act&&m[0].columns==2560){if(t==Type::Q6_K)return issue<Type::Q6_K,2560,Kind::shared_act,4>(d,m,b);if(t==Type::Q8_0)return issue<Type::Q8_0,2560,Kind::shared_act,1>(d,m,b);}
 if(kind==Kind::shared_combine&&t==Type::Q8_0&&m[0].columns==640)return issue<Type::Q8_0,640,Kind::shared_combine,1>(d,m,b);
 throw std::invalid_argument("p39 unsupported fixed shape");
}
}
