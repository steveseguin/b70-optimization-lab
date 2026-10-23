#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p42_submit.cpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#endif
#line 1
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/p42_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/p42_tiny.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/p42_cooperative.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/p42_gdn.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/round2_submit.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace p42 {
#ifndef OWN_RT_HOST_ONLY
struct Guard {int error(ng::Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).load();}void fail(ng::Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).store(1);}};
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/p42_gdn.inc"
struct Team {
 sycl::nd_item<1> it;float* x;
 template<class F>void each(int n,F f)const{for(int j=it.get_local_linear_id();j<n;j+=256)f(j);}
 void barrier()const{it.barrier(sycl::access::fence_space::global_and_local);}
 int error(ng::Args a)const{return Guard{}.error(a);}void fail(ng::Args a)const{Guard{}.fail(a);}
 float sum(int n,int base=0)const{for(int stride=1;stride<n;stride*=2){each((n+2*stride-1)/(2*stride),[&](int j){int i=j*2*stride;x[base+i]=x[base+i]+(i+stride<n?x[base+i+stride]:0.f);});barrier();}return x[base];}
};
#endif
template<ng::Op Code,int Stage=0,int Flags=0>struct Kernel final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 ng::Shape s;explicit Kernel(ng::Shape v):s(v){}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {ng::Args a;std::copy_n(p.begin(),19,a.p.begin());
  if constexpr(Code==ng::gdn)p42parallel::gdn_host(s,a);
  else if constexpr(Code==ng::activation)p42tiny::cpu<ng::activation,1>(s,a);
  else {std::vector<float>x(Code==ng::select?round2::local_floats(s):ng::local_floats(s));int count=Code==ng::select?round2::groups(s):ng::groups(s);for(int g=0;g<count;++g){if constexpr(Code==ng::select)round2::group<Code,Stage>(s,a,g,static_cast<float*>(p[19]),ng::HostTeam{x.data()});else p42tiny::cooperative_group<Code>(s,a,g,ng::HostTeam{x.data()});}}
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{auto shape=s;ng::Args a;std::copy_n(p.begin(),19,a.p.begin());auto scratch=static_cast<float*>(p[19]);
 if constexpr(Code==ng::activation)return ownrt::prepared_submit(q,[=,p35_range0=sycl::range<1>(p42tiny::elements(shape))](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::id<1>i){p42tiny::element<Code>(shape,a,i[0],Guard{});}));});
 else if constexpr(Code==ng::gdn)return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(6144*32,32)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{gdn_device<Flags>(shape,a,it);}));});
 else {int count=Code==ng::select?round2::groups(s):ng::groups(s),local=Code==ng::select?round2::local_floats(s):ng::local_floats(s);return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(count)*256,256)](sycl::handler& h){sycl::local_accessor<float,1>x(local,h);h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{auto t=Team{it,x.get_multi_ptr<sycl::access::decorated::no>().get()};if constexpr(Code==ng::select)round2::group<Code,Stage>(shape,a,it.get_group_linear_id(),scratch,t);else p42tiny::cooperative_group<Code>(shape,a,it.get_group_linear_id(),t);}));});}
 }
#endif
};
integrated::Launch submit(ownrt::Device&d,ng::Shape s,std::span<const ownrt::Allocation>a,ownrt::Allocation scratch,int implementation,std::span<const ownrt::Event>deps){
 ng::validate(s);if(a.size()!=19)throw std::invalid_argument("p42 binding count");auto need=ng::required_bytes(s);for(int j=0;j<19;++j)if(d.arena.row(a[j]).bytes<need[j])throw std::invalid_argument("p42 short binding");
 if(d.arena.row(scratch).bytes<(s.op==ng::select?round2::scratch_floats(s):1)*4)throw std::invalid_argument("p42 scratch size");
 std::vector<std::pair<unsigned,bool>>used;
 if(s.op==ng::gdn)used={{0,false},{1,false},{2,false},{3,false},{4,false},{5,false},{6,true},{7,true}};
 else if(s.op==ng::gated_norm)used={{0,false},{1,false},{2,false},{3,true}};
 else if(s.op==ng::prepare)used={{0,false},{1,false},{2,false},{3,false},{4,false},{5,false},{6,true},{7,true},{8,true},{9,true},{16,false}};
 else if(s.op==ng::pool)used={{0,false},{1,false},{2,false},{3,false},{4,true},{5,true},{6,true},{7,true},{16,false}};
 else if(s.op==ng::select)used={{0,false},{1,false},{2,true}};
 else if(s.op==ng::activation){used={{0,false},{2,true}};if(s.extra)used.push_back({1,false});}
 used.insert(used.end(),{{15,true},{17,false},{18,false}});
 for(size_t j=0;j<used.size();++j){auto[slot,write]=used[j];auto&r=d.arena.row(a[slot]);if(!r.live||r.memory!=ownrt::Memory::device||reinterpret_cast<uintptr_t>(r.pointer)%2||a[slot]==scratch)throw std::invalid_argument("p42 binding lifetime/memory/alignment/scratch alias");for(size_t i=0;i<j;++i){auto[other,writes]=used[i];bool state=s.op==ng::gdn&&slot==7&&other==5;bool inplace=s.op==ng::activation&&((slot==2&&other==0)||(slot==1&&other==2));if(a[slot]==a[other]&&(write||writes)&&!state&&!inplace)throw std::invalid_argument("p42 writable binding alias");}}
 std::array<ownrt::Allocation,20>b;std::copy(a.begin(),a.end(),b.begin());b[19]=scratch;
 auto issue=[&]<ng::Op Code,int Flags=0>(){Kernel<Code,0,Flags>k(s);auto first=d.compute(k,b,deps);if constexpr(Code==ng::select){Kernel<Code,1>tail(s);std::array after{first};auto last=d.compute(tail,b,after);return integrated::Launch{first,last,2};}return integrated::Launch{first,first,1};};
 if(implementation==7&&s.op==ng::gdn&&s.tokens==1){switch(s.flags&14){
#define F(N) case N:return issue.template operator()<ng::gdn,N>()
 F(0);F(2);F(4);F(6);F(8);F(10);F(12);F(14);
#undef F
 }}
 if(implementation==8){if(s.op==ng::gated_norm)return issue.template operator()<ng::gated_norm>();if(s.op==ng::prepare)return issue.template operator()<ng::prepare>();if(s.op==ng::pool)return issue.template operator()<ng::pool>();}
 if(implementation==9&&s.op==ng::activation)return issue.template operator()<ng::activation>();
 if(implementation==10&&s.op==ng::select)return issue.template operator()<ng::select>();
 throw std::invalid_argument("p42 unsupported shape/implementation op="+std::to_string(s.op)+" flags="+std::to_string(s.flags)+" tokens="+std::to_string(s.tokens)+" implementation="+std::to_string(implementation));
}
}
