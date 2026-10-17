#pragma once
#include "../packet45-merged3/p33_candidates.hpp"
#include "../packet45-merged3/runtime_kernels.hpp"
#include "../packet45-merged3/performance.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
// Independent packet46 composition; all arithmetic helpers are lab-owned P45.
namespace p46 {
using iq3::Type;
#ifdef OWN_RT_HOST_ONLY
using Base=integrated::HostOperation;
#else
using Base=ownrt::SyclOperation;
#endif
inline float bf(float x){return iq3::bits_float(uint32_t(iq3::bf16_bits(x))<<16);}
inline float get(const uint16_t* p,size_t i){return iq3::bits_float(uint32_t(p[i])<<16);}
inline uint32_t error(void*p){
#ifdef OWN_RT_HOST_ONLY
 return *static_cast<uint32_t*>(p);
#else
 return sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*static_cast<uint32_t*>(p)).load();
#endif
}
inline void fail(void*p){
#ifdef OWN_RT_HOST_ONLY
 *static_cast<uint32_t*>(p)=1;
#else
 sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*static_cast<uint32_t*>(p)).store(1);
#endif
}

struct DenseBinding {const uint8_t* w;const uint16_t* x;uint16_t* y;};
template<Type T,unsigned R,unsigned K,unsigned Split,bool StoreScratch=false> struct Member {
 static constexpr unsigned rows=R,cols=K,split=Split;
 static constexpr bool store_scratch=StoreScratch;
 // Use runtime's layout, including retained metadata; never infer stride from bits.
 static size_t stride(){return iq3::expanded::row_bytes(T,K);}
 static float lane(const uint8_t*w,const uint16_t*x,unsigned part,unsigned lane){auto b=iq3::kopt2::bounds(K,part,Split);return p33::dense_lane<T,K>(w,x,b.first,b.second,lane);}
 static float cpu(const uint8_t*w,const uint16_t*x){float part[Split];for(unsigned p=0;p<Split;++p){float lanes[32];for(unsigned l=0;l<32;++l)lanes[l]=lane(w,x,p,l);part[p]=iq3::tree32(lanes);}if constexpr(Split==4)return (part[0]+part[1])+(part[2]+part[3]);else return part[0];}
};
using Qkv=Member<Type::Q6_K,10240,2560,1>;
using Z=Member<Type::Q6_K,6144,2560,1>;
using Q=Member<Type::Q6_K,12288,2560,1>;
using K=Member<Type::Q6_K,512,2560,4>;
using Iq=Member<Type::BF16,512,2560,4>;
using Ik=Member<Type::BF16,128,2560,4,true>;
using Gate=Member<Type::Q8_0,10240,320,1>;
// Each subgroup owns a row and retains the eight consecutive inputs per lane,
// adjacent SG32 tree and separate split-four tree. No device operation dispatch.
template<class... Ms> struct Tuple final:Base {
 static constexpr size_t count=sizeof...(Ms);
 static constexpr size_t rows=(Ms::rows+...+0);
 std::array<size_t,count> strides{Ms::stride()...};
 static auto bind(std::span<void*const>p){std::array<DenseBinding,count>b{};for(size_t i=0;i<count;++i)b[i]={static_cast<const uint8_t*>(p[3*i]),static_cast<const uint16_t*>(p[3*i+1]),static_cast<uint16_t*>(p[3*i+2])};return b;}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{auto b=bind(p);size_t i=0;([&]{auto v=b[i];auto rb=strides[i++];for(unsigned r=0;r<Ms::rows;++r)v.y[r]=iq3::bf16_bits(Ms::cpu(v.w+r*rb,v.x));}(),...);}
#else
 template<class M>static void row(DenseBinding b,size_t rb,unsigned r,sycl::sub_group sg,unsigned lane,float*scratch){float parts[M::split];for(unsigned part=0;part<M::split;++part){float v=M::lane(b.w+r*rb,b.x,part,lane);for(unsigned s=1;s<32;s*=2){float other=sycl::select_from_group(sg,v,(lane+s)%32);if(lane%(2*s)==0)v=v+other;}parts[part]=v;if constexpr(M::store_scratch)if(!lane)scratch[r*8+part]=v;}if(!lane){float y=parts[0];if constexpr(M::split==4)y=(parts[0]+parts[1])+(parts[2]+parts[3]);b.y[r]=iq3::bf16_bits(y);}}
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{auto b=bind(p);auto rb=strides;auto scratch=static_cast<float*>(p[count*3]);return q.submit([&](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(rows*32,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{unsigned r=it.get_global_linear_id()/32,lane=it.get_sub_group().get_local_linear_id();size_t off=0,j=0;([&]{if(r>=off&&r<off+Ms::rows)row<Ms>(b[j],rb[j],r-off,it.get_sub_group(),lane,scratch);off+=Ms::rows;++j;}(),...);});});}
#endif
};
// Four independently computed HC gates belong to one output coordinate. The
// BF16 gate store remains before sigmoid; mix preserves h=0,1,2,3 ordering.
struct GateMix final:Base {
 size_t rb=Gate::stride();
 static void tail(std::span<void*const>p,unsigned k,const float (&values)[4]){auto gate=static_cast<uint16_t*>(p[2]),out=static_cast<uint16_t*>(p[4]);auto norm=static_cast<const uint16_t*>(p[3]);float sum=0;for(unsigned h=0;h<4;++h){unsigned i=h*2560+k;gate[i]=iq3::bf16_bits(values[h]);sum=sum+ng::sigmoid(bf(values[h]))*get(norm,i);}if(!*static_cast<uint32_t*>(p[6])||error(p[5]))return;if(*static_cast<uint32_t*>(p[7])>=4096){if(!k)fail(p[5]);return;}out[k]=iq3::bf16_bits(sum/4.f);}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{auto w=static_cast<const uint8_t*>(p[0]);auto x=static_cast<const uint16_t*>(p[1]);for(unsigned k=0;k<2560;++k){float v[4];for(unsigned h=0;h<4;++h)v[h]=Gate::cpu(w+(h*2560+k)*rb,x);tail(p,k,v);}}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{std::array<void*,8>a;std::copy_n(p.begin(),8,a.begin());auto stride=rb;return q.submit([&](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(2560*32,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),k=it.get_global_linear_id()/32;auto w=static_cast<const uint8_t*>(a[0]);auto x=static_cast<const uint16_t*>(a[1]);float v[4];for(unsigned h=0;h<4;++h){float s=Gate::lane(w+(h*2560+k)*stride,x,0,lane);for(unsigned z=1;z<32;z*=2){float other=sycl::select_from_group(sg,s,(lane+z)%32);if(lane%(2*z)==0)s=s+other;}v[h]=s;}if(!lane)tail(a,k,v);});});}
