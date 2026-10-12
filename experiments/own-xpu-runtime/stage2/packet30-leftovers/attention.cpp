#include "attention.hpp"
#ifndef HOST_ONLY
namespace p30::attention {
namespace {
using Atomic=sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>;
inline void fail(ng::Args a){Atomic(a.i(15)[0]).store(1);}
inline int admitted(sycl::sub_group sg,ng::Shape s,ng::Args a){
 int n=0;if(sg.get_local_linear_id()==0){
  if(!a.i(18)[0]||Atomic(a.i(15)[0]).load())n=-1;
  else if(a.i(17)[0]<0||a.i(17)[0]>=s.capacity){fail(a);n=-1;}
  else {while(n<s.budget+3&&a.i(4)[n]!=-1){int id=a.i(4)[n];if(id<0||id>=s.capacity||id>a.i(17)[0]||n>=s.extra){fail(a);n=-1;break;}++n;}}
 }
 return sycl::select_from_group(sg,n,0);
}
// Adjacent 32-leaf subtrees. Register shuffles communicate VALUES, not
// globally stored data, so no subgroup memory barrier is required.
inline float leaves32(sycl::sub_group sg,float v,int base,int n){
 int lane=sg.get_local_linear_id();
 for(int stride=1;stride<32&&stride<n;stride*=2){
  float rhs=sycl::select_from_group(sg,v,(lane+stride)%32);
  if(lane%(2*stride)==0&&base+lane<n)v=v+(base+lane+stride<n?rhs:0.f);
 }return v;
}
template<class F> inline float subgroup_tree(sycl::sub_group sg,int n,F value){
 int lane=sg.get_local_linear_id();float partial[65];int chunks=(n+31)/32;
 for(int c=0;c<chunks;++c){int j=c*32+lane;float x=j<n?value(j):0.f;x=leaves32(sg,x,c*32,n);if(lane==0)partial[c]=x;}
 float answer=0;if(lane==0)answer=chunks==1?partial[0]:tree(partial,chunks);
 return sycl::select_from_group(sg,answer,0);
}
inline float score(sycl::sub_group sg,ng::Args a,int h,int id){
 int lane=sg.get_local_linear_id();float p[8];for(int j=0;j<8;++j){int k=lane*8+j;p[j]=a.b(2,(id*2+h/12)*256+k)*a.b(0,h*256+k);}
 float v=tree(p,8);for(int stride=1;stride<32;stride*=2){float rhs=sycl::select_from_group(sg,v,(lane+stride)%32);if(lane%(2*stride)==0)v=v+rhs;}
 return sycl::select_from_group(sg,v,0)/detmath::sqrt(256.f);
}
inline float lane_score(ng::Args a,int h,int id){float p[256];for(int k=0;k<256;++k)p[k]=a.b(2,(id*2+h/12)*256+k)*a.b(0,h*256+k);return tree(p,256)/detmath::sqrt(256.f);}
struct Capture {ng::Shape s;ng::Args a;};static_assert(sizeof(Capture)<=1024);
template<int Stage> sycl::event issue(sycl::queue& q,ng::Shape s,ng::Args a,size_t groups,const std::vector<sycl::event>& deps){
 Capture cap{s,a};return q.submit([&](sycl::handler& handler){handler.depends_on(deps);
 handler.parallel_for(sycl::nd_range<1>(std::max(size_t(1),groups)*32,32),[=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
  auto s=cap.s;auto a=cap.a;auto sg=it.get_sub_group();int lane=sg.get_local_linear_id(),g=it.get_group_linear_id(),S=s.budget+3;
  int n=admitted(sg,s,a);if(n<=0)return;
  if constexpr(Stage==0){int h=g/s.extra,j=g%s.extra;if(j>=n)return;float x=score(sg,a,h,a.i(4)[j]);if(lane==0)a.f(6)[h*S+j]=x;}
  if constexpr(Stage==1){int h=g;float m=-INFINITY;for(int j=0;j<n;++j)m=std::max(m,a.f(6)[h*S+j]);
   float den=subgroup_tree(sg,n,[&](int j){return detmath::exp(a.f(6)[h*S+j]-m);});
   for(int j=lane;j<n;j+=32)a.f(7)[h*S+j]=detmath::exp(a.f(6)[h*S+j]-m)/den;
  }
  if constexpr(Stage==2){int h=g/256,k=g%256;float x=subgroup_tree(sg,n,[&](int j){return a.f(7)[h*S+j]*a.b(3,(a.i(4)[j]*2+h/12)*256+k);});
   if(lane==0)a.put(5,g,ng::Args::bf(x)*ng::sigmoid(a.b(1,g)));
  }
  if constexpr(Stage==3){int h=g;float owned[65]{};
   for(int j=lane;j<n;j+=32){float x=lane_score(a,h,a.i(4)[j]);owned[j/32]=x;a.f(6)[h*S+j]=x;}
   // Sequential std::max in selected order preserves the incumbent NaN
   // behavior too; the communication path never reads newly stored scores.
   float m=-INFINITY;for(int j=0;j<n;++j){float x=sycl::select_from_group(sg,owned[j/32],j%32);m=std::max(m,x);}
   for(int c=0;c<(n+31)/32;++c)if(c*32+lane<n)owned[c]=detmath::exp(owned[c]-m);
   float den=subgroup_tree(sg,n,[&](int j){return owned[j/32];});
   for(int j=lane;j<n;j+=32)a.f(7)[h*S+j]=owned[j/32]/den;
  }
 });});
}
}
std::vector<sycl::event> submit(sycl::queue& q,ng::Shape s,ng::Args a,float* scratch,int variant,const std::vector<sycl::event>& deps){
 validate(s,variant);(void)scratch;std::vector<sycl::event> events;
 if(variant==0){events.push_back(issue<0>(q,s,a,size_t(24)*s.extra,deps));events.push_back(issue<1>(q,s,a,24,{events.back()}));}
 else events.push_back(issue<3>(q,s,a,24,deps));
 events.push_back(issue<2>(q,s,a,6144,{events.back()}));return events;
}
}
#endif
