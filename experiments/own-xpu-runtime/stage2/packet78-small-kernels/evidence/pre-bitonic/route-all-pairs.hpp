#pragma once
#include "p49d_route.hpp"
// One workgroup owns every global dependency. Rank the rounded probabilities,
// never raw logits: exp/division can introduce ties. No floating-point reorder.
namespace p78route {
inline void host(route42::Args a) {
  for(unsigned c=0;c<32;++c)route42::phase<0,512,10>(a,c);
  if(!*a.active||a.failed())return;
  p49c::route_exp_host(a);
  float den=route42::subtree<256>(32,0,[&](int j){return a.scratch[32+j];});
  float probabilities[512];
  for(unsigned j=0;j<512;++j)probabilities[j]=a.scratch[64+j]/den;
  for(unsigned j=0;j<512;++j){
    unsigned rank=0;
    for(unsigned k=0;k<512;++k)
      rank+=probabilities[k]>probabilities[j]||(probabilities[k]==probabilities[j]&&k<j);
    route42::output<512,10>(a,j,rank);
  }
  route42::phase<4,512,10>(a,0);
}
struct Kernel final:p49c::Base {
  integrated::Spec spec;
#ifdef OWN_RT_HOST_ONLY
  void run(std::span<void*const> p)const override{p78route::host(route42::bind(spec,p));}
#else
  sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
    auto a=route42::bind(spec,p);
    return q.submit([&](sycl::handler&h){
      h.depends_on(deps);
      sycl::local_accessor<float,1> cache(513,h);
      sycl::local_accessor<uint32_t,1> control(1,h);
      h.parallel_for(sycl::nd_range<1>(256,256),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
        unsigned tid=it.get_local_linear_id(),lane=tid%32;auto sg=it.get_sub_group();
        if(!tid)control[0]=uint32_t(*a.active&&!a.failed());
        it.barrier(sycl::access::fence_space::local_space);if(!control[0])return;
        if(tid<32)route42::phase<0,512,10>(a,tid);
        it.barrier(sycl::access::fence_space::global_and_local);
        if(!tid)control[0]=!a.failed();
        it.barrier(sycl::access::fence_space::local_space);if(!control[0])return;
        if(!tid){float m=-INFINITY;for(unsigned c=0;c<32;++c)m=std::max(m,a.scratch[c]);cache[512]=m;}
        it.barrier(sycl::access::fence_space::local_space);
        float maximum=cache[512];
        for(unsigned offset=0;offset<512;offset+=256){
          unsigned j=offset+tid;float v=detmath::exp(a.in().get(j)-maximum);a.scratch[64+j]=v;
          for(unsigned width=1;width<16;width*=2){float r=sycl::select_from_group(sg,v,(lane+width)%32);if(lane%(2*width)==0)v=v+r;}
          if(lane%16==0)a.scratch[32+j/16]=v;
        }
        it.barrier(sycl::access::fence_space::global_and_local);
        if(!tid)cache[512]=route42::subtree<256>(32,0,[&](int j){return a.scratch[32+j];});
        it.barrier(sycl::access::fence_space::local_space);
        float den=cache[512];
        for(unsigned j=tid;j<512;j+=256)cache[j]=a.scratch[64+j]/den;
        it.barrier(sycl::access::fence_space::local_space);
        float v0=cache[tid],v1=cache[tid+256];unsigned r0=0,r1=0;
        for(unsigned k=0;k<512;++k){float other=cache[k];r0+=other>v0||(other==v0&&k<tid);r1+=other>v1||(other==v1&&k<tid+256);}
        route42::output<512,10>(a,tid,r0);route42::output<512,10>(a,tid+256,r1);
        it.barrier(sycl::access::fence_space::global_and_local);
        if(!tid)route42::phase<4,512,10>(a,0);
      });
    });
  }
#endif
};
inline integrated::Launch submit(ownrt::Device&d,const integrated::Spec&s,std::span<const ownrt::Allocation>a,std::span<const ownrt::Event>deps={}){
  p49droute::validate(d,s,a);Kernel k;k.spec=s;auto e=d.compute(k,a,deps);return {e,e,1};
}
}
