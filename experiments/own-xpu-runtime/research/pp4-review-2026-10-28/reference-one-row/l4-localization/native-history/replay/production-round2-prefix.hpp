#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#endif
#include "stage2/packet194-expert-diet-engine/round2_submit.hpp"
#include "stage2/packet194-expert-diet-engine/mock_order.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace round2 {
#ifndef OWN_RT_HOST_ONLY
struct Team {
 sycl::nd_item<1> it;float* x;
 template<class F>void each(int n,F f)const{for(int j=it.get_local_linear_id();j<n;j+=32)f(j);}
 void barrier()const{it.barrier(sycl::access::fence_space::global_and_local);}
 int error(ng::Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).load();}
 void fail(ng::Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).store(1);}
 float sum(int n,int base=0)const{for(int stride=1;stride<n;stride*=2){each((n+2*stride-1)/(2*stride),[&](int j){int i=j*2*stride;x[base+i]=x[base+i]+(i+stride<n?x[base+i+stride]:0.f);});barrier();}return x[base];}
};
// This is an adjacent reduction, NOT the implementation-defined SYCL sum.
inline float lane_tree(sycl::sub_group sg,float v){
 unsigned lane=sg.get_local_linear_id();
 for(unsigned stride=1;stride<32;stride*=2){float right=sycl::select_from_group(sg,v,sycl::id<1>((lane+stride)%32));if(lane%(2*stride)==0)v=v+right;}
 return sycl::select_from_group(sg,v,sycl::id<1>(0));
}
template<bool Prepared> inline void gdn_device(ng::Shape s,ng::Args a,float* prepared,sycl::nd_item<1> it){
 auto sg=it.get_sub_group();int lane=sg.get_local_linear_id(),g=it.get_group_linear_id();
 Team t{it,nullptr};int blocked=lane==0?int(!a.i(18)[0]||t.error(a)):0;
 if(sycl::select_from_group(sg,blocked,sycl::id<1>(0)))return;
 int pos=a.i(17)[0];if(pos<0||pos>s.capacity-s.tokens){if(g==0&&lane==0)t.fail(a);return;}
 int h=g/128,j=g%128,key=(s.flags&4)?h%16:h/3,state=g*128;
 for(int r=0;r<s.tokens;++r){int qb=r*10240+key*128,kb=qb+2048;float q[4],k[4],v[4],decay,beta,pred=0.f;
  if constexpr(Prepared){
   const float* prep=prepared+size_t(r)*gdn_prep_floats;
   for(int z=0;z<4;++z){q[z]=prep[key*128+4*lane+z];k[z]=prep[2048+key*128+4*lane+z];}
   decay=prep[4096+h];beta=prep[4144+h];
  }else{
   float qs=0.f,ks=0.f;for(int z=0;z<4;++z){q[z]=a.b(0,qb+4*lane+z);k[z]=a.b(0,kb+4*lane+z);qs=qs+q[z]*q[z];ks=ks+k[z]*k[z];}
   float qn=detmath::sqrt(lane_tree(sg,qs)+1e-6f),kn=detmath::sqrt(lane_tree(sg,ks)+1e-6f);
   float gate=a.b(1,r*48+h)+a.weight(4,h,s.flags),sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate,av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));
   decay=detmath::exp(av*sp);beta=ng::sigmoid(a.b(2,r*48+h));
   for(int z=0;z<4;++z){q[z]=(q[z]/qn)/detmath::sqrt(float(128));k[z]=k[z]/kn;}
  }
  for(int z=0;z<4;++z){v[z]=a.b(r?7:5,state+4*lane+z)*decay;pred=pred+v[z]*k[z];}
  pred=lane_tree(sg,pred);float delta=(a.b(0,r*10240+4096+h*128+j)-pred)*beta,y=0.f;
  for(int z=0;z<4;++z){v[z]=v[z]+delta*k[z];y=y+v[z]*q[z];}
  y=lane_tree(sg,y);if(lane==0)a.put(6,(r*48+h)*128+j,y);
  for(int z=0;z<4;++z)a.put(7,state+4*lane+z,v[z]);
  // Next token reads the rounded state, including when input/output alias.
  sycl::group_barrier(sg,sycl::memory_scope::device);
 }
}
inline void gdn_prep_device(ng::Shape s,ng::Args a,float* prepared,sycl::nd_item<1> it){
 auto sg=it.get_sub_group();int lane=sg.get_local_linear_id(),group=it.get_group_linear_id(),r=group/16,key=group%16;
 Team t{it,nullptr};int blocked=lane==0?int(!a.i(18)[0]||t.error(a)):0;
 if(sycl::select_from_group(sg,blocked,sycl::id<1>(0)))return;
 int pos=a.i(17)[0];if(pos<0||pos>s.capacity-s.tokens){if(group==0&&lane==0)t.fail(a);return;}
 prepared+=size_t(r)*gdn_prep_floats;
 int qb=r*10240+key*128,kb=qb+2048;float q[4],k[4],qs=0.f,ks=0.f;
 for(int z=0;z<4;++z){q[z]=a.b(0,qb+4*lane+z);k[z]=a.b(0,kb+4*lane+z);qs=qs+q[z]*q[z];ks=ks+k[z]*k[z];}
 float qn=detmath::sqrt(lane_tree(sg,qs)+1e-6f),kn=detmath::sqrt(lane_tree(sg,ks)+1e-6f);
 for(int z=0;z<4;++z){prepared[key*128+4*lane+z]=(q[z]/qn)/detmath::sqrt(float(128));prepared[2048+key*128+4*lane+z]=k[z]/kn;}
 for(int u=0;u<3;++u)if(lane==0){int h=(s.flags&4)?key+16*u:key*3+u;
  float gate=a.b(1,r*48+h)+a.weight(4,h,s.flags),sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate,av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));
  prepared[4096+h]=detmath::exp(av*sp);prepared[4144+h]=ng::sigmoid(a.b(2,r*48+h));
 }
}
#endif
#ifdef OWN_RT_HOST_ONLY
template<ng::Op Code,int Stage> struct Kernel final:integrated::HostOperation {
 ng::Shape s;explicit Kernel(ng::Shape v):s(v){}
 void run(std::span<void*const> p)const override{ng::Args a;std::copy_n(p.begin(),19,a.p.begin());if constexpr(Code==ng::gdn)gdn_host(s,a);else {std::vector<float> local(round2::local_floats(s));packet24::mock_items(round2::groups(s),[&](size_t g){group<Code,Stage>(s,a,int(g),static_cast<float*>(p[19]),ng::HostTeam{local.data()});});}}
};
#else
template<ng::Op Code,int Stage> struct Kernel final:ownrt::SyclOperation {
 ng::Shape s;explicit Kernel(ng::Shape v):s(v){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
  ng::Args a;std::copy_n(p.begin(),19,a.p.begin());auto shape=s;float* global=static_cast<float*>(p[19]);int count=round2::groups(s),local=round2::local_floats(s);
  a.f32=(s.flags&ng::f32_activations_flag)!=0; // as ng::group(): F32 exact-mode buffers are read and written as F32
  if constexpr(Code==ng::gdn){
   if constexpr(Stage==1)return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(shape.tokens)*16*32,32)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{gdn_prep_device(shape,a,global,it);}));});
   else if(gdn_prep(s))return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(count)*32,32)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{gdn_device<true>(shape,a,global,it);}));});
   else return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(count)*32,32)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{gdn_device<false>(shape,a,global,it);}));});
  }
  else return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(count)*32,32)](sycl::handler& h){sycl::local_accessor<float,1> x(local,h);h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{group<Code,Stage>(shape,a,int(it.get_group_linear_id()),global,Team{it,x.get_multi_ptr<sycl::access::decorated::no>().get()});}));});
 }
};
#endif

} // namespace round2