#endif
};
// The current norm materializes eighty 32-leaf partials per stream. Preserve
// those FP32 bytes while keeping its two reduction levels in one workgroup.
struct Norm final:Base {
 static void subtree(std::span<void*const>p,unsigned row,unsigned chunk){auto x=static_cast<const uint16_t*>(p[0]);auto tmp=static_cast<float*>(p[3]);tmp[row*80+chunk]=specialised::subtree(2560,chunk,[&](int k){float v=get(x,row*2560+k);return v*v;});}
 static float inverse(std::span<void*const>p,unsigned row){return detmath::rsqrt(specialised::upper(static_cast<float*>(p[3])+row*80,80)/2560.f+1e-6f);}
 static void output(std::span<void*const>p,unsigned row,unsigned k,float inv){auto x=static_cast<const uint16_t*>(p[0]);auto w=static_cast<const float*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);unsigned i=row*2560+k;y[i]=iq3::bf16_bits((get(x,i)*inv)*(w[i]+0.f));}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{if(!*static_cast<uint32_t*>(p[5])||error(p[4]))return;if(*static_cast<uint32_t*>(p[6])>=4096){fail(p[4]);return;}for(unsigned r=0;r<4;++r){for(unsigned c=0;c<80;++c)subtree(p,r,c);float inv=inverse(p,r);for(unsigned k=0;k<2560;++k)output(p,r,k,inv);}}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{std::array<void*,7>a;std::copy_n(p.begin(),7,a.begin());return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<float,1>inv(1,h);h.parallel_for(sycl::nd_range<1>(4*128,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{unsigned lane=it.get_local_linear_id(),r=it.get_group_linear_id();if(!lane)inv[0]=float(!*static_cast<uint32_t*>(a[5])||error(a[4]));it.barrier(sycl::access::fence_space::local_space);if(inv[0])return;it.barrier(sycl::access::fence_space::local_space);if(*static_cast<uint32_t*>(a[6])>=4096){if(!lane&&!r)fail(a[4]);return;}if(lane<80)subtree(a,r,lane);it.barrier(sycl::access::fence_space::global_and_local);if(!lane)inv[0]=inverse(a,r);it.barrier(sycl::access::fence_space::local_space);for(unsigned k=lane;k<2560;k+=128)output(a,r,k,inv[0]);});});}
#endif
};
struct MoeTail final:Base {
 static void element(std::span<void*const>p,unsigned k){auto y=static_cast<const uint16_t*>(p[0]);auto prob=static_cast<const float*>(p[1]);auto shared=static_cast<const uint16_t*>(p[2]);auto gate=static_cast<const uint16_t*>(p[3]);auto mix=static_cast<uint16_t*>(p[4]);auto out=static_cast<uint16_t*>(p[5]);auto streams=static_cast<uint16_t*>(p[6]);auto inject=static_cast<const uint16_t*>(p[7]);float sum=0;for(unsigned e=0;e<10;++e)sum=sum+get(y,e*2560+k)*prob[e];mix[k]=iq3::bf16_bits(sum);if(!*static_cast<uint32_t*>(p[9])||error(p[8]))return;if(*static_cast<uint32_t*>(p[10])>=4096){if(!k)fail(p[8]);return;}float selected=0.f+get(mix,k)*1.f;float v=bf(selected)+bf(get(shared,k)*ng::sigmoid(get(gate,0)));out[k]=iq3::bf16_bits(v);for(unsigned h=0;h<4;++h){unsigned i=h*2560+k;streams[i]=iq3::bf16_bits(get(streams,i)+get(out,k)*(2.f*ng::sigmoid(get(inject,h)/4.f)));}}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{for(unsigned k=0;k<2560;++k)element(p,k);}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{std::array<void*,11>a;std::copy_n(p.begin(),11,a.begin());return q.submit([&](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::range<1>(2560),[=](sycl::id<1>i){element(a,i[0]);});});}
#endif
};
}
