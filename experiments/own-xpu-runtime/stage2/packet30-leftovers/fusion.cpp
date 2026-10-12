#include "fusion.hpp"
namespace p30::fusion {
namespace {
inline bool ready(ng::Shape s,ng::Args a,sycl::nd_item<1> it){
 using Atom=sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>;
 if(!a.i(18)[0]||Atom(a.i(15)[0]).load())return false;int p=a.i(17)[0];if(p<0||p>s.capacity-s.tokens){if(it.get_global_linear_id()==0)Atom(a.i(15)[0]).store(1);return false;}return true;
}
template<bool Combine,bool Tiled> sycl::event norm(sycl::queue& q,ng::Shape s,ng::Args a,const std::vector<sycl::event>& deps){
 unsigned tiles=Tiled?(s.width+255)/256:1;
 auto kernel=[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{if(!ready(s,a,it))return;auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),row=it.get_group_linear_id()/tiles,tile=it.get_group_linear_id()%tiles;
  float partial[80];unsigned chunks=(s.width+31)/32;
  for(unsigned c=0;c<chunks;++c){unsigned k=c*32+lane;float v=0;if(k<unsigned(s.width)){float x=value<Combine>(s,a,row,k);v=x*x;}
   // Each live left tree node adds its original right node, including +0 odd tails.
   for(unsigned stride=1;stride<unsigned(std::min(s.width,32));stride*=2){float other=sycl::select_from_group(sg,v,(lane+stride)%32);if(lane%(stride*2)==0&&k<unsigned(s.width))v=v+(k+stride<unsigned(s.width)?other:0.f);}if(lane==0)partial[c]=v;
  }
  float inv=0;if(lane==0)inv=detmath::rsqrt(specialised::upper(partial,chunks)/float(s.width)+1e-6f);inv=sycl::select_from_group(sg,inv,0);
  unsigned begin=Tiled?tile*256:0,end=Tiled?std::min(unsigned(s.width),begin+256):unsigned(s.width);
  for(unsigned k=begin+lane;k<end;k+=32){float x=value<Combine>(s,a,row,k);float y=(x*inv)*(a.weight(Combine?3:1,row*s.width+k,s.flags)+float(s.flags&1));a.put(Combine?5:2,row*s.width+k,y);if constexpr(Combine)a.put(4,row*s.width+k,x);}
 };static_assert(sizeof(kernel)<=1024);return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(4*tiles*32,32),kernel);});
}
}
std::vector<sycl::event> submit(sycl::queue& q,ng::Shape s,ng::Args a,const std::array<size_t,19>& bytes,std::string_view v,const std::vector<sycl::event>& deps){validate(s,a,bytes,v);
 if(s.op==ng::combine_norm){if(v=="tiled")return {norm<true,true>(q,s,a,deps)};return {norm<true,false>(q,s,a,deps)};}
 if(s.op==ng::norm){if(v=="tiled")return {norm<false,true>(q,s,a,deps)};return {norm<false,false>(q,s,a,deps)};}
 unsigned local=v=="sg32"?32:128;auto kernel=[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{if(!ready(s,a,it))return;unsigned k=it.get_global_linear_id();if(k>=unsigned(s.width))return;float sum=0;for(unsigned h=0;h<4;++h)sum=sum+ng::sigmoid(a.b(1,h*s.width+k))*a.b(0,h*s.width+k);a.put(2,k,sum/4.f);};static_assert(sizeof(kernel)<=1024);
 return {q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(((s.width+local-1)/local)*local,local),kernel);})};
}
}
