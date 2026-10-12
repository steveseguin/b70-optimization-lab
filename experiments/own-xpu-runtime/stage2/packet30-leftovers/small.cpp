#include "small.hpp"
namespace p30::small {
namespace {
template<class M> void row(Bound b,unsigned r,sycl::sub_group sg,unsigned lane,size_t rb){
 float partial[M::split];for(unsigned p=0;p<M::split;++p){float sum=r<M::rows?M::lane(b.w+size_t(r)*rb,b.x,p,lane):0.f;
  for(unsigned stride=1;stride<32;stride*=2){float other=sycl::select_from_group(sg,sum,(lane+stride)%32);if(lane%(stride*2)==0)sum=sum+other;}partial[p]=sum;}
 if(r<M::rows&&lane==0){float v=partial[0];if constexpr(M::split==4)v=(partial[0]+partial[1])+(partial[2]+partial[3]);b.y[r]=iq3::bf16_bits(v);}
}
template<class A,class B=void,class C=void,class D=void> sycl::event launch(sycl::queue& q,std::span<const Bound> bs,unsigned local,const std::vector<sycl::event>& deps){
 std::array<Bound,4> b{};for(size_t i=0;i<bs.size();++i)b[i]=bs[i];unsigned rows=A::rows;if constexpr(!std::is_void_v<B>)rows+=B::rows;if constexpr(!std::is_void_v<C>)rows+=C::rows+D::rows;
 auto kernel=[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),r=it.get_global_linear_id()/32;
  if(r<A::rows)row<A>(b[0],r,sg,lane,b[0].weight_bytes/A::rows);
  else if constexpr(!std::is_void_v<B>){r-=A::rows;if(r<B::rows)row<B>(b[1],r,sg,lane,b[1].weight_bytes/B::rows);
   else if constexpr(!std::is_void_v<C>){r-=B::rows;if(r<C::rows)row<C>(b[2],r,sg,lane,b[2].weight_bytes/C::rows);else {r-=C::rows;if(r<D::rows)row<D>(b[3],r,sg,lane,b[3].weight_bytes/D::rows);}}}
 };static_assert(sizeof(kernel)<=1024);return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(((size_t(rows)*32+local-1)/local)*local,local),kernel);});
}
}
std::vector<sycl::event> submit(sycl::queue& q,std::string_view n,std::span<const Bound> bs,std::string_view v,const std::vector<sycl::event>& deps){validate(n,bs,v);unsigned l=v=="sg32"?32:128;
 // Clamp extents used as strides to exact admitted matrix size, not allocation padding.
 auto ss=shapes(n);std::vector<Bound> exact(bs.begin(),bs.end());for(size_t i=0;i<ss.size();++i)exact[i].weight_bytes=size_t(ss[i].rows)*row_bytes(ss[i]);
 if(n=="hc.gate")return {launch<Gate>(q,exact,l,deps)};if(n=="shexpdown")return {launch<Down>(q,exact,l,deps)};
 if(n=="small.hc")return {launch<Low,Inject>(q,exact,l,deps)};
 if(n=="small.ffn.q6")return {launch<Router,Q6,Q6,Shared>(q,exact,l,deps)};
 if(n=="small.ffn.q8")return {launch<Router,Q8,Q8,Shared>(q,exact,l,deps)};throw std::invalid_argument("p30 small family");
}
}
