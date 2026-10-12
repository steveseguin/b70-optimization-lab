#include "p33r2.hpp"
#include "p33_candidates.hpp"
#include "p28/submit.hpp"
#include "mock_order.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace p33r2 {
using namespace round2;
#ifndef OWN_RT_HOST_ONLY
struct Team {
 sycl::nd_item<1> it;float* x;
 template<class F>void each(int n,F f)const{for(int j=it.get_local_linear_id();j<n;j+=32)f(j);}
 void barrier()const{it.barrier(sycl::access::fence_space::global_and_local);}
 int error(ng::Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).load();}
 void fail(ng::Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).store(1);}
 float sum(int n,int base=0)const{for(int stride=1;stride<n;stride*=2){each((n+2*stride-1)/(2*stride),[&](int j){int i=j*2*stride;x[base+i]=x[base+i]+(i+stride<n?x[base+i+stride]:0.f);});barrier();}return x[base];}
};

#endif
#ifdef OWN_RT_HOST_ONLY
template<ng::Op Code,int Stage,bool Fixed=false> struct Kernel final:integrated::HostOperation {
 ng::Shape s;explicit Kernel(ng::Shape v):s(v){}
 void run(std::span<void*const> p)const override{ng::Args a;std::copy_n(p.begin(),19,a.p.begin());{std::vector<float> local(round2::local_floats(s));packet24::mock_items(round2::groups(s),[&](size_t g){if constexpr(Fixed)p33::qsa_group<Code,Stage,128,2048,1>(s,a,int(g),static_cast<float*>(p[19]),ng::HostTeam{local.data()});else group<Code,Stage>(s,a,int(g),static_cast<float*>(p[19]),ng::HostTeam{local.data()});});}}
};
#else
template<ng::Op Code,int Stage,bool Fixed=false> struct Kernel final:ownrt::SyclOperation {
 ng::Shape s;explicit Kernel(ng::Shape v):s(v){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
  ng::Args a;std::copy_n(p.begin(),19,a.p.begin());auto shape=s;float* global=static_cast<float*>(p[19]);int count=round2::groups(s),local=round2::local_floats(s);
  return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> x(local,h);h.parallel_for(sycl::nd_range<1>(size_t(count)*32,32),p28::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{if constexpr(Fixed)p33::qsa_group<Code,Stage,128,2048,1>(shape,a,int(it.get_group_linear_id()),global,Team{it,x.get_multi_ptr<sycl::access::decorated::no>().get()});else group<Code,Stage>(shape,a,int(it.get_group_linear_id()),global,Team{it,x.get_multi_ptr<sycl::access::decorated::no>().get()});}));});
 }
};
#endif
template<ng::Op Code> integrated::Launch issue(ownrt::Device& d,ng::Shape s,std::span<const ownrt::Allocation> a,std::span<const ownrt::Event> deps){auto launch=[&]<bool Fixed>(){Kernel<Code,0,Fixed> first(s);return d.compute(first,a,deps);};auto e=(s.capacity==128&&s.budget==2048&&s.tokens==1)?launch.template operator()<true>():launch.template operator()<false>();return {e,e,1};}
integrated::Launch submit(ownrt::Device& d,ng::Shape s,std::span<const ownrt::Allocation> a,ownrt::Allocation scratch,std::span<const ownrt::Event> deps){
 ng::validate(s);if(a.size()!=19||(s.op!=ng::attention_score&&s.op!=ng::attention_softmax&&s.op!=ng::attention_value))throw std::invalid_argument("round2 non-GEMV binding/op");auto need=ng::required_bytes(s);for(int j=0;j<19;++j)if(d.arena.row(a[j]).bytes<need[j])throw std::invalid_argument("round2 non-GEMV short binding");if(d.arena.row(scratch).bytes<round2::scratch_floats(s)*4)throw std::invalid_argument("round2 non-GEMV scratch");
 std::vector<std::pair<int,bool>> used;
 switch(s.op){
 case ng::attention_score:used={{0,false},{2,false},{4,false},{6,true}};break;
 case ng::attention_softmax:used={{4,false},{6,false},{7,true}};break;
 case ng::attention_value:used={{1,false},{3,false},{4,false},{5,true},{7,false}};break;
 }
 used.insert(used.end(),{{15,true},{17,false},{18,false}});
 for(size_t i=0;i<used.size();++i){auto [slot,write]=used[i];const auto& binding=d.arena.row(a[slot]);if(!binding.live||binding.memory!=ownrt::Memory::device||reinterpret_cast<uintptr_t>(binding.pointer)%4)throw std::invalid_argument("round2 binding memory/alignment");if(a[slot]==scratch)throw std::invalid_argument("round2 scratch aliases binding");for(size_t j=0;j<i;++j){auto [other,other_write]=used[j];constexpr bool state_alias=false;if(a[slot]==a[other]&&(write||other_write)&&!state_alias)throw std::invalid_argument("round2 conflicting binding aliases");}}
 const auto& scratch_row=d.arena.row(scratch);if(!scratch_row.live||scratch_row.memory!=ownrt::Memory::device||reinterpret_cast<uintptr_t>(scratch_row.pointer)%4)throw std::invalid_argument("round2 scratch memory/alignment");
 std::array<ownrt::Allocation,20> bound;std::copy(a.begin(),a.end(),bound.begin());bound[19]=scratch;
 switch(s.op){case ng::attention_score:return issue<ng::attention_score>(d,s,bound,deps);case ng::attention_softmax:return issue<ng::attention_softmax>(d,s,bound,deps);case ng::attention_value:return issue<ng::attention_value>(d,s,bound,deps);default:throw std::invalid_argument("round2 non-GEMV op");}
}

} // namespace p33r2
