#include "native.hpp"
#include "sycl_operation.hpp"
namespace ng {
struct DeviceTeam {
 sycl::nd_item<1> it;float* x;
 template<class F> void each(int n,F f)const{for(int j=it.get_local_linear_id();j<n;j+=it.get_local_range(0))f(j);}
 int error(Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[2]).load();}
 void fail(Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[2]).store(1);}
 void barrier()const{it.barrier(sycl::access::fence_space::global_and_local);}
 float sum(int n,int base=0)const{
  for(int stride=1;stride<n;stride*=2){each((n+2*stride-1)/(2*stride),[&](int j){int i=j*2*stride;x[base+i]=x[base+i]+(i+stride<n?x[base+i+stride]:0.f);});barrier();}
  return x[base];
 }
};
struct Kernel final:ownrt::SyclOperation{
 Shape shape;
 explicit Kernel(Shape s):shape(s){}
 sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps)const override{
  Args a;std::copy(p.begin(),p.end(),a.p.begin());auto s=shape;
  int work=s.op==gdn?32:128;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> scratch(local_floats(s),h);
   h.parallel_for(sycl::nd_range<1>(size_t(groups(s))*work,work),[=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]]{
    group(s,a,int(it.get_group_linear_id()),DeviceTeam{it,scratch.get_multi_ptr<sycl::access::decorated::no>().get()});
   });
  });
 }
};
ownrt::Event submit(ownrt::Device& d,Shape s,std::span<const ownrt::Allocation> a,std::span<const ownrt::Event> deps){validate(s);if(a.size()!=16)throw std::invalid_argument("16 bound slots required");auto bytes=required_bytes(s);for(size_t j=0;j<a.size();++j)if(d.arena.row(a[j]).bytes<bytes[j])throw std::invalid_argument("short allocation binding");Kernel k(s);return d.compute(k,a,deps);}
}
