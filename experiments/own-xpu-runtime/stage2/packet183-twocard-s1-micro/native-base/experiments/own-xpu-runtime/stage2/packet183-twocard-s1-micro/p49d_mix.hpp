#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p49d_mix.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/build/checked/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/prepared_submission.hpp"
#endif
#line 1
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/build/checked/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/runtime_kernels.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/build/checked/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/specialised.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/build/checked/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/performance.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#endif

// Packet54: independent scheduling changes over packet49c's arithmetic.
// The ordinary layer is M=1. M=2 is two serial invocations using the same
// owner state, as in the production engine; it is not a changed batch tree.
namespace p49dmix {
using integrated::Op;
struct Bound {
 integrated::Spec s;
 std::array<void*,32> p{};
 integrated::View in(unsigned j)const{return {p[j],s.sizes[j],s.types[j]};}
 integrated::View out(unsigned j)const{unsigned k=s.ni+j;return {p[k],s.sizes[k],s.types[k]};}
 unsigned tail()const{return s.ni+s.no+s.nw;}
 float* scratch()const{return static_cast<float*>(p[tail()]);}
 uint32_t* error()const{return static_cast<uint32_t*>(p[tail()+1]);}
 uint32_t* position()const{return static_cast<uint32_t*>(p[tail()+2]);}
 uint32_t* active()const{return static_cast<uint32_t*>(p[tail()+3]);}
 uint32_t failed()const{
#ifdef OWN_RT_HOST_ONLY
  return *error();
#else
  return sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*error()).load();
#endif
 }
 void fail()const{
#ifdef OWN_RT_HOST_ONLY
  *error()=1;
#else
  sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*error()).store(1);
#endif
 }
 float gain(unsigned i)const{return static_cast<const float*>(p[s.ni+s.no])[i];}
};
inline Bound bind(integrated::Spec s,std::span<void*const>p){Bound b{s,{}};std::copy(p.begin(),p.end(),b.p.begin());return b;}
inline bool admitted(Bound b,bool check_position,unsigned index){
 if(!*b.active()||b.failed())return false;
 if(check_position&&*b.position()>=unsigned(b.s.g.context)){if(!index)b.fail();return false;}
 return true;
}
inline void mix4(Bound b,unsigned vector_index){
 if(!admitted(b,true,vector_index))return;
 unsigned first=vector_index*4;
 float sum[4]{};
 // Each dimension has the unchanged stream-0,1,2,3 left-associated sum.
 for(unsigned stream=0;stream<4;++stream)for(unsigned j=0;j<4;++j){
  unsigned i=stream*2560+first+j;
  sum[j]=sum[j]+ng::sigmoid(b.in(1).get(i))*b.in(0).get(i);
 }
 for(unsigned j=0;j<4;++j)b.out(0).put(first+j,sum[j]/4.f);
}

#ifdef OWN_RT_HOST_ONLY
using Base=integrated::HostOperation;
#else
using Base=ownrt::SyclOperation;
#endif
struct Kernel final:Base {
 integrated::Spec spec;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {auto b=bind(spec,p);for(unsigned i=0;i<640;++i)mix4(b,i);}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {
  auto b=bind(spec,p);return ownrt::prepared_submit(q,[=,p35_range0=sycl::range<1>(640)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::id<1>i){mix4(b,i[0]);}));});
 }
#endif
};
} // namespace p49dmix
