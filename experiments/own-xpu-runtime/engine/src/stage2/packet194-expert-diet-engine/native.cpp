#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#endif
#include "stage2/packet194-expert-diet-engine/native.hpp"
#include "stage1/packet3-prep/src/sycl_operation.hpp"
#include "stage2/packet194-expert-diet-engine/experts_v2.hpp"
namespace ng {
struct DeviceTeam {
 sycl::nd_item<1> it;float* x;
 template<class F> void each(int n,F f)const{for(int j=it.get_local_linear_id();j<n;j+=it.get_local_range(0))f(j);}
 int error(Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).load();}
 void fail(Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).store(1);}
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
  if((s.op==activation||s.op==mix||s.op==moe_combine)&&experts_v2::enabled("ew")){
   // OWNRT_EXPERTS_V2 "ew" (lab 2026-10-26): the element-wise ops without the 128-lane team (no local scratch, no
   // barriers): item idx computes group()'s expression for idx unchanged; the active/sticky-error guard is read once per
   // 32-lane subgroup, and an out-of-range position fails once (item 0) and stops, as in group().
   const size_t n=size_t(s.tokens)*size_t(s.width);
   return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>((n+127)/128*128,128)](sycl::handler& h){
    h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]]{
     Args b=a;b.f32=(s.flags&f32_activations_flag)!=0;auto sg=it.get_sub_group();
     const int blocked=sycl::group_broadcast(sg,sg.get_local_linear_id()==0?int(!b.i(18)[0]||DeviceTeam{it,nullptr}.error(b)):0,0);
     if(blocked)return;
     const size_t idx=it.get_global_linear_id();
     const int pos=b.i(17)[0];if(pos<0||pos>position_limit(s)-s.tokens){if(idx==0)DeviceTeam{it,nullptr}.fail(b);return;}
     if(idx>=n)return;
     const int r=int(idx/size_t(s.width)),k=int(idx%size_t(s.width));const int i=int(idx);
     if(s.op==activation){float v=b.b(0,i);b.put(2,i,s.extra?silu(v)*b.b(1,i):detmath::silu_div4(v));}
     else if(s.op==mix){float sum=0;for(int hh=0;hh<4;++hh)sum=sum+sigmoid(b.b(1,(r*4+hh)*s.width+k))*b.b(0,(r*4+hh)*s.width+k);b.put(2,i,sum/4.f);}
     else{float sum=0;for(int e=0;e<s.extra;++e)sum=sum+b.b(0,(r*s.extra+e)*s.width+k)*b.f(1)[r*s.extra+e];b.put(4,i,b.rnd(sum)+b.rnd(b.b(2,i)*sigmoid(b.b(3,r))));}
    }));
   });
  }
  int work=s.op==gdn?32:128;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(groups(s))*work,work)](sycl::handler& h){sycl::local_accessor<float,1> scratch(local_floats(s),h);
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]]{
    group(s,a,int(it.get_group_linear_id()),DeviceTeam{it,scratch.get_multi_ptr<sycl::access::decorated::no>().get()});
   }));
  });
 }
};
ownrt::Event submit(ownrt::Device& d,Shape s,std::span<const ownrt::Allocation> a,std::span<const ownrt::Event> deps){validate(s);if(a.size()!=19)throw std::invalid_argument("19 bound slots required");auto bytes=required_bytes(s);for(size_t j=0;j<a.size();++j)if(d.arena.row(a[j]).bytes<bytes[j])throw std::invalid_argument("short allocation binding");Kernel k(s);return d.compute(k,a,deps);}
}
