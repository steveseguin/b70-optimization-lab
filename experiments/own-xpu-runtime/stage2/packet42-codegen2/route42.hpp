#pragma once
#ifndef OWN_RT_HOST_ONLY
#include <sycl/sycl.hpp>
#endif
#include "../packet29-merged/adapter.hpp"
#include "../packet29-merged/p28/submit.hpp"
namespace route42 {
using namespace integrated;
struct Args {const void* input;void* output[4];float* scratch;uint32_t* error;const uint32_t* active;flash::Scalar input_type;flash::Scalar output_type[4];unsigned n,top,mid,h,no;
 View in()const{return {const_cast<void*>(input),n,input_type};}View out(unsigned j)const{return {output[j],j<2?top:top*3,output_type[j]};}
 uint32_t failed()const{
#ifdef OWN_RT_HOST_ONLY
 return *error;
#else
 return sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*error).load();
#endif
 }
 void fail()const{
#ifdef OWN_RT_HOST_ONLY
 *error=1;
#else
 sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*error).store(1);
#endif
 }
};
static_assert(sizeof(Args)<=128);
inline Args bind(const Spec&s,std::span<void*const>p){Args a{};a.input=p[0];a.input_type=s.types[0];a.n=s.sizes[0];a.top=s.site.shape[1];a.mid=s.g.mid;a.h=s.g.h;a.no=s.no;for(unsigned j=0;j<a.no;++j){a.output[j]=p[s.ni+j];a.output_type[j]=s.types[s.ni+j];}unsigned tail=s.ni+s.no+s.nw;a.scratch=static_cast<float*>(p[tail]);a.error=static_cast<uint32_t*>(p[tail+1]);a.active=static_cast<const uint32_t*>(p[tail+3]);return a;}
template<int Width,class F>float subtree(int n,int begin,F get){float v[Width];int count=std::min(Width,n-begin);for(int i=0;i<count;++i)v[i]=get(begin+i);for(int stride=1;stride<Width&&stride<n;stride*=2)for(int i=0;i<count;i+=2*stride)v[i]=v[i]+(i+stride<count?v[i+stride]:0.f);return v[0];}
template<unsigned Stage,unsigned N=0,unsigned Top=0>void phase(Args a,unsigned index){if(!*a.active||a.failed())return;unsigned n=N?N:a.n,top=Top?Top:a.top,chunks=(n+15)/16;float*sum=a.scratch+chunks;float*ex=sum+chunks;
 if constexpr(Stage==0){float maximum=-INFINITY;for(unsigned j=index*16;j<std::min(n,(index+1)*16);++j){float x=a.in().get(j);if(!std::isfinite(x)){a.fail();return;}maximum=std::max(maximum,x);}a.scratch[index]=maximum;}
 if constexpr(Stage==1){float maximum=-INFINITY;for(unsigned j=0;j<chunks;++j)maximum=std::max(maximum,a.scratch[j]);sum[index]=subtree<16>(n,index*16,[&](int j){float v=detmath::exp(a.in().get(j)-maximum);ex[j]=v;return v;});}
 if constexpr(Stage==4){float total=subtree<32>(top,0,[&](int j){return a.out(1).get(j);});for(unsigned j=0;j<top;++j)a.out(1).put(j,a.out(1).get(j)/total);}
}
template<unsigned N=0>unsigned rank_lane(Args a,unsigned index,unsigned lane){unsigned n=N?N:a.n,chunks=(n+15)/16;float*sums=a.scratch+chunks,*ex=sums+chunks;float den=subtree<256>(chunks,0,[&](int j){return sums[j];});float value=ex[index]/den;unsigned rank=0;for(unsigned k=lane;k<n;k+=32){float x=ex[k]/den;rank+=x>value||(x==value&&k<index);}return rank;}
template<unsigned N=0,unsigned Top=0>void output(Args a,unsigned index,unsigned rank){unsigned n=N?N:a.n,top=Top?Top:a.top,chunks=(n+15)/16;if(rank<top){float*sums=a.scratch+chunks,*ex=sums+chunks;float den=subtree<256>(chunks,0,[&](int j){return sums[j];});float v=ex[index]/den;a.out(0).put(rank,index);a.out(1).put(rank,v);if(a.no>=4)for(unsigned k=0;k<3;++k){a.out(2).put(rank*3+k,k==0?index:k==1?0:a.mid);a.out(3).put(rank*3+k,k==0?index:k==1?0:a.h);}}}
inline void host(Args a){for(unsigned i=0;i<(a.n+15)/16;++i)phase<0>(a,i);for(unsigned i=0;i<(a.n+15)/16;++i)phase<1>(a,i);if(*a.active&&!a.failed())for(unsigned j=0;j<a.n;++j){unsigned rank=0;for(unsigned lane=0;lane<32;++lane)rank+=rank_lane(a,j,lane);output(a,j,rank);}phase<4>(a,0);}
integrated::Launch submit(ownrt::Device&,const Spec&,std::span<const ownrt::Allocation>,std::span<const ownrt::Event> = {});
}
