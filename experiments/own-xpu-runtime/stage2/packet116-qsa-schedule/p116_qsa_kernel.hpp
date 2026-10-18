#pragma once
#include "p116_qsa_host.hpp"
#include "p49_qsa_kernel.hpp"
namespace p116 {
// Integer rank reduction may use a different tree: it cannot round or overflow
// (at most8192 pool blocks). Score trees remain explicitly adjacent FP32 trees.
inline int integer_sum(sycl::sub_group sg,int value){return sycl::reduce_over_group(sg,value,sycl::plus<int>());}
template<int Stage>inline sycl::event selection_device(sycl::queue&q,ng::Shape s,ng::Args a,float*global,const std::vector<sycl::event>&deps){
 int L=(ng::launch_extent(s)+3)/4,cap=(s.capacity+3)/4,S=s.budget+3;
 return q.submit([&](sycl::handler& handler){handler.depends_on(deps);
 handler.parallel_for(sycl::nd_range<1>(size_t(s.tokens)*L*32,32),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  auto sg=it.get_sub_group();int lane=sg.get_local_linear_id(),g=it.get_group_linear_id(),r=g/L,b=g%L;
  int stop=lane==0?int(p47::blocked(a)):0;if(sycl::select_from_group(sg,stop,0))return;
  int pos=a.i(17)[0];if(pos<0||pos>ng::position_limit(s)-s.tokens){if(g==0&&lane==0)p47::Atomic(a.i(15)[0]).store(1);return;}
  int n=(pos+r+1)/4,count=std::min(n,s.budget/4);
  if constexpr(Stage==0){if(b>=n)return;float score=0.f;
   for(int h=0;h<4;++h){float v[4];for(int j=0;j<4;++j){int k=lane*4+j;v[j]=a.b(0,(r*4+h)*128+k)*a.b(1,b*128+k);}float x=(v[0]+v[1])+(v[2]+v[3]);float d=p47::lane_tree(sg,x);score=score+std::max(0.f,d);}
   if(lane==0)global[r*cap+b]=score/detmath::sqrt(128.f);
  }else {if(b>=n&&b!=0)return;bool finite=true;int rank=0;float v=b<n?global[r*cap+b]:0.f;
   for(int k=lane;k<n;k+=32){float x=global[r*cap+k];finite=finite&&std::isfinite(x);rank+=x>v||(x==v&&k<b);}
   finite=sycl::all_of_group(sg,finite);rank=integer_sum(sg,rank);
   if(!finite){if(b==0){for(int k=lane;k<S;k+=32)a.i(2)[r*S+k]=-1;if(lane==0)p47::Atomic(a.i(15)[0]).store(1);}return;}
   if(b==0){int end=count*4+(pos+r+1-n*4);for(int k=end+lane;k<S;k+=32)a.i(2)[r*S+k]=-1;for(int k=lane;k<pos+r+1-n*4;k+=32)a.i(2)[r*S+count*4+k]=n*4+k;}
   if(b<n&&rank<count&&lane<4)a.i(2)[r*S+rank*4+lane]=b*4+lane;
  }
 });});
}
inline sycl::event tiles(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,float*partial,const std::vector<sycl::event>&deps){
 int C=p47::splits(s);return q.submit([&](sycl::handler& handler){handler.depends_on(deps);sycl::local_accessor<float,1> local(65,handler);
 handler.parallel_for(sycl::nd_range<1>(size_t(s.tokens)*24*C*256,256),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  int g=it.get_group_linear_id(),c=g%C,h=(g/C)%24,r=g/(C*24),lid=it.get_local_linear_id(),n=counts[r],S=s.budget+3,start=c*32;
  if(n<=0||p47::blocked(a)||start>=n)return;auto sg=it.get_sub_group();int lane=sg.get_local_linear_id(),sub=lid/32;float*p=partial+size_t(g)*258;
  for(int j=sub;j<32;j+=8){float x=-INFINITY;if(start+j<n)x=p47::score(sg,a,r,h,a.i(4)[r*S+start+j]);if(lane==0)local[j]=x;}
  it.barrier(sycl::access::fence_space::local_space);
  if(lid==0){float m=-INFINITY;for(int j=0;j<32&&start+j<n;++j)m=std::max(m,local[j]);local[64]=m;p[256]=m;}
  it.barrier(sycl::access::fence_space::local_space);
  if(lid<32){float x=start+lid<n?detmath::exp(local[lid]-local[64]):0.f;local[32+lid]=x;float den=p47::lane_tree(sg,x);if(lid==0)p[257]=den;}
  it.barrier(sycl::access::fence_space::local_space);
  // Retain production's vector2 numerator body and operand/storage order.
  // The other128 lanes parallelize scores; the original128 own value pairs.
  if(lid<128){
   sycl::vec<float,2> vals[32];for(int j=0;j<32;++j){vals[j]=sycl::vec<float,2>(0.f);if(start+j<n){int id=a.i(4)[r*S+start+j];sycl::vec<uint16_t,2>v;v.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(static_cast<const uint16_t*>(a.p[3])+(id*2+h/12)*256+lid*2));for(int d=0;d<2;++d)vals[j][d]=local[32+j]*p47::bf(v[d]);}}
   for(int z=1;z<32;z*=2)for(int j=0;j<32;j+=2*z)vals[j]=vals[j]+vals[j+z];
   p[lid*2]=vals[0][0];p[lid*2+1]=vals[0][1];
  }
 });});
}
}
