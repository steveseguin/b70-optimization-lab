#include <sycl/sycl.hpp>
#include "fused.hpp"
struct Team {
 sycl::nd_item<1> it;float* x;
 template<class F>void each(int n,F f)const{for(int j=it.get_local_linear_id();j<n;j+=128)f(j);}
 void barrier()const{it.barrier(sycl::access::fence_space::global_and_local);}
 int error(ng::Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[2]).load();}
 void fail(ng::Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[2]).store(1);}
 float sum(int n,int base=0)const{for(int stride=1;stride<n;stride*=2){each((n+2*stride-1)/(2*stride),[&](int j){int i=j*2*stride;x[base+i]=x[base+i]+(i+stride<n?x[base+i+stride]:0.f);});barrier();}return x[base];}
};
sycl::event submit_chain(sycl::queue&q,const fusion::Site* device_sites,int count,int local,const std::vector<sycl::event>& deps){return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<float> x(local,h);h.parallel_for(sycl::nd_range<1>(128,128),[=](sycl::nd_item<1>it){fusion::chain(device_sites,count,Team{it,x.get_multi_ptr<sycl::access::decorated::no>().get()});});});}
sycl::event submit_attention(sycl::queue&q,ng::Shape s,ng::Args a,const std::vector<sycl::event>& deps){return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<float>x(std::max(1024,s.budget+3),h);h.parallel_for(sycl::nd_range<1>(s.tokens*24*128,128),[=](sycl::nd_item<1>it){fusion::attention(s,a,it.get_group_linear_id(),Team{it,x.get_multi_ptr<sycl::access::decorated::no>().get()});});});}
std::array<sycl::event,2> submit_route(sycl::queue&q,ng::Shape s,ng::Args a,float* selected,const std::vector<sycl::event>&deps){
 auto rank=q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<float>x(2048,h);h.parallel_for(sycl::nd_range<1>(s.tokens*4*128,128),[=](sycl::nd_item<1>it){fusion::route_rank(s,a,selected,it.get_group_linear_id(),Team{it,x.get_multi_ptr<sycl::access::decorated::no>().get()});});});
 auto finish=q.submit([&](sycl::handler&h){h.depends_on(rank);sycl::local_accessor<float>x(s.extra,h);h.parallel_for(sycl::nd_range<1>(s.tokens*128,128),[=](sycl::nd_item<1>it){fusion::route_finish(s,a,selected,it.get_group_linear_id(),Team{it,x.get_multi_ptr<sycl::access::decorated::no>().get()});});});return {rank,finish};
}
// Compile/link artifact only: never execute, even --help.
int main(){return 0;}
