#pragma once
#include "launch_native.hpp"
#include "tiny_core.hpp"
#include "../packet29-merged/native.hpp"
namespace p42tiny {
struct Guard{int error(ng::Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).load();}void fail(ng::Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).store(1);}};
template<int Code,int WG>class TinyKernel;
template<ng::Op Code,int WG>struct Element:ownrt::SyclOperation{
 ng::Shape shape;explicit Element(ng::Shape s):shape(s){}
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto s=shape;ng::Args a;std::copy_n(p.begin(),19,a.p.begin());auto n=elements(s);static_assert(sizeof(s)+sizeof(a)<=1024);
  return q.submit([&](sycl::handler&h){h.depends_on(deps);if constexpr(WG==0)h.parallel_for<TinyKernel<Code,WG>>(sycl::range<1>(n),[=](sycl::id<1>i){element<Code>(s,a,i[0],Guard{});});else h.parallel_for<TinyKernel<Code,WG>>(sycl::nd_range<1>(((n+WG-1)/WG)*WG,WG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{auto i=it.get_global_linear_id();if(i<n)element<Code>(s,a,i,Guard{});});});
 }
};

template<int WG>struct DeviceTeam{
 sycl::nd_item<1>it;float*x;
 template<class F>void each(int n,F f)const{for(int j=it.get_local_linear_id();j<n;j+=WG)f(j);}
 void barrier()const{it.barrier(sycl::access::fence_space::global_and_local);}
 int error(ng::Args a)const{return Guard{}.error(a);}void fail(ng::Args a)const{Guard{}.fail(a);}
 float sum(int n,int base=0)const{for(int stride=1;stride<n;stride*=2){each((n+2*stride-1)/(2*stride),[&](int j){int i=j*2*stride;x[base+i]=x[base+i]+(i+stride<n?x[base+i+stride]:0.f);});barrier();}return x[base];}
};
template<int Code,int WG>class CooperativeKernel;
template<ng::Op Code,int WG>struct Cooperative:ownrt::SyclOperation{
 ng::Shape shape;explicit Cooperative(ng::Shape s):shape(s){}
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto s=shape;s.op=Code;ng::Args a;std::copy_n(p.begin(),19,a.p.begin());static_assert(sizeof(s)+sizeof(a)<=1024);
  return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<float,1>x(ng::local_floats(s),h);h.parallel_for<CooperativeKernel<Code,WG>>(sycl::nd_range<1>(size_t(ng::groups(s))*WG,WG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{cooperative_group<Code>(s,a,int(it.get_group_linear_id()),DeviceTeam<WG>{it,x.get_multi_ptr<sycl::access::decorated::no>().get()});});});
 }
};
template<int WG> ownrt::Event submit(ownrt::Device&d,ng::Shape s,std::span<const ownrt::Allocation>a,std::span<const ownrt::Event>deps={}){ng::validate(s);if(a.size()!=19)throw std::invalid_argument("19 tiny bindings");auto sizes=ng::required_bytes(s);for(unsigned j=0;j<19;++j)if(d.arena.row(a[j]).bytes<sizes[j])throw std::invalid_argument("tiny binding size");switch(s.op){
 case ng::activation:{Element<ng::activation,WG>op(s);return d.compute(op,a,deps);}
 case ng::mix:{Element<ng::mix,WG>op(s);return d.compute(op,a,deps);}
 case ng::moe_combine:{Element<ng::moe_combine,WG>op(s);return d.compute(op,a,deps);}
 case ng::conv:{Element<ng::conv,WG>op(s);return d.compute(op,a,deps);}
 case ng::gated_norm:{Cooperative<ng::gated_norm,WG?WG:128>op(s);return d.compute(op,a,deps);}
 case ng::prepare:{Cooperative<ng::prepare,WG?WG:128>op(s);return d.compute(op,a,deps);}
 case ng::pool:{Cooperative<ng::pool,WG?WG:128>op(s);return d.compute(op,a,deps);}
 default:throw std::invalid_argument("unsupported tiny class");}}
}
